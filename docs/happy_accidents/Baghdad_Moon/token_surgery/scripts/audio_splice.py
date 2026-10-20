#!/usr/bin/env python3
"""Local comp: graft corrected regions from a token-surgery render into the original.

Token surgery re-decodes the whole waveform (the NAR flow is globally coupled), so
a candidate differs from the original everywhere at the sample level even though
the perceptual change is concentrated at the edit. For delivery we only want the
corrected word: take the candidate's audio around each edited token range and
crossfade it into the untouched original, at low-energy points (consonant gaps),
as in normal vocal comping.

Everything outside the comp regions stays bit-identical to the original.

Usage:
    python3 audio_splice.py ORIGINAL.wav CANDIDATE.wav OUT.wav \
        --tokens tokens.json --baseline tokens_baseline.json \
        [--margin 0.30] [--fade 0.04] [--snap 0.12]
"""
from __future__ import annotations

import argparse
import json

import numpy as np
import soundfile as sf


def changed_ranges(tokens, baseline):
    diff = [i for i, (a, b) in enumerate(zip(baseline, tokens)) if a != b]
    ranges = []
    for i in diff:
        if ranges and i <= ranges[-1][1] + 1:
            ranges[-1][1] = i
        else:
            ranges.append([i, i])
    return ranges  # inclusive frame indices


def rms_env(x, sr, hop=0.01):
    h = max(1, int(hop * sr))
    n = len(x) // h
    return np.sqrt(np.mean(x[: n * h].reshape(n, h) ** 2, axis=1)), h


def snap_quiet(x, sr, t, window=0.12):
    """Move a cut point to the quietest 10 ms frame within +/- window seconds."""
    env, hop = rms_env(x, sr)
    lo = max(0, int((t - window) * sr) // hop)
    hi = min(len(env), int((t + window) * sr) // hop + 1)
    if hi <= lo:
        return t
    idx = lo + int(np.argmin(env[lo:hi]))
    return (idx * hop + hop / 2) / sr


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("original")
    ap.add_argument("candidate")
    ap.add_argument("out")
    ap.add_argument("--tokens", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--margin", type=float, default=0.30)
    ap.add_argument("--fade", type=float, default=0.04)
    ap.add_argument("--snap", type=float, default=0.12)
    a = ap.parse_args()

    orig, sr = sf.read(a.original, dtype="int16", always_2d=True)
    cand, sr2 = sf.read(a.candidate, dtype="int16", always_2d=True)
    assert sr == sr2 and orig.shape == cand.shape, (orig.shape, cand.shape, sr, sr2)
    out = orig.copy()

    tokens = json.load(open(a.tokens))
    baseline = json.load(open(a.baseline))
    fps = 25.0
    regions = []
    for f0, f1 in changed_ranges(tokens, baseline):
        t0 = max(0.0, f0 / fps - a.margin)
        t1 = min(len(orig) / sr, (f1 + 1) / fps + a.margin)
        # snap cuts to quiet points, but never inside the changed frames
        s0 = snap_quiet(orig.astype(np.float32).mean(1), sr, t0, a.snap)
        s1 = snap_quiet(orig.astype(np.float32).mean(1), sr, t1, a.snap)
        s0 = min(max(s0, t0 - a.snap), f0 / fps)
        s1 = max(min(s1, t1 + a.snap), (f1 + 1) / fps)
        regions.append((s0, s1))

    # merge overlapping/nearby regions (a word can have a 1-frame gap)
    regions.sort()
    merged = []
    for s0, s1 in regions:
        if merged and s0 <= merged[-1][1] + 0.10:
            merged[-1] = (merged[-1][0], max(merged[-1][1], s1))
        else:
            merged.append((s0, s1))
    regions = merged

    fade = a.fade
    for t0, t1 in regions:
        i0, i1 = int(t0 * sr), int(t1 * sr)
        nf = int(fade * sr)
        a_seg = orig[i0:i1].astype(np.float64)
        b_seg = cand[i0:i1].astype(np.float64)
        w = np.ones((i1 - i0, 1))
        m = min(nf, (i1 - i0) // 2)
        if m > 0:
            ramp = 0.5 - 0.5 * np.cos(np.pi * np.arange(m) / m)
            w[:m, 0] = ramp
            w[-m:, 0] = ramp[::-1]
        out[i0:i1] = np.clip(np.round(a_seg * (1 - w) + b_seg * w), -32768, 32767).astype(np.int16)

    sf.write(a.out, out, sr, subtype="PCM_16")

    # verification: samples outside the comp regions must be identical
    mask = np.ones(len(orig), dtype=bool)
    for t0, t1 in regions:
        mask[int(t0 * sr):int(t1 * sr)] = False
    ident = np.array_equal(out[mask], orig[mask])
    d = np.abs(out.astype(np.int32) - orig.astype(np.int32)).max(axis=1)
    changed = np.where(d > 0)[0]
    span = (changed[0] / sr, changed[-1] / sr) if len(changed) else None
    print(json.dumps({
        "out": a.out,
        "regions_s": [[round(x, 3), round(y, 3)] for x, y in regions],
        "identical_outside_regions": bool(ident),
        "first_changed_s": round(span[0], 3) if span else None,
        "last_changed_s": round(span[1], 3) if span else None,
        "n_changed_samples": int(len(changed)),
    }))


if __name__ == "__main__":
    main()
