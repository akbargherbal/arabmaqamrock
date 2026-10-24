# ArabMaqamRock — generation

Generate **Arabic maqam rock** songs from lyrics you supply, using a fine-tuned
**YuE2** LoRA. This repo is the *what we have and how to use it* half of the project:
download, build, generate. No training, no cloud, no infrastructure.

- **What you get:** a LoRA that turns YuE2 into a symphonic/orchestral Arabic
  maqam-rock generator (four maqams: Hijaz, Kurd, Nahawand, Ajam).
- **What you need:** an NVIDIA CUDA GPU.
- **License:** the weights are **non-commercial** (CC-BY-NC-4.0). Read
  [License](#license) before you use anything.

> Status: **BETA.** The v3 adapter was listening-judged 4/5; quality is a settings
> problem, not a finished product. See [MODEL_CARD.md](MODEL_CARD.md) and the parent
> repo for the research trail.

## Requirements

| | |
|---|---|
| GPU | NVIDIA CUDA GPU. Verified on a **Tesla T4**; also builds/runs on L4 (sm_89) and A100 (sm_80) |
| Disk | ~15 GB (CUDA build tree + ~7.5 GB GGUF + adapters) |
| Toolchain | CUDA toolkit (`nvcc`), `cmake`, `g++`, `ccache`, `git`, GNU `time` (`/usr/bin/time`), Python 3 |
| HF CLI | `pip install -U "huggingface_hub[cli]"` (provides `hf`) |
| Base model | downloaded automatically from [`audio-cpp/Yue2-3B-GGUF`](https://huggingface.co/audio-cpp/Yue2-3B-GGUF) |

On Debian/Ubuntu: `apt-get install git cmake g++ ccache time python3` plus the
[NVIDIA CUDA toolkit](https://developer.nvidia.com/cuda-downloads).

## Quickstart

```bash
git clone https://github.com/akbargherbal/arabmaqamrock.git
cd arabmaqamrock

./install.sh                        # stage the binary + fetch the model & LoRA

python3 generate.py songs.example.json --dry-run   # validate + print the plan (no GPU, writes nothing)
python3 generate.py songs.example.json             # the real run  → out/<timestamp>_.../  (a .wav)
```

`install.sh` stages `audiocpp_cli` for your GPU's arch — from this project's GCS
prefix when reachable (fast), otherwise by building from source (~20 min cold; no GPU
needed to build). Force either path:

```bash
./plumbing/fetch_binary.sh --cuda-arch 75   # build for sm_75 yourself
./plumbing/fetch_binary.sh --build          # force a source build
```

### On Colab (ephemeral VM)

Colab wipes `/content` on VM loss, so this repo fetches fast and backs up its output:

```bash
git clone https://github.com/akbargherbal/arabmaqamrock.git /content/arabmaqamrock
cd /content/arabmaqamrock
./setup_colab.sh    # binary (prebuilt, arch-selected) + model + LoRA + backup sidecar
python3 generate.py songs.example.json
```

`setup_colab.sh` wants `gcloud auth login` (to read the prebuilt binary and write
backups) and `HF_TOKEN`. Outputs mirror to
`gs://akbar-december-2024-backup/arabmaqamrock/runs/`. The helpers live in
[`plumbing/`](plumbing/) — you do not need any of them to just generate.

Expect **~6–7 minutes per track** on a T4. Generation is **sequential** (two
concurrent runs can run out of memory), so a batch of N songs takes roughly N × that.

## Bring your own lyrics

A run is driven by one JSON file. Each song takes a **style** (or a style file) and
**lyrics** (or a lyrics file), and renders 1..N takes.

```json
{
  "defaults": { "style_file": "prompts/Hijaz_style.txt", "quantile": 0.95 },
  "songs": [
    { "name": "my_song",  "lyrics": "[Verse 1]\nيا لَيلُ ...", "seed": 7 },
    { "name": "two_takes", "lyrics_file": "my_lyrics.txt", "repeat": 2 }
  ]
}
```

```bash
python3 generate.py my_songs.json --dry-run     # plan only
python3 generate.py my_songs.json               # generate
python3 generate.py my_songs.json --out-dir out/20261013_mysongs   # resume later (skips finished takes)
```

Per-song fields (`strict` — unknown keys are an error):

| Field | Meaning |
|---|---|
| `name` | required slug (letters/digits, `-`/`_`); the output filename prefix |
| `style` / `style_file` | exactly one — the style text, or a path (relative to the JSON) |
| `lyrics` / `lyrics_file` | exactly one — the lyrics |
| `seed` / `seeds` / `repeat` | one seed, an explicit list, or N takes with random seeds (`< 2^32`) |
| `cap` / `quantile` | explicit token cap, or a quantile (0.90 / 0.95 / 0.975, default 0.95) |
| `lora` | optional alias into the top-level `loras` map (see below) |

`defaults` supplies `style`/`style_file`, `repeat`, `quantile`, and `lora` for every
song. The trigger word **`arabmaqamrock`** is prepended to any style that lacks it
(every training caption carried it; disable with `--no-trigger`).

The optional top-level `loras` map lets one batch mix adapters:

```json
"loras": { "v3": { "dir": "loras" }, "quran": { "dir": "loras/quran" } }
```

Useful flags: `--dry-run`, `--limit N`, `--label`, `--out-dir`, `--force`,
`--lora-ar` / `--lora-nar`, `--no-trigger`. Sampler knobs
(`guidance_scale`, `semantic_temperature`, `semantic_repetition_penalty`) pass through
the `EXTRA_REQUEST_OPTS` environment variable, e.g.:

```bash
EXTRA_REQUEST_OPTS="guidance_scale=1.5" python3 generate.py my_songs.json
```

## Maqams

Four style templates ship in `prompts/`, one per maqam — use them as-is or edit them:

| File | Maqam | Mood |
|---|---|---|
| `prompts/Hijaz_style.txt` | Hijaz | poignant, chivalric, emotional |
| `prompts/Kurd_style.txt` | Kurd | tense, ominous, lethal, dramatic |
| `prompts/Nahawand_style.txt` | Nahawand | nostalgic, faithful, solemn hope |
| `prompts/Ajam_style.txt` | Ajam | heroic, proud, defiant |

`prompts/example_lyrics.txt` is the lyrics file used by the smoke test.

Single-track use without JSON (style/lyrics default to `prompts/<Maqam>_*.txt`):

```bash
STYLE_FILE=prompts/Kurd_style.txt LYRICS_FILE=my_lyrics.txt ./run_one.sh Kurd 1
```

## Output

Every run lands in `out/<YYYYMMDD-HHMMSS>_<label>/`:

```
input.json                 exact copy of your input
batch_manifest.json        resolved seeds/caps + asset hashes (written before generation)
batch_summary.txt          per-track exit/wall/duration
prompts/<name>_{style,lyrics}.txt   the conditioning text actually used
<name>_<seed>.wav          the audio
<name>_<seed>.log / _time.txt / _gpu.csv / .json   per-track log, timings, GPU trace, sidecar
```

`out/latest` names the newest run. Re-run with `--out-dir <folder>` to resume.

## Optional: symbolic transcription

Turn a finished run into melody **ABC** scores on CPU with SheetSage2. This is
separate from generation: no GPU, no changes to `bin/audiocpp_cli`, and no extra
model in the audio.cpp stack.

```bash
./plumbing/setup_transcribe.sh        # once; CPU wheels by default
./transcribe.sh out/latest --dry-run  # plan only
./transcribe.sh out/latest --smoke    # one track
./transcribe.sh out/latest            # whole run
```

Scores land in `out/<run>/transcripts/<name>_<seed>/score.abc`, with MIDI/event
side artifacts, a per-track `meta.json`, and a run-level manifest. Existing
scores are skipped only when their recorded source-WAV hash still matches; use
`--force` after re-rendering a take.

See [docs/transcription.md](docs/transcription.md) for CPU/GPU options, resume
guards, and licensing. ABC scores can also be used as a symbolic guide for a new
render via `run_one.sh`’s `COT`/`ABC_FILE` environment variables; see
[the Baghdad Moon session](docs/sessions/2026-10-24_baghdad_moon_abc_guide.md).
The optional env is also available via `./install.sh --with-transcribe` and
`./setup_colab.sh --with-transcribe`.

## License

**The weights are non-commercial.** This project is a derivative of
[YuE2](https://huggingface.co/m-a-p/YuE2-3B), which is **CC-BY-NC-4.0**. The LoRAs
released here inherit that: **non-commercial use only.**

- **Code** in this repository: **MIT** (see [LICENSE](LICENSE)).
- **Weights** (the LoRAs) and the base model: **CC-BY-NC-4.0** (see
  [MODEL_CARD.md](MODEL_CARD.md)).
- **Transcription model** (optional): SheetSage2 / MERT-v2-FullSong are
  **CC-BY-NC-4.0**; their use is non-commercial too.
- The training data (Suno-rendered audio) is **not** distributed.

## Provenance

- **Weights:** [`akbargherbal/arabmaqamrock-yue2-lora`](https://huggingface.co/akbargherbal/arabmaqamrock-yue2-lora)
  (v3) and [`akbargherbal/quran-pronunciation-yue2-lora`](https://huggingface.co/akbargherbal/quran-pronunciation-yue2-lora).
- **Parent project** (training, dataset, research trail, monitoring): [`akbargherbal/maqamrock-yue2-lora-finetuning`](https://github.com/akbargherbal/maqamrock-yue2-lora-finetuning).
- **Base model:** [`m-a-p/YuE2-3B`](https://huggingface.co/m-a-p/YuE2-3B) →
  [`audio-cpp/Yue2-3B-GGUF`](https://huggingface.co/audio-cpp/Yue2-3B-GGUF).
- **Runtime:** [`0xShug0/audio.cpp`](https://github.com/0xShug0/audio.cpp).
- **Training toolkit:** [`ostris/ai-toolkit`](https://github.com/ostris/ai-toolkit).
