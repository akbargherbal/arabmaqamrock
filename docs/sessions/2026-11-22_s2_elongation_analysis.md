# Session — Ibn Zuraiq song 03: score vs. generated elongation (2026-11-22)

**Status:** open. All four takes are generated. The next session compares
SheetSage2 transcripts of those takes with the original ABC score to locate the
~37 s that separates the score's written length from the generated 4:40.

## Run

| | |
|---|---|
| GCS run | `gs://akbar-december-2024-backup/arabmaqamrock/runs/20261122-102016_ibn_zuraiq_song_03_s2_a015/` |
| manifest | `manifests/ibn_zuraiq_song_03_s2_a015.json` |
| original score | `scores/llm_score_writer/s2_ibn_zuraiq_song_03/s2_score.abc` |
| takes in the run | 4 (the manifest says `repeat: 3`; it was changed to 4 on the run machine) |
| cap | **7000** tokens (`quantile: 0.95`, 536 Arabic letters) |
| all takes | exit 0, `wav_duration_s = 279.9986666666667`, `truncated: true` (`duration_heuristic`) |

Seeds and measured tempo (beat tracking on the MP3s):

| Take | Seed | BPM | Duration |
|---:|---|---:|---:|
| 1 | `3123930954` | 73.83 | 280.0 s |
| 2 | `2834984256` | 76.00 | 280.0 s |
| 3 | `2102509235` | 76.00 | 280.0 s |
| 4 | `1523879993` | 73.83 | 280.0 s |

## What is established

- The score header is `Q:1/4=73`; it has **74 bars** and parses to **243.29 s**
  (4:03).
- The generated tempo is **73.8–76.0 BPM**, i.e. equal to or slightly faster
  than the score. The output was **not** time-stretched down to ~63 BPM.
- At those tempos, 280 s implies roughly **86–89 bars**: about **12–15 extra
  bars** beyond the score's 74.
- The exact 4:40 is arithmetic: `7000 / 25 = 280 s`. All four takes hit
  `emitted_tokens=7000` and `semantic.truncated=1`.
- The cut is not in a quiet tail: the last 20 s have the highest RMS in the
  analysed take (~0.223), so the cap cut active music.

## Hypothesis to test with the transcripts

Where did the extra 12–15 bars enter?

1. an extended intro or outro;
2. a repeated verse/chorus (structural insertion);
3. a slower phrase realization inside the score's sections (more rests, longer
   notes, melisma);
4. added instrumental interludes;
5. a combination (for example, a repeated chorus plus a longer outro).

## Next-session inputs (the user will provide)

SheetSage2 outputs for the four takes, produced on the other machine with
`./transcribe.sh` (see `docs/transcription.md`). Per take:

- `score.abc`
- `melody_vocal.mid` / `melody_instrumental.mid`
- `beat.lab`, `downbeat.lab`, `structure.lab`, `chord.lab`, `key.lab`
- `events.json` / `events.tsv`
- `meta.json`

The expected parent directory is `transcripts/<take>/`.

## Comparison plan

1. Parse the original ABC and each transcript (Vocal voice, `%` sections,
   chord annotations). Reuse the parser in `datasets/five_stars/measure/abc.py`
   where possible.
2. Build a section table for each: section name, start/end bar, bars, seconds.
   Compare against the original's 74 bars at 73 BPM:
   - intro 10 bars (4 instrumental + 6 vocal)
   - verse 1 24 bars
   - chorus 6 bars
   - verse 2 20 bars
   - chorus 6 bars
   - outro 8 bars
   The transcript's own `%` section names are SheetSage2 texture labels, not
   lyric sections: take 4 labels 80–210 s (verse 2) as "chorus". Anchor the
   lyric sections with the karaoke word timings, not the transcript's `%`
   markers.
3. Align the original per-bar chord sequence (`Dm`, `Bb`, `Gm`, `C`) with the
   transcript's `chord.lab` / per-bar chords using DTW or a simple
   insert-delete-substitute alignment. Runs of inserted bars show repeats or
   added sections; substitutions show harmonic drift.
4. Compare vocal density per section: notes per bar, rest share, median note
   duration, and repeated melodic motifs (pitch-interval k-grams). This
   separates "same sections, slower delivery" from "more sections/bars".
5. Report which sections grew, by how many bars/seconds, and whether the added
   material is repeated existing material or new material.
6. Caveat: SheetSage2 is an estimate, not ground truth. Use time-based section
   boundaries and pitch-class normalisation; do not require exact bar-for-bar
   agreement with the original notation.

## Follow-up experiment

The score is the length contract. `generate.py` now derives a scored song's cap
from the score, not from the lyrics fit: **score length + 3%**. For this score
that is `ceil(243.3 × 1.03 × 25) = 6265` tokens (251 s); `quantile` is ignored
when a score is present, and an explicit `cap` above the 3% margin is rejected.

Before re-rendering, the score must end with a **full-bar rest in both voices**
(`Z|`) after the final tonic cadence. The YuE2 native dialect ends every music
line with a plain `|`; `]` is not part of it and the runtime parser rejects it.
The skill's checker enforces the final rest as a hard check.

Re-run the same score and style with `cap: 6265` and the same seed. If the song
ends before the cap, the cut was the cap; if it still hits 6265, the model is
vamping past the score — more room will make a longer vamp, not a natural
ending. The 3% margin (7.3 s) is the guardrail; the natural `cot=off` takes of
the same song ended at 234.8–237.8 s, while the ABC-conditioned takes ran to
280.0 s (+15.2%).
