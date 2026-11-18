#!/usr/bin/env bash
# Install the generation stack in this repo:
#   1. stage audiocpp_cli  (prebuilt from GCS if available, else build from source)
#   2. download the YuE2 GGUF model + VAE + sidecars from Hugging Face
#   3. stage the default LoRA sets declared in plumbing/loras.manifest
#      (today: blend a0.15 + the own Arabic-instrumental pair). That file is the
#      one place to add a set or flip one from opt-in to default; it also holds
#      the sha256 pins. The scales/guidance/cot preset is docs/generation-defaults.md.
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
#   ./install.sh --verify            # re-hash cached LoRAs too (default: only fresh downloads)
#   ./install.sh --with-transcribe   # also build the optional SheetSage2 venv
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

MODELS="$PWD/models/Yue2-3B-GGUF"
HF_GGUF_REPO="audio-cpp/Yue2-3B-GGUF"
# LoRA repos, paths and sha256 pins live in plumbing/loras.manifest; stage them
# with plumbing/fetch_loras.sh (below) instead of editing this script.

BIN_ARGS=()
WITH_TRANSCRIBE=0
FORCE_VERIFY=0       # 0 = sha256 only for files fetched in this run (fast restart)
while [ $# -gt 0 ]; do
  case "$1" in
    --cuda-arch) BIN_ARGS+=(--cuda-arch "${2:?}"); shift 2 ;;
    --build)     BIN_ARGS+=(--build); shift ;;
    --with-transcribe) WITH_TRANSCRIBE=1; shift ;;
    --verify)    FORCE_VERIFY=1; shift ;;      # re-hash every staged LoRA, even cached ones
    --prebuilt)  shift ;;                      # kept for compatibility; GCS-first is the default
    -h|--help)   awk 'NR>1 && /^set -euo/{exit} NR>1{print}' "$0"; exit 0 ;;
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

echo "== 3. LoRAs from Hugging Face (plumbing/loras.manifest) =="
if [ "$FORCE_VERIFY" = 1 ]; then
  ./plumbing/fetch_loras.sh --verify
else
  ./plumbing/fetch_loras.sh
fi

echo "== verifying =="
ok=1
for f in bin/audiocpp_cli "$MODELS/yue2-3b-bf16.gguf" "$MODELS/yue2-vae-f16.gguf"; do
  if [ -e "$f" ]; then echo "  [ok] $f"; else echo "  [MISSING] $f"; ok=0; fi
done
./plumbing/fetch_loras.sh --check || ok=0
[ -d "$MODELS/sidecars" ] && echo "  [ok] $MODELS/sidecars" || { echo "  [MISSING] $MODELS/sidecars"; ok=0; }

if [ "$ok" = 1 ]; then
  if [ "$WITH_TRANSCRIBE" = 1 ]; then
    echo "== 4. optional transcription env =="
    ./plumbing/setup_transcribe.sh
  fi
  echo
  echo "Done. The built-in adapter pair is the staged blend a0.15 pair:"
  echo "  python3 generate.py manifests/songs.example.json --dry-run"
  echo "  (drop --dry-run to actually render; use loras/arabic-instrumental/ for the"
  echo "   instrumental-only pair; the v3 pair is opt-in — see the commented blocks above)"
  if [ "$WITH_TRANSCRIBE" = 1 ]; then
    echo "  ./transcribe.sh out/latest --dry-run"
  else
    echo "  (optional) ./plumbing/setup_transcribe.sh && ./transcribe.sh out/latest --dry-run"
  fi
else
  echo "Install incomplete — see [MISSING] above." >&2; exit 1
fi
