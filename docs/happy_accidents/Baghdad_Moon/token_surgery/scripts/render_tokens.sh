#!/usr/bin/env bash
# Render an exact YuE2 semantic token stream to WAV with the prefix-capable binary.
# Usage: render_tokens.sh <tokens.json> <out.wav> [binary] [seed]
#   tokens.json : flat JSON array, 25 fps, values in [0,32768)
#   binary      : prefix-capable audiocpp_cli (default: $REPO/bin/audiocpp_cli_prefix)
#   seed        : only used for NAR noise/metadata; default original 1712905618
set -euo pipefail
REPO=/content/arabmaqamrock
TOK="${1:?tokens.json}"
OUT="${2:?out.wav}"
BIN="${3:-$REPO/bin/audiocpp_cli_prefix}"
SEED="${4:-1712905618}"
LYRICS="$REPO/happy_accident/prompts/02B_lyrics.txt"
STYLE="$REPO/happy_accident/prompts/02B_style.txt"
N=$(python3 -c "import json,sys; a=json.load(open(sys.argv[1])); assert all(isinstance(x,int) and 0<=x<32768 for x in a); print(len(a))" "$TOK")
echo "[render_tokens] frames=$N tokens=$TOK"
[ "$N" -gt 0 ] || { echo "empty token stream" >&2; exit 1; }
sha256sum "$LYRICS" "$STYLE"
cd "$REPO"
. ./cuda_loader_path.sh
mkdir -p "$(dirname "$OUT")"
"$BIN" --task gen --family yue2 --model models/Yue2-3B-GGUF --backend cuda --threads 8 \
  --session-option yue2.model_gguf=yue2-3b-bf16.gguf \
  --session-option yue2.vae_gguf=yue2-vae-f16.gguf \
  --session-option yue2.ar_lora="$REPO/loras/arabmaqamrock-v3-ar.safetensors" \
  --session-option yue2.ar_lora_scale=1.0 \
  --session-option yue2.nar_lora="$REPO/loras/arabmaqamrock-v3-nar.safetensors" \
  --session-option yue2.nar_lora_scale=1.0 \
  --session-option yue2.attention=flash \
  --lyrics "$(cat "$LYRICS")" \
  --request-option style="$(cat "$STYLE")" \
  --request-option cot=off \
  --request-option semantic_prefix_file="$TOK" \
  --request-option semantic_min_tokens="$N" \
  --request-option semantic_max_tokens="$N" \
  --request-option export_semantic=true \
  --seed "$SEED" \
  --out "$OUT" \
  --out-dir "$(dirname "$OUT")/artifacts" \
  --log
sha256sum "$OUT"
