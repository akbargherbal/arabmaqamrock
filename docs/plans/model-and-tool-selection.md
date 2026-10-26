# Model and tool selection for the in-house editor agent

**Status:** proposal, feeds Phase 3 of `inhouse-maqam-editor.md`
**Date:** 2026-10-26
**Question:** which model runs the edit, and what tools must it have so that model
choice stops being the thing that decides the outcome?

---

## 1. What the Claude sessions actually tell us about tools

Measured from the three exports in `local_workspace/claude_chat/`:

| | april | autumn | orange |
|---|---:|---:|---:|
| tool calls | 20 | 21 | 10 |
| shell lines issued | 613 | 558 | 273 |
| lines of Python written | ~560 | ~556 | ~269 |
| separate scripts | 17 | 19 | 6 |

**42 throwaway scripts, about 1,385 lines of Python, for three songs.** Nearly all
of it was bookkeeping: parse the ABC, count bar durations, find phrases, find
echoes, rewrite the score, check the rewrite.

Three consequences:

1. **The task is not too hard for a model. It is too hard for a model without
   tools.** Claude had bash, so it built an ad-hoc music library from scratch each
   time — `parse.py` three times, `lib.py`, `show.py`, `phr.py`, `clean.py`,
   `ech.py`, `model.py`, `render.py`, `versions.py`, `val.py`, `gen.py`, `b.py`.
   Every one slightly different, every one buggy in a different way. One session
   patched its own parser in place with `sed`. Another gambled on
   `pip install music21`.
2. **That is also why its counts were wrong.** The report was written from memory
   of what the scripts printed, after the scripts had been patched.
3. **The parts it never had to invent are the answer.** Segment into phrases, mark
   cadences, colour five, keep the rest plain — that took it almost no work. The
   90% of the transcript that looks like effort is arithmetic.

So the tools are not an optimisation. They are what makes a mid-tier model
viable at all.

## 2. The tool surface (v0)

One CLI, `maqam`, with a small stable surface. The agent gets bash; it should need
nothing else. Versioned in this repo, so every model is graded against the same
tools.

```
maqam inspect   <score.abc> [--phrases] [--json]
maqam clean     <in.abc> -o <clean.abc>
maqam candidates <clean.abc> [--maqam hijaz] [--n 5]
maqam figures   [--maqam hijaz]
maqam apply     <clean.abc> --edit <edit.json> -o <mid.abc>
maqam validate  <mid.abc> --against <clean.abc> [--json]
maqam measure   <mid.abc> [--corpus]
maqam diff      <a.abc> <b.abc>
```

### 2.1 `inspect` — the decision surface

This is the most important tool, because it is the only thing the agent sees on
which to base a musical judgement. It must print a **phrase table**, not a score:

```
idx sec     bars      n  first  last  contour  mean  vs_sec  ends_on   rest_after acc
 3  verse   12-15     9  D5     D4    down     D4.6   +0.2   tonic      1.75     0
 4  verse   16-18     7  A4     A4    arch     A4.1   -0.3   fifth      2.00     0
...
 25 outro   61-69    12  D4     D4    down     D4.0    0.0   tonic      4.00     0
```

Columns are the ones the agent needs to decide: section, span, note count,
starting and **final** note, contour, mean pitch and its offset from the section
mean, whether the final falls on the tonic or fifth, and the rest that follows
(phrase boundary evidence).

Everything the agent might otherwise try to compute is precomputed. If it has to
count, we have failed.

Also print a corpus context block, once per sheet:

```
corpus context: accidental rate this score 0.0/100 (corpus median 0.38, p90 2.4)
                step motion 86% (corpus 85%)   leaps>=5  3.9% (corpus 4.2%)
```

### 2.2 `candidates` — a proposal, not a decision

Ranks phrases by the §5.1 rules: ends on tonic or fifth, final note is long,
one per section except a verse which may take two, minimum three phrases apart,
cover verse / pre-chorus / chorus / last third. Prints a proposed set of five with
the reason for each. The agent may accept, swap a member, or override with a
stated reason — `decisions.json` records which.

### 2.3 `apply` — the write boundary, with rails

The agent does not write ABC. It declares an edit:

```json
{
  "maqam": "hijaz",
  "phrases": [
    {"index": 12, "reason": "verse cadence on the tonic",
     "changes": [
       {"note": -3, "from": "E", "to": "_E"},
       {"note": -2, "from": "F", "to": "^F"}]}
  ]
}
```

`apply` refuses only on **structural breakage** — cases where the file would not
be a valid score or would not be the same song:

- phrase index unknown, or note index outside the phrase;
- a pitch list whose length differs from the phrase's note count;
- a tie joining two different pitches after substitution;
- a bar that no longer sums, a note count that changed, or syntax this dialect
  cannot express;
- a change outside the phrases declared in the edit.

Everything else — how many phrases, how many accidentals, how far the register
moved — is **measured and reported, not refused**. `validate` prints the numbers
and their distance from the spec's starting point; `decisions.json` records
deviations with the agent's reason. A hard budget wall would hardcode a musical
decision we are not sure about; a measured deviation is visible, comparable across
tracks, and reversible.

This still inverts the failure mode we saw. Claude wrote the score first and
discovered the damage afterwards; here the damage that invalidates the file
cannot be written, and the damage that is merely bad taste is loud.

### 2.4 `validate` — prints the report

Runs `check_abc.py` and the budget checks and prints the §9 `CHANGES` block with
counted values. The agent pastes it; it does not compose it. Numbers in the report
are tool output or they are absent.

### 2.5 `measure` and `diff`

`measure` returns the corpus-distance numbers for a candidate sheet: accidental
rate, step/leap shares, contour, register shift per section, silence share.
`diff` prints a note-level diff in musical terms (`bar 34, phrase 12, degree 3:
E → E♭, unchanged duration`) so the agent — and we — can read what changed without
parsing ABC by eye.

### 2.6 What is deliberately *not* a tool

- **Which phrases to colour.** Judgement. The `candidates` output is a suggestion
  with reasons, and the agent may ignore it. If this ever stabilises, it becomes
  a better ranking — not a new agent job.
- **What figure to write.** Judgement, informed by `figures` and by the measured
  numbers.
- **Rewriting the melody.** Not offered as a tool of convenience. There is no
  `maqam rewrite` subcommand, and the skill explains why: it was tried twice in
  the reference sessions and failed both times. That is project history, not a
  taste rule.

## 3. Ground truth: playbook, not the model's memory

The models we are choosing between have read a lot about maqam, and much of it
contradicts what we measured. Our corpus is **diatonic** (0.83 accidentals per 100
notes; 74 of 177 tracks have none; 0 of 177 are Hijaz-shaped) and the brief asks
for a small edit on a diatonic band. A model answering from its priors will
produce v2 again, confidently.

Therefore:

- **The playbook and spec v3 are the house rules and override the model's
  knowledge.** Both are in the agent's instructions, and `apply` enforces them
  mechanically.
- **No web access in the batch run.** Searching "maqam Hijaz" returns general
  theory that argues for exactly the failure we are correcting. Nothing it needs
  is outside the repo.
- **Training-data knowledge is welcome for one thing only:** recognising a jins
  gesture so it can pick a plausible figure from the catalogue. It is not welcome
  as a source of rules.

This is testable, and §5 tests it.

## 4. Axes worth testing

| axis | values available now | note |
|---|---|---|
| model | `deepseek-v4.1-flash` (BytePlus plan), `deepseek-v4-pro`, `moonshotai/Kimi-K3`, `Kimi-K2.7-Code`, `Kimi-K2-Thinking`, `GLM-5.3`, `GLM-5.3-Flash` | the BytePlus plan is coding-oriented; that is not disqualifying once the tools carry the arithmetic |
| reasoning effort | `none, low, medium, high, xhigh` (BytePlus flash), `low, high, max` (others) | a real axis: the edit needs planning, not speed |
| context | 1,024k on the BytePlus model | the spec + playbook + a score + corpus stats fit comfortably |
| tool surface | full / narrowed | narrowing to `inspect, apply, validate` may help weaker models |

Not worth testing: temperature-style randomness, prompt micro-variants. The spec
is fixed, or the comparison is meaningless.

### Cost is probably not the constraint

BytePlus is a subscription, so marginal cost inside quota is ~0. Even at metered
prices — flash $0.15/$0.60 per million, pro $0.66/$1.98 — a track at ~30k in /
~5k out is **$0.01–0.03 on flash, $0.05–0.15 on pro**, so $2–30 for all 177. The
real costs are wall-clock time and the renders, which are 5–7 minutes of GPU each
and dominate everything. Choose for quality per track, not per token.

## 5. The selection protocol

A benchmark, not an opinion. Three fixed tracks (101, 313, 577) from the frozen
transcripts, the same spec v3, the same playbook, the same tool versions, the
same prompt. Claude's round-2 sheets are the reference.

### 5.1 Hard gates — pass/fail, and a fail disqualifies

| | gate | how |
|---|---|---|
| H1 | validates: bar sums, one voice, one meter, note count within 2% | `maqam validate` |
| H2 | finishes unattended: no question to the user, no invented input | run log |
| H3 | writes the three declared files, correctly named | filesystem |
| H4 | report numbers agree with tool output (±1) | `changes.txt` vs `validate` |

### 5.2 Scored, 100 points

| | criterion | points | how |
|---|---|---:|---|
| S1 | phrase agreement with Claude (Jaccard over coloured phrase indices) | 30 | automatic |
| S2 | budget compliance: 4–6 phrases, 10–18 notes, 10–18 accidentals | 20 | `validate` |
| S3 | corpus distance: accidental rate, step motion, leaps inside p10–p90 | 20 | `measure` |
| S4 | figure quality: augmented second present once per coloured phrase, entered and left by step, phrase final on tonic/fifth | 20 | `validate` |
| S5 | efficiency: tool calls, tokens, wall time | 10 | run log |

S1 is a proxy, not truth, which is why it is 30 and not 60. A model that loses S1
but wins S2–S4 is **not** rejected — it may be better than Claude. It goes to the
blind listen.

### 5.3 Behaviour tests — one run each, cheap, and they matter more than S1

| | test | expected |
|---|---|---|
| F1 | send the score and the prompt, omit the lyrics | stop, name the missing input, ask |
| F2 | paste a truncated guide (nothing after §4) | detect it, ask for the rest |
| F3 | send a score with a stray 5/8 bar inside 2/4 | collapse it, no crash, no pitch change |
| F4 | ask for "a fuller version as well" | refuse the third reading, per the brief |
| F5 | send a phrase where the budget is exceeded | `apply` refuses; the model reports the refusal instead of forcing it |

F1 and F2 test whether the model follows the input gate or bluffs. F5 tests
whether it respects a tool's "no". A model that argues with its own validator is
unusable at 177 tracks, however good its music.

### 5.4 Schedule

1. **Smoke test** — one model, one track, to prove the harness and the tool
   contracts. Not a ranking.
2. **Screen** — 6 models × 1 track × 1 rep. Cut to three.
3. **Qualify** — 3 models × 3 tracks × 3 reps, variance included. This is where
   H1–H4 and F1–F5 run.
4. **Blind** — the winner plus Claude's sheets, six renders, two listeners
   (this is G3 of the main plan).

Total symbolic work is minutes and cents; the only expensive step is step 4, which
is the same render budget already planned.

## 6. Where the tools make the biggest difference

Ordered by what the logs say would have saved the most:

1. **`inspect --phrases`.** Claude recomputed phrases in every session, and its
   phrase boundaries were hand-counted and admitted to be approximate. If the
   agent receives the phrase table, its whole budget goes to the choice instead of
   the census.
2. **The parser, once.** Three sessions wrote three parsers. One shared, tested
   parser with the `]` fix removes a class of quiet corruption.
3. **`apply` with rails.** Removes broken bars, lost ties, accidental-persistence
   bugs and `^/2` syntax. Claude spent multiple steps chasing each.
4. **`validate` printing the report.** Removes invented counts, which is the one
   defect that makes a sheet untrustworthy even when the music is fine.
5. **`diff` in musical terms.** Lets a model (or a human) check "did you only
   touch five cadences?" without reading ABC.

## 7. Recommendation

1. Build the tools before comparing models. A model comparison run on hand-written
   ABC measures the model's bookkeeping, not its musical judgement — and we
   already know the bookkeeping loses.
2. Default candidate: **`deepseek-v4-pro` at high reasoning effort**, with
   `deepseek-v4.1-flash` as the cheap control. The plan's subscription makes flash
   free to try; the gate decides.
3. Keep Kimi-K3 and GLM-5.3 in the screen. They are the natural alternatives if
   the DeepSeek family fails on S4, and they cost one run each to find out.
4. Do not add web access to the batch agent. The house rules beat general theory
   for this corpus.
5. If the winner still fails H1 or F5, the answer is not a bigger model. It is a
   narrower job: the agent proposes phrase indices and figures, and `apply`
   performs the edit from a template.
