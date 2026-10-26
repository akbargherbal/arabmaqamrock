---
name: maqam-edit
description: >-
  Use when editing an ABC melody transcription for the arabmaqamrock project —
  given a SheetSage2 transcript, a maqam, a style prompt and lyrics, produce a
  CLEAN sheet (mechanical repair) and an MID sheet (a small, cadence-placed maqam
  edit). Describes a working method, the tool contracts it relies on, and the
  project's verification rules.
---

# arabmaqamrock — melody edit

You are editing a melody, not composing one. Read this whole file before you
touch a score.

**What the result must satisfy** is in `prompts/arabmaqamrock_abc_edit_spec.md`.
That spec governs the output. This file governs the process — how to get there
without breaking the file or losing track of what you changed.

This is a method that has worked, not the only method. If you can satisfy §4 and
§5 another way, do that instead; the checks are the contract, the steps are not.

## 1. The gate

Before any work, confirm you have all four inputs:

1. the spec;
2. the style block and the task;
3. the transcription (`X:`, `M:`, `L:`, `Q:`, `V: Vocal`, `V: Ins`, `K:`, `%`
   section markers);
4. the lyrics.

If any is missing or truncated, stop and ask — naming exactly which one. Do not
reconstruct a missing input, and do not guess a key, a meter or a section that is
not written down. Compare the score's `%` section markers against the lyrics'
sections, and report any mismatch before proceeding.

State what you received in a short `INPUTS` block, including the score's bar
count, note count per voice, meters and sections, so a truncated score is caught
at the door.

## 2. The method

**1. Parse to a flat timeline.** Turn the ABC into a sequence of notes and rests,
each with a duration in sixteenths, carrying its bar index and section. Assert
that every bar sums to the meter *before* doing anything else. Do not edit text;
edit the timeline.

**2. Build the phrase table.** Cut at rests of one beat or more, and at section
markers. For each phrase, print: index, section, start position, note count,
total duration, and the pitch list with durations and ties. This table is where
your judgement happens — read it, don't read the ABC.

Optionally annotate each phrase with: contour (rising / falling / arch), mean
pitch and its offset from the section mean, whether the final note is the tonic or
its fifth, and the rest that follows. Useful, not mandatory.

**3. Clean (pass 1).** Merge echo runs (three or more identical adjacent pitches),
merge adjacent rests, fix octave slips, complete short bars, collapse to one
meter, delete the `Ins` voice. Change no pitch except an octave slip and the final
tonic. Re-assert every bar sum after cleaning.

**4. Read the anomalies before editing.** Print runs of repeated pitches, the
transcript's own accidentals, any bar that does not sum, and any note that jumps
an octave and back. Decide each case explicitly and write down what you decided.

**5. Choose the phrases to colour.** This is the musical decision, and it is
yours. State a list of phrase indices with a one-line reason each, *before*
writing any pitch. The spec gives a starting budget — roughly five phrases, the
last two to four notes of each. Treat it as a starting point, not a cage: if your
reading of the melody needs a different count or placement, do it and justify it
in the report. What you may not do is colour secretly — every changed note must
fall in a phrase you listed.

**6. Express the edit as pitch lists.** For each chosen phrase, supply a list of
pitches of exactly the same length as the phrase's notes, and substitute. Assert
length equality and tie consistency (a tie must join two identical pitches after
substitution). Expressing the edit this way makes the rhythm structurally
impossible to disturb, which is the property you want.

**7. Write, verify, report.** Serialise back to ABC, then verify §4. Report from
tool output, never from memory.

## 3. Tools

Use these. If one is missing or broken, say so and stop — do not write a
replacement inline. Duplicated or ad-hoc parsers are where counting errors enter,
and once the counts are wrong everything downstream is wrong.

| tool | must return |
|---|---|
| `maqam inspect <score.abc> --phrases` | the phrase table from step 2, plus bar sums, note counts per voice, sections, meters, the transcript's own accidentals |
| `maqam clean <in.abc> -o <clean.abc>` | pass 1, with a log of every mechanical change and the resulting bar sums |
| `maqam apply <clean.abc> --edit <edit.json> -o <mid.abc>` | the written score; refuses only on structural breakage (§4 hard) |
| `maqam validate <mid.abc> --against <clean.abc>` | pass/fail on the hard checks, the measured numbers from §4, and the `CHANGES` block |
| `maqam diff <clean.abc> <mid.abc>` | a musical diff: bar, phrase, degree, old → new, duration unchanged |
| `maqam measure <score.abc>` | the corpus-distance numbers: accidental rate, step motion, leaps, contour, register per section, silence |

`edit.json` is declarative:

```json
{"phrases": [
  {"index": 12, "reason": "verse cadence already on the tonic",
   "pitches": ["E4", "Eb4", "F#4", "D4"]},
  {"index": 19, "reason": "chorus cadence, wants the fifth",
   "pitches": ["C5", "Bb4", "A4"]}]}
```

Pitch spelling, accidental state within a bar, octave marks and tie handling are
the tool's job. Do not hand-write ABC to work around a spelling problem — say
what you wanted and let the tool report what it could not express.

## 4. Verification

**Hard — the file is unusable if any fails. No justification accepts these:**

1. exactly one voice, `Vocal`;
2. exactly one `M:`, and every bar sums to it;
3. note count within 2% of the input (lyrics must still fit, one note per
   syllable);
4. section order and count unchanged;
5. no microtonal syntax, no chords, tuplets, grace notes, embedded lyrics;
6. ties consistent, accents and spelling valid in this ABC dialect;
7. ends on the tonic;
8. every changed note lies inside a phrase you declared in step 5.

**Measured — report the number, and if it is outside the spec, the reason:**

| | starting point | why it matters |
|---|---|---|
| phrases coloured | about 5 of ~25 | edits confined to one or two phrases are not reliably audible in the render |
| notes altered | 10–18 | a wholesale re-mapping changes the vocal's character enough to displace the arrangement |
| accidentals | 10–18, net of the transcript's own | corpus: median 0.38 per 100 notes, p90 2.4 |
| register shift per section | within ±2 semitones | a lifted vocal makes the guitars read as a bed |
| augmented second per coloured phrase | appears once, entered and left by step | the interval is the maqam's signature |
| unchosen phrases | zero pitch changes | contrast is what makes five cadences audible |

Deviation is allowed and must be visible: the numbers go in `decisions.json` and
the report. A silent overrun is a defect; a justified one is a judgement call.

## 5. Report

`CHANGES.txt`, one block per score, every number copied from `maqam validate`:
`notes_in, notes_out, notes_removed, notes_pitched, notes_pitched_pct,
accidentals, bars, sections, phrases_total, phrases_coloured, coloured_bars,
plain_phrases_untouched, rhythm_kept, register_shift, maqam_figures`.

`decisions.json` alongside it: the phrase list from step 5 with reasons, the edit
as applied, any deviation from the measured table with its justification, and the
anomalies you decided in step 4.

## 6. Where your knowledge is welcome, and where it is not

The corpus is **diatonic**: 0.83 accidentals per 100 notes, median track 0.38,
74 of 177 tracks with none, 0 of 177 Hijaz-shaped even where the production
prompt says "Maqam Hijaz". arabmaqamrock is a minor rock band with maqam accents,
not a maqam ensemble.

- **Welcome:** recognising a jins gesture, choosing a plausible cadence figure,
  hearing whether a line wants to settle or climb, knowing what makes Hijaz
  recognisable as Hijaz.
- **Not welcome:** general maqam theory as a rule for how much colour belongs in
  this material, or a scale as a target to re-map onto. The spec's budget and the
  corpus's measured distributions outrank a remembered convention.

No web research during the edit. Everything needed is in the repo.

## 7. Known traps

- Writing the score first and checking it afterwards. Check at every step instead.
- Counting bars or notes by hand, then reporting the hand count. Use the tool.
- Merging repeated notes without respecting bar lines: this produces notes that
  straddle a bar, and every later count is off by one.
- Accidental state persisting within a bar, or a natural that a previous
  accidental made necessary and a later bar must clear.
- Trying to express a neutral second or quarter tone. `^/2` does not parse; use the
  nearest semitone.
- "Fixing" the transcript's own accidentals. If the singer sang it, it stays; it
  counts against the budget instead.
