# ABC transcription — `abu01_a01_3285212580`

Full SheetSage2 transcription of the take (melody + chords + beats + structure),
copied here from `local_workspace/` so the case is self-contained.

## Provenance

| field | value |
|---|---|
| tool | `arabmaqamrock-transcribe/1` (`./transcribe.py`, `--full`) |
| model | `m-a-p/SheetSage2` @ `b83c3d79a6d98bcffaf8f9ed112c90aa887887bc` |
| device / dtype | CPU / fp32, 4 threads · **139.5 s** |
| created | 2026-11-14T14:49:29Z |
| source WAV | `abu01_a01_3285212580.wav` · sha256 `30860a08…` · 229.079 s |
| `score.abc` | 2338 bytes · sha256 `8784150fc2252c3ad4bd3c5b9d058355f58fca73636dea7d895938ccf4856912` |
| key / meter / tempo | A minor · 4/4 · ♩=79 |

## What is here

| file | what it is |
|---|---|
| `score.abc` | full score, vocal + instrumental melodies with chord symbols |
| `melody_vocal.lab` / `.mid` | **sung vocal melody as (start, end, midi) notes** — the useful one here |
| `melody_instrumental.lab` / `.mid`, `melody_full.lab`, `melody.mid`, `transcription.mid` | accompaniment / combined melody |
| `beat.lab`, `downbeat.lab`, `rhythm_events.lab`, `notation/song_beats.txt` | beat grid |
| `chord.lab`, `notation/song_chords.txt`, `chords.mid` | chords |
| `structure.lab`, `notation/song_structures.txt` | sections (chorus 1 = 87.98–112.17) |
| `key.lab`, `notation/song_keys.txt` | key |
| `events.json` / `.tsv`, `tokens.json` / `.txt`, `playback.json`, `result.json`, `meta.json` | raw model output and player data |

## How it is used in this case — and how it is not

**It tells you where to look.** It flagged that the target word does not end
where the forced-alignment box says: the vocal melody shows a note
**110.73–112.17** while the word box ends at **111.329**. That is what
triggered the measurement on the stem.

**It is a melody yardstick, not a ruler.** Around the target:

```
109.89 – 110.31   C4
110.31 – 110.52   B3
110.73 – 112.17   B3   (the long note)
```

- Its **note onset at 110.31** matched the measured syllable boundary at
  **110.30** (10 ms) — good.
- Its **note end at 112.17** is **0.34 s early** against the measured release at
  **112.51** — bad, and exactly where holds are weakest.

So: use it to (a) reject a candidate that sings the word on different notes,
(b) know where a note starts. **Never use its end times as cut points.**

Regenerate with:

```bash
./transcribe.py work/abu01_a01_3285212580.wav --out-dir work/abc --full --device cpu
```
