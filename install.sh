#!/usr/bin/env bash
# Install the generation stack in this repo:
#   1. stage audiocpp_cli  (prebuilt from GCS if available, else build from source)
#   2. download the YuE2 GGUF model + VAE + sidecars from Hugging Face
#   3. download the ArabMaqamRock v3 LoRA (AR + NAR) from Hugging Face
#
# Idempotent. The binary step is delegated to plumbing/fetch_binary.sh, which is
# GCS-first with a build fallback, so this works both on a Colab VM with GCS access
# (fast) and on a plain box with no credentials (builds from source).
#
# Prerequisites:
#   git, python3, the `hf` CLI  (pip install -U "huggingface_hub[cli]")
#   only for a source build: the CUDA toolkit (nvcc), cmake, ccache
#
# Usage:
#   ./install.sh                     # GCS prebuilt if reachable, else build
#   ./install.sh --cuda-arch 75      # forward the arch (needed to build with no GPU)
#   ./install.sh --build             # force a source build
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

MODELS="$PWD/models/Yue2-3B-GGUF"
LORAS="$PWD/loras"
HF_GGUF_REPO="audio-cpp/Yue2-3B-GGUF"
HF_LORA_REPO="akbargherbal/arabmaqamrock-yue2-lora"
LORA_AR="arabmaqamrock-v3-ar.safetensors"
LORA_NAR="arabmaqamrock-v3-nar.safetensors"

BIN_ARGS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --cuda-arch) BIN_ARGS+=(--cuda-arch "${2:?}"); shift 2 ;;
    --build)     BIN_ARGS+=(--build); shift ;;
    --prebuilt)  shift ;;                      # kept for compatibility; GCS-first is the default
    -h|--help)   sed -n '2,20p' "$0"; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

echo "== checking prerequisites =="
command -v git >/dev/null 2>&1 || { echo "MISSING: git"; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "MISSING: python3"; exit 1; }
if command -v hf >/dev/null 2>&1; then HF=hf
elif command -v huggingface-cli >/dev/null 2>&1; then HF=huggingface-cli
else echo "MISSING: the 'hf' CLI — pip install -U 'huggingface_hub[cli]'"; exit 1; fi
[ -x /usr/bin/time ] || echo "WARN: /usr/bin/time (GNU time) missing — run_one.sh needs it (apt-get install time)"

echo "== 1. binary =="
./plumbing/fetch_binary.sh "${BIN_ARGS[@]}"
[ -x bin/audiocpp_cli ] || { echo "no bin/audiocpp_cli after fetch_binary.sh" >&2; exit 1; }

echo "== 2. YuE2 GGUF model (bf16 + f16 VAE + sidecars) =="
mkdir -p "$MODELS"
$HF download "$HF_GGUF_REPO" yue2-3b-bf16.gguf yue2-vae-f16.gguf --local-dir "$MODELS"
$HF download "$HF_GGUF_REPO" --include "sidecars/*" --local-dir "$MODELS"

echo "== 3. ArabMaqamRock v3 LoRA =="
mkdir -p "$LORAS"
$HF download "$HF_LORA_REPO" "$LORA_AR" "$LORA_NAR" --local-dir "$LORAS"

echo "== verifying =="
ok=1
for f in bin/audiocpp_cli "$MODELS/yue2-3b-bf16.gguf" "$MODELS/yue2-vae-f16.gguf" \
         "$LORAS/$LORA_AR" "$LORAS/$LORA_NAR"; do
  if [ -e "$f" ]; then echo "  [ok] $f"; else echo "  [MISSING] $f"; ok=0; fi
done
[ -d "$MODELS/sidecars" ] && echo "  [ok] $MODELS/sidecars" || { echo "  [MISSING] $MODELS/sidecars"; ok=0; }

if [ "$ok" = 1 ]; then
  echo
  echo "Done. Then:"
  echo "  python3 generate.py songs.example.json --dry-run"
  echo "  python3 generate.py songs.example.json"
else
  echo "Install incomplete — see [MISSING] above." >&2; exit 1
fi
