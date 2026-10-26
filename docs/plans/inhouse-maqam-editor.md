# Plan — in-house maqam editor agent

**Status:** checkpoint at the end of the Claude edit experiments.
Phase 0 partially done (transcripts copied out of `/tmp`); Phase 1 is the next
experiment.
**Date:** 2026-10-26
**Owner:** this repository (`arabmaqamrock`)
**Upstream data:** `datasets/five_stars/` (177 tracks), 3 exported Claude sessions
**Depends on:** `prompts/arabmaqamrock_abc_edit_spec.md` (spec v3), `check_abc.py`,
`datasets/five_stars/measure/`, `generate.py`, `transcribe.py`

**Next action:** Phase 1 — three Claude sessions with spec v3 and the calibrated
prompt (`local_workspace/claude_prompt.md`), then six renders.

---

## 1. The decision

The editor is an **in-house AI agent** — a DeepSeek model running in this repo
with shell and file tools, guided by the spec and by a playbook distilled from
the Claude sessions. It **replaces Claude as the thing that does the edit**.

It is not a deterministic program that composes the edit, and it is not a prompt
the agent answers blind. It is an agent, with a budget of tool calls, doing the
same work Claude did — except that the mechanical parts it used to improvise are
now handed to it as tools.

Claude's role changes: **calibration instrument only.** Two more rounds at most,
to produce reference sheets and to expose its decision procedure. After that it
is not in the loop.

## 2. Why in-house, and why an agent

The problem with the Claude rounds was never the intelligence. It was the
packaging:

1. **One manual conversation per track.** Paste the guide, the style, the score,
   the lyrics; wait; ask again for files; download; rename. Roughly 30–60 minutes
   of human orchestration per track (estimate). At 200 tracks that is 100–200
   hours of someone sitting in a browser.
2. **The agent spends most of its steps on work that should be a tool call.** The
   three exported sessions contain 75, 98 and 78 reasoning steps and 180–200 KB
   each, and most of that is the model writing throwaway parsers to check its own
   bar sums and accidentals. That is not musical judgement; it is bookkeeping it
   should not have had to do.
3. **Nothing is reproducible or auditable.** Two runs of the same brief give
   different phrase choices, and there is no record of which spec produced which
   sheet.

An agent solves (1) completely and (3) partly — a batch run leaves logs and
sheets we can diff. (2) is the real design task, and it is where this plan
differs from the previous one: we do not remove the agent, we **remove the
bookkeeping from the agent** and leave it the judgement.

The judgement is genuinely hard to write as code, and this is the concession to
your point: *which* phrase is the emotional peak, whether a cadence wants the
augmented second or a plain descent, whether a chorus has been lifted too far —
these are the parts that resisted specification. That is what the agent is for.

## 3. What we already have, and what is fragile

| asset | where | durable? |
|---|---|---|
| 177 ABC transcripts | `datasets/five_stars/transcripts/` | local only (gitignored) — **moved out of `/tmp`** |
| the same, archived | `gs://akbar-december-2024-backup/arabmaqamrock/datasets/five_stars/v1/transcripts/` | yes |
| lyrics, style, maqam, manifest | `datasets/five_stars/{lyrics,manifest}.jsonl` | local only (gitignored) |
| ABC parser (with the `]` fix) | `datasets/five_stars/measure/abc.py` | **no — gitignored, local only** |
| measured M1 / structure | `datasets/five_stars/derived/` | local only |
| validator | `check_abc.py` | tracked, but **depends on the untracked parser** |
| 3 Claude reference triples | `scores/moon_*_{clean,v1,v2}.abc` | tracked |
| 3 Claude sessions | `local_workspace/claude_chat/*.json` | local only |
| spec v3 | `prompts/arabmaqamrock_abc_edit_spec.md` | tracked |
| calibrated prompt | `local_workspace/claude_prompt.md` | local only |

Still to fix in Phase 0: the validator cannot run on a fresh clone because its
parser sits in a gitignored directory. The in-house agent will depend on that
validator, so this stops being cosmetic.

## 4. What we know at this checkpoint

Carried forward so we do not re-derive it.

**The ABC channel works, but coarsely.** v2 moved the mode (D minor → D Hijaz)
and the register (chorus +2.5 to +4.2 semitones) and was immediately audible. It
did not reproduce the score note-for-note — measured adherence is at chance. So
the renderer transmits **pitch set and register**, not the melody. Any edit finer
than that is not reliably heard.

**The dose curve is bracketed.** 7–9 altered notes placed mid-phrase (v1):
inaudible. ~150 altered notes, every phrase rewritten (v2): unmistakably Arabic,
but the band disappeared behind it. The middle is **placement**, not quantity.

**The corpus is diatonic.** 0.83 accidentals per 100 notes overall; median track
0.38; 90th percentile 2.4; 74 of 177 tracks have none; 0 of 177 are Hijaz-shaped
even when the production prompt says "Maqam Hijaz". arabmaqamrock is a minor rock
band with maqam accents, not a maqam ensemble.

**The v2 failure was the brief, not the model.** Spec v2 said "change the pitches
freely… not obliged to preserve a single pitch", asked for a sayr in every
section, made "is the maqam identifiable" the first quality test, and told the
model to raise the chorus. Claude did all four. Spec v3 replaces the licence with
a budget.

**Only one of the four maqams is editable in this dialect.** The corpus is Hijaz
49, Ajam 43, Kurd 43, Nahawand 42. Of those, only Hijaz has a chromatic colour
that survives as `^`/`_` semitones and is not already the diatonic set. For
Nahawand, Ajam and Kurd the correct edit is close to *nothing* — a cadence note
or two. Most of the 200 tracks should get a very small edit, and an agent that
always wants to add colour will damage three-quarters of the catalogue.

## 5. The architecture: an agent with a toolbox

```
              agent (DeepSeek, in opencode, this repo)
                       |
     reads: spec v3 + playbook + corpus facts
                       |
     calls tools:
       maqam_inspect   parse, count, list phrases, cadences, sections, registers
       maqam_clean     pass 1 — mechanical repair, no pitch change
       maqam_candidates rank phrases by cadence suitability (deterministic)
       maqam_apply     apply a declared pitch edit to named notes, rewrite ABC
       maqam_validate  run check_abc.py + budget checks, return pass/fail + numbers
       measure         corpus distribution distance for a candidate sheet
       render          queue a YuE2 render
                       |
     writes: CLEAN.abc, MID.abc, CHANGES.txt, decisions.json
```

**The division of labour is the whole design.** The agent decides *what* to
change — which phrases, which notes, which figure. The tools decide *what the
numbers are*. An agent that has to count bars will get the numbers wrong and burn
its context doing it; an agent that is handed a phrase table and a validator can
spend its whole budget on the musical choice.

This is exactly what Claude lacked. It wrote its own parsers in 60 of its 98
steps and still misreported counts in its final report. We are not making the
agent smarter; we are removing the reason it was dumb.

### What the agent must never do

- Emit a count it did not get from `maqam_validate`. Every number in
  `CHANGES.txt` is tool output, not an estimate.
- Hand-write the ABC. It edits a structured note list; `maqam_apply` serialises.
  This removes the whole class of errors we saw: broken bars, lost ties,
  accidental-persistence bugs, `^/2` syntax.
- Skip the gate. `maqam_validate` must pass before a sheet is written.

### Why not a pure prompt, and why not a pure program

| option | what it is | verdict |
|---|---|---|
| (a) prompt-only skill | agent writes the score from scratch in one answer | **no** — this is v1/v2 again: no tools, no validation, invented counts |
| (b) **agent + tools** | the loop Claude ran, local, with the bookkeeping automated | **chosen** |
| (c) deterministic search | no LLM; generate and score candidate edits | not now — the policy is not understood well enough to encode, and the musical choice is the part that resisted specification. May become the inner loop of (b) later |

Option (c) is not abandoned, it is **demoted to the tool layer**: everything in
(c) that we can write down is a tool the agent calls. If a decision later proves
stable across tracks, it graduates from agent judgement to a deterministic tool —
that is how the agent's job shrinks over time instead of growing.

### Model choice

Measured prices (USD per million tokens): `deepseek-flash` $0.15 in / $0.60 out,
`deepseek-v4-pro` $0.66 / $1.98. Cache reads are near-free, which matters because
the spec and playbook are a fixed prefix on every track.

A Claude session was ~190 KB ≈ 50k tokens of transcript, most of it tool noise.
With the tools above, a track should be ~20–40k input and 3–6k output:
**≈$0.01–0.03 per track on flash, ≈$0.05–0.15 on pro** — so $2–30 for 200 tracks,
an estimate to be replaced by measurement in Phase 3.

Plan: test both on the Gate G2 task. If flash gets 3 of 5 phrases right, use
flash for the batch and pro only for disputes. If not, pro. Do not decide this
from vibes; the gate decides.

## 6. What to distil from the exported sessions

This is what the next Claude round is actually for. The logs already show the
procedure; what we lack is Claude's *preference function*.

| what | where it comes from | what it becomes |
|---|---|---|
| phrase segmentation | logs ("counted 25 phrases") | `maqam_inspect` output |
| cadence marking | logs + every `maqam_figures` line names a bar | `maqam_inspect` |
| which phrases get coloured | **only** from the reference sheets | playbook decision table + agent judgement |
| the shapes written at a cadence | **only** from the reference sheets | figure catalogue (10–20 items) in the playbook |
| how it avoids excess | v2 report counts accidentals per section | budget enforced by `maqam_validate` |
| failure modes it reaches for | logs ("re-map onto scale ladder", "raise the chorus") | forbidden list, spec v3 §6 |
| its self-check list | the `CHANGES` block | `maqam_validate` |

The playbook is the agent's knowledge, and it is the deliverable that makes the
agent portable to other models. It is written in the vocabulary Claude used —
phrase, cadence, jins, qarar, sayr, tessitura — because that is the vocabulary
that produced the behaviour we want.

## 7. Phases

### Phase 0 — freeze the checkpoint (~1 hour)

- ~~Copy `/tmp/opencode/fs_abc/` into `datasets/five_stars/transcripts/`~~ done,
  177 files.
- Still to do: verify checksums against the GCS archive.
- Make the validator runnable on a fresh clone: track `measure/`, or vendor the
  parser next to `check_abc.py`. **The agent depends on this.**
- Archive the three Claude sessions to
  `gs://…/arabmaqamrock/reference/claude_chat/round1/` — `local_workspace/` is
  gitignored and will be lost.
- Snapshot the 9 rendered WAVs and their transcripts.
- Tag `checkpoint-2026-10-26`.

**Gate G0:** a fresh clone can validate a score, and nothing we need lives only
in `/tmp` or only in `local_workspace/`.

### Phase 1 — calibration run (Claude, 3 tracks)

Claude redoes the same three takes with spec v3 and
`local_workspace/claude_prompt.md`. This is the reference set the in-house agent
has to match.

Inputs, unchanged between runs:

```
datasets/five_stars/transcripts/<uuid>.abc     the 177-track corpus
local_workspace/moon_edit/baghdad_moon_vanilla_01_101/score.abc   101
local_workspace/moon_edit/baghdad_moon_vanilla_02_313/score.abc   313
local_workspace/moon_edit/baghdad_moon_vanilla_03_577/score.abc   577
```

On return: export the three sessions to `local_workspace/claude_chat/round2/`,
save six sheets as `scores/moon_<seed>_{clean,mid}.abc`, and record per sheet:
`phrases_total, phrases_coloured, coloured_bars, notes_pitched, notes_pitched_pct,
accidentals, register_shift per section, notes_removed, notes_added`.

Then render `clean` and `mid` at the seed of the source take — six tracks, ~45 min
— and listen to each trio: original vanilla → clean → mid.

**Gate G1:** does `mid` sound like the band *and* carry the maqam? If it is still
bland on one side or a different band on the other, the edit idea is dead at the
spec level and no agent will save it. Stop and reconsider — most likely the
renderer, not the score, is the ceiling.

### Phase 2 — playbook + figure catalogue (~half a day)

`docs/guides/maqam_edit_playbook.md`, the agent's knowledge base:

- the task in Claude's vocabulary, one page;
- a decision table: given a phrase's section, final note, contour and register,
  colour it or not;
- the figure catalogue as data:
  `datasets/five_stars/derived/cadence_figures.json` — per coloured phrase,
  *(bar, phrase-final degree, degrees used, augmented-second pair, resolution,
  note count, rhythmic placement)*, 15–20 shapes from the reference sheets,
  filtered so each stays inside the corpus's step-motion and leap statistics;
- the forbidden list and the budget, restated as rules the agent applies.

**Gate G1b:** a person who has not read the chats can reproduce Claude's phrase
choices from the playbook alone, for all three tracks, within one phrase.

### Phase 3 — the agent harness (~2–3 days)

Build the tools in §5 (`maqam_inspect`, `clean`, `candidates`, `apply`,
`validate`, `measure`) and the agent configuration:

- a subagent definition in this repo: model, the playbook + spec v3 as its
  instructions, tool allowlist, and a hard rule that it cannot write an `.abc`
  except through `maqam_apply` and cannot finish without `maqam_validate` passing;
- a batch runner: one session per track, manifest in / results out, resumable,
  N parallel;
- `decisions.json` per track — the five chosen phrases, the figures used, the
  rejections — so a run can be audited without reading a transcript.

**Gate G2:** the in-house agent reproduces `MID` for the three calibration
transcripts. Measure: phrase-choice overlap with Claude, altered-note count,
accidental rate, register shift, corpus distance, validator pass rate, tokens
and dollars per track. If fewer than 3 of 5 phrases coincide, fix the playbook —
not the prompt, and not the model.

### Phase 4 — parity, blind (~1 day + 6 renders)

Render the in-house `MID` at the same seeds; compare against Claude's `MID` and
the vanilla take, unlabelled. Two listeners, forced ranking, repeat after a week.

**Gate G3:** in-house is not worse than Claude on the majority of pairs. If it
is worse, the agent is not ready and Phase 5 waits; the fallback is not "go back
to Claude" but "give the agent narrower work" — for example, it chooses the
phrases and the figure, and a deterministic tool writes the notes.

### Phase 5 — scale (deferred)

Batch over the 177 (and then the 200 new tracks): edit, validate, render, score,
shortlist automatically, listen only to the shortlist. See §8.

## 8. Evaluating without listening to 200 tracks

Auditioning 200 renders is the same manual bottleneck we are removing.

| layer | metric | exists? |
|---|---|---|
| structural | `check_abc.py` (bars, voices, meter, counts) | yes |
| budget compliance | phrases coloured, notes pitched, register shift | to build (Phase 3) |
| symbolic style | accidental rate, step motion, leaps, contour, register, silence | yes — `measure/` |
| audio style | embedding distance to the 177-track centroid | to build |
| "the band went quiet" | vocal-to-backing balance from the mix | to build — the v2 failure as a number |
| human | A/B on the shortlist | yes, last |

The audio metric is what makes 200 tracks tractable. Build it once on the corpus
we already have and use it to rank, not to decide.

## 9. Risks

| risk | why it matters | mitigation |
|---|---|---|
| the agent drifts from the budget | v2 happened because the brief allowed it; a weaker model may drift further | the budget is checked by `maqam_validate`, not asserted in prose; a failing sheet is not written |
| the agent invents counts | Claude did, even with tools | no number reaches `CHANGES.txt` except from a tool; the report is generated, not written |
| the renderer is the ceiling, not the score | adherence is chance-level note-wise | keep the dose coarse (5 phrases); measure the audio before optimising sheets |
| the in-house model is simply weaker at musical judgement | flash is cheap for a reason | G2 decides the model; if both fail, narrow the agent's job to phrase selection and let tools write the notes |
| overfitting to 3 reference sheets | a catalogue from 3 songs encodes 3 songs | extract shapes, not sequences; every figure must pass the corpus statistics; grow to 6 sheets max |
| most corpus maqams are diatonic | an always-colour agent damages Nahawand/Ajam/Kurd | dose is a function of the maqam, near-zero for the diatonic three; enforce in the playbook and validate |
| the baseline is a machine transcript | we are beautifying a transcript of a render, not the band's composition | accept it; the task is defined on transcripts and the renderer is the consumer |

## 10. What we are not doing

- Not fine-tuning a model on the edits. The playbook plus tools is smaller,
  inspectable, and does not drift.
- Not more than two more Claude rounds. Round 1 (old brief) and round 2 (spec v3)
  bracket the range; a third only if G1 is ambiguous.
- Not encoding production in ABC. Guitars, drums and mix are out of reach, and
  they were the other half of "the band went quiet".
- Not copying corpus phrases. Distribution matching only.
- Not a deterministic composer. If a decision stabilises, it becomes a tool; it
  does not become a replacement for the agent.

## 11. Deliverables

| file | phase | tracked |
|---|---|---|
| `datasets/five_stars/transcripts/` (177) | 0 | no (gitignored, archived to GCS) |
| `measure/` importable from a fresh clone | 0 | **yes** |
| `scores/moon_<seed>_{clean,mid}.abc` (6) | 1 | yes |
| `local_workspace/claude_chat/round2/` | 1 | no (archived to GCS) |
| `docs/guides/maqam_edit_playbook.md` | 2 | yes |
| `datasets/five_stars/derived/cadence_figures.json` | 2 | no (derived) |
| `maqam_tools.py` (inspect/clean/candidates/apply/validate/measure) | 3 | yes |
| agent definition (subagent prompt, model, tool allowlist) | 3 | **yes** |
| batch runner + `decisions.json` schema | 3 | yes |
| embedding scorer | 5 | yes |
| this plan, updated per gate | — | yes |

## 12. Next action

Phase 1 first, because it is cheap and it can cancel everything: three Claude
sessions with spec v3 and `local_workspace/claude_prompt.md`, export, six-track
render, listen.

In parallel, Phase 0's remaining items — the validator on a fresh clone and the
session archive — because the agent cannot be built on a validator that only
works on this machine.

Nothing in Phase 3 starts until G1 passes.
