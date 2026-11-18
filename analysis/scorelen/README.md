# Score-length experiment (`manifests/harith_hac_scorelen.json`)

> **Goal update, 2026-11-18.** The real target is copying a reference take at
> 5:34 / 5:49, and the transcribed scores are already 337.2 / 350.3 s — so
> trimming the score is **not** the fix for the clone; it would make a 4:30
> track. This manifest is kept as a *mechanism probe* only. The goal-aligned
> matrix is in [`../hac_clone/README.md`](../hac_clone/README.md).

Six takes, one song (`hac_01`), one seed each, built to test **one** claim from
`../last_bayt_repeat/REPORT.md`: the last-bayt loop is the model filling a score
that asks for more sung time than the lyrics can supply.

Nothing here runs on a low-end VM — `generate.py` needs the generation binary and
enough VRAM for a 9000-token take. The manifest and the trimmed score are ready;
the counts are measured afterwards with the tools we already have.

## Design

| id | change vs `sl_b0_base` | what it isolates |
|---|---|---|
| `sl_b0_base` | none (full score, seed 1114111) | determinism check against the existing A/`hac_01_1114111` take |
| `sl_b1_short` | score trimmed 337.2 s → **269.7 s** (sung vocal 285.5 → 219.3 s) | **score length** (the hypothesis) |
| `sl_b1_short_s2` | as B1, seed 1117111 | is a change in count seed noise? |
| `sl_b2_sampling` | `semantic_temperature 0.8`, `top_p 0.9`, `top_k 60` | decoding tightness |
| `sl_b3_lora_ar05` | `lora_ar_scale 0.5` | adapter is off-distribution for `cot=full` |
| `sl_b4_cap` | `cap 8432` (= score frames, no headroom) | does capping cure anything, or only truncate? |

Everything else is byte-identical to the HAC batch: `cot=full`, `guidance_scale
1.5`, 8 ODE steps, LoRA `a015` (AR 0.75 / NAR 1.0), same style text, same lyrics,
`trigger: true`.

## The three numbers that are easy to confuse

| term | value for `hac_01` | where it comes from |
|---|---|---|
| `cap` (`semantic_max_tokens`) | 9000 = **360 s** | a hard ceiling in 25 Hz frames; `duration_cap.py` would fit 616 letters to ≈7600 |
| p95 length fit (`lyric_fit_s`) | **300 s** | `111.1 + 0.3126 × 616` — how long a song with these lyrics *usually* is |
| **word budget** | **228.5 s** | `0.371 s/letter × 616`, the pace of the one take whose score matched its lyrics (`abc_cfg15`) |

The experiment trims to the **word budget**, not to the cap. That is why B1 keeps
`cap=9000`: the cap was never the binding constraint (15/16 HAC takes ended by
EOS well below it), and changing it in B1 would confound the test.

## The trimmed score

`plumbing/trim_score.py` cuts whole voice-aligned steps from the top until the
total is under `--target-s`, pads nothing, and appends two rest bars so both
voices end together.

```bash
python3 plumbing/trim_score.py scores/harith_hat/hat_01.abc \
    --target-s 270 --out scores/harith_hat/hat_01_short270.abc
# duration 337.2 -> 269.7 s, sung vocal 285.5 -> 219.3 s, 41 sung blocks (was 53)
```

219.3 s is ~4 % *under* the 228.5 s word budget, i.e. on the safe side: after
trimming there is no melody left that needs words.

## Run

On a box that can generate:

```bash
python3 generate.py manifests/harith_hac_scorelen.json --out-dir out/scorelen
```

`--dry-run` is validated here already (6 tracks, ~39 min projected on a T4).

## Measure

For every take, the same three instruments used in `../last_bayt_repeat/`:

```bash
# 1. vocal stem
python3 -m demucs --two-stems vocals -n htdemucs -d cuda -o work/stems/SCORELEN out/scorelen/*.mp3

# 2. repeat count (ASR is the arbiter; CTC only for onsets)
cd analysis/last_bayt_repeat
python3 count_last_bayt_words.py --run-dir ../../work/asr_scorelen --model small \
    --device cuda --compute-type float16 --cache-dir ../../work/asr_cache/scorelen \
    --out ../../work/asr_SCORELEN_small.csv
```

3. **score adherence** (optional but recommended): transcribe each render with
   `transcribe.py` (SheetSage2) and score it against the conditioning ABC with
   `analysis/vendor/abc_similarity.py` — the pipeline in
   `docs/plans/yt500-instrumental-abc-similarity.md` §0. For a 6-take batch that
   is ~5 minutes of GPU, and it gives a number for "how far off the score is the
   melody", which no counters can.

## How to read the result

| B1 result | conclusion |
|---|---|
| ≤ 2 renditions, adherence metrics improve | score surplus confirmed as the mechanism → trim scores to the word budget |
| still 4+, but adherence improves | the loop is not only a length effect; look at end-of-text handling (`[Outro]`, `[End]`) |
| unchanged | the score *length* is not the knob; the CoT prefix itself is enough to trigger the loop |

`sl_b0_base` must reproduce the existing take bit-for-bit (same seed and
settings, per `docs/suno-generation-controls.md` D.9). If it does not, stop: the
environment differs and the rest of the matrix is not comparable.
