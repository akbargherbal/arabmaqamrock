# CHECKPOINT — pronunciation repair workflow

**Date:** 2026-11-14
**Purpose:** a repeatable, ~30-minute repair on a good track. The current track
(`abu01_a01`) is **not** special; it is the test case. The deliverable is the
workflow, not the fix.

> **This file supersedes** the `111.35` comp end in `README.md`,
> `RUNBOOK.md`, `spec/repair_spec.draft.json` and `intake/defect_card.md`.
> The latest measurement puts the vowel onset at **~110.30**, so the
> recommended comp end is **110.35** (see §6).

---

## 0. One-screen version

```
listen + card (5 min)  →  measure unit (5)  →  preflight (5)
   →  one GPU run: token gate + 16 tails (unattended, ~25)
   →  filter + comp (5)  →  full-track listen (5)
```

- **Human attention:** ~20–25 min. **Wall:** ~30–40 min.
- **Four human gates:** defect card, unit/strategy, take pick, final listen.
- **Three stop rules:** gate fails → stop; 16 seeds fail the same way → change
  text/route; two rounds → stop.
- **The only thing that breaks the 30-minute budget** is a take that was not
  generated "repairable" (no exported semantic tokens).

---

## 1. Mental model

Four layers; three are one-time:

1. **Foundation** (at generation): WAV + semantic tokens + lyrics/style + seed
   + model/LoRA/binary/GPU hashes. Cost now: zero. Cost later: a session.
2. **Triage** (per take): is it worth repairing? is a sibling take already
   correct? Most time is saved here by deciding *not* to repair.
3. **Localization** (per defect): word, occurrence, musical unit, target sound.
   **Hardest stage.** Wrong unit = everything downstream is wasted.
4. **Repair** (per unit): re-sing the smallest unit → filter → ear → comp vocal
   only → verify → listen.

Difficulty is concentrated at the two ends: the generation-time decision, and
the unit decision. The render in the middle is a button.

---

## 2. Generic workflow

| phase | question | tool | output | gate | time |
|---|---|---|---|---|---|
| 0 intake | what exactly is wrong? | hash + probe + Demucs + forced alignment + f0/RMS | card + map + clips | target word found; all occurrences known | 2–5 min machine |
| 1 card | is the defect / occurrence / tail right? | ear | closed card | 3–4 answers | 5–8 min human |
| 2 preflight | can the GPU session succeed? | asset/hash checks + request JSON | ready-to-run session | tokens, LoRA, binary, GPU | 3–5 min |
| 3 gate | is the token stream this take's? | re-derive + full render | pass/fail | fingerprints + perceptual match | ~6 min GPU |
| 4 batch | can the model sing the unit? | prefix + 8–16 seeds | candidates | every candidate covers the comp | 10–20 min GPU |
| 5 pick + comp | which take, which width? | filter + comp + verify | final composite | outside diff = 0; seam measured | 5–8 min |
| 6 listen | is it transparent? | ear, full track or complete section | ship / keep / retry | — | 5–10 min |

**One render, several comp widths.** Generate a window wider than the unit, then
comp B / D / A from the *same* candidate. The hardest decision (where the unit
ends) becomes a comparison, not a guess, at zero extra cost.

---

## 3. Rules that survived (with evidence)

1. **Repair, don't regenerate.** Baghdad Moon ended at 9.5–9.7/10 with two tiny
   spans replaced.
2. **Keep what is correct; replace less.** The winning move was keeping the
   5.5 s final `ه` byte-identical.
3. **The unit is musical, not lexical.** A word can end lexically at 111.33 and
   musically at 112.55.
4. **The word box is an index, not a cut.** Aligners are early at holds; in this
   take the box ends 111.33 but the vowel starts ~110.30.
5. **Judge boundaries on the stem, not the mix.** A 70 ms vocal break is
   invisible in the mix; the instruments fill it.
6. **Joins at word onsets or real gaps; never inside a sustain.** Baghdad's two
   failures: 204.775 inside `الله`, 207.90 inside a 5.5 s `ه`.
7. **The model generates forward; it does not know where the splice is.** The
   phrase candidate in Baghdad ended on D4 instead of the original G4 — no fade
   fixes a wrong final note.
8. **Filter before the ear.** 16 seeds → 3–5 candidates; rejects are never
   auditioned.
9. **The ear is the oracle; metrics are filters.** Envelope correlation ranked
   `s13` first despite its wrong final note.
10. **Bit-identity outside the edit; never claim it inside.**
11. **If 16 seeds fail the same way, it is the text or the route, not luck.**
    One phonetic respelling attempt; then stop.
12. **Stop at good enough.** 9.5/10 is a valid stop; the last half-point may
    cost the take.

---

## 4. Dead ends — do not redo

- **Donor splices** from another take: 0/4 accepted in Baghdad. Same singer is
  not enough; prosody/timbre do not transfer.
- **Partial-word comps** (changed frames only, or a single phoneme): produce
  "ف + نصف نون" / two attacks.
- **Comp ending inside a melisma**: produces a second `ه`.
- **Envelope-only selection**: hides wrong pitch.
- **ABC timestamps as cut points**: quantized, 0.2–0.5 s off; can backfire with
  false precision. It is a map, not a ruler.
- **Bit-identity as a hard gate across GPU architectures**: the original is L4,
  the prefix binary is T4. Use token fingerprints + a perceptual match; record
  whether bit-identity was achieved.
- **MP3 as the edit source**: always the run's 48 kHz WAV.
- **Assuming one occurrence**: the chorus repeats; check all.
- **Fixing while listening**: collect all defects first.

---

## 5. Tool notes

| tool | gives | does not give | cost |
|---|---|---|---|
| Demucs `htdemucs` | vocal/instrumental stems | perfect separation | ~1 min CPU / seconds GPU |
| forced CTC alignment | word index, all occurrences, line cues | the cut | ~2 min CPU |
| f0 / RMS / spectral flux | consonant closure+burst, sustain start/end, pitch | word identity | seconds |
| ABC (SheetSage2) | structure, beats, long-note flags, melody reference | phonemes, sample-accurate cuts; can be an octave off | ~1 min GPU / 140 s CPU |
| semantic tokens | continuation of the *same* performance | not exported after the fact | generation-time flag |

**ABC's single biggest advantage:** it flags that a word does not end where the
box says — the long-note trap. In this take it showed a note 110.73–112.17 while
the box ended 111.33, which triggered the measurement that found the vowel at
~110.30. **Use it to know where to look; measure on the stem.**
**ABC can backfire:** false precision at exactly the boundaries where it is
weakest (sustains, melismas, dense mixes).

---

## 6. Case 002 — `abu01_a01` state

### Take

| field | value |
|---|---|
| WAV | `abu01_a01_3285212580.wav`, sha256 `30860a08d5ca53731e76766e529d6de7039fa3e6eb96548b18c002417923dad0` |
| duration / format | 229.079 s, 48 kHz stereo PCM_16 |
| seed / cap / frames | `3285212580` / `7250` / **5727** @ 25 fps |
| LoRA | `a01` = `mix_v3/a0.1`; AR `d48109b3…`, NAR `88f00bcb…` |
| run | `20261113-044223_abu01_defaults` (not `abu01_orig`) |
| original GPU | Tesla **L4**; binary commit unknown |
| semantic export | **missing** → token gate required |

### Defect (confirmed by ear)

| field | value |
|---|---|
| word | `وَالْأَجْدَادِ`, chorus 1, line 13 |
| occurrence | 1 of 2; **chorus 2 (200.10–201.92) is correct** → one edit |
| heard | final `د` = /g/ (Egyptian ج) |
| tail | correct; keep it (`المد` confirmed) |
| reference | `الْأَجْسَادِ` 97.028–98.808 (same take, correct final د) |

### Measured map

| marker | time |
|---|---|
| word box (aligner) | 109.149 – 111.329 |
| word boundary (wā onset) | **109.10** |
| defective final د (closure+burst) | **110.18 – 110.27** |
| vowel/sustain starts | **~110.30** |
| note body ends | 112.55 |
| reverb ends | ~113.2 |
| 70 ms vocal break (inside `الْآبَاءِ`) | 108.85 – 108.92 |
| section end (ABC) | 112.17 |
| beat grid / key | 4/4, ~79 BPM, A minor |

### Comp strategies

| id | span | replaces | note |
|---|---|---|---|
| **B** | **109.10 – 110.35** | the word up to the end of the final د | **recommended**; keeps 2.25 s of correct vowel; join at the vowel onset |
| B-old | 109.10 – 111.35 | word + 1 s of the vowel | superseded; cuts ~1 s into the sustain |
| D | 106.20 – 110.35 | the whole line (`هَوَانُ الْآبَاءِ وَالْأَجْدَادِ`) | starts in the 400 ms gap before `هَوَانُ`; replaces two correct words |
| A | 108.88 – 110.35 | hamza release + kasra + word | last resort; starts **inside** `الْآبَاءِ` |

Tail-replacement variant (only if the candidate's sustain matches the original
in pitch and length): end at **112.70** instead of 110.35.

### Generation

```
start 106.00 s (prefix 2650)   end 113.00 s (max 2825)
seeds 3285212580 + 0..15, export_semantic=true
```

One render covers B, D and A. Comp all variants from the same candidate; the
ear picks the strategy, not the theory.

### Why not `D` by default

The same line in chorus 1 vs chorus 2 differs by **0.54 s** (5.04 vs 4.50 s),
and the target word by **0.36 s** (2.18 vs 1.82 s). A whole-line replacement
must match a fixed instrumental grid; the drift risk is real. D is a legitimate
first choice if you value the clean gap start; B is the smaller bet.

---

## 7. Next session — exact plan

### Preflight (local, ~5 min)

1. Verify assets:
   - base model + VAE from HF (`4cf3fdff…` / `d4f4a05d…`);
   - LoRA a01 from
     `gs://…/OSTRIS_Arabic_Suno_Finetuning/arabic_instrumental_lora/mix_v3/a0.1/`
     (`d48109b3…` / `88f00bcb…`);
   - prefix binary
     `gs://…/arabmaqamrock/binaries/sm75-t4/prefix/audiocpp_cli_prefix_sm75`
     (sha `4117a46a…`), T4 only.
2. Build the two request JSONs: re-derive (semantic only) and the 16-tail batch.
3. Confirm stems are available (backed up to the run's `stems/`; 44.1 kHz).

### GPU session (T4)

1. **Re-derive** `stop_after=semantic`, original seed/lyrics/style/cap,
   `export_semantic=true` → expect **5727** tokens, prefix **1156**, truncated 0.
2. **Gate:** render the full stream with `min=max=5727`.
   - G1 fingerprints pass.
   - G2 same performance: correlation ≥ 0.99, median mel Δ ≲ 1 dB.
   - G3 bit-identity (`30860a08…`) is a bonus across L4→T4, not a requirement.
   - **Fail → stop.** No donor fallback.
3. **Batch:** 16 tails, prefix 2650, max 2825, seeds `base+0..15`,
   `export_semantic=true`.
4. Download candidates to the local machine.

### Local (CPU, ~10 min)

1. Filter: sustain pitch ≈247 Hz and length (only for tail-replacement), onset
   lag ≤60 ms, `/d/` present (CTC presence filter), edge step <1 dB.
2. Audition 3–5 on the full line (106.1–113.3), never on a partial word.
3. Comp **B @ 110.35** first; then `D @ 110.35`; then `B @ 111.35` if needed;
   `112.70` only if the candidate sustain matches.
4. Verify: outside diff = 0; duration unchanged; original tail byte-identical
   for ends at 110.35/111.35; edge step reported.
5. Full-track listen; verdict.

---

## 8. The 30-minute budget

| phase | human | machine |
|---|---:|---:|
| intake | — | 2–5 min |
| card | 5–8 | — |
| preflight | 3–5 | — |
| gate + batch | 2–5 | 20–25 |
| filter + comp | 5–8 | 5 |
| listen | 5–10 | — |
| **total** | **20–25 min** | **30–35 min** |

**What breaks it:** (a) no exported tokens (gate becomes a session), (b) a wrong
unit (every render is wasted), (c) seed grinding after the same failure.
**What protects it:** export tokens at generation; measure the unit on the stem;
one render, several comp widths; filter before the ear.

---

## 9. Friction log (condensed)

| # | friction | cost | fix |
|---|---|---|---|
| 1 | user gives a **region**, not a word | one round-trip | ask for the lyric line; ship a locator clip |
| 2 | word occurs **twice** | a second session if missed | alignment lists occurrences |
| 3 | three different "ends" (word / note / reverb) | rejected render | measure f0/RMS |
| 4 | no `export_semantic` | session blocked | default export for keepers |
| 5 | original L4, prefix binary T4, commit unknown | gate may fail for the wrong reason | record provenance; perceptual gate |
| 6 | LoRA in another bucket, not the run | 10–20 min hunting | store the LoRA URI in the sidecar |
| 7 | mp3 vs WAV | quality loss, no bit-identity | always the WAV |
| 8 | sibling takes have different durations | naive sibling check wrong | align each sibling (2 min) or skip |
| 9 | stems 44.1 kHz vs mix 48 kHz | clicks/shift | resample before comp |
| 10 | aligner boxes early at holds | wrong cut | stem measurement |
| 11 | run names lie (`abu01_orig`) | wrong file | name by controls |
| 12 | judging a 70 ms boundary on the mix | impossible | judge on the stem |

---

## 10. Files

- `cases/002_abu01_ajdad/README.md` — case summary
- `cases/002_abu01_ajdad/PREP.md` — preparation timeline + friction
- `cases/002_abu01_ajdad/RUNBOOK.md` — phase plan
- `cases/002_abu01_ajdad/intake/` — card, alignment, words, hashes
- `cases/002_abu01_ajdad/spec/repair_spec.draft.json` — numbers (end 111.35 →
  update to 110.35)
- `cases/002_abu01_ajdad/scripts/plot_gaps.py` — generic gap chart
- `cases/002_abu01_ajdad/review/gaps.png` — committed preview
- ABC transcription: `local_workspace/abu01_a01_3285212580/` (full; byte-identical
  to the previous zip)

**One line to remember:** replace less, keep the take, and measure the end on
the stem — not in the score, not in the mix.
