# Session — maqam edit, round 2 complete, render/listening pending (2026-10-26)

Read this first when resuming. It is the state of play, not a narrative.

**Status:** all three round-2 sheets are checked (§3a–§3c) and the six-track
render spec is built, dry-run, and pushed as `920b0d9`. The user is rendering in
Colab. **Next session: listen in trios, decide G1, then distil the three Claude
chat logs into `skills/maqam-edit/SKILL.md`.** 313 and 101 are clean; 577 is
verse-only (no chorus cadence) and has one G-ending colour. Round 2 = three
Claude sessions (spec v3 + calibrated prompt) -> six reference sheets -> six
renders -> one listening test that decides whether the in-house plan is worth
building.

## 1. Where we are in one paragraph

The edit experiment produced a bracketed dose curve: a light maqam edit (v1,
7–9 altered notes, mid-phrase) was inaudible; a full maqam reading (v2, ~150
altered notes, every phrase rebuilt) was unmistakably Arabic but erased
arabmaqamrock — "nice to have what v2 is giving us, but we lose our touch". The
cause was the brief, not the model: spec v2 granted unlimited pitch licence,
demanded a sayr in every section, made "is the maqam identifiable" the first
quality test, and told the model to raise the chorus. Spec v3 replaces that with
a measured budget and cadence placement, and a calibrated prompt now gates the
inputs. Round 2 tests whether the middle ground exists.

## 2. What is running right now

The user is running the six-track render in Colab:

```bash
git pull          # 920b0d9
python3 generate.py moon_edit2.json
```

- `moon_edit2.json`: six tracks, `cot: melody`, `quantile: 0.975`, lyrics inline.
- Dry-run: 6 tracks, ~39 min on T4, caps 7000, headroom 892–1493 frames.
- Output: `out/<timestamp>_moon_edit2/`.
- Scores: `scores/moon_<seed>_{clean,mid}2.abc`, tracked.
- Listening trios, per seed: round-1 vanilla WAV -> clean2 -> mid2. The vanilla
  WAVs are the source takes (`baghdad_moon_vanilla_0{1,2,3}_{101,313,577}.wav`).

The three Claude sessions are done. Their chat exports are still pending; the
sheets are in `local_workspace/moon_edit/edited2/<seed>/` and the zips in
`local_workspace/moon_edit/`.

## 3. How the round-2 sheets were checked

Done for all three seeds; kept as the verification recipe. The results are in
§3a–§3c, the comparison in §3d.

Put the files in `local_workspace/moon_edit/edited2/<seed>/` and the chat export in
`local_workspace/claude_chat/round2/`, then run:

```bash
./check_abc.py local_workspace/moon_edit/edited2/313/baghdad_moon_313_MID.abc \
  --lyrics local_workspace/baghdad_moon_lyrics.txt
```

Then measure the six numbers below. **Do not trust the CHANGES file for these;
recompute.**

| number | target | how |
|---|---|---|
| phrases coloured | 4–6 of ~26 | count distinct phrases containing a pitch change |
| notes pitched | 10–18 (≤8% of 444) | note-by-note diff vs its CLEAN |
| accidentals | 10–18 | count `^`/`_` tokens in the music body |
| register shift per section | within ±2 semitones | mean pitch per section, vs CLEAN |
| unchosen phrases | zero pitch changes | every change inside a declared phrase |
| hard checks | all pass | `check_abc.py` |

**Reference points from round 1** (same three takes, old brief), for calibration:

| seed | v1 accidentals | v2 accidentals | v2 notes pitched | v2 register shift |
|---|---:|---:|---:|---:|
| 101 | 9 | 151 | 227 / 376 | +2.5 semitones |
| 313 | 7 | 134 | 178 / 435 | +1.7 |
| 577 | 5 | 131 | 215 / 369 | +4.2 |

Round 1 numbers in the commit message of `4ddb025` are wrong (they say 0/5–7/
70–133). The table above is correct.

### How to read the result

- **~10–18 notes on ~5 cadences, register flat** → the spec worked; run 101 and 577.
- **Under 8 notes, or all mid-phrase** → the budget is being read as "a couple of
  touches". Raise the floor, not the ceiling.
- **Over 40 notes, or any section transposed** → the budget is being ignored or
  the sheet is a v2 again. Fix the prompt's `MID` paragraph before the other two
  sessions; do not spend them.
- **Sheets differ from each other by more than 20% on notes pitched** → placement
  is unstable; that is expected, and it means round 2 is about the *policy*, not
  the output.

### 3a. Seed 313 — verified result (2026-10-26)

Files in `local_workspace/moon_edit/edited2/313/`. The chat export is not in
`local_workspace/claude_chat/round2/`, so the `INPUTS` gate is **not yet
verified**; the CHANGES form ledger suggests it fired, but that is inference.

Recomputed from the ABC (parser, not CHANGES):

| number | measured | target |
|---|---:|---|
| phrases coloured | 5 / 28 | 4–6 of ~26 |
| notes pitched | 13 / 443 = 2.9% | 10–18 |
| accidentals | 10 (2 per coloured phrase) | 10–18 |
| register shift | verse +0.01, chorus −0.07; max 0.07 | ±2 |
| unchosen phrases | 0 pitch changes | 0 |
| rhythm | 0 onset/duration/bar changes vs CLEAN | 0 |
| hard checks | 13/14 pass; 1 source-related | all pass |

`bars complete` passes. The 10 "incomplete" bars were tie continuations the
parser forgot to add to the current bar (one-line fix in the local parser; note
data unchanged). The one remaining failure is `leaps <= 7`: 4 leaps of 8
semitones at bars 25/33/51/96, all real melodic leaps in the source. Smoothing
them is forbidden by spec §6, so the CLEAN correctly keeps them. They are
identical in the CLEAN, the MID, the round-1 sheets and the source.

CLEAN and MID have the same 443 notes, bars, onsets, durations and sections; the
edit changes pitch only (new pitch classes: Eb, F#; none lost). **The edit
introduces no new hard failure: all 14 `check_abc.py` outcomes are identical
between CLEAN and MID, and all 16 spec §8 checks pass.** The leap failure is an
extra heuristic in the checker, not a §8 check, and it is a property of the
source preserved by the CLEAN.

All five coloured phrases cadence on D, with a consistent tail. (Phrase numbers
are the checker's: it drops fragments shorter than 3 notes, so they run one
behind CHANGES; bars are the parser's, one behind CHANGES' 1-based count.)

| phrase | section | phrase bars | tail (MID) | CLEAN cadence |
|---|---|---|---|---:|
| 2 | verse 1 | 14–16 | E F# Eb D | D |
| 8 | verse 1 | 33–36 | F F# Eb D | E → D |
| 12 | chorus 1 | 50–52 | A F# Eb D | F → D |
| 17 | verse 2 | 76–79 | E F# Eb D | D |
| 20 | verse 2 | 86–88 | E F# Eb D | D |

No two coloured phrases are adjacent; chorus 2, the outro and the other 23
phrases are untouched. Each edit is one augmented second (F#–Eb) resolving to D.

Bookkeeping corrections to CHANGES: `notes_out` is 453 written / 443 parsed
(10 tied continuations merged by the parser); `phrases_total` is 30 by its
4-beat rest rule vs 28 by the checker's 1-beat rule (the two missing are <3
notes). Neither changes the five coloured phrases. CHANGES quotes register
against the input; the table measures against CLEAN, which is the specified
comparison.

Key caveat: the prompt's form rule reads `K:D#m` on plain letters as Dm ("no
transposition"), and CHANGES follows it. Written pitch is unchanged, but a
literal D#m reading sounds a semitone higher; `key.lab` says D#:minor at 0.01
confidence. Round 1 made the same call, so clean-vs-mid is unaffected, but keep
it in mind if vanilla-vs-clean sounds a semitone apart.

**Verdict:** the "spec worked" row, on the conservative side. The dose sits just
above v1 (7–9 accidentals) and far below v2 (134); placement is the variable
that changed, which is the point of the test.

### 3b. Seed 101 — verified result (2026-10-26)

Files in `local_workspace/moon_edit/edited2/101/`. The chat export is also not in
`claude_chat/round2/`, so its `INPUTS` gate is unverified. Recomputed from the
ABC:

| number | measured | target |
|---|---:|---|
| phrases coloured | 5 / 25 | 4–6 |
| notes pitched | 10 / 390 = 2.6% | 10–18 |
| accidentals | 10 (5 `^`, 5 `_`) | 10–18 |
| register shift | 0.00 in every section | ±2 |
| unchosen phrases | 0 pitch changes | 0 |
| rhythm | 0 changes vs CLEAN | 0 |
| hard checks | 13/14 pass; 1 writer check | all pass |

All 16 spec §8 checks pass. The CLEAN is a faithful copy: 0 pitch changes vs
input, 0 notes removed (7 tied continuations merged by the parser, hence 390 vs
397 written). The edit is five cadences, two notes each, all ending on D:

| phrase | section | phrase bars | tail (MID) |
|---|---|---|---|
| 2 | verse 1 | 15–18 | F E **F# Eb** D |
| 11 | chorus 1 | 57–60 | E **F# Eb** D D |
| 17 | verse 2 | 93–95 | F G **F# Eb** D |
| 21 | chorus 2 | 106–109 | E **F# Eb** D D |
| 22 | chorus 3 | 121–122 | F G **F# Eb** D |

Phrase numbers are the checker's; CHANGES runs one ahead on 21/23 because it
keeps a one-note fragment. Every figure enters F# by step and leaves Eb by step
to D; the closest pair of coloured cadences is 23.5 beats apart, across the
11-bar interlude. This is the floor of the budget: 10 notes, 2 per cadence,
10/390 = 2.6%, below the spec's 3–5% share row. The count is at the 10-note
floor; CHANGES does not flag the share, a minor self-report omission. The
phrases are 6.0 beats (the 2/4 corpus median), against 11.5 for 313.

101-specific form fix: the source has one `M:5/8` bar. The CLEAN splits it into
two 2/4 bars and fills the second with `z12`; every note keeps its bar-relative
position, and the extra 1.5 beats fall inside an existing 2-bar silence. Absolute
onsets after that bar are +12 units, identical in CLEAN and MID. This is the
prompt's prescribed repair, not a rhythm edit.

`check_abc.py` still reports one failure, `bar budget`: 268 beats vs the
95th-percentile cap of 328. The source audio is 217.3 s = 264 beats at 73 BPM,
so the transcription is faithful and the song is simply 18% shorter than the
cap. The bar budget is a writer check from the from-scratch spec; edit spec §3
says keep the section layout, so length is not ours to change. Not an edit
defect.

**Verdict:** compliant, but at the conservative end — 10 notes, 10 accidentals,
exactly the floor. If 101 is inaudible while 313 is not, the variable is dose,
not placement. That is the useful comparison in the listening test.

### 3c. Seed 577 — verified result (2026-10-26)

Files in `local_workspace/moon_edit/edited2/577/`. Chat export still pending;
`INPUTS` gate unverified. Recomputed from the ABC:

| number | measured | target |
|---|---:|---|
| phrases coloured | 4 / 24 | 4–6 |
| notes pitched | 10 / 379 = 2.6% (11 vs input, incl. the CLEAN final note) | 10–18 |
| accidentals | 11 (10 new + the transcript's own `^c`); plus one `=e` | 10–18 |
| register shift | 0.00 every section vs CLEAN | ±2 |
| unchosen phrases | 0 pitch changes | 0 |
| rhythm | 0 vs CLEAN; CLEAN keeps 380/390 (7 echo notes removed) | 0 |
| hard checks | 11/14; 3 source/writer | all §8 pass |

All 10 hard §8 checks pass. The CLEAN is more processed than the other two:
7 echo notes collapsed (1.8%, inside the 2% cap), 3 surviving notes lengthened
to cover them, and the final note moved Bb4→D5 (the nearest tonic; D4 is 8
semitones away). 390 written / 386 parsed in, 383 / 379 out (4 tied pairs). The
transcript's own `^c` is kept and counts against the budget.

Only four phrases can take the figure:

| phrase | section | phrase bars | tail (MID) | ends |
|---|---|---|---|---|
| 5 | verse 1 | 13–15 | D E **Eb F#** F# G | G |
| 14 | verse 2 | 36–39 | G G **F# F# Eb** D | D |
| 17 | verse 2 | 43–45 | E E F **F# Eb** D | D |
| 24 | verse 3 | 65–66 | A A **F# Eb** D D | D |

Three are the textbook descending F#–Eb–D cadence. The first is an ascending
Eb–F#–G colour and **ends on G, not D or A** — a reported §5.3 deviation. The
larger deviation is placement: **no pre-chorus and no chorus is coloured**.
Every pre-chorus and chorus tail ends C–Bb–A, with no E/F pair near the cadence;
reaching F#–Eb would need a leap or a new note, both forbidden. The model left
them plain and says §5.1 item 3 is not met. That is a material limitation, not a
budget overrun.

`check_abc.py` reports three failures, all source/writer:

- `bar budget` 276 beats vs 310. The audio is 237.8 s = 273.5 beats at 69 BPM;
  the transcription is faithful and the song is 12% under the cap.
- `line length` 6.2 beats. 577 is a 4/4 outlier; the source is also 6.2, and
  rhythm preservation forbids changing phrase length.
- `leaps` 4 source leaps (two A4→F5 pickups, the A5→A4 drop, one more A4→F5),
  identical in the source and the CLEAN.

Plus a soft `chorus at least as high as verse` warning: verse max 82, chorus max
81. That is the source's register, not the edit's; the MID's section means are
0.00.

**Verdict:** compliant but the weakest of the three. It tests **verse-only**
colour, with three proper cadences and one ascending colour ending on G. Accept
it for the listening test, but do not treat 577 as comparable to 313/101 on
placement. If 577 is inaudible while 313 is not, the likely cause is the missing
chorus, not the dose. The policy question for the skill: when no chorus cadence
can take the figure without a leap or a new note, is verse-only colour the right
fallback, or should the brief allow a chorus colour with a leap? 577 is the
evidence for that decision.

### 3d. Round-2 summary

| seed | meter / BPM | phrases | notes pitched | accidentals | register | placement | `check_abc` residual |
|---|---|---:|---:|---:|---|---|---|
| 313 | 4/4, 112 | 5/28 | 13 (2.9%) | 10 | +0.01 / −0.07 | 2 verse, 1 chorus, 2 verse | 4 source leaps |
| 101 | 2/4, 73 | 5/25 | 10 (2.6%) | 10 | 0.00 | 2 verse, 3 chorus | writer bar budget |
| 577 | 4/4, 69 | 4/24 | 10 (2.6%) | 11 | 0.00 | 4 verse, no chorus | bar budget, line length, 4 source leaps |

All three: CLEAN and MID have identical `check_abc.py` outcomes, and the edit
introduces no new hard failure. 313 and 101 are the clean comparison; 577 is the
verse-only case.

## 4. Then

1. ~~577~~ done (§3c).
2. ~~Build `moon_edit2.json`~~ done: six scores (`clean`, `mid` × three seeds),
   same seeds as the source takes, `cot: melody`, `quantile 0.975`, lyrics
   inline. Score files are `scores/moon_<seed>_{clean,mid}2.abc`. Pushed as
   `920b0d9`.
3. ~~Dry-run~~ passed: 6 tracks, ~39 min on T4, cap 7000, headroom 892–1493.
4. **Render** — running in Colab (`python3 generate.py moon_edit2.json`).
5. **Listen in trios** — next session: original vanilla → clean → mid, per seed.

### Gate G1 — the decision that matters

| outcome | meaning | next |
|---|---|---|
| mid sounds like the band and carries the maqam | the middle ground exists | build the agent plan |
| mid is inaudible | placement does not transmit; only mode/register do | either accept v2-style dosing and fix the arrangement, or stop editing |
| mid is a different band | the budget is not binding | narrow the brief further, or conclude the renderer cannot hold both |
| clean differs from the vanilla WAV | ABC conditioning is doing something we have not modelled | re-plan before any in-house work |

## 5. Canonical numbers — do not re-derive

Corpus (177 tracks, `datasets/five_stars/`):

- 0.83 explicit accidentals per 100 notes; median track **0.38**; p90 **2.4**;
  p75 1.17; **74 of 177** tracks have none; max 11.04.
- **0 of 177** are Hijaz-shaped, including the 49 whose prompt says Hijaz.
- 7 pitch classes typical; step motion 85%; leaps ≥5 semitones 4.2%; silence 30%;
  off-beat starts 64%; descending phrases 62%; line length 10 beats (4/4) /
  6 beats (2/4).
- Maqam labels are prompt provenance, not ground truth. Only **Hijaz** has an
  editable chromatic colour in this ABC dialect; Nahawand/Ajam/Kurd edits should
  be near-zero.

Render behaviour (measured):

- ABC adherence at note level is **chance**: score-to-audio overlap 0.19–0.21,
  against 0.20 for unrelated pairs.
- What does transmit: **pitch set** and **register**. v2 was heard as Hijaz
  because of those two, not because of the melodic line.
- Corrections to earlier statements in this repo's history: the "0.2 accidentals
  per 100 notes" figure was wrong (real: 0.83 overall / 0.38 median), and the
  "80% of notes kept" rule was orphaned when pitch became fully editable.

## 6. Files

Tracked:

| file | state |
|---|---|
| `prompts/arabmaqamrock_abc_edit_spec.md` | **spec v3**, the active brief |
| `prompts/arabmaqamrock_abc_spec.md` | from-scratch writer spec, kept for v4 training |
| `skills/maqam-edit/SKILL.md` | in-house agent skill (method + tool contracts) |
| `docs/plans/inhouse-maqam-editor.md` | agent plan, phases 0–5, gates G0–G3 |
| `docs/plans/model-and-tool-selection.md` | tool surface + model benchmark protocol |
| `scores/moon_<seed>_{clean,v1,v2}.abc` | round 1 sheets, 9 files |
| `moon_edit.json` | round 1 render spec (9 tracks) |
| `baghdad_moon_spec.json` | the original A/B spec (6 tracks) |

Local only (gitignored):

| path | contents |
|---|---|
| `local_workspace/claude_prompt.md` | calibrated round-2 prompt, `<SEED>` placeholder |
| `local_workspace/claude_chat/*.json` | round 1 exports (3 sessions) |
| `local_workspace/moon_edit/` | round 1 transcripts, zips, extracted sheets |
| `local_workspace/baghdad_moon_lyrics.txt` | lyrics, 6 sections, 35 lines |
| `datasets/five_stars/transcripts/` | 177 ABC transcripts (copied out of `/tmp`) |
| `datasets/five_stars/measure/` | parser (`]` fix), m1, structure |

`skills/maqam-edit` is symlinked from `~/.config/opencode/skills/maqam-edit`, so
the skill loads in this harness. Single source of truth is the repo file.

## 7. Open items — Phase 0, still outstanding

1. `check_abc.py` cannot run on a fresh clone: its parser lives in the gitignored
   `datasets/five_stars/measure/`. Track or vendor it. **The in-house agent
   depends on it.** Local fix applied 2026-10-26: a tied continuation now adds
   its duration to the current bar (every tied bar looked incomplete; 10 in the
   313 score). Note data is unchanged; the fix is still untracked.
2. Archive the three round-1 session exports to
   `gs://akbar-december-2024-backup/arabmaqamrock/reference/claude_chat/round1/`.
3. Verify the 177 transcripts in `datasets/five_stars/transcripts/` against the
   GCS archive checksums.
4. Snapshot the round-1 rendered WAVs; tag `checkpoint-2026-10-26`.
5. Checker corrections made during the 101 check, matched to the corpus method
   rather than loosened to pass:
   - line length is meter-aware: 2/4 target 6.0 beats (band 4.2–8.4), 4/4 stays
     7–14. The old band failed 71 of 78 2/4 corpus tracks; the 2/4 median is 6.0.
   - leaps are measured inside phrases: a leap after a rest of ≥1 beat starts a
     new phrase, matching `measure/structure.py` ("rests do not create phantom
     leaps"). 101's 12-semitone jump is across a 1.5-beat rest.
   - bar budget compares beats, not 2/4 bar counts against a 4/4-derived budget.
   After these, 313 fails only `leaps` (4 real source leaps); 101 fails only
   `bar budget` (writer-only; the source is 18% under the 95th-percentile cap);
   577 fails `bar budget`, `line length` and `leaps` — all source properties
   (12% under the cap, 6.2-beat 4/4 phrases, 4 source leaps).

## 8. Rules of engagement

- **Do not re-litigate the diagnosis.** v2 failed because of the brief. That is
  measured, not opinion.
- **Do not re-derive the corpus numbers** in §5; they are recomputed facts.
- **Do not put a hard wall on the budget.** `apply` refuses only structural
  breakage; budget and register are measured and reported, with deviations
  visible in `decisions.json`. Guidelines, not restrictions.
- **Do not let the agent write ABC.** Pitch lists in, serialised ABC out. The
  rhythm must be structurally impossible to disturb.
- **Do not add web access** to the batch agent: general maqam theory argues for
  the exact edit that failed, while the corpus says the band is diatonic.
- **Claude is calibration, not production.** Two rounds maximum. If the agent is
  not ready after G2, narrow its job, do not go back to manual sessions.
- **Verify, do not trust reports.** Every sheet gets `check_abc.py` plus a
  recomputed diff against its own CLEAN.

## 9. Next session — listening review, then skill distillation

### 9.1 First: the listening review

The user brings per-seed impressions of the trios. Capture, per seed:

- **MID vs CLEAN:** same band, same vocal character? Is the maqam audible, and
  where? Does the cadence land?
- **CLEAN vs vanilla:** any audible ABC-conditioning effect (timing, register,
  final note, echo removal)?
- **Placement:** 313 and 101 have a chorus cadence; 577 does not, and its first
  colour is ascending and ends on G.

Then apply G1 (table in §4). The decision is not "did Claude follow the spec" —
it did. It is whether the middle ground exists: mid sounds like the band and
carries the maqam / mid is inaudible / mid is a different band / clean differs
from vanilla.

Keep the dose differences in view: 313 = 13 notes (5 cadences, 1 chorus); 101 =
10 notes (5 cadences, 3 chorus, at the floor); 577 = 10 notes (4 verse cadences,
no chorus). If 101 is inaudible and 313 is not, the variable is dose. If 577 is
the odd one out, the missing chorus is the likely cause.

### 9.2 Second: distil the three Claude chats into `skills/maqam-edit/SKILL.md`

The chat exports are still pending. Export all three to
`local_workspace/claude_chat/round2/` before closing the tabs. They are the
source for the *thinking process*, not just the outputs.

For each session, extract:

- the `INPUTS` block and what it caught (gate evidence);
- the phrase table and the chosen phrases with reasons, especially the rejected
  cadences;
- the form decisions (key, meter, units, final note, echo policy);
- the conflicts and how they were resolved: 313's 36 echo runs vs the 2% cap;
  101's 5/8 bar; 577's no-chorus and G-ending colour; 577's final-note fix;
- any gap between what CHANGES claims and what the ABC shows.

Then update the skill, preserving its current shape (gate -> phrase table ->
CLEAN -> choose -> pitch lists -> verify/report):

- Add the traps proven this round:
  * a tie continuation still occupies time in the bar; count it in bar sums (the
    parser bug that made 10 bars look incomplete);
  * echo collapse is capped by the 2% note-count rule; the cap outranks "merge
    every run" (313 kept 35/36; 577 removed 7 notes = 1.8%);
  * line length is meter-aware (2/4 6.0 beats, 4/4 10); a 4/4 outlier like 577
    (6.2 beats) is a source property, not an edit defect;
  * a leap after a rest of >=1 beat starts a new phrase, not a melodic leap;
  * the bar budget is a writer check; an edit inherits the transcript's length;
  * when no chorus/pre-chorus cadence can take the figure without a leap or a new
    note, verse-only is a legitimate fallback — but say so, and do not claim
    §5.1 placement was met;
  * the 4-phrase minimum can force an ascending Eb-F#-G colour ending on G;
    report it as a cadence deviation, not a qarar;
  * the D#m->Dm rule lives in the calibration prompt, not the spec; decide
    whether it belongs in the skill;
  * fix the `edit.json` example: `E4, F#4, Eb4, D4` (step in, augmented second
    down, step out to D), not `E4, Eb4, F#4, D4`.
- Do not overfit: §6 (the corpus is diatonic; no web; no general-maqam-theory
  dosing) stays.

The goal is Claude's *process*, not a transcription of its three answers. If a
step is proven, keep it; if a step was improvised and worked, name the condition.
Do this **regardless of the G1 outcome**: even if the render fails, the
transcripts show which moves were proven and which were improvised, and that is
what stops the next attempt from reinventing them.

### 9.3 State and open items

- **Render:** `moon_edit2.json`, six tracks, `out/<timestamp>_moon_edit2/`.
  Record the run dir and confirm all six WAVs landed.
- **Chat exports:** 313/101/577 pending; the `INPUTS` gate is unverified for all
  three.
- **Parser:** the tie fix is local-only (`datasets/` is gitignored);
  `check_abc.py` still cannot run on a fresh clone. The render does not need it.
  Track/vendor before the agent.
- **Unchanged:** round-1 exports to GCS; 177 transcript checksums; round-1 WAV
  snapshot/tag.
- **Session delta:** `920b0d9` is the render spec (sheets, `moon_edit2.json`,
  checker fixes, §3a–§3d); this checkpoint update is the doc commit that follows.
  Local: `edited2/`, `claude_prompt_{101,577}.md`, and the empty
  `claude_chat/round2/`.
