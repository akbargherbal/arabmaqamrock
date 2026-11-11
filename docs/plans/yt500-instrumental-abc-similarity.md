# YT500 instrumental — output-vs-input ABC similarity at 460 tracks

**Status:** planned (2026-11-11). Nothing implemented yet.
**Dataset:** `gs://akbar-december-2024-backup/DATASET/yt500_instrumental/`
**Input ABC:** `tracks/<name>/score.abc` (the score the model was conditioned on)
**Output ABC:** does **not** exist — must be produced by transcribing
`tracks/<name>/audio.mp3` with SheetSage2.
**Oracle:** `local_workspace/abc_similarity.zip` (the 10-track study).
**Goal:** for every track, measure how closely the generated instrumental's ABC
transcript matches the input ABC — at 460-track scale, with exact all-pairs
statistics, in minutes not hours.

---

## 0. TL;DR

- **The bottleneck is transcription, not comparison.** 460 tracks × ~51 s/track
  (measured: 24 tracks in 1225 s on a Colab GPU, `device=cuda`, `dtype=fp32`)
  = **~6.5 GPU-hours**, 3 sessions.
- **Transcription is ~1000× more expensive than storage.** Persist the **full**
  transcript directory for every track (archive + a flat
  `<name>.output.abc` / `<name>.output.meta.json` mirror), not just the ABC:
  measured 1.58 MB/track raw → ~0.73 GB / ~50–80 MB gzipped for all 460. No
  later task may ever need a re-transcription.
- **The old comparison scales badly by construction, not by nature.** It
  compares all N² pairs with 17 metrics, two of which are full-sequence DTW.
  At N=460 that is 211,600 pairs × 2 DTWs ≈ 1.7 h single-core.
- **Fix:** canonicalize each score into a fixed feature vector once, then
  compute the 14 cheap metrics for **all N² pairs with BLAS/broadcasting**
  (seconds). The 4 expensive metrics (2 DTW, 2 four-gram F1) become an
  **escalation/audit path**: full DTW on ~30 stratified tracks, banded DTW on
  flagged tracks only.
- **Comparison budget:** matched table < 1 s, exact 460×460 matrix ~40 s,
  cohort stats + permutation test < 5 s, escalation < 10 s, deep audit ~1 s.
  **Peak RAM < 300 MB, no GPU.**
- **Nothing is sampled away.** The full matrix is cheap once it is linear
  algebra, so baseline, `composite_adj`, retrieval rank and lift stay exact.
- **Validation before GPU spend:** the cheap pipeline is prototyped and
  parity-tested locally against the vendored oracle on 489 corpus scores plus
  11 real input/output pairs already on disk.

---

## 1. Definitions

| Term | Meaning here |
|---|---|
| **input score** | `DATASET/yt500_instrumental/tracks/<name>/score.abc`: the score the model was conditioned on. Two voices, `V:Vocal` = chord symbols + rests, `V:Ins` = monophonic melody, `\n% section` comments, `L:1/32`. Read-only. |
| **output score** | the SheetSage2 transcript of `tracks/<name>/audio.mp3`, produced by `transcribe.py --full`. Two voices, chords retained. |
| **naming contract** | the only file ever called `score.abc` is the **input** inside the read-only dataset. Everywhere we stage or publish, use `<name>.input.abc` (input) and `<name>.output.abc` (output); output sidecars are `<name>.output.meta.json`; archives are `<name>.output-transcript.tar.gz`. Never publish a bare `score.abc` on the output side. |
| **track** | one dataset folder, `yt500-NNNN-<video_id>`; N = 460. |
| **cheap metrics** | 14 metrics computable from per-score feature vectors (no pairwise sequence alignment). |
| **deep metrics** | 4 metrics from the oracle that need alignment/sequences: `chord_timeline_dtw`, `melody_chroma_dtw`, `interval_4gram_f1`, `rhythm_4gram_f1`. |
| **matched pair** | (input_i, output_i). |
| **mismatched pair** | (input_j, output_i), j ≠ i; used for the chance baseline. |

---

## 2. What exists (verified 2026-11-11)

| Item | Value |
|---|---|
| Tracks | **460** (`audio.mp3` count confirmed on GCS) |
| Audio | 3.02 GB, MP3; `tracks.jsonl` row per track |
| Input score | `score.abc` per track, ~1.5 MB total; `\n% intro/verse/...` present |
| Output score | **absent** |
| Metadata | `tracks.jsonl` / `catalog.jsonl`: name, rank, title, artist, country, tier, `nominal_s`, `wav_s`, `delta_pct`, sections, score hash, generation run/seed |
| Corpus cross-check | `work/yt500_gen/corpus/index.json` holds `instrumental_abc_sha256` per track (489-track frozen corpus) |
| Existing proof of concept | `local_workspace/fadhl_shaker_selected_scores.zip`: 23/24 tracks transcribed from **MP3** with `--full`; output has `V:Vocal` + chords + `V:Ins`; ~40–75 s/track |
| Local 11-pair test set (dev machine only) | input scores in `local_workspace/20261108-191143_fadhl_shaker_instrumental_16_/scores/`, matching transcripts in the zip (see §5.3) |

The input score is itself a transcription of the original song, and the output
score is a transcription of generated audio. Both carry transcriber noise, so
the achievable composite has a ceiling below 1.0 and varies with source
complexity. **Per-track verdicts must be cohort-relative**, not fixed cutoffs
tuned on 10 tracks.

---

## 3. Why the 10-track script does not scale — and the fix

The oracle's `build_report()` needs (a) matched scores, (b) a chance baseline,
(c) a retrieval rank. It gets all three by computing **every pair** with
`compare_features()`, which rebuilds chroma frames and runs two DTWs each time.

Measured on real corpus scores (12 scores, 16 pairs): **29.6 ms/pair**.

| N | Pairs | Old cost (1 core) | Old cost (8 cores) |
|---:|---:|---:|---:|
| 10 | 100 | 3 s | < 1 s |
| **460** | **211,600** | **1.74 h** | ~13 min |
| 5,000 | 25,000,000 | ~8.6 days | ~1 day |

The fix is to separate the metrics by cost class:

1. **Per-score features** (O(notes)): pitch/interval/chord/rhythm histograms,
   register, density, key, tempo, meter, duration. Computed once per track.
2. **Cheap pairwise metrics** = elementwise functions of two feature vectors.
   All 211,600 pairs are then 14 × (a 460×460 BLAS or broadcast) operations.
3. **Set-based metrics** (chord bigram F1, interval/chord vocab) = sparse
   boolean matrix products, still N² but with vocabulary-sized sparse rows.
4. **Alignment metrics** (DTW, four-grams) move out of the default path.
   Full DTW runs on a 30-track audit; banded DTW runs only on flagged tracks
   against their own input.

Complexity: `O(N·notes + N²·D)` with D ≈ 60 and a handful of sparse products.
For N=460 that is ~13 MFLOP per histogram metric — microseconds to
milliseconds on BLAS. **No sampling is required**; exact semantics are kept.

Scanning the old `build_report`: the only thing that was N²-expensive was
`compare_features`; the report logic itself (`base`, `_adj`, `rank`, `lift`)
is unchanged.

---

## 4. Architecture

```
DATASET/yt500_instrumental/tracks/<name>/{audio.mp3, score.abc}   # INPUT (read-only)
        |
        | (Phase 2, GPU, ~6.5 h)
        v
DATASET/yt500_instrumental_transcripts/                           # OUTPUT (durable)
  <name>.output.abc + <name>.output.meta.json
  archives/<name>.output-transcript.tar.gz
        |
        | (Phase 3, local; staged as input/<name>.input.abc, output/<name>.output.abc)
        v
pairs manifest (460 rows: name, input_abc, output_abc, input_sha256, output_sha256)
        |
        | (Phase 4, local, < 2 min)
        v
parse_abc (vendored, unchanged)  ->  feature vector per score
        |
        +--> cheap metrics, all N^2 pairs (BLAS / sparse)  -> baseline, rank, lift
        +--> matched table (460 rows)
        +--> cohort calibration (median/MAD, percentiles) + permutation test
        +--> flags -> banded DTW + deep oracle metrics (own input only)
        +--> 30-track deep audit -> Spearman(cheap, deep)
        |
        v
similarity/{matched_pairs_scores, all_pairs.parquet, baseline, flags,
            cohort_stats.json, escalation, audit, summary.md, *.png}
```

Only two new moving parts: a transcription sync helper (Phase 2) and the
scaled comparison (Phase 4). The parser and the deep metric code are vendored
verbatim from the zip and never edited.

---

## 5. Phase 0 — local preflight and prototype (no GPU)

### 5.1 Inventory and hash verification

1. Download `tracks.jsonl` + all 460 `score.abc` (≈1.5 MB). Write each one
   **renamed by role** to `work/yt500_abc/input/<name>.input.abc`, so no path in
   our tree ever has the ambiguous basename `score.abc`.
2. Assert 460 rows, unique names, every row has `score.abc` and `audio.mp3` in
   the read-only dataset.
3. Verify `sha256(<name>.input.abc)` against, in order:
   - `tracks.jsonl` → `score.abc_sha256`,
   - `work/yt500_gen/corpus/index.json` (or the tracked
     `outputs/YT500/generation/index.json`) → `instrumental_abc_sha256`.
4. Write `work/yt500_abc/inventory.json`: name, `role: "input"`, sha256,
   `input_sha256`, `nominal_s`, `wav_s`, `delta_pct`, sections count, tier,
   country, duration quartile.

**Gate:** 460/460 hashes match (or every mismatch explained and logged).

### 5.2 Vendor the oracle (committed — do not fetch at run time)

The oracle is committed at:

```
analysis/vendor/abc_similarity.py     # verbatim; parse_abc + compare_features
analysis/vendor/regen_filter.py       # verbatim; threshold reference only
analysis/vendor/README.md             # provenance, sha256, "do not edit"
```

Its source of truth was `local_workspace/abc_similarity.zip`, but
`local_workspace/` is **gitignored** and is not present on a fresh Colab VM.
Never reference `local_workspace/` from code, tests or run instructions, and
never try to fetch the oracle from GitHub: it was never tracked there. The
committed copies are the only oracle.

`parse_abc` is the valuable, battle-tested component. Everything else in the
oracle is an audit oracle, not the production path.

### 5.3 Cheap-path prototype and parity test

**Colab note.** `local_workspace/` and `scores/yt500_instrumental/` are
gitignored, so a fresh VM does not have them. Either materialize the 489-score
corpus (`python3 plumbing/yt500_generation_corpus.py --fetch`) or run checks
(a), (b), (d) on the 460 dataset input scores from §5.1 — those are the
production inputs anyway. Skip (c) on the VM and run the deep-parity check on
the 3 Phase-1 probe pairs instead; the 11-pair table exists only on the dev
machine. `outputs/YT500/generation/index.json` (tracked) supplies the
`instrumental_abc_sha256` values for §5.1 without fetching the corpus.

Build `analysis/abc_scale.py` (features + vectorized matrices + banded DTW)
and validate three ways:

**(a) Identical-score sanity.** For each of the 489 corpus scores, compare it
with itself: every cheap metric and the composite must be exactly 1.0.

**(b) Scalar ↔ matrix parity.** On 100 random corpus pairs, assert every cheap
metric from the 460×460 matrix equals `compare_features(...)` to 1e-6.

**(c) Cheap ↔ deep parity on real pairs.** Use the 11 input/output pairs
already on disk (same generation/transcription setup, MP3, `--full`):

| input slug (`…/scores/`) | transcript stem (zip) |
|---|---|
| `al_dawr_ala_meen` | `الدور على مين` |
| `al_hal` | `الحال` |
| `awwal_ma_bashufak` | `أول مابشوفك` |
| `badeet_atib` | `بديت أطيب` |
| `bafakker_bil_sa3at` | `بفكر بالساعات` |
| `feen_layalik` | `فين لياليك` |
| `ghayb` | `غيب` |
| `leh_aljarh` | `ليه الجرح` |
| `ma3_alsalama` | `مع السلامة` |
| `min_kothr_hobbi_feek` | `من كثر حبي فيك` |
| `ya_tkoon_habibi` | `يا تكون حبيبي` |

Compute `composite_cheap` and `composite_deep` (oracle, matched pair only) and
report Spearman ρ and Pearson r. These pairs are only *approximately* matched
(the take dates differ), which is fine — parity is about metric agreement on a
spread of similarity values, not about the pair being the true generation.

**(d) Scale dry run.** Run the full 489×489 cheap matrix on the corpus input
scores; record wall time, peak RAM, and the baseline table. This is the
production code path at N≈N_prod.

**Gates before any GPU spend:**
- 100% identical pairs = 1.0;
- scalar/matrix parity 1e-6;
- ρ(cheap, deep) ≥ 0.85 and r ≥ 0.80 on the 11 pairs;
- 489² matrix ≤ 120 s, RSS ≤ 500 MB.

If a gate fails, fix the cheap feature definitions *before* transcribing.

---

## 6. Phase 1 — Colab probe (3 tracks, ~10 min)

Pick the shortest, median and longest track by `nominal_s` from
`inventory.json`. For each:

```bash
./transcribe.sh /content/yt500_probe/audio \
  --out-dir /content/yt500_probe/transcripts \
  --full --device auto
```

Check per track:
- the transcript (`transcripts/<name>/score.abc` in the working tree, published
  as `<name>.output.abc`) exists and passes `abc_is_valid`;
- contains `V: Vocal` and `V: Ins`;
- chord-symbol count > 0 (important: harmony dimension);
- `parse_abc` succeeds, notes > 0, `total_sec` within ±20% of `wav_s`;
- wall seconds, peak GPU memory, and whether mp3 decoding needed anything
  beyond ffmpeg.

Then run the cheap comparison on these three matched pairs and confirm the
values are in a sane range (not 0, not 1) and the parser handles real output.

**Go/no-go:** median ≤ 120 s/track and chords present in ≥ 2/3 tracks.
If not: try `--melody-only` (accept harmony-blind output), or stage
`mp3 → wav` via ffmpeg, and update Phase 2 accordingly.

---

## 7. Phase 2 — bulk transcription (GPU, 3 sessions)

### 7.1 Staging (the name-collision trap)

Every dataset track stores its audio as `audio.mp3`, so a flat copy collides.
Stage by track name:

```bash
# on Colab
mkdir -p /content/yt500/{audio,input,transcripts}
python3 plumbing/stage_yt500_transcription.py \
  --inventory work/yt500_abc/inventory.json \
  --audio-dir /content/yt500/audio \
  --input-dir /content/yt500/input
```

The stager copies `gs://…/tracks/<name>/audio.mp3` to
`/content/yt500/audio/<name>.mp3` (parallel, ~3 GB) and the dataset's
`score.abc` to `/content/yt500/input/<name>.input.abc`. Stable names and
byte-identical MP3s are required: `transcribe.py` skips a track only when
`meta.json.source_wav_sha256` matches the staged file. **Never re-encode,
re-tag or tar an MP3 in place.**

### 7.2 Run

```bash
./plumbing/setup_transcribe.sh --cuda        # once per VM
./transcribe.sh /content/yt500/audio \
  --out-dir /content/yt500/transcripts \
  --full --device auto --threads 4 \
  --time-budget 7200
```

Rules that matter:

- **`--full`**, not the default melody-only: the comparison needs chord symbols.
- **No `--limit`.** `--limit` truncates the *file list* before the skip check,
  so a resumed run would re-scan the same head of the list forever. Use
  `--time-budget` per session; the next session skips by hash and moves on.
- `--fail-fast` off: one bad track must not end a session.
- Keep `--out-dir` constant across sessions.

Expected: 460 × ~51 s ≈ **6.5 h**, so three 2.5-hour sessions (or two longer
ones). Model load is once per session.

### 7.3 Backup and resume contract (persist everything)

Transcription is the expensive artifact (~6.5 GPU-hours); storage is not.
The measured size of the proven 24-track transcript set is **38 MB raw
(1.58 MB/track)** and **2.6 MB zipped**; all 460 tracks are therefore
**~0.73 GB raw / ~50–80 MB gzipped**. Keep the **entire** transcript directory
for every finished track — ABC, MIDI, labs, `events.json`, `tokens.json`,
`notation/`, `beat/chord/key/structure.lab` — not just `score.abc`. A future
consumer (new metrics, melody analysis, training data, a different comparison)
must never force a re-transcription.

Use the existing, already-tested `plumbing/transcript_archive.py` rather than
reimplementing the archive contract. `plumbing/yt500_transcribe_sync.py` is a
thin wrapper:

- `push` (every 5 min, and once before stopping):
  1. call `archive_transcripts(transcripts_dir)` — it archives **only** dirs
     whose `meta.json` says `status == "ok"` and whose
     `sha256(score.abc) == meta.abc_sha256`, into a deterministic
     `transcripts/<name>.tar.gz` and `_archive_index.json` (sha256, file count,
     source fingerprint);
  2. upload the archive + index as
     `…/archives/<name>.output-transcript.tar.gz` (remote name carries the
     role; the local tool name stays `<name>.tar.gz`);
  3. upload the flat mirror as
     `…/<name>.output.abc` and `…/<name>.output.meta.json`, where the meta is
     the transcribe `meta.json` plus `role: "output_transcript"`,
     `input_sha256`, `input_uri`, `audio_sha256`, `audio_uri`. The ABCs are
     usable without untarring and cannot be mistaken for the input;
  4. per session, upload `_driver.log`, `_timings.csv`,
     `transcribe_manifest.json` to `sessions/<utc>/`.
  Remote objects are **never deleted or overwritten**; a matching sha256 is
  skipped, a missing/corrupt one is re-uploaded. `push` is idempotent.
  Note: inside the archive the ABC keeps transcribe.py's filename `score.abc`;
  that is the only remaining legacy name and the archive filename, its
  `output.meta.json` and the dataset card all mark it as the output side.
- `pull` (session start): download the flat mirror into
  `transcripts/<name>/score.abc` + `transcripts/<name>/meta.json` (the layout
  `transcribe.py` needs, and optionally extract archives). Because the pair is
  verified, `transcribe.py` reports `skipped`, not `skipped-unverified`.
- `--verify`: after each session, run `transcript_archive.py --verify` and
  `./transcribe.sh … --verify`, and upload both reports.

Disk on the VM: 460 archives ≈ 50–80 MB, negligible next to the 3 GB of audio.

### 7.4 Failures

- Expected: `no-abc`/`invalid-abc` on ~4% of tracks (1/24 in the Fadhl run) →
  ~15–20 tracks.
- Retry 1: re-run only the failed names (`--force` on an explicit file list).
- Retry 2: `ffmpeg -i <name>.mp3 -ac 1 -ar 24000 <name>.wav` into a separate
  `wav/` input dir and transcribe there (separate `--out-dir` suffix, or accept
  that the source hash now refers to the WAV).
- Still failing → `status: missing-output` with the error, excluded from the
  matched table and reported in `flags.csv`.

### 7.5 End-of-phase checks

- ≥ 95% of 460 tracks have a verified **output transcript** (≥ 437); in the
  working tree it is `transcripts/<name>/score.abc`, in the published bundle it
  is `<name>.output.abc` / `<name>.output-transcript.tar.gz`.
- The local transcript set and the published dataset prefix agree one-to-one
  (name set plus sha256, compared through the `.output.meta.json` fields).
- `inventory.transcribed/` count + `failures.json` == 460.

---

## 8. Phase 3 — pairs assembly (local, seconds)

```bash
python3 analysis/run_yt500_similarity.py build-pairs \
  --input-dir work/yt500_abc/input \
  --transcripts work/yt500_abc/transcripts \
  --inventory work/yt500_abc/inventory.json \
  --out work/yt500_abc/pairs.json
```

`build-pairs` copies each verified transcript to
`work/yt500_abc/output/<name>.output.abc` (it refuses to proceed if the
transcribe `meta.abc_sha256` does not match). `pairs.json` rows:
`{name, role: "matched_pair", input_abc: "input/<name>.input.abc",
output_abc: "output/<name>.output.abc", status, input_sha256, output_sha256,
audio_sha256}`. **Invariant:** `input_sha256 != output_sha256` for every row
(they can never be byte-identical); if a row violates it, abort — it means the
sides were swapped or one file was copied twice. Validation before metrics:

- every `output_abc` passes `abc_is_valid` and `parse_abc` yields notes > 0;
- parse failures are collected, not crashed on (`parse_abc` returns an empty
  score for garbage);
- the 460 − failures set is the analysis cohort, recorded in `cohort.json`;
- optionally emit `pairs_460.json` in the oracle's column names
  (`ORIGINAL_ABC`, `INST_ABC`, `TRACK_ORIGINAL_ID`) so the old CLI can be run
  verbatim on the 30-track audit.

---

## 9. Phase 4 — scalable similarity (local, < 2 min)

### 9.1 Canonical feature vector (per score, computed once)

`analysis/abc_scale.py:score_features(score) -> dict[str, ndarray]`

| Block | Fields |
|---|---|
| global | `fifths`, `tempo` (quarter/min), `bar_sec`, `total_sec`, `meter` |
| melody (primary line only) | duration-weighted `pc_hist[12]`; `iv_hist[25]` (intervals clipped ±12); `mean_pitch`, `pitch_span` (p95−p5); `interval_set` (4-grams, audit only) |
| harmony | `chord_time[classes]` (time-weighted root+maj/min/dim/aug/sus), `chord_chroma[12]` (time-weighted), `chord_bigrams` (audit only) |
| rhythm | `density` (notes/s), `silence_ratio` (fraction of 0.5 s frames with no sounding note), `dur_hist[16]` (log2 s), `onset_phase[8]` (tempo-fold aligned), `rhythm_4grams` (audit only) |

Melody features come from `primary_line()` (`Ins` when present), not all
voices: the input's `Vocal` voice has no notes while the output's `Vocal` voice
often does, so using all voices would compare different things. `pc_all` is
kept as a diagnostic only.

### 9.2 Cheap metrics, all N² pairs

For each pair (i, j), with `a = features[i]`, `b = features[j]`:

| Group | Metric | Formula |
|---|---|---|
| global | `key_sim` | `1 − min(|fifths_i − fifths_j|, 6)/6` |
| | `tempo_sim` | `max(0, 1 − 2·|log2(t_i/t_j) − fold|)`, `fold = clip(round(log2 ratio), −1, 1)` |
| | `bar_length_sim` | `min/max(bar_sec)` |
| | `duration_sim` | `min/max(total_sec)` |
| harmony | `chord_vocab_wjaccard` | `Σ_k min(a_k,b_k) / Σ_k max(a_k,b_k)`, `a_k` = time share |
| | `chord_transition_f1` | F1 of chord-class bigram sets |
| | `chord_chroma_cos` | cosine of `chord_chroma` |
| melody | `pitch_class_cos` | cosine of `pc_hist` |
| | `interval_hist_cos` | cosine of `iv_hist` |
| | `register_sim` | `½(1 − min(|Δmean|,12)/12) + ½·min/max(span)` |
| rhythm | `density_sim` | `min/max(density)` |
| | `silence_ratio_sim` | `1 − |occ_i − occ_j|` |
| | `duration_hist_cos` | cosine of `dur_hist` |
| | `onset_phase_cos` | cosine of `onset_phase`, tempo-fold aligned |

Groups keep the oracle's weights: **global 0.15, harmony 0.30, melody 0.35,
rhythm 0.20**; group score = mean of its cheap metrics; composite = weighted
sum. `chord_chroma_cos` replaces `chord_timeline_dtw` in the cheap harmony
mean; the deep audit restores the DTW and four-gram terms exactly.

Vectorization:

- histograms → row-normalize `H (N×D)`, `S = H @ H.T` (one BLAS call each);
- ratios → `min(a[:,None], b[None,:]) / max(...)` broadcasting;
- `key_sim`, `tempo_sim` → broadcast on the 1-D global vectors;
- set F1 → sparse boolean `B (N×V)`; `inter = B @ B.T`; sizes from row sums;
- `float32`; process in row blocks of 256 when N > 2,000 to bound memory.

Memory at N=460: 460² × 4 B = 0.85 MB per metric; 14 metrics ≈ 12 MB, plus
the 460×460 composite. All-pairs output as parquet (~10–20 MB); the oracle's
CSV shape would be ~50 MB.

### 9.3 Exact report statistics (unchanged semantics, exact values)

- `base[m]` = mean of metric m over all off-diagonal pairs (was: mean over
  90 mismatched pairs for N=10; now exact over 459 per track).
- `metric_adj = clip((metric − base)/(1 − base), 0, 1)`.
- `composite`, `composite_adj`, `grp_*` exactly as the oracle.
- `retrieval_rank` = 1 + count of off-diagonal composites above the diagonal
  (exact 1..N).
- `lift_vs_mismatched` = diagonal − mean of the row's off-diagonal values.

### 9.4 Cohort calibration (replaces transplanted thresholds)

From the 460 matched values, per metric/group/composite:

- robust center and scale: median, MAD; `z = 0.6745·(x − median)/MAD`;
- empirical percentiles p01/p05/p50/p95/p99;
- stratum medians by `tier`, `country`, and duration quartile (from
  `tracks.jsonl`) — to confirm failures aren't a stratum artifact.

Flag policy (all thresholds CLI flags, defaults shown):

| Code | Rule |
|---|---|
| `missing-output` | no verified transcript |
| `parse-error` | `parse_abc` yields 0 notes |
| `truncated` | `duration_sim < 0.80` |
| `sparse` | note-count ratio < 0.60 |
| `no-chords` | output chord symbols == 0 |
| `key-drift` | `key_sim < 0.50` |
| `tempo-drift` | folded `tempo_sim < 0.50` |
| `cohort-outlier` | composite or any group < p05 of the cohort, or robust z < −3 |
| `not-distinctive` | `retrieval_rank > 100` of 460, or `lift < 0.10` |

Decision (same vocabulary as `regen_filter.py`, cohort-derived defaults):

- **REGENERATE** — any hard invariant (`truncated`, `sparse`, `no-chords`,
  `key-drift`, `tempo-drift`) **and** deep composite < 0.65 after escalation;
- **REVIEW** — cohort outlier or composite < p10;
- **KEEP** — otherwise.

### 9.5 Corpus-level verdict (paired permutation test)

For each track, `d_i = composite_matched_i − mean_{j≠i} composite_ij`.
Sign-flip permutation (10,000 draws) on the 460 `d_i` gives a p-value for
"matched beats chance"; report mean `d`, Cohen's `dz`, and the fraction of
tracks with `d_i > 0`. This replaces the 10-track "rank 1/10" anecdote with a
corpus-level effect size.

### 9.6 Escalation (flagged tracks only)

For each flagged track (expected 30–60):

1. **Banded DTW** on melody and chord chroma against its **own input only**:
   2.0 s frames (≈150 frames for 5 min), Sakoe–Chiba band ±10% of the longer
   sequence, `O(n·band)`. This tolerates drift **and** does not stretch a
   truncated output over the full input, which full DTW does.
2. **Deep oracle metrics** for that single pair via
   `analysis.vendor.abc_similarity.compare_features` (exact old definitions).
3. Report cheap vs deep side by side; only then apply the REGENERATE decision.

### 9.7 Deep audit (30 tracks, acceptance test for the proxy)

Stratified sample: 10 tracks from the low, 10 from the median, 10 from the
high band of `composite_cheap`. For each, run the full oracle 17-metric
`compare_features` on the matched pair.

**Acceptance:** Spearman ρ(cheap composite, deep composite) ≥ 0.85. If lower,
widen the audit to 60 tracks and adjust the cheap group members before
trusting corpus-wide numbers. The audit table is a deliverable either way.

---

## 10. Phase 5 — report and deliverables

### 10.1 Local run directory

```
work/yt500_abc/
  inventory.json, pairs.json, cohort.json, failures.json
  input/<name>.input.abc                 # conditioning score (role: input)
  output/<name>.output.abc               # SheetSage2 transcript (role: output)
  transcripts/<name>/score.abc           # transcribe.py working tree (unpublished)
  similarity/
    matched_pairs_scores.csv    460 rows: input_sha256, output_sha256, groups,
                                14 cheap metrics, composite, composite_adj,
                                rank, lift, z-scores, flags
    all_pairs.parquet           211,600 rows x 14 cheap metrics (plus row/col ids)
    baseline_mismatched_mean.csv
    cohort_stats.json           median/MAD, percentiles, strata, p-value, dz
    flags.csv                   name -> codes, reasons, decision
    escalation.csv              flagged: banded DTW, deep 17-metric values
    audit_30.csv                cheap vs deep, rho/r
    summary.md                  corpus verdict, distributions, worst 20,
                                failure taxonomy, stratum table
    distributions.png           composite + group histograms, rank histogram
```

Every CSV and the summary carry the side labels explicitly: `input` =
conditioning score, `output` = transcript of generated audio. No deliverable
column or path is called just `score`. The `matched_pairs_scores.csv` also
carries `input_sha256`/`output_sha256` so any row can be re-derived from the
durable bundle without ambiguity.

### 10.2 GCS bundle (two prefixes, different lifetimes)

**Durable transcript dataset** — the expensive output; reusable independently
of this study. Everything is named by role:

```
gs://akbar-december-2024-backup/DATASET/yt500_instrumental_transcripts/
  <name>.output.abc                             # flat mirror, no untar needed
  <name>.output.meta.json                       # role=output + input/audio hashes
  archives/<name>.output-transcript.tar.gz      # complete transcript dir
  archives/_archive_index.json                  # sha256 + fingerprint per track
  manifest.jsonl                                # name, role, hashes, model, mode
  _STATE.json                                   # target/ok/failed/accounted/complete
  SHA256SUMS, README.md, DATASET_CARD.md
  _SUCCESS                                      # ONLY when accounted >= target
  _PARTIAL.json                                 # otherwise (with counts)
```

Completion markers are not progress logs: publish `_SUCCESS` only when the
cohort is accounted for (`ok + failures >= 460`); while a run is in flight
write `_STATE.json` and `_PARTIAL.json`, and delete any stale `_SUCCESS`. A
watcher must never finalize the analysis below the cohort gate.

The dataset card opens with the disambiguation, verbatim:

> **This is the OUTPUT side.** Every `*.output.abc` here is a SheetSage2
> transcript of the generated instrumental audio. The **INPUT** scores are the
> conditioner: `gs://…/DATASET/yt500_instrumental/tracks/<name>/score.abc`.
> Match them by `<name>`; `output.meta.json` records `input_sha256`.

**Analysis products** — cheap to regenerate:

```
gs://akbar-december-2024-backup/ANALYSIS/yt500_instrumental_abc/
  input/<name>.input.abc                        # copy of the conditioning scores
  similarity/…                                  # as in §10.1
  sessions/<utc>/{_driver.log,_timings.csv,transcribe_manifest.json}
  SHA256SUMS, README.md
```

Both prefixes are configurable (`--dataset-prefix`, `--analysis-prefix`); the
source dataset is never modified. The output bundle is documented as its own
reusable dataset (ABC + full side artifacts + provenance), so no later task has
to pay the transcription cost again.

### 10.3 Decision-facing outputs

- headline corpus numbers: median composite, IQR, matched-vs-chance effect
  size/p, % of tracks with rank 1, % flagged per reason;
- the ordered `flags.csv` (worst first) as the regeneration shortlist;
- `summary.md` one paragraph per reason code with 2–3 example track names.

---

## 11. Scale and cost budget

Measured unless marked *est.*

| Stage | Work | Hardware | Time |
|---|---|---|---|
| Phase 0 inventory + hashes | 460 small files | local CPU | < 1 min |
| Phase 0 prototype + parity | 489² cheap matrix | local CPU | ~1–2 min |
| Phase 1 probe | 3 tracks | Colab GPU | ~5–10 min |
| Phase 2 transcription | 460 × ~51 s | Colab GPU | **~6.5 h** (3 sessions) |
| Phase 3 pairs + validation | 460 parses | local CPU | < 10 s |
| Phase 4 features | 460 parses | local CPU | ~5 s |
| Phase 4 cheap all-pairs | 211,600 pairs × 14 metrics | BLAS, 1 core | *est.* 20–60 s |
| Phase 4 cohort + permutation | 460×3 stats, 10k sign flips | local CPU | < 5 s |
| Phase 4 escalation | ~50 × banded DTW + deep | local CPU | < 10 s |
| Phase 4 audit | 30 × full oracle | local CPU | ~1 s |
| **Comparison total** | | **no GPU** | **< 2 min** |

Peak RAM *est.* < 300 MB at N=460. Growth path: at N=5,000 keep the features
and retrieval matmul, block the pair matrix (256 rows), and switch the chance
baseline to a fixed decoy set; the deep path stays sample-based.

Storage: input scores ~1.5 MB; **full output transcripts measured at 1.58 MB/track
raw → ~0.73 GB for 460, ~50–80 MB gzipped**. Persist all of it. One
re-transcription (~6.5 GPU-hours) costs orders of magnitude more than the
storage, so storage is never the constraint to optimize.

---

## 12. Failure modes

| Failure | Symptom | Mitigation |
|---|---|---|
| MP3 staging names collide | all stems `audio` | flatten to `<name>.mp3` (§7.1) |
| `--limit` used for chunks | resume never advances | use `--time-budget` + hash skip (§7.2) |
| Torn transcript uploaded | `skipped-unverified` forever | archive only `status=ok` + hash-verified dirs (`transcript_archive.is_complete`) (§7.3) |
| Artifacts dropped to save space | a later task forces a full re-transcription | persist the complete dir as `<name>.tar.gz` + flat ABC/meta mirror (§7.3) |
| Remote archive overwritten/lost | provenance gap, silent data loss | `push` never deletes or clobbers; sha256 match = skip (§7.3) |
| MP3 re-encoded during staging | source hash changes, mass re-run | copy bytes; never transcode (§7.1) |
| SheetSage2 `no-abc` | no output for a track | retry, then MP3→WAV, then `missing-output` (§7.4) |
| No chord symbols in output | harmony group = 0 | `no-chords` flag; deep escalation decides (§9.4) |
| Output `Vocal` has notes, input's does not | melody metrics compare different things | primary-line melody features (§9.1) |
| DTW stretches truncated output | false "moderate" score | duration/note gates + banded DTW only (§9.6) |
| Thresholds from n=10 over-flag | mass REVIEW/REGENERATE | cohort percentiles + MAD (§9.4) |
| Parser chokes on output ABC | crash mid-corpus | parse per track, collect failures, never abort (§8) |
| Colab VM dies mid-session | lost work | 5-min push + hash-skip resume (§7.3) |

---

## 13. Command appendix

```bash
# ---- Phase 0 (local) ----
python3 plumbing/stage_yt500_transcription.py --inventory-only \
  --out work/yt500_abc/inventory.json

python3 analysis/run_yt500_similarity.py self-test \
  --input-dir work/yt500_abc/input \
  --transcripts work/yt500_abc/transcripts \
  --out work/yt500_abc/self_test
# dev-only deep-parity extra flags: --corpus scores/yt500_instrumental
#   --pairs-local local_workspace/…/scores --transcripts-fadhl ~/fadhl_selected_scores
# On Colab: self-test on work/yt500_abc/input and the Phase-1 probe pairs.

# ---- Phase 2 (Colab) ----
./plumbing/setup_transcribe.sh --cuda
python3 plumbing/stage_yt500_transcription.py \
  --inventory work/yt500_abc/inventory.json \
  --audio-dir /content/yt500/audio --input-dir /content/yt500/input

python3 plumbing/yt500_transcribe_sync.py pull   # resume
nohup bash -c 'while sleep 300; do python3 plumbing/yt500_transcribe_sync.py push; done' &
./transcribe.sh /content/yt500/audio \
  --out-dir /content/yt500/transcripts \
  --full --device auto --threads 4 --time-budget 7200
python3 plumbing/yt500_transcribe_sync.py push
./transcribe.sh /content/yt500/audio \
  --out-dir /content/yt500/transcripts --verify

# ---- Phase 3-5 (local) ----
python3 analysis/run_yt500_similarity.py run \
  --input-dir work/yt500_abc/input \
  --transcripts work/yt500_abc/transcripts \
  --inventory work/yt500_abc/inventory.json \
  --out work/yt500_abc/similarity \
  --audit 30 --permutations 10000 --blocks 256
```

---

## 14. Files to add

| File | Role |
|---|---|
| `analysis/vendor/abc_similarity.py` | verbatim oracle (parser + deep metrics) |
| `analysis/vendor/regen_filter.py` | verbatim decision reference |
| `analysis/abc_scale.py` | features, vectorized cheap matrices, banded DTW |
| `analysis/abc_calibrate.py` | baseline, adj, rank, lift, cohort stats, permutation, flags |
| `analysis/run_yt500_similarity.py` | CLI: `self-test`, `build-pairs`, `run`, `report` |
| `plumbing/stage_yt500_transcription.py` | inventory + flatten audio + input scores |
| `plumbing/yt500_transcribe_sync.py` | thin wrapper over `transcript_archive.py`: `push` full archives + flat mirror + session logs, `pull`, `verify` |
| `tests/test_abc_scale.py` | identity, scalar↔matrix parity, invariance, truncation, runtime |

Nothing in `transcribe.py`, `generate.py` or the dataset needs to change.

---

## 15. Acceptance criteria

1. **Phase 0:** identity = 1.0; scalar↔matrix 1e-6; ρ(cheap, deep) ≥ 0.85 on
   the 11 local pairs; 489² ≤ 120 s.
2. **Phase 1:** 3/3 parse; median ≤ 120 s/track; chords in ≥ 2/3.
3. **Phase 2:** ≥ 95% of 460 verified; local == GCS transcript set; every
   finished track has a verified `<name>.output-transcript.tar.gz` plus a flat
   `<name>.output.abc` / `<name>.output.meta.json` in the dataset prefix, and
   `transcript_archive.py --verify` reports 0 bad; every failure has an error
   string and a retry attempt.
4. **Phase 3:** cohort size + failure list == 460; no silent parse drops;
   `input_sha256 != output_sha256` on every row; no published path or report
   column is named just `score`.
5. **Phase 4:** matched table covers the whole cohort; every flag has a reason
   code; all-pairs row count == N_ok²; audit ρ ≥ 0.85.
6. **Phase 5:** `summary.md` states the corpus verdict with effect size and
   p-value, the reason-code breakdown, and the top-20 worst tracks; the GCS
   bundle verifies against `SHA256SUMS`.
7. **Reproducibility:** Phases 3–5 re-run from the GCS bundle with the three
   commands in §13.

---

## 16. Open decisions (defaults chosen)

| # | Decision | Default |
|---|---|---|
| 1 | Comparison scope | **all 460** (cheap matrix makes sampling pointless). A stratified 120-track sample would cut GPU time to ~1.7 h if a corpus verdict is enough. |
| 2 | Transcription mode | **`--full`** (chords needed for harmony), as in the proven Fadhl run. |
| 3 | GCS prefixes | transcripts `DATASET/yt500_instrumental_transcripts/`, analysis `ANALYSIS/yt500_instrumental_abc/`. Input stays `DATASET/yt500_instrumental/`. |
| 4 | Backup scope | **full transcript dir per track** (`<name>.output-transcript.tar.gz` + `<name>.output.abc`/`.output.meta.json` + per-session logs); never delete or overwrite remote. |
| 5 | Audit size | 30, widen to 60 if ρ < 0.85. |
| 6 | Decision thresholds | CLI flags; defaults from cohort percentiles (§9.4), not the 10-track constants. |
| 7 | Side naming | input = `*.input.abc` (only the read-only dataset keeps `score.abc`); output = `*.output.abc`; assert `input_sha256 != output_sha256`. |

---

## Appendix A — feature vector layout

```
global   : fifths(f32), tempo(f32), bar_sec(f32), total_sec(f32)
melody   : pc_hist[12], iv_hist[25], mean_pitch, pitch_span
harmony  : chord_time[k] (vocab dict), chord_chroma[12]
rhythm   : density, silence_ratio, dur_hist[16], onset_phase[8]
audit    : interval_4grams(set), chord_bigrams(set), rhythm_4grams(set)
          + cached chroma frames for DTW (built only during escalation)
```

## Appendix B — deep metric inventory (audit/escalation only)

`chord_timeline_dtw`, `melody_chroma_dtw`, `interval_4gram_f1`,
`rhythm_4gram_f1`, plus the diagnostic section-boundary F1. These are the four
oracle metrics removed from the production path; the audit restores them
unmodified and the escalation computes the two DTWs at 2 s / banded resolution.

## Appendix C — reason codes

`missing-output`, `parse-error`, `truncated`, `sparse`, `no-chords`,
`key-drift`, `tempo-drift`, `cohort-outlier`, `not-distinctive`.
Decision mapping: hard invariant + deep < 0.65 → REGENERATE; cohort outlier or
composite < p10 → REVIEW; otherwise KEEP.
