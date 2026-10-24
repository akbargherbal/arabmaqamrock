# Plan — adapt the `music-cover` transcription tools into ArabMaqamRock

**Status:** implemented (v1); see §14
**Date:** 2026-10-24
**Source:** [`akbargherbal/maqamrock-yue2-lora-finetuning`](https://github.com/akbargherbal/maqamrock-yue2-lora-finetuning), branch `music-cover`
**Target:** this repository (`arabmaqamrock`, generation-only)

## 1. Recommendation

Port the **Python SheetSage2 batch transcriber** as an optional, CPU-default tool
that turns a finished generation run into a symbolic melody score (`score.abc`
plus side artifacts), with provenance and resume guards. It is CPU-capable by
design and can use CUDA only when explicitly enabled.

Concretely:

- **Port:** `INFERENCE/sheetsage2_transcribe.py` → `transcribe.py`,
  `INFERENCE/ss2_venv.sh` → `plumbing/setup_transcribe.sh`.
- **Fold in:** the useful operational behavior from `INFERENCE/abc_transcribe.py`
  (time budget, per-track timeout, collision-safe stems, defensive output
  discovery), **without** its audio.cpp backend.
- **Do not port in v1:** `abc_transcribe.py` itself, the rescue/cover drivers,
  `suno_to_songs.py`, or the scratch probe. They are either superseded upstream,
  depend on an adapter this repo does not ship, or are not transcription.
- **Leave the generation path untouched.** `generate.py`, `run_one.sh`, the
  binary, models, and LoRAs must not change.

The result is a first-class optional capability:

```bash
./plumbing/setup_transcribe.sh          # once, builds .venv-sheetsage2 (CPU)
./transcribe.sh out/latest --dry-run    # plan only, no model loaded
./transcribe.sh out/latest --smoke      # one track, then stop
./transcribe.sh out/latest              # all takes
```

## 2. What exists upstream

The `music-cover` branch contains two transcription paths and several consumers.
Only one path is production-ready.

| Upstream file | What it is | Decision |
|---|---|---|
| `INFERENCE/sheetsage2_transcribe.py` | Batch WAV → melody ABC using official Python `m-a-p/SheetSage2`, `melody_only=True`; one model load; resumable; writes `score.abc`, `_driver.log`, `_timings.csv`, `transcribe_manifest.json` | **Port and harden** |
| `INFERENCE/ss2_venv.sh` | Builds isolated `/content/.venv-sheetsage2` (uv, Python 3.11, torch 2.8.0, transformers 4.45.2, pinned deps) | **Port, make repo-local and CPU-first** |
| `INFERENCE/ss2_probe.py` / `.sh` | Scratch diagnostic: loads by repo ID, clears the HF dynamic-module cache, measures time/RAM/VRAM | **Fold into `--doctor` / `--smoke`; do not ship as a separate tool** |
| `INFERENCE/abc_transcribe.py` | audio.cpp `--task midi --family sheetsage2` path; expects `bin/audiocpp_cli` with SheetSage2 and `models/SheetSage2-GGUF/` | **Defer.** Upstream docs call it superseded; flags are marked unverified |
| `INFERENCE/rescue_abc_batch.sh` | Re-renders takes conditioned on ABC with `qfinal_a0.3` | **Out of scope.** No `qfinal` adapter here |
| `INFERENCE/v2_abc_to_qfinal.sh` | B1 “export v2 plan, then rescue” path | **Out of scope** |
| `INFERENCE/suno_to_songs.py` | Suno manifest → `generate.py` song JSON | **Not transcription** |
| `docs/music-cover-workflow.md`, `docs/PRON_LORA_RESCUE.md` phase 2, `docs/music-cover-feasibility.md` §2.1, `docs/COMMAND_HANDOVER_GOTCHAS.md` | Design, measured CPU feasibility, and the known silent-failure traps | **Mine for requirements; rewrite for this repo** |

### Why the Python path is the right default

Upstream measured the Python route on a free CPU runtime:

- SheetSage2 runs CPU-only at roughly **4–6 min per track** and **~4.3 GB peak RAM**
  for a ≤10-minute song.
- Model load is ~10 s; 2 threads are enough; 8 cores add little.
- The audio.cpp route would require rebuilding the binary with SheetSage2 support
  and fetching a separate GGUF. The ancestor docs record that the staged binary
  was built `--model-set custom --models yue2`, contains no SheetSage2 support,
  and that the rebuild was abandoned as unnecessary.

This repository’s build recipe (`plumbing/fetch_binary.sh`) also builds
`--model-set custom --models yue2`, and this repository ships no `qfinal` adapter.
The Python route gives the capability without touching the generation stack.

It is also the **only transcription path that works on a GPU-less box today**:
the Python env can be built with CPU torch wheels and needs no CUDA runtime,
whereas the current audio.cpp binary is CUDA-linked and would have to be rebuilt
before it could transcribe on CPU.

## 3. Hardware compatibility and the GPU-unavailable case

Generation needs a CUDA GPU; transcription does not. That separation is a
deliberate part of this plan.

| Scenario | Python SheetSage2 | audio.cpp SheetSage2 |
|---|---|---|
| **No GPU at all** (CPU-only VM / Colab CPU runtime) | ✅ works after `setup_transcribe.sh`; CPU wheels, no CUDA | ❌ not with the current binary: it is a CUDA build and needs `libcublas` just to start |
| GPU box, transcribing only | ✅ works; CPU default leaves the GPU free | ⚠️ only after rebuilding with SheetSage2 + GGUF |
| GPU box, generating and transcribing | ✅ CPU default avoids GPU contention; GPU mode is opt-in | ⚠️ GPU mode contends with generation; rebuild still required |
| No Python 3.11 available | ✅ `uv` provisions it | — (not applicable) |
| Wants a single native runtime / no Python | ❌ needs the Python env | ✅ after a validated rebuild |

The practical consequence:

- On a free CPU runtime, stop the GPU and transcribe there. The WAVs are already
  on disk (or GCS); transcription is local, CPU-only, and billed as CPU time.
- On a GPU VM, `CUDA_VISIBLE_DEVICES=""` plus CPU wheels guarantees the
  transcription job cannot hold or OOM the GPU that generation needs.
- If the only machine available has no GPU, the Python path still works; the
  audio.cpp path does not, unless someone first builds a CPU-capable binary.

## 4. What this tool is for (and what it is not)

**Good uses now**

- Archive a symbolic score beside every generated take.
- Build a melody fingerprint to compare seeds/takes or to check that a repair
  kept the original melody.
- Prepare for a future ABC-conditioned “cover” render, if and when a compatible
  adapter and a validated binary path exist.

**Not claimed**

- It is **not** lyric transcription or pronunciation verification. The existing
  ASR/CTC scripts under `docs/happy_accidents/.../scripts/` serve that purpose.
- `melody_only=True` keeps the **Vocal and Ins melody staves** and omits chord
  symbols; it is not “lead vocal only”. If vocal-only melody is needed later,
  extract it from `melody_vocal.mid` or `events.json`.
- ABC conditioning is **off-distribution and unvalidated** for this
  repository’s `cot=off` generation path. This plan does not change generation
  and makes no quality claim.

## 5. Target UX and layout

### Prerequisites

`uv` (to create the Python 3.11 venv), `ffmpeg` (SheetSage2 decodes audio through
it; upstream recommends FFmpeg 6.1 with shared libraries), and ~3–5 GB of disk
for the venv plus model cache. A Hugging Face token is optional for these public
repos but useful against rate limits. No GPU is required.

### Commands

```bash
# Build the isolated environment (once).
./plumbing/setup_transcribe.sh
./plumbing/setup_transcribe.sh --doctor     # env + optional model probe

# Plan / validate without loading the model.
./transcribe.sh out/latest --dry-run

# One track, then stop (the smoke gate).
./transcribe.sh out/latest --smoke

# A whole run.
./transcribe.sh out/latest

# Explicit paths and a separate output tree.
./transcribe.sh out/20261024-102834_ibn_zuraiq_formatted \
  --out-dir /tmp/abc_ibn_zuraiq
```

`transcribe.sh` is a thin wrapper around
`.venv-sheetsage2/bin/python transcribe.py "$@"`. Calling `python3 transcribe.py`
directly still works for `--dry-run` and `--doctor`; the model path requires the
venv because system Python 3.13 is not compatible with SheetSage2’s custom code.

### Default output layout

Keep the ancestor’s provenance spine (`<name>_<seed>`), but make the run
self-contained:

```
out/<run>/
  <name>_<seed>.wav                          # from generate.py
  transcripts/                               # default output root
    <stem>/
      score.abc                              # primary artifact
      transcription.mid
      melody_vocal.mid
      melody_instrumental.mid
      chords.mid
      events.json
      meta.json                              # new: source hash + model/env provenance
    _driver.log
    _timings.csv
    transcribe_manifest.json
```

- Default `--out-dir` is `<resolved-run>/transcripts`.
- For an explicit single WAV, it is `<wav-parent>/transcripts`.
- For multiple inputs without a common run directory, `--out-dir` is required.
- WAV discovery is **non-recursive**, so `transcripts/` can never be mistaken for
  input audio.
- Because the output lives under `out/`, the existing backup sidecar mirrors it
  automatically. No `--gcs` flag is needed.

A separate output tree remains possible with `--out-dir`; nothing depends on the
default.

### CLI sketch

```
transcribe.py [INPUT ...] [options]

Inputs
  INPUT                      WAV files or run directories. Default: resolve
                             out/latest (a text pointer written by generate.py).
  --out-dir DIR              Output root (default: <input>/transcripts)
  --exclude REGEX            Skip matching stems. No default exclusion.
  --recursive                Recurse into subdirectories (default: off)
  --limit N                  Cap number of tracks (0 = all)
  --smoke                    Process at most one track, then stop

Model / device
  --model ID                 Default: m-a-p/SheetSage2
  --revision REV             Default: pinned commit (see §9)
  --device cpu|cuda|auto     Default: cpu
  --threads N                Default: min(4, CPU count)
  --melody-only / --full     Default: melody-only (matches the cover front end);
                             --full means SheetSage2 full transcription (chords),
                             not YuE2 `cot=full`
  --on-collision error|suffix
                             Duplicate-stem policy (default: error)

Execution
  --force                    Re-transcribe even if a valid ABC exists
  --verify                   Re-check hashes only; no model load
  --fail-fast                Stop on first failure (default: continue)
  --time-budget SEC          Stop starting new tracks after SEC (0 = off)
  --per-track-timeout SEC    Best-effort per-track alarm (0 = off)
  --dry-run                  Plan only; no torch import, no writes
  --doctor                   Print env/dependency diagnostics and exit
  --verbose                  Keep full tracebacks in the log
```

## 6. Behavior specification

### 6.1 Input resolution

1. If `INPUT` is omitted, read `out/latest` (the text pointer written by
   `generate.py`). If it points to a missing run, fail with the command to
   generate first.
2. If `INPUT` is a directory, collect `*.wav` / `*.WAV` at its top level.
3. If `INPUT` is a file, accept it directly.
4. Deduplicate by resolved path; preserve a stable sort order.
5. **Do not silently exclude `_[23]_` stems.** This is a deliberate change from
   upstream. This repository legitimately produces duplicate-take names such as
   `..._3_810750224.wav` (see `cases/001_harith03_faadduha/`), so the ancestor’s
   default `VARIANT_MARKER = re.compile(r"_[23]_")` would silently drop real
   takes. Exclusion is opt-in via `--exclude`.
6. Handle Unicode and spaces in stems (Arabic names are expected). Sanitize only
   path separators and control characters; do not transliterate.

### 6.2 Track identity and collisions

- `stem = sanitized(Path(input).stem)`; output folder is `<out>/<stem>/`.
- If two inputs share a stem, fail by default with a clear message. Optional
  `--on-collision suffix` appends `_2`, `_3`, … and records the mapping.
- Never overwrite a source WAV; transcription is read-only on inputs.

### 6.3 Resume and stale-ABC guard

This is the most important hardening over upstream.

For each track, read `score.abc` and `meta.json`:

| State | Action |
|---|---|
| no ABC | transcribe |
| ABC + `meta.json` with matching `source_wav_sha256` | skip (`skipped`) |
| ABC + `meta.json` with a **different** source hash | **fail the track** unless `--force`; print “source WAV changed; re-run with --force” |
| ABC but no `meta.json` | skip with a warning (`skipped-unverified`); `--force` redoes it |

This closes the upstream failure mode where an existing `score.abc` is silently
stapled to a re-rendered WAV. A new `--verify` mode can re-check all hashes
without loading the model.

### 6.4 Model load and execution

- Load once by **repository ID** (`AutoModel.from_pretrained(model_id,
  trust_remote_code=True)`), not from a local directory. Upstream found that
  loading a local snapshot caches only the entry module and fails on sibling
  imports.
- Pin the revision (default: `b83c3d79a6d98bcffaf8f9ed112c90aa887887bc`, the
  current `main` at planning time) and record it in every manifest. Allow
  `SHEETSAGE2_REVISION` / `--revision` to override.
- Use an isolated `HF_MODULES_CACHE` under the run or a repo-local cache to avoid
  stale `transformers_modules`; `--doctor` reports the cache path. Do not delete
  the user’s global cache silently.
- Default to **CPU**. `--device cuda` is opt-in and warns that it holds the GPU
  and can contend with generation. The venv is built with CPU wheels by default,
  so accidental GPU use is unlikely.
- Set `torch.set_num_threads(--threads)`; default `min(4, os.cpu_count())`.
- Sequential only. One model, one track at a time; this matches upstream and
  avoids RAM spikes.

### 6.5 Output validation

A track is `ok` only if:

- `score.abc` exists and is non-empty; and
- it looks like ABC (contains `X:` and `K:` headers, at least one note line).

If SheetSage2 returns no ABC, print the tail of the exception/log and mark the
track `no-abc`. Continue with the next track unless `--fail-fast`.

Keep all side artifacts (`transcription.mid`, `melody_*.mid`, `chords.mid`,
`events.json`, `*.lab`) for future analysis; they are cheap compared with audio.

### 6.6 Per-track metadata (`meta.json`)

```json
{
  "tool": "arabmaqamrock-transcribe/1",
  "created_utc": "2026-10-24T12:00:00Z",
  "status": "ok",
  "source_wav": "/abs/path/out/<run>/<stem>.wav",
  "source_wav_sha256": "...",
  "source_wav_bytes": 12345678,
  "duration_s": 237.5,
  "model": "m-a-p/SheetSage2",
  "model_revision": "b83c3d79...",
  "melody_only": true,
  "device": "cpu",
  "threads": 4,
  "python": "3.11.x",
  "torch": "2.8.0+cpu",
  "transformers": "4.45.2",
  "seconds": 250.1,
  "abc": "score.abc",
  "abc_sha256": "...",
  "abc_bytes": 3120
}
```

The aggregate `transcribe_manifest.json` records the source run, the
`batch_manifest.json` hash when present, model/env versions, and one row per
track. `_timings.csv` mirrors the table for quick inspection.

### 6.7 Errors, exit codes, and logging

- Continue on per-track failure by default; exit `1` if any track failed, else
  `0`; `130` on interrupt.
- `--fail-fast` stops at the first failure.
- `--per-track-timeout` is best-effort (`signal.alarm` on Unix); document that a
  stuck C extension may delay cancellation. For hard limits, wrap the whole run
  in `timeout`.
- Write `_driver.log` in UTF-8, including the exact command, resolved paths,
  model revision, and full tracebacks when `--verbose`.
- No network calls other than the Hugging Face model download/cache.

### 6.8 Licensing

SheetSage2 and its MERT-v2-FullSong backbone are **CC-BY-NC-4.0**. The code in
this repo is MIT, but transcription outputs and any use of the model are
non-commercial. Add this to `docs/transcription.md` and the README section; do
not imply that the LoRA’s non-commercial terms are the only restriction.

## 7. File-level changes

| File | Change |
|---|---|
| `transcribe.py` | **New.** Port and harden `sheetsage2_transcribe.py`; incorporate `abc_transcribe.py`’s time budget, timeouts, and collision handling. |
| `transcribe.sh` | **New.** Thin wrapper selecting `.venv-sheetsage2/bin/python`; clear error if the env is missing. |
| `plumbing/setup_transcribe.sh` | **New.** Port `ss2_venv.sh`: repo-local venv, Python 3.11, CPU wheels, pinned deps, ffmpeg check, `--doctor`, idempotent. |
| `tests/test_transcribe.py` | **New.** Unit tests with a fake model; no torch/model download. |
| `docs/transcription.md` | **New.** What/why, install, usage, output layout, CPU sizing, gates, troubleshooting, license. |
| `README.md` | Add a short “Optional: symbolic transcription” section linking the doc. |
| `plumbing/README.md` | Add `setup_transcribe.sh` to the script table. |
| `install.sh` | Add optional `--with-transcribe` that calls the setup script; default behavior unchanged. |
| `setup_colab.sh` | Add optional `--with-transcribe`; do not install by default. |
| `.gitignore` | Add `.venv-sheetsage2/` and any local model cache under the repo. |
| `docs/plans/transcription-tools-adaptation.md` | This plan. |

No changes to `generate.py`, `run_one.sh`, `MODEL_CARD.md`, prompts, models, or
LoRAs.

## 8. Implementation phases

### Phase 1 — CLI skeleton and planning (no model)

**Tasks**

- Extract input discovery, `out/latest` resolution, stem sanitation, collision
  handling, and `--dry-run` into `transcribe.py`.
- Delay `torch`/`transformers` imports until after `--dry-run`/`--doctor`.
- Remove the `_[23]_` default exclusion and all `/content/...` defaults.
- Add `--out-dir` derivation and `_timings.csv`/manifest scaffolding.

**Verify**

```bash
python3 transcribe.py out/latest --dry-run
# lists every WAV, including names containing _2_/_3_, and writes nothing
python3 -m unittest discover -s tests -p 'test_transcribe.py' -v
```

### Phase 2 — environment and real smoke

**Tasks**

- Port `ss2_venv.sh` to `plumbing/setup_transcribe.sh`.
- Require/detect `uv` and `ffmpeg`; print actionable install hints.
- Use a repo-local `.venv-sheetsage2`, CPU torch wheels, and the upstream pins:
  `torch==2.8.0`, `torchaudio==2.8.0`, `transformers==4.45.2`,
  `huggingface-hub==0.36.0`, `safetensors==0.5.3`, `numpy==1.24.3`,
  `scipy==1.13.1`, `mir_eval==0.8.2`, `pretty_midi==0.2.10`, `mido==1.3.3`,
  `setuptools==78.1.1`.
- Add `--doctor`: Python, venv, torch, transformers, ffmpeg, HF cache, optional
  HF whoami, CUDA visibility.
- Add `--smoke` and run one real track on CPU.

**Verify**

```bash
./plumbing/setup_transcribe.sh --doctor
CUDA_VISIBLE_DEVICES="" ./transcribe.sh out/latest --smoke --verbose
# score.abc non-empty; meta.json has source/abc hashes; no GPU process
```

### Phase 3 — provenance, resume, and failure hardening

**Tasks**

- Implement the stale-ABC guard (`source_wav_sha256` comparison).
- Write `meta.json` per track and the aggregate manifest.
- Add source-run detection and `batch_manifest.json` hash when present.
- Add `--force`, `--fail-fast`, `--time-budget`, best-effort
  `--per-track-timeout`, `--limit`, `--verify`.
- Detect duplicate stems and provide the `--on-collision suffix` option.
- Validate ABC headers before marking `ok`.

**Verify**

- Change a WAV after transcription; rerun without `--force` → track fails with
  the stale-hash message; with `--force` → re-transcribes.
- Delete `meta.json`; rerun → `skipped-unverified` warning, no silent overwrite.
- Corrupt one WAV/ABC in a 3-track fixture → other tracks still complete, exit 1.

### Phase 4 — docs, install flags, and Colab

**Tasks**

- Write `docs/transcription.md` (including the license note and CPU sizing).
- Add README and plumbing README entries.
- Add opt-in `--with-transcribe` to `install.sh` and `setup_colab.sh`.
- Add `.venv-sheetsage2/` to `.gitignore`.
- Document the free-CPU workflow: stop the GPU, transcribe on CPU, output is
  backed up by the existing sidecar.

**Verify**

- Fresh clone + `./install.sh` still needs no transcription dependencies.
- `./install.sh --with-transcribe --help` prints the new flag.
- Colab CPU run: dry-run under system Python, real run under the venv.

### Phase 5 — validation on this repo’s output

**Tasks**

- Transcribe the current 8-track run (`out/20261024-102834_ibn_zuraiq_formatted`)
  on CPU, starting with `--smoke`.
- Compare `score.abc` for two seeds of the same song to confirm the output is
  useful as a melody fingerprint.
- Record timings and peak RSS in `docs/transcription.md`.
- Confirm the backup sidecar mirrors `transcripts/`.

**Acceptance**

- Every track gets a non-empty, ABC-parseable `score.abc` (or a recorded,
  actionable failure).
- A second run skips all valid tracks.
- No `/content` path is required; the tool works from a clean clone.
- No change to `generate.py` output or generation behavior.

### Phase 6 — optional follow-ups

Only after v1 is stable:

- **audio.cpp backend:** rebuild `bin/audiocpp_cli` with SheetSage2 support
  (build flags, `audio-cpp/SheetSage2-GGUF`), add `--backend audiocpp`, and
  verify the upstream-unverified flags before relying on them.
- **ABC-conditioned render:** `run_one.sh` now accepts `COT`/`ABC_FILE` for a
  direct guide render. Exposing it through `generate.py` and validating it on the
  shipped adapter is still future work.
- **Vocal-only melody:** derive a lead-vocal ABC from `melody_vocal.mid` /
  `events.json` if that proves more useful than the combined melody score.
- **Analysis integration:** optional comparison of pre/post-repair scores.

## 9. Pinned upstream facts to preserve or correct

| Upstream behavior | Our adaptation |
|---|---|
| Default `_[23]_` exclusion | **Removed.** Real stems can contain these markers. |
| Hardcoded `/content/audiocpp_inference/...` | Replaced by repo-relative defaults and `out/latest`. |
| Auto-selects CUDA when available | Default CPU; CUDA opt-in only. |
| Silently skips an existing `score.abc` | Hash-guarded; stale source fails loudly. |
| Optional `--gcs` upload | Removed; existing backup sidecar owns GCS. |
| Loads model `main` by repo ID | Repo ID retained; revision pinned and recorded. |
| Local-directory load fails on sibling imports | Keep repo-ID loading; document why. |
| `melody_only=True` | Keep; note it includes Vocal + Ins melody, not chords. |
| No per-track timeout in the Python path | Add best-effort timeout; document limits. |
| `abc_transcribe.py` aborts on first failure | Default continue; `--fail-fast` for the old behavior. |
| Scratch probe clears global HF module cache | Use an isolated cache; do not silently delete global state. |

## 10. Test plan

### Unit tests (no model, no network)

Use stdlib `unittest` so no new runtime dependency is required.

1. `out/latest` pointer resolution (valid, missing, stale).
2. Directory/file discovery; `_2_`/`_3_` names are **not** excluded.
3. `--exclude` is opt-in and applies only when given.
4. Unicode/Arabic stems and spaces survive sanitation.
5. Duplicate-stem handling: default error; `--on-collision suffix` maps safely.
6. `--dry-run` writes nothing and never imports torch.
7. Resume with matching `meta.json` → `skipped`.
8. Resume with mismatched `source_wav_sha256` → failure; `--force` → success.
9. ABC header validation: empty, malformed, and valid cases.
10. Manifest fields (hashes, model revision, versions, status) and `_timings.csv`.
11. Failure isolation: fake model raises on track 2; track 3 still runs; exit 1.
12. `--limit` and `--smoke` cap the work.
13. `--verify` detects a changed source WAV without loading the model.

### Integration (manual, real model)

- 60 s clip: ABC non-empty; transcribe time roughly ≤2 min at 4 threads;
  peak RSS ≤ ~6 GB.
- Full 4–6 min track: ABC non-empty; ~4–6 min at 4 threads.
- Second run skips; `--force` redoes.
- `CUDA_VISIBLE_DEVICES=""` and the CPU venv keep `nvidia-smi` free of this
  process.
- Output is mirrored by `python plumbing/backup_to_gcp.py --once --dry-run`.

### Acceptance criteria

- One documented setup command and one transcribe command work on a clean clone.
- CPU-only by default; no GPU is required or consumed.
- No silent stale-ABC path exists.
- All unit tests pass; the manual smoke is recorded.
- Generation behavior is unchanged; the new capability is strictly optional.

## 11. Risks and mitigations

| Risk | Mitigation |
|---|---|
| SheetSage2 / transformers incompatibility with system Python 3.13 | Isolated Python 3.11 venv with upstream pins; `--doctor` before model load. |
| `trust_remote_code` pulls changing code | Pin a revision; record it in manifests; document the trust boundary. |
| Stale `score.abc` paired with a re-rendered WAV | `source_wav_sha256` guard; fail unless `--force`. |
| Silent exclusion of real `_3_` takes | Remove the default exclusion; add a regression test. |
| CPU transcription holding the GPU VM | CPU wheels, default `--device cpu`, document free-CPU workflow; `CUDA_VISIBLE_DEVICES=""`. |
| Long tracks exceed RAM/time | Sequential processing; document tested limits; `--time-budget` and best-effort timeout. |
| Model download size / disk | Setup is opt-in; cache is documented and git-ignored. |
| Ambiguous output location | Default `<run>/transcripts`; dry-run prints the resolved path; `--out-dir` override. |
| Non-commercial model license | Explicit CC-BY-NC-4.0 note in docs and README. |
| Future ABC use is mistaken for validated covers | Docs state that generation is `cot=off` and ABC conditioning is unvalidated here. |

## 12. Open decisions

These are the only choices that need a user decision before Phase 1; the
recommendations above are the defaults.

1. **Output location:** `<run>/transcripts` (recommended, self-contained and
   backed up automatically) vs. a sibling `<run>_abc` tree (closer to the
   ancestor’s `out/abc_v2`).
2. **Install integration:** separate `plumbing/setup_transcribe.sh`
   (recommended) plus opt-in `--with-transcribe` flags, vs. always installing
   the transcription env.
3. **Revision pin:** pin the current SheetSage2 commit
   `b83c3d79a6d98bcffaf8f9ed112c90aa887887bc` (recommended) vs. track `main`.
4. **Scope:** transcription only (recommended) vs. also porting the
   ABC-conditioned render/rescue path. The latter needs an adapter and a
   validated `cot`/`abc_file` path that this repository does not currently have.

## 13. Effort estimate

| Phase | Estimate |
|---|---|
| CLI skeleton + discovery + dry-run | 0.5 day |
| Environment + real smoke | 0.5 day |
| Provenance/resume/hardening | 1 day |
| Tests + docs + install flags | 1 day |
| Validation on the current run | 0.5 day |
| **Total** | **~3 focus days** |

Phase 1 can ship independently and is useful even before the model env exists
(`--dry-run` only). Phase 2 is the first real-value milestone. Phases 3–4 make
it safe to keep.

## 14. Implementation record (v1)

Implemented on 2026-10-24:

| File | What landed |
|---|---|
| `transcribe.py` | CPU-default SheetSage2 batch driver; dry-run/verify/doctor; hash-guarded resume; per-track metadata; manifest/timings; Unicode-safe stems; no `_[23]_` default exclusion |
| `transcribe.sh` | venv wrapper; clear error when `.venv-sheetsage2` is absent |
| `plumbing/setup_transcribe.sh` | repo-local Python 3.11 env, CPU wheels by default, `--cuda`, `--doctor`, `--warm`, `--force` |
| `tests/test_transcribe.py` | 19 stdlib `unittest` cases with a fake model (discovery, collisions, stale/force, failed-status retry, tampered ABC, failure isolation, time budget, smoke/limit, verify, pointer) |
| `docs/transcription.md` | user guide, hardware matrix, resume semantics, provenance, license, troubleshooting |
| `README.md`, `plumbing/README.md` | optional-feature and setup-script entries |
| `install.sh`, `setup_colab.sh` | opt-in `--with-transcribe` |
| `run_one.sh` | optional `COT=melody\|full` + `ABC_FILE=...` for guide-conditioned renders; `generate.py` remains `cot=off` |
| `generate.py` | explicitly pins the batch path to `COT=off` so an exported guide env cannot change it silently |
| `docs/sessions/2026-10-24_baghdad_moon_abc_guide.md` | worked example: transcription, cap investigation, v1 guide render, five variants |
| `.gitignore` | `.venv-sheetsage2/`, `.cache/` |

Verification performed:

```bash
python3 -m unittest discover -s tests -p 'test_transcribe.py' -v
# Ran 19 tests ... OK
./transcribe.sh --doctor
# Python 3.11.17, torch 2.8.0+cpu, transformers 4.45.2, ffmpeg 6.1.1
./transcribe.sh out/latest --dry-run
# lists all 8 takes and resolves <run>/transcripts
```

The real-model smoke on the current repo completed successfully:

```text
model loaded in 37.8s  torch=2.8.0+cpu  transformers=4.45.2
[1/1] 01-العذل-والمطامع-وفلسفة-الرزق_1332683623  433.2s  ok  abc=2609B
done  ok=1/1  failed=0
```

A warmed resume then reported `skipped (source WAV unchanged)` after a 10.7 s
model load, and `--verify` reported `1/1 ok`.

Follow-up work on 2026-10-24:

- transcribed the accepted Baghdad Moon final with both `--melody-only` and
  `--full`;
- found the original generation cap was **6750**, not the length-matched
  **5397** used by the first guide render;
- rendered one ABC-guided track and ran five cap-6750 variants (combined,
  skeleton, full/chords, temperature 0.7, and vocal-only after the hard-prefix
  test failed);
- confirmed the current prebuilt binary has no `semantic_prefix` support, so the
  hard-prefix variant is a no-op until audio.cpp is rebuilt.

The session record is in
[`docs/sessions/2026-10-24_baghdad_moon_abc_guide.md`](../sessions/2026-10-24_baghdad_moon_abc_guide.md).
The batch path remains `cot=off`; `run_one.sh` gained optional `COT`/`ABC_FILE`,
and `generate.py` explicitly pins `COT=off`. The audio.cpp binary, models, and
LoRAs were not modified.
