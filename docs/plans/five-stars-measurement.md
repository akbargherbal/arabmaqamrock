# Plan — Five Stars measurement script

**Status:** M1 implemented and run (2026-10-25); M2–M6 not started
**Date:** 2026-10-25
**Owner:** this repository (`arabmaqamrock`)
**Supersedes:** §8 (Phase 3) of `docs/plans/five-stars-abc-corpus.md`
**Inputs:** `v1/transcripts/` (177 ABC + per-track artifacts), `v1/corpus/*`,
`../Five_Stars_ArabMaqamRock/FIVE_STARS_DATASET/` (177 MP3)
**Outputs:** `derived/` — facts tables, no prose
**Compute:** CPU only. No GPU, ever, for this script.

## 1. Why this script exists

The deliverable is a **style document** that an LLM reads to write ABC scores
from new lyrics. A document is only as good as its evidence: an LLM asked to
write "how maqam Hijaz works" will produce fluent, confident, wrong prose. The
only defence is that **every claim in the document traces to a count over the
corpus**.

So this script is the evidence layer. It produces numbers; agents later write
prose over the numbers. It must never contain an opinion.

Two rules follow, and they are the whole design:

1. **No prose, no recommendations, no music theory.** Only quantities,
   counts, and per-track flags. A field that would require an interpretation is
   out of scope.
2. **Two sources of truth, kept separate.** The ABC tells us *what the
   transcription thinks*; the audio tells us *what is actually played*. Where
   they disagree, that is a finding to record, not an error to fix.

## 2. The finding that shapes the design

A first probe (3 tracks, first 120 s, `chroma_cqt` over the HPSS harmonic
component, fmin 130.8 Hz, 4 octaves) put the audio and the maqam label at odds:

| Track | Label | Audio pitch content | Defining degree missing |
|---|---|---|---|
| `6d35a1fb` | Hijaz | C natural minor (C D Eb F G Ab Bb) | Db — the Hijaz second |
| `71530287` | Kurd | D minor/Dorian (D E F G A B C) | Eb — the Kurd second |
| `85895ab9` | Ajam | G minor/Dorian (G A Bb C D F) | B natural — the Ajam third |

A syntax survey of 11 ABC scores says the same thing from the other side:
`K:` is always a **minor** key (`Cm`, `Dm`, `Gm`, `D#m`), no accidentals are
written in most files, and no score contains a Hijaz (b2 + natural 3) or Kurd
(b2 + b3) signature interval.

This is consistent with an earlier finding in this repository (a "Hijaz" track
that was really G natural minor).

**Working hypothesis:** the maqam label came from the *generation prompt* — the
corpus owner confirms the four names were written into the prompt used to render
these tracks. How faithfully the renderer honoured them is unknown, and is not
assumed either way. The labels therefore describe a request, not a measurement,
and the document must be built on the latter.

**This is not yet established.** The probe is 3 tracks, 2 minutes each, with a
method that has real weaknesses (no tonic prior, no microtonal handling, mixed
sources in the chroma). §5 makes it the first milestone, measured properly. The
rest of the plan is written to be correct under *either* outcome.

Why it matters: it decides whether the document is called **"how to write
Hijaz"** or **"how this corpus actually sounds"**. Choosing the first when the
second is true would produce a document that is confidently wrong in exactly the
way §1 warns about.

## 3. What counts as measurement

| In scope | Out of scope |
|---|---|
| counts, distributions, medians, IQRs | adjectives ("often", "characteristic") |
| per-track flags with evidence | fixes to the ABC or audio |
| agreement / disagreement between sources | picking exemplars |
| scale degrees relative to an estimated tonic | naming the maqam of the *music* |
| note-level facts recovered from ABC and audio | claims about Arab music theory |

The corpus's own label is recorded as a *string*, never as ground truth.

## 4. Data sources

| Source | Path | Used for |
|---|---|---|
| ABC scores | `transcripts/<id>/score.abc` | structure, metre, tempo, note sequence, phrase shape |
| Note events | `transcripts/<id>/events.json` | cross-check of the ABC parse |
| Note lists | `transcripts/<id>/melody_{vocal,instrumental}.lab` | independent check of per-voice membership |
| Keys / structure | `notation/song_keys.txt`, `song_structures.txt` | the model's own key and section guesses |
| Audio | `FIVE_STARS_DATASET/<maqam>/<id>.mp3` | **pitch truth**, tempo of the real performance |
| Corpus index | `corpus/manifest.jsonl` | label, mood, poem, duration, style prompt |
| Lyrics | `corpus/lyrics.jsonl` | line and section counts, syllable estimate |

`manifest.jsonl`'s `audio_path` uses the packaged layout (`audio/<maqam>/<id>.mp3`).
The local tree uses `FIVE_STARS_DATASET/<maqam>/<id>.mp3`. The script takes one
`--audio-root` and maps.

## 5. M1 — what is actually in the corpus

**Question:** for each track, what pitch content is there, in the audio and in
the ABC, and how does the corpus group by content?

**The label is provenance, not ground truth.** Hijaz / Kurd / Nahawand / Ajam
were given to Suno in the generation prompt. How faithfully the renderer honoured
them is unknown, and this plan does not assume it either way. M1 does **not**
test whether the labels are "right": it describes the content and reports
label-vs-content agreement as one descriptive statistic among several.

A track labelled Hijaz whose content is diatonic is not an error to be corrected.
It is a fact about the generation pipeline, and it is recorded alongside the
prompt that produced it.

Method, per track:

1. Estimate the **tonic from audio**, not from membership (see §8.1).
2. Classify by the **2nd and 3rd degrees above that tonic** — a 2×2 that
   separates all four labels:

   | 2nd | 3rd | ⇒ |
   |---|---|---|
   | natural (2) | natural (4) | Ajam |
   | natural (2) | flat (3) | Nahawand |
   | flat (1) | flat (3) | Kurd |
   | flat (1) | natural (4) | Hijaz |

3. Repeat the same classification from the ABC.
4. Compute the **tonic-free** Hijaz test (§8.6) for both, which does not depend
   on any tonal-centre judgement.
5. Emit `scale_label`, `scale_abc`, `scale_audio_at_abc_tonic`,
   `scale_audio_own`, plus `hijaz_excess` for both sources.

**Output:** cross-tabulations of label against each content measure, plus
per-track rows. The question the tables answer is *"what is in this corpus and
how is it grouped?"*, not *"did Suno obey?"*.

**Acceptance:** every track classified or explicitly `unclassified`, the
unclassified rate below 10%, and the 11 surveyed tracks reproduced.

**Decision gate.** When M1 reports, the corpus is one of these, and each implies
a different shape for the document:

| Corpus finding | Consequence for the document |
|---|---|
| content tracks the label groups | organise the document by maqam label |
| content is uniform across labels | document describes one realised style; the label is a tag, not a category |
| content clusters, but not by label | organise by content cluster, and cite the label only as provenance |
| content is heterogeneous within labels | no aggregate document; per-cluster sections or per-track exemplars |

Do not write M2+ results into the document before this reports.

### 5.1 M1 result — 2026-10-25

Run: `./measure.py --stage m1 --jobs 8` over 177 tracks, 3m11s. Artefacts in
`datasets/five_stars/derived/m1/` (`tracks.jsonl`, `REPORT.md`, `params.json`,
`audio_cache/`).

| measure | value |
|---|---|
| Hijaz-tagged tracks that are Hijaz-shaped in audio | **0 / 49** |
| Non-Hijaz tracks that are Hijaz-shaped in audio | **0 / 128** |
| ABC Hijaz-shaped, any label | **0 / 177** |
| ABC vs audio classification, same tonic | **90%** |
| Hijaz verdict agrees, ABC vs audio | **100%** |
| Label vs audio content | 23% |
| Label vs ABC content | 27% |
| ABC tonic vs audio tonic | 50% |
| Unclassified (audio, at the score's tonic) | 10.2% |

**1. There is no Hijaz in the corpus.** Not in the audio, not in the ABC, in any
track, under any tag. This is the tonic-free test (§8.6), and a third-tone
resolution check on 40 tracks confirms it is not a rounding artifact: the
133–166-cent band — where a neutral Hijaz second would sit — carries 1.1–2.8% of
energy in *every* label group, identically. The 100-cent band is equally empty.

**2. The transcription is faithful.** ABC and audio agree 90% of the time when
read at the same tonic. The ABCs are a good record of what is in the audio; the
transcription is not the weak link.

**3. The four label groups are indistinguishable on pitch content.** Key
signature distributions are the same (`Dm` dominant in all four), median
diatonic mass is 0.999–1.000 in all four, and the mean chroma profiles correlate
0.992–0.998 between every pair of groups. There is no measurable pitch-content
difference between tracks tagged Ajam, Hijaz, Kurd and Nahawand.

**4. The realised style is one thing.** Diatonic throughout, `K:` minor in
177/177, most often the D-minor set, with `A` the most common tonic — i.e.
Phrygian-on-A / natural-minor-on-D as the dominant sonority, across all tags.

**Acceptance:** partially met. Every track classified or explicitly
`unclassified`, but the unclassified rate is **10.2%**, marginally over the 10%
target. The cause is diagnosed and does not affect the Hijaz result: the 2nd
degree splits ~50/50 flat/natural because the tonic is uncertain, so the 2×2
cannot resolve it. The Hijaz test does not use a tonic and is 100% unambiguous.

**Gate decision recorded: "content is uniform across labels"** → the document
describes **one realised style**, with the maqam tag carried as provenance. Four
maqam cards are not supported by this corpus.

**What this does and does not block.**

- *Blocked:* teaching Hijaz (or any maqam's defining intervals) **from this
  corpus**. The evidence is not there, and no amount of aggregation will create
  it.
- *Not blocked:* everything else the document needs — form (intro/verse/chorus/
  outro), phrase length, note density, vocal and instrumental register, tempo,
  two-voice ABC layout, section order, melisma estimate. That is corpus-derived
  and measurable.
- *Separate, if wanted later:* maqam pitch guidance has to come from theory or
  from real maqam recordings, and must be labelled as **not** corpus-derived.
  Mixing the two without marking which is which would produce exactly the
  confident-but-unsourced document §1 exists to prevent.

### 5.2 Structural measurements — the document's evidence

Run 2026-10-25, `./measure.py --stage structure`, 177/177 tracks, Vocal voice.
Artefacts in `datasets/five_stars/derived/structure/`.

| property | median | p10–p90 |
|---|---|---|
| bars per track | 126 | 82–152 |
| notes per bar | 3.8 | 3.1–5.5 |
| bars containing a note | 85% | 74–93% |
| notes per lyric line | 16.9 | 14.8–19.3 |
| notes per syllable | 1.28 | 1.16–1.41 |
| phrase length | 4 bars | 3–5 |
| notes per phrase | 16 | 14–20 |
| step motion (≤2 st) | 85% | 81–88% |
| leaps ≥5 st / ≥8 st | 4.2% / 0.9% | 2.5–5.9 / 0.2–2.2 |
| repeated notes | 33% | 29–38% |
| chorus minus verse mean pitch | +2.4 st | 0.0–5.4 |
| vocal register | F4–A5, centre D5 | — |
| section bars: verse/chorus/intro/interlude/bridge | 18/16/9/8/8 | — |

Two findings changed the spec rather than describing the corpus:

- **The two voices drift apart** by a median of 23 bars, and by more than 4 bars
  in 166/177 tracks. The transcriptions are not bar-aligned across voices, so the
  spec prescribes **one voice** (`V: Vocal`), which is also what `COT=melody`
  consumes.
- **The corpus is bar-incomplete** in a median of 17 bars per track, mostly by
  half a beat. The spec therefore demands complete bars, which is a correction of
  the corpus, not an imitation of it.

The bar-budget formula in §2 comes from `run_one.sh`'s duration cap, and was
checked against the corpus: implied duration at 110 BPM has median 288 s versus a
formula median of 290 s (ratio 0.99).

### 5.3 Deliverables built on these measurements

| File | Role |
|---|---|
| `prompts/arabmaqamrock_abc_spec.md` | the document itself — pasted into the LLM conversation above the lyrics |
| `check_abc.py` | external validator: 11 structural checks plus an n-gram originality test against the corpus |

`check_abc.py` exists because two of the document's requirements cannot be
self-verified by the model that wrote the score: *"every bar is complete"* and
*"this is not a copy"*. The second is measured as the count of shared 8-grams of
`(interval, duration)` against all 177 tracks.

Validated by two independent generation runs on `baghdad_moon_lyrics.txt`
(agent given only the spec and the lyrics): 10/11 and 11/11 checks passed, both
with **zero shared 8-grams**. Each run surfaced ambiguities that were then fixed
in the document — octave spelling, how to count letters, what to do when a
section has fewer lines than its median, and how to raise the chorus without
modulating.

## 6. ABC parser spec

Built from an 11-file syntax survey. Anything outside this inventory must **fail
loudly with the track id**, never silently skip — a parser that skips notes
produces a wrong histogram, and wrong histograms are undetectable downstream.

**Header lines** (each once, before music):

| Field | Observed | Notes |
|---|---|---|
| `X:` | always `1` | |
| `T:` | always empty | |
| `M:` | `4/4`, `2/4`, `1/4`, `3/4`, `3/8` — and **99 occurrences across 11 files** | mid-score changes; must be per-bar |
| `L:` | `1/16` or `1/32` | default note length, per file |
| `Q:` | `1/4=63` … `1/4=119` | must be parsed; see §8.4 |
| `V:` | `Vocal`, `Ins` | two forms: full declaration, and bare switch |
| `K:` | `Cm`, `Dm`, `Gm`, `D#m` | always minor |
| `%` | `% intro`, `% verse`, `% chorus`, `% outro` | section boundaries |

**Music syntax present:** notes `A-G`/`a-g` with `^`/`_`/`=` prefixes (0–2) and
`,`/`'` octave suffixes; lengths (`2`, `4`, `/2`, `3`); rests `z`; multi-measure
rests `Z` / `Z4`; ties `-` across a barline; bar separators `|`.

**Not observed** in the survey but must be detected and reported if they appear
across the full set: chords `[..]`, grace `{..}`, tuplets `(3`, broken rhythm
`>`/`<`, `w:` lines.

**Found during implementation, absent from the 11-file survey:**

- **Inline fields `[K:..]`, `[M:..]`, `[L:..]`, `[V:..]`.** One track
  (`9ccadbaf`) changes key five times (`Fm → Bbm → Bbm → Fm → Fm`). A parser that
  does not apply an inline key change transposes every subsequent note. This was
  caught only because the parser refuses unknown syntax instead of skipping it —
  which is the argument for that rule.
- **Key signatures actually used across 177 tracks:** `Dm` 72, `D#m` 31, `Gm` 28,
  `Cm` 20, `Fm` 15, `Em` 4, `Am` 3, `BBm` 2, `G#m` 1, `Bm` 1. All minor. `D#m` is
  enharmonic with `Eb minor`; it must be spelled consistently or the pitch-class
  arithmetic drifts.

**Not present anywhere in the 177:** chords, grace notes, tuplets, broken
rhythm, `w:` lines, `%%` directives.

**Validation the parser must perform**, per bar:

- the summed duration equals the active `M:` — a mismatch is a flag, not a
  crash (it is evidence about transcription, not about the parser);
- note count per voice reconciles with `events.json` (pitch multiset equality
  modulo ties and rests). This is the parser's own correctness test and it is
  mandatory: it is the only way to know the parser is not lying.

## 7. Output tables

Long-form JSONL, one row per unit, `track_id` first, sorted. All derived from
`manifest.jsonl` — no track may appear that is not in the manifest, and none may
be missing.

| # | Table | Grain | Fields | Consumed by |
|---|---|---|---|---|
| T1 | `bars.jsonl` | track × voice × bar | meter, duration sum, ok, n_notes, lo/hi midi | structure section, filler-bar detection |
| T2 | `notes.jsonl` | note | bar, onset in quarters, midi, spelling, duration, tied, degree | everything downstream |
| T3 | `phrases.jsonl` | rest-delimited phrase | bars, n_notes, start/end degree, ambitus, contour | melodic-shape section |
| T4 | `sections.jsonl` | `%` section | bars, n_notes, density, mean pitch | form section |
| T5 | `pitch_profile.jsonl` | track | tonic + method + confidence, 12-bin ABC profile, 12-bin audio profile, degree histogram, 2×2 classification, label | M1 gate, maqam cards |
| T6 | `rhythm.jsonl` | track | `Q:`, meter distribution, note-length histogram, rest ratio | tempo/metre section |
| T7 | `intervals.jsonl` | track | semitone interval histogram, degree-2 and degree-3 presence and weight | maqam cards |
| T8 | `lyrics_facts.jsonl` | track | n_lines, n_sections, syllable estimate, notes-per-syllable | text-setting section |
| T9 | `flags.jsonl` | track × code | code, severity, evidence (bar, notes) | QC, exemplar exclusion |
| T10 | `aggregate/<maqam>.json` | maqam | median/IQR/min/max of every T5–T7 quantity + n | document writer |
| T11 | `ARTIFACTS.md` | — | T10 rendered as markdown tables | document writer |

T10/T11 are generated, never hand-edited. If a number in the final document
cannot be found in T10/T11, the document is wrong.

## 8. Methods that need to be pinned down

### 8.1 Tonic estimation

Membership cannot determine the tonic: a diatonic set is simultaneously "Ajam
on C", "Nahawand on A" and "Kurd on E". Any classifier that maximises template
overlap across rotations returns ties — confirmed experimentally in the §2 probe
and again during implementation, where three templates scored identically.

Worse, and not anticipated when this plan was written: **three of the four
labels are the same seven notes.** Ajam on X, Nahawand on X+3 and Kurd on X+8
are one pitch-class set. So "Ajam vs Nahawand vs Kurd" is not a test of pitch
content at all — it is a test of tonal centre and nothing else. Only Hijaz is a
different set. That asymmetry drives the design in §8.6.

Measured on 40 randomly chosen tracks, each candidate estimator compared against
the ABC's last sung note (an independent measurement, not the label):

| estimator | agreement |
|---|---:|
| bass chroma argmax | **62%** |
| 3.0·bass + 0.5·mid | 57% |
| 1.4·bass + 1.1·mid + 1.0·final (first attempt) | 55% |
| bass + 0.25·mid | 55% |
| 2.0·bass + 1.0·mid + fifth terms | 52% |
| 2.0·bass + 1.0·mid + fifth terms + scale coverage | 52% |

Two conclusions:

- **Bass emphasis is the best available cue** — it is where the drone or
  ostinato root sits, and it is the only band that a busy melody cannot swamp.
- **The fixed final-15-seconds window is worse than no cue at all.** In this
  corpus the final window is frequently an instrumental outro, so it reports the
  outro's tonal centre rather than the vocal cadence. It is kept as a diagnostic
  field and excluded from the cue.

62% is not a defect to tune away; it is a measurement that the tonal centre of
this repertoire is genuinely contested between two readings. The plan records
both tonics and never overwrites one with the other. The decisive comparison is
therefore made **at the score's own tonic** (§5), which isolates transcription
fidelity from estimator error.

### 8.6 Tonic-free test: Hijaz vs diatonic

Because only Hijaz has a distinct pitch-class set, the one maqam question that
can be answered without a tonic is "is this Hijaz?".

`hijaz_excess` = (best Hijaz template mass) − (best diatonic template mass), each
maximised over all 12 rotations. No tonic is assumed. No diatonic rotation
contains both a raised second and a natural third for any root, so a diatonic
track must score negative while a Hijaz-shaped one scores positive.

This is the gate's primary metric: it is insensitive to the tonic ambiguity that
compromises everything else, and it is computed identically from the ABC and from
the audio, so the two can be compared directly.

### 8.7 Audio chroma: a method that failed

The first implementation folded a single CQT into chroma by summing magnitudes
across octaves and bands. It produced a **near-uniform profile with no usable
peaks** (all 12 bins within 4.5–12.5%), which would have made every track look
"ambiguous" and every classification meaningless.

The cause: raw magnitude summation is dominated by the lowest, loudest octave,
and per-frame normalisation — which `librosa.feature.chroma_cqt` performs and a
hand-fold does not — is what keeps loud low harmonics from flattening the
profile. The fix is to call `chroma_cqt` three times with different `fmin` and
`n_octaves`, one per band.

Recorded here because the failure mode is silent: a flat chroma still produces
valid numbers, a valid report, and a confident verdict.

### 8.2 Microtonal handling

Arabic practice does not sit on exact semitones, and the corpus is labelled with
maqams whose defining degrees are the ones most likely to be mistuned. Chroma
bins smear that energy across neighbours. The script therefore reports, per
track, the **weight in the two semitones adjacent to each defining degree**
(e.g. both D and Db for a Hijaz second) rather than forcing a single choice.
A track whose defining degree is genuinely between bins is not "unknown"; it is
`microtonal`, and that is a distinct, reportable value.

### 8.3 Phrase segmentation

Two candidate rules, both computed, reported separately until one is justified:
rest-gap (silence ≥ one beat in the Vocal voice) and section-bounded (each `%`
section split at its longest rest). Phrase length in bars is the quantity that
matters for the document, so the rule must be stable across tracks.

### 8.4 Filler bars

`M:` changes 99 times across 11 scores, including `1/4` bars wedged inside `4/4`
passages. This is almost certainly the transcriber absorbing leftover beats, not
a musical metre change. The script must quantify it: bars whose duration is
shorter than the section's prevailing metre, and how often a metre change
coincides with a section boundary.

**The document must not teach filler bars as a stylistic feature.** T1 must
expose them so §9's writer can exclude them.

### 8.5 Syllable estimate

Full accuracy requires alignment (deferred). For a *global* melisma density, an
estimate is enough: count Arabic vowel diacritics plus long-vowel letters in the
NFC-normalised text, report it as `syllables_est` with an explicit
`estimate: true` field. `notes_per_syllable = vocal_notes / syllables_est`.
Report the estimate's own uncertainty (compare against 3 hand-counted lines).

## 9. Layout and CLI

```
datasets/five_stars/
  measure.py            # entry point, orchestration
  measure/
    abc.py              # parser + validation
    audio.py            # chroma, tonic, 2x2 classification
    facts.py            # T1..T9 assembly
    aggregate.py        # T10/T11
```

```
./measure.py --transcripts /content/out/transcripts \
             --manifest  ../v1/corpus/manifest.jsonl \
             --lyrics    ../v1/corpus/lyrics.jsonl \
             --audio-root ../Five_Stars_ArabMaqamRock/FIVE_STARS_DATASET \
             --out derived/ \
             [--stage parse|audio|facts|aggregate|all] \
             [--only <track_id>] [--jobs N]
```

Staged so a failure in audio does not lose parsed facts, and so a single track
can be inspected.

## 10. Milestones and acceptance

| M | Work | Accepted when |
|---|---|---|
| M1 | audio pitch + 2×2 classification + confusion matrices (§5) | every track classified; 11-track survey reproduced; gate decision recorded in this plan |
| M2 | ABC parser + `events.json` reconciliation (§6) | 177/177 parse; pitch multisets match `events.json`; every bar either sums to its metre or is flagged |
| M3 | T1–T2, T6 | bars, notes, rhythm; filler-bar count reported |
| M4 | T3–T4, T7 | phrases, sections, intervals; phrase rule stability measured both ways |
| M5 | T5, T8, T9 | profiles, lyrics facts, flags |
| M6 | T10–T11 | per-maqam aggregates render to markdown; a spot-check of 5 numbers reproduces from T2 by hand |

## 11. Determinism, performance, dependencies

- **Deterministic:** sorted iteration, no timestamps in table bodies, fixed
  audio analysis parameters recorded in the output header (fmin, hop, n_octaves).
  Re-running must produce byte-identical tables.
- **Performance:** ABC parsing is seconds. Audio analysis is the cost — 12.7 h
  at `chroma_cqt`/hop 1024 is roughly 2 h single-threaded, ~20 min at
  `--jobs 8`. Memory is one track at a time; no corpus-wide audio load.
- **Dependencies:** `numpy`, `librosa`, stdlib. `abc2midi` is *not* installed on
  this machine and is **optional**, used only as an independent parse check —
  the parser's real test is the `events.json` reconciliation.

## 12. Non-goals

- no edits to any ABC or audio file
- no exemplar selection, no tiers, no token budgeting (that is §9 of the corpus
  plan)
- no alignment / `w:` lines
- no synthesis, no rendering, no listening evaluation
- no statement about what the music "is", only about what it contains

## 13. Risks

| Risk | Consequence | Mitigation |
|---|---|---|
| Labels are aspirational (§2) | the document describes maqams that are not there | M1 gate runs before any writing |
| Parser silently drops notes | every downstream histogram is wrong and looks plausible | mandatory `events.json` reconciliation |
| Tonic estimation flips between relative major/minor | 2×2 classification shifts by a rotation | three signals, disagreements flagged, never auto-resolved |
| Microtonal degrees forced into semitones | genuine Hijaz reads as Nahawand | adjacent-bin reporting (§8.2) |
| Aggregates hide a bimodal corpus | medians describe nothing real | report IQR *and* min/max, plus per-track scatter in T5 |

## 14. Open decisions

1. **Audio as pitch truth.** The plan assumes yes. The alternative — trust the
   ABC because it is the artifact being taught — is defensible and cheaper, but
   it cannot detect the §2 problem at all. Say so if you prefer it.
2. **What the document is allowed to be called.** If M1 confirms §2, the honest
   title is about this corpus's realised style, not about four maqams. This is a
   decision about the deliverable's framing, and it is yours, not the script's.
