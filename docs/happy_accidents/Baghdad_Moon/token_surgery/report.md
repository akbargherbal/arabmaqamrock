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

### 6.4 Round-3 listening pack, scorecard and verdict

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

**Verdict (2026-10-20 12:57 UTC, `rating_20261020-1557.md`).** Six tracks rated,
not blind, run `scorecard_baghdad_moon_e2_round3`:

| take | `ف` onset | diction | melody | seam | naturalness | overall | keep |
|---|---|---:|---:|---|---:|---:|---|
| `00_ORIGINAL` | still `ب` | 1 | 1 | bad | 1 | 1 | no |
| **`e2_ar_s08`** | **fixed** | **5** | **5** | **none** | **5** | **5** | **yes** |
| **`e2_ar_s13`** | **fixed** | **5** | **5** | **none** | **5** | **5** | **yes** |
| `e2_ar_s14` | unclear | 4 | 4 | none | 5 | 4 | maybe (`ف` heard as `v`) |
| `e2_ar_s11` | fixed | 5 | 1 | bad | 1 | 1 | no |
| `e2_ar_s07` | still `ب` | 1 | 1 | bad | 1 | 1 | no |

- **`s08` and `s13` both fix `فَإِنَّ`** and are rated equal (5/5, keep). `s08`
  is chosen because it also had the best rhythmic alignment with the original
  (5.5 dB vs 5.8 dB); `s13` remains an equally-rated alternate.
- `s11` proves the phoneme was right but the *tail* collapsed after the word
  (`الله` mangled into `ينزعه`); `s07` re-sang `عَلَيْهِ` twice and kept `ب`.
- The listener flagged one limitation: the 7 s clips end inside `ينزعه`, so the
  final syllable of the outro could not be judged. **This does not affect the
  delivery**: only 201.835–204.775 s is taken from `s08`, and everything after
  204.775 s — including `ينزعه` — remains bit-identical to the original, so a
  tail collapse like `s11`'s cannot propagate into the final track.

### 6.5 Final assembly and QC

`FINAL_e1_ar_s03_s08.wav` = word-1 hybrid `e1_ar_s03` (already accepted) +
whole-word `s08` comp for `فَإِنَّ`, assembled by `runs/assemble_final.py`:

| check | value |
|---|---|
| final sha256 | `51c6e238dfaad123779e32b113786df651b4c7053771f6f7dfc4970e2fb2a8e1` |
| format | 48 kHz, stereo, PCM_16, 215.879 s (10,362,176 frames, 41,448,748 bytes) |
| original sha256 | `dbc00722…` — unchanged, never overwritten |
| comp regions | 156.995–158.855 s and 201.835–204.775 s (`identical_outside_regions: true`) |
| measured changed span | 156.9964–158.8546 s and 201.8353–204.7747 s (230,261 samples) |
| max abs diff outside regions | **0** |
| e1 region vs `e1_ar_s03` | max diff **0** |
| e2 region vs `e2_ar_s08` | identical except the 40 ms cosine fades at each edge (1905 / 1903 samples) |
| splice continuity | sample step at all four cuts equals the original (391.5, 2127.5, 482.0, 1089.5) → no click/DC step |

A final A/B pack of the *delivered* audio is in `deliverables/listen_final/`
(`00_ORIGINAL__e1/e2` vs `FINAL__e1/e2`) for last-mile confirmation; the full
track is `deliverables/tracks/FINAL_e1_ar_s03_s08.wav`.

### 6.6 Post-delivery listen — the outro join (open)

The user's verdict on the delivered track (2026-10-20 PM): **S1 is
transparent, S2 has a sudden jump — it sounds like two clips joined.** The
phoneme is right; this is a comp/join problem, not a pronunciation problem.

Measured (10 ms envelopes, original vs `s08`; word timing from `evidence.md`):

- The comp edges are fixed word ± 0.3 s, not chosen at word/phrase boundaries.
  With the ASR/CTC timing, the start (201.835 s) is inside the preceding
  `عَلَيْهِ` (201.04–202.26 s) and the end (204.775 s) is inside `الله`
  (204.54–204.98 s) — the comp cuts both neighbours mid-vowel.
- Neither edge is low-energy: 201.835 s sits in a sustained ~74–75 dB region,
  204.775 s at ~71 dB.
- At the end cut `s08` is ~**+3.5 dB** relative to the original, and the
  envelopes diverge immediately after (205.10 s: original 76.2 dB, take
  69.3 dB). The 40 ms fade removes the click but not the level/timbre step.
- The comp reverts to the original **mid-phrase**. The model re-sings
  `فَإِنَّ اللهَ يَنْزِعُهُ` as a unit (202.26–207.74 s); we keep only
  `فَإِنَّ` and cut back to the original inside `الله`, discarding the model's
  phrase continuation.

Next options (details and cost order in `PROGRESS.md` §4):

1. **Sub-phrase comp** (`فَإِنَّ اللهَ يَنْزِعُهُ`, 202.26–207.74 s) from the
   existing `s08` / `s13` tails, end after 207.74 s (or at minimum after
   `الله`, 204.98 s), no GPU. Risk: replaces more original audio and `s08`'s
   post-word envelope drifts after ~205 s, so audition before committing.
2. Word-level comp with level matching and a longer fade at envelope
   crossings — cheap sanity check, may not fix phrase continuity.
3. Demucs vocal/instrumental split; comp the **vocal stem only** against the
   original instrumental. `demucs` is not installed in the current runtime.
4. GPU: re-render the phrase with an earlier prefix (frame ~4980–5000) for
   lead-in, then phrase-comp.

The user's cut-point idea — 4-stem separation, cut at the lowest trough across
stems — is sound for *attribution* (avoid sustained bass, drums, held vowels),
but stems sum to the mix, so the global trough is essentially the mix trough.
For a vocal comp the primary criterion should be a voiceless gap/breath in the
lead vocal, with the instrumental stems as constraints. Case-by-case is the
right policy: keep the transparent S1 word-level edit, reconsider only S2.

### 6.7 Round 4 — phrase-level S2 comp (in progress)

Approach: treat `فَإِنَّ اللهَ يَنْزِعُهُ` as one unit (202.26–207.74 s), comp
the whole phrase, and put both joins in the performance:

| setting | value |
|---|---|
| region | **202.21–207.90 s** (enter in the vocal breath 202.15–202.21, leave after the phrase) |
| fade | 50 ms in, 120 ms out, cosine |
| level | linear dB gain ramp matching the take to the original at the edges |
| delivery | **vocal stem only**, original instrumental kept (Demucs htdemucs) |
| outside | bit-identical to the original / to the accepted word-1 hybrid |

Take choice was re-done at **phrase level**, not word level. All 16 existing
tails scored over 202.26–207.74 s: `s13` is best (envelope corr 0.50 at 0 ms,
word 0.66, `الله` 0.74, `ينزعه` 0.51); `s08` — the word-level winner — is 0.30
at +190 ms and is not suitable for a phrase comp.

Demucs shows why a full-mix comp is wrong here: over the phrase, the take's
instrumental stems correlate with the original at ≈0 (drums −0.34, bass −0.33,
other −0.03) and drums are +4 dB louder. A full-mix comp would replace the
arrangement; the vocal-stem comp keeps the original music.

First candidate (`s13`, vocal): edge level steps **0.0 dB / −0.4 dB** (v1 was
~+3.5 dB at the end), changed only 202.2105–207.8996 s plus the word-1 region,
outside max diff **0**, sha256 `19343646…`. It is in `listen_v5/` as `23`.

16 new tails (prefix 5056, seeds +16..+27; prefix 5040, +16..+19) are
rendering on the T4. They will be scored the same way; the best take replaces
`s13` if it improves whole-phrase continuity.

### 6.8 Round 5/6 — the final `ه` is a ~5.5 s melisma (correction)

The user's diagnosis was exact: the final `ه` of `يَنْزِعُهُ` is not a word
ending that can be crossed at 207.9 s; it is a long melismatic hold.

Measured on the Demucs vocal stem, original take:

| event | time | measurement |
|---|---|---|
| `فَإِنَّ` | 202.26–204.54 | lyric/ASR timing |
| `الله` | 204.54–204.98 | lyric/ASR timing |
| `يَنْزِعُ` | 204.98–~207.7 | lyric/ASR timing |
| **final `ه`** | **~207.7–213.2** | stable **G4 ≈ 391 Hz** (p10–p90 389–394 Hz), ≈5.5 s |
| release/reverb | 213.2–~215.3 | level falls from −21 dB to −45 dB |
| track end | 215.879 | — |

The phrase comps `20`–`31` ended at **207.90 s**, i.e. **160 ms into the
hold**. They therefore cut the candidate’s `ه` and handed the rest of the same
note back to the original. That is the audible “another `ه` comes after”.

The envelope-only phrase score missed a second, independent problem:

| take | final-note pitch | final-note duration | verdict |
|---|---|---|---|
| original | **G4 ≈ 391 Hz** | ~5.5 s + release | reference |
| `s13` | **D4 ≈ 295 Hz** | ~2.8 s | wrong final note; cannot be fixed by moving the cut |
| `s08`/`pick` | G4 ≈ 391 Hz | ~3.0 s | correct pitch, too short |
| `p5056_s25` | G4 ≈ 391 Hz | ~5.1 s, but decays earlier/quieter | closest new take; still not the original hold |
| `p5040_s17` | G4 ≈ 391 Hz | active to ~212.2, then artifacts | too short/unstable |
| `p5056_s18` | G4 ≈ 391 Hz | ~1.4 s | correct pitch, much too short |

So no generated take reproduces the original’s 5.5 s hold at the same level.
Replacing the hold with a shorter take is worse than keeping the original.

**Minimal fix:** replace only `فَإِنَّ`, region **202.21–204.54 s** (the
`فَإِنَّ` / `الله` boundary), and leave the original `اللهَ يَنْزِعُهُ` —
including the entire final `ه` — untouched:

| candidate | first word | shift | exit crossfade | edge step at 204.54 |
|---|---|---|---|---|
| `40` | `s13` | −110 ms | 80 ms | −0.58 dB |
| `41` | `s13` | 0 ms | 80 ms | −0.36 dB |
| `42` | `s13` | −110 ms | 150 ms | −0.19 dB |
| `43` | `p5056_s18` | +20 ms | 80 ms | −0.99 dB |

All four pass bit-identity outside 156.995–158.855 s and 202.21–204.54 s
(outside max diff **0**). Pack: `deliverables/listen_v6/`, with full-outro
(200–215.879 s) and hold-only (207.5–215.879 s) clips.

**Verdict (2026-10-20): `41` accepted; the others rejected.** `41` is `s13`,
no timing shift, 80 ms crossfade at 204.54. `40`/`42` (110 ms shift) and `43`
(`s18`) did not pass. The user also judged the hold-only clips `50`/`51`/`52`
**sub-word**: starting at 207.5 s isolates the sustained vowel
(“عهوووو”), not `يَنْزِعُهُ`, so they are a technical check, not a valid word
A/B. They were withdrawn. The final review pack
(`deliverables/listen_final_v2/`) contains full tracks plus a complete
outro-to-end file; no clip ends inside a sung word.

v2 final: `FINAL_e1_ar_s03_s13_41.wav` — 215.879 s, sha256 `9b8fdb…`.
Changed spans **156.9964–158.8546 s** and **202.2105–204.5395 s**; outside
max diff **0**; 207.5 s–end hold byte-identical to the original
(raw-sample sha256 `dbb7ec72…`).

## 7. Files

- Final track (v2): `happy_accident/deliverables/tracks/FINAL_e1_ar_s03_s13_41.wav`
- Final A/B clips (v2): `happy_accident/deliverables/listen_final_v2/`
- Superseded v1 track: `happy_accident/deliverables/tracks/FINAL_e1_ar_s03_s08.wav`
- Multi-session summary: `PROGRESS.md`
- Round-3 raw results: `docs/.../results_20261020_e2_round3.json`,
  `docs/.../rating_20261020-1557.md`
- Full candidates: `happy_accident/runs/token_surgery/v2/<id>.wav`
- Local comps: `happy_accident/runs/token_surgery/v2/hybrid/<id>.wav`
- Audition clips (original + H1–H4, e1 and e2 windows):
  `happy_accident/deliverables/listen/`
- GCS mirror: `gs://akbar-december-2024-backup/arabmaqamrock/runs/20261019_baghdad_moon_token_surgery/`
