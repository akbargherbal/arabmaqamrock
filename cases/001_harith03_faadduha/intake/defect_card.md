# Defect card — case 001

One card, one occurrence. Gate A: this card must be right before anything is
rendered. Gate B (the unit) is separate.

| field | value |
|---|---|
| **song / take** | Harith 03, take `810750224` |
| **section / line** | Verse 2, line 14 (the verse's first line) |
| **lyric** | `أَيَّمَا خُطَّةٍ أَرَدْتُمْ فَأَدُّوهَا إِلَيْنَا` |
| **target word** | `فَأَدُّوهَا` |
| **occurrence** | 1 of 1 (word 65 of 115) |
| **alignment box** | 126.790 – 129.180 s (the A1 127.810 end is mid-`هَا`; the note ends ≈129.15) |
| **heard** | `فَأَدُوهَا` — a single `د`, the shaddah is collapsed |
| **target** | `fa-ʾad-dū-hā` — a real geminate: longer closure, then the release |
| **class** | consonant / gemination (shaddah) |
| **note after** | **keep** — the continuous note (`هَا` 415→465 + `إِلَيْنَا` 465→368) is correct |
| **must not change** | `أَرَدْتُمْ`, `هَا`, `إِلَيْنَا`, the 311→355→370→415→465 Hz contour, the instrumental, the timing |

## What only the ear can confirm

1. **`heard`** — is it a single `د` (degemination), or is the `د` itself wrong
   in some other way (place, voicing, a vowel inserted)? The plan assumes
   degemination; the fix differs if it is a different consonant.
2. **`note_after`** — `هَا` and `إِلَيْنَا` are **not separate**: the 465 Hz note
   runs through both and descends to ≈368 Hz at 129.10. Is that whole
   continuous note correct? If yes, A keeps it (join at 127.72). If re-singing
   the phrase is more natural, P (join at 129.18, in the breath). This is why
   there is no "cut between the words" option. **Judge it on the full line**
   (guide §8, rule 10), not on a 0.4 s clip.
3. **`must_not_change`** — anything else in the line that is precious and
   should be named now (a breath, a guitar phrase under the word, a backing
   vocal).

## Why the word box is not the cut

The aligner is an index. Its ends drift at note offsets and releases:

- `words.json` says the word ends 127.810 and `إِلَيْنَا` starts 128.130 —
  the end is mid-`هَا`;
- the character-level CTC says the word ends ≈127.61 — but that region is still
  /u/ (F1≈420), so it is before the `هَا`;
- the vocal f0 + formants say `هَا` starts ≈127.76 (/a/, F1≈835), and
  `إِلَيْنَا` begins ≈128.13 (front vowel, F2≈1850) on the **same note**;
- the note continues through both words and descends 427→368 Hz to ≈129.15,
  then a breath. There is no gap to cut in at 128.13 or 128.87.

The ear approves a unit in the **audio**, not the box. The proposed numbers are
in `../spec/repair_spec.draft.json`.

## Objective reference (not a verdict)

Same take, same singer, a **correct** `دّ` in `حُدِّثْتُمُوهُ`:

- Verse 2: 176.006 – 177.796 s, `دّ` ≈176.4 s;
- Outro: 214.257 – 216.477 s.

The closure before the release is ≈100–120 ms there, vs ≈55 ms in the target.
That is consistent with the ear's report, but the stems and reverb make the
number fuzzy. Use it to rank candidates, not to accept one.

## Card status

- [ ] `heard` confirmed
- [ ] `note_after` confirmed
- [ ] `must_not_change` confirmed
- [ ] no second defect in this take (or it is added to this case)
