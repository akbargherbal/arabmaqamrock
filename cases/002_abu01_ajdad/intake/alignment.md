# Alignment index — case 002

**Tool:** `yue2-karaoke-align/scripts/a1_align_run.py` (forced CTC; the lyrics
are known, so it cannot invent words).
**Model:** `akbargherbal/wav2vec2-large-xlsr-53-arabic` @
`4ca1c9c6ac85d839eebc530ec85b6a89f697e4e8`.
**Run:** 2026-11-14, CPU (this laptop), Demucs `htdemucs` stem.
**Result:** 141/141 words, coverage 1.0, no overlaps, 30 line cues.
**Source of truth:** `words.json` (this folder).

## Cost

| step | wall |
|---|---:|
| Demucs `htdemucs` on CPU (229 s song) | 59 s |
| forced alignment + model load | ~55 s |
| **total** | **~2 min** |

## Command

Staged layout: `<name>_<seed>.wav` + `prompts/<name>_lyrics.txt`.

```bash
cd ~/Jupyter_Notebooks/OpenCode/yue2-karaoke-align
.venv/bin/python scripts/a1_align_run.py \
  --run-dir /tmp/opencode/abu01/runsrc \
  --out /tmp/opencode/abu01/a1 \
  --device cpu --sep-device cpu
```

The vocal stem is cached at
`yue2-karaoke-align/work/stems/htdemucs/abu01_a01_3285212580/vocals.wav`
(44.1 kHz; resample to 48 kHz before any comp).

## The line and its neighbours (chorus 1)

```
line 13: هَوَانُ الْآبَاءِ وَالْأَجْدَادِ...

  هَوَانُ        106.289 – 107.009
  الْآبَاءِ      107.109 – 108.989
  وَالْأَجْدَادِ  109.149 – 111.329   ← target
```

There is **no silent gap** before the word: `الْآبَاءِ` ends 108.989 and the
target starts 109.149. The only quiet point is a dip in the vocal at
**108.88–108.92** (−31 dB, band 200–3500 Hz), i.e. the release of the previous
word. That dip is the natural start for a comp.

### The dip is a glottal closure — and the mix hides it

Measured at 5 ms resolution on the **Demucs vocal stem**:

| time | RMS (vocal) | what it is |
|---|---:|---|
| 108.80 – 108.84 | −16 to −20 dB | end of the long `ā` of `الْآبَاءِ` |
| **108.85 – 108.92** | **−26 → −35 → −27 dB** | **70 ms break in voicing** (low spectral flatness → closure, not a breath) |
| 108.93 – 109.12 | −18 dB @ ≈220 Hz | the final kasra `/i/` of `الْآبَاءِ` |
| 109.15 → | f0 241 → 264 Hz | the `wā` of `وَالْأَجْدَادِ` |

In the **full mix**, the same 70 ms only drops to ≈−24 dB (instruments fill it),
which is why the ear hears the hamza and the waw as almost merged.

**Consequence for the method:** the comp replaces the **vocal stem only**, so a
70 ms vocal break is a valid cut even if the mix is not quiet. Judge boundaries
on the stem, not on the mix — the mix's instrumental bed is there precisely to
mask the join.

**Three start strategies (see `../review/gaps.html`):**

- **B (default): start 109.10**, at the `wā`. The previous word stays 100 %
  original, but the join is between two voiced sounds (`/i/ → /w/`) and must be
  short and level-matched.
- **D (fallback): start 106.20**, in the 400 ms gap before `هَوَانُ`, and
  re-sing the whole line. Both joins are clean, but it replaces two correct
  words.
- **A (last resort): start 108.88**, inside the closure. The only silent start,
  but it begins inside `الْآبَاءِ` (a partial-word comp).

**A third candidate, C (107.05), is withdrawn:** the chart shows continuous
energy there. The alignment "gap" between `هَوَانُ` and `الْآبَاءِ` is not
acoustic.

## The word ends before the note ends

The aligner's end (111.329) is the **lexical** end, not the musical end.

| marker | time | evidence (Demucs vocal stem) |
|---|---:|---|
| word start (`وَا…`) | 109.15 | f0 jumps 221 → 241 → 264 Hz |
| lexical end (end of the final `ī`) | **≈111.33** | aligner + line end |
| sustained tail | 111.33 – 112.55 | f0 steady **≈246–248 Hz**, RMS −17 to −18 dB |
| release / reverb | 112.55 – 113.2 | RMS falls −20 → −45 dB |
| next sung event | 118.27 | Verse 2 line 14 |

So there are **three candidate "ends"**: 111.33 (word), 112.55 (note body),
113.16 (your first guess — end of the reverb). Only 112.70 is a safe join: the
note is over, the reverb is decaying.

The exact onset of the defective final `د` was **not** measured (it needs
formants or a character-level CTC). It sits between the second `دَا` and the
final `ī`, roughly 110.5–111.1. The unit does not need it: both units start
before the whole word.

## The second occurrence (chorus 2)

The chorus repeats, so the word occurs **twice**:

```
line 27: هَوَانُ الْآبَاءِ وَالْأَجْدَادِ...

  وَالْأَجْدَادِ  200.096 – 201.916   ← occurrence 2
  sustained tail  201.92 – ≈202.80
  next event      202.90 (bass, 124 Hz)
```

The two occurrences are musically parallel (same contour, same ≈247 Hz ending),
so if one is wrong the other probably is too — but the model can differ between
occurrences. **This must be checked by ear**, not assumed.

## Free reference: the same rhyme, presumably clean

The poem's rhyme is `-dī`; the same take sings it several times:

| word | time | note |
|---|---|---|
| `الْأَجْسَادِ` | **97.028 – 98.808** | two lines earlier, same chorus, same rhyme |
| `الْأَضْدَادِ` | 139.331 – 140.571 | Verse 2 |
| `الْآبَادِ` | 150.930 – 153.030 | Verse 2 |
| `سَوَادِ` | 175.994 – 177.995 | Verse 2 |

`الْأَجْسَادِ` is the best reference: same section, same singer, same phrase
shape, ~12 s before the defect. The review pack uses it as an A/B
(`review/04_*_correct_then_wrong.wav`).

## QA caveats

- 7 gaps > 2.0 s (max 6.94 s): orchestral intros/breaks, normal.
- The last word of the outro (`سَوَادِ`) spans 14.70 s — the aligner collapsed
  the final melisma. Far from this edit; ignore, but do not trust the last line's
  box.
- The box is an **index**, not a cut. The numbers used for the unit come from
  the f0/RMS measurements above.
