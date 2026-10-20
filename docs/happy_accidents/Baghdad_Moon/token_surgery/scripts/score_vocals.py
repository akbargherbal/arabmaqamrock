#!/usr/bin/env python3
"""Score takes on the lead vocal only (Demucs stems), over the outro phrase.

This removes the confound of the model's different instrumental when choosing a
phrase-level take. Envelopes are 10 ms log-RMS of the vocal stem.

Usage:
  python3 score_vocals.py ORIGINAL_VOCALS.wav OUT.json STEMDIR [STEMDIR ...]
Each STEMDIR must contain vocals.wav (Demucs).
"""
import json
import os
import sys

import librosa
import numpy as np
import soundfile as sf

HOP = 0.01
SR = 48000
WINDOWS = {
    "word": (202.26, 204.54),
    "allah": (204.54, 204.98),
    "yinz": (204.98, 207.74),
    "phrase": (202.26, 207.74),
}


def load48(path, n=None):
    y, sr = sf.read(path, dtype="float64", always_2d=True)
    if sr != SR:
        y = librosa.resample(y.T, orig_sr=sr, target_sr=SR, axis=1).T
    if n is not None:
        if len(y) < n:
            y = np.pad(y, ((0, n - len(y)), (0, 0)))
        y = y[:n]
    return y


def envelope(x):
    h = int(HOP * SR)
    n = len(x) // h
    return 20 * np.log10(np.sqrt(np.mean(x[: n * h].reshape(n, h) ** 2, axis=1)) + 1e-9)


def best_lag(a, b, lo=-20, hi=21):
    x = a - a.mean()
    y = b - b.mean()
    lags = list(range(lo, hi))
    cc = [np.corrcoef(x, np.roll(y, l))[0, 1] for l in lags]
    i = int(np.argmax(cc))
    return lags[i] * 10, float(cc[i])


def main(orig_vocals, out_json, stemdirs):
    vo = load48(orig_vocals)
    eo = envelope(vo.mean(1))
    t = np.arange(len(eo)) * HOP
    rows = []
    for d in stemdirs:
        v = load48(os.path.join(d, "vocals.wav"), len(vo))
        ey = envelope(v.mean(1))
        row = {"dir": d, "seed": os.path.basename(d.rstrip("/"))}
        for lbl, (a, b) in WINDOWS.items():
            m = (t >= a) & (t < b)
            lag, c = best_lag(eo[m], ey[m])
            row[lbl + "_corr"] = round(c, 3)
            row[lbl + "_lag_ms"] = lag
            row[lbl + "_rms_db"] = round(float(ey[m].mean() - eo[m].mean()), 2)
        m = (t >= 202.26) & (t < 207.74)
        k = 10
        r = (np.convolve(ey[m], np.ones(k) / k, "valid") -
             np.convolve(eo[m], np.ones(k) / k, "valid"))
        row["worst100ms_db"] = round(float(r.min()), 2)
        rows.append(row)
    rows.sort(key=lambda x: -x["phrase_corr"])
    json.dump(rows, open(out_json, "w"), indent=1)
    print(f"{'seed':14s} {'phr_c':>6s} {'lag':>5s} {'word_c':>7s} {'allah':>6s} {'yinz':>6s} {'worst100':>9s} {'rms':>6s}")
    for d in rows:
        print(f"{d['seed']:14s} {d['phrase_corr']:6.3f} {d['phrase_lag_ms']:4d}ms "
              f"{d['word_corr']:7.3f} {d['allah_corr']:6.3f} {d['yinz_corr']:6.3f} "
              f"{d['worst100ms_db']:9.2f} {d['phrase_rms_db']:6.2f}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3:])
