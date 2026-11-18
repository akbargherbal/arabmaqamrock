# Cloning the reference (`manifests/harith_hac_clone.json`)

**Goal.** Reproduce the two Suno "happy accident" takes: duration 5:34 / 5:49
(±5 s), the closing bayt **twice**, everything else already good.

The reference alignments are at `/content/hac_01.words.json` and
`/content/hac_02.words.json` (139 words each, same lyric text as our renders).
`compare_reference.py` scores any take against them.

## What the reference actually does

| | `hac_01` | `hac_02` |
|---|---:|---:|
| duration | 334.94 s | 349.87 s |
| words | 139 | 139 |
| closing bayt #1 | 291.1 s | 302.4 s |
| closing bayt #2 | 307.9 s | 315.9 s |
| final word `عَمْيَاءُ` | 321.5 → **334.9** | 329.0 → 339.4 |
| after the last word | 0 s (held to the end) | 10.5 s |

So the reference reaches the closing bayt **at 87 % of the track**, sings it
twice in ~16 s, and then *holds the last syllable* for 13 s. It never re-starts
the line. Our takes reach it at ~75 % and then re-start it.

## The gap is pace, not length

`compare_reference.py` fits `our_start ≈ pace × ref_start + offset` on the first
85 % of the words (both alignments have the same 139 words in the same order).
All 16 existing takes, with their ASR/CTC counts and duration error:

| take | pace | ASR | CTC | dur | Δdur vs target |
|---|---:|---:|---:|---:|---:|
| A/`hac_02_3337333` | **0.999** | 2 | 3 | 353.0 | +4.0 |
| B/`hac_01_1117111` | **0.955** | 3 | 4 | 335.2 | **+1.2** |
| B/`hac_01_1212121` | 0.917 | 2 | 4 | 319.4 | −14.6 |
| B/`hac_02_3331333` | 0.909 | 3 | 4 | 335.2 | −13.8 |
| A/`hac_01_1117111` | 0.904 | 4 | 4 | 327.8 | −6.2 |
| A/`hac_01_1212121` | 0.901 | 4 | 6 | 336.8 | +2.8 |
| B/`hac_01_1114111` | 0.899 | 5 | 5 | 334.8 | +0.8 |
| B/`hac_01_1616161` | 0.880 | 4 | 6 | 360.0 | +26.0 |
| A/`hac_01_1616161` | 0.875 | 5 | 6 | 329.8 | −4.2 |
| A/`hac_01_1114111` | 0.865 | 7 | 7 | 334.1 | +0.1 |
| B/`hac_02_7772777` | 0.862 | 1 | 5 | 328.6 | −20.4 |
| A/`hac_02_3331333` | 0.848 | 3 | 5 | 322.6 | −26.4 |
| A/`hac_02_7772777` | 0.832 | 4 | 6 | 322.4 | −26.6 |
| B/`hac_02_3337333` | 0.830 | 5 | 6 | 338.4 | −10.6 |
| A/`hac_02_7774777` | 0.817 | 4 | 5 | 318.9 | −30.1 |
| B/`hac_02_7774777` | 0.815 | 2 | 6 | 330.8 | −18.2 |

**`r(pace, CTC count) = −0.71`** across the 16. The faster the delivery, the more
renditions: the model runs out of text early and pads. That is the same
mechanism the control batches showed (`../last_bayt_repeat/` §3.2), now measured
against the reference itself.

Two consequences:

* **Do not trim the score to the "word budget".** The score is 337.2 / 350.3 s
  and the reference is 334.9 / 349.9 s — it is already the right length. Trimming
  would produce a 4:30 track and miss the target by a minute. `../scorelen/` is a
  mechanism probe only.
* **The figure of merit is pace.** A take at pace 0.86 cannot be fixed at the
  end; it has already spent 40 s too little on the lyrics.

## Existing best starting points

* `hac_01`: **B/`hac_01_1117111`** — 335.2 s (+1.2 vs target), pace 0.955,
  3–4 renditions. Same seed and settings as A/`hac_01_1117111` (pace 0.904), so
  **the B lyric line breaks alone buy ~5 pace points** (0.904 → 0.955); on seed
  1114111 the same change buys 3.4 (0.865 → 0.899). The matrix below starts from
  the B text.
* `hac_02`: **A/`hac_02_3337333`** — 353.0 s (+4.0), pace 0.999, 2–3 renditions.

And the most useful detail in the whole set — where that take puts the bayt:

| | rendition onsets (s) |
|---|---|
| reference `hac_01` | 291.1, 307.9 |
| B/`hac_01_1117111` | 258.3, 273.6, 290.9, 303.1 |
| A/`hac_01_1114111` | 250.2, 260.2, 274.0, 283.5, 296.1, 305.0, 314.0 |

B/`1117111` sings the final chorus **twice in exactly the reference's place**
(290.9 vs 291.1; 303.1 vs 307.9) and inserts one extra pair *before* it. So the
model is not confused about where the ending is — it volunteers a repeat of the
closing line earlier in the chorus. Suppressing that inserted pair is the whole
job, which is what the penalty window is for.

## The lever that targets the repeat

`semantic_repetition_penalty` looks back `penalty_window` semantic frames; the
default is **50 frames = 2 s** at 25 frames/s, while one bayt rendition is
**~262 frames (10.5 s)**. When the model starts the next rendition, the previous
one is already outside the penalty's memory — the loop is not penalised at all,
by construction.

`semantic_penalty_window` is now a first-class manifest field (added 2026-11-18;
the runtime always supported it). 250–450 makes the penalty see the previous
line.

## Matrix (10 takes, ~65 min on a T4)

| id | change vs base | tests |
|---|---|---|
| `cl_base` | B text, seed 1117111, nothing else | reproduces B/`1117111` (335.2 s, pace 0.955, 3–4 renditions) **plus** the tag, i.e. it is also the `[End]` test |
| `cl_rw300` | `semantic_penalty_window: 300` (12 s) | repeat memory long enough to see one line |
| `cl_rw450` | `=450` (18 s) | memory spanning two lines |
| `cl_rw300_rp125` | window 300 + `repetition_penalty 1.25` | harder penalty, same memory |
| `cl_tight` | `T .85 / p .9 / k 60` | score adherence / pace without the penalty |
| `cl_tight_rw300` | both | likely winner combination |
| `cl_g10` | `guidance_scale: 1.0` | does less style/lyrics pressure let the model linger on the score (slow down)? |
| `cl2_base` | `hac_02`, A text, seed 3337333 | reproduces the best `hac_02` take |
| `cl2_rw300` | + window 300 | does the fix transfer |
| `cl2_tight_rw300` | + tight sampling | combination on the second song |

All keep `cot=full`, 8 steps, LoRA `a015` (AR 0.75 / NAR 1.0), `cap=9000`. The
cap is deliberately loose: it is not the duration knob, and a cap below 8432
frames (337.2 s) would cut the score itself.

## Run

```bash
python3 generate.py manifests/harith_hac_clone.json --out-dir out/hac_clone
```

`--dry-run` passes; `--limit 7` runs only the `hac_01` half.

## Score every take against the reference

```bash
python3 -m demucs --two-stems vocals -n htdemucs -d cuda -o work/stems/CLONE out/hac_clone/*.mp3
# karaoke alignment -> words.json for each stem (yue2-karaoke-align a0_align.py)
python3 analysis/hac_clone/compare_reference.py \
    --reference /content/hac_01.words.json \
    --candidates work/karaoke_clone --glob '*hac_01*' \
    --out work/clone_fit_new.csv
```

Success criteria, in order:

1. **duration** 329–339 s (`hac_01`) / 344–354 s (`hac_02`);
2. **closing bayt = 2, at ~291 and ~308 s** (±3 s) — not just the right count, the
   right place;
3. **pace ≥ 0.95** — the clone must reach the closing bayt at ~87 % of the
   track, not 75 %.

## Every take ends with `[End]`

All ten lyric sheets now close with `[End]`. Nothing in the pipeline parses it —
`generate.py` passes the lyric text verbatim, and the only tag vocabulary in the
code is the instrumental LoRA's
`intro/verse/pre-chorus/chorus/bridge/outro` list (`generate.py:517`) — so it is
a house convention, not a documented control. It was added because it is free,
not because it is proven.

The control comes for free from the archive: **B/`hac_01_1117111` has identical
settings and no tag**. So:

| `cl_base` vs archived B/`1117111` | conclusion |
|---|---|
| byte-identical | the model ignores `[End]`; the tag is decorative |
| same duration/count, different audio | the tag perturbs sampling but not structure |
| fewer renditions or earlier end | the tag does something and belongs in every sheet |

Mechanically it cannot be the whole fix: the extra renditions in B/`1117111` sit
at 258 and 274 s, i.e. **before** the end, so an end marker has nothing to remove
there. At best it terminates the tail.

## Two failure modes to check first

1. **Silent no-op.** If the binary ignores `semantic_penalty_window`, `cl_rw300`
   will be byte-identical to `cl_base`. Check `request.options` in the take JSON
   and compare WAVs. Fallback: `EXTRA_REQUEST_OPTS="penalty_window=300"` on a
   manifest with no per-song controls.
2. **Melisma damage.** The penalty cannot tell a verbal repeat from a musical
   one (`docs/suno-generation-controls.md` D.5). `cl_rw450` may flatten the tarab
   ornaments — listen to the *early* verses, not only the ending.

## Assets: the corpus on GCS (the local stems were deleted)

The 44.1 kHz WAV stems were only ever a cache and are **gone from this VM**. The
portable copy — **16 kHz mono FLAC, 512 MB instead of 4.31 GB** — plus the
karaoke/ASR/CTC metadata and a per-file sha256 manifest is published at

```
gs://akbar-december-2024-backup/arabmaqamrock/datasets/last_bayt_repeat/
```

Layout and rationale: [`gcs_corpus.md`](gcs_corpus.md); rebuild with
`python3 analysis/hac_clone/build_gcs_corpus.py`.

Fetch the stems back (no GPU, no Demucs):

```bash
gsutil -m cp -r gs://akbar-december-2024-backup/arabmaqamrock/datasets/last_bayt_repeat/stems16k/* work/stems16k/
```

`stems16k/<batch>/<track>/{vocals,no_vocals}.flac`; control folders keep the
`_<seed>` suffix, the HAC ones already end in it.

Still local (2 MB, same content also under the GCS prefix above):
`work/karaoke/{A,B}/*.words.json`, `work/asr_*.csv` + `work/asr_cache*/`,
`work/ctc/`, `work/results_*.csv`.

**What is missing:** the lyrics *with the repetitions written out*. The sheets in
`manifests/harith_hac_{A,B}.json` list the closing bayt twice (correct for the
reference, wrong for our renders, which sing it 3–7 times). The onsets needed to
build the expanded text are in `work/ctc/<batch>_<track>.json` and
`work/asr_{A,B}_small.csv`, but no `*_expanded.txt` exists yet.

**Not retained:** the source MP3s (they live in the run directories on GCS) and
the 44.1 kHz stereo stems (regenerable with one Demucs run, ~10 GPU-minutes, if
anything ever needs full bandwidth again).
