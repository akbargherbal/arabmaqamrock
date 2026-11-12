# YT500 input-vs-output ABC similarity — run log

Branch: `feat/yt500-abc-similarity`
Started: 2026-11-11 (Colab L4, 12 vCPU, 236 GB disk)
Dataset: `gs://akbar-december-2024-backup/DATASET/yt500_instrumental/` (read-only)
Durable outputs: `gs://akbar-december-2024-backup/DATASET/yt500_instrumental_transcripts/`
Analysis bundle: `gs://akbar-december-2024-backup/ANALYSIS/yt500_instrumental_abc/`

## Phase 0 — inventory, self-test

- 460/460 input `score.abc` sha256 match
  `outputs/YT500/generation/index.json` → `instrumental_abc_sha256`.
- 4 inputs have zero melody notes (rests/chords only); kept in the cohort and
  flagged `empty-input`.
- Self-test on the 460 role-labelled inputs (`work/yt500_abc/input`):
  - identity: **1.0** for all 14 cheap metrics;
  - scalar ↔ matrix parity: **3.68e-07** (300 pairs, gate 1e-6);
  - 460×460 matrix: **0.09 s** (gate 120 s).
- Vendored oracle committed by `c0f9e70`; no code edits to it.

## Phase 1 — 3-track probe

Shortest / median / longest by `nominal_s`:

| track | nominal_s | seconds | notes | chords | duration vs wav_s |
|---|---:|---:|---:|---:|---:|
| yt500-0504-BWveNYQDmF4 | 142.7 | 34.7 | 366 | 97 | +2.2% |
| yt500-0380-F7BKcTNNvIc | 276.7 | 40.2 | 857 | 153 | +1.3% |
| yt500-0120-rjw-rOsZMis | 418.2 | 59.5 | 1378 | 386 | +0.2% |

Gate: 3/3 `ok`, median **40.2 s/track** (≤120), chords **3/3**. PASS.
Cheap composites 0.845 / 0.970 / 0.819; deep 0.825 / 0.949 / 0.748.

## Phase 2 — bulk transcription

- Model `m-a-p/SheetSage2`, revision `b83c3d79…`, `--full`, `device=cuda`,
  `dtype=bf16`, `--threads 4`, `--time-budget 7200`, no `--limit`.
- 460 MP3s staged byte-exact and flattened to `/content/yt500/audio/<name>.mp3`;
  inputs to `/content/yt500/input/<name>.input.abc`.
- Push loop every 5 min: exporter recovery → verified push (flat role-labelled
  mirror + full archives) → dataset docs/manifest/SHA256SUMS.
- Measured steady state ≈ 25–40 s/track; early observed failures were
  deterministic exporter edge cases, recovered from the model's own
  `notation/` exports:
  - a final sub-beat note that cannot be quantised → drop that trailing note;
  - one dropped beat row → insert the missing sequential beat.
  Recovered tracks keep `meta.pre-recovery.json` and `recovered: true`.
- Failures that cannot be recovered remain `missing-output` with the error.

## Naming contract (4facb4a)

- `score.abc` exists only as the read-only dataset input.
- Local input `input/<name>.input.abc`; local output
  `output/<name>.output.abc`.
- Published output `<name>.output.abc` + `<name>.output.meta.json`
  (`role: output_transcript`, input/audio hashes and URIs).
- Archives `archives/<name>.output-transcript.tar.gz`.
- `build-pairs` aborts on `input_sha256 == output_sha256`.

## Phase 3–5

Run by `plumbing/finalize_yt500_similarity.sh` when the watcher sees ≥437
verified outputs (or both transcription jobs exit):

```bash
python3 analysis/run_yt500_similarity.py run \
  --input-dir work/yt500_abc/input \
  --transcripts /content/yt500/transcripts \
  --inventory work/yt500_abc/inventory.json \
  --out work/yt500_abc/similarity \
  --work work/yt500_abc \
  --audit 30 --permutations 10000 --blocks 256
```

Deliverables and the final numbers are in
`work/yt500_abc/similarity/summary.md` and the analysis GCS prefix.

## Resume — 2026-11-11 20:05Z (fresh Colab L4 VM)

- Remote at resume: 71 flat `.output.abc` (65 with archives); `_PARTIAL` said
  65 because the six tracks `yt500-0088…0098` were uploaded flat but their
  archives were not yet written. `pull` + `verify` recovered all **71 verified**;
  the next push wrote their archives (remote archives 71).
- Inventory rebuilt: **460/460** input sha256 verified.
- Audio re-staged byte-exact: **460/460** (2.9 GB), inputs 460/460.
- Phase 0 self-test re-passed on this VM: identity **1.0**, scalar↔matrix
  **3.677e-07**, 460² matrix **0.16 s**.
- `recover_yt500_abc.py` had a latent `FileExistsError`: it pre-creates
  `__init__.py` in the temp package and then symlinks every `*.py`. Fixed
  (`f2233f0`) to skip already-materialised files; recovery now runs clean.
- Work isolation: an unrelated agent sharing the VM switched the primary
  checkout to `main` mid-setup. This run continues in a dedicated git worktree
  of `feat/yt500-abc-similarity`; `/content/yt500/transcripts` is unchanged.
- Supervisor (`TARGET=460`, `TIME_BUDGET=7200`), 120 s recovery→push→publish
  loop, and watcher (`TARGET=437`) launched 20:05Z.

### Progress checkpoints (resume)

| UTC | verified | remote | new | median s | failures |
|---|---:|---:|---:|---:|---|
| 20:23 | 109 | 109 | 38 | 26.0 | 0 (STABLE) |
| 20:50 | 162 | 157 | 91 | 27.1 | 1 `no-abc` (`yt500-0208`, recovery attempted, not recoverable) |
| 21:13 | 212 | 210 | 141 | 26.4 | 2 `no-abc` (`yt500-0208`, `yt500-0277`) |
| 21:38 | 264 | 262 | 193 | 26.1 | 3 `no-abc` (`…0208`, `…0277`, `…0329`) |
| 22:02 | 317 | 317 | 246 | 25.9 | 5 `no-abc` (adds `…0388`, `…0457`) |

**Stopped for VM shutdown at 22:02Z.** Clean stop: GPU job frozen, loops
stopped, final push+verify+publish completed; local verified == remote ==
archives == **317**, `_STATE`/`_PARTIAL` accounted 317, no `_SUCCESS`.
Resume from `docs/runbooks/yt500-abc-similarity-resume.md`; 138 tracks remain
plus the 5 known failures. Analysis gate is still ≥437.

The `yt500-0181` and `yt500-0214` `no-abc` exporter cases were auto-recovered
(`drop.tail-note`); recovery runs every 120 s and is idempotent.


## Resume — 2026-11-12 06:22Z (fresh Colab L4 VM)

Starting state re-verified before launching (not assumed):

- Branch `feat/yt500-abc-similarity` at `142eeb4`.
- Remote flat `.output.abc` **317**, remote archives **317**, `_SUCCESS`
  absent, `_STATE`/`_PARTIAL` `ok=317 failed=0 accounted=317 target=460
  complete=false`.
- Inventory rebuilt: **460/460** input sha256 match.
- `pull` recovered **317** verified; `verify` **317/317**, exit 0.
- Audio re-staged byte-exact **460/460** (2.9 GB), inputs 460/460.
- CUDA env rebuilt: torch **2.8.0+cu126**, CUDA available (NVIDIA L4).

**Publisher defect fixed before launch.** `analysis/run_yt500_similarity.py`
writes `failures.json` as `{"missing": [...], "parse_errors": [...]}` but
`publish_yt500_bundle.py` only read `payload["failures"]`, so `failed` was
always 0: at 455 ok it computed `accounted=455 < 460`, wrote `_PARTIAL`, and
never wrote `_SUCCESS`. `failure_names()` now normalizes bare lists,
`{"failures": [...]}`, and the analysis `missing`/`parse_errors` shapes
(deduped by name), so the finalizer can close the cohort at `ok+failed == 460`.

Launched 06:22Z: supervisor `TARGET=460 TIME_BUDGET=7200`, recovery→push→publish
loop every 120 s, watcher `TARGET=437`.

### Progress checkpoints (resume 2)

| UTC | verified | remote | new | median s | failures |
|---|---:|---:|---:|---:|---|
| 06:46 | 356 | 351 | 39 | 28.6 | 6 `no-abc` (5 known + `…0471`, `AbcRebuildError`); `…0503` recovered `drop.tail-note` |
| 07:01 | 388 | 386 | 71 | 27.1 | 7 `no-abc` (adds `…0471`, `…0579`) |
| 07:35 | 452 | 452 | 135 | 26.0 | 8 `no-abc`; pass 460/460, supervisor exited (`no progress`), watcher finalized |

## Final — cohort closed 2026-11-12T07:43Z

**Starting → final:** 317 verified / 0 failed → **452 published + 8 failed =
460 accounted**, `complete: true`, `_SUCCESS` present, `_PARTIAL.json` gone.
Remote flat `.output.abc` = meta = archives = manifest = **452**; SHA256SUMS
**1356/1356 OK** (`sha256sum -c`). Local `verify`: total 460, verified 452,
archives_ok 452, **archives_bad 0**. Analysis bundle SHA256SUMS **473/473 OK**.

- Wall clock: launch 06:22Z → `_SUCCESS` 07:38Z (**76 min**); transcription
  session 1 06:22–07:30 (67 min) attempted 143 tracks including the retries,
  ≈**28 s/track**; median transcript time **26.0 s**.
- Recovered from exporter bugs by the 120 s loop: **7** tracks
  (`drop.tail-note` etc., including `…0181`, `…0214`, `…0503`).
- **8 irrecoverable failures**, all `no-abc` (`SheetSage2 produced no .abc`):
  `yt500-0208-G8CygooGxFE`, `yt500-0277-89bDyAU6Wfg`,
  `yt500-0329-NlwSdL64lIc`, `yt500-0388-Gst0fsBDOUA`,
  `yt500-0457-Q7c_ExWZDRw`, `yt500-0471-3ZljEHI4RCo`,
  `yt500-0579-JEq8MHpjS2k`, `yt500-0635-rlxEW1UqPWY`.
  (Beyond the 5 known: `…0471` fails ABC rebuild on a sub-beat interval;
  `…0579` and `…0635` produced no ABC and recovery could not repair them.)

### Analysis headline (cohort 452 / 460)

| metric | value |
|---|---:|
| median composite | **0.921** (IQR 0.060) |
| mean matched−chance d | **0.340** |
| Cohen dz | **5.012** |
| sign-flip p (10,000) | **9.999e-05** |
| fraction d > 0 | **0.991** |
| retrieval rank-1 | **94.0%** (425/452) |
| deep-audit Spearman ρ | **0.925** (n=30) |
| decisions | KEEP 379, REVIEW 75, REGENERATE 6 |

- Code commit used for the analysis: **`460a31d`** (publisher
  `failure_names()` fix included; analysis records this in
  `cohort_stats.json` / bundle `_SUCCESS`).
- Both bundles republished at 07:42Z with `--commit 460a31d`; the stale
  `STABLE.json` (109-track gate, old VM PIDs) was removed from the analysis
  prefix.
- Final state is reproducible from this branch + GCS; no `/content` state is
  required.

### Shortlist — KEEP/REVIEW only (2026-11-12T07:50Z)

- File: `docs/plans/yt500-abc-shortlist-keep-review.json` (tracked) and
  `ANALYSIS/yt500_instrumental_abc/similarity/shortlist_keep_review.json`
  (identical, hashed in the analysis bundle).
- **446 tracks shortlisted: KEEP 379 + REVIEW 67.** Excluded by design:
  **6 REGENERATE** (`…0149`, `…0247`, `…0311`, `…0378`, `…0439`, `…0449`)
  and **8 no-output** (`no-abc`) tracks.
- Each row keeps `decision`, `composite`, `composite_z`, `retrieval_rank`,
  `lift_vs_mismatched`, reason `codes`, `deep_composite`, `recovered`,
  `tier`/`country`/`duration_quartile`, the four group scores, and
  input/output/audio SHA256s. Top-level counts, rules, thresholds, source
  hashes, and the excluded lists are included for audit.
- Analysis bundle SHA256SUMS re-verified **474/474 OK** after adding it.
