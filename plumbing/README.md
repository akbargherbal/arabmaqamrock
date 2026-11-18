# plumbing/

Infrastructure that supports generation — fetch the binary, back up outputs.
Not part of the generation path itself (`run_one.sh` / `generate.py` need none of this).

## GCS prefix

Everything lives under one prefix at the **bucket root**:
`gs://akbar-december-2024-backup/arabmaqamrock/`. The bucket root is `GCP_ROOT`
(overridable); the prefix is `$GCP_ROOT/arabmaqamrock` (`GCP_PREFIX`). It is kept in
its own variable on purpose — the parent project's `GCP_BACKUP_BASE` is a *project
prefix*, so exporting one never silently relocates the other.

```
gs://akbar-december-2024-backup/arabmaqamrock/
  README.md                                                    what this prefix is
  binaries/index.json                                          aggregate register of every prebuilt
  binaries/<arch-tag>/audiocpp_cli + .sha256 + manifest.json   prebuilt, arch-selected
  runs/<timestamp>_<label>/                                    mirrored from ./out/
    <take>.mp3                    default: trial audio (WAV stays local)
    <take>.wav                    only for takes marked in UPLOAD_POLICY.json,
                                  or with --include-wav when the MP3 fails
    UPLOAD_POLICY.json            optional per-run audio policy
    transcripts/<take>.tar.gz     compressed complete transcription dirs
    transcripts/_archive_index.json
    ...                           logs, sidecars, manifests (unchanged)
  logs/                                                        mirrored from ./logs/
  run_manifest.json                                            written by backup_to_gcp.py
```

`<arch-tag>` = `sm75-t4` (T4) · `sm80-a100` (A100) · `sm89-l4` (L4).

Generation always writes WAV locally. `backup_to_gcp.py` transcodes finished
WAVs to MP3 in `.cache/gcs_mp3/` (outside `out/`) and uploads only the MP3 by
default. A take or run opted into WAV with `mark_production.py` uploads the WAV
instead. If an MP3 export fails, the take is **not** uploaded as WAV by
default: the pass logs a warning and retries next pass (`--include-wav` opts
into uploading the WAV anyway). Finished transcript song directories are
archived to `<take>.tar.gz` before upload; incomplete ones are never archived.

The GGUF model and the LoRAs are **not** here — they come from Hugging Face and
are re-downloaded on a fresh VM. Which LoRAs: `plumbing/loras.manifest`.

## Scripts

| File | What |
|---|---|
| `env.sh` | sourced by the others: repo root, `GCP_BACKUP_BASE`/`GCP_PREFIX`, `gcs_*` wrappers (`gcloud storage`, else `gsutil`) |
| `arch.sh` | compute capability ⇄ arch tag (`detect_compute_cap`, `arch_tag_for_cc`) |
| `binary_registry.py` | read every `binaries/<arch>/manifest.json` and print/publish the aggregate `binaries/index.json` register (arch, GPU, build date, CUDA, commit, sha256); flags missing arches |
| `fetch_binary.sh` | stage `./bin/audiocpp_cli`: fetch the arch prebuilt from GCS, sha256-verify, else build from source; `--publish` uploads a new build |
| `fetch_loras.sh` | stage the YuE2 LoRA adapters declared in `loras.manifest`; enabled rows by default, `--all` / `--only <set>` for the opt-in ones, `--check` to verify a staged tree offline |
| `loras.manifest` | the LoRA staging table: one row per file (set, repo, target dir, file, sha256) plus an `on`/`off` column — the single place to add a set or change what the installers fetch |
| `setup_transcribe.sh` | build the optional repo-local `.venv-sheetsage2` for `./transcribe.sh` (Python 3.11, CPU default; `--cuda` opt-in) |
| `backup_to_gcp.py` | mirror `./out/` → `runs/` and `./logs/` → `logs/` on a timer (append-only `gsutil rsync`); transcodes finished WAVs to MP3 and archives completed transcript dirs by default |
| `audio_export.py` | find finished WAVs, keep the MP3 cache outside `out/`, verify each encode; used by `backup_to_gcp.py` |
| `transcript_archive.py` | deterministic `<take>.tar.gz` archives for complete transcript song dirs + `_archive_index.json`; `--verify`/`--dry-run` |
| `mark_production.py` | write `UPLOAD_POLICY.json` to upload selected WAVs (or a whole run) instead of MP3 |
| `audio_cpp.pin` | the audio.cpp commit a build should use (empty = track main) |
| `instrumentalize_scores.py` | convert native YuE2/SheetSage2 scores to instrumental form (Vocal → Ins); vendored official helpers in `yue2_instrumental/` |
| `check_lora.py` | validate a YuE2 AR or NAR LoRA safetensors header (28 layers, tensor count, rank) before loading it on the GPU |

## Use

```bash
./plumbing/fetch_binary.sh                  # prebuilt for this GPU
./plumbing/fetch_binary.sh --build --publish --cuda-arch 75   # rebuild + re-publish

python plumbing/binary_registry.py            # what is on GCS, and when it was built
python plumbing/binary_registry.py --write-index   # refresh binaries/index.json
python plumbing/binary_registry.py --check    # manifest sha256 vs published .sha256

./plumbing/setup_transcribe.sh              # optional SheetSage2 env (CPU)
./transcribe.sh out/latest --dry-run

python plumbing/backup_to_gcp.py --once     # one backup pass
python plumbing/backup_to_gcp.py            # daemon every 5 min
python plumbing/backup_to_gcp.py --include-wav   # allow WAV on MP3 failure
# inspect the policies without uploading:
python plumbing/backup_to_gcp.py --once --dry-run
python plumbing/audio_export.py out/<run> --dry-run
python plumbing/transcript_archive.py out/<run>/transcripts --dry-run
# select a take for WAV upload:
python plumbing/mark_production.py out/<run> --take <name>_<seed>
```

Escape hatches: `--audio-upload wav` restores the old upload-everything-WAV
behaviour, `--include-wav` uploads a take's WAV when its MP3 export fails
(default: withhold and retry), and `--legacy-transcripts` uploads raw
transcript directories.

Only one backup daemon may run per checkout: a second `--interval-minutes`
loop exits with code 4 ("another backup daemon is already running") instead of
duplicating the sync. `--allow-concurrent` overrides, and `--once` is always
allowed (handy for cron).

The transcription venv and its module cache are git-ignored
(`.venv-sheetsage2/`, `.cache/`). Nothing in the generation path imports them.

Backup as a detached sidecar (survives closing the tab):

```bash
setsid nohup python plumbing/backup_to_gcp.py > logs/gcp_backup_stdout.log 2>&1 & disown
pgrep -af backup_to_gcp.py
```

## Notes

- **The prebuilt is arch + CUDA-suite + audio.cpp-commit specific.** A CUDA-13
  image needs the CUDA-12 runtime on `LD_LIBRARY_PATH`; `run_one.sh` sources
  `cuda_loader_path.sh` for that. When audio.cpp moves, the binary can go stale —
  `binaries/<tag>/manifest.json` records the commit, and `fetch_binary.sh --build
  --publish` rebuilds and re-records it.
- **MP3 trials need `ffmpeg`.** If it is missing (or an encode fails), the
  take is withheld from that pass and retried; the pass logs which takes were
  skipped and how to upload them as WAV (`--include-wav`). The MP3 cache is
  local (`.cache/gcs_mp3/`) and is never placed inside `out/`, so
  `transcribe.py` still sees one audio file per take.
- **Never run two daemons on one checkout.** They race on the same
  `<take>.mp3.tmp` cache file, which looks like an encode failure; the daemon
  lock now refuses the second loop. `gsutil rsync` never deletes, so a WAV
  uploaded by accident stays until you remove it by hand.
- **Building needs no GPU** (`nvcc` cross-compiles for `--cuda-arch`); it needs the
  CUDA toolkit + cmake + ccache and takes ~21 min cold.
- `GCP_ROOT` (bucket root) is runtime-supplied, never hardcoded in the scripts beyond a
  convenience default in `env.sh`; it is overridable.
