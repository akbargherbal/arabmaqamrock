#!/usr/bin/env bash
# Install the generation stack in this repo:
#   1. stage audiocpp_cli  (prebuilt from GCS if available, else build from source)
#   2. download the YuE2 GGUF model + VAE + sidecars from Hugging Face
#   3. download the default ArabMaqamRock LoRA sets from Hugging Face:
#        blend a0.15 (v3 x instrumental)   -> loras/blend/a0.15/
#        own instrumental pair             -> loras/arabic-instrumental/
#      These two are the default generation stack; the scales, guidance and
#      cot settings are in docs/generation-defaults.md. The other own sets (v3
#      style pair, blend a0.1, blend a0.2) are kept below as commented-out
#      downloads in section 3 — uncomment the matching block (and its sha256
#      line) only if a manifest needs them.
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
LORAS="$PWD/loras"
HF_GGUF_REPO="audio-cpp/Yue2-3B-GGUF"
HF_LORA_REPO="akbargherbal/arabmaqamrock-yue2-lora"
HF_INSTR_OWN_REPO="akbargherbal/arabic-instrumental-yue2-lora"
HF_BLEND_REPO="akbargherbal/arabmaqamrock-blend-yue2-lora"
LORA_AR="arabmaqamrock-v3-ar.safetensors"
LORA_NAR="arabmaqamrock-v3-nar.safetensors"
INSTR_AR="arabic-instrumental-ar.safetensors"
INSTR_NAR="arabic-instrumental-nar.safetensors"
BLEND_A1_AR="a0.1/v3instr_a0.1_ar.safetensors"
BLEND_A1_NAR="a0.1/v3instr_a0.1_nar.safetensors"
BLEND_A15_AR="a0.15/v3instr_a0.15_ar.safetensors"
BLEND_A15_NAR="a0.15/v3instr_a0.15_nar.safetensors"
BLEND_A2_AR="a0.2/v3instr_a0.2_ar.safetensors"
BLEND_A2_NAR="a0.2/v3instr_a0.2_nar.safetensors"

# sha256 pins (from the published model cards); mismatches are warnings, not
# failures — a corrected upstream re-upload should not brick the installer.
LORA_SHA256_AR="3531bb9106d2292eefe58eabe11ec08bb7dddc69554f2b016dc9f13f711fab18"
LORA_SHA256_NAR="a7eabcadb22146048bcb5e65d04828ee9454559523ca161bd38c06060deb0cae"
INSTR_SHA256_AR="69517eea8bbc9fec2ace47c271f1bde7058881e89eabe9f9c0b10cb91ae97edb"
INSTR_SHA256_NAR="f84fdd4e9332c8be27e2d716fec9048f3d8ea3835c5e7582d6689322b6e0ea2f"
BLEND_A1_SHA256_AR="d48109b3117bf7851390ac9d4de86a45c5edd99cc5d17ddb97481e5c77ef64a0"
BLEND_A1_SHA256_NAR="88f00bcb1b60cb7638eff07d7f1a7ff1d19705e987a138bf82e0c36e84ea5b58"
BLEND_A15_SHA256_AR="fef2104e13560700e118af92b7be139f7711df59e2a68ddde4691a0e5a5fecc3"
BLEND_A15_SHA256_NAR="e1696863534e330b290ad92fbe16d904b69b8e5eebf208b9ba738778447a1fb7"
BLEND_A2_SHA256_AR="820f1ce90ab64965606a5a57451b2dcf255072ab4b9c7be182bc14b80bd86dd6"
BLEND_A2_SHA256_NAR="f9738e214361c02428f6baa01327ba42ce1208236d33868fd6c3d3a7b584225f"

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

echo "== 3. LoRAs from Hugging Face (default: blend a0.15 + own instrumental) =="
mkdir -p "$LORAS" "$LORAS/arabic-instrumental" "$LORAS/blend/a0.15"

echo "-- 3a. Arabic instrumental (own adapter, no vocals) --"
$HF download "$HF_INSTR_OWN_REPO" "$INSTR_AR" "$INSTR_NAR" --local-dir "$LORAS/arabic-instrumental"

echo "-- 3b. blend a0.15 of v3 x instrumental (alpha baked in) --"
$HF download "$HF_BLEND_REPO" "$BLEND_A15_AR" "$BLEND_A15_NAR" --local-dir "$LORAS/blend"

# --- optional LoRA sets: NOT downloaded by default ---------------------------
# The blend a0.15 pair already carries the v3 style/voice character, so the
# standalone v3 pair and the a0.1/a0.2 blend arms are staged only on demand.
# Uncomment a block (download + its sha256 line) when a manifest needs it.
#
# echo "-- opt-in: ArabMaqamRock v3 (style, vocals) --"
# mkdir -p "$LORAS"
# $HF download "$HF_LORA_REPO" "$LORA_AR" "$LORA_NAR" --local-dir "$LORAS"
#
# echo "-- opt-in: blend a0.1 of v3 x instrumental --"
# mkdir -p "$LORAS/blend/a0.1"
# $HF download "$HF_BLEND_REPO" "$BLEND_A1_AR" "$BLEND_A1_NAR" --local-dir "$LORAS/blend"
#
# echo "-- opt-in: blend a0.2 of v3 x instrumental --"
# mkdir -p "$LORAS/blend/a0.2"
# $HF download "$HF_BLEND_REPO" "$BLEND_A2_AR" "$BLEND_A2_NAR" --local-dir "$LORAS/blend"

echo "-- 3c. sha256 check (warn only; this run's downloads, --verify for all) --"
sha256_warn() {  # file, expected
  [ -e "$1" ] || return 0
  # Hashing multi-hundred-MB adapters on every idempotent re-run is the slowest
  # part of a restart, so cached files are skipped unless --verify was passed.
  if [ "$FORCE_VERIFY" = 0 ] \
     && [ $(( $(date +%s) - $(stat -c %Y "$1") )) -gt 300 ]; then
    echo "  [skip] sha256 (cached): $(basename "$1") — use --verify to re-hash"
    return 0
  fi
  if echo "$2  $1" | sha256sum -c - >/dev/null 2>&1; then
    echo "  [ok] sha256: $(basename "$1")"
  else
    echo "  [WARN] sha256 mismatch: $1 (expected $2)" >&2
  fi
}
sha256_warn "$LORAS/arabic-instrumental/$INSTR_AR" "$INSTR_SHA256_AR"
sha256_warn "$LORAS/arabic-instrumental/$INSTR_NAR" "$INSTR_SHA256_NAR"
sha256_warn "$LORAS/blend/$BLEND_A15_AR" "$BLEND_A15_SHA256_AR"
sha256_warn "$LORAS/blend/$BLEND_A15_NAR" "$BLEND_A15_SHA256_NAR"
# Opt-in sets (one line per downloaded file; enable with the download blocks):
# sha256_warn "$LORAS/$LORA_AR" "$LORA_SHA256_AR"
# sha256_warn "$LORAS/$LORA_NAR" "$LORA_SHA256_NAR"
# sha256_warn "$LORAS/blend/$BLEND_A1_AR" "$BLEND_A1_SHA256_AR"
# sha256_warn "$LORAS/blend/$BLEND_A1_NAR" "$BLEND_A1_SHA256_NAR"
# sha256_warn "$LORAS/blend/$BLEND_A2_AR" "$BLEND_A2_SHA256_AR"
# sha256_warn "$LORAS/blend/$BLEND_A2_NAR" "$BLEND_A2_SHA256_NAR"

echo "== verifying =="
ok=1
for f in bin/audiocpp_cli "$MODELS/yue2-3b-bf16.gguf" "$MODELS/yue2-vae-f16.gguf" \
         "$LORAS/arabic-instrumental/$INSTR_AR" "$LORAS/arabic-instrumental/$INSTR_NAR" \
         "$LORAS/blend/$BLEND_A15_AR" "$LORAS/blend/$BLEND_A15_NAR"; do
  if [ -e "$f" ]; then echo "  [ok] $f"; else echo "  [MISSING] $f"; ok=0; fi
done
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
