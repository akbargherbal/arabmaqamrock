# Reconciliation log

Append-only. One dated entry per approved docs pass: date — file/topic — what
changed — authority. Do not edit or delete old entries; they quote past drift
reports verbatim. See `skills/docs-reconciler/SKILL.md`.

## 2026-11-15 — first reconciliation pass

Approved after review of the first drift report (11 flagged: 3 missing paths,
4 flags not found in code; 650 claims, 19 live docs). Scope was the live-doc
allowlist in the skill; frozen/history docs untouched.

- 2026-11-15 — `analysis/vendor/README.md` — production modules
  (`analysis/abc_scale.py`, `analysis/abc_calibrate.py`,
  `analysis/run_yt500_similarity.py`) relabelled as planned and not in the repo;
  oracle reuse described as intended, not current — authority:
  `docs/plans/yt500-instrumental-abc-similarity.md` status line, repo file list.
- 2026-11-15 — `skills/maqam-edit/SKILL.md` — `maqam` CLI marked as the planned
  target interface with no executable in the repo; `check_abc.py` documented as
  the tracked validator and its local-only `datasets/five_stars/measure/`
  dependency stated; report step now allows validator/scratch output — authority:
  `docs/plans/model-and-tool-selection.md` §tool interface, `check_abc.py`
  argparse, import at `check_abc.py:32`.
- 2026-11-15 — `docs/suno-generation-controls.md` — §7.3 marked not implemented
  (no `--from-run`/`--set` in `generate.py`); §7.4 status split into the README
  sentence (present) and the `MODEL_CARD.md` provenance paragraph (open) —
  authority: `generate.py` argparse, `README.md` “Sampler and adapter controls”.
- 2026-11-15 — `SOURCE_OF_TRUTH.md` — ABC-edit row now names the planned CLI,
  the tracked validator and its local dependency — authority: same as above.
- 2026-11-15 — `generate.py` — docstring/`--help`/comment no longer cite the
  nonexistent `INFERENCE/run_one.sh`; reference is the root `run_one.sh` —
  authority: `generate.py:136-137`, `ls run_one.sh`.
- 2026-11-15 — `.gitignore` — added `/.reconcile/` for scratch claims/report
  output — authority: `skills/docs-reconciler/scripts/*`.

Post-pass audit: 667 claims, checkable 529, flagged 0 (0.0%), ignored 130.
`python3 -m unittest discover -s tests` — 150 tests, OK.

## 2026-11-16 — blend a0.2 published

Publishing pass: the tested `a0.2` blend (the intended primary arm) moved from
GCS-only to the public Hub, so the installer/docs no longer describe it as
unpublished.

- 2026-11-16 — `install.sh`, `setup_colab.sh` — stage the blend `a0.2` pair
  (`a0.2/v3instr_a0.2_{ar,nar}.safetensors`) alongside `a0.1`/`a0.15`, with
  sha256 pins `820f1ce90ab6…` / `f9738e214361…` — authority:
  `gs://akbar-december-2024-backup/OSTRIS_Arabic_Suno_Finetuning/arabic_instrumental_lora/mix_v3/MANIFEST.json`
  (`arms."0.2"`), verified by local `sha256sum` before upload.
- 2026-11-16 — `setup_colab.sh` — removed the stale “a0.2 exists on HF but is
  intentionally not staged” comment — authority: published file listing of
  `akbargherbal/arabmaqamrock-blend-yue2-lora` at `a0.2/`.
- 2026-11-16 — `MODEL_CARD.md` — added the instrumental donor and the blend arms
  (`a0.1` 8.9%, `a0.15` 12.9%, `a0.2` 16.5% donor share; alpha baked in, verify
  by sha256 not `check_lora.py --kind nar`) — authority: the blend repo card and
  `mix_v3/MANIFEST.json`.
- 2026-11-16 — `README.md` §Provenance — weights list now names the
  instrumental and blend repos and the three blend arms — authority: same.
- 2026-11-16 — HF card `akbargherbal/arabmaqamrock-blend-yue2-lora` — added the
  `a0.2` row/bullet/provenance line, made `a0.2` the load example, and replaced
  “not published here” with the primary-arm note — authority: same manifest.

## 2026-11-16 — blend a0.15 adopted as the generation default

Listening decision on the five-poem blend sweep. The 15-track batch
`gs://akbar-december-2024-backup/arabmaqamrock/runs/20261116-121703_imru_al_qais_sama_laka_shawqun_mix_grid/`
rendered `a0.1` / `a0.15` / `a0.2` at one seed per poem; `a0.15` was judged the
best arm. This is a reviewable working default, not a blind measurement; test
and experiment manifests are exempt.

- 2026-11-16 — `docs/generation-defaults.md` — new authority for the default
  recipe: blend `a0.15`, `lora_ar_scale: 0.75`, `lora_nar_scale: 1.0`,
  `guidance_scale: 1.5`, `cot: off`, `quantile: 0.95`, one take per song;
  records the batch evidence, scope and review procedure — authority: the
  batch `batch_summary.txt` / per-track sidecars and the listening verdict.
- 2026-11-16 — `manifests/imru_al_qais_sama_laka_shawqun_a015.json` — new
  runnable reference: the winning `a0.15` arm (five poems, same seeds, same
  caps) with the preset in `defaults` — authority: `generate.py --dry-run`
  resolves 5 tracks with caps 7750/7500/7250/7500/8250, matching the batch.
- 2026-11-16 — `generate.py`, `run_one.sh` — built-in adapter pair changed from
  the standalone v3 pair to `loras/blend/a0.15/v3instr_a0.15_{ar,nar}.safetensors`;
  `"dir"` aliases still resolve to `arabmaqamrock-v3-{ar,nar}` — authority:
  `docs/generation-defaults.md`, staged layout in `install.sh`.
- 2026-11-16 — `install.sh`, `setup_colab.sh` — closing hints now use the
  built-in default (no `--lora-ar` / `--lora-nar` flags); the staged set is
  unchanged (blend `a0.15` + own instrumental) — authority: same.
- 2026-11-16 — `README.md`, `docs/base-prompt.md`, `MODEL_CARD.md`,
  `manifests/README.md`, `SOURCE_OF_TRUTH.md` — point at the preset and the
  reference manifest; `MODEL_CARD.md` now records that `a0.15` won the
  listening batch while `a0.2` was the merge-time intended primary — authority:
  same.
- 2026-11-16 — `plumbing/backup_to_gcp.py`, `plumbing/audio_export.py`,
  `plumbing/README.md`, `README.md`, tests — a failed MP3 export no longer
  uploads the WAV by default: the take is withheld for that pass, retried next
  pass, and the warning names it plus the `--include-wav` opt-in; a daemon lock
  refuses a second `--interval-minutes` loop (`--allow-concurrent` overrides,
  `--once` unaffected) and the encode temp file is per-process — authority: the
  2026-11-16 `logs/gcp_backup.log`, which shows two daemons (5-min from setup at
  12:15:12, 2-min manual at 12:18:58) racing on `<take>.mp3.tmp`; the resulting
  `Errno 2` / `ffmpeg wrote no MP3` errors at 13:43:10, 14:40:30 and 15:06:32
  pushed three WAVs into `runs/20261116-121703_*` although their MP3s succeeded
  seconds later (`rsync` never deletes, so they stayed).
- 2026-11-16 — `run_one.sh`, `README.md` — the per-take `_gpu.csv` now starts
  with a header row and carries `timestamp_utc,elapsed_s,gpu_index` alongside
  the four `nvidia-smi` fields (`gpu_util_pct`, `mem_used_mib`, `power_w`,
  `temp_c`), one row per visible GPU per second; `[N/A]` passes through — the
  old files had four bare columns with no labels, no time reference and no GPU
  index, and were left untouched (bygones) — authority: `run_one.sh` lines
  that write the CSV and a real 2026-11-16 trace (max 100 %, 11329 MiB,
  95.52 W, 81 °C, confirming the field order).
