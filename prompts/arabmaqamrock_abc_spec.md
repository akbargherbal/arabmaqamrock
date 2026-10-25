# arabmaqamrock — ABC melody specification

Paste this into the conversation, then paste the lyrics. Produce one ABC score.

---

## 0. What you are producing, and what you are not

You are writing **one melody**, encoded as ABC text, to be sung to the supplied
lyrics.

The track's sound — genre, instrumentation, production, vocal character, and the
maqam flavour — is **already fixed elsewhere** in the pipeline (a style text and a
LoRA adapter). Your score does not carry any of it. Do not try to describe,
imply, or encode production, mood, maqam, or arrangement. Your score is the
melody the singer will follow.

Everything below was measured from 177 reference tracks in this style. Numbers in
`code` are the measured median, with the 10th–90th percentile range in brackets.
Where a rule and a number disagree, the rule wins.

**The numbers are in beats, not bars.** The reference corpus mixes 2/4 and 4/4
transcriptions, so "bars" mean different durations in different tracks. A beat is
a quarter note and means the same thing everywhere. This is the single most
important correction in this document: an earlier version counted bars and made
every lyric line 60% too long, which is what turns a moving melody into a slow
one.

## 1. Format — hard rules

One ABC block. No prose before or after it.

```
X:1
T:
M:4/4
L:1/16
Q:1/4=110
V: Vocal clef=treble name="Vocal Melody" snm="Vocal"
K:Dm
% intro
Z8|
...
```

- `X:1`, `T:` may be empty or the song title.
- `M:4/4` — four beats to the bar. **Never change `M:` mid-piece.**
- `L:1/16` — the default note length. `A2` is two units, `A/2` is half a unit.
  Remember: `A4` = a quarter note = one beat.
- `Q:1/4=110` — use the tempo you were given; 110 is the default for this style.
- `K:` — use the key you were given. If none, use `K:Dm`. Minor keys only.
- **One voice.** `V: Vocal` only. Do not write a second voice.
- `% intro`, `% verse`, `% chorus`, `% bridge`, `% outro` mark sections. These are
  comments; the renderer ignores them and humans need them.
- Bars end with `|`. **Every bar must be complete**: the durations in a bar must
  add up exactly to the meter. `Z` is a whole bar of rest; `z4` is a one-beat rest.
- No chord symbols in quotes, no tuplets `(3`, no grace notes `{}`, no `[]`
  chords, no `P:`/`R:` fields, no lyrics inside the ABC.

## 2. Length

Bar budget: `bars ≈ (111.1 + 0.3126 × L) × BPM / 240`, rounded to the nearest 4.

`L` is the number of **Arabic letters** in the lyrics: consonants *and* the long
vowels ا و ي. Do not count diacritics (fatha, damma, kasra, shadda, sukun,
tanwin), punctuation, spaces, section tags or Latin text. Count every written
line, including lines that repeat (a chorus written twice counts twice).

Worked example: 508 letters at 110 BPM → `(111.1 + 158.8) × 110 / 240` = 124 bars.

Being 10% under or over is fine. Beyond that the renderer truncates or pads and
the lyrics stop lining up.

## 3. Form

**One lyric line = one phrase = about 10 beats** `[7–14]`. That is two and a half
bars of 4/4 — a line usually starts mid-bar and ends mid-bar. Do not force one
line into four bars; that is the single most common way to make this style sound
slow and sentimental.

Default section order, following the section tags in the lyrics:

```
intro → verse → chorus → interlude → verse → chorus → outro
```

Rules, in priority order:

1. **Follow the lyrics file.** Its `[Section]` tags define the sections and their
   order. The sequence above is only a default for missing tags.
2. **Lines under a section are sung in that section.** `[Intro]` and `[Outro]`
   often carry real lines; sing them. Rest only in sections with no lines.
3. **Do not pad a section with silence.** If a section's lines give fewer bars
   than the section needs, repeat the phrase — the same lines, the same melody.
   A two-line chorus (about 20 beats) sung three times fills a chorus section.
4. **Silence is bounded.** No more than 8 consecutive beats without a sung note,
   except across an intro, interlude or outro.

## 4. Register

- Lowest note: `F4` (MIDI 65) `[60–70]`
- Highest note: `A5` (MIDI 81) `[75–84]`
- Median pitch: `D5` (MIDI 74) `[72–75]`

ABC octaves: `C` is middle C (C4, MIDI 60), and `c` is the octave above (C5, 72).
So the range above is written **from `F` to `a`** — uppercase `F` at the bottom,
lowercase `a` at the top. Do not go below `F` or above `a`.

**Use the range, do not live in it.** A melody that stays inside one octave for a
whole section is too narrow — that reads as crooning. Each phrase should cover
**5 to 9 semitones**, and the song as a whole must reach both ends of the range.

## 5. Rhythm — this is where the style lives

- **`1.5` notes per beat** `[1.0–1.9]` across the whole song.
- **`~16` notes per lyric line** `[14–19]` — that is roughly **2 notes per beat
  inside a phrase**, so most notes are short.
- Note values: **`92%` are an eighth note or shorter** (0.5 beat or less). Only
  `8%` are a quarter note, and a note longer than a beat is rare — one or two per
  line, at the end. If most of your notes are quarters, the melody is wrong.
- **Silence is `30%` of the sung span** `[24–38%]`. That is a lot, and it is the
  difference between singing and crooning. Every line ends with a rest of **1 to
  3 beats** `[1–5.5]` before the next line begins.
- **Note starts are spread across the grid**, not stacked on the beat:

  | where the note starts | share |
  |---|---:|
  | exactly on a beat | `36%` |
  | on the "and" (half-beat offbeat) | `36%` |
  | on a sixteenth (¼ or ¾ of a beat) | `28%` |

  A third of your note starts must be off the beat. A melody with every note on
  the beat is a hymn, not this style.

## 6. Setting the lyrics

- **Counting syllables.** A syllable is one consonant carrying a short vowel
  mark — fatha `َ`, damma `ُ`, kasra `ِ` — or a tanwin (`ً ٌ ٍ`). A consonant with
  sukun `ْ` carries none. Long vowels (ا و ي) belong to the syllable of the vowel
  before them and do not add a count.
- `1.28` notes per syllable `[1.16–1.41]`: **one note per syllable**, almost
  always.
- Melisma is optional. Writing none lands at ~1.0–1.2 notes per syllable, which
  is correct for this style. If you use it: at most **one per line**, on the
  final syllable, never inside a word.
- The last note of every line is long — a quarter note or more — and is followed
  by a rest. Never end a line on a short note.
- If a line has more than **18 syllables**, give it two phrases and a cadence at
  the end of each.
- Stress falls where the syllable is long; keep the strong syllable of each foot
  on a strong beat.

## 7. Melody

- **Step motion dominates**: `85%` of moves are two semitones or less.
- Leaps of a fifth or more: `4%`. Leaps of an octave or more: `1%`. Allow at most
  one large leap (more than 7 semitones) per section.
- Repeated notes: `33%` of moves. Repetition within a phrase is normal.
- End each phrase on the tonic or the fifth. End the final phrase on the tonic.
- Do not modulate. One key for the whole piece.

**Phrase shape — the correction that matters most.** In the reference tracks,
`62%` of phrases **descend**: they open high in the phrase and settle down to the
cadence. `17%` rise, `16%` arch (rise then fall), and almost none are flat.

Do **not** give every phrase the same shape. Write a mix, weighted to descending:

- about two in three phrases: start on a high note (the phrase's peak) and work
  downward to the cadence;
- about one in three: start low, climb to a peak late in the phrase, then cadence.

A melody where all phrases rise and fall the same way is the sound of a
machine writing a melody. Vary the shape.

## 8. Phrase-to-phrase variation

In the reference tracks, **consecutive phrases share almost nothing** — measured
at `5%` overlap of melodic material `[0–9%]`. Each new line is a new idea, not a
variation of the last.

- **No two adjacent phrases may share a run of four or more notes.** Measured as
  the shared share of three-interval patterns between neighbouring phrases; it
  must stay under about a third.
- Repeat a phrase **only** when the lyrics repeat it — that is, in a chorus that
  comes back. A repeated chorus carries the same melody, exactly.
- Verses may share a contour family but must not share their note sequence.
- Over the whole song, `62%` of short note-sequences recur at least once. That is
  the repetition you get from returning choruses and repeated verse melodies —
  not from looping the same bar.

## 9. Verse and chorus

In 157 of 177 reference tracks the chorus sits higher than the verse — median
**+2.4 semitones** of mean pitch `[0 to +5.4]`.

- **Do not modulate.** Stay in the key. Raise the tessitura instead: aim for the
  chorus's highest note to be 2 to 4 semitones above the verse's highest note.
- Same lyrics in a repeated chorus → **the same melody, repeated**. Do not write
  a new tune for the second chorus.
- The chorus should contain the highest note of the song.
- The verse should be narrower and lower; the chorus wider and louder in contour,
  not in note count.

## 10. Originality

- Write a new melody. Do not reproduce, quote, or closely paraphrase any existing
  song, including any track in this style.
- You are deliberately not given reference scores. Do not ask for them, and do
  not reconstruct one from memory.
- Shared idioms (step motion, syllabic setting, a stepwise descent to the tonic)
  are the style. Shared note sequences are not: a run of eight or more identical
  pitches and rhythms is a copy, not a style.

## 11. Check before you answer

Verify each of these and fix the score if any fails:

1. Every bar's durations sum exactly to 4/4. No bar over or under.
2. `M:` appears once. No mid-piece meter changes.
3. Exactly one `V:` voice, declared once.
4. Total bars within ±10% of the budget from §2.
5. Every lyric line has a corresponding phrase, in order, with no line skipped.
   If you repeated a section, the repeat carries the same lines.
6. Notes per line between 12 and 22.
7. **Each line occupies 7 to 14 beats.** Count them. Not 16, not 20.
8. **At least 25% of the sung span is rests.** Add up the `z` durations and the
   `Z` bars and divide by the total beats.
9. **At least 25% of note starts are off the beat** (an eighth or sixteenth
   offbeat). If almost everything lands on beats 1, 2, 3, 4, rewrite the rhythm.
10. **Adjacent lines share little melodic material** — at most a third of their
    three-interval patterns. Compare each line's intervals with the line before
    it.
11. **At least 40% of lines descend** — open high, cadence low.
12. **The melody spans at least 12 semitones** between its low 5% and high 5% of
    notes. Staying inside one octave for the whole song is too narrow.
13. At most one melisma per line, and only on a line's final syllable.
14. Highest note in the chorus is at or above the highest note in the verse.
15. The piece ends on the tonic.
16. No chord symbols, tuplets, grace notes, or embedded lyrics.

If you cannot satisfy all sixteen, say which one you broke and why, rather than
silently shipping it.

---

## Reference values (all measured from the 177 reference tracks)

| property | median | p10–p90 |
|---|---|---|
| bars per track (at 4/4, 110 BPM) | 126 | 82–152 |
| **lyric line length** | **10 beats** (4/4 tracks) / 6 beats (2/4 tracks) | 4.3–14.5 |
| notes per beat | 1.53 | 1.01–1.93 |
| notes per lyric line | 16.9 | 14–19 |
| notes per syllable | 1.28 | 1.16–1.41 |
| note values an eighth or shorter | 92% | 72–97% |
| note values a quarter or longer | 8% | 3–28% |
| **silence, share of sung span** | **30%** | 24–38% |
| rest after each line | 2.5 beats | 1–5.5 |
| note starts on a beat | 36% | 26–50% |
| note starts on the half-beat | 36% | 26–50% |
| note starts on a sixteenth | 28% | 1–45% |
| **descending phrases** | **62%** | 46–73% |
| rising phrases | 17% | 7–30% |
| arch phrases | 16% | 5–26% |
| **adjacent-phrase melodic overlap** | **5%** | 0–9% |
| step motion (≤2 semitones) | 85% | 81–88% |
| leaps ≥ 5 semitones | 4.2% | 2.5–5.9% |
| leaps ≥ 8 semitones | 0.9% | 0.2–2.2% |
| repeated notes | 33% | 29–38% |
| chorus − verse pitch | +2.4 st | 0.0–5.4 |
| register | F4–A5, centre D5 | — |
