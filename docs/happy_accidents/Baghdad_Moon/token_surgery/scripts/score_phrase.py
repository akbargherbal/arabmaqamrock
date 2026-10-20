#!/usr/bin/env python3
"""Score full-tail takes against the original over the outro phrase.

Metrics are computed on 10 ms log-energy envelopes:
  phrase 202.26-207.74, word 202.26-204.54, allah 204.54-204.98,
  yinz 204.98-207.74, plus the worst 100 ms level drop inside the phrase.

Usage: python3 score_phrase.py ORIGINAL.wav OUT.json TAKE.wav [TAKE.wav ...]
"""
import json
import os
import sys

import numpy as np
import soundfile as sf

HOP = 0.01
WINDOWS = {
    "word": (202.26, 204.54),
    "allah": (204.54, 204.98),
    "yinz": (204.98, 207.74),
    "phrase": (202.26, 207.74),
}


def envelope(x, sr):
    h = int(HOP * sr)
    n = len(x) // h
    return 20 * np.log10(np.sqrt(np.mean(x[: n * h].reshape(n, h) ** 2, axis=1)) + 1e-9)


def best_lag(a, b, lo=-20, hi=21):
    x = a - a.mean()
    y = b - b.mean()
    lags = list(range(lo, hi))
    cc = [np.corrcoef(x, np.roll(y, l))[0, 1] for l in lags]
    i = int(np.argmax(cc))
    return lags[i] * 10, float(cc[i])


def main(orig_path, out_json, takes):
    o, sr = sf.read(orig_path, dtype="int16", always_2d=True)
    eo = envelope(o.astype(np.float64).mean(1), sr)
    t = np.arange(len(eo)) * HOP
    rows = []
    for p in takes:
        y, sr2 = sf.read(p, dtype="int16", always_2d=True)
        assert sr2 == sr, (p, sr, sr2)
        ey = envelope(y.astype(np.float64).mean(1), sr)
        d = {"file": p, "seed": os.path.basename(p).replace("e2_ar_", "").replace(".wav", "")}
        for lbl, (a, b) in WINDOWS.items():
            m = (t >= a) & (t < b)
            lag, c = best_lag(eo[m], ey[m])
            d[lbl + "_corr"] = round(c, 3)
            d[lbl + "_lag_ms"] = lag
            d[lbl + "_rms_db"] = round(float(ey[m].mean() - eo[m].mean()), 2)
        m = (t >= 202.26) & (t < 207.74)
        k = 10
        r = (np.convolve(ey[m], np.ones(k) / k, "valid") -
             np.convolve(eo[m], np.ones(k) / k, "valid"))
        d["worst100ms_db"] = round(float(r.min()), 2)
        rows.append(d)
    rows.sort(key=lambda x: -x["phrase_corr"])
    json.dump(rows, open(out_json, "w"), indent=1)
    print(f"{'seed':15s} {'phr_c':>6s} {'lag':>5s} {'word_c':>7s} {'allah':>6s} {'yinz':>6s} {'worst100':>9s} {'rms':>6s}")
    for d in rows:
        print(f"{d['seed']:15s} {d['phrase_corr']:6.3f} {d['phrase_lag_ms']:4d}ms "
              f"{d['word_corr']:7.3f} {d['allah_corr']:6.3f} {d['yinz_corr']:6.3f} "
              f"{d['worst100ms_db']:9.2f} {d['phrase_rms_db']:6.2f}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3:])
