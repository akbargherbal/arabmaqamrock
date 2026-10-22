# Repair Session Runbook

## Fixing one or two mispronounced words in a generated take

> The take is the asset. The repair is a composite, not a new performance.
> The aligner finds the word; the ear decides the defect; the tools narrow the
> search and execute the edit.

**Version:** 0.1 — 2026-10-22  
**Status:** draft for the first live run  
**Companion:** [Fixing Mispronunciations in AI Music](fixing_ai_music_mispronunciations.md)
(the field guide: principles, evidence, failure modes) and the
[Baghdad Moon token surgery](../happy_accidents/Baghdad_Moon/token_surgery/README.md)
reference run.

---

## How to use this document

- **Before the session:** read §1–3 and fill the intake sheet in §8.
- **During the session:** follow §5 one step at a time. Fill the record in §4 as
  you go.
- **After the session:** §9 closes the case. The filled record is the template
  for the next song.
- **If a rule conflicts with what you hear:** the ear wins. Change the rule
  only after the session, with a note and a measurement.

The motion in one block:

```
listen → collect defects → freeze + align → defect card → propose unit
→ approve loop → render batch → score + shortlist → audition → comp
→ verify → package → full listen
```

### One-screen checklist

```
[ ] Exact take hashed; original frozen
[ ] Lyric + semantic token stream + seed/prompt located
[ ] Alignment run on the exact stem/timebase used for the comp
[ ] All defects collected before any editing
[ ] Defect card filled for each occurrence
[ ] Unit proposed; 2–4 s loop approved by ear
[ ] Generation and comp windows recorded
[ ] Seed batch rendered (short tails, one batch)
[ ] Candidates scored on the comp window; shortlist of 3–5
[ ] Take picked by ear
[ ] All accepted units comped in one pass onto the original
[ ] Outside-diff = 0; edges, duration, kept melisma, downstream checked
[ ] Full section / full track listened
[ ] Record, manifest, checksums, A/B pack written
```

---

## Decisions locked in this session

1. The aligner is an **index**, not a ruler. It finds the word; it does not
   define the cut.
2. The edit is a **musical unit**, not a word box: note offsets, breaths and the
   next onset decide the boundaries.
3. A correct held note is **never** replaced to fix a word.
4. The human owns four gates: the defect card, the unit approval, the take pick
   and the final listen.
5. **One case = one take.** Collect all defects before editing; batch the
   renders.
6. No UI, no full re-render, and no `repair` CLI until the first live run proves
   the specification.

---

## 1. The deal

This session is:

- **one case = one take**; do not mix takes in a case;
- one existing take, preserved;
- one or more named words, fixed in one pass;
- a deterministic composite: outside the changed spans, the final is
  byte-identical to the original in the same sample format;
- documented with a record, a manifest and an A/B pack.

This session is **not**:

- a new generation;
- a mix revision;
- a lyric rewrite;
- a UI project;
- a seed lottery;
- a research loop. The method is fixed before the session starts.

**Done means:** the target words pass the ear, everything kept is unchanged,
the checks pass, and the record is filled.

---

## 2. What the reference run proved

These findings are the reason for the rules below. They are not up for
renegotiation mid-session; the full evidence is in field guide §14 and the
Baghdad `token_surgery/` docs.

| finding | consequence for this session |
|---|---|
| The aligner found 125/125 words in ~45 s CPU, but word starts can be ~0.6 s late and ends at holds are unstable. | Use it as an **index** — which word, which occurrence, roughly where — not as the cut. |
| The repair unit is wider than the word: word 2 starts at 203.92 s, but the unit starts at 202.21 s. | Find the unit from the **audio** (note offsets, breaths, next onset), not from the word box. |
| The phrase candidate sang the word but ended the final note on D4 instead of the original G4. | **Never replace a correct held note** to fix a word. |
| Per-character scores separated the bad `ه` (−3.2 vs fixed −0.1) and `ف` (−5.0 vs fixed −0.1); word scores diluted them. | Score the **target characters on the comp window**, not the whole phrase. |
| The final is bit-identical outside the two changed spans in the same sample format; the word-1 composite preserves the original outside its unit. | **Comp onto the original**, verify outside the union, and do not chain full re-renders. |

---

## 3. Roles

| human | tool |
|---|---|
| Listen to the whole take and collect defects. | Align, locate, list occurrences. |
| Write the defect card: occurrence, heard vs target, note-after, what must not change. | Propose the unit, the two windows and the prefix/max. |
| Approve the unit by loop. | Render the seed batch. |
| Pick the take by ear. | Score, filter, shortlist. |
| Final full-section listen. | Comp, verify, package, record. |
| Decide keep / fix / abandon. | Never decide aesthetics. |

The human gates are not ceremony. They are exactly where the machine is
unreliable: a single consonant, timbre, “same singer”, and whether the note
after the word is correct.

---

## 4. The repair record

One record per case. Fill it as you go; it is the model for every future song.

```yaml
case:
song:
take:
take_sha256:
model / seed / prompt:
lyric:
target_word:
occurrence:
section / line:
defect:
  heard:
  target:
  class:            # consonant | vowel | syllable | wrong word | ending/tanwin | stress | note/pitch | timing | mix
  note_after:       # keep | replace | unsure
  must_not_change:
alignment:
unit:               # start–end
generation:         # start–end, prefix, max
comp:               # start–end, fades, gain
candidates:         # seeds, count
shortlist:          # take, char score, f0, duration, edge
accepted:
final:              # path, sha256, changed spans, outside diff
checks:             # outside 0 | edges | duration | melisma | downstream
verdict:            # ship | keep original | retry
notes:
```

---

## 5. The protocol

### Phase 0 — Intake (human, before any editing)

1. Listen to the whole track once without stopping to fix anything.
2. Note every defect: timestamp, section, line, word, what you heard.
3. Decide whether the take is worth keeping. If not, generate a new take; this
   runbook is for a take you want to preserve.
4. Do **not** open the editor yet. Batch the defects; one session repairs all
   of them.

**Output:** a list of candidate defects. No audio edits yet.

---

### Phase 1 — Freeze and align (tool)

**Input:** the exact take, the lyric, the semantic token stream, the seed and
prompt.

**Do:**

- hash the take; never overwrite it;
- align the lyric to the **exact stem/timebase** that will be comped (usually
  the vocal stem);
- confirm every target occurrence and its neighbours;
- list occurrences with timestamps and line numbers; play a short clip if a
  word repeats;
- record the model revision and the alignment date.

**Output:** `words.json`, occurrence list, hashes.

**Gate:** the target words are found, the neighbours are known, and the stem
and alignment use the same timebase.

**Fail:** no token stream → the prefix route is unavailable. Choose donor or
section re-render and record why. Do not pretend the prefix route is available.

---

### Phase 2 — Defect card (human)

For each defect, fill the `defect` block in §4.

**Rules:**

- The **occurrence** is part of the defect. Fix “this occurrence”, not “the
  word”.
- Rough phonetics is enough for `heard`.
- `note_after: unsure` defaults to **keep the original note** and comp only the
  word. That is the safe side.
- If the defect is the note itself — pitch, melisma, a held final vowel — say
  so; the unit changes.
- Write `must_not_change`: the phrase, the melisma, the instrumental, the
  timing.

**Output:** one card per defect.

**Gate:** `heard`, `target`, `class` and `note_after` are filled. No rendering
before this.

---

### Phase 3 — Propose the unit (tool)

For each card:

- **Start:** the last real boundary before the word — a note offset, a breath,
  a real gap — minus 0.2–0.3 s. Do not use the aligned word start if it falls
  inside the word.
- **End:** the next word’s onset or the note boundary. If the word’s own final
  note is held and correct, end **before** the hold.
- **Mode:** `word-only` by default; `note-replace` only if the card says the
  note is the defect.
- **Two windows:**
  - `generation` — where the model starts re-singing; at or before the unit
    start. Cutting earlier is safe: the extra lead is generated and discarded,
    not comped.
  - `comp` — what is actually replaced; the musical unit.
  - They may differ. If the comp starts before the generation cut, that lead-in
    comes from the candidate and must be auditioned.
- **Prefix/max:** `prefix = floor(gen_start × 25)`,
  `max = ceil(gen_end × 25)`, on the exact token timeline. Leave a small tail.
- **Flags:** no gap before the word, continuous word, long hold, neighbour
  inside the unit, unit longer than ~4 s, target at the song edge.

**Output:** `spec/repair_spec.json` plus a 2–4 s loop of original vs proposed
unit.

**Gate:** none yet; the human approves next.

---

### Phase 4 — Approve the unit (human)

Loop the proposed unit 2–3 times. Check:

- the first consonant is inside the loop;
- the last vowel is inside the loop;
- the note after the word is the one you intend to keep or replace;
- the join is at a performance boundary, not mid-word.

**Output:** approved numbers, or a nudge of ±0.1–0.3 s.

**Gate:** “This is the smallest unit that contains the defect and keeps what is
correct.” If you cannot say yes, widen to the phrase and log why. Do not render
yet.

---

### Phase 5 — Render the batch (tool)

- Build the request from the **baseline token stream**; use the approved
  prefix/max.
- Sweep 8–16 seeds; 32 only if the first round fails.
- Render a **short tail**, not the whole song.
- Batch all words in the case in one session; model load is the fixed cost.
- Save every request and seed.

**Output:** `candidates/` with one WAV per seed, plus the requests.

**Gate:** every candidate exists through the comp end; no truncation.

**Fail:** truncation → increase max. Model or environment error → fix the
environment; do not change the musical parameters.

---

### Phase 6 — Score and shortlist (tool)

Score **on the comp window only**:

- target character scores (same aligner), compared to the original and to a
  known-correct occurrence if one exists;
- f0 contour and final note;
- duration and onset lag;
- edge RMS step and click.

**Hard filters:**

- wrong final note when the note is being kept → reject;
- audible edge step → reject or mark;
- duration/onset off by more than ~20% → flag.

**Output:** a table and a shortlist of 3–5.

**Gate:** at least one candidate is not worse than the original on the target
characters. If all candidates fail the same phoneme, stop and change the text
or respelling; do not add seeds.

---

### Phase 7 — Audition and pick (human)

A/B the original and the shortlist at the same timestamp. Check:

- the word, not just the phoneme;
- the note after it;
- the join;
- the timbre — “same singer”.

**Output:** accepted take, or reject.

**Gate:** “Same singer, right word, right note, no audible join.”

**Fail:** use the branches in §6. After two rounds, stop; keep the original or
change the route.

---

### Phase 8 — Comp and verify (tool)

- Apply all accepted units to the **original** in one pass.
- Vocal stem only; keep the instrumental.
- Fades and level match inside the unit; joins at the approved boundaries.
- Verify:
  - outside the union of comps: max abs diff = 0;
  - edge steps: report, do not hide;
  - duration unchanged; no clipping or DC;
  - target character score not worse, and ideally improved;
  - kept melisma: f0 contour and end unchanged;
  - local re-align: downstream words did not move.

**Output:** `output/final.wav`, `qc/`.

**Gate:** all checks pass. If not, fix the cause; never ship a failed check.

---

### Phase 9 — Package and close (tool + human)

- A/B clips and a full-track review file.
- Manifest, checksums, reproduce script.
- The filled record from §4.
- One paragraph: what worked, what did not, which rule changed.

**Human:** full-section or full-track listen. Verdict: ship / keep original /
retry.

**Output:** the case folder. This is the model for the next song.

---

## 6. Failure branches

| symptom | likely cause | action |
|---|---|---|
| First consonant missing | cut too late; alignment late | move the generation and comp start earlier by 0.2 s |
| Word right, hold wrong | the note was replaced | switch to word-only; keep the original hold |
| Audible click or level jump | join mid-word or no fade | widen the comp 50 ms; fade inside the unit; level-match |
| All seeds sing the same wrong phoneme | text/prompt, not luck | change the phonetic respelling in the request; do not grind seeds |
| Candidate timing drifts | wrong stem/timebase; time-stretch | align the exact stem; do not time-stretch |
| Score high, ear rejects | metric gap | trust the ear; the score is a filter |
| Downstream words move | whole-file re-align instability | re-align locally; compare word timings around the edit |
| Unit includes a neighbour | boundary chosen from the word box | use the note offset/onset; re-approve |
| No safe gap before the word | continuous phrase | widen to the phrase; if still unsafe, section re-render |
| Best take is not better | the repair is making it worse | keep the original; record the decision |

---

## 7. Guards

1. **Preserve first.** Hash; never overwrite.
2. **Repair, don’t re-render.**
3. **The unit is musical, not lexical.**
4. **Cut before the error;** keep 100% of the context before it.
5. **Keep what is correct;** replace less.
6. **Never replace a correct held note** to fix a word.
7. **Score what you comp;** the ear is the oracle.
8. **Bit-identity outside the edit** (same sample format) is the only
   guarantee.
9. **If 32 seeds fail the same way, it is the text, not luck.**
10. **Stop at good enough;** keeping the original is a valid outcome.

---

## 8. The first live run

### Intake

- **Batch:** the songs you are listening to now.
- **When you hear it:** pause, write the timestamp, section, lyric line and what
  you heard; resume. Do not open the editor.
- **Trigger:** the first defect you are sure of.
- **Do not fix while listening.** Finish the listen, then start the session.
- If a second defect appears in the same take, include it in the same case and
  batch the renders.

### Pre-flight for the chosen take

```
[ ] The take has its semantic token stream, seed and prompt
[ ] The lyric file matches what was actually sung
[ ] A vocal stem exists, or can be separated
[ ] The exact stem/timebase for the comp is known
[ ] The original is hashed and write-protected
```

**Route check:** Phase 5 assumes a prefix-capable token model. If the take is
from a hosted system without token/prefix control, replace Phase 5 with the
donor or section-regeneration route from the field guide; the intake, defect
card, unit approval and verification steps still apply.

### Case sheet

```
case: 001
song:
take:
section / line:
word:
occurrence:
heard:
target:
note after: keep / replace / unsure
must not change:
```

### Dry run: known example from the current batch

Use these two cards to rehearse the spec and the loop before a live defect, if
you want a dry run. They are **not** the session; they are the test.

| field | `مُكْفَهِرًّا` | `حُصُونٌ` |
|---|---|---|
| section | Chorus | Verse 1 |
| line | `مُكْفَهِرًّا عَلَى الْحَوَادِثِ` | `تَنْمِينَا حُصُونٌ` |
| occurrence | 1 of 1 | 1 of 1 |
| heard | to confirm | to confirm |
| target | `مُكْفَهِرًّا` | `حُصُونٌ` |
| likely class | ending / shadda / long vowel | `ص` |
| note after | to confirm; default keep | to confirm; default keep |

If the defect is the final held vowel, the card must say `note after: replace`;
otherwise the default is word-only.

A side note: the lyric’s `...اؤوا` endings are unusual and may cause other
wobbles. Treat that as a generation-prompt issue, not a reason to change this
protocol mid-repair.

### Session order

1. Freeze and align the chosen take.
2. Fill the defect card(s).
3. Propose and approve the unit(s).
4. Render all words in one batch.
5. Score and shortlist.
6. Audition and pick.
7. Comp and verify.
8. Package and full listen.
9. Fill the record and close.

### Time box

| phase | human | machine |
|---|---|---|
| listen + intake | 5–10 min | — |
| freeze + align | — | ~1 min |
| defect card + unit approval | 5–10 min | — |
| render (8–16 seeds, short tails) | — | 10–20 min |
| score + shortlist | — | 1–2 min |
| audition + pick | 5–10 min | — |
| comp + verify | — | 1–2 min |
| full listen + record | 5–10 min | — |

**Stop rule:** two render rounds per word. If no candidate beats the original by
ear, keep the original or change the route.

### What not to do in this run

- Do not build a UI.
- Do not re-render the whole song.
- Do not rewrite the lyric mid-repair.
- Do not accept a take because its score is high.
- Do not keep grinding seeds after the same failure.
- Do not ship without the outside-diff check.

---

## 9. What we are not building yet

- **The `repair` CLI.** The first live run is the specification. Automate only
  what you had to do by hand twice.
- **An automatic wrong-word detector.** Character scores are a filter, not a
  verdict.
- **A replacement for the aligner.**
- **A UI.** Audition files in the DAW or player are enough.

### Protocol change control

After the live run, change a step only if the session produced evidence for it.
Record the change, the reason and the affected case. Do not silently turn the
method back into trial and error.

---

## Appendix A — Timing and token math

- The model timeline is **25 frames per second**.
- `prefix = floor(gen_start × 25)`; `max = ceil(gen_end × 25)`.
- Reference: `3933 / 25 = 157.32`, `5056 / 25 = 202.24`,
  `5397 / 25 = 215.88`.
- The comp window can be wider than the generation window; the extra lead or
  tail comes from the candidate and is auditioned.
- Use the exact stem/timebase. A cached stem 25 ms longer than the mix is enough
  to move a join.
- A short tail is usually enough; verify the candidate exists through the comp
  end. Rendering to the end of the song is not required.

## Appendix B — Case folder layout

```
cases/<case-id>/
  README.md              one-page summary + verdict
  record.md              the filled §4 record
  inputs/                original.wav, hashes, requests
  stems/                 original + candidate vocals
  tokens/                baseline + prefixes
  spec/                  repair_spec.json, loops
  candidates/            one WAV per seed
  qc/                    comp/verify reports, edge steps
  output/                final.wav + sha256
  review/                A/B clips, full-track review file
```

Copy the reference run’s layout; do not invent a new one.

## Appendix C — Command cheat sheet

Current pieces (paths from the reference run and the karaoke repo; exact
reference commands are in field guide §14):

- alignment: `a1_align_run.py` / `a0_align.py` (`yue2-karaoke-align`)
- comp: `scripts/comp_region.py`
- verify: `scripts/verify_final.py`
- melisma: `scripts/analyze_melisma.py`
- render: the prefix-capable `audio.cpp` binary plus a request JSON

Future CLI (not built yet):

```
repair index <run>
repair occurrences "<word>"
repair fix <id> --seeds 16
repair audition <id>
repair accept <id> <take>
repair build
```

Record the exact command in the case record, even if it is manual. The first run
defines the CLI.

## Appendix D — Glossary

- **Unit:** the musical span that contains the defect and is replaced.
- **Generation window:** where the model starts and ends re-singing.
- **Comp window:** the span actually grafted into the original.
- **Melisma:** a sustained or ornamented note, often after the word.
- **Prefix:** the semantic-token position where the re-sing starts.
- **Bit-identity:** outside the comp, the final is byte-for-byte the original.
- **Defect card:** the human’s structured description of the error.
- **Repair record:** the filled, reproducible account of the case.
