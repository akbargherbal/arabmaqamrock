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

## 5. Human evaluation (round 1) — all four rejected

Source: rating app export `rating_20261020-1223.md`, raw data in
`results_20261020.json` (10 clips, blind off). The listener rated the original
and H1–H4 on both words.

| version | e1 verdict / diction | e2 verdict / diction | melody | seam | overall | keep |
|---|---|---|---:|---:|---:|---|
| `00_ORIGINAL` | still wrong / 2 | still wrong / 1 | 5 | none | 1 | no |
| `H1_minimal` | still wrong / 2 | still wrong / 1 | 2 | **bad** | 2 | no |
| `H2_e2word` | still wrong / 2 | still wrong / 1 | 2 | **bad** | 1 | no |
| `H3_e1word` | still wrong / 2 | still wrong / 1 | 1 | **bad** | 1 | no |
| `H4_bothword` | still wrong / 2 | still wrong / 1 | 1 | **bad** | 1 | no |

Verdict: **0/4 accepted**. Two distinct failures, and they have different
causes.

### 5.1 Word 2 — the comp region was too short (delivery bug, now fixed)

The listener's description is precise: *“he starts ف … then sings the wrong
word again (بِأَنَّ)”*, and for H2 *“he sang (فَإِنَّ) fully but stopped in the
middle of the nūn — out came (فإ) + half a nūn”*, with a bad seam.

Cause: `audio_splice.py` grafted only the frames that **differ from the
baseline**, not the whole word. For e2 the edit window is 58 frames
(202.24–204.56 s) but only the first 13 or 26 frames carry changed tokens:

| hybrid | grafted | word actually spans |
|---|---|---|
| H1/H3 | 201.84–203.16 s | 202.24–204.56 s |
| H2/H4 | 201.84–203.52 s | 202.24–204.56 s |

So the graft ended 1.0–1.4 s before the end of the word, and everything after
the cut was the original `…بِأَنَّ` again. Sample inspection confirms it: the
first differing sample after 203.515 s is *identical to the original*.
The listener heard exactly that: corrected onset, original tail.

Fix: `audio_splice.py` now takes `--word-ranges 3933:3964,5056:5114` and
extends every changed run to the whole word before adding margin and snapping
to quiet points. New comps in `runs/token_surgery/v2/hybrid_full/`, regions
156.995–158.855 s and 201.835–204.775 s, `identical_outside_regions: true`.

### 5.2 Word 1 — the donor does not carry a convincing `ه`

Even H3/H4, which replaced the **whole** 31-frame word with the Outro instance,
were heard as unchanged (`عَلِيم`, diction 2, "no regression, no fix"). The
Outro donor is the muddy instance; its final consonant is not a clean `ه`.
The donor route for e1 is exhausted — see §6.

## 6. Round 2 — AR resample for word 1

Fallback from the checkpoint: regenerate frames 3933–3964 from the AR model
with the correct lyrics, conditioning on the first 3933 tokens.

```
semantic_prefix_file = tokens_prefix_e1_3933.json   (first 3933 frames)
semantic_min_tokens = semantic_max_tokens = 3964    (exactly 31 new frames)
seeds 1712905618 + 0..15
```

Each run re-sings the word with the real lyric text, so `ه` is available to
the model; the seed sweep gives several renditions to choose from. The render
itself already contains the word in full context (0–158.56 s), so candidates
can be auditioned before committing to a full 5397-frame render. Only the
winner is rendered once more as a complete stream and comped into the original
(word-span graft).

### 6.1 Result — word 1 is fixed

16 seeds were generated; 4 diverse ones got full 5397-frame renders and were
comped. The listener tested 6 versions in `deliverables/listen_v3/`:

| version | what it is | verdict |
|---|---|---|
| `e1_ar_s01`, `e1_ar_s03`, `e1_ar_s04` | AR re-sing, whole-word comp | **pass** |
| `e1_ar_s15` | AR re-sing, whole-word comp | fail |
| `GNOTE_donor_audio` | Outro's final note as audio | fail |
| `GWORD_donor_audio` | Outro's whole word as audio | fail |

The two *real-audio* grafts also failed, which is informative: the listener's
problem with the old candidates was not merely "wrong timbre" — the donor word
itself does not deliver a convincing `ه` in the Verse-2 context, whether it is
re-synthesised from tokens or copied as audio. Only re-singing the word from
the lyric works.

Winner: **`e1_ar_s03`** (the user rated s01/s03/s04 as equally good; s03 also
has the best donor DTW of the three). Comp region 156.995–158.855 s,
`identical_outside_regions: true`.

### 6.2 Word 2 — the donor splice still fails

The whole-word comp (`E2_FIXED_fullword`, region 201.835–204.775 s) removed the
mid-word cut, but the listener still hears the wrong word: the donor's 26-frame
`فَإِنَّ` spliced into a 58-frame slot does not transfer the `ف` either.

Same conclusion as word 1: re-sing it. The documented fallback is a tail
resample — prefix = first **5056** frames, `semantic_max_tokens = 5397`, seeds
`1712905618 + 0..15`. 16 tails are rendered; the four most diverse will be
auditioned before any comp.

### 6.3 Result — 16 tails, five auditioned

All 16 renders are valid: 5397 frames, first 5056 tokens identical to the
baseline, 338–341 regenerated tail frames. The takes are mutually unrelated
(55–58 of the word's 58 tokens differ between any two), so the shortlist was
chosen for **rhythmic alignment** — how closely the 202–205 s energy envelope
matches the original (a shifted or dropped word shows up as a 15–20 dB dip):

| seed | max 50 ms level Δ | verdict |
|---|---:|---|
| s08 | 5.5 dB | auditioned |
| s13 | 5.8 dB | auditioned |
| s11 | 6.2 dB | auditioned |
| s14 | 6.2 dB | auditioned |
| s07 | 6.4 dB | auditioned |
| s00, s04, s10 | 14–20 dB | rejected before audition (word displaced/dropped) |

Pack: `deliverables/listen_v4/` (original + 5 seeds, window 199.8–206.8 s).
Only the chosen seed gets comped (region 201.835–204.775 s).

### 6.4 Round-3 listening pack and scorecard (pending)

`deliverables/listen_v4/` contains `00_ORIGINAL` plus `e2_ar_s08`, `s13`, `s11`,
`s14`, `s07`, all cut 199.8–206.8 s. The rating-app scorecard is
`scorecard_baghdad_moon_e2_round3.json` (schema v1, 10 Arabic questions:
`ف` onset, diction, word completeness, seam, melody, naturalness, overall,
"pick this take"). It scores word 2 only; word 1 is already fixed and is not in
this pack.

The clips are cut from raw AR renders, so the 13.6 s tail is a fresh take —
listeners are told not to judge the music after the word. In the final track
only the word is taken from the winner; everything outside the comp regions
stays bit-identical to the original.

**Clipping rule.** An AR tail render differs from the baseline over the whole
regenerated tail (341 frames), not just the word. `--word-ranges` therefore
*clips* a changed run to the word it touches instead of extending it; otherwise
the comp would replace the entire 13.6 s outro. Verified: the assembled track
changes only 156.996–204.775 s in two regions and the original stays
`dbc00722…`.

## 7. Files

- Full candidates: `happy_accident/runs/token_surgery/v2/<id>.wav`
- Local comps: `happy_accident/runs/token_surgery/v2/hybrid/<id>.wav`
- Audition clips (original + H1–H4, e1 and e2 windows):
  `happy_accident/deliverables/listen/`
- GCS mirror: `gs://akbar-december-2024-backup/arabmaqamrock/runs/20261019_baghdad_moon_token_surgery/`
