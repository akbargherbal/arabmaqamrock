# Plan — in-house maqam editor

**Status:** checkpoint at the end of the Claude edit experiments.
Phase 0 to run now; Phase 1 (calibration render) is the next experiment.
**Date:** 2026-10-26
**Owner:** this repository (`arabmaqamrock`)
**Upstream data:** `datasets/five_stars/` (177 tracks), 3 exported Claude sessions
**Depends on:** `prompts/arabmaqamrock_abc_edit_spec.md` (spec v3), `check_abc.py`,
`datasets/five_stars/measure/`, `generate.py`, `transcribe.py`

**Next action:** Phase 0 — freeze the corpus and the three reference runs out of
`/tmp` and into durable storage; tag the repo. Then Phase 1.

---

## 1. The decision

The edit is going in-house. Claude is a **calibration instrument**, not a
production component: we will use it for at most two more rounds, to produce
reference sheets and to expose its decision procedure, and then stop.

The target state is a local program that takes a transcript and returns the same
kind of edited score in seconds, at the same quality, with no human in the loop.

## 2. Why it has to be in-house

Not primarily the money. Three structural reasons:

1. **It is manual.** Each edit was a separate conversation: paste the guide, the
   style, the score, the lyrics, wait, then export the result as files. That is
   roughly 30–60 minutes of orchestration per track (estimate). At 200 tracks
   that is 100–200 hours of someone sitting in a browser.
2. **It is heavy.** The three exported sessions contain 75, 98 and 78 reasoning
   steps and 180–200 KB of transcript each. Most of that is the model writing
   throwaway parsers to check its own bars. A program does that check in
   milliseconds and never gets it wrong.
3. **It is not reproducible.** Two runs of the same brief give different phrase
   choices. For 200 tracks we need a policy we can audit and re-run, and a
   baseline we can diff against when we change the spec.

Claude's real contribution was not the notes it wrote. It was the **procedure**
it invented — segment into phrases, mark cadences, colour a few, keep the rest
plain. That procedure is now visible in the logs and can be executed locally.

## 3. What we already have, and what is fragile

| asset | where | durable? |
|---|---|---|
| 177 ABC transcripts | `/tmp/opencode/fs_abc/*/score.abc` | **no — `/tmp`** |
| the same, archived | `gs://akbar-december-2024-backup/arabmaqamrock/datasets/five_stars/v1/transcripts/` | yes |
| lyrics, style, maqam, manifest | `datasets/five_stars/{lyrics,manifest}.jsonl` | local only (gitignored) |
| ABC parser (with the `]` fix) | `datasets/five_stars/measure/abc.py` | **no — gitignored, local only** |
| measured M1 / structure | `datasets/five_stars/derived/` | local only |
| validator | `check_abc.py` | tracked, but **depends on the untracked parser** |
| 3 Claude reference triples | `scores/moon_*_{clean,v1,v2}.abc` | tracked |
| 3 Claude sessions | `local_workspace/claude_chat/*.json` | local only |
| spec v3 | `prompts/arabmaqamrock_abc_edit_spec.md` | tracked |

Two of these will bite us and are Phase 0 items: the transcripts live in `/tmp`,
and the validator cannot run on a fresh clone because its parser is inside a
gitignored directory.

## 4. What we know at this checkpoint

Carried forward so we do not re-derive it:

**The ABC channel works, but coarsely.** v2 moved the mode (D minor → D Hijaz)
and the register (chorus +2.5 to +4.2 semitones) and was immediately audible.
It did not reproduce the score note-for-note — measured adherence is at chance.
So the renderer transmits **pitch set and register**, not the melody. Any edit
finer than that is not reliably heard.

**The dose curve is bracketed.** 7–9 altered notes placed mid-phrase (v1):
inaudible. ~150 altered notes, every phrase rewritten (v2): unmistakably Arabic,
but the band disappeared behind it. The middle is **placement**, not quantity.

**The corpus is diatonic.** 0.83 accidentals per 100 notes overall; median track
0.38; 90th percentile 2.4; 74 of 177 tracks have none; 0 of 177 are Hijaz-shaped
even when the production prompt says "Maqam Hijaz". arabmaqamrock is a minor
rock band with maqam accents, not a maqam ensemble.

**The v2 failure was the brief, not the model.** Spec v2 said "change the pitches
freely… not obliged to preserve a single pitch", asked for a sayr in every
section, made "is the maqam identifiable" the first quality test, and told the
model to raise the chorus. Claude did all four. Spec v3 replaces the licence with
a budget.

**Only one of the four maqams is editable in this dialect.** The corpus is Hijaz
49, Ajam 43, Kurd 43, Nahawand 42. Of those, only Hijaz has a chromatic colour
that survives as `^`/`_` semitones and is not already the diatonic set. For
Nahawand, Ajam and Kurd the correct edit is close to *nothing* — a cadence note
or two. This matters at scale: most of the 200 tracks should get a very small
edit, and an editor that always wants to add colour will do damage.

## 5. The architecture

Not a prompt. A program. The LLM may decide *whether* to colour a phrase; it must
never emit the bytes.

```
transcript (ABC)
  -> parse + clean          deterministic  (pass 1 of the spec)
  -> phrase model           deterministic  (phrase boundaries, cadences, registers)
  -> candidate cadences     deterministic  (rank phrases by suitability)
  -> figure generation      CATALOGUE      (shapes distilled from reference edits)
  -> scoring                deterministic  (corpus statistics + maqam rules + budget)
  -> selection              deterministic  (greedy under the budget)
  -> validation             deterministic  (check_abc: bars, voices, counts)
  -> edited ABC
```

Three candidate implementations were considered:

| option | what it is | verdict |
|---|---|---|
| (a) skill = prompt | a skill whose instructions make an LLM write the score | **no** — an LLM without tools miscounts bars; this is what needed 75 tool calls to get right |
| (b) sub-agent = LLM with tools | same loop Claude ran, locally | viable fallback; still pays per track, still non-deterministic |
| (c) **CLI = deterministic search** | the pipeline above | **chosen** — seconds per track, auditable, diffable |

The "skill" we build is therefore (c) plus a knowledge document: a CLI, a
catalogue of figures, and `docs/guides/maqam_edit_playbook.md`. If we later want
judgement in the loop (which cadence is the emotional peak), that is an LLM call
that returns **a phrase index**, not a score.

### Corpus as objective function, not as example bank

The 177 tracks are not material to imitate — copying them is the thing we spent
effort avoiding. They are the **scorer**: accidental rate, step-motion share,
leap distribution, contour, register, silence, line length. Every candidate edit
is scored against those distributions, and an edit that drifts outside them is
rejected no matter how good the maqam looks.

## 6. The thing to distil from the exported sessions

This is the actual deliverable of the next Claude round. From the logs we can
already see the procedure; what we still lack is Claude's *preference function*.

| what | where it comes from | what it becomes |
|---|---|---|
| phrase segmentation | visible in the logs ("counted 25 phrases") | code |
| cadence marking | logs + every `maqam_figures` line names a bar | code |
| which phrases get coloured | **only** from the reference sheets | selection policy |
| the shapes written at a cadence | **only** from the reference sheets | figure catalogue (10–20 items) |
| how it avoids excess | the v2 report counts accidentals per section | budget in the scorer |
| the failure modes it reaches for | logs ("re-map onto scale ladder", "raise the chorus") | forbidden list — already in spec v3 |
| its self-check list | the `CHANGES` block | `check_abc.py` |

The catalogue is the key in-house asset that does not exist yet. It is small: for
each coloured phrase we record *(bar, phrase-final degree, degrees used, the
augmented-second pair, its resolution, note count, rhythmic placement)*. Fifteen
to twenty shapes, extracted automatically from the reference sheets, filtered by
the corpus's step-motion and leap statistics so they stay singable.

## 7. Phases

### Phase 0 — freeze the checkpoint (now, ~1 hour)

- Copy `/tmp/opencode/fs_abc/` into durable storage (`datasets/five_stars/transcripts/`),
  verify 177 files and checksums against the GCS archive.
- Make the validator runnable on a fresh clone: track `measure/` (or vendor the
  parser next to `check_abc.py`). Today `git clone && ./check_abc.py` fails.
- Copy the three Claude session exports out of `local_workspace` into a durable
  archive (`gs://…/arabmaqamrock/reference/claude_chat/round1/`), since
  `local_workspace/` is gitignored.
- Snapshot the 9 rendered WAVs and their transcripts.
- Tag: `git tag checkpoint-2026-10-26`.

**Gate G0:** a fresh clone can validate a score, and the corpus survives a reboot.

### Phase 1 — calibration run (Claude, 3 tracks)

Claude redoes the same three takes with spec v3. Not a re-render of the old
sheets — the new brief, from the same transcripts.

Prompt order, per track: spec v3 → style block → `score.abc` → lyrics. Ask for
`CLEAN` and `MID` only.

Frozen inputs (must not change between runs):

```
local_workspace/moon_edit/baghdad_moon_vanilla_01_101/score.abc   seed 101, 376 notes, 2/4, 73 BPM
local_workspace/moon_edit/baghdad_moon_vanilla_02_313/score.abc   seed 313, 435 notes, 4/4, 112 BPM
local_workspace/moon_edit/baghdad_moon_vanilla_03_577/score.abc   seed 577, 369 notes, 4/4, 69 BPM
```

On return: export all three sessions to `local_workspace/claude_chat/round2/`,
save the six sheets as `scores/moon_<seed>_{clean,mid}.abc`, and record for each:

```
phrases_total, phrases_coloured, coloured_bars,
notes_pitched, notes_pitched_pct, accidentals,
register_shift per section, notes_removed, notes_added (must be 0)
```

Then render `clean` and `mid` at the seed of the source take (101 / 313 / 577),
six tracks, ~45 min, and listen to each trio: original vanilla → clean → mid.

**Gate G1:** does `mid` sound like the band *and* carry the maqam? If the answer
is "still bland" or "still a different band", the edit idea is dead at the spec
level and no in-house work will save it. Stop and reconsider the whole approach
(most likely: the renderer, not the score, is the ceiling).

### Phase 2 — the playbook (~half a day)

Write `docs/guides/maqam_edit_playbook.md`: the operator's model of the task in
the vocabulary Claude actually used — phrase, cadence, jins, qarar, sayr,
tessitura. Plus a decision table: given a phrase's section, final note, contour
and register, colour it or not.

Success test: a person who has not read the chats can reproduce Claude's phrase
choices from the document alone, for all three tracks, within one phrase.

Deliverable also includes the **figure catalogue** (§6), as data:
`datasets/five_stars/derived/cadence_figures.json`.

### Phase 3 — the editor (~2–3 days)

`maqam_edit.py`, following §5, with `--dose` levels. It must:

- emit `CLEAN` (pass 1 only) and `MID` (budget 5 phrases / 10–18 notes);
- refuse to emit a score that fails `check_abc.py`;
- print the same `CHANGES` block Claude printed, computed, not estimated;
- run on all 177 corpus tracks without crashing (they have 2 voices, 5 median
  meter changes, 16 median incomplete bars — the messy case is the normal case).

**Gate G2:** produce `MID` for the three calibration transcripts. Compare with
Claude's sheets on: phrase-choice overlap, altered-note count, accidental rate,
register shift, and corpus distance. If fewer than 3 of 5 coloured phrases
coincide, read the playbook against the sheets and fix the policy, not the code.

### Phase 4 — parity, blind (~1 day + 6 renders)

Run in-house `MID` on the three tracks, render at the same seeds, and compare
against Claude's `MID` and the vanilla take without labels. Two listeners who
have not seen the sheets, forced ranking, and a second pass a week later.

**Gate G3:** in-house is not worse than Claude on the majority of pairs. If it is
worse, we keep Claude for a small number of calibration tracks and ship (b) —
a local sub-agent with tools — instead of (c).

### Phase 5 — scale (deferred)

Only after G3. Then: batch over the 177 (or the 200 new tracks), render, score
automatically, shortlist, and listen to the shortlist only. See §8.

## 8. Evaluating without listening to 200 tracks

Auditioning 200 renders is the same manual bottleneck we are removing. The
shortlist has to be automatic.

| layer | metric | exists? |
|---|---|---|
| structural | `check_abc.py` (bars, voices, meter, counts) | yes |
| symbolic style | accidental rate, step motion, leaps, contour, register, silence | yes — `measure/` |
| budget compliance | phrases coloured, notes pitched, register shift | yes, from the editor |
| audio style | embedding distance to the 177-track centroid | **to build** |
| "the band went quiet" | vocal-to-backing balance from the mix | **to build** — this is the v2 failure as a number |
| human | A/B on the shortlist | yes, last |

The audio metric is the one that makes 200 tracks tractable. Build it once, on
the corpus we already have, and use it as the reward for the shortlist.

## 9. Risks

| risk | why it matters | mitigation |
|---|---|---|
| the renderer is the ceiling, not the score | adherence is chance-level note-wise; if pitch set and register are all that transmit, fine editing is invisible | keep the dose coarse (5 phrases, not 5 notes); measure the audio before optimising the sheet |
| overfitting to 3 reference sheets | a catalogue built from 3 songs encodes 3 songs | extract shapes, not sequences; require every figure to pass the corpus's step/leap statistics; grow to 6 sheets max |
| most corpus maqams are diatonic | an editor that always adds Hijaz will damage Nahawand/Ajam/Kurd tracks | dose is a function of the maqam: near-zero for the diatonic three |
| the baseline is a machine transcript | we are beautifying a transcription of a render, not the band's composition | accept it; the task is defined on transcripts, and the renderer is the consumer |
| building the program before the sound is proven | G1 could fail and make Phase 3 pointless | Phase 1 and its render come first; it is cheap |

## 10. What we are not doing

- Not fine-tuning a model on the edits. The catalogue plus a scorer is smaller,
  inspectable, and does not drift.
- Not scraping more than two rounds of chats. Round 1 (old brief) and round 2
  (spec v3) bracket the range; a third round only if G1 is ambiguous.
- Not encoding production in ABC. Guitars, drums and mix are out of reach and
  were the other half of "the band went quiet".
- Not copying corpus phrases. Distribution matching only.

## 11. Deliverables

| file | phase | tracked |
|---|---|---|
| `datasets/five_stars/transcripts/` (177) | 0 | no (gitignored, archived to GCS) |
| `measure/` made importable from a fresh clone | 0 | **yes** |
| `scores/moon_<seed>_{clean,mid}.abc` (6) | 1 | yes |
| `local_workspace/claude_chat/round2/` | 1 | no (archived to GCS) |
| `docs/guides/maqam_edit_playbook.md` | 2 | yes |
| `datasets/five_stars/derived/cadence_figures.json` | 2 | no (derived) |
| `maqam_edit.py` | 3 | yes |
| embedding scorer | 5 | yes |
| this plan, updated per gate | — | yes |

## 12. Next action

Phase 0, in this order: transcripts out of `/tmp`; validator runnable on a fresh
clone; sessions archived; tag `checkpoint-2026-10-26`.

Then Phase 1: three Claude sessions with spec v3, export, and the six-track
render. Nothing in Phase 2 or 3 starts until G1 is passed.
