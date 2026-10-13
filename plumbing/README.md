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
  binaries/<arch-tag>/audiocpp_cli + .sha256 + manifest.json   prebuilt, arch-selected
  runs/<timestamp>_<label>/                                    mirrored from ./out/
  logs/                                                        mirrored from ./logs/
  run_manifest.json                                            written by backup_to_gcp.py
```

`<arch-tag>` = `sm75-t4` (T4) · `sm80-a100` (A100) · `sm89-l4` (L4).

The GGUF model and the LoRA are **not** here — they come from Hugging Face and are
re-downloaded on a fresh VM.

## Scripts

| File | What |
|---|---|
| `env.sh` | sourced by the others: repo root, `GCP_BACKUP_BASE`/`GCP_PREFIX`, `gcs_*` wrappers (`gcloud storage`, else `gsutil`) |
| `arch.sh` | compute capability ⇄ arch tag (`detect_compute_cap`, `arch_tag_for_cc`) |
| `fetch_binary.sh` | stage `./bin/audiocpp_cli`: fetch the arch prebuilt from GCS, sha256-verify, else build from source; `--publish` uploads a new build |
| `backup_to_gcp.py` | mirror `./out/` → `runs/` and `./logs/` → `logs/` on a timer (append-only `gsutil rsync`) |
| `audio_cpp.pin` | the audio.cpp commit a build should use (empty = track main) |

## Use

```bash
./plumbing/fetch_binary.sh                  # prebuilt for this GPU
./plumbing/fetch_binary.sh --build --publish --cuda-arch 75   # rebuild + re-publish

python plumbing/backup_to_gcp.py --once     # one backup pass
python plumbing/backup_to_gcp.py            # daemon every 5 min
```

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
- **Building needs no GPU** (`nvcc` cross-compiles for `--cuda-arch`); it needs the
  CUDA toolkit + cmake + ccache and takes ~21 min cold.
- `GCP_ROOT` (bucket root) is runtime-supplied, never hardcoded in the scripts beyond a
  convenience default in `env.sh`; it is overridable.
