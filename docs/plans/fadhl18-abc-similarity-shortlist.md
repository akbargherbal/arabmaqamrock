# Fadl Shaker Instrumental 18 — ABC similarity shortlist plan

Status: **plan only** (no shortlist executed yet).
Target dataset (read-only):
`gs://akbar-december-2024-backup/DATASET/fadhl_shaker_instrumental_18/`
Proposed branch: `feat/fadhl18-abc-shortlist`
Parent code: `feat/yt500-abc-similarity` (reuses `analysis/run_yt500_similarity.py`
and the generic analysis publisher).

## 1. Goal

Shortlist the generated tracks whose **SheetSage2 output ABC** is acceptably
similar to the **reference ABC used as the generation conditioner**.

This is an input-vs-output comparison only. It does **not** regenerate audio,
re-transcribe, or modify the dataset. The eventual merge into the YT500 ABC
cohort is a separate, later phase.

## 2. Verified starting facts (2026-11-12)

- Cohort size: **24 tracks** (so the answer is necessarily `< 30`).
- Every track has:
  - `abc/<name>.abc` — reference/conditioner score (the **input** side)
  - `abc_transcription/<name>.abc` — SheetSage2 `--full` transcript (the
    **output** side)
  - `captions/<name>.json`, `tracks.jsonl` / `tracks.parquet`, `manifest.json`
- `tracks.jsonl` rows carry `abc_reference_sha256`,
  `abc_transcription_sha256`, `audio_sha256`, `duration_s`, `run_id`,
  `track_id`, `seed`.
- `manifest.json` says `abc_transcription_parse.ok = 24`, all captions and
  both ABC sides present.
- Base names are unique (24/24); filenames add the seed, e.g.
  `al_dawr_ala_meen_1678957498`.
- 23 tracks carry `vocal_sparse`; this is expected for an instrumental run and
  is **not** a transcription or similarity failure.
- No audio download is needed for this comparison. The MP3s remain referenced
  by GCS URI + SHA-256.

## 3. What "qualifies" means

Use the YT500 decision rules for comparability, plus an absolute floor because
a 24-track cohort makes p05/p10 and robust-z unstable.

A track is **shortlisted** only when all are true:

1. `decision in {KEEP, REVIEW}` from the standard flag logic, i.e. it is not
   `REGENERATE`;
2. cheap `composite >= 0.85` (the observed minimum of YT500 `KEEP` rows);
3. deep/oracle `deep_composite >= 0.65` (same hard-reject floor as YT500).

Buckets written to the JSON:

| bucket | rule |
|---|---|
| `qualify` | `decision != REGENERATE` AND `composite >= 0.85` AND `deep_composite >= 0.65` |
| `borderline` | not qualify, not REGENERATE, and `composite >= 0.75` |
| `reject` | `decision == REGENERATE`, or `composite < 0.75`, or deep `< 0.65` |

Existing reason codes are preserved (`truncated`, `sparse`, `no-chords`,
`key-drift`, `tempo-drift`, `cohort-outlier`, `not-distinctive`,
`empty-input`). The shortlist is the `qualify` bucket; `borderline` is kept in
a separate array for manual review, not in the shortlist.

For N=24, `--audit 30` samples all 24 tracks (3 bands × 8), so every row gets a
deep composite and the cheap-vs-deep Spearman is computed over the full cohort.

## 4. Naming and future merge contract

- Working name now: the existing filename stem, e.g.
  `al_dawr_ala_meen_1678957498`.
- Merge-safe ID to write into the shortlist now: `fs18-<stem>` (example
  `fs18-al_dawr_ala_meen_1678957498`). This guarantees no collision with
  `yt500-…` names.
- Preserve `source_dataset: fadhl_shaker_instrumental_18`, `source_run_id`,
  `source_track_id` and all three SHA-256 values. Do not rename the GCS source
  objects.
- When the later merge happens, union this shortlist with the YT500
  `KEEP/REVIEW` shortlist, carry `source_dataset`, and re-run the combined
  analysis. Per-dataset shortlists remain provenance, not the merged cohort.

## 5. Work layout (all under the gitignored `work/` tree)

```
work/fadhl18/
  tracks.jsonl                 # copy of dataset tracks.jsonl
  inventory.json               # 24 rows for the analysis runner
  input/<name>.input.abc       # downloaded reference ABCs
  transcripts/<name>/score.abc # downloaded output ABCs
  transcripts/<name>/meta.json # synthesized verified-output sidecar
  similarity/                  # analysis products
  shortlist_keep_review.json   # generated shortlist (also copied to repo)
```

Do **not** reuse `work/yt500_abc/`: its `failures.json`, `pairs.json` and
`cohort.json` belong to the YT500 cohort.

## 6. Execution phases

### Phase 0 — provenance and readiness (CPU, <1 min)

1. Download `tracks.jsonl` and `manifest.json` (plus the 48 ABCs).
2. Verify every reference and every transcription SHA-256 against
   `tracks.jsonl`; require **48/48** matches.
3. Confirm the reference and transcription stem sets are identical
   (**24/24**), no duplicates.
4. Run an ABC parse check (`X:` and `K:` present) on all 48 files; require
   **48/48**.

Gate: stop if any hash or parse check fails. The dataset prefix is never
written to.

### Phase 1 — stage the standard layout

1. Copy each `abc/<stem>.abc` to `input/<stem>.input.abc`.
2. Copy each `abc_transcription/<stem>.abc` to `transcripts/<stem>/score.abc`.
3. Synthesize `transcripts/<stem>/meta.json` from the `tracks.jsonl` row:

```json
{
  "status": "ok",
  "role": "output_transcript",
  "name": "<stem>",
  "abc_sha256": "<abc_transcription_sha256>",
  "input_sha256": "<abc_reference_sha256>",
  "source_wav_sha256": "<audio_sha256>",
  "input_uri": "gs://…/DATASET/fadhl_shaker_instrumental_18/abc/<stem>.abc",
  "audio_uri": "<gs_uri from tracks.jsonl>",
  "output_abc": "<stem>.output.abc",
  "transcriber": "m-a-p/SheetSage2",
  "source_dataset": "fadhl_shaker_instrumental_18"
}
```

4. Build `inventory.json` with one row per track:
   `name`, `input_sha256`, `nominal_s`/`wav_s` from `duration_s`, plus
   `source_dataset`, `source_run_id`, `source_track_id`. Omit `tier`/`country`
   unless a real value exists; do not invent metadata.

Gate: 24 inventory rows, 24 input files, 24 transcript directories.

### Phase 2 — run the existing analysis (CPU, seconds)

```bash
python3 analysis/run_yt500_similarity.py run \
  --input-dir work/fadhl18/input \
  --transcripts work/fadhl18/transcripts \
  --inventory work/fadhl18/inventory.json \
  --out work/fadhl18/similarity \
  --work work/fadhl18 \
  --audit 30 --permutations 10000 --blocks 64
```

Expected: `cohort 24 / 24 (missing=0, parse errors=0)`, audit `n=24`,
all-pairs rows 576, parity within `1e-6`.

Read `work/fadhl18/similarity/summary.md` and `cohort_stats.json` before
writing the shortlist; confirm no hash collisions and a sane deep/cheap
correlation. Because N=24, do not treat p05/p10 as calibrated population
thresholds; the absolute floor in §3 is primary.

### Phase 3 — write the shortlist JSON

Generate `work/fadhl18/shortlist_keep_review.json` and copy it to
`docs/plans/fadhl18-abc-shortlist-keep-review.json`.

Top level:

```json
{
  "title": "Fadl Shaker Instrumental 18 — ABC similarity shortlist",
  "generated_at": "...Z",
  "commit": "<sha>",
  "source_dataset": "gs://…/DATASET/fadhl_shaker_instrumental_18",
  "source_run_id": "20261110-050958_fadhl_shaker_instrumental_18",
  "criteria": {
    "qualify": "decision != REGENERATE AND composite >= 0.85 AND deep_composite >= 0.65",
    "borderline": "not qualify, not REGENERATE, composite >= 0.75",
    "reject": "REGENERATE or composite < 0.75 or deep < 0.65",
    "yt500_decision_rules": { "...": "same thresholds as YT500" }
  },
  "counts": {"cohort": 24, "qualify": 0, "borderline": 0, "reject": 0},
  "sources": {"flags_csv": {"uri": "...", "sha256": "..."},
              "matched_pairs_scores_csv": {"uri": "...", "sha256": "..."},
              "cohort_stats_json": {"uri": "...", "sha256": "..."},
              "tracks_jsonl": {"uri": "...", "sha256": "..."}},
  "tracks": [
    {
      "name": "fs18-<stem>",
      "source_name": "<stem>",
      "decision": "KEEP",
      "qualify": true,
      "composite": 0.0,
      "composite_z": 0.0,
      "retrieval_rank": 0,
      "lift_vs_mismatched": 0.0,
      "codes": "-",
      "deep_composite": 0.0,
      "duration_s": 0.0,
      "grp_global": 0.0, "grp_harmony": 0.0,
      "grp_melody": 0.0, "grp_rhythm": 0.0,
      "input_sha256": "...", "output_sha256": "...", "audio_sha256": "..."
    }
  ],
  "excluded": {
    "borderline": [{"name": "...", "composite": 0.0, "why": "..."}],
    "reject": [{"name": "...", "composite": 0.0, "why": "..."}]
  }
}
```

Invariant: `qualify + borderline + reject == 24`; every `qualify` row has all
three hashes and `deep_composite` is finite.

### Phase 4 — publish the analysis products

Durable prefix (new; does not touch the dataset):

```
gs://akbar-december-2024-backup/ANALYSIS/fadhl_shaker_instrumental_18_abc/
  input/<name>.input.abc
  similarity/{matched_pairs_scores.csv,flags.csv,cohort_stats.json,summary.md,
              all_pairs.parquet,audit_30.csv,distributions.png,
              shortlist_keep_review.json}
  shortlist_keep_review.json
  pairs.json cohort.json failures.json
  README.md SHA256SUMS _SUCCESS
```

Reuse the generic analysis publisher:

```bash
python3 plumbing/publish_yt500_bundle.py analysis \
  --input-dir work/fadhl18/input \
  --similarity work/fadhl18/similarity \
  --work work/fadhl18 \
  --prefix gs://akbar-december-2024-backup/ANALYSIS/fadhl_shaker_instrumental_18_abc \
  --staging work/fadhl18/publish_bundle/analysis \
  --commit "$(git rev-parse --short HEAD)"
```

Before running it, either add an optional `--label`/`--title` flag so the
README does not say "YT500", or overwrite the generated README with a
dataset-specific one. Keep `SHA256SUMS` covering every uploaded object and
verify with `sha256sum -c` after download.

### Phase 5 — optional confidence checks (not required)

- Spot-check 3 tracks: cheap composite vs deep composite delta, note counts,
  duration ratio, key/tempo similarity.
- Optional GPU re-transcription of 3 tracks (~25 s each) to confirm the
  published `abc_transcription` matches a fresh SheetSage2 run. This is a
  sanity check only; the published transcriptions are already the comparison
  target.

## 7. Final gates

1. 48/48 source ABC hashes match `tracks.jsonl`.
2. 24/24 pairs parse; `build-pairs` reports 0 missing, 0 parse errors,
   0 hash collisions.
3. Analysis cohort = 24/24; audit `n=24`; cheap/deep Spearman reported.
4. Shortlist JSON: `qualify + borderline + reject == 24`; counts in the file
   match the arrays; all shortlisted rows have finite `deep_composite` and
   all three hashes.
5. Analysis bundle `SHA256SUMS` verifies and `_SUCCESS` exists.
6. No object under `DATASET/fadhl_shaker_instrumental_18/` was created,
   modified, or deleted.
7. Repo contains `docs/plans/fadhl18-abc-shortlist-keep-review.json` and a
   short run-log entry; both committed and pushed.

## 8. Effort

- CPU-only: download <1 min, staging seconds, analysis <1 min, publish <1 min.
- No GPU, no model download, no audio download.
- Expected result: some subset of 24; the plan does not assume the number.
  Given the YT500 median composite 0.921, most tracks are expected to qualify,
  but a hard `key-drift`/`tempo-drift`/`sparse` track must be rejected even if
  it is a minority.

## 9. Risks / decisions to confirm before execution

1. **Small-n calibration** — absolute composite/deep floors are primary; the
   YT500 percentile rules are reported but not trusted at N=24.
2. **Threshold ownership** — `0.85` / `0.65` / `0.75` are inherited from the
   YT500 observed KEEP floor and hard-reject floor. If the operator prefers a
   different acceptance bar, change it in Phase 3 only; the raw scores are
   unchanged.
3. **Transcription trust** — the plan trusts the dataset's published
   `abc_transcription` files and verifies their hashes; it does not re-run the
   model unless Phase 5 is requested.
4. **Merge naming** — `fs18-` prefix is a proposal; confirm before the first
   merged manifest is written.
5. **`vocal_sparse`** — ignored for this decision; it is expected for
   instrumentals and is not a similarity metric.

## 10. Later merge (out of scope here)

When ready:
1. Take only `qualify` rows (plus any manually promoted `borderline`).
2. Map to `fs18-<stem>` IDs, carry `source_dataset`, `source_run_id`,
   `source_track_id`, input/output/audio hashes and URIs.
3. Append to the merged cohort manifest; keep the per-dataset shortlist as
   provenance.
4. Re-run the combined similarity analysis so cohort-relative stats are
   computed on the merged population, not on either subset alone.
