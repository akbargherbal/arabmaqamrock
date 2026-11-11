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

The `yt500-0181` and `yt500-0214` `no-abc` exporter cases were auto-recovered
(`drop.tail-note`); recovery runs every 120 s and is idempotent.


