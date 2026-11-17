# Last-bayt repetition in the HAC batches

**Batches:** `20261117-082924_harith_hac_a` (A) and `20261117-093512_harith_hac_b` (B)
**Symptom:** the final chorus bayt (`أَتَلَهَّى بِهَا الْهَوَاجِرَ … بَلِيَّةٌ عَمْيَاءُ`) is sung many times instead of the two written in the lyric sheet.
**Scope:** diagnosis only. No production code was changed, no generation was run on this VM.

---

## 1. Verdict

Every one of the 16 takes repeats the last bayt. The estimated count is **3–9 renditions where the lyric sheet asks for 2** (mean 5.6, median 5.5); 12/16 are at 5× or more.

The evidence points at the **length mismatch between the external ABC score and the lyric text**, not at seeds, sampler settings, CFG, cap, or the A/B lyric re-formatting:

* A and B use the **same model, LoRA, seeds, cap, sampler and CFG**; they differ only in lyric line breaks and a few spelling variants — and **both repeat**. Lyric formatting is therefore not the cause.
* All 8 distinct seeds repeat, so it is not a bad seed.
* Sampler/CFG are identical to the previous clean batch (`cot=off`, no ABC), so they are not sufficient on their own.
* The score asks for **+57 s (HAC01) / +84 s (HAC02)** of sung vocal beyond what the 616-letter lyric supplies at the model's natural pace. The model fills the extra vocal time by looping the last bayt once it runs out of words. Forced alignment shows the final word absorbing up to **23.1 s** of unaligned audio — the signature of repeats the aligner cannot place.
* `cap=9000` is not the trigger: only 1/16 takes actually hit it. It merely permits the overrun (and truncates that one take instead of curing the loop).

Because no generation controls could be run here (low-end VM, GPU work deferred on request), the causal statement is inferential. Section 7 lists the one-variable matrix that would confirm it on a GPU box.

---

## 2. Data and method

| What | Where |
|---|---|
| Audio, per-track metadata, logs | `gs://…/runs/20261117-082924_harith_hac_a/`, `…/20261117-093512_harith_hac_b/` (downloaded to `/tmp/opencode/hacA|hacB`) |
| Karaoke forced alignments (`words.json`) | `…/karaoke/` (downloaded to `/tmp/opencode/karaokeA|karaokeB`) |
| Score / lyric fit metrics | `analysis/last_bayt_repeat/score_gap.csv` (`analyze_score_gap.py`) |
| Ground-truth ASR count | `analysis/last_bayt_repeat/count_last_bayt.py` |

Three independent measurements were used:

1. **ASR occurrence counting** (`count_last_bayt.py`) — faster-whisper Arabic transcription of the tail, Arabic normalisation, fuzzy matching of the last bayt, NMS de-duplication. Validated on `hac_01_1114111` only.
2. **Forced-alignment geometry** (`measure_alignment.py`, new) — reads the karaoke `words.json`, measures the final chorus span and the duration of the last aligned word. Cheap, whole-batch, CPU-only.
3. **Score-vs-lyrics budget** (`analyze_score_gap.py`) — sung-vocal seconds encoded in the ABC vs the lyric-fit duration.

### 2.1 ASR validation

`hac_01_1114111.mp3` (334.08 s), reference = last sung block:

```
occurrences: 7
times: 250.74 261.74 272.74 282.74 296.02 307.70 315.62
mean occurrence: 10.97 s
strict >=85 score: 3 (250.74, 261.74, 272.74)
```

The `small` model and an independent `medium` pass both returned **7**. The user heard **6**. The disputed item is the last one at 315.62–328.62 s, a lower-confidence cadential reprise (score 77.6). Treat this track as **6–7**, and treat the mean rendition length (10.97 s) as the calibration constant for the cheap proxy.

### 2.2 Why the alignment cannot count directly

The forced aligner must place every lyric word exactly once, so it cannot emit extra words for repeated audio. When the model loops, the aligner stretches the surrounding cues instead:

* the final chorus block becomes far longer than two renditions;
* the final word often absorbs many seconds (`عَمْيَاءُ` = 11.9 s on A/1114111, 23.1 s on B/3337333, vs a 0.7 s median word).

This gives a good *duration* proxy but not an exact count:

```
est_count = round( final_chorus_span / 10.97 )
```

Calibration is exact on the validated track: `74.26 / 10.97 = 6.77 → 7`. Treat other rows as **±1**; use them to rank takes, not to certify a number.

---

## 3. Results

`analysis/last_bayt_repeat/results.csv` (16 rows). `est` is the alignment proxy; `exp` is the number of renditions actually written in the lyric sheet; `span` is the final-chorus sung span; `last` is the final word's aligned duration.

| batch | track | dur (s) | cap | trunc | span (s) | est | exp | excess | last word (s) | ASR |
|---|---|---:|---:|:---:|---:|---:|---:|---:|---:|---:|
| A | hac_01_1114111 | 334.1 | 9000 | no | 74.3 | 7 | 2 | +5 | 11.88 | **7** |
| A | hac_01_1117111 | 327.8 | 9000 | no | 68.6 | 6 | 2 | +4 | 17.98 | – |
| A | hac_01_1212121 | 336.8 | 9000 | no | 65.8 | 6 | 2 | +4 | 4.20 | – |
| A | hac_01_1616161 | 329.8 | 9000 | no | 69.7 | 6 | 2 | +4 | 16.36 | – |
| A | hac_02_3331333 | 322.6 | 9000 | no | 62.7 | 6 | 2 | +4 | 11.34 | – |
| A | hac_02_3337333 | 353.0 | 9000 | no | 34.9 | 3 | 2 | +1 | 17.48 | – |
| A | hac_02_7772777 | 322.4 | 9000 | no | 45.9 | 4 | 2 | +2 | 14.90 | – |
| A | hac_02_7774777 | 318.9 | 9000 | no | 53.7 | 5 | 2 | +3 | 11.86 | – |
| B | hac_01_1114111 | 334.8 | 9000 | no | 71.5 | 7 | 2 | +5 | 1.16 | – |
| B | hac_01_1117111 | 335.2 | 9000 | no | 59.7 | 5 | 2 | +3 | 14.90 | – |
| B | hac_01_1212121 | 319.4 | 9000 | no | 51.0 | 5 | 2 | +3 | 12.44 | – |
| B | hac_01_1616161 | 360.0 | 9000 | **yes** | 96.6 | 9 | 2 | +7 | 13.32 | – |
| B | hac_02_3331333 | 335.2 | 9000 | no | 39.3 | 4 | 2 | +2 | 4.30 | – |
| B | hac_02_3337333 | 338.4 | 9000 | no | 78.2 | 7 | 2 | +5 | 23.08 | – |
| B | hac_02_7772777 | 328.6 | 9000 | no | 44.4 | 4 | 2 | +2 | 11.64 | – |
| B | hac_02_7774777 | 330.8 | 9000 | no | 58.7 | 5 | 2 | +3 | 15.72 | – |

* Estimated count mean 5.56, median 5.5, range 3–9.
* 16/16 ≥ 3× the written renditions; 12/16 ≥ 5×.
* Only B/`hac_01_1616161` hit the 9000 cap (360.0 s) and was flagged `truncated` (duration heuristic).

---

## 4. What changed vs the clean batches

| Variable | Prior clean batches | HAC A | HAC B | Implicated? |
|---|---|---|---|---|
| `cot` | `off` (all takes) | `full` | `full` | **yes — leading** |
| external ABC | none | `hac_01.abc` / `hac_02.abc` | same | **yes — leading** |
| cap | 6500–8250 | 9000 | 9000 | enabler only (1/16 hit it) |
| guidance_scale | 1.5 | 1.5 | 1.5 | no (same as clean) |
| sampler | temp 1, top_p 0.95, top_k 100, rep 1.2, window 50 | identical | identical | no |
| ODE steps | 8 | 8 | 8 | no |
| LoRA | `a015` family, AR 0.75 | `a015`, AR 0.75 / NAR 1.0 | identical | not separated |
| lyrics | – | 23 sung lines | 45 sung lines (re-broken) | no (both fail) |
| seeds | various | 4 per song | **same 4 per song** | no (all 8 fail) |

Resolved HAC request line (all 16 tracks):

```
yue2.request seed=<seed> cot=full stop_after=audio guidance_scale=1.5
            num_inference_steps=8 context=24576 abc=provided nar_noise=generated
yue2.sampling.semantic temperature=1 top_p=0.95 top_k=100
                      repetition_penalty=1.2 penalty_window=50
                      min_tokens=200 max_tokens=9000
```

A/B are a clean natural control for lyric formatting: same seeds `1114111, 1117111, 1212121, 1616161` (hac_01) and `3331333, 3337333, 7772777, 7774777` (hac_02), same weights, cap, CFG and sampler; only line breaks and two spelling variants (`اليَوم`/`اليوم`, `القَنَّاص`/`القُنَّاص`) differ. Both batches repeat, so neither line breaks nor those spellings cause it.

### 4.1 The score/lyrics length mismatch

`score_gap.csv` decomposes the ABC into sung vs instrumental time:

| song | letters | score total | **sung vocal** | lyric fit (p95) | score − fit | sung s/letter | control s/letter |
|---|---:|---:|---:|---:|---:|---:|---:|
| hac_01 | 616 | 337.2 s | **285.5 s** | 300 s | **+37.2 s** | 0.463 | 0.371 |
| hac_02 | 616 | 350.3 s | **312.3 s** | 300 s | **+50.3 s** | 0.507 | 0.371 |
| `abc_cfg15` (control) | 557 | 233.9 s | 206.6 s | 290 s | **−56.1 s** | 0.371 | – |

At the control's natural pace (0.371 s/letter), 616 letters need **≈228.5 s** of singing:

* HAC01 score: 285.5 s → **+57.0 s** of vocal with no new words
* HAC02 score: 312.3 s → **+83.8 s** of vocal with no new words

The clean `abc_cfg15` control also had an external ABC and CFG 1.5, but its score is **shorter** than its lyric fit (−56.1 s), and it showed no repetition. That is the strongest natural evidence that *score length relative to lyrics* matters more than the mere presence of an ABC.

The score is also more vocally dense than the lyric sheet: `score_gap.csv` counts **53 sung vocal blocks for 23 lyric lines (2.3×)** in HAC01 and **31 for 23 (1.35×)** in HAC02, versus **0.7×** for the control. Even before matching seconds, the score encodes more vocal phrases than the lyrics have lines.

Mechanically: with an external `abc_file` the plan stage is skipped and the score is injected as a token prefix (`docs/suno-generation-controls.md` §D.11). The v3 adapter was trained with `cot=off`; a full, note-dense ABC is off-distribution (`docs/transcription.md`), and `guidance_scale` amplifies style/lyrics rather than ABC adherence. The model follows the score's *time* budget, exhausts the lyric text, and — having no more words — re-sings the last bayt.

### 4.2 Duration surplus vs repeat count

All 16 takes overrun the 300 s lyric fit by **+18.9 to +60.0 s**. Total duration is nevertheless a **poor predictor** of how many repeats occur:

| grouping | r(count, duration) |
|---|---:|
| all 16 | 0.33 |
| batch A only | −0.36 |
| batch B only | +0.78 |
| hac_01 only (8 takes) | +0.85 |
| hac_02 only (8 takes) | −0.31 |

Examples: A/`hac_02_3337333` is the longest A take (353.0 s) yet only 3 renditions; A/`hac_01_1114111` is 334.1 s with 7. B/`hac_02_7772777` is 328.6 s with 4, while B/`hac_02_3337333` is 338.4 s with 7.

**Interpretation:** the model does not simply fill a fixed wall-clock budget. The total surplus is roughly constant per song (score-driven), but *where* the AR trajectory spends it varies: sometimes in the final chorus (many loops), sometimes in earlier instrumental/melismatic space. This is why duration alone cannot be used as the QA gate; the final-chorus span can. HAC02 even has the larger surplus (+83.8 s) with fewer mean repeats (4.75) than HAC01 (6.38, +57.0 s), so surplus magnitude is not linear across songs either — the *shape* of the score decides where the extra vocal time lands.

### 4.3 Alignment signature

On every take the final word is stretched far beyond a normal syllable:

* median word ≈ 0.70–0.75 s;
* final-word ratio **1.6× to 30.4×** the median;
* B/`hac_02_3337333` stretches `عَمْيَاءُ` to **23.08 s**;
* A/`hac_01_1117111` stretches it to **17.98 s**.

The one low ratio (B/`hac_01_1114111`, 1.16 s) does **not** mean fewer repeats: there the aligner distributed the surplus across the chorus lines instead (`span` 71.5 s → 7 renditions). So use the span, not the last-word ratio, as the primary proxy.

---

## 5. Ruled out (or not supported)

| Hypothesis | Verdict |
|---|---|
| Lyric line breaks / formatting (A vs B) | **Ruled out** — identical seeds, both repeat |
| Bad seed | **Ruled out** — all 8 distinct seeds repeat |
| Sampler / CFG | **Ruled out as sufficient** — identical to the clean `cot=off` batch |
| `cap=9000` as trigger | **Not supported** — 15/16 end below cap with an end token; cap only permits the overrun and truncates B/1616161 |
| Standard Arabic diacritics (`النَّجَاءُو` etc.) | **Unlikely** — affects one verse line, not the final chorus; no evidence in the data |
| Total duration → repeat count | **Not monotonic** — r = 0.33 overall, sign flips by song |
| ODE steps / NAR rendering | **Unlikely** — 8 steps in both clean and defective batches; steps affect detail, not text budget |
| ABC presence alone | **Not sufficient** — the `abc_cfg15` control had an ABC and did not loop; its score is shorter than its lyrics |

---

## 6. Measurement caveats

1. **The alignment proxy is not a count.** It measures final-chorus sung time / 10.97 s. Calibrated exactly on one track, ±1 elsewhere. Only A/`hac_01_1114111` has an ASR ground truth (7; user heard 6; the 7th is a low-confidence cadential reprise).
2. **The 10.97 s rendition constant** comes from one song and one tempo; a slower take would slightly under-count.
3. **`lyric_fit_s = 300 s`** is a 95th-percentile fit for 616 letters, not an exact target.
4. **The 0.371 s/letter natural pace** comes from a different song (the `abc_cfg15` control). It is the best available reference, not a per-song measurement.
5. **`truncated`** in the batch metadata is a duration heuristic (`truncated_source: duration_heuristic`), not a decoded end-token flag.
6. **No generation controls were run** on this VM. The causal chain (score surplus → text exhaustion → last-bayt loop) is supported by the natural controls (A/B formatting, seed spread, clean `cot=off` batch, short-score ABC control) but not by a one-variable render.

---

## 7. Next session: GPU analysis only (no generation)

A T4 is available for **analysis**, not for new renders. The full handoff — stems, full-batch ASR, CTC/forced alignment, reconciliation, commands, time budget — is in **[`NEXT_SESSION.md`](NEXT_SESSION.md)**.

In one line: Demucs vocal stems → faster-whisper `small`+`medium` on all 16 → CTC placement of the last bayt on the stems → rewrite `results.csv` with measured counts. The generation matrix in §8 stays parked until those numbers exist.

---

## 8. Parked: one-variable generation experiments (not this session)

Run **only after** the measured counts from `NEXT_SESSION.md` are in. Same model/LoRA/style, **seed `1114111` plus `1117111` and `1212121`** to separate effect from seed noise. Measure every take with `count_last_bayt.py` (not the proxy). Baseline = current A/`hac_01.abc`, seed 1114111, expected count 7.

| ID | Change vs baseline | Tests | Prediction if score-length hypothesis holds |
|---|---|---|---|
| E0 | none (reproduce baseline) | sanity | 7 |
| E1 | trim HAC01 ABC sung vocal to ≈228 s (lyric fit), keep everything else | score length | count drops to ~2–3 |
| E2 | same ABC, `cot=melody` instead of `full` | chord-annotation weight | small drop or unchanged |
| E3 | remove ABC, `cot=off`, same style/lyrics/cap | necessity of ABC | ~2 (matches prior clean batches) |
| E4 | same ABC, `cap=7500` | cap as enabler | count may stay high but audio truncates; no cure |
| E5 | same ABC, `guidance_scale=1.0` vs 1.5 | CFG | little change; CFG is not the driver |
| E6 | same ABC, chorus written 1× / 2× / 3× | text supply | more text → fewer loops; 1× worse |
| E7 | same ABC, add explicit outro lyrics (or an end marker) after the last chorus | end-of-text behaviour | loop shrinks or stops |
| E8 | `النَّجَاءُ` vs `النَّجَاءُو` in verse 4 | diacritic/trailing-waw | no effect on final-chorus count |

Acceptance: E1 and E6 are the decisive tests. If trimming the score to the lyric budget removes the loop, the cause is confirmed. If it does not, re-test with E3/E2 to see whether `cot=full` with *any* external ABC is the trigger.

---

## 9. Recommendations (no production edits)

Ranked by evidence strength and cost:

1. **Do not increase `cap` to fix this.** `cap=9000` is what allowed a 360 s take; 15/16 loops happened below the cap anyway. For scored songs, keep the README rule (score length + 60 s) but treat the cap as a safety net, not a target.
2. **Make the score fit the lyrics.** Target `score_sung_s ≈ 0.37–0.40 × n_letters` (≈228–246 s for 616 letters), or trim/space out the ABC until its sung-vocal budget is within ~10 % of the lyric fit. This is the one change most likely to remove the loop.
3. **Prefer `cot=off` + no ABC for release takes** unless score conditioning is the point of the experiment. That is the configuration of every clean batch to date.
4. **If the ABC must stay, cut the cap to the lyric fit** (e.g. 7250–7500 for a 616-letter song) so an overrun is truncated rather than shipped, and add a **QA gate** on the final-chorus span: flag `span > 2.5 × 10.97 s ≈ 27 s` (i.e. more than ~2.5 renditions). `measure_alignment.py` already emits this.
5. **Do not chase the A/B line-break or diacritic variants.** They are not causal; both batches fail identically.
6. **Re-run the E1/E6 controls on a GPU VM** before changing defaults, and re-measure with ASR rather than the proxy.

---

## 10. Artifacts

```
analysis/last_bayt_repeat/
├── count_last_bayt.py       # ASR + Arabic normalisation + fuzzy occurrence counter (ground truth)
├── measure_alignment.py     # cheap karaoke-alignment proxy, whole batch
├── analyze_score_gap.py     # ABC sung/instrumental budget vs lyric fit
├── score_gap.csv            # score-gap metrics for HAC01/02 + control
├── results.csv              # 16 takes: duration, chorus span, proxy count, expected, ASR (1 row)
├── NEXT_SESSION.md          # T4 analysis handoff: stems, ASR, CTC, reconciliation
└── REPORT.md                # this file
```

Reproduce the cheap table (no GPU, no ASR):

```bash
# batch A
python3 analysis/last_bayt_repeat/measure_alignment.py \
  --karaoke-dir /tmp/opencode/karaokeA --runs-dir /tmp/opencode/hacA \
  --manifest manifests/harith_hac_A.json --batch A \
  --asr-json /tmp/opencode/asr_hac_01_1114111.json \
  --score-gap analysis/last_bayt_repeat/score_gap.csv \
  --out analysis/last_bayt_repeat/results.csv

# batch B (append)
python3 analysis/last_bayt_repeat/measure_alignment.py \
  --karaoke-dir /tmp/opencode/karaokeB --runs-dir /tmp/opencode/hacB \
  --manifest manifests/harith_hac_B.json --batch B \
  --score-gap analysis/last_bayt_repeat/score_gap.csv \
  --out analysis/last_bayt_repeat/results.csv --append
```

Reproduce the ASR ground truth for one track (CPU, ~1 min with the `small` model; reuses the cache in `/tmp/opencode/hac_cache`):

```bash
python3 analysis/last_bayt_repeat/count_last_bayt.py \
  --audio /tmp/opencode/hacA/hac_01_1114111.mp3 \
  --lyrics-file /tmp/opencode/hacA/hac_01_lyrics.txt \
  --cache-dir /tmp/opencode/hac_cache --threshold 75
```

Full-batch ASR counting for the other 15 takes is deliberately **not** run here; it is the first task for the GPU/stronger VM (`count_last_bayt.py --run-dir … --out …`).
