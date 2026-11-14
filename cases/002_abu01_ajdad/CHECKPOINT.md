# CHECKPOINT — pronunciation repair workflow

**Date:** 2026-11-14, updated after the three repair sessions
**Purpose:** a repeatable, ~30-minute repair on a track the user wants to keep.
The deliverable is the workflow. The current case is the test, not the goal.

> **Read §0 and §7 first.** The original L4 take is **closed** as a repair
> target. The active track is the **CFG 1.5 ABC take** (`repro_abc_cfg15.wav`),
> which the user prefers musically and which was generated with
> `export_semantic=true`. The old `110.35` plan in §6A belongs to the original
> take only; it does **not** apply to the CFG 1.5 track.

---

## 0. State in one screen

| track | where it came from | tokens | status |
|---|---|---|---|
| `abu01_a01_3285212580.wav` | **L4**, CFG 1.0, no ABC | **not exported** | **closed** — T4 re-derivation is a different performance |
| `abu01_orig/abu01_a01_3285212580.wav` | **L4**, CFG **1.5**, no ABC | **not exported** | **not the active track** — the “orig” run is misnamed; 6095 tokens, no export |
| `repro_abc.wav` | T4, CFG 1.0, ABC-conditioned | **5728**, exported | **fallback** — `وَالْأَجْدَادِ` correct, ~95 % similar, audible timbre shift; its `مِلَّتِي` was not checked |
| `repro_abc_cfg15.wav` | T4, CFG **1.5**, ABC-conditioned | **5606**, exported | **active** — user prefers the music; one opening defect: `مِلَّتِي` (missing م), occurrence 1 of 2 |

### What the three sessions established

- **Session 1 — Baghdad Moon / workflow.** The method came from a real repair:
  replace the smallest *musical* unit, keep the original everywhere else, comp
  the vocal only, and judge on the full track. It also fixed the case-002
  preparation and produced the “ABC is a map, not a ruler” rule.
- **Session 2 — checkpoint review.** Re-measured on the vocal stem and corrected
  the workflow: the vowel starts at ~110.30, not 111.33; `110.35` is on an
  ornament peak, so the end must follow the candidate; the gap before `هَوَانُ`
  is **1.2 s**, not 400 ms; CTC cannot separate `/d/` from `/g/`; comp with
  `mix + (cand_voc − orig_voc)`, never `no_vocals + cand`.
- **Session 3 — Colab T4.** The original take has no exported tokens. Two T4
  re-derivations (two different binaries) produced **identical 5937-token**
  streams, but the source L4 take is **5727**. A full render of the first 5727
  frames failed the gate: envelope correlation **0.216**, median mel Δ
  **7.47 dB**, divergence from the first 5 s (r = 0.382). The user's ear agreed:
  **“very different.”** The original was left untouched and the repair stopped.
- **Session 3, after the stop.** Feeding the take's *transcribed* ABC score back
  as `abc_file` (`cot=full`) produced a new performance, not a reproduction:
  **5728 tokens**, 229.119 s, r = 0.633, mel Δ 4.19 dB, line r = 0.58. The
  user heard the defect gone, ~95 % similar, with a slight timbre difference.
- **CFG 1.5.** Same score/seed/LoRA with `guidance_scale=1.5` produced
  **5606 tokens**, **224.239 s**, r = 0.220, mel Δ 6.36 dB, line r = 0.086.
  The assistant rejected it on similarity-to-original. In the saved session the
  user initially agreed it was worse (“not as good as the previous one”,
  19:35Z); **after the session, on another listen, the user reversed that
  judgment: “CFG 1.5 is actually better in terms of music.”** It had one mistake
  at the start — **`مِلَّتِي` in the opening verse, pronounced without the
  initial م** — which created a bad first impression; the repeated verse sings
  the word correctly. The later verdict is the governing one for choosing the
  base take.

**Session-3 time, for the record:** assets + hashes 2.8 min; two token
re-derivations 9.8 min (4.9 each); gate render 6.4 min; stop decision at
~22 min; then the ABC CFG 1.0 experiment 9.3 min and CFG 1.5 11.1 min — about
75 min total, with no repair delivered. The budget did **not** fail on the GPU;
it failed on the missing foundation (no exported tokens) and on treating a new
take as a reproduction.

> **Provenance note.** The saved session-3 export
> (`S03_VM_session-a11e0aba-…json`) ends at 19:36Z, before the later listening
> verdict and before the request to fix the opening. The user reports that the
> Colab session then crashed/disconnected; the later verdict is therefore not in
> the export. The CFG 1.5 preference and the “one mistake at the start” are
> **user-reported after that export**. The raw exports are in
> `local_workspace/sessions_fixing_mispronunciation/`.

### Why the pivot is legitimate

The CFG 1.5 take was generated on **T4** with `export_semantic=true`. Its
semantic stream is therefore **the take's own recording**, already exported:

- `5606` frames @ 25 fps → `5606 / 25 = 224.24 s`, matching the WAV's
  `224.238667 s`;
- the token file and the WAV are from the same run;
- no L4→T4 re-derivation is needed, and the cross-architecture gate is
  irrelevant.

This is the first time in the case that the **foundation layer is complete**:
WAV + tokens + lyrics/style + seed + LoRA/model/binary/GPU provenance. The only
open question is the repair itself: identify the opening defect, re-sing the
smallest unit from the take's own prefix, and make the seam inaudible.

---

## 1. Mental model

Four layers; three are one-time:

1. **Foundation** (at generation): WAV + semantic tokens + lyrics/style + seed
   + model/LoRA/binary/GPU hashes. Cost now: zero. Cost later: a session.
2. **Triage** (per take): is it worth repairing? Which take does the user
   actually want to keep? Most time is saved by deciding *which* take and
   whether to repair at all.
3. **Localization** (per defect): word, occurrence, musical unit, target sound.
   **Hardest stage.** Wrong unit = everything downstream is wasted.
4. **Repair** (per unit): re-sing the smallest unit → filter → ear → comp vocal
   only → verify → listen.

Difficulty is concentrated at the two ends: the generation-time decision
(tokens!), and the unit decision. The render in the middle is a button.

---

## 2. Generic workflow

```
listen + card (5)  →  token check (0.5)  →  preflight (5)
   →  one GPU run: prefix + 4–16 candidates (10–20)
   →  filter + comp (5–8)  →  full-track listen (5–10)
```

- **Human attention:** ~20–25 min. **Wall:** ~30–35 min.
- **Four human gates:** card, unit/strategy, take pick, final listen.
- **Three stop rules:** token check fails → stop; 4 seeds fail the same way →
  widen once, then stop; audible seam → stop.
- **The only thing that breaks the 30-minute budget** is a take that was not
  generated “repairable” (no exported semantic tokens) — or repairing the wrong
  take.

| phase | question | tool | output | gate | time |
|---|---|---|---|---|---|
| 0 intake | what exactly is wrong? | hash + probe + Demucs + forced alignment + f0/RMS | card + map + clips | target found; all occurrences known | 2–5 min machine |
| 1 card | is the defect / occurrence / tail right? | ear | closed card | 3–4 answers | 5–8 min human |
| 2 preflight | can the GPU session succeed? | asset/hash checks + request JSON | ready-to-run session | tokens, LoRA, binary, GPU | 3–5 min |
| **3a token check** | **are the tokens this take's?** | **count + duration + sha** | **pass/fail** | **`len(tokens) ≈ duration × 25`; sha recorded** | **30 s** |
| 3b re-derive gate | only if tokens are missing | re-derive + full render | pass/fail | fingerprints + perceptual match | ~6–16 min GPU |
| 4 batch | can the model sing the unit? | prefix + 8–16 seeds | candidates | every candidate covers the comp | 10–20 min GPU |
| 5 pick + comp | which take, which width? | filter + comp + verify | final composite | outside diff = 0; seam measured | 5–8 min |
| 6 listen | is it transparent? | ear, full track or complete section | ship / keep / retry | — | 5–10 min |

**Two rules about the gate:**

- **If tokens exist, do not re-derive.** A token count matching the WAV duration
  and a recorded hash is enough provenance. A full re-render is optional, not a
  gate.
- **If tokens do not exist, the gate can fail for reasons unrelated to the
  repair** (different GPU architecture). That is a foundation failure, not a
  failed repair. Stop and keep the take.

**One render, several comp widths.** Generate a window wider than the unit, then
comp 2–3 widths from the *same* candidate. The hardest decision (where the unit
ends) becomes a comparison, not a guess, at zero extra cost.

---

## 3. Rules that survived (with evidence)

1. **Repair, don't regenerate.** Baghdad Moon ended at 9.5–9.7/10 with two tiny
   spans replaced.
2. **Keep what is correct; replace less.** The winning move was keeping the
   5.5 s final `ه` byte-identical.
3. **The unit is musical, not lexical.** A word can end lexically at 111.33 and
   musically at 112.55.
4. **The word box is an index, not a cut.** Aligners are early at holds; in the
   original take the box ends 111.33 but the vowel starts ~110.30.
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
13. **Same seed is not portable across GPU architectures.** T4 produced
    **5937** tokens twice (two different binaries, element-for-element
    identical); the L4 source is **5727**. The token stream is the portable
    recording; the seed is only meaningful with the same build + arch + backend.
14. **Export tokens at generation; a WAV alone cannot be repaired.** Cost at
    generation: one flag. Cost later: a session that may fail.
15. **ABC conditioning is a new performance, not a reproduction.** It anchors
    length and structure (5728 ≈ 5727), not the performance (stream differs from
    frame 0; line r = 0.58; `/d/` at 110.94 vs 110.24). Use it to create an
    alternative take, not to recover the original.
16. **CFG is a musical lever, not a fidelity lever.** CFG 1.5 moved similarity
    to the *original* down (5606, r = 0.220) but the user preferred its music.
    Similarity-to-original is the wrong metric once the base is a new take.
17. **Metrics filter; the ear chooses the base.** Once the base is chosen, the
    repair is still judged by the two conditions: correct sound **and** no
    audible seam.
18. **Repair the take you will keep.** Do not spend a session repairing a take
    you will discard; and never comp a word from a different take into the
    chosen one.
19. **An opening defect has no left context.** Use the intro as prefix if it
    exists. If the defect is the first vocal sound, the left edge is the file
    start (no left join); the right seam follows the candidate's corrected
    consonant. Judge the whole first phrase, not the isolated word.
20. **Never reuse timestamps across takes.** The CFG 1.5 take is **224.239 s**,
    not 229.079 s. The same word can move by seconds. Re-align and re-measure
    on the new take.

---

## 4. Dead ends — do not redo

- **Re-deriving the L4 original's tokens on T4.** 5937 vs 5727, gate r = 0.216,
  mel Δ 7.47 dB, different from the first 5 s. No export exists. Stop.
- **Feeding the ABC transcription back to reproduce the original.** 5728 tokens,
  r = 0.633, line r = 0.58; it is a new performance. Not the take.
- **CFG 1.5 as a closer match to the original.** 5606 tokens, −4.84 s,
  r = 0.220. Not a fidelity lever.
- **Donor splices** from another take: 0/4 accepted in Baghdad. Same singer is
  not enough; prosody/timbre do not transfer.
- **Partial-word comps** (changed frames only, or a single phoneme): produce
  “ف + نصف نون” / two attacks.
- **Comp ending inside a melisma/sustain**: produces a second `ه`.
- **Envelope-only selection**: hides wrong pitch.
- **ABC timestamps as cut points**: quantized, 0.2–0.5 s off; false precision.
  It is a map, not a ruler.
- **Bit-identity as a hard gate across GPU architectures**: the original is L4,
  the prefix binary is T4. With exported tokens, the gate is just a count/hash
  check; without them, bit-identity is not a reasonable requirement.
- **MP3 as the edit source**: always the run's 48 kHz WAV.
- **Assuming one occurrence**: the chorus repeats; check all.
- **Fixing while listening**: collect all defects first.
- **Rejecting a take on similarity-to-original when the user wants a new take.**
  That is a category error; keep it as an alternative and let the ear decide.
- **Reusing the original take's map on a new take.** Re-align and re-measure.

---

## 5. Tool notes

| tool | gives | does not give | cost |
|---|---|---|---|
| Demucs `htdemucs` | vocal/instrumental stems | perfect separation | ~1 min CPU / seconds GPU |
| forced CTC alignment | word index, all occurrences, line cues | the cut; cannot distinguish `/d/` from `/g/` | ~2 min CPU |
| f0 / RMS / spectral flux | consonant closure+burst, sustain start/end, pitch | word identity | seconds |
| ABC (SheetSage2) | structure, beats, long-note flags, melody reference | phonemes, sample-accurate cuts; can be an octave off | ~1 min GPU / 140 s CPU |
| semantic tokens | **the portable record of the performance; prefix continuation** | not recoverable after the fact | generation-time flag |
| ABC *conditioning* (`cot=full` + `abc_file`) | a new take anchored to the score's structure/length | a reproduction; it changes the performance | ~9–11 min per 4-min track on T4 |

**ABC's single biggest advantage:** it flags that a word does not end where the
box says — the long-note trap. In the original take it showed a note
110.73–112.17 while the box ended 111.33, which triggered the measurement that
found the vowel at ~110.30. **Use it to know where to look; measure on the
stem.** **ABC can backfire:** false precision at exactly the boundaries where it
is weakest (sustains, melismas, dense mixes).

**Tokens are the foundation.** A take with tokens is repairable on any machine
that has the same model/LoRA/binary and a prefix-capable build. A take without
tokens is not repairable in general — and never trust “same seed” to recover it.

---

## 6. Case 002 — state

### 6A Original take — **CLOSED as a repair target**

Kept as the reference map and the evidence for the rules. **Do not run the old
B/D/A plan on T4.**

| field | value |
|---|---|
| WAV | `abu01_a01_3285212580.wav`, sha256 `30860a08d5ca53731e76766e529d6de7039fa3e6eb96548b18c002417923dad0` |
| duration / format | 229.079 s, 48 kHz stereo PCM_16 |
| seed / cap / frames | `3285212580` / `7250` / **5727** @ 25 fps |
| LoRA | `a01` = `mix_v3/a0.1`; AR `d48109b3…`, NAR `88f00bcb…` |
| run | `20261113-044223_abu01_defaults` (not `abu01_orig`) |
| original GPU | Tesla **L4**; binary commit unknown |
| semantic export | **missing** |
| status | **untouched; no repair delivered** |

**Defect (confirmed by ear):** `وَالْأَجْدَادِ`, chorus 1, line 13; occurrence
1 of 2; chorus 2 (200.10–201.92) is correct; final `د` = /g/ (Egyptian ج); the
≈247 Hz tail is correct and must be kept. Reference: `الْأَجْسَادِ`
97.028–98.808 (same take, correct final د).

**Measured map (original only — do not reuse):**

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

**Historical comp strategies** (for the record; the route is closed):

| id | span | replaces | note |
|---|---|---|---|
| **B** | 109.10 – 110.35 | the word up to the end of the final د | keeps 2.25 s of correct vowel; join at the vowel onset |
| B-old | 109.10 – 111.35 | word + 1 s of the vowel | superseded; cuts ~1 s into the sustain |
| D | 106.20 – 110.35 | the whole line | starts in the 1.2 s gap before `هَوَانُ`; replaces two correct words |
| A | 108.88 – 110.35 | hamza release + kasra + word | last resort; starts inside `الْآبَاءِ` |

**Why the route closed:** no exported tokens; T4 re-derivation is a different
performance; the gate failed before any batch. See
[RUN2.md](RUN2.md) and `runs/20261114-183900_repair002/`.

### 6B Active take — ABC CFG 1.5

> This is the **T4 ABC-conditioned** CFG 1.5 take from session 3. Do not confuse
> it with `abu01_orig`, which is also CFG 1.5 but was generated on **L4**, has no
> ABC score, has **6095** tokens, and has **no exported token stream**. The
> “orig” name is misleading; it is not the original and not the active track.

| field | value |
|---|---|
| WAV | `repro_abc_cfg15.wav` |
| sha256 | `4f9006defa5390c001ce5d3c3a742350c2ab8c3c80c5e400b13ac54919f95b4a` |
| duration / format | **224.238667 s**, 48 kHz stereo PCM_16 |
| tokens | **5606** @ 25 fps; `tokens/abc_cfg15_semantic.json`; file sha `c218c41c77faf879a9f2d079fcae0cc6b155cb6fa8d18a24c47e54596213b9e0` |
| token check | `5606 / 25 ≈ 224.24 s` — consistent |
| generation | T4; seed `3285212580`; **guidance 1.5**; steps 8; context 24576; `cot=full`; `abc_file=abc/score.abc`; `nar_noise=generated`; semantic T=1, p=0.95, k=100, rp=1.2, window=50, min=200; cap 7250; LoRA a01 (AR+NAR 1.0); attention flash; `export_semantic=true` |
| run | `20261114-191700_abc_cfg15` |
| score | `cases/002_abu01_ajdad/abc/score.abc` (post-hoc transcription of the original; 190 ms grid at ♩=79) |
| stems | **not yet generated** — run Demucs 4.1.0 `htdemucs` on this WAV |
| user verdict | “CFG 1.5 is actually better in terms of music”; likes it; one mistake at the start; the mistake caused a negative first impression |
| defect | **`مِلَّتِي`**, opening verse (lyrics line 1; aligner line 0: `غَيْرُ مُجْدٍ فِي مِلَّتِي وَاعْتِقَادِي`), **occurrence 1 of 2**; heard as **“لتي”** — the initial **م** is missing. Occurrence 2 (the repeated verse, lyrics line 3 / aligner line 2) is **correct**. |

**Fallback take — ABC CFG 1.0**

| field | value |
|---|---|
| WAV | `repro_abc.wav` |
| sha256 | `d79f9e5472269e73eedac6206e348620c347d18e310eee8cc6edf79df60d86b6` |
| duration / tokens | 229.118667 s / **5728** (exported) |
| similarity to original | r = 0.633, mel Δ 4.19 dB, line r = 0.58 |
| user ear | defect gone, ~95 % similar, audible timbre shift when switching |
| role | a repairable alternative base if the CFG 1.5 opening cannot be fixed; **not** a comp source for the original |

### 6C The CFG 1.5 opening defect — localized

**Card (closed by the user’s ear, 2026-11-15):**

| field | value |
|---|---|
| line | `غَيْرُ مُجْدٍ فِي مِلَّتِي وَاعْتِقَادِي` — opening verse (lyrics line 1; aligner line 0) |
| target word | **`مِلَّتِي`** |
| occurrence | **1 of 2** — the repeated verse (lyrics line 3; aligner line 2) sings it **correctly** |
| heard | **“لتي”** — the initial **م** is missing |
| target | `مِلَّتِي` with a clean initial /m/ |
| next word | `وَاعْتِقَادِي` — correct, do not touch |
| previous word | `فِي` — correct, do not touch |

**Measured map (CFG 1.5 vocal stem, Demucs 4.1.0, 44.1 kHz):**

| marker | time |
|---|---|
| aligner box for `مِلَّتِي` | 27.782 – 28.902 |
| **actual word start** (f0 / vowel onset) | **~27.52** |
| previous word `فِي` | /f/ onset **27.00**; vowel 27.15–27.48 |
| previous word `فِي` ends | ~27.48 |
| **actual word end** | **~28.90** |
| next word `وَاعْتِقَادِي` onset | **~29.00** (aligner 29.102) |
| **comp B (default)** | **27.50 – 28.95** |
| **comp D (fallback)** | **27.00 – 28.95** |
| **comp A (last resort)** | 27.10 – 28.95 |
| correct occurrence 2 | aligner 41.423 – 42.244; actual ~**41.13 – 42.55** |

> **The aligner box is an index, not a cut — again.** The box starts **~0.26 s
> late**. Cutting at 27.782 would cut into the sung word and miss the position
> where the **م** should be (immediately before 27.52). This is the same failure
> the original take taught at 111.33; the fix is the same: measure on the stem.

**Pitch contour of `مِلَّتِي`:** **220 → 247 → /t/ closure → 247 → 221 → 200
Hz**. The 197 Hz segment before 27.52 is the vowel of `فِي`, not the target
word. `مِلَّتِي` is ~1.38 s in occurrence 1; occurrence 2 is ~1.42 s. Occurrence
2 is a **reference for the /m/ and vowel**, not a donor splice.

**Unit and joins:**

- **B (default): start ~27.50**, at the candidate’s `مِلَّتِي` /m/ onset; keeps
  `فِي` byte-identical. Do not start before ~27.45 (that would eat the `فِي`
  vowel). The join is a voiced word onset, so it must be level-matched.
- **D (fallback): start ~27.00**, at the /f/ onset of `فِي`; replaces one
  correct word but gives a consonant-word join. Use it if B’s join is audible.
- **A (last resort): start 27.10**, inside the `فِي` vowel; not recommended.
- End follows the **candidate’s own** word end, in its quietest point, and must
  stay **before 29.00** so `وَاعْتِقَادِي` is not touched. Safe end **28.95**.
- Because the prefix is before `فِي`, the candidate re-sings `فِي` as well.
  B must align the candidate’s `مِلَّتِي` onset to the original `فِي` end; if
  that timing shifts, **D is safer** because it uses the candidate’s whole
  `فِي + مِلَّتِي` phrase and joins at the /f/ onset instead.

**Generation window for this unit:**

```
prefix 26.88 s = 672 tokens   max 31.00 s = 775 tokens
seeds 3285212580 + 0..3 first (16 ceiling)
same request as the take: guidance 1.5, cot=full, abc_file=score.abc,
steps 8, context 24576, nar_noise=generated, export_semantic=true
```

The prefix starts ~120 ms before the /f/ of `فِي`, so it covers both B and D.
The candidate is generated from 26.88 to 31.00; B uses 27.50 onward, D uses
27.00 onward. The word sits in the middle of the generated segment, not at its
edge.

**Filter (before the ear):**

1. an audible **/m/**: a nasal murmur or closure+release at 27.50–27.55, before
   the vowel; compare it with the correct occurrence’s /m/ at 41.13–41.20
   (do not use CTC to “prove” it — the ear decides);
2. word end **≤ 28.98** so the seam stays before `وَاعْتِقَادِي`;
3. pitch contour close to **220 → 247 → 247 → 221 → 200 Hz** in the used span;
   no new defect;
4. |Δf0| ≤ 20 cents and |ΔRMS| ≤ 1 dB at the seam.

**ABC in this repair (decision):** do **not** transcribe the isolated ~1.4 s
word. A **full-track transcription of `repro_abc_cfg15` is allowed as an
analysis map** (optional, ~1 min GPU / ~140 s CPU), but it is **not** a
conditioning input and **not** a cut source. Keep `abc/score.abc` for the batch:
feeding the new transcription back as `abc_file` would change the request and
produce a third performance. Use the new map only to confirm the first line’s
notes and to filter candidates by melody; the cut stays measured on the stem.
The full map is also useful as an archive of the new take’s structure, beats,
and long notes for any future defect.

**Acceptance** is still the pair: the **م** is audible **and** the user cannot
hear where the edit is. If only one holds, keep the CFG 1.5 take as it is.

---

## 7. Next session — exact plan (T4)

### 0) Preflight (~5 min)

1. `git pull`; `./setup_colab.sh`.
2. Fetch the active take and its provenance:
   - WAV: `gs://akbar-december-2024-backup/arabmaqamrock/runs/20261114-191700_abc_cfg15/repro_abc_cfg15.wav`
   - tokens: `…/tokens/abc_cfg15_semantic.json`
   - session log: `…/session/repro.log`
   - score: `…/score.abc` (or `cases/002_abu01_ajdad/abc/score.abc`)
3. Verify:
   - WAV sha = `4f9006de…`, duration = **224.238667 s**, 48 kHz / 2 ch;
   - token file sha = `c218c41c…`, length = **5606**;
   - `5606 / 25 ≈ 224.24 s`.
4. Stage the model, VAE, LoRA a01, and the prefix binary; verify hashes as in
   §6A. Confirm `strings bin/audiocpp_cli_prefix | grep semantic_prefix`
   (the prefix option must not be silently ignored).
   The prefix binary is `eb8e21bd` + the clean prefix cherry-pick, i.e. the same
   base as the standard binary; the NAR/VAE path should match. If the candidate
   timbre does not match the CFG 1.5 take, record it and stop — do not try to
   EQ/fade a different voice into the take.
5. **G0 — token check (30 s):** count + duration + sha. **No re-derive, no full
   render.** If the count/duration do not match, stop: wrong token file.
6. Play the track and confirm with the user that this is the CFG 1.5 take they
   mean (there are three T4 takes in the bucket).

### 1) Verify the card and the unit (~5 min; localization already done)

The card is closed in §6C; the alignment is saved at
`intake/words_cfg15.json`, the measurement at `intake/measure_cfg15.json`.
Do this once on the VM:

- play `27.50–28.95` (B) and `27.00–28.95` (D) in a loop; the user confirms
  they contain `مِلَّتِي` and that the **م** is missing;
- play `41.13–42.55` (the correct occurrence) as the reference;
- if the local stem is absent, run Demucs 4.1.0 `htdemucs` on the CFG 1.5 WAV
  and re-check the same two windows. Do not re-use the original take’s boxes.

If the loop does not match the card, stop and re-localize before any GPU batch.

### 2) Batch (~5–10 min GPU)

- `prefix = 672` tokens (**26.88 s**) from the take’s own 5606-token stream.
  This is ~120 ms before the /f/ of `فِي`, so the model can enter the phrase
  naturally and the same render covers B and D.
- `min = max = 775` tokens (**31.00 s**) — the line ends ~30.68, so this covers
  the phrase with margin. The comp ends at the candidate’s word end, not at 31.
- Seeds `3285212580 + 0..3` first; **16 is a ceiling, not a target**.
- **Sequential only; one `audiocpp_cli_prefix` process.** Two concurrent GPU
  runs can OOM a T4. Generate one seed first, then the rest.
- Do **not** run Demucs or the optional ABC before/during generation; run them
  after the process exits (Demucs on CPU if RAM is tight).
- Check the log before seeds 2–4: `max_tokens=775`, final tokens **775** (or
  **103** new if reported separately), `truncated 0`. If it says 7250 or 5606,
  stop — the bounds were not applied.
- Same request as the take: `guidance_scale=1.5`, `cot=full`,
  `abc_file=cases/002_abu01_ajdad/abc/score.abc`, `num_inference_steps=8`,
  `context=24576`, `nar_noise=generated`, semantic sampler defaults, cap 7250,
  LoRA a01 scale 1.0, `attention=flash`, `export_semantic=true`.
- Check the output length before any coordinate math: is it the full timeline
  up to `max`, or only the tail after `prefix`? If tail-only, subtract
  `prefix_s` (26.88) from every coordinate.

### 3) Filter + comp (~5–10 min, CPU/GPU)

- Demucs each candidate (same 4.1.0 `htdemucs`).
- Reject if:
  - the initial **/m/** is not audible before the vowel (nasal murmur or
    closure+release) — this is the whole point of the edit;
  - the candidate’s `مِلَّتِي` ends after **28.98**, which would collide with
    `وَاعْتِقَادِي` (onset ~29.00);
  - the pitch/contour differs in the used span from
    **220 → 247 → 247 → 221 → 200 Hz**;
  - |Δf0| > 20 cents or |ΔRMS| > 1 dB at the seam;
  - a new defect appears.
- Keep at most 3 for listening.
- Comp on the **vocal** only:
  `new_mix = mix + (cand_voc − orig_voc)` inside the region; compute the
  difference at 44.1 kHz and resample to 48 kHz. Never `no_vocals + cand`.
- Prepare two comps from the **same** candidate:
  - **B (default): candidate /m/ onset (~27.50) – candidate word end**,
    keeping `فِي` byte-identical; do not start before ~27.45;
  - **D (fallback): 27.00 – candidate word end**, joining at the /f/ onset.
  Both ends must be **≤ 28.98**, before `وَاعْتِقَادِي`.
- Verify: outside the region **byte-identical**; duration **224.238667 s**;
  original tail byte-identical if it was kept; f0/RMS edge steps reported; no
  click.

### 4) Listen (~5–10 min)

- The whole opening phrase, then the whole track; then a blind A/B against the
  unedited CFG 1.5 take.
- If the user hears a seam → stop; the CFG 1.5 take stays as it is.
- If transparent → deliver the new WAV + sidecar (tokens, params, hashes, comp
  points, verification report).

### Optional — full-track ABC map

If time permits, transcribe `repro_abc_cfg15` **once, full track** (SheetSage2,
~1 min GPU / ~140 s CPU) and store it under `abc_cfg15/`. Use it as a **map**:
structure, beats, long notes, and a melody reference for filtering candidates.
Do **not** use its timestamps as cuts, and do **not** feed it back as
`abc_file` for the batch — the batch keeps `abc/score.abc`. Skip it if the
repair is already transparent or the session is tight.

### Stop rules

- **G0 fails** (count/duration/sha) → stop; do not re-derive.
- **4 candidates fail the same way** → widen the window once (earlier start /
  later end), then stop.
- **Opening has no prefix and candidates do not match the singer** → stop; do
  not comp a different opening.
- **Audible seam** → stop; the original CFG 1.5 take remains the deliverable.
- **Two rounds** → stop.

---

## 8. The 30-minute budget

| phase | human | machine |
|---|---:|---:|
| intake / card | 5–8 min | 2–5 min |
| preflight | 3–5 min | — |
| G0 token check | — | 30 s |
| batch | 2–5 min | 10–20 min |
| filter + comp | 5–8 min | 5 min |
| listen | 5–10 min | — |
| **total** | **20–25 min** | **25–30 min** |

**What breaks it:** (a) no exported tokens (gate becomes a session), (b) the
wrong take (the user wants CFG 1.5, not the original), (c) a wrong unit (every
render is wasted — here, trusting the 27.782 aligner box instead of the measured
B 27.50 / D 27.00 – 28.95), (d) seed grinding after the same failure, (e) trying
to comp across takes.

**What protects it:** export tokens at generation; choose the take the user will
keep; re-align/re-measure on that take; one render, several comp widths; filter
before the ear; stop when the seam is audible.

---

## 9. Friction log (condensed)

| # | friction | cost | fix |
|---|---|---|---|
| 1 | user gives a **region**, not a word | one round-trip | ask for the lyric line; ship a locator clip |
| 2 | word occurs **twice** | a second session if missed | alignment lists occurrences |
| 3 | three different “ends” (word / note / reverb) | rejected render | measure f0/RMS |
| 4 | no `export_semantic` | session blocked | default export for keepers |
| 5 | original L4, prefix binary T4, commit unknown | gate may fail for the wrong reason | record provenance; with tokens, skip the gate |
| 6 | LoRA in another bucket, not the run | 10–20 min hunting | store the LoRA URI in the sidecar |
| 7 | mp3 vs WAV | quality loss, no bit-identity | always the WAV |
| 8 | sibling takes have different durations | naive sibling check wrong | align each sibling (2 min) or skip |
| 9 | stems 44.1 kHz vs mix 48 kHz | clicks/shift | resample before comp |
| 10 | aligner boxes early at holds | wrong cut | stem measurement |
| 11 | run names lie (`abu01_orig`) | wrong file | name by controls |
| 12 | judging a 70 ms boundary on the mix | impossible | judge on the stem |
| 13 | **L4 → T4 token re-derivation** | 22 min, no repair | export tokens; a token count is the gate |
| 14 | **ABC fed back as “reproduction”** | 2 extra GPU runs, still a new take | call it an alternative take, not a reproduction |
| 15 | **metrics rejected the take the ear liked** | delayed the right decision | use similarity only for reproduction; the ear chooses the base |
| 16 | **opening defect has no left context** | unclear comp strategy | use the intro as prefix; otherwise the left edge is the file start; judge the whole phrase |
| 17 | **old map reused on a new take** | wrong cut | re-align/re-measure; duration differs by 4.8 s |
| 18 | **candidate tokens not exported** | future repair blocked | `export_semantic=true` for candidates too |
| 19 | “same T4 machine” assumed to be required | unnecessary constraint | the exported tokens are the portable lock; a fresh T4 with the same binary is enough |
| 20 | **aligner box late at the opening word** | would cut inside `مِلَّتِي` and leave the missing م | measure f0/spectral onset on the stem: actual start ~27.52, box 27.782 (~0.26 s late) |

---

## 10. Files and evidence

- `cases/002_abu01_ajdad/README.md` — case summary (still contains the old
  111.35 wording; **this file supersedes it**).
- `cases/002_abu01_ajdad/PREP.md` — preparation timeline + friction.
- `cases/002_abu01_ajdad/RUNBOOK.md` — original phase plan (historical; original
  take only).
- `cases/002_abu01_ajdad/RUN2.md` — session-3 report: gate stop, ABC CFG 1.0,
  CFG 1.5, evidence. **On `origin/main`; pull it before reading.**
- `cases/002_abu01_ajdad/STEPS.md` — the plain-language repair procedure.
- `cases/002_abu01_ajdad/intake/` — the original card/alignment/words/hashes,
  plus **`defect_card_cfg15.md`** (the closed opening card),
  **`words_cfg15.json`** (the CFG 1.5 alignment) and
  **`measure_cfg15.json`** (the opening-defect map: B 27.50 / D 27.00 – 28.95,
  prefix 672, max 775).
- `cases/002_abu01_ajdad/spec/repair_spec.draft.json` — original numbers (end
  111.35 → historically corrected to ~110.30; **not the active plan**).
- `cases/002_abu01_ajdad/scripts/plot_gaps.py` — generic gap chart.
- `cases/002_abu01_ajdad/review/gaps.png` — committed preview (original take).
- `cases/002_abu01_ajdad/abc/` — full SheetSage2 transcription of the original;
  used as the conditioning score for the T4 takes.
- `local_workspace/sessions_fixing_mispronunciation/` — raw session exports:
  - `S01_LM_baghdad_moon.json` — workflow / Baghdad precedent;
  - `S02_LM_checkpoint-md.json` — checkpoint corrections;
  - `S03_VM_session-a11e0aba-…json` — Colab T4 run (ends 19:36Z, before the
    later CFG 1.5 listening verdict).
- `local_workspace/prompt.md` — the **old** Colab prompt for the original L4
  take. **Do not reuse it for the CFG 1.5 opening repair.** Write a short new
  prompt from §7, or use this checkpoint directly.

**GCS evidence**

- Original gate stop: `gs://…/runs/20261114-183900_repair002/`
- ABC CFG 1.0: `gs://…/runs/20261114-185000_abc_repro/`
- **Active CFG 1.5: `gs://…/runs/20261114-191700_abc_cfg15/`**
  - `repro_abc_cfg15.wav` (sha `4f9006de…`, 224.238667 s)
  - `tokens/abc_cfg15_semantic.json` (sha `c218c41c…`, 5606 frames)
  - `session/repro.log`, `score.abc`, `gate/`, `listen/`

**One line to remember:** choose the take you will keep, repair it from its own
tokens, measure the unit on its stem, and let the ear — not the gate — choose
the base.
