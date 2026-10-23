#!/usr/bin/env python3
"""Rebuild the audition loops for case 001.

Evidence only — this is the clip cutter used for the human gates, not the repair
pipeline. It reads the take and its Demucs vocal stem; it writes new files only.

    python3 make_loops.py --original /path/to/take.wav \
        --vocals /path/to/htdemucs/<stem>/vocals.wav \
        --out ../review

The ladder (wide -> narrow):

  L1  126.60–129.18  whole phrase, including the continuous note
  L2  126.60–127.72  فَأَدُّو; keeps the original note
  L3  127.18–127.65  دُّو (the syllable; the floor)

See ../spec/repair_spec.draft.json.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import soundfile as sf

LINE = (123.00, 129.20)
PHRASE = (124.50, 129.50)
WORD = (126.79, 128.13)
L1 = (126.60, 129.18)
L2 = (126.60, 127.72)
L3 = (127.18, 127.65)
DONOR = (175.60, 178.50)
DONOR_GEM = (176.15, 176.75)
TARGET_GEM = (127.05, 127.65)


def span(a: float, b: float) -> str:
    return f"{a:.2f}_{b:.2f}"


def cut(y: np.ndarray, sr: int, a: float, b: float) -> np.ndarray:
    return y[int(round(a * sr)): int(round(b * sr))]


def save(out: Path, name: str, y: np.ndarray, sr: int) -> None:
    sf.write(out / name, y, sr, subtype="PCM_16")
    print(f"{name:52s} {len(y) / sr:6.3f}s  {sr} Hz")


def loop(y: np.ndarray, sr: int, a: float, b: float, n: int = 3,
         gap_s: float = 0.35) -> np.ndarray:
    seg = cut(y, sr, a, b)
    gap = np.zeros((int(gap_s * sr), y.shape[1]), dtype=y.dtype)
    return np.concatenate([x for _ in range(n) for x in (seg, gap)][:-1])


def marked(y: np.ndarray, sr: int, a: float, b: float, marks) -> np.ndarray:
    seg = cut(y, sr, a, b).copy()
    n = int(0.04 * sr)
    t = np.arange(n) / sr
    burst = (0.12 * np.sin(2 * np.pi * 1800 * t) * np.hanning(n))[:, None]
    for m in dict.fromkeys(marks):
        i = int(round((m - a) * sr))
        seg[i:i + n] += burst.astype(seg.dtype)
    return seg


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--original", required=True, help="the take (full mix)")
    ap.add_argument("--vocals", required=True, help="Demucs vocal stem of the take")
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent.parent / "review"))
    args = ap.parse_args()

    mix, sr = sf.read(args.original, dtype="float32", always_2d=True)
    voc, vsr = sf.read(args.vocals, dtype="float32", always_2d=True)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    for tag, y, s in (("mix", mix, sr), ("vocal", voc, vsr)):
        save(out, f"00_{tag}_phrase_{span(*PHRASE)}.wav", cut(y, s, *PHRASE), s)
        save(out, f"01_{tag}_line_{span(*LINE)}.wav", cut(y, s, *LINE), s)
        for name, unit in (("L1", L1), ("L2", L2), ("L3", L3)):
            save(out, f"02_{tag}_unit{name}_{span(*unit)}.wav", cut(y, s, *unit), s)
            save(out, f"03{name}_{tag}_loop3.wav", loop(y, s, *unit), s)
        save(out, f"04_L1_{tag}_marked_{span(*L1)}.wav",
             marked(y, s, 125.8, 129.5, (L1[0], WORD[0], L1[1])), s)
        save(out, f"04_L2_{tag}_marked_{span(*L2)}.wav",
             marked(y, s, 125.8, 129.5, (L2[0], WORD[0], L2[1])), s)
        save(out, f"05_{tag}_donor_geminate_{span(*DONOR)}.wav", cut(y, s, *DONOR), s)
        # locating montage only — not a review clip (guide §8: judge on the line)
        gap = np.zeros((int(0.45 * s), y.shape[1]), dtype=y.dtype)
        montage = np.concatenate([cut(y, s, *WORD), gap, cut(y, s, *L1),
                                  gap, cut(y, s, *L2), gap, cut(y, s, *L3), gap], 0)
        save(out, f"10_{tag}_QUICK_word_L1_L2_L3.wav", montage, s)

    save(out, "07_vocal_target_geminate_loop4.wav", loop(voc, vsr, *TARGET_GEM, 4, 0.30), vsr)
    save(out, "07_vocal_donor_geminate_loop4.wav", loop(voc, vsr, *DONOR_GEM, 4, 0.30), vsr)


if __name__ == "__main__":
    main()
