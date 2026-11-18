# Last-bayt repetition in the HAC batches

**Batches:** `20261117-082924_harith_hac_a` (A) and `20261117-093512_harith_hac_b` (B)
**Symptom:** the final chorus bayt (`أَتَلَهَّى بِهَا الْهَوَاجِرَ … بَلِيَّةٌ عَمْيَاءُ`) is sung many times instead of the two written in the lyric sheet.
**Scope:** diagnosis only. No production code was changed, no generation was run on this VM.

---

## 1. Verdict

Every one of the 16 takes sings the last bayt at least as often as the sheet writes it, and **12/16 sing it more**. The proxy estimated **3–9 renditions where the lyric sheet asks for 2** (mean 5.6); the measured answer is lower and firmer: **3.62 renditions on average by Whisper word-level counting, 12/16 takes above the written 2** — roughly **double** the 1.85 that the same counter returns on 27 takes rendered without a score (§3.2).

> **Update 3, 2026-11-18 (control batches + calibration).** Two things changed after the first draft of this verdict.
> 1. **CTC placement is not a counter.** On 15 takes of a different poem rendered with `cot=off` and no score — where the transcript shows the closing bayt exactly twice — the same CTC rule returns **4–8 placements (mean 5.8)**. Its output tracks the length of the scanned region (≈ one placement per 17–20 s), not the number of renditions, and the 10/11/12/13 s window sweep does not flag it. The earlier "5.1 (3–7)" claim is retracted: `ctc_count` now means *placements, an upper bound*, and `ctc_count_asr_ok` keeps only the placements Whisper also heard.
> 2. **The "we always used an ABC" worry has an empirical answer.** 27 existing takes across three poems, rendered with `cot=off` and no score, repeat the closing bayt **1.85×** (21/27 exactly 2, none above 3). The 16 HAC takes repeat it **3.62×** by the same Whisper counter. See §3.2.

> **Identification status.** HAC differs from every clean batch in two things: **CoT/score conditioning** (`cot=full` + an external ABC) and `cap=9000`. `abc_file` is *not* a third independent variable — `generate.py` rejects a score with `cot=off` ("has no effect with cot=off"), so every scored render is also a CoT render. The cap is exonerated: **15/16 takes ended by EOS, not at the cap** (`truncated=False`). What is established is the **class** of cause — score-conditioned generation — not which switch (`full` vs `melody`) does it, nor the exact mechanism. §8 lists the single render that would separate them.

The most consistent mechanism is still the **length mismatch between the external ABC score and the lyric text**: the score asks for more sung vocal seconds than the 616-letter lyric supplies at the model's natural pace, and the model fills the surplus by looping the last bayt once it runs out of words.

* A and B use the **same model, LoRA, seeds, cap, sampler and CFG**; they differ only in lyric line breaks and a few spelling variants — and **both repeat**. Lyric formatting is therefore not the cause.
* All 8 distinct seeds repeat, so it is not a bad seed.
* Sampler/CFG are identical to the no-score control batches that do **not** loop (§3.2), so they are not sufficient on their own.
* The score asks for **+57 s (HAC01) / +84 s (HAC02)** of sung vocal beyond what the 616-letter lyric supplies at the model's natural pace. Forced alignment shows the final word absorbing up to **23.1 s** of unaligned audio — the signature of repeats the aligner cannot place.
* `cap=9000` is not the trigger: only 1/16 takes actually hit it. It merely permits the overrun (and truncates that one take instead of curing the loop).

The control batches already existed on GCS, so this conclusion did not need a render: it needed measuring the takes we had. The remaining one-variable question (`cot=full` vs `cot=melody`, same score) still needs a render and is parked in §8.

---

## 2. Data and method

| What | Where |
|---|---|
| Audio, per-track metadata, logs | `gs://…/runs/20261117-082924_harith_hac_a/`, `…/20261117-093512_harith_hac_b/` (downloaded to `/tmp/opencode/hacA`, `/tmp/opencode/hacB`) |
| Karaoke forced alignments (`words.json`) | `…/karaoke/` (downloaded to `/tmp/opencode/karaokeA`, `/tmp/opencode/karaokeB`) |
| Score / lyric fit metrics | `analysis/last_bayt_repeat/score_gap.csv` (`analyze_score_gap.py`) |
| ASR counters | `analysis/last_bayt_repeat/count_last_bayt.py` (segments), `count_last_bayt_words.py` (words) |
| CTC placement counter | `analysis/last_bayt_repeat/ctc_placements.py` → `work/ctc/` |

Four measurements plus one reconciliation step; 4–5 were added in the 2026-11-18 GPU session and are what §3.1 reports:

1. **ASR occurrence counting** (`count_last_bayt.py`, `count_last_bayt_words.py`) — faster-whisper Arabic transcription of the tail, Arabic normalisation, fuzzy matching of the last bayt, NMS de-duplication. The word-timestamp variant is the usable one on stems, and it is the **arbiter** for counts.
2. **Forced-alignment geometry** (`measure_alignment.py`) — reads the karaoke `words.json`, measures the final chorus span and the duration of the last aligned word. Cheap, whole-batch, CPU-only.
3. **Score-vs-lyrics budget** (`analyze_score_gap.py`) — sung-vocal seconds encoded in the ABC vs the lyric-fit duration.
4. **CTC placement** (`ctc_placements.py`) — XLSR-53 Arabic, 11 s sliding window, CTC forward + Viterbi over the known bayt, NMS on the aligned span. Runs on the Demucs vocal stem. Useful as an **onset detector**; it over-counts ~3× when the count is known (§3.1.1), so it is reported as an upper bound.
5. **Reconciliation** (`reconcile_counts.py`, `check_acceptance.py`) — joins 1–4 into `results.csv`, adds `ctc_count_asr_ok` (placements Whisper corroborates), sets `review_flag`, and gates the table.
6. **Control batches** (`count_final_bayt.py`, `summarize_controls.py`) — the same counters applied to 27 existing takes rendered with `cot=off` and no score, which is what turns the causal claim from inference into a comparison (§3.2).

### 2.0 Stems

All audio measurements run on **Demucs vocal stems**, never on the full mix: on a mix, backing vocals and reverb tails land between renditions and both ASR and CTC start treating them as extra passes. 16/16 stems were produced with `demucs==4.1.0` (`htdemucs`, `--two-stems vocals`, CUDA); duration matches the source within 0.1 s (Demucs resamples 48 kHz → 44.1 kHz). A and B share track filenames, so the stems are kept in separate batch directories — a single combined run silently overwrites A with B.


### 2.1 ASR validation

`hac_01_1114111.mp3` (334.08 s), reference = last sung block:

```
occurrences: 7
times: 250.74 261.74 272.74 282.74 296.02 307.70 315.62
mean occurrence: 10.97 s
strict >=85 score: 3 (250.74, 261.74, 272.74)
```

The `small` model and an independent `medium` pass both returned **7**. The user heard **6**. The disputed item is the last one at 315.62–328.62 s, a lower-confidence cadential reprise (score 77.6). Treat this track as **6–7**, and treat the mean rendition length (10.97 s) as the calibration constant for the cheap proxy.

Re-measured on the vocal stem (§3.1): `small` returns 7, `medium` **9**, CTC **7**, and CTC is stable at 7 for every window length from 10 to 13 s. This is the one take where all three agree, which is why it is the anchor case. The `medium` pass over-splits: it emits overlapping windows (250.96, 261.66, 273.80, 283.26, then *both* 290.10 and 295.86) because the merged 9-word window straddles a boundary. On the rest of the corpus **model size does not buy counting accuracy**, and CTC agreement here is partly luck — see the calibration in §3.1.1.

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

`analysis/last_bayt_repeat/results.csv` (16 rows). `est` is the alignment proxy; `exp` is the number of renditions actually written in the lyric sheet; `span` is the final-chorus sung span; `last` is the final word's aligned duration. The `ASR` column is the historical single-track check only — the full measured counts are in **§3.1**, and the control comparison that identifies the recipe is **§3.2**.

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

* Proxy estimate mean 5.56, median 5.5, range 3–9.
* Proxy: 16/16 ≥ 3× the written renditions; 12/16 ≥ 5×.
* Only B/`hac_01_1616161` hit the 9000 cap (360.0 s) and was flagged `truncated` (duration heuristic).

> These are **proxy** numbers (`span / 10.97 s`). The measured counts are lower: ASR mean **3.62**, 12/16 above the written 2 (§3.1), against **1.85** on 27 no-score control takes (§3.2). The proxy ranks the takes acceptably (±1 on 12/16) but over-reads the absolute level, and it over-reads most on the takes where the aligner had to absorb the surplus into one word.

### 3.1 Measured counts (Whisper on vocal stems, CTC as corroboration)

All 16 takes were re-measured on this GPU box, on **Demucs vocal stems only** (never on the full mix, where backing vocals and reverb tails smear the placements). The numbers live in `results.csv`; the required columns are `asr_count` (Whisper `small`, fuzzy ratio ≥ 75), `asr_count_strict85`, `asr_count_medium`, `ctc_count`, `ctc_first_onset_s`, `ctc_last_offset_s`, `review_flag` and a one-line `note` on every disputed row. `ctc_count_asr_ok` is new: it keeps only the CTC placements that have a Whisper onset within 3 s.

| batch | track | proxy `est` | **ASR s (75)** | ASR s (85) | ASR m (75) | CTC (upper) | CTC ASR-ok | CTC 10–13 s | flag |
|---|---|---:|---:|---:|---:|---:|---:|---:|:---|
| A | `hac_01_1114111` | 7 | **7** | 4 | 9 | 7 | 7 | 7–7 | disputed |
| A | `hac_01_1117111` | 6 | **4** | 3 | 3 | 4 | 3 | 3–4 | agree |
| A | `hac_01_1212121` | 6 | **4** | 2 | 5 | 6 | 4 | 6–6 | disputed |
| A | `hac_01_1616161` | 6 | **5** | 5 | 6 | 6 | 5 | 4–6 | agree |
| A | `hac_02_3331333` | 6 | **3** | 0 | 1 | 5 | 3 | 4–5 | disputed |
| A | `hac_02_3337333` | 3 | **2** | 1 | 3 | 3 | 1 | 2–3 | agree |
| A | `hac_02_7772777` | 4 | **4** | 3 | 2 | 6 | 4 | 4–6 | disputed |
| A | `hac_02_7774777` | 5 | **4** | 3 | 4 | 5 | 4 | 4–5 | agree |
| B | `hac_01_1114111` | 7 | **5** | 5 | 6 | 5 | 5 | 5–5 | disputed |
| B | `hac_01_1117111` | 5 | **3** | 1 | 3 | 4 | 3 | 3–4 | agree |
| B | `hac_01_1212121` | 5 | **2** | 1 | 3 | 4 | 2 | 4–5 | disputed |
| B | `hac_01_1616161` | 9 | **4** | 3 | 5 | 6 | 4 | 5–6 | disputed |
| B | `hac_02_3331333` | 4 | **3** | 0 | 3 | 4 | 3 | 4–4 | agree |
| B | `hac_02_3337333` | 7 | **5** | 4 | 7 | 6 | 5 | 6–6 | agree |
| B | `hac_02_7772777` | 4 | **1** | 0 | 3 | 5 | 1 | 5–5 | disputed |
| B | `hac_02_7774777` | 5 | **2** | 0 | 4 | 6 | 2 | 5–6 | disputed |

**Measured result.** ASR mean **3.62**, median **4**, range **1–7**; **12/16 are above the written 2** and **9/16 are at 4 or more**. The proxy predicted 12/16 within ±1 of the ASR count. Against the no-score control batches (§3.2, mean 1.85) that is a **2× difference**, and it is the conservative direction: the HAC stems are the harder audio, so Whisper loses words there, not gains them.

`medium` is not a better counter: it agrees exactly with `small` on only 3/16 takes and is *higher* on 9/16 (up to 9 on A/`hac_01_1114111`, where two of its matches are the same rendition placed at 290.1 and 295.9 s). It shares Whisper's segmentation and its over-splitting, so it is a sensitivity check, not independent evidence.

#### 3.1.1 CTC over-counts — measured against a known answer

The CTC placement rule was calibrated on the control batches, where the true count is known twice over (the transcript and the lyric sheet both say 2):

| batch | takes | true count | ASR count | **CTC placements** |
|---|---:|---:|---:|---:|
| `OFF` (imru al-qais, 5 maqamat × 3 adapters) | 15 | 2 | 1.80 | **5.80** (4–8) |
| HAC (all 16, for comparison) | 16 | 2 | 3.62 | 5.12 (3–7) |

CTC returns **4–8 placements on takes that contain exactly two renditions**, and the count scales with the scanned region (≈ one placement per 17–20 s), not with the content. The window-length sweep does not catch it either: on the first `OFF` take, scanning only the last 30 % of the track, it reports 4 at 10/11/13 s windows and 5 at 12 s — against a truth of 2. Keeping only ASR-corroborated placements cuts HAC's 82 placements to 56 (68 %), and not all of the 26 dropped ones are false — but the rule cannot tell which is which.

**Consequence:** `ctc_count` is an upper bound and an onset locator, not a count; the headline number in this report is `asr_count`. The earlier draft's "mean 5.1, range 3–7" came from the uncalibrated CTC rule and is withdrawn.

#### 3.1.2 What CTC *is* good for: onsets and the 6-vs-7 split

* **Onset accuracy.** 56 of 82 CTC placements sit within 3 s of a Whisper onset (median absolute offset **0.56 s**, signed −0.34 s). Where the two agree, the timestamp is trustworthy to about half a second.
* **The 6-vs-7 question on A/`hac_01_1114111`.** Both machines say **7**, with placements at 249.7, 259.6, 274.0, 283.5, 296.1, 304.8, 314.0 s, identical at every window length. The 7th (314–325 s) is a full-length (10.98 s) rendition with vocal-stem energy comparable to its neighbours, so it is not a bleed from the mix and not a truncated echo. The honest statement is: **the stem contains seven renditions; the ear that reports six is grouping the last one into the cadence.** The row stays `disputed` rather than overwriting the user's count.
* **Disputed rows** (`|asr_count − ctc_count| ≥ 2`, 9 rows, plus the 6-vs-7 take) each carry a `note` with the timing evidence. These are exactly the rows where the upper bound and the arbiter disagree, i.e. the rows where the true count is least certain.

---

### 3.2 Control batches: the same counter on takes with no score

The open worry was that **every take we had ever rendered used an external ABC**, so the repetition could have been a property of the model, the poem, or Arabic singing in general rather than of the recipe. That is testable against takes that already exist. `generate.py` refuses a score with `cot=off` ("has no effect with cot=off"), so the real variable is **score-conditioned generation** (`cot=melody|full` + ABC) versus **plain lyric generation** (`cot=off`, no score). The repo has 208 such `cot=off` song entries across 25 manifests, and the three batches below had audio on GCS:

| batch | poem | takes | `cot` | ABC | cap | ASR count | distribution |
|---|---|---:|---|---|---:|---:|---|
| `20261116-121703_imru…_mix_grid` (`OFF`) | imru al-qais, 5 maqamat × 3 adapters | 15 | off | none | 7250–8250 | **1.80** | 12×2, 3×1 |
| `20261115-134829_wolf_grid04` (`WOLF`) | al-shanfara, adapter grid | 8 | off | none | quantile | **1.88** | 5×2, 2×1, 1×3 |
| `20261115-184206_kurd_mix_grid` (`KURD`) | ibn zuraiq, adapter grid | 4 | off | none | quantile | **2.00** | 4×2 |
| **pooled control** | 3 poems | **27** | off | none | 7250–8250 | **1.85** | 21×2, 5×1, 1×3 |
| **HAC A+B** | harith | **16** | **full** | **2 scores** | **9000** | **3.62** | 5×4, 3×3, 3×5, 3×2, 1×7, 1×1 |

`summarize_controls.py` regenerates this from `work/asr_{OFF,WOLF,KURD}_small.csv` and `results.csv`; every count comes from the same Whisper `small` word-level pass on a Demucs vocal stem, so the two rows are directly comparable.

**Result.** The control batches repeat the closing bayt **1.85× on average**, and **21 of 27 sing it exactly twice — the number written in the sheet**. Not one of them loops. The HAC takes average **3.62×**, and 12/16 exceed 2.

The adapter is not the difference either: five of the control takes (`p01…p05_…_a015_c15_ar075`) use the **same LoRA and scale as HAC** (`a015`, AR 0.75) and average **1.80** renditions. The only thing those five share with HAC is the absence of a score.

* Mann–Whitney (HAC > controls): **p = 8.6 × 10⁻⁶**.
* Tracks above 2: **12/16 vs 1/27**, Fisher exact **p = 1.4 × 10⁻⁶**.
* The one control take at 3 is `wolf_a01_c15_ar1`; it is also the only control where the strict-85 pass collapses to 1, i.e. the least trustworthy row in the control set.

**What this rules out.**

| Candidate | Verdict from the controls |
|---|---|
| The model/LoRA always loops the last line | **no** — 21/27 takes with the same architecture sing it twice |
| The poem / the closing bayt invites looping | **no** — 3 different poems, 1.85× |
| Arabic singing or melisma inherently repeats | **no** — same language, same style tag |
| Seeds / sampler / CFG | **no** — identical settings, and they are also in the controls |
| Lyric line breaks (A vs B) | **no** — both HAC variants loop, controls with other line breaks do not |
| `cap=9000` | **no** — 15/16 HAC takes ended by EOS, and the control caps (7250–8250) are close |
| **Score-conditioned generation (`cot=full` + ABC)** | **yes** — the only variable left standing |

**Caveats on this comparison.** (1) The control poems are different from the HAC poem, so this is a between-song comparison; it is robust because the effect is uniform across three poems and 27 takes, but it is not a same-song A/B. (2) Takes within a batch share a song and a seed set, so the p-values overstate independence. (3) Whisper undercounts *more* on the HAC stems (dense symphonic-metal vocal), so the 3.62 is a lower bound while 1.85 is close to exact — the gap is if anything larger than measured. (4) Nothing here separates `cot=full` from `cot=melody`; both take the score, and only `full` has been rendered with it. 

---

## 4. What changed vs the clean batches

| Variable | Prior clean batches | HAC A | HAC B | Implicated? |
|---|---|---|---|---|
| `cot` | `off` (all takes) | `full` | `full` | **yes — now demonstrated (§3.2)** |
| external ABC | none | `hac_01.abc` / `hac_02.abc` | same | not independent: `generate.py` rejects a score with `cot=off` |
| cap | 6500–8250 | 9000 | 9000 | no — 15/16 ended by EOS, and controls at 7250–8250 do not loop |
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

The clean `abc_cfg15` control also had an external ABC and CFG 1.5, but its score is **shorter** than its lyric fit (−56.1 s), and it showed no repetition. That fits the surplus mechanism: a score that asks for *less* vocal time than the words need leaves nothing for the model to fill. (It is one take on a different adapter, so it is supporting evidence, not a control; the 27-take comparison in §3.2 is what establishes that the score has to be in play at all.)

The score is also more vocally dense than the lyric sheet: `score_gap.csv` counts **53 sung vocal blocks for 23 lyric lines (2.3×)** in HAC01 and **31 for 23 (1.35×)** in HAC02, versus **0.7×** for the control. Even before matching seconds, the score encodes more vocal phrases than the lyrics have lines.

Mechanically: with an external `abc_file` the plan stage is skipped and the score is injected as a token prefix (`docs/suno-generation-controls.md` §D.11). The v3 adapter was trained with `cot=off`; a full, note-dense ABC is off-distribution (`docs/transcription.md`), and `guidance_scale` amplifies style/lyrics rather than ABC adherence. The model follows the score's *time* budget, exhausts the lyric text, and — having no more words — re-sings the last bayt.

### 4.2 Duration surplus vs repeat count

All 16 takes overrun the 300 s lyric fit by **+18.9 to +60.0 s**. Total duration is nevertheless a **poor predictor** of how many repeats occur. Pearson `r` against duration, on the ASR counts (CTC values in brackets, proxy in braces):

| grouping | r(count, duration) |
|---|---:|
| all 16 | +0.07 (−0.02) {0.33} |
| batch A only | −0.25 (−0.39) {−0.35} |
| batch B only | +0.54 (+0.53) {0.78} |
| hac_01 only (8 takes) | +0.19 (+0.45) {0.85} |
| hac_02 only (8 takes) | −0.23 (−0.60) {−0.31} |

Examples (ASR): A/`hac_02_3337333` is the longest A take (353.0 s) yet only 2 renditions; A/`hac_01_1114111` is 334.1 s with 7. B/`hac_02_7772777` is 328.6 s with 1 transcribed rendition (the worst ASR failure in the set), while B/`hac_02_3337333` is 338.4 s with 5.

**Interpretation:** the model does not simply fill a fixed wall-clock budget. The total surplus is roughly constant per song (score-driven), but *where* the AR trajectory spends it varies: sometimes in the final chorus (many loops), sometimes in earlier instrumental/melismatic space. This is why duration alone cannot be used as the QA gate; the final-chorus span can. HAC02 even has the larger surplus (+83.8 s) with fewer ASR renditions (3.00) than HAC01 (4.25, +57.0 s), so surplus magnitude is not linear across songs either — the *shape* of the score decides where the extra vocal time lands.

### 4.3 Alignment signature

On every take the final word is stretched far beyond a normal syllable:

* median word ≈ 0.70–0.75 s;
* final-word ratio **1.6× to 30.4×** the median;
* B/`hac_02_3337333` stretches `عَمْيَاءُ` to **23.08 s**;
* A/`hac_01_1117111` stretches it to **17.98 s**.

The one low ratio (B/`hac_01_1114111`, 1.16 s) does **not** mean fewer repeats: there the aligner distributed the surplus across the chorus lines instead (`span` 71.5 s). CTC measures 5 renditions there, and 5 is also what ASR hears, so this is the clearest case of the proxy over-reading a stretched span. Use the span as a cheap gate, not as the count.

---

## 5. Ruled out (or not supported)

| Hypothesis | Verdict |
|---|---|
| Lyric line breaks / formatting (A vs B) | **Ruled out** — identical seeds, both repeat |
| Bad seed | **Ruled out** — all 8 distinct seeds repeat |
| Sampler / CFG | **Ruled out as sufficient** — identical to the 27 `cot=off` control takes that do not loop (§3.2) |
| The model / the poem / Arabic singing repeats by nature | **Ruled out** — 27 takes, 3 poems, `cot=off`, mean 1.85, 21/27 exactly 2 |
| `cap=9000` as trigger | **Ruled out** — 15/16 end below cap with an end token, and the control caps (7250–8250) are close; cap only permits the overrun and truncates B/1616161 |
| Standard Arabic diacritics (`النَّجَاءُو` etc.) | **Unlikely** — affects one verse line, not the final chorus; no evidence in the data |
| Total duration → repeat count | **Not monotonic** — r = 0.33 on the proxy, +0.07 on the measured ASR counts, sign flips by song |
| ODE steps / NAR rendering | **Unlikely** — 8 steps in both clean and defective batches; steps affect detail, not text budget |
| ABC *file* presence as a separate switch | **Not a separate variable** — `generate.py` rejects a score with `cot=off`; ABC and CoT travel together |
| Score-conditioned generation (`cot=full` + ABC) | **Implicated** — the only variable that differs from the 27 no-score takes, all of which stay at ≤3 |

---

## 6. Measurement caveats

1. **The alignment proxy is not a count.** It measures final-chorus sung time / 10.97 s. Keep `est_count` only as a cheap whole-batch gate; the measured ASR counts differ from it by up to 3 (B/`hac_01_1616161`, the truncated take: 9 vs 4).
1. **CTC is an upper bound, not a count.** Calibrated on 15 takes with a known answer of 2, the placement rule returns 4–8 (mean **5.8**), roughly one placement per 17–20 s of scanned region (§3.1.1). Use `ctc_count_asr_ok` (placements Whisper corroborates) or `asr_count`; treat `ctc_count` as "at most this many". The per-placement spans, scores and window sweep are still in `work/ctc/<batch>_<track>.json` for anyone who wants a stricter rule.
1. **CTC onsets are trustworthy even when its counts are not.** 56/82 placements sit within 3 s of a Whisper onset (median 0.56 s, signed −0.34 s). The window-length sweep (10/11/12/13 s) is stable on 7/16 HAC rows *and* on the mis-counted control take, so it is a reproducibility check, not a validity check.
1. **ASR is a lower bound, not a ground truth.** Whisper merges adjacent renditions into one 20 s segment (the segment-level counter returned 4 on A/`hac_01_1114111`) and drops whole renditions on dense mixes (1 match on B/`hac_02_7772777`, where the vocal stem is at full energy throughout the run — so ASR is missing, not the audio). `medium` over-splits in the other direction (9 on A/`hac_01_1114111`, with two boxes on the same rendition at 290.1 and 295.9 s). It is still the best available count because its errors are omissions, which cannot manufacture the HAC-vs-control gap.
1. **The control comparison is between songs, not within one.** 27 takes, 3 poems, all `cot=off`. Take-level p-values overstate independence because takes in a batch share a song and a seed set; the effect is nonetheless uniform (21/27 exactly 2, max 3).
2. **The 10.97 s rendition constant** comes from one song and one tempo; a slower take would slightly under-count.
3. **`lyric_fit_s = 300 s`** is a 95th-percentile fit for 616 letters, not an exact target.
4. **The 0.371 s/letter natural pace** comes from a different song (the `abc_cfg15` control). It is the best available reference, not a per-song measurement.
5. **`truncated`** in the batch metadata is a duration heuristic (`truncated_source: duration_heuristic`), not a decoded end-token flag.
6. **No generation was run for this update.** The control batches were already on GCS; the missing piece is the `cot=melody` render (§8), which isolates the last remaining switch.
7. **All measurement was on Demucs stems.** Separation can move a little energy between stems, but a rendition is a 9–11 s vocal event, far above the bleed scale.

---

## 7. Next session: GPU analysis only (no generation)

**Status: done, 2026-11-18.** A T4 was used for analysis only — no `generate.py`, no `run_one.sh`, no token surgery, no re-render. Demucs → faster-whisper `small`+`medium` → CTC placement on the stems → `results.csv` reconciled → §3.1 written, then the control batches measured → §3.2. The handoff itself stays in **[`NEXT_SESSION.md`](NEXT_SESSION.md)** for reference.

What it produced, in one line: the loop is real (12/16 takes above the written 2; ASR mean 3.62 vs 1.85 on 27 no-score takes), the ear's "many times" was somewhat high (3.62, not 5.6), and the cause is score-conditioned generation rather than the model, the poem or the ABC file by itself — with `cot=full` vs `cot=melody` still unseparated.

What is still parked: the single `cot=melody` render in §8.

---

## 8. Parked: one-variable generation experiments (not this session)

Run **only after** the measured counts from `NEXT_SESSION.md` are in. Same model/LoRA/style, **seed `1114111` plus `1117111` and `1212121`** to separate effect from seed noise. Measure every take with `count_last_bayt_words.py` on the Demucs stem (ASR is the arbiter; use `count_final_bayt.py` only for onsets, not for counts — it over-counts ~3×, §3.1.1). Baseline = current A/`hac_01.abc`, seed 1114111, measured count **7** by both machines.

**E3 is already answered and needs no render** — §3.2 measures 27 existing no-score takes at 1.85 renditions (max 3). The remaining one-variable question is E2, because `generate.py` cannot run a score with `cot=off`.

| ID | Change vs baseline | Tests | Status / prediction if score-length hypothesis holds |
|---|---|---|---|
| E0 | none (reproduce baseline) | sanity | optional; measured baseline is 7 |
| E1 | trim HAC01 ABC sung vocal to ≈228 s (lyric fit), keep everything else | score length | **decisive** — count drops to ~2–3 |
| E2 | same ABC, `cot=melody` instead of `full` | which CoT mode takes the score | **decisive switch test** — small drop, or no change |
| E3 | remove ABC, `cot=off`, same style/lyrics/cap | necessity of ABC | **answered by §3.2: 1.85** (existing takes) |
| E4 | same ABC, `cap=7500` | cap as enabler | count may stay high but audio truncates; no cure |
| E5 | same ABC, `guidance_scale=1.0` vs 1.5 | CFG | little change; CFG is not the driver |
| E6 | same ABC, chorus written 1× / 2× / 3× | text supply | more text → fewer loops; 1× worse |
| E7 | same ABC, add explicit outro lyrics (or an end marker) after the last chorus | end-of-text behaviour | loop shrinks or stops |
| E8 | `النَّجَاءُ` vs `النَّجَاءُو` in verse 4 | diacritic/trailing-waw | no effect on final-chorus count |

Acceptance: **E1 and E2** are the decisive tests. If trimming the score to the lyric budget removes the loop, the mechanism is the surplus vocal budget. If `cot=melody` with the same score does not loop, the trigger is `cot=full` specifically, not score conditioning in general.

---

## 9. Recommendations (no production edits)

Ranked by evidence strength and cost:

1. **Do not increase `cap` to fix this.** `cap=9000` is what allowed a 360 s take; 15/16 loops happened below the cap anyway. For scored songs, keep the README rule (score length + 60 s) but treat the cap as a safety net, not a target.
2. **Make the score fit the lyrics.** Target `score_sung_s ≈ 0.37–0.40 × n_letters` (≈228–246 s for 616 letters), or trim/space out the ABC until its sung-vocal budget is within ~10 % of the lyric fit. This is the change most likely to remove the loop, but it is now a *mechanism* bet: §3.2 shows the loop appears only when the score is in play, not that score length is the knob.
3. **Prefer `cot=off` + no ABC for release takes** unless score conditioning is the point of the experiment. That is the configuration of every batch that does not loop — 27 takes, mean 1.85 (§3.2).
4. **If the ABC must stay, cut the cap to the lyric fit** (e.g. 7250–7500 for a 616-letter song) so an overrun is truncated rather than shipped, and add a **QA gate** on the final-chorus span: flag `span > 2.5 × 10.97 s ≈ 27 s` (i.e. more than ~2.5 renditions). `measure_alignment.py` already emits this.
5. **Do not chase the A/B line-break or diacritic variants.** They are not causal; both batches fail identically.
6. **Re-run E1/E2 (score trim, `cot=melody`) on a GPU VM** before changing defaults, and count with ASR, not the proxy or the CTC placement count.
7. **Do not reuse `ctc_placements.py` as a counter without a known-answer calibration.** It looked stable and articulate and was still 3× high; the 15-take control is the check to repeat (`work/ctc_OFF.csv`).

---

## 10. Artifacts

```
analysis/last_bayt_repeat/
├── count_last_bayt.py       # ASR + Arabic normalisation + fuzzy occurrence counter (ablation reference)
├── count_last_bayt_words.py # word-timestamp variant: splits merged 20 s segments back into renditions (the arbiter)
├── ctc_placements.py        # CTC placement of the bayt on a vocal stem -> onsets + upper bound (not a count)
├── count_final_bayt.py      # same placement rule over any run dir / any reference: control batches + calibration
├── summarize_controls.py    # joins the control ASR runs with results.csv -> work/controls_vs_hac.csv
├── reconcile_counts.py      # joins proxy + ASR + CTC -> results.csv + work/results_asr_ctc.csv
├── check_acceptance.py      # T5 gate: 16 rows, no blank counts, notes on disputed rows
├── measure_alignment.py     # cheap karaoke-alignment proxy, whole batch
├── analyze_score_gap.py     # ABC sung/instrumental budget vs lyric fit
├── score_gap.csv            # score-gap metrics for HAC01/02 + control
├── results.csv              # 16 takes: proxy + measured ASR/CTC counts + flags + notes
├── NEXT_SESSION.md          # T4 analysis handoff: stems, ASR, CTC, reconciliation
└── REPORT.md                # this file
```

Working artifacts from the measurement run (`work/` is untracked, nothing was copied to GCS):

| Path | What |
|---|---|
| `work/stems/{A,B}/htdemucs/<track>/vocals.wav` | 16 Demucs vocal stems (44.1 kHz, duration preserved) |
| `work/stems/{OFF,WOLF,KURD}/htdemucs/<track>/vocals.wav` | 27 control stems (§3.2) |
| `work/asr{A,B}/`, `work/mix{A,B}/` | symlink run dirs with `input.json` + `batch_manifest.json` for the ASR scripts |
| `work/asr_{A,B}_small.csv` | word-level ASR on the stems, `small` |
| `work/asr_{A,B}_medium.csv` | word-level ASR on the stems, `medium` |
| `work/asr_{A,B}_small_mix_words.csv` | word-level ASR on the full mix (cross-check only) |
| `work/asr_{OFF,WOLF,KURD}_small.csv` | control-batch ASR, same instrument (§3.2) |
| `work/controls_vs_hac.csv` | the 43-row control-vs-HAC table behind §3.2 |
| `work/ctc/<batch>_<track>.json` | per-track placements, spans, scores, window-length stability |
| `work/ctc/ctc_summary.csv` | the 16-row CTC summary consumed by `reconcile_counts.py` |
| `work/ctc_OFF.csv` | CTC calibration: 15 control takes with a known answer of 2 |
| `work/results_asr_ctc.csv` | copy of the reconciled table |

Reproduce the measured counts (T4, ~4 min for CTC, ~8 min for `medium` ASR):

```bash
export LD_LIBRARY_PATH=/usr/local/lib/python3.13/dist-packages/nvidia/cublas/lib:/usr/local/lib/python3.13/dist-packages/nvidia/cudnn/lib:$LD_LIBRARY_PATH

# 1. vocal stems (Demucs, per batch — A and B share track filenames)
python3 -m demucs --two-stems vocals -n htdemucs -d cuda -o work/stems/A work/asrA/*.mp3

# 2. ASR on the stems (word timestamps) — this is the count
cd analysis/last_bayt_repeat
python3 count_last_bayt_words.py --run-dir ../../work/asrA --model small  --device cuda --compute-type float16 --cache-dir ../../work/asr_cache/A --out ../../work/asr_A_small.csv
python3 count_last_bayt_words.py --run-dir ../../work/asrA --model medium --device cuda --compute-type float16 --cache-dir ../../work/asr_cache/A_medium --out ../../work/asr_A_medium.csv

# 3. CTC placement (XLSR-53 Arabic, 11 s window, NMS on the span) — onsets, upper bound
python3 ctc_placements.py --device cuda

# 4. reconcile + gate
python3 reconcile_counts.py
python3 check_acceptance.py
```

Reproduce the control comparison (§3.2) and the CTC calibration (§3.1.1):

```bash
cd analysis/last_bayt_repeat
# control stems live beside the render, named <track>.mp3 so --run-dir accepts them
python3 count_last_bayt_words.py --run-dir /tmp/opencode/stems_OFF  --model small --device cuda \
  --compute-type float16 --cache-dir ../../work/asr_cache_ctrl --out ../../work/asr_OFF_small.csv
python3 count_last_bayt_words.py --run-dir /tmp/opencode/stems_WOLF --model small --device cuda \
  --compute-type float16 --cache-dir ../../work/asr_cache_ctrl --out ../../work/asr_WOLF_small.csv
python3 count_last_bayt_words.py --run-dir /tmp/opencode/stems_KURD --model small --device cuda \
  --compute-type float16 --cache-dir ../../work/asr_cache_ctrl --out ../../work/asr_KURD_small.csv
python3 summarize_controls.py          # -> work/controls_vs_hac.csv  (§3.2)

# CTC on the control takes: known answer is 2, the rule returns 4-8
python3 count_final_bayt.py --audio-dir /tmp/opencode/vocal_off \
  --input-json /tmp/opencode/vocal_off/input.json \
  --manifest /tmp/opencode/vocal_off/batch_manifest.json \
  --stems-root ../../work/stems/OFF --region-frac 0.55 --out ../../work/ctc_OFF.csv
```

Reproduce the cheap proxy table (no GPU, no ASR):

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

Note: `measure_alignment.py` rewrites the proxy columns only; run `reconcile_counts.py` afterwards to restore the measured columns.

Reproduce the ASR ground truth for one track (CPU, ~1 min with the `small` model; reuses the cache in `/tmp/opencode/hac_cache`):

```bash
python3 analysis/last_bayt_repeat/count_last_bayt.py \
  --audio /tmp/opencode/hacA/hac_01_1114111.mp3 \
  --lyrics-file /tmp/opencode/hacA/hac_01_lyrics.txt \
  --cache-dir /tmp/opencode/hac_cache --threshold 75
```

