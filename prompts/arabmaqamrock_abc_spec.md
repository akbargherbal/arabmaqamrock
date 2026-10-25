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
- `M:4/4` — four beats to the bar. **Never change `M:` mid-piece.** (99 of the
  177 reference tracks start in 4/4 and 78 in 2/4; the transcripts flip between
  them mid-song, which is a barline artifact rather than music. Choose 4/4 and
  stay in it.)
- `L:1/16` — the default note length. `A2` is two units, `A/2` is half a unit.
- `Q:1/4=110` — use the tempo you were given; 110 is the default for this style.
- `K:` — use the key you were given. If none, use `K:Dm`. Minor keys only.
- **One voice.** `V: Vocal` only. Do not write a second voice.
- `% intro`, `% verse`, `% chorus`, `% bridge`, `% outro` mark sections. These are
  comments; the renderer ignores them and humans need them.
- Bars end with `|`. **Every bar must be complete**: the durations in a bar must
  add up exactly to the meter. `Z` is a whole bar of rest; `z4` is a four-unit rest.
- No chord symbols in quotes, no tuplets `(3`, no grace notes `{}`, no `[]`
  chords, no `P:`/`R:` fields, no lyrics inside the ABC.

## 2. Length

Bar budget: `bars ≈ (111.1 + 0.3126 × L) × BPM / 240`, rounded to the nearest 4.

`L` is the number of **Arabic letters** in the lyrics: consonants *and* the long
vowels ا و ي. Do not count diacritics (fatha, damma, kasra, shadda, sukun,
tanwin), punctuation, spaces, section tags or Latin text. Count every written
line, including lines that repeat (a chorus written twice counts twice).

Worked example: 508 letters at 110 BPM → `(111.1 + 158.8) × 110 / 240` = 124 bars.
Reference tracks run `126` bars `[82–152]`.

Being 10% under or over is fine. Beyond that the renderer truncates or pads and
the lyrics stop lining up.

## 3. Form

One lyric line = one phrase = **4 bars** `[3–5]`.

Default section order, following the section tags in the lyrics:

```
intro (9 bars) → verse (18) → chorus (16) → interlude (8)
               → verse (18) → chorus (16) → outro (8)
```

These are the measured medians per section type: verse `18`, chorus `16`,
intro `9`, interlude `8`, bridge `8`, pre-chorus `8`.

Rules, in priority order:

1. **Follow the lyrics file.** Its `[Section]` tags define the sections and their
   order. The sequence above is only a default for missing tags. The per-section
   bar counts are **descriptions, not targets** — when a section's lines imply
   more bars than its median, the lines win.
2. **Lines under a section are sung in that section.** `[Intro]` and `[Outro]`
   often carry real lines; sing them. Rest only in sections with no lines.
3. **If a section's lines give fewer bars than its median, repeat the phrase** —
   the same lines, the same melody — using the repeat count that lands closest to
   the median, in whole phrases. Do not pad with silence. A two-line chorus
   (8 bars) is therefore sung twice, reaching exactly the 16-bar median, which is
   what the reference tracks do.
4. **Silence is bounded.** No more than 8 consecutive bars without a sung note,
   except across an intro, interlude or outro.

## 4. Register

- Lowest note: `F4` (MIDI 65) `[60–70]`
- Highest note: `A5` (MIDI 81) `[75–84]`
- Median pitch: `D5` (MIDI 74) `[72–75]`

ABC octaves: `C` is middle C (C4, MIDI 60), and `c` is the octave above (C5, 72).
So the range above is written **from `F` to `a`** — uppercase `F` at the bottom,
lowercase `a` at the top. Do not go below `F` or above `a`.

Stay inside that range. Do not sit in one octave for a whole section; move
through the range across the song and reserve the highest notes for the chorus.

## 5. Rhythm and density

- `3.8` notes per bar `[3.1–5.5]`
- `85%` of bars contain at least one sung note. That is a whole-song average and
  most of the silence falls in intros, interludes and outros. Inside a sung
  phrase do **not** drop a whole bar — use rests of one or two beats (`z4`,
  `z2`) instead.
- Typical note length: an eighth note (two `1/16` units). Use quarter notes for
  the last note of a line and for stressed syllables.
- `16.9` notes per lyric line `[14.8–19.3]`.

Do not fill every bar at the same density. The texture alternates: a few bars of
eighth notes, then a held note, then a short rest — a beat or two, not a whole
bar.

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
- The last note of every line is long — a quarter note or more. Never end a line
  on a short note.
- If a line has more than **18 syllables**, give it two 4-bar phrases (8 bars)
  and a cadence at the end of each.
- Stress falls where the syllable is long; keep the strong syllable of each foot
  on a strong beat (beat 1 or 3).

## 7. Melody

- **Step motion dominates**: `85%` of moves are two semitones or less.
- Leaps of a fifth or more: `4%`. Leaps of an octave or more: `1%`. A "large
  leap" below means more than 7 semitones; allow at most one per section.
- Repeated notes: `33%` of moves. Repetition is normal and welcome — do not
  decorate everything.
- End each phrase on the tonic or the fifth. End the final phrase on the tonic.
- Within a phrase: begin on the tonic, third or fifth; move to the phrase's
  highest or lowest point around bar 2–3; then resolve down to the cadence.
- Do not modulate. One key for the whole piece.

## 8. Verse and chorus

In 157 of 177 reference tracks the chorus sits higher than the verse — median
**+2.4 semitones** of mean pitch `[0 to +5.4]`.

- **Do not modulate.** Stay in the key. Raise the tessitura instead: aim for the
  chorus's highest note to be 2 to 4 semitones above the verse's highest note.
- Same lyrics in a repeated chorus → **the same melody, repeated**. Do not write
  a new tune for the second chorus.
- The chorus should contain the highest note of the song.
- The verse should be narrower and lower; the chorus wider and louder in contour,
  not in note count.

## 9. Originality

- Write a new melody. Do not reproduce, quote, or closely paraphrase any existing
  song, including any track in this style.
- You are deliberately not given reference scores. Do not ask for them, and do
  not reconstruct one from memory.
- Shared idioms (step motion, syllabic setting, a stepwise descent to the tonic)
  are the style. Shared note sequences are not: a run of eight or more identical
  pitches and rhythms is a copy, not a style.

## 10. Check before you answer

Verify each of these and fix the score if any fails:

1. Every bar's durations sum exactly to 4/4. No bar over or under.
2. `M:` appears once. No mid-piece meter changes.
3. Exactly one `V:` voice, declared once.
4. Total bars within ±10% of the budget from §2.
5. Every lyric line has a corresponding 4-bar phrase, in order, with no line
   skipped. If you repeated a section, the repeat carries the same lines.
6. Notes per line between 12 and 22.
7. At most one melisma per line, and only on a line's final syllable.
8. Highest note in the chorus is at or above the highest note in the verse.
9. List every interval larger than 7 semitones, with its bar number. There must
   be at most one per section. If you have more, rewrite one of them.
10. The piece ends on the tonic.
11. No chord symbols, tuplets, grace notes, or embedded lyrics.

If you cannot satisfy all eleven, say which one you broke and why, rather than
silently shipping it.

---

## Reference values (all measured from the 177 reference tracks)

| property | median | p10–p90 |
|---|---|---|
| bars per track | 126 | 82–152 |
| notes per bar | 3.8 | 3.1–5.5 |
| bars containing a note | 85% | 74–93% |
| notes per lyric line | 16.9 | 14.8–19.3 |
| notes per syllable | 1.28 | 1.16–1.41 |
| phrase length | 4 bars | 3–5 |
| notes per phrase | 16 | 14–20 |
| step motion (≤2 semitones) | 85% | 81–88% |
| leaps ≥ 5 semitones | 4.2% | 2.5–5.9% |
| leaps ≥ 8 semitones | 0.9% | 0.2–2.2% |
| repeated notes | 33% | 29–38% |
| chorus − verse pitch | +2.4 st | 0.0–5.4 |
| register | F4–A5, centre D5 | — |
| section bars: verse / chorus / intro / interlude / bridge | 18 / 16 / 9 / 8 / 8 | — |
