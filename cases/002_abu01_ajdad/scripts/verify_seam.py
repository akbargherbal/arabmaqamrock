#!/usr/bin/env python3
"""Seam verification for a comp: click, f0 step, RMS step on the resulting vocal."""
import sys, json
import numpy as np, soundfile as sf, librosa
from scipy.signal import resample_poly

def main(mix, orig_voc, cand_voc, start, end, label):
    m, sm = sf.read(mix, always_2d=True)
    ov, so = sf.read(orig_voc, always_2d=True)
    cv, sc = sf.read(cand_voc, always_2d=True)
    i0, i1 = int(round(start * so)), int(round(end * so))
    n = int(round(0.015 * so))
    d = cv[i0:i1].astype(np.float64) - ov[i0:i1].astype(np.float64)
    w = np.ones(len(d)); w[:n] = np.linspace(0, 1, n); w[-n:] = np.linspace(1, 0, n)
    d *= w[:, None]
    voc = ov.copy()
    voc[i0:i1] += d.astype(ov.dtype)

    out = {'label': label, 'start': start, 'end': end}
    hop = 441
    for name, s in (('before', start), ('after', end)):
        a = s - 0.12; b = s + 0.12
        seg = voc[int(a * so):int(b * so)].mean(1).astype(np.float32)
        f0 = librosa.pyin(seg, fmin=150, fmax=420, sr=so, frame_length=2048,
                          hop_length=hop, fill_na=np.nan)[0]
        f0 = f0[~np.isnan(f0)]
        rms = librosa.feature.rms(y=seg, frame_length=2048, hop_length=hop)[0]
        out[name] = {'f0_med': float(np.median(f0)) if len(f0) else None,
                     'rms_med': float(np.median(rms))}
    if out['before']['f0_med'] and out['after']['f0_med']:
        out['d_f0_cents'] = round(1200 * np.log2(out['after']['f0_med'] / out['before']['f0_med']), 2)
    out['d_rms_db'] = round(20 * np.log10(out['after']['rms_med'] / out['before']['rms_med']), 2)

    # click test on the 48k mix: worst sample-to-sample jump near the seam vs the region
    x = m.mean(1)
    j = np.abs(np.diff(x))
    def win(a, b): return float(j[int(a * sm):int(b * sm)].max())
    out['max_step_at_seams'] = max(win(start - 0.02, start + 0.02), win(end - 0.02, end + 0.02))
    out['max_step_region'] = win(start, end)
    out['click_ratio'] = round(out['max_step_at_seams'] / (out['max_step_region'] + 1e-12), 3)

    # broadband energy burst at the seam vs neighbours (10 ms)
    for nm, s in (('start', start), ('end', end)):
        a = s - 0.05; b = s + 0.05
        seg = m[int(a * sm):int(b * sm)].mean(1).astype(np.float32)
        r = librosa.feature.rms(y=seg, frame_length=480, hop_length=240)[0]
        out[f'{nm}_rms_series'] = [round(float(v), 4) for v in r]
    print(json.dumps(out, indent=1))

if __name__ == '__main__':
    mix, ov, cv, start, end, label = sys.argv[1:7]
    main(mix, ov, cv, float(start), float(end), label)
