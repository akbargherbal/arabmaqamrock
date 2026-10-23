# Alignment index — how the word was found

**Tool:** `yue2-karaoke-align/scripts/a1_align_run.py` (forced CTC; the lyrics
are known, so it cannot invent words).
**Model:** `akbargherbal/wav2vec2-large-xlsr-53-arabic` @
`4ca1c9c6ac85d839eebc530ec85b6a89f697e4e8`.
**Run:** 2026-10-23T10:54:10Z, CPU (20 threads), Demucs `htdemucs` stem.
**Result:** 115/115 words, coverage 0.943, on/off 2.32, intro ok, 26 line cues.
**Source of truth:** `words.json` (this folder).

## Command

```bash
# staged input: <name>_<seed>.wav + prompts/<name>_lyrics.txt
cd ~/Jupyter_Notebooks/OpenCode/yue2-karaoke-align
.venv/bin/python scripts/a1_align_run.py \
  --run-dir /tmp/opencode/repair_intake/runsrc \
  --out /tmp/opencode/repair_intake/a1 \
  --device cpu --sep-device cpu
```

Cost on this machine: Demucs 61 s, align 55 s, model load ~2 s. The vocal stem
is cached at
`yue2-karaoke-align/work/stems/htdemucs/03-…_810750224/vocals.wav`.

## The line and its neighbours

```
line 14: أَيَّمَا خُطَّةٍ أَرَدْتُمْ فَأَدُّوهَا إِلَيْنَا

word 62  أَيَّمَا      123.130 – 123.990
word 63  خُطَّةٍ      124.430 – 125.190
word 64  أَرَدْتُمْ    125.470 – 126.430
word 65  فَأَدُّوهَا   126.790 – 127.810   ← target (end is mid-هَا)
word 66  إِلَيْنَا     128.130 – 128.870   (end is early: the note runs to ≈129.15)
word 67  تَمْشِي      129.990 – 130.630
```

Character-level CTC on the vocal stem (window 125.0–129.4, same model) places
the word more tightly:

```
ف 126.788   َ 126.848   أ 127.009   َ 127.089
د 127.250   ُ 127.311   ّ 127.331   و 127.351
ه 127.471   َ 127.532   ا 127.592
إِلَيْنَا from 127.692
```

The `ّ` token is placed immediately after the first `د` — i.e. the model heard a
single consonantal position, which is the defect.

**But the char-level end is wrong too.** It puts `ه` at 127.47 and `ا` at 127.59.
Those frames are still /u/ (LPC: F1≈421 / F2≈1091 at 127.45). The real `هَا` is
the rising 415→465 Hz note at 127.76–≈128.10 (F1≈835 / F2≈1300 → /a/).
`إِلَيْنَا` starts ≈128.13, where the formants move to a front vowel
(F1≈505 / F2≈1850) — but on the **same 465 Hz note**. The note then descends
427→368 Hz from 128.85 to ≈129.15, followed by a breath and `تَمْشِي` at
129.99. So the acoustic phrase end is ≈129.15, not the aligner's 128.87. The
boundaries used for the unit come from f0 + formants, not from either aligner
(`../record.md`).

## Caveats (do not skip)

1. **Alignment ends drift.** At a held note, the word end can be 0.1–0.6 s late
   (reference-run finding). Here the two aligners disagree by 0.5 s on the
   target's end, and both are wrong: the whole-song end is mid-`هَا`, the local
   end is before it. The unit was measured on the vocal stem with f0 + LPC
   formants. This is guide §2.2 ("text timing is not musical timing") in
   practice.
2. **One word elsewhere collapses.** `الْعَلَاءُو` (word 105, line 23) spans
   24.3 s — a known aligner failure over a sparse passage. It is nowhere near
   this edit, but it means the whole-song `words.json` must not be used as a
   downstream-QC ruler. Re-align **locally** around 122–130 s after the comp.
3. **Same take, different stem.** Local Demucs ran at 44.1 kHz; the original WAV
   is 48 kHz. The comp must use one consistent stem pair (original + candidate)
   resampled once, and the outside-diff check is on the 48 kHz int16 deliverable.
   On Colab, regenerate both stems with the same Demucs so they are comparable.
4. **The prompt's line breaks are not the user's line breaks.** The prompt has
   the whole line as one line; the singer still makes a 0.36 s gap before the
   target. The lyric file is the ground truth for what was asked; the audio is
   the ground truth for what was sung.
