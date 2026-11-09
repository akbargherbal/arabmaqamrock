# Plan — reduce GCS consumption during prototyping

**Status:** implemented (v1; `plumbing/audio_export.py`,
`plumbing/transcript_archive.py`, `plumbing/mark_production.py`, and the
`backup_to_gcp.py` integration)
**Date:** 2026-11-09
**Revision:** generation stays WAV; MP3 is an upload-layer concern
**Scope:** `plumbing/backup_to_gcp.py`, new `plumbing/audio_export.py`,
new `plumbing/mark_production.py`, `transcribe.py` (archive hook only),
`plumbing/transcript_archive.py`, docs
**Goal:** stop paying GCS storage for prototype WAVs and for thousands of tiny
transcription files, without touching the generation path.

---

## 1. Recommendation in one page

Two independent changes, both auditable and reversible:

1. **Generation is untouched.** `generate.py`, `run_one.sh`, and `audio.cpp`
   keep producing WAV exactly as today. The **upload layer** transcodes each
   finished WAV to MP3 with `ffmpeg` and uploads only the MP3 by default.
   Trials are the rule, so MP3 is the default upload format. A small
   `UPLOAD_POLICY.json` in a run directory can select specific takes (or a whole
   run) for WAV upload. This means:
   - no changes to resume, sidecars, batch manifests, or transcription inputs;
   - local WAVs remain available for listening, transcription, and production;
   - `transcribe.py` never sees a duplicate MP3 next to the WAV because the MP3
     cache lives outside `out/`.

2. **Transcription archives.** Before each upload pass,
   `backup_to_gcp.py` archives every **completed** per-song transcript
   directory (`out/<run>/transcripts/<stem>/`) into one
   `out/<run>/transcripts/<stem>.tar.gz`, then excludes the raw directory from
   upload. Completion is proven per track by `meta.json.status == "ok"` plus a
   matching `score.abc` hash. A failed or interrupted track is never archived.

Why this is safe:

- The generation path does not change at all. The worst case of a bug in the
  uploader is a wrong upload policy, not a broken render or a lost take.
- The daily backup remains append-only. Nothing is deleted from GCS by the
  normal pass.
- The WAV is never deleted locally. If a take is selected for production, its
  WAV can be uploaded as-is while it still exists; if the VM is gone, it can be
  re-rendered from the recorded seed/controls.
- Every new behaviour has an escape hatch (`--audio-upload wav`,
  `--legacy-transcripts`, per-run `UPLOAD_POLICY.json`).

Expected savings:

| Item | Current | Proposed | Ratio |
|---|---|---|---|
| One 5-minute WAV take | ~57 MB | ~7 MB at 192 kbps MP3 | ~8× |
| Same, at 128 kbps | ~57 MB | ~4.8 MB | ~12× |
| One transcript song dir | many small objects | one `.tar.gz` | ~5–15× bytes, ~10–20× fewer objects |

Measure the baseline first (§5.1); these are planning numbers, not promises.

---

## 2. What the code does today (verified)

- `run_one.sh` always writes `$OUT/<name>_<seed>.wav`; the name is hard-coded
  (line 50). This stays.
- `generate.py` hard-codes `.wav` in `run_batch()` (line 1474),
  `_succeeded()` (line 1345), resume checks (line 1147), the sidecar
  (`wav_sha256`, `wav_duration_s`, line 1533), and the summary. This stays.
- `audio.cpp` has **no MP3 sink**: `src/framework/audio/output.cpp` exposes only
  `WavPcm16Sink` and `WavSink`, and `wav_writer.h` lists only PCM16/PCM24/Float32.
  This is exactly why MP3 belongs in the upload layer, not in the runner.
- `transcribe.py` already accepts `.mp3` (`AUDIO_EXTS`), but it also discovers
  audio **non-recursively** (`root.glob("*")`). A derived MP3 placed next to the
  WAV would therefore be transcribed twice (or collide). The MP3 cache must live
  outside the run directory.
- `transcribe.py` writes each track's `meta.json` **last**, after all artifacts
  and the ABC hash are known. That makes it the reliable completion marker.
- The run-level `transcribe_manifest.json` is written at the end of a batch, is
  overwritten by later runs into the same tree, and is written even when
  `--time-budget` stops early. Do not use it as the sole completion test.
- `plumbing/backup_to_gcp.py` mirrors `out/ → runs/` and `logs/ → logs/` with
  `gsutil -m rsync -r -x '.*\.tmp$'`; it never deletes remote objects.
- `setup_colab.sh` starts `backup_to_gcp.py` as a detached sidecar, so the first
  upload pass normally happens within ~5 minutes of a finished take.

---

## 3. Part A — keep WAV generation, upload MP3 only

### 3.1 Policy

| Run state | What is uploaded | Marker |
|---|---|---|
| Trial / exploration (default) | `.mp3` only | no marker, or `{"audio": "mp3"}` |
| Production, selected takes | `.wav` for selected takes; `.mp3` for the rest | `UPLOAD_POLICY.json` with `"audio": "wav"` and a `takes` list |
| Production, whole run | `.wav` for every take | `{"audio": "wav"}` with no `takes` |
| Legacy override | everything, including WAV | `backup_to_gcp.py --audio-upload wav` |

**Default is MP3**, because exploration is the normal mode now. The local WAV is
always kept; only the upload decision changes.

A run-level policy file is deliberately used instead of changing generation:
generation does not need to know how the run will be stored.

`out/<run>/UPLOAD_POLICY.json`:

```json
{
  "audio": "wav",
  "takes": ["qissa_band_391847", "qissa_band_882001"],
  "reason": "selected for production",
  "marked_utc": "2026-11-09T18:20:00Z"
}
```

- `takes` names are take stems (`<name>_<seed>`), not filenames.
- An empty/absent `takes` list with `"audio": "wav"` means the whole run.
- The file is uploaded with the run, so the GCS copy documents why it has WAVs.
- `mark_production.py` (below) writes it; hand-editing is also fine.

### 3.2 New module: `plumbing/audio_export.py`

Pure functions, testable without GCS:

```text
is_finished_take(run_dir, wav) -> bool
    # wav exists, non-empty, and <stem>_time.txt contains "Exit status: 0"
    # (override with --transcode-unverified for restored/copied WAVs)

mp3_cache_path(cache_root, run_dir, wav) -> Path
    # .cache/gcs_mp3/<run>/<relative>.mp3

ensure_mp3(wav, cache_root, bitrate, *, force=False) -> Path
    # hash-keyed reuse; encode to .tmp, verify, os.replace
```

Encoding command:

```bash
ffmpeg -nostdin -hide_banner -loglevel error -y \
  -i take.wav -map_metadata 0 -c:a libmp3lame -b:a 192k \
  -id3v2_version 3 take.mp3.tmp
```

Verification before publishing the MP3:

1. `ffprobe` duration matches the WAV within ~0.05 s (or one frame).
2. A full decode smoke check succeeds:
   `ffmpeg -v error -i take.mp3.tmp -f null -`.
3. The file is non-empty and smaller than the WAV (sanity check).

Then `os.replace()` and write a small sidecar next to the cached MP3:

```json
{
  "source_wav": "qissa_band_391847.wav",
  "source_sha256": "...",
  "source_bytes": 57600044,
  "mp3_sha256": "...",
  "mp3_bytes": 8123456,
  "bitrate": "192k",
  "duration_s": 300.02,
  "ffmpeg": "ffmpeg version ...",
  "created_utc": "..."
}
```

The cache is keyed by the WAV's sha256, so re-running the same seed or touching
the file does not force a re-encode if the bytes are unchanged. If the bytes
change, the MP3 is rebuilt and `rsync` replaces the remote object.

Recommended settings:

- **192 kbps CBR** by default. Good enough to judge structure, melody, lyrics,
  and arrangement.
- `--mp3-bitrate 128k` or `160k` for broad sweeps where size matters more.
- `-q:a 2` VBR is acceptable, but CBR makes sizes predictable.
- Do not evaluate fine timbre or mastering on MP3; promote the take and listen
  to the WAV.

### 3.3 Backup integration

`backup_to_gcp.py` gains:

```text
--audio-upload {mp3,wav}     default: mp3
--mp3-bitrate 192k           default: 192k
--mp3-cache DIR              default: .cache/gcs_mp3
--transcode-unverified       default: off (require _time.txt success)
```

Per pass, for each run directory:

1. Read `UPLOAD_POLICY.json` (missing → trial policy).
2. Collect `*.wav` files.
3. If trial policy:
   - For each finished WAV, ensure its cached MP3 exists.
   - Sync the run tree **excluding `*.wav`** to `runs/<run>/`.
   - Sync the MP3 cache tree to `runs/<run>/`; the cache mirrors the run's
     relative paths, so `runs/<run>/<take>.mp3` appears in the expected place.
4. If production policy with selected takes:
   - Same as trial for non-selected takes.
   - For each selected take, upload its WAV directly to `runs/<run>/<take>.wav`
     and skip its MP3 (WAV is the production artifact).
5. If production policy for the whole run:
   - Sync the run tree without excluding WAV; skip MP3 generation.
6. If `--audio-upload wav`: this is the legacy behaviour; upload everything.

Important details:

- **Do not** put the derived MP3 in `out/<run>/`: `transcribe.py` would discover
  both files. The cache is under `.cache/`, which is already gitignored.
- The cache tree must contain *only* MP3s and their JSON sidecars. Syncing it
  into `runs/<run>/` cannot overwrite the run's logs, manifests, or scores.
- The order is: encode → verify → upload MP3. If the encode fails for a WAV,
  **fall back to uploading that WAV** and log an error. Never let a transcode
  failure silently drop audio from the backup.
- If `ffmpeg` is missing, the pass does the same fallback (upload WAVs) and logs
  loudly; it does not fail the whole backup.
- A WAV is only considered finished when `<take>_time.txt` says
  `Exit status: 0`. This avoids uploading a partial WAV from a crashed or
  still-running render. `--transcode-unverified` covers restored WAVs that have
  no time file.
- MP3 export is serial in v1. A 5-minute WAV encodes in seconds, so this keeps
  CPU free for the GPU run without a job pool.

The remote layout stays natural:

```text
runs/<run>/
  input.json
  batch_manifest.json
  batch_summary.txt
  prompts/...
  scores/...
  plans/...
  qissa_band_391847.mp3          # trial take
  qissa_band_391847.json         # unchanged sidecar
  qissa_band_391847_time.txt
  qissa_band_391847.log
  qissa_band_882001.wav          # selected production take
  transcripts/...
```

### 3.4 Production marking and promotion

New helper `plumbing/mark_production.py`:

```bash
# mark one take in a run (WAV will be uploaded, MP3 suppressed for it)
python plumbing/mark_production.py out/<run> --take qissa_band_391847

# mark the whole run
python plumbing/mark_production.py out/<run> --all

# inspect without writing
python plumbing/mark_production.py out/<run> --dry-run
```

It writes/merges `UPLOAD_POLICY.json`. The next backup pass uploads the selected
WAVs.

If the local WAV still exists, that is the end of the story: no re-render.

If the VM is gone and only the MP3 is in GCS, re-render from the sidecar:

```bash
python plumbing/promote_take.py gs://.../runs/<run>/qissa_band_391847.json \
  --label prod_qissa_391847
```

`promote_take.py` (optional convenience; can be a documented manual recipe in
v1):

1. Downloads the take's `.json` sidecar and the run's `batch_manifest.json`.
2. Rebuilds a one-song input JSON with the same seed, cap, style/lyrics files,
   ABC score, CoT mode, controls, LoRA aliases, and adapter scales.
3. Checks the recorded asset hashes against the local assets and refuses to run
   on a mismatch.
4. Calls `generate.py` into a new run directory (which produces WAV as always).
5. Writes `UPLOAD_POLICY.json` with `"audio": "wav"` for the new run.
6. Records `promoted_from` (source run, take, seed, original MP3 sha256) and a
   note that this is a **re-render**, not a transcode.

Do not transcode an MP3 to WAV and call it production. The only production WAV
is either the original local WAV or a fresh render from the recorded seed.

### 3.5 Risks and mitigations

| Risk | Mitigation |
|---|---|
| `ffmpeg` missing on the VM | Fall back to uploading WAVs and log loudly; never drop audio |
| Transcode runs while generation needs CPU | serial encode; seconds per take |
| Partial WAV uploaded | Require `_time.txt` `Exit status: 0`; `--transcode-unverified` is opt-in |
| MP3 cache lost when the VM dies | Remote MP3 already uploaded; WAV can be re-rendered from the seed |
| A take is selected after the VM is gone | `promote_take.py` re-renders from the sidecar; never upsample MP3 |
| Transcribe picks up derived MP3 | Cache lives outside `out/`; never write MP3 beside the WAV |
| Production selected by mistake | Policy file is explicit and uploaded; `--dry-run` shows the plan |
| A re-render differs slightly | Expected for a stochastic model; record environment and seed, promote on the same GPU/commit when possible |

### 3.6 Why not generate MP3 directly?

Because `audio.cpp` has no MP3 sink, and because changing the runner would
change resume names, sidecars, batch manifests, and transcription inputs. The
upload layer is the right seam: it sees only finished WAVs, it can be retried,
and it can be disabled with one flag.

---

## 4. Part B — compress finished transcription song directories

### 4.1 Completion rule

A directory `tdir = out/<run>/transcripts/<stem>/` is safe to archive when:

1. `tdir/meta.json` exists, parses, and has `"status": "ok"`.
2. `tdir/score.abc` exists and is non-empty.
3. `sha256(tdir/score.abc) == meta["abc_sha256"]`.
4. Optionally, every artifact named in `meta.json` exists.

`meta.json` is written last in `transcribe_track()`, so a successful hash check
proves all earlier artifacts were written. A failed track (`failed`, `timeout`,
`no-abc`, `invalid-abc`) is never archived.

Do **not** require `transcribe_manifest.json` by default. Add an opt-in
`--require-run-manifest` that additionally checks `n_failed == 0` and the stem's
status for users who want the stricter gate.

### 4.2 Archive format and layout

Keep the existing directory path in `out/` and add one archive beside it:

```text
out/<run>/transcripts/
  _driver.log
  _timings.csv
  transcribe_manifest.json
  _archive_index.json          new, small
  <stem>/                      local working copy, kept by default
  <stem>.tar.gz                new, uploaded
```

GCS after the change:

```text
runs/<run>/transcripts/_driver.log
runs/<run>/transcripts/_timings.csv
runs/<run>/transcripts/transcribe_manifest.json
runs/<run>/transcripts/_archive_index.json
runs/<run>/transcripts/<stem>.tar.gz
```

The tar contains `tdir.name/` as its top-level directory so
`tar -xzf <stem>.tar.gz` restores the exact original tree.

Compression:

- **Default: gzip** (`tarfile` + `gzip`, level 9). It is in the standard library
  and available on every VM. ABC/MIDI/JSON/token text compresses well.
- Optional `--compression xz` for maximum ratio (xz is present here).
- Optional `--compression none` for debugging.
- Do not use zstd unless it is installed in `setup_colab.sh`; it is not present
  on this machine.

Determinism and idempotence:

- Sort entries; normalize `uid`, `gid`, `uname`, `gname`, mode, and `mtime`.
- Set the gzip `mtime=0`.
- Re-archiving an unchanged directory produces the same bytes, so the index hash
  proves "already done".
- Write to `<stem>.tar.gz.tmp`, then `os.replace()`.
- The existing backup exclude for `*.tmp` already covers the temporary file.

Index format (`transcripts/_archive_index.json`):

```json
{
  "version": 1,
  "tool": "transcript-archive/1",
  "generated_utc": "2026-11-09T12:00:00Z",
  "compression": "gzip",
  "archives": {
    "song_123": {
      "archive": "song_123.tar.gz",
      "source_bytes": 412345,
      "archive_bytes": 61234,
      "ratio": 0.148,
      "file_count": 14,
      "sha256": "...",
      "source_fingerprint": "...",
      "created_utc": "..."
    }
  }
}
```

### 4.3 New module: `plumbing/transcript_archive.py`

Pure functions, testable without GCS:

```text
is_complete(tdir) -> (bool, reason)
fingerprint(tdir) -> str
build_archive(tdir, dest, compression) -> ArchiveEntry
archive_transcripts(transcripts_dir, *, compression, dry_run) -> Index
verify_archive(tdir, archive, entry) -> bool
```

CLI for manual use:

```bash
python plumbing/transcript_archive.py out/20261109-.../transcripts --dry-run
python plumbing/transcript_archive.py out/20261109-.../transcripts
python plumbing/transcript_archive.py out/20261109-.../transcripts --verify
```

`backup_to_gcp.py` imports this module. `transcribe.py` can optionally call it
after `write_outputs()` via `--archive` for immediate compression, but that is
not required; the backup pass is idempotent.

### 4.4 Backup integration

Add to `backup_to_gcp.py`:

```text
--compress-transcripts / --legacy-transcripts   default: compress
--compression {gzip,xz,none}                    default: gzip
--require-run-manifest                          default: off
```

The local transcript directory is always kept in v1 (so resume works).
`--prune-local-transcripts` and the remote prune tool are future work.

Per pass:

1. For each `transcripts/` directory under a watched run:
   - Run `archive_transcripts(..., dry_run=args.dry_run)`.
   - Log: archived, skipped-incomplete, skipped-unchanged, failed.
2. Sync with an exclude for raw per-song directories:
   - `.*/transcripts/[^/]+/.*` — matches files inside `transcripts/<stem>/`
     but not `transcripts/<stem>.tar.gz`, `_timings.csv`, or the manifests.
3. If archiving fails for a run, **fall back to the old full sync for that
   run** and log an error. A larger bucket is better than a missing backup.
4. The local transcript directory is always kept in v1, so `transcribe.py`
   resume still works. Local pruning is future work.

A forced re-transcription can temporarily make an existing archive stale: the
source fingerprint changes and the next pass rebuilds that one archive. That is
safe and idempotent. If stricter avoidance is desired, `transcribe.py` can write
a `transcripts/.transcribe.lock` and the archiver can skip while it exists.

### 4.5 Reclaiming space from already-uploaded runs (opt-in, later)

The normal pass does not delete anything. Once archives are proven, add
`plumbing/prune_gcs_transcripts.py`:

```text
--prefix gs://.../arabmaqamrock/runs   required
--dry-run                             default: on; --yes to delete
--older-than-days N                   only old runs
--require-index                       only delete when the local index matches
```

Safety rules:

1. List `runs/*/transcripts/<stem>/...` objects.
2. Require the corresponding `runs/<run>/transcripts/<stem>.tar.gz` to exist
   remotely and be non-empty.
3. If a local `_archive_index.json` is available, require its `sha256` to match
   the remote archive.
4. Print object count and bytes to be deleted; require `--yes`.
5. Never delete `transcripts/*.csv`, `*.json`, `*.log`, or the archives.
6. Optionally require `--older-than-days` to avoid racing a live run.

Also worth doing outside the code:

- Check bucket versioning. If enabled, deleted objects leave noncurrent versions
  that still cost money; add a lifecycle rule for noncurrent versions.
- For old production WAV runs that must be kept, use a lifecycle rule to move
  `runs/` to Nearline/Coldline/Archive after N days. Remember GCS minimum
  storage durations (30/90/365 days) before deleting early.

---

## 5. Measurement, tests, and rollout

### 5.1 Phase 0 — baseline (no code change)

Record before touching anything:

```bash
gcloud storage du -s gs://akbar-december-2024-backup/arabmaqamrock/runs
gcloud storage ls -r gs://akbar-december-2024-backup/arabmaqamrock/runs | wc -l
# one representative run:
gcloud storage du -s gs://.../runs/<run>
```

Also record local `du -sh out/<run>` and the transcript directory's file count.

### 5.2 Phase 1 — helpers and tests, no default change

- `plumbing/audio_export.py` + `tests/test_audio_export.py`.
- `plumbing/transcript_archive.py` + `tests/test_transcript_archive.py`.
- Backup policy helpers + `tests/test_backup_policy.py` with fake run dirs.
- Run the existing suite (`python -m unittest discover -s tests`).

Tests to add:

1. A finished WAV (time file exit 0) is encoded; an unfinished one is not.
2. MP3 duration tolerance; a corrupt output is rejected and the WAV is
   uploaded as fallback.
3. Cache reuse: same WAV bytes → no second ffmpeg call (mock the subprocess).
4. Cache invalidation: changed WAV bytes → re-encode.
5. Backup policy: default MP3 excludes WAV; selected takes upload WAV; whole-run
   production uploads all WAVs; `--audio-upload wav` is the legacy path.
6. Derived MP3 is not placed in `out/` and is not discovered by
   `transcribe.expand_tracks`.
7. Transcript complete vs incomplete (status, missing ABC, hash mismatch).
8. Archive round-trip: extract, compare every file hash.
9. Deterministic archive: build twice, compare sha256.
10. Archive failure → fallback to raw sync.

Skip MP3 tests gracefully when `ffmpeg` is absent, but log clearly in real runs.

### 5.3 Phase 2 — opt-in trial on one small run

```bash
# generate as usual; no special flag
python generate.py <manifest> --limit 2 --label upload_mp3_smoke

# inspect what the uploader would do
python plumbing/backup_to_gcp.py --once --audio-upload mp3 --dry-run
python plumbing/backup_to_gcp.py --once --audio-upload mp3
gcloud storage ls gs://.../runs/<upload_mp3_smoke>/
```

Expected: `.mp3` audio objects, no `.wav`; all logs/sidecars/manifests still
present. The local run still has its `.wav` files.

Then confirm transcription still sees one audio file per take:

```bash
./transcribe.sh out/<upload_mp3_smoke> --dry-run
```

Expected: the plan lists the WAVs, not the cached MP3s.

### 5.4 Phase 3 — opt-in transcript compression on one run

```bash
python plumbing/transcript_archive.py out/<run>/transcripts
tar -tzf out/<run>/transcripts/<stem>.tar.gz | head
mkdir -p /tmp/extract && tar -xzf ... -C /tmp/extract
diff -r out/<run>/transcripts/<stem> /tmp/extract/<stem>
python plumbing/backup_to_gcp.py --once --compress-transcripts --dry-run
```

Expected dry-run: raw `transcripts/<stem>/...` excluded, `<stem>.tar.gz`
included. Then run it for real and verify with `gcloud storage ls`.

### 5.5 Phase 4 — make it the default

Because trials are the rule:

- `backup_to_gcp.py`: default `--audio-upload mp3` and
  `--compress-transcripts` (already the proposed defaults). Keep
  `--audio-upload wav` and `--legacy-transcripts` as escape hatches.
- `setup_colab.sh`: start the sidecar with the new defaults and print the new
  verify commands.
- Update `README.md` (Output section), `plumbing/README.md`, and
  `docs/transcription.md`.

### 5.6 Phase 5 — optional cleanup of existing GCS data

Run the prune tool in dry-run mode, review the byte/object counts, then run with
`--yes` on one old run. Only after that consider a bucket lifecycle rule.

### 5.7 Rollback

| Desired old behaviour | Command |
|---|---|
| Upload WAVs (old behaviour) | `backup_to_gcp.py --audio-upload wav` |
| Stop archiving transcripts | `backup_to_gcp.py --legacy-transcripts` |
| Recreate a raw transcript dir | `tar -xzf <stem>.tar.gz` in `transcripts/` |
| Force a WAV for one take | `mark_production.py out/<run> --take <stem>` |
| Force a WAV for one pass | `backup_to_gcp.py --audio-upload wav --once` |

Generation itself never needs a rollback because it is unchanged.

---

## 6. Concrete file-by-file changes

| File | Change |
|---|---|
| `generate.py` | **no change** |
| `run_one.sh` | **no change** |
| `transcribe.py` | **no change in v1**; a future `--archive` can call `transcript_archive.py` |
| `plumbing/audio_export.py` | new: finish check, MP3 cache, ffmpeg verify, policy reader |
| `plumbing/transcript_archive.py` | new: completion check, deterministic tar.gz, index, verify |
| `plumbing/mark_production.py` | new: write/merge `UPLOAD_POLICY.json` |
| `plumbing/promote_take.py` | future: rebuild a one-song manifest from a sidecar and re-render |
| `plumbing/backup_to_gcp.py` | per-run policy, MP3 cache sync, WAV excludes, archive pre-pass, fallback, `--legacy-*` flags, per-pass savings report |
| `plumbing/prune_gcs_transcripts.py` | future: dry-run-first remote cleanup |
| `setup_colab.sh` | sidecar defaults + verification hints |
| `README.md`, `plumbing/README.md`, `docs/transcription.md` | document the trial/production split, flags, archive layout, extraction, and rollback |
| `tests/test_audio_export.py` | new |
| `tests/test_transcript_archive.py` | new |
| `tests/test_backup_policy.py` | new |

---

## 7. Open decisions

1. **Resolved:** trial default is MP3. The daily sidecar runs with
   `--audio-upload mp3`; production is opt-in per take/run via
   `UPLOAD_POLICY.json`.
2. **Resolved:** `mark_production.py --take <stem>` is the unit; `--all` is
   also available.
3. **Transcript compression default:** currently on, with `--legacy-transcripts`
   as the escape hatch. Keep it that way unless a run shows a problem.
4. **Archive codec:** gzip is the default. `--compression xz` is available.
   zstd is not installed.
5. **Existing GCS data:** not touched by the normal pass. The prune tool is not
   implemented in v1; use a manual, verified cleanup if needed.
6. **Promotion UX:** `mark_production.py` handles the common case (WAV still
   local). A `promote_take.py` for re-rendering from a sidecar remains future
   work.

---

## 8. What not to do

- Do not change `run_one.sh` or `audio.cpp` to emit MP3; audio.cpp has no MP3
  sink, and generation must stay reproducible and unchanged.
- Do not write derived MP3s inside `out/<run>/`; `transcribe.py` discovers audio
  non-recursively and would see duplicates.
- Do not transcode a trial MP3 to WAV and label it production.
- Do not delete the local WAV before the MP3 is verified and uploaded.
- Do not archive a transcript directory whose `meta.json` is not `ok`.
- Do not rely on the run-level `transcribe_manifest.json` alone for completion.
- Do not add a `-d`/delete flag to the daily backup pass. Remote deletion must
  remain a separate, explicit, dry-run-first operation.
- Do not let a transcode failure silently drop audio: fall back to WAV upload.

---

## 9. Expected outcome

After the rollout:

- A 20-take exploration run that used to upload ~1.1 GB of WAV uploads ~140 MB
  of MP3 at 192 kbps, while the local WAVs remain available for listening and
  transcription.
- A selected take is uploaded as WAV with one command, or re-rendered from its
  recorded seed if the VM is gone.
- A transcription run with 50 songs uploads ~50 archives plus a handful of
  run-level files instead of ~750 small objects.
- No change to `generate.py`, `run_one.sh`, resume semantics, or sidecars.
- Every saving is reversible with one flag, and the daily backup remains
  append-only by default.
