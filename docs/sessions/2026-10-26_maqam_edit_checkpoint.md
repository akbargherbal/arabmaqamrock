# Session — maqam edit checkpoint, round 2 pending (2026-10-26)

Read this first when resuming. It is the state of play, not a narrative.

**Status:** session paused with the user running the seed-313 Claude pass.
Round 2 = three Claude sessions (spec v3 + calibrated prompt) to produce six
reference sheets, then six renders, then one listening test that decides whether
the whole in-house plan is worth building.

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

## 2. What the user is doing right now

Pasting, in this order, into a fresh Claude conversation:

1. `prompts/arabmaqamrock_abc_edit_spec.md`
2. `local_workspace/claude_prompt.md` with `<SEED>` replaced by `313`
3. `local_workspace/moon_edit/baghdad_moon_vanilla_02_313/score.abc`
4. `local_workspace/baghdad_moon_lyrics.txt`

Expected: an `INPUTS` block first, then `CLEAN` + `MID` sheets and a
`CHANGES.txt`, returned as three attached files named
`baghdad_moon_313_{CLEAN,MID}.abc` and `baghdad_moon_313_CHANGES.txt`.

If it starts writing ABC without the `INPUTS` block, the gate did not fire —
that is a finding about the prompt, not about the take.

## 3. First task when the 313 result arrives

Put the files in `local_workspace/moon_edit/edited2/313/` and the chat export in
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

## 4. Then

1. 101 and 577, same prompt, same order (`<SEED>` → `101`, `577`).
2. Build `moon_edit2.json`: six scores (`clean`, `mid` × three seeds), same seeds
   as the source takes (101 / 313 / 577), `cot: melody`, `quantile 0.975`,
   lyrics inline. Model it on `moon_edit.json`. Score files to `scores/moon_<seed>_
   {clean,mid}2.abc` so round 1 is not overwritten.
3. Dry-run `python3 generate.py moon_edit2.json --dry-run`, check headroom.
4. Render, ~45 min.
5. **Listen in trios**: original vanilla → clean → mid, per seed.

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
   depends on it.**
2. Archive the three round-1 session exports to
   `gs://akbar-december-2024-backup/arabmaqamrock/reference/claude_chat/round1/`.
3. Verify the 177 transcripts in `datasets/five_stars/transcripts/` against the
   GCS archive checksums.
4. Snapshot the round-1 rendered WAVs; tag `checkpoint-2026-10-26`.

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
