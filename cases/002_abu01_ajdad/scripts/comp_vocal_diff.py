#!/usr/bin/env python3
"""Vocal-only comp: new_mix = mix + (cand_voc - orig_voc) inside the region.

Everything is computed at 44.1 kHz (Demucs' rate) and the difference is
resampled to 48 kHz before it is added to the 48 kHz mix. Never
`no_vocals + candidate`.

Usage:
  comp.py --orig-mix M.wav --orig-voc V.wav --cand-voc C.wav \
          --start 27.50 --end 28.95 --cand-offset 26.88 --out OUT.wav \
          [--ramp 0.015] [--report report.json]
"""
import argparse, json, hashlib
import numpy as np
import soundfile as sf
from scipy.signal import resample_poly


def sha(path, n=None):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--orig-mix', required=True)
    ap.add_argument('--orig-voc', required=True)
    ap.add_argument('--cand-voc', required=True)
    ap.add_argument('--start', type=float, required=True)
    ap.add_argument('--end', type=float, required=True)
    ap.add_argument('--cand-offset', type=float, default=0.0,
                    help='track time of candidate sample 0')
    ap.add_argument('--out', required=True)
    ap.add_argument('--ramp', type=float, default=0.015)
    ap.add_argument('--report', default=None)
    a = ap.parse_args()

    mix, smix = sf.read(a.orig_mix, always_2d=True)
    ov, sov = sf.read(a.orig_voc, always_2d=True)
    cv, scv = sf.read(a.cand_voc, always_2d=True)
    assert sov == scv and sov != smix, (smix, sov, scv)
    sr = sov
    if mix.shape[1] == 1 and ov.shape[1] == 2:
        ov = ov[:, :1]
    if mix.shape[1] == 1 and cv.shape[1] == 2:
        cv = cv[:, :1]

    i0 = int(round(a.start * sr)); i1 = int(round(a.end * sr))
    j0 = int(round((a.start - a.cand_offset) * sr))
    j1 = int(round((a.end - a.cand_offset) * sr))
    assert j0 >= 0 and j1 <= len(cv), (j0, j1, len(cv), a.cand_offset)
    assert (j1 - j0) == (i1 - i0)
    diff = cv[j0:j1].astype(np.float64) - ov[i0:i1].astype(np.float64)

    # ramps on the difference so the seam is click-free
    n = int(round(a.ramp * sr))
    w = np.ones(len(diff))
    w[:n] = np.linspace(0.0, 1.0, n)
    w[-n:] = np.linspace(1.0, 0.0, n)
    diff *= w[:, None]

    # 44.1k -> 48k
    diff48 = resample_poly(diff, 480, 441, axis=0)
    m0 = int(round(a.start * 48000)); m1 = int(round(a.end * 48000))
    L = min(len(diff48), m1 - m0)
    if L < m1 - m0:
        diff48 = np.pad(diff48, ((0, m1 - m0 - L), (0, 0)))
        L = m1 - m0
    out = mix.copy()
    out[m0:m1] += diff48[:m1 - m0].astype(out.dtype)

    sf.write(a.out, out, 48000, subtype='PCM_16')

    # ---- verification -----------------------------------------------------
    back, sb = sf.read(a.out, always_2d=True)
    rep = {
        'out': a.out,
        'sr': sb,
        'duration': round(len(back) / sb, 6),
        'region_44k': [a.start, a.end],
        'cand_offset': a.cand_offset,
        'ramp_s': a.ramp,
        'sha256_out': sha(a.out),
        'diff_peak': float(np.abs(diff48).max()),
        'diff_rms': float(np.sqrt((diff48 ** 2).mean())),
    }
    # byte identity outside the region (allow 2 ms guard either side)
    g = int(0.002 * 48000)
    before = np.array_equal(back[:m0 - g], mix[:m0 - g])
    after = np.array_equal(back[m1 + g:], mix[m1 + g:])
    rep['identical_before_region'] = bool(before)
    rep['identical_after_region'] = bool(after)
    rep['identical_outside_region'] = bool(before and after)
    # inside-region change (sanity)
    rep['changed_inside_region'] = bool(not np.array_equal(back[m0:m1], mix[m0:m1]))
    if a.report:
        json.dump(rep, open(a.report, 'w'), indent=1)
    print(json.dumps(rep, indent=1))


if __name__ == '__main__':
    main()
