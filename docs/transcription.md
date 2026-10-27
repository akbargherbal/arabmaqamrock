# Symbolic transcription (SheetSage2)

Turn a finished generation run into a symbolic melody score with the official
[`m-a-p/SheetSage2`](https://huggingface.co/m-a-p/SheetSage2) model. This is an
**optional, CPU-default** tool: it does not touch the audio.cpp generation stack
and does not need a GPU.

> This is melody/score transcription, not lyric transcription or pronunciation
> verification. For ASR/CTC checks of a repair, use the scripts under
> `docs/happy_accidents/.../scripts/`.

## What you get

For each take `<name>_<seed>.wav`:

```
out/<run>/transcripts/<name>_<seed>/
  score.abc                  primary artifact
  transcription.mid          combined MIDI
  melody_vocal.mid           vocal melody
  melody_instrumental.mid    instrumental melody
  melody_*.lab               timed melody annotations
  events.json / events.tsv   timed annotations
  beat.lab / downbeat.lab / key.lab / chord.lab / structure.lab
  notation/                  beat/chord/key/structure text exports
  tokens.json / tokens.txt   model token stream
  meta.json                  source hash + model/env provenance
```

plus run-level `_driver.log`, `_timings.csv`, and `transcribe_manifest.json`.

`--melody-only` (the default) keeps the Vocal and Ins melody staves and omits
chord symbols from the ABC. It is **not** “lead vocal only”. Use `--full` for a
full SheetSage2 transcription with chord symbols.

## Install

Prerequisites:

- `uv` (`python3 -m pip install -U uv`)
- `ffmpeg` (upstream recommends 6.1 with shared libraries)
- ~3–5 GB of disk for the venv and model cache

```bash
./plumbing/setup_transcribe.sh            # CPU wheels (recommended)
./plumbing/setup_transcribe.sh --cuda     # CUDA 12.6 wheels, optional
./plumbing/setup_transcribe.sh --doctor   # build/reuse, then diagnostics
./plumbing/setup_transcribe.sh --warm     # also pre-download the models
```

The env is repo-local at `.venv-sheetsage2/` and ignored by git. The system
Python (3.13 / transformers 5.x here) is not compatible with SheetSage2’s custom
code; the venv pins Python 3.11, `torch==2.8.0`, and `transformers==4.45.2`.

`./install.sh --with-transcribe` and `./setup_colab.sh --with-transcribe` call
the same setup script. It remains opt-in.

## Use

```bash
# Plan only: no model load, no writes.
./transcribe.sh out/latest --dry-run

# One track, then stop. Use this before a batch.
./transcribe.sh out/latest --smoke

# The whole newest run.
./transcribe.sh out/latest

# Explicit run + separate output tree.
./transcribe.sh out/20261024-102834_ibn_zuraiq_formatted \
  --out-dir /tmp/abc_ibn_zuraiq
```

`out/latest` is the text pointer written by `generate.py`. `transcribe.sh` runs
the driver inside `.venv-sheetsage2`; `python3 transcribe.py` also works for
`--dry-run`, `--verify`, and `--doctor` without the venv.

Common flags:

| Flag | Meaning |
|---|---|
| `--device cpu\|cuda\|auto` | default `auto`; `auto` chooses CUDA when `torch.cuda.is_available()` |
| `--dtype auto\|bf16\|fp32` | CUDA compute dtype; `auto` picks bf16 only on native-bf16 GPUs, fp32 on T4 |
| `--threads N` | torch CPU threads (default `min(4, CPU count)`) |
| `--exclude REGEX` | skip matching stems; **no default exclusion** |
| `--limit N`, `--smoke` | cap the batch / one-track smoke |
| `--force` | re-transcribe even when a valid ABC exists |
| `--verify` | re-check ABC + source hashes without loading the model |
| `--fail-fast` | stop at the first failure (default: continue) |
| `--time-budget SEC` | stop starting new tracks after SEC |
| `--per-track-timeout SEC` | best-effort per-track alarm |
| `--on-collision error\|suffix` | duplicate-stem policy (default: error) |
| `--cache-dir DIR` | use DIR as `HF_HOME` for the model cache |
| `--doctor` | environment diagnostics |

There is intentionally **no default `_[23]_` exclusion**. Real take names in
this repo can contain those markers, e.g.
`03-الرد-على-الواشي-والرسوخ-كالأرعن_3_810750224.wav` in
`cases/001_harith03_faadduha/`. Excluding them silently was a bug in the
ancestor driver.

## Resume and stale-ABC guard

An existing `score.abc` is skipped only when its `meta.json` says the last
transcription succeeded, records the same `source_wav_sha256` as the current
WAV, and its `abc_sha256` matches the ABC on disk:

- **all three match** → `skipped`
- **different source hash** → `stale`, exit 1; re-run with `--force`
- **previous status was not `ok`** → retried automatically
- **no `meta.json`** → `skipped-unverified` with a warning; `--force` redoes it
- **ABC does not match `abc_sha256`** → `invalid`, exit 1; `--force` redoes it

This prevents the ancestor failure mode where an old ABC is silently paired with
a re-rendered take, and it also prevents a failed `--force` run from being
mistaken for a finished one. `--verify` performs the same checks without loading
the model.

## CPU / GPU

| Scenario | Result |
|---|---|
| CPU-only machine / Colab CPU runtime | Works with the default CPU wheels; no CUDA runtime |
| GPU box, transcribing only | `auto` uses the GPU once the venv has CUDA wheels; the default install is CPU-only |
| GPU box, generating and transcribing | Pass `--device cpu` (or `CUDA_VISIBLE_DEVICES=""`) to keep the GPU free |
| CUDA-accelerated transcription | `setup_transcribe.sh --cuda` then `--device auto` (or `cuda`) |

`--device auto` uses the GPU whenever the venv has a CUDA torch build. The
default install uses CPU wheels, so check `torch.cuda.is_available()` (or run
`transcribe.py --doctor`) before expecting GPU speed. On a T4, `--dtype auto`
falls back to fp32 because Turing only emulates bf16; pass `--dtype bf16` only
on Ampere or newer.

The audio.cpp SheetSage2 backend is **not** used here. The current
`bin/audiocpp_cli` is built `--models yue2`, has no SheetSage2 family, and is
CUDA-linked; using it would require a separate rebuild and model download. The
Python path produces the same `score.abc` without touching generation.

Measured upstream on CPU: roughly **4–6 minutes per track** and **~4.3 GB peak
RAM** for a ≤10-minute song. Long tracks are processed sequentially; memory is
not shared across tracks.

Measured in this repo on a 2-vCPU / 12 GB CPU box: **433 s for a 272 s track**
(2 threads, ~2.6 KB ABC) with roughly **4 GB RSS**; a warmed resume that skipped
the same track took 10.7 s to load the model and 0.2 s to finish.

The Baghdad Moon session measured **417.1 s** for a 215.9 s melody-only score
and **381.9 s** for the full/chords score on the same box. It also has a worked
ABC-guided render and five variants:
[`docs/sessions/2026-10-24_baghdad_moon_abc_guide.md`](sessions/2026-10-24_baghdad_moon_abc_guide.md).

## Use the ABC as a guide (advanced)

The generation runner accepts two optional environment variables:

```bash
OUT_DIR=/path/to/guide-run \
STYLE_FILE=/path/to/style.txt \
LYRICS_FILE=/path/to/lyrics.txt \
COT=melody \
ABC_FILE=/path/to/score.abc \
./run_one.sh MyGuideSong 20261024 6750
```

- `COT` is `off` by default. ABC conditioning requires `melody` or `full`.
- `ABC_FILE` must be a melody ABC; for a SheetSage2 `--melody-only` score use
  `COT=melody`.
- The final argument is `semantic_max_tokens`; use a cap that matches the
  score/lyrics length (25 frames per second). The original Baghdad Moon batch
  used **6750** (`q=0.95`, 507 letters). A length-matched **5397** cap
  (`215.879 s × 25`) hits the cap, so use 6750 for a like-for-like run.
- Pick a **new seed** for a new rendition.

For batch runs, the same thing is available from the JSON: `input.scores`
aliases plus `abc_file` and `cot` per song (see the README section *ABC scores
(melody / chord conditioning)*). The batch path records the score's sha256 in
`batch_manifest.json` and refuses to resume a take whose score changed.

This is a symbolic guide, not audio-to-audio, and it is **off-distribution** for
the v3 adapter (trained with `cot=off`). It is not expected to reproduce the
source track bit-for-bit; listen before trusting it.

## Controlling ABC influence

There is no single “ABC strength” value. The score is a token prefix, so
influence is structural.

| Control | Effect |
|---|---|
| Score scope/content | A short or sparse score is a loose hint; a full, note-dense score constrains more |
| `cot=melody` vs `cot=full` | Full/chord-annotated ABC adds harmonic constraints |
| Vocal-only vs Vocal+Ins | Vocal-only steers singing and leaves arrangement freer; keeping both constrains both |
| Partial score | Guides only the covered section; the model extrapolates beyond it |
| `semantic_prefix[_file]` | Forces exact semantic frames at the start; the strongest lock |
| `semantic_temperature`, `semantic_top_p/k` | Soft sampling controls; lower is usually tighter/more repeatable |
| Seed | Different seeds find different compromises; useful for selection |

Things that are **not** ABC-strength controls:

- `guidance_scale` amplifies style/lyrics, not the ABC. With an external score,
  the same ABC is present in both CFG branches. If style conflicts with the
  score, raising guidance can move away from the ABC.
- `abc_temperature`, `abc_top_p`, `abc_top_k`, `abc_repetition_penalty`,
  `abc_min_tokens`, `abc_max_tokens` apply only when the model generates its
  own ABC. They are ignored with an external `abc` / `abc_file`.
- `num_inference_steps` affects NAR rendering quality, not ABC adherence.

**Current binary note:** `bin/audiocpp_cli` in this repo has no
`semantic_prefix` / `semantic_prefix_file` support (`strings bin/audiocpp_cli |
grep semantic_prefix` is empty). The hard-lock row needs a newer audio.cpp build;
without it, passing the option is silently a no-op.

A worked session with five variants is in
[`docs/sessions/2026-10-24_baghdad_moon_abc_guide.md`](sessions/2026-10-24_baghdad_moon_abc_guide.md).

## Provenance

The driver records:

- source WAV path, size, duration, SHA-256
- ABC SHA-256 and size
- SheetSage2 model ID and pinned revision
- Python/torch/transformers versions, device, thread count
- source run and `batch_manifest.json` hash when present
- per-track status, seconds, and error

The default model revision is
`b83c3d79a6d98bcffaf8f9ed112c90aa887887bc`. Override with `--revision` or
`SHEETSAGE2_REVISION`; a different revision is recorded in the manifest.

The model is loaded by repository ID with `trust_remote_code=True`. A local
snapshot cannot be used directly because SheetSage2’s custom module imports a
sibling module that a local-directory load does not cache correctly.

## Backup

Outputs live under `out/<run>/transcripts/`, so the existing backup sidecar
(`plumbing/backup_to_gcp.py`) mirrors them with the rest of the run. There is no
separate `--gcs` flag.

```bash
python3 plumbing/backup_to_gcp.py --once --dry-run
```

## Licensing

SheetSage2 and its MERT-v2-FullSong backbone are **CC-BY-NC-4.0**. This repo’s
code is MIT, but use of the transcription model and its outputs is
non-commercial. This is separate from, and in addition to, the non-commercial
terms of the ArabMaqamRock LoRA weights.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `SheetSage2 env not found` | `./plumbing/setup_transcribe.sh` |
| `IMPORT FAIL` for torch/transformers in `--doctor` | You are outside the venv; use `./transcribe.sh` |
| `ffmpeg: MISSING` | `apt-get install -y ffmpeg` |
| HF rate limit / 401 | Set `HF_TOKEN`; both repos are public but rate-limited |
| `stale` on a track | The WAV changed; use `--force` if the new take is intended |
| `invalid` ABC | Re-run that track with `--force`; check `_driver.log` |
| OOM on CPU | Close other jobs; the model needs ~4.3 GB peak |
| Model download is slow | `setup_transcribe.sh --warm`, or pre-populate `~/.cache/huggingface` |

For the design rationale and the full adaptation plan, see
[`docs/plans/transcription-tools-adaptation.md`](plans/transcription-tools-adaptation.md).
