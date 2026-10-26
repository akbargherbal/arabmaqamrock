# arabmaqamrock — ABC melody EDIT guide

Paste this into the conversation, then the transcription, then the lyrics.
Return **two** scores (`CLEAN` and `MID`) and one change report per score.

---

## 0. The job, in one image

You are given a manuscript and asked to line-edit it.

- **The premise** is the key, the maqam, the tempo, the meter, the section order,
  the lyric setting. Do not touch it.
- **The plot** is what each phrase does: where it rises, where it falls, where it
  ends. Do not touch it.
- **The scenes** are the phrases themselves. You may sharpen one, and only if it
  is on your list.
- **The prose** is the individual notes inside a phrase. This is the only place
  where you are allowed to rewrite.

An editor who rewrites the plot has written a different book. The manuscript is
the band's. You are improving the sentences, not the story.

This matters more here than in ordinary editing, because a melody that leaves
its own contour stops being *this* song. The thing you must protect is not the
notes — it is the shape the band already committed to.

## 1. The house rule: the corpus is the target, not the defect

`arabmaqamrock` is a **diatonic minor** band. Measured across 177 reference
tracks:

- 7 pitch classes per track, in practice the natural-minor set;
- **0.83 explicit accidentals per 100 notes** overall;
- median track: **0.38** per 100; 90th percentile: **2.4** per 100;
- **74 of 177** tracks contain no accidental at all;
- **0 of 177** are Hijaz-shaped, even the ones whose production prompt says
  "Maqam Hijaz".

So in this material the maqam is not the language. It is an **accent**. The band
plays minor rock; the maqam shows up in a handful of gestures, at moments where
the singer leans on a degree.

### Calibration: two failed attempts bracket your job

Both were made from the same kind of transcript as the one in front of you.

- One attempt coloured **two cadences**: 7–9 notes out of ~370. Musically correct,
  and inaudible. The listener could not tell it from the plain take.
- One attempt rebuilt **every phrase** on the maqam's scale: ~150 altered notes,
  40% of the melody, replaced the original contour. Immediately recognisable as
  Arabic, and the band disappeared behind it — the arrangement went small, the
  riff stopped carrying the song, and it no longer sounded like this band.

You are writing the version between those two. Not a gentler full reading —
a *different placement* of a similar idea: fewer notes than the second attempt,
placed where they are actually heard.

The reason the first attempt failed is placement, not quantity. Maqam is heard at
the cadence. An altered degree in the middle of a phrase is a passing colour; an
altered degree at the end of a phrase is a statement. Spend the budget at the
ends.

## 2. What you receive

1. **The transcript** — SheetSage2 output. The thing you are editing.
2. **The lyrics** — line order, stress, section names.
3. **The maqam and key**, if supplied.
4. Optionally the production prompt the take came from.

Be clear-eyed about the transcript. It is machine output with known defects,
measured across the 177 reference transcripts:

| defect | how common |
|---|---|
| two voices (`Vocal` + `Ins`) | all of them |
| mid-piece `M:` changes | median 5 per track |
| bars that do not add up | median 16 per track |
| octave slips (a note an octave off, then back) | common |
| echoed / duplicated notes | common |

None of that is music. Fixing it costs no fidelity.

### The style text, if you are given one

It will look like: `arabmaqamrock, classical arabic, melismatic, belting,
symphonic metal, rhythm guitar, epic, vocal-forward mix, Maqam Hijaz,
mood: "yearning, deep sorrow, lamenting"`.

**The first word is not a genre.** `arabmaqamrock` is a LoRA trigger — a label
for one fine-tuned sound. Do not interpret it from the token itself; its meaning
is exactly this, and only this:

> A grand, solemn symphonic-rock ballad driven by a commanding, deeply resonant
> Arabic male vocal delivering ornate, hymn-like melodies over heavy guitars and
> sweeping orchestral strings.

Read it for three things only:

- **The idiom.** "classical arabic", "maqam ..." — which tradition's grammar to
  write in, and that the grammar matters more than novelty.
- **The emotional register.** "yearning, deep sorrow, lamenting" — a lament
  descends and settles; it does not leap around brightly.
- **The formal shape.** "call and response" — let the verse and the chorus answer
  each other rather than being variations of one phrase.

Ignore the rest. "rhythm guitar", "symphonic metal", "audiophile",
"vocal-forward mix", "crisp consonants", "belting" describe a *production*, not
a melody. The ABC carries no production.

One word to discount explicitly: **"melismatic"**. The measured setting is about
1.3 notes per syllable — one note per syllable, almost always. Read it as a
description of the performance, not an instruction to write runs.

## 3. Non-negotiables — the form ledger

These are not preferences. If any of them changes, the take breaks.

- **One voice.** Delete every `Ins` line. Output `Vocal` only.
- **One meter.** The transcript's dominant meter, declared once. Never a second
  `M:` in the music. `4/4` and `2/4` are both fine; do not convert between them.
- **Every bar complete.** Durations must sum exactly to the meter.
- **Keep the transcript's `Q:`** unless it is obviously wrong.
- **Keep the key.** Minor only.
- **Keep the section layout** — same sections, same order, same count.
- **Keep the note count** within 2% of the input. You may only *remove* echo
  notes (see §4); never add a note, never split one.
- **Keep every onset and duration** you are not explicitly removing as an echo.
- **Keep every rest.** Do not shorten a rest to place a note in it.
- **End on the tonic** of the key you declared.

ABC mechanics: bars end with `|`; `Z` is a whole bar of rest, `z4` is a beat of
rest; no chord symbols, no tuplets `(3`, no grace notes `{}`, no `[]` chords, no
`P:`/`R:` fields, no lyrics inside the ABC. `% intro`, `% verse`, `% chorus`,
`% interlude`, `% outro` mark sections.

## 4. Pass 1 — `CLEAN`

Mechanical repair only. **No pitch changes**, with two named exceptions:

1. **Octave slips.** A note that jumps 12+ semitones from its neighbours and
   straight back is an error; put it in the octave of its neighbours.
2. **The final note.** If the piece does not end on the tonic, move that one note.
   Report it.

Everything else:

1. **Delete the `Ins` voice.** All of it.
2. **Collapse to one meter**, re-barring into the dominant meter.
3. **Complete every bar.** Fill a short bar with a rest; split or tie an overlong
   one.
4. **Remove echoes.** The same pitch repeating inside a sixteenth, or a note
   repeated with identical duration, is a transcriber artefact. Collapse to one
   note and extend it. Only collapse runs of three or more; a doubled note is
   often a syllable.
5. **Do not delete the transcript's own accidentals.** If the singer sang a C♯,
   it stays. It counts against your budget in §5.

`CLEAN` is the control. It must sound like the input.

## 5. Pass 2 — `MID`: the colour ledger

This is the whole edit. It is a **budget**, not a licence.

### 5.1 Make the list first

1. Walk the score and number the phrases. A new phrase starts after a rest of at
   least one beat, or at a section marker. Most scores here have **25 ± 2**
   phrases.
2. For each phrase record: section, final note, whether it rises or falls, mean
   pitch.
3. Choose **5 phrases** (`MID` may use 4–6; never more). They must satisfy:
   - at least one in a verse, one at the end of a pre-chorus, one in a chorus,
     one in the last third of the song;
   - at most one per section, except a verse may take two;
   - chosen phrases at least 3 apart;
   - prefer phrases that already end on the tonic (D) or its fifth (A).
4. Write the list down before you edit. It is a contract.

**Every pitch you change must fall inside a phrase on that list.** If a change
would land outside it, it is not yours to make — undo it. At the end you will
report how many of the unchosen phrases have zero pitch changes; the answer must
be *all of them*.

### 5.2 The budget

| thing | value |
|---|---|
| phrases coloured | 5 (4–6) |
| of total phrases | about 1 in 5 |
| notes altered | **10–18** |
| as a share of notes | 3–5% |
| as a rate | 2.5–4.5 per 100 notes |
| accidentals written | 10–18 |

A 370-note, 25-phrase score should come out with about 5 coloured phrases and 15
altered notes. That is the 90th percentile of the corpus's own accidental rate —
the top of what this band does, not the top of what a maqam can do. If the
transcript already contains accidentals, **they count against the budget.**

### 5.3 What to write inside a chosen phrase

Only the **last 2–4 notes** of the phrase may change.

- The phrase must still end on D (the qarar) or A (its fifth). If it already does,
  keep it. If not, move that one note and nothing else.
- Inside those 2–4 notes, place the maqam's characteristic step **once**: the
  augmented second, E♭–F♯ or F♯–E♭. Enter it by step and leave it by step. The
  note after it should be D, G or A.
- No leap into or out of an altered note.
- At most one altered note per beat.
- The last note of the phrase is longer than the ones before it, or tied to a
  rest. Give the cadence weight; do not leave it clipped.

That is the whole technique: the phrase arrives, the augmented second marks the
arrival, the line settles. Nothing else in the phrase moves.

### 5.4 Everything else stays plain

The other ~20 phrases are the band's. Leave them diatonic and untouched.

This is not caution, it is contrast. Five coloured cadences are audible because
twenty plain phrases surround them. Colour every phrase and the listener hears a
scale, not a song — which is exactly what the failed attempt did.

## 6. Forbidden operations

Each of these was performed in the failed attempt. Each is now out of scope. If
you catch yourself doing one, stop and undo it.

- **Re-mapping the melody onto the maqam's scale ladder.** Not "move each phrase
  onto the new degrees". No global substitution of any kind.
- **Rebuilding phrases one by one.** You are not composing the melody, you are
  editing five cadences.
- **Composing new material** — bridges, pickups, connective phrases, extensions.
- **Transposing a section**, or the chorus.
- **Raising the tessitura.** See §7.
- **Deleting the transcript's own accidentals**, or "correcting" a note that is
  outside the scale but was actually sung.
- **Making every section visit a jins.** A section may be entirely plain.
- **Varying repeated phrases so they differ from each other.** If the transcript
  repeats a chorus, the repeat stays. Sameness is the song.
- **Smoothing leaps or filling rests** to make the line prettier.

## 7. Why the vocal must not get higher

The band is the loud thing. The vocal is the soloist, and it sits where the
arrangement left room for it.

Lifting the tessitura makes the arrangement recede: the listener's attention goes
to the top of the spectrum, the guitars read as a bed instead of a wall, and the
track goes small and quiet even though nothing in the mix changed. That is what
happened in the failed attempt — the choruses were pushed 4 semitones above the
verses.

The reference corpus does raise the chorus, but by **about 2.4 semitones**, and
by contour rather than by transposition. So:

- each section's mean pitch stays within **±2 semitones** of the input's mean for
  that section;
- lift in the chorus comes from the *shape* — climb inside the phrase, then
  settle — not from moving the whole line up;
- keep the rests. The holes are where the band answers.

## 8. Check before you answer

**Hard** — the take breaks if these fail:

1. Exactly one voice, `Vocal`; the `Ins` voice is gone.
2. Exactly one `M:`.
3. Every bar sums exactly to the meter.
4. Note count within 2% of the input.
5. Section order and section count match the input.
6. No microtonal syntax anywhere.
7. No chord symbols, tuplets, grace notes, or embedded lyrics.
8. The piece ends on the tonic.
9. `notes_pitched` ≤ 8% of `notes_in` (for `MID`).
10. Every changed note lies inside a phrase on your §5.1 list.

**Soft** — report these, and fix if you can:

11. Coloured phrases: 4–6.
12. Accidentals written: 10–18.
13. The augmented second appears once per coloured phrase, and resolves by step.
14. Unchosen phrases have zero pitch changes.
15. No two coloured phrases are adjacent.
16. Each section's mean pitch within ±2 semitones of the input's.

If the maqam is not identifiable from your five cadences, do not add a sixth and
do not spread the colour wider. Make the five land harder: put the augmented
second on a longer note, and make sure the note before it is approached by step.

## 9. Change report — after each ABC block

Fill in counted numbers, not estimates.

```
CHANGES (CLEAN)
notes_in:            <Vocal notes in the input>
notes_out:           <notes in your score>
notes_removed:       <deleted as echoes>
notes_pitched:       <should be 0, or 1 for the final tonic>
accidentals:         <^ or _ you introduced>
bars_in / bars_out:
sections_in / sections_out:
notes:               <anything you deliberately left alone>

CHANGES (MID)
phrases_total:       <phrases you counted>
phrases_coloured:    <must be 4-6>
coloured_bars:       <bar numbers, one per coloured phrase>
plain_phrases_untouched: <unchosen phrases with zero pitch changes> / <total unchosen>
notes_in / notes_out:
notes_pitched:       <must be <= 8% of notes_in>
notes_pitched_pct:
accidentals:         <must be 10-18>
rhythm_kept:         <notes whose onset and duration are unchanged>
register_shift:      <per section, semitones vs input>
maqam_figures:       <bar, and the two degrees forming the augmented second>
notes:               <what you deliberately left plain>
```

If `kept_pct` is below 95%, you changed more than cadences. The form ledger in
§3 is not a suggestion — go back and restore the onsets.

## 10. Reference values (context, not targets)

Measured from the 177 reference tracks; median with the 10th–90th percentile.
These describe the vibe. Use them to tell an error from a style choice.

| property | median | p10–p90 |
|---|---|---|
| lyric line length | 10 beats (4/4) / 6 beats (2/4) | 4–14 |
| notes per beat | 1.53 | 1.01–1.93 |
| note values an eighth or shorter | 92% | 72–97% |
| silence, share of sung span | 30% | 24–38% |
| note starts off the beat | 64% | 50–74% |
| descending phrases | 62% | 46–73% |
| step motion (≤2 semitones) | 85% | 81–88% |
| leaps ≥ 5 semitones | 4.2% | 2.5–5.9% |
| repeated notes | 33% | 29–38% |
| register | F4–A5, centre D5 | — |
| distinct pitch classes | 7 | 7–8 |
| explicit accidentals per 100 notes | 0.38 | 0.0–2.4 |

The last row is the one that governs this edit. The band lives at the bottom of
that range. Your budget in §5.2 is the top of it. Do not exceed it, however much
clearer the maqam would be.
