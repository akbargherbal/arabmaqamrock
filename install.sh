#!/usr/bin/env bash
# Install the ArabMaqamRock generation stack in this repo:
#   1. clone + build audio.cpp's `audiocpp_cli` (or fetch a prebuilt release asset)
#   2. download the YuE2 GGUF model + VAE + sidecars from Hugging Face
#   3. download the ArabMaqamRock v3 LoRA (AR + NAR) from Hugging Face
#
# Idempotent: re-running skips whatever already exists.
#
# Prerequisites (install these first — this script does not apt-install):
#   git, cmake, g++, the CUDA toolkit (nvcc), ccache, python3, GNU time
#   the `hf` CLI:   pip install -U "huggingface_hub[cli]"
#
# Usage:
#   ./install.sh                     # detect the GPU's compute capability and build
#   ./install.sh --cuda-arch 75      # force a compute capability (e.g. CPU-only builder)
#   ./install.sh --prebuilt          # fetch a matching prebuilt binary instead of building
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AUDIO_CPP="$ROOT/audio.cpp"
BIN="$ROOT/bin/audiocpp_cli"
MODELS="$ROOT/models/Yue2-3B-GGUF"
LORAS="$ROOT/loras"

HF_GGUF_REPO="audio-cpp/Yue2-3B-GGUF"
HF_LORA_REPO="akbargherbal/arabmaqamrock-yue2-lora"
LORA_AR="arabmaqamrock-v3-ar.safetensors"
LORA_NAR="arabmaqamrock-v3-nar.safetensors"
AUDIO_CPP_REPO="https://github.com/0xShug0/audio.cpp"
RELEASE_BASE="https://github.com/akbargherbal/arabmaqamrock/releases/latest/download"

CUDA_ARCH=""
USE_PREBUILT=0
while [ $# -gt 0 ]; do
  case "$1" in
    --cuda-arch) CUDA_ARCH="${2:?--cuda-arch needs a value}"; shift 2 ;;
    --prebuilt)  USE_PREBUILT=1; shift ;;
    -h|--help)   sed -n '2,16p' "$0"; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

need() { command -v "$1" >/dev/null 2>&1 || { echo "MISSING: '$1' — install it first ($2)"; exit 1; }; }
echo "== checking prerequisites =="
need git "apt-get install git"
need python3 "apt-get install python3"
if command -v hf >/dev/null 2>&1; then HF=hf
elif command -v huggingface-cli >/dev/null 2>&1; then HF=huggingface-cli
else echo "MISSING: the 'hf' CLI — run: pip install -U 'huggingface_hub[cli]'"; exit 1; fi
[ -x /usr/bin/time ] || echo "WARN: /usr/bin/time (GNU time) missing — run_one.sh needs it (apt-get install time)"

# --- resolve the CUDA compute capability -----------------------------------
arch_tag() { case "$1" in 75) echo sm75-t4 ;; 80) echo sm80-a100 ;; 89) echo sm89-l4 ;; *) echo "sm$1" ;; esac; }
if [ -z "$CUDA_ARCH" ]; then
  if command -v nvidia-smi >/dev/null 2>&1; then
    CUDA_ARCH="$(nvidia-smi --query-gpu=compute_cap --format=csv,noheader | head -n1 | tr -d '.')"
    echo "detected compute capability -> --cuda-arch $CUDA_ARCH"
  else
    echo "No nvidia-smi and no --cuda-arch. On a CPU-only builder pass e.g. --cuda-arch 75." >&2
    exit 1
  fi
fi

# --- 1. audiocpp_cli -------------------------------------------------------
if [ -x "$BIN" ]; then
  echo "== $BIN already exists; skipping binary step (delete it to redo) =="
elif [ "$USE_PREBUILT" = 1 ]; then
  tag="$(arch_tag "$CUDA_ARCH")"
  mkdir -p "$ROOT/bin"
  echo "== fetching prebuilt binary for $tag =="
  if curl -fL "$RELEASE_BASE/audiocpp_cli.$tag" -o "$BIN"; then
    chmod +x "$BIN"
  else
    echo "No prebuilt asset for $tag — building from source instead."
    USE_PREBUILT=0
  fi
fi
if [ ! -x "$BIN" ]; then
  need cmake "apt-get install cmake"
  need nvcc "install the CUDA toolkit (nvcc)"
  need ccache "apt-get install ccache"
  if [ -d "$AUDIO_CPP/.git" ]; then
    echo "== audio.cpp present; fetching latest =="
    git -C "$AUDIO_CPP" fetch --depth 1 origin && git -C "$AUDIO_CPP" reset --hard FETCH_HEAD
  else
    echo "== cloning audio.cpp =="
    git clone --depth 1 "$AUDIO_CPP_REPO" "$AUDIO_CPP"
  fi
  echo "== building audiocpp_cli (--cuda-arch $CUDA_ARCH) — cold build is ~20+ min =="
  ( cd "$AUDIO_CPP" && scripts/build_linux.sh --backend cuda --cuda-arch "$CUDA_ARCH" --ccache \
      --model-set custom --models yue2 --target audiocpp_cli )
  mkdir -p "$ROOT/bin"
  cp "$AUDIO_CPP/build/linux-cuda-release/bin/audiocpp_cli" "$BIN"
fi
ls -la "$BIN"

# --- 2. YuE2 GGUF model (bf16 + f16 VAE + sidecars) ------------------------
echo "== fetching YuE2 GGUF (bf16 model + f16 VAE + sidecars) =="
mkdir -p "$MODELS"
$HF download "$HF_GGUF_REPO" yue2-3b-bf16.gguf yue2-vae-f16.gguf --local-dir "$MODELS"
$HF download "$HF_GGUF_REPO" --include "sidecars/*" --local-dir "$MODELS"

# --- 3. ArabMaqamRock v3 LoRA ----------------------------------------------
echo "== fetching the ArabMaqamRock v3 LoRA =="
mkdir -p "$LORAS"
$HF download "$HF_LORA_REPO" "$LORA_AR" "$LORA_NAR" --local-dir "$LORAS"

# --- verify ----------------------------------------------------------------
echo "== verifying =="
ok=1
for f in "$BIN" "$MODELS/yue2-3b-bf16.gguf" "$MODELS/yue2-vae-f16.gguf" \
         "$LORAS/$LORA_AR" "$LORAS/$LORA_NAR"; do
  if [ -e "$f" ]; then echo "  [ok] $f"; else echo "  [MISSING] $f"; ok=0; fi
done
[ -d "$MODELS/sidecars" ] && echo "  [ok] $MODELS/sidecars" || { echo "  [MISSING] $MODELS/sidecars"; ok=0; }

if [ "$ok" = 1 ]; then
  echo
  echo "Done. Smoke-check the binary, then generate:"
  echo "  .$(printf '%s' "${BIN#"$ROOT"}") --version        # should print a version, not a link error"
  echo "  python3 generate.py songs.example.json --dry-run"
  echo "  python3 generate.py songs.example.json"
else
  echo "Install incomplete — see the [MISSING] lines above." >&2; exit 1
fi
