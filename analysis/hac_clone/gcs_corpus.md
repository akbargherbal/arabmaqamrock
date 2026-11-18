# last_bayt_repeat — offline test corpus

**Purpose:** re-test alignment, counting and karaoke ideas on these takes
**without a GPU and without re-running Demucs**. This is not audio for listening
or mixing; it is the input the models see.

Built 2026-11-18 from `github.com/akbargherbal/arabmaqamrock`. See
`MANIFEST.json` for per-file sha256 and per-track metadata.

## Why FLAC at 16 kHz mono

Demucs wrote 44.1 kHz stereo PCM (~4.3 GB for these 86 stems). Every consumer in
this project — faster-whisper, XLSR-53 CTC, the karaoke aligner — resamples to
16 kHz mono, so the extra bandwidth buys nothing. Measured on one 334 s stem:

| form | size | ratio |
|---|---:|---:|
| WAV 44.1 kHz stereo PCM-16 | 58.9 MB | 100 % |
| FLAC 44.1 kHz stereo | 29.3 MB | 50 % |
| **FLAC 16 kHz mono** (this corpus) | **7.1 MB** | **12 %** |

The 44.1 kHz stereo stems are regenerable in ~10 GPU-minutes:
`python3 -m demucs --two-stems vocals -n htdemucs -d cuda -o work/stems/<batch> <run>/*.mp3`
(the source MP3s live in the run directories under `runs/`). Because of that, this
corpus keeps only the 16 kHz mono form.

## Layout

```
stems16k/<batch>/<track>/{vocals,no_vocals}.flac   16 kHz mono, duration preserved
karaoke/<A|B>/*.words.json                         karaoke word alignments of the 16 HAC takes
karaoke/reference/hac_0{1,2}.words.json            the two Suno reference alignments
asr/asr_<BATCH>_<model>.csv                        per-track repeat counts (the arbiter)
asr/cache/<batch>/<track>.<model>.words.0.55.json  raw Whisper words + timestamps
ctc/ctc_summary.csv, ctc/<batch>_<track>.json      CTC placements, spans, scores, stability
ctc/ctc_OFF.csv                                    CTC calibration: known answer is 2, rule says 4-8
results/results.csv                                16 HAC takes: ASR/CTC counts + flags
results/controls_vs_hac.csv                        27 no-score takes vs the 16 HAC takes
results/clone_fit_*.csv                            pace / drift of each take vs the reference
```

## The two groups

| group | tracks | recipe | closing-bayt count |
|---|---:|---|---|
| `A`, `B` | 16 | `cot=full` + external ABC, cap 9000 | 3–7 by CTC, 1–7 by ASR |
| `OFF`, `WOLF`, `KURD` | 27 | `cot=off`, no score | 1–3 by ASR, 21/27 exactly 2 |

`A` and `B` are the same songs, seeds and weights with different lyric line
breaks. `B/<track>` is often the closer clone (see `results/clone_fit_*.csv`).

## Known properties (use them as test fixtures)

- **Text says 2, audio says 7:** `A/hac_01_1114111` — the case that breaks
  monotone forced alignment. `karaoke/A/hac_01_1114111.words.json` shows what the
  aligner does with it: 139/139 words, coverage 0.974, no loud gap, and four
  words stretched 4–14× (one bayt copy spans 43.9 s instead of 15.9).
- **Ground truth for a clean case:** `karaoke/reference/hac_01.words.json` — same
  text, same 139 words, two renditions, no stretching.
- **A counter that over-counts:** run any CTC idea against `ctc/ctc_OFF.csv`
  before trusting it; the true answer there is 2.

## Reading it

```python
import soundfile as sf, json
y, sr = sf.read("stems16k/A/hac_01_1114111/vocals.flac")   # 16000 Hz, mono
words = json.load(open("karaoke/A/hac_01_1114111.words.json"))["words"]
```

Nothing here needs Demucs, librosa's resampler, or a GPU.
