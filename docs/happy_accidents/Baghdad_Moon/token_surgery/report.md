# Report — Baghdad Moon B: two mis-sung words (2026-10-20)

Target: `02-استيداع-قمر-بغداد-ولوعة-الوداع-B_1712905618`
Original WAV: `dbc00722534d5ee763ae54a048cd704eaa4c927e37834cd54542eaf379e0de42`
(unchanged, never overwritten).

Fixes attempted by length-preserving semantic-token surgery:

| id | word | sung | correct | frames |
|---|---|---|---|---|
| e1 | Verse 2 | `عَلِيمْ` (ends م) | `عَلَيْهِ` (ends ه) | `[3933,3964)` |
| e2 | Outro | `بِأَنَّ` (starts ب) | `فَإِنَّ` (starts ف) | `[5056,5114)` |

The Outro's `عَلَيْهِ` (between e2 and the preceding line) is the "muddy but
acceptable" instance and was **not** edited.

## 1. Gate results — both exact

| check | expected | observed | verdict |
|---|---|---|---|
| semantic-only re-run | `1b1aa3e2…`, 5397 frames, 1079/12 | identical, 5397, 1079/12, truncated 0 | **byte-identical** |
| full render from `tokens_baseline.json`, `min=max=5397` | `dbc00722…` | `dbc00722…` | **bit-identical** |

The prefix-capable sm75 binary (`4e1534f3…`, `git 58caf774`) runs correctly on
the T4. Batch mode is also exact: the same baseline tokens rendered through
`--request-sequence` are bit-identical too.

## 2. The 13 pre-computed splices

All rendered in one batch (single model load, sequential), exit 0. Every output
is 5397 frames / 41,448,748 bytes, and each render's exported `semantic.json`
matches its input token file exactly.

| candidate | overall corr | mean 5 s | worst 5 s | mel Δ out (dB) | mel Δ in (dB) | e1-final DTW | e2-onset DTW |
|---|---:|---:|---:|---:|---:|---:|---:|
| `e1_A_note` | 0.9922 | 0.9927 | 0.9317 | **0.090** | 0.443 | 4.459 | 5.327 |
| `e2_B_word` | 0.9907 | 0.9907 | 0.8104 | 0.102 | 1.910 | 4.754 | **3.544** |
| `e2_A_onset` | 0.9905 | 0.9905 | 0.8359 | 0.103 | 1.432 | 4.817 | 3.575 |
| `e2_A_onset_A` | 0.9915 | 0.9915 | 0.8582 | 0.103 | 1.372 | 4.524 | 5.883 (bad donor) |
| `e2_A_onset_C` | 0.9871 | 0.9870 | 0.8204 | 0.115 | 1.662 | 4.570 | 5.738 (bad donor) |
| `combo_e1_A_note__e2_A_onset` | 0.9851 | 0.9854 | 0.8377 | 0.120 | 1.641 | 4.581 | 3.522 |
| `combo_e1_A_note__e2_B_word` | 0.9828 | 0.9832 | 0.8016 | 0.126 | 2.166 | 4.731 | 3.497 |
| `e1_C_C` | 0.9858 | 0.9863 | 0.7951 | 0.134 | 1.728 | 4.985 | — |
| `e1_C_A` | 0.9704 | 0.9717 | 0.6567 | 0.159 | 2.242 | 5.729 | — |
| `e1_B_word` | 0.9746 | 0.9759 | 0.7399 | 0.161 | 1.289 | 4.726 | — |
| `combo_e1_B_word__e2_A_onset` | 0.9693 | 0.9703 | 0.7464 | 0.172 | 2.397 | 4.696 | 3.611 |
| `combo_e1_B_word__e2_B_word` | 0.9664 | 0.9676 | 0.7393 | 0.182 | 2.898 | 4.666 | 3.579 |
| `combo_e1_B_word__e2_A_onset_C` | 0.9681 | 0.9690 | 0.7564 | 0.193 | 2.594 | 4.727 | 5.693 (bad donor) |

Original control: e1-final DTW **4.482**, e2-onset DTW **5.244**.

### What this says

- **e2 is well supported.** `e2_B_word` and `e2_A_onset` move the onset from
  DTW **5.24 → 3.54 / 3.58** toward the known-correct B Verse 2 instance. The
  A/C-Outro donor variants move *away* (5.74–5.88), which shows the metric
  discriminates the right donor rather than just rewarding any change.
- **e1 is weaker evidence.** Its donor is the Outro, a different arrangement, so
  DTW is confounded. `e1_A_note` is marginally closer on the final note
  (4.459 vs 4.482); `e1_B_word` is not (4.726). Wide-context CTC shows the
  original's `عَلَيمِي` losing its `م` in both, but does not cleanly produce the
  Outro's `عَلَىيهٍ`.
- **CTC cannot confirm the e2 `ف`.** Phrase-level CTC separates the *known*
  correct/wrong instances in the original (Verse 2 → `فَاإِنَ`; Outro →
  `بِعِل`), but every e2 candidate still decodes with `ب` in the phrase window.
  Reported as-is; the DTW evidence is stronger and points the other way.

### Collateral damage (important)

Token surgery is **not sample-local**. Every candidate differs from the original
across the whole file because the NAR flow is globally coupled (a one-request
batch control with the baseline tokens is still bit-identical, so this is the
model, not batch RNG). Perceptually it is small:

- median mel Δ outside the edited regions: **0.034–0.071 dB**
- p95 outside: **0.33–0.82 dB**
- peak 1 s mel Δ lands exactly on the edited second (157/158 or 202 s)

## 3. Local comp (recommended delivery)

To make the repair genuinely surgical, the edited word is grafted back into the
**original** WAV with ~40 ms crossfades snapped to quiet points. Outside those
regions the output is **bit-identical** to the original (verified per file);
inside, the difference is real (−15 to −17 dB RMS, peaks near 0 dBFS).

Comp regions (seconds, absolute):

| hybrid | e1 region | e2 region |
|---|---|---|
| H1 `combo_e1_A_note__e2_A_onset` | 158.05–158.86 | 201.84–203.16 |
| H2 `combo_e1_A_note__e2_B_word` | 158.05–158.86 | 201.84–203.52 |
| H3 `combo_e1_B_word__e2_A_onset` | 157.00–158.86 | 201.84–203.16 |
| H4 `combo_e1_B_word__e2_B_word` | 157.00–158.86 | 201.84–203.52 |

Script: `happy_accident/audio_splice.py` (reusable).

## 4. Recommendation

- **H1** — least change: e1 final note only, e2 onset only. Best fidelity
  (mel Δ out 0.120 dB, corr 0.985). Start here.
- **H2** — same e1, e2 first 26 frames. Slightly stronger `فَإِنَّ`, closer
  donor match (3.497), a little more melodic change.
- **H3** — whole-word e1 + conservative e2. Use if H1/H2's e1 still sounds like
  `عَلِيم`; it replaces the vowel too, at the cost of more change (corr 0.969).
- **H4** — both whole words; strongest phonetic change, largest collateral.

Nothing here is claimed to be bit-identical to the original *inside* the edited
words — only outside them. The final choice is by ear.

## 5. Files

- Full candidates: `happy_accident/runs/token_surgery/v2/<id>.wav`
- Local comps: `happy_accident/runs/token_surgery/v2/hybrid/<id>.wav`
- Audition clips (original + H1–H4, e1 and e2 windows):
  `happy_accident/deliverables/listen/`
- GCS mirror: `gs://akbar-december-2024-backup/arabmaqamrock/runs/20261019_baghdad_moon_token_surgery/`
