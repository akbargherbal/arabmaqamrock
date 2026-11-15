# Defect card — CFG 1.5 take (`repro_abc_cfg15`)

One card for the active take. Gate A: this card must be right before any render.

| field | value |
|---|---|
| **song / take** | Abu al-Ala', `repro_abc_cfg15.wav`, T4 CFG 1.5 ABC take |
| **section / line** | opening verse (lyrics line 1; aligner line 0): `غَيْرُ مُجْدٍ فِي مِلَّتِي وَاعْتِقَادِي` |
| **target word** | **`مِلَّتِي`** |
| **occurrence** | **1 of 2** — the repeated verse (lyrics line 3; aligner line 2) sings it **correctly** |
| **heard** | **“لتي”** — the initial **م** is missing |
| **target** | `مِلَّتِي` with a clean initial /m/ |
| **alignment box** | 27.782 – 28.902 s (late by ~0.26 s; **not a cut**) |
| **measured word** | ~27.52 – 28.90 s on the vocal stem |
| **previous word** | `فِي`: /f/ onset 27.00, vowel 27.15–27.48 — correct, keep it in B |
| **next word** | `وَاعْتِقَادِي` starts ~29.00 s — correct, do not touch |
| **comp B (planned)** | 27.50 – 28.95 s (word onset; keeps `فِي`; end follows the candidate, ≤28.98) |
| **comp B (used)** | **27.46 – 28.98 s** — candidate s2's nasal onset begins ~27.45, so 27.50 would cut the م |
| **comp D (fallback)** | 27.00 – 28.95 s (starts at the /f/ onset; replaces `فِي` + `مِلَّتِي`); RUN3 used 27.00 – 28.98, not chosen |
| **comp A (last resort)** | 27.10 – 28.95 s (starts inside the `فِي` vowel; not used) |
| **correct reference** | occurrence 2, ~41.13 – 42.55 s (box 41.423 – 42.244) — ear/spectrum only, no donor splice |
| **must not change** | `فِي`; `وَاعْتِقَادِي`; the rest of the track; the instrumental; timing |

## What only the ear can confirm

1. The opening occurrence is the wrong one; the repeated verse is correct.
   **Confirmed by the user, 2026-11-15.**
2. The missing sound is the initial **م** (“لتي”), not a different vowel.
   **Confirmed by the user.**
3. After the repair, the **م** is audible and the join is inaudible.
   **Closed — the user heard the م and answered “No seam — accept 02.”**
   Final: `B_s2_3285212582.wav`, sha `ae9217c1…87a654`, comp 27.46–28.98 s.

## Evidence

- `words_cfg15.json` — full 141-word alignment of the CFG 1.5 take.
- `measure_cfg15.json` — the measured map and the generation window.
- Stem: `yue2-karaoke-align/work/stems/htdemucs/repro_abc_cfg15_3285212580/vocals.wav`
  (Demucs 4.1.0, 44.1 kHz).
