#!/usr/bin/env python3
"""Build the audition clips for case 002 (abu01, `وَالْأَجْدَادِ`).

Evidence only: this is the clip cutter for the human gates, not the repair
pipeline. It reads the take and its Demucs vocal stem and writes new files.

    python3 make_loops.py \
        --original /tmp/opencode/abu01/abu01_a01_3285212580.wav \
        --vocals  ~/Jupyter_Notebooks/OpenCode/yue2-karaoke-align/work/stems/htdemucs/abu01_a01_3285212580/vocals.wav \
        --out ../review

Everything is labelled by what it is for, not by the edit:
  01  the whole line, in context   -> judge the word, the tail and the join
  02  the word alone               -> locate the defect
  03  the word x3                  -> the defect, repeated
  04  correct د vs wrong ج         -> confirm the class (same take)
  05  the second chorus occurrence -> is it wrong there too?
  06  the word, 0.75x              -> hear the consonant
  07  the two candidate units      -> approve the unit
  08  the tail alone               -> is the tail correct? keep or replace
"""
from __future__ import annotations

import argparse
from pathlib import Path

import librosa
import numpy as np
import soundfile as sf

SR = 48000

# timeline (seconds) — see intake/alignment.md
LINE = (106.10, 113.30)
WORD = (109.10, 112.70)
UNIT_L1 = (108.88, 112.70)   # whole word incl. the sustained tail
UNIT_L2 = (108.88, 111.40)   # word up to the start of the sustain; keeps the tail
TAIL = (111.30, 113.30)
REF = (97.03, 98.81)         # الْأَجْسَادِ — correct final د, same take
CH2_LINE = (197.40, 202.90)
CH2_WORD = (200.10, 202.80)


def load(path: Path) -> np.ndarray:
    y, sr = sf.read(path, always_2d=True)
    if sr != SR:
        y = librosa.resample(y.T, orig_sr=sr, target_sr=SR).T
    return y.astype(np.float32)


def cut(y: np.ndarray, a: float, b: float) -> np.ndarray:
    return y[int(round(a * SR)): int(round(b * SR))]


def gap(seconds: float) -> np.ndarray:
    return np.zeros((int(seconds * SR), 2), dtype=np.float32)


def loop(y: np.ndarray, a: float, b: float, n: int = 3, g: float = 0.45) -> np.ndarray:
    seg = cut(y, a, b)
    return np.concatenate([x for _ in range(n) for x in (seg, gap(g))][:-1])


def pair(y: np.ndarray, ref: tuple[float, float], tgt: tuple[float, float],
         n: int = 2, g: float = 0.5) -> np.ndarray:
    parts = []
    for _ in range(n):
        parts += [cut(y, *ref), gap(g), cut(y, *tgt), gap(g * 1.4)]
    return np.concatenate(parts[:-1])


def save(out: Path, name: str, y: np.ndarray) -> None:
    sf.write(out / name, np.clip(y, -1, 1), SR, subtype="PCM_16")
    print(f"{name:52s} {len(y) / SR:6.2f}s")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--original", required=True)
    ap.add_argument("--vocals", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    mix = load(Path(args.original).expanduser())
    voc = load(Path(args.vocals).expanduser())
    print(f"mix {len(mix)/SR:.2f}s  vocal {len(voc)/SR:.2f}s")

    save(out, "01_mix_line_106.10_113.30.wav", cut(mix, *LINE))
    save(out, "01_vocal_line_106.10_113.30.wav", cut(voc, *LINE))

    save(out, "02_mix_word_109.10_112.70.wav", cut(mix, *WORD))
    save(out, "02_vocal_word_109.10_112.70.wav", cut(voc, *WORD))

    save(out, "03_vocal_word_loop3.wav", loop(voc, *WORD, n=3))

    save(out, "04_vocal_correct_then_wrong.wav", pair(voc, REF, WORD, n=2))
    save(out, "04_mix_correct_then_wrong.wav", pair(mix, REF, WORD, n=2))

    save(out, "05_mix_chorus2_line_197.40_202.90.wav", cut(mix, *CH2_LINE))
    save(out, "05_vocal_chorus2_word_200.10_202.80.wav", cut(voc, *CH2_WORD))

    slow = librosa.resample(cut(voc, *WORD).T, orig_sr=SR, target_sr=int(SR / 0.75)).T
    save(out, "06_vocal_word_slow075.wav", slow)

    save(out, "07_mix_unitL1_108.88_112.70.wav", cut(mix, *UNIT_L1))
    save(out, "07_mix_unitL2_108.88_111.40.wav", cut(mix, *UNIT_L2))

    save(out, "08_vocal_tail_111.30_113.30.wav", cut(voc, *TAIL))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
