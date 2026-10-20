#!/usr/bin/env python3
"""Comp a time region from a candidate take into the original.

Two modes:
  full  - comp the candidate's full mix (simple, but replaces music too)
  vocal - comp only the lead-vocal stem, keeping the original instrumental
          (needs Demucs stems for original and candidate; 4-stem htdemucs)

Boundaries are explicit times, so joins can be placed at phrase edges instead
of token-derived word +/- margin. Optional linear dB gain ramp across the region
matches the candidate level to the original at both boundaries.

Outside the region the output is a byte-for-byte copy of the original.
"""
from __future__ import annotations

import argparse
import json
import os

import numpy as np
import soundfile as sf

try:
    import librosa
except Exception:  # pragma: no cover
    librosa = None


def db(x):
    return 20.0 * np.log10(max(x, 1e-12))


def rms(x):
    return float(np.sqrt(np.mean(np.square(x))))


def resample_to(x, sr_in, sr_out, n_out):
    if sr_in == sr_out:
        y = x
    else:
        if librosa is None:
            raise RuntimeError("librosa is required to resample stems")
        y = librosa.resample(x.T, orig_sr=sr_in, target_sr=sr_out, axis=1).T
    if len(y) < n_out:
        y = np.pad(y, ((0, n_out - len(y)), (0, 0)))
    return y[:n_out]


def load_stem(path, n_out, sr_out):
    x, sr = sf.read(path, dtype="float64", always_2d=True)
    return resample_to(x, sr, sr_out, n_out) * 32768.0


def fade_weights(n, nf_in, nf_out=None):
    if nf_out is None:
        nf_out = nf_in
    w = np.ones(n)
    mi = min(nf_in, n // 2)
    mo = min(nf_out, n // 2)
    if mi > 0:
        w[:mi] = 0.5 - 0.5 * np.cos(np.pi * np.arange(mi) / mi)
    if mo > 0:
        w[-mo:] = (0.5 - 0.5 * np.cos(np.pi * np.arange(mo) / mo))[::-1]
    return w[:, None]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("original")
    ap.add_argument("candidate")
    ap.add_argument("out")
    ap.add_argument("--mode", choices=["full", "vocal"], default="full")
    ap.add_argument("--orig-stems", help="Demucs dir for the original (vocal mode)")
    ap.add_argument("--cand-stems", help="Demucs dir for the candidate (vocal mode)")
    ap.add_argument("--start", type=float, required=True)
    ap.add_argument("--end", type=float, required=True)
    ap.add_argument("--fade", type=float, default=0.08)
    ap.add_argument("--fade-in", type=float, help="override fade at region start (s)")
    ap.add_argument("--fade-out", type=float, help="override fade at region end (s)")
    ap.add_argument("--gain-ramp", action="store_true",
                    help="linear dB gain ramp matching candidate to original at edges")
    ap.add_argument("--max-gain-db", type=float, default=6.0)
    ap.add_argument("--probe", type=float, default=0.05,
                    help="window for boundary level matching")
    ap.add_argument("--shift-ms", type=float, default=0.0,
                    help="shift the candidate vocal by this many ms (negative = earlier)")
    args = ap.parse_args()

    orig, sr = sf.read(args.original, dtype="int16", always_2d=True)
    cand, sr2 = sf.read(args.candidate, dtype="int16", always_2d=True)
    assert sr == sr2 and orig.shape == cand.shape, (orig.shape, cand.shape, sr, sr2)
    n = len(orig)
    i0, i1 = int(round(args.start * sr)), int(round(args.end * sr))
    assert 0 <= i0 < i1 <= n
    nfi = int((args.fade_in if args.fade_in is not None else args.fade) * sr)
    nfo = int((args.fade_out if args.fade_out is not None else args.fade) * sr)

    if args.mode == "full":
        a = orig.astype(np.float64)
        b = cand.astype(np.float64)
        # boundary gains from short RMS probes just inside the region
        p = int(args.probe * sr)
        g0 = db(rms(a[i0:i0 + p])) - db(rms(b[i0:i0 + p]))
        g1 = db(rms(a[i1 - p:i1])) - db(rms(b[i1 - p:i1]))
        g0 = float(np.clip(g0, -args.max_gain_db, args.max_gain_db))
        g1 = float(np.clip(g1, -args.max_gain_db, args.max_gain_db))
        if args.gain_ramp:
            dbg = np.linspace(g0, g1, i1 - i0)[:, None]
            b[i0:i1] = b[i0:i1] * (10.0 ** (dbg / 20.0))
        seg = a[i0:i1] * (1 - fade_weights(i1 - i0, nfi, nfo)) + b[i0:i1] * fade_weights(i1 - i0, nfi, nfo)
        out = orig.copy()
        out[i0:i1] = np.clip(np.round(seg), -32768, 32767).astype(np.int16)
        detail = {"mode": "full", "gain_start_db": round(g0, 2), "gain_end_db": round(g1, 2)}
    else:
        if not (args.orig_stems and args.cand_stems):
            raise SystemExit("vocal mode needs --orig-stems and --cand-stems")
        vo = load_stem(os.path.join(args.orig_stems, "vocals.wav"), n, sr)
        vc = load_stem(os.path.join(args.cand_stems, "vocals.wav"), n, sr)
        k = int(round(args.shift_ms * sr / 1000.0))
        if k > 0:
            vc = np.pad(vc, ((k, 0), (0, 0)))[:n]
        elif k < 0:
            vc = np.pad(vc[-k:], ((0, n + k), (0, 0)))[:n]
        p = int(args.probe * sr)
        g0 = db(rms(vo[i0:i0 + p])) - db(rms(vc[i0:i0 + p]))
        g1 = db(rms(vo[i1 - p:i1])) - db(rms(vc[i1 - p:i1]))
        g0 = float(np.clip(g0, -args.max_gain_db, args.max_gain_db))
        g1 = float(np.clip(g1, -args.max_gain_db, args.max_gain_db))
        if args.gain_ramp:
            dbg = np.linspace(g0, g1, i1 - i0)[:, None]
        else:
            dbg = np.zeros((i1 - i0, 1))
        vcg = vc[i0:i1] * (10.0 ** (dbg / 20.0))
        w = fade_weights(i1 - i0, nfi, nfo)
        vnew = vo[i0:i1] * (1 - w) + vcg * w
        seg = orig[i0:i1].astype(np.float64) - vo[i0:i1] + vnew
        out = orig.copy()
        out[i0:i1] = np.clip(np.round(seg), -32768, 32767).astype(np.int16)
        detail = {"mode": "vocal", "gain_start_db": round(g0, 2), "gain_end_db": round(g1, 2)}

    sf.write(args.out, out, sr, subtype="PCM_16")

    d = np.abs(out.astype(np.int32) - orig.astype(np.int32)).max(1)
    nz = np.where(d > 0)[0]
    changed = [round(float(nz[0]) / sr, 4), round(float(nz[-1]) / sr, 4)] if len(nz) else []
    # level step at each edge: compare 30 ms either side in the output vs original
    q = int(0.03 * sr)
    steps = {}
    for lbl, idx in (("start", i0), ("end", i1)):
        steps[lbl] = round(db(rms(out[max(0, idx - q):idx].astype(np.float64))) -
                           db(rms(orig[max(0, idx - q):idx].astype(np.float64))), 2)
    # outside identity
    mask = np.ones(n, bool)
    mask[i0:i1] = False
    outside = int(np.abs(out[mask].astype(np.int32) - orig[mask].astype(np.int32)).max()) if mask.any() else 0
    info = {
        "out": args.out,
        "region_s": [round(i0 / sr, 4), round(i1 / sr, 4)],
        "changed_span_s": changed,
        "n_changed_samples": int(len(nz)),
        "identical_outside_region": bool(outside == 0),
        "outside_max_abs_diff": outside,
        "edge_rms_step_db": steps,
        **detail,
    }
    print(json.dumps(info, indent=1))


if __name__ == "__main__":
    main()
