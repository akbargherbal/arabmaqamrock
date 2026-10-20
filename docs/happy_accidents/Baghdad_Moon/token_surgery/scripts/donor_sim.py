#!/usr/bin/env python3
"""Compare candidate vocal windows against same-take donor instances via MFCC-DTW.

The donor instances are known-correct occurrences in the same take:
  e1 (عَلَيْهِ)  B Outro    frames [5025,5056) = 201.00-202.24 s
  e2 (فَإِنَّ)   B Verse 2   frames [3962,3988) = 158.48-159.52 s

For each candidate we take the corresponding edited window from its demucs vocal
stem and report the normalized MFCC-DTW distance to the donor, alongside the
original's distance as a control. Lower = closer to the correct rendition.
Also reports how much the candidate differs from the original inside the edited
window (so a no-op edit is obvious).

Usage:
    python3 donor_sim.py --run-dir RUN_DIR --stems DIR_WITH_ORIGINAL_VOCALS
"""
from __future__ import annotations

import argparse
import json
import os

import numpy as np

# word windows (seconds) in the B take
WINDOWS = {
    "e1_word": {"cand": (157.25, 158.65), "donor": (200.95, 202.35)},
    "e1_final": {"cand": (158.15, 158.70), "donor": (201.85, 202.40)},
    "e2_onset": {"cand": (202.15, 202.90), "donor": (158.45, 159.20)},
    "e2_word": {"cand": (202.15, 204.65), "donor": (158.45, 159.65)},
}


def mfcc(y, sr, n_mfcc=20):
    import librosa
    m = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=n_mfcc, n_fft=512, hop_length=160)
    m = (m - m.mean(axis=1, keepdims=True)) / (m.std(axis=1, keepdims=True) + 1e-8)
    return m.T


def dtw_dist(a, b):
    import librosa
    D, wp = librosa.sequence.dtw(X=a.T, Y=b.T, metric="euclidean")
    return float(D[-1, -1] / len(wp))


def load(path, sr=16000):
    import librosa
    y, _ = librosa.load(path, sr=sr, mono=True)
    return y, sr


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--orig-stem", required=True)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    yo, sr = load(a.orig_stem)
    rows = []
    jobs = [("ORIGINAL", a.orig_stem)]
    for name in sorted(os.listdir(a.run_dir)):
        p = os.path.join(a.run_dir, name, "eval", "demucs", "htdemucs", name, "vocals.wav")
        if os.path.exists(p):
            jobs.append((name, p))

    for name, path in jobs:
        y = yo if name == "ORIGINAL" else load(path)[0]
        row = {"id": name}
        for key, w in WINDOWS.items():
            lo, hi = w["cand"]
            dlo, dhi = w["donor"]
            seg = y[int(lo * sr):int(hi * sr)]
            don = yo[int(dlo * sr):int(dhi * sr)]
            d = dtw_dist(mfcc(seg, sr), mfcc(don, sr))
            ref = yo[int(lo * sr):int(hi * sr)]
            n = min(len(seg), len(ref))
            # local change vs original (dBFS RMS of the difference)
            diff = seg[:n] - ref[:n]
            rms = 20 * np.log10(np.sqrt(np.mean(diff ** 2)) + 1e-12)
            row[key] = {"dtw": round(d, 3), "change_rms_db": round(float(rms), 2)}
        rows.append(row)
        print(json.dumps(row, ensure_ascii=False))

    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=2)
        print(f"\nwrote {a.out}")


if __name__ == "__main__":
    main()
