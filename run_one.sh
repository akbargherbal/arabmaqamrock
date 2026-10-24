#!/usr/bin/env bash
# One observed YuE2 generation (LoRA AR+NAR scale 1.0) with audio.cpp.
# Usage: run_one.sh <Maqam> <seed> [semantic_max_tokens]
#   cap defaults to "auto": derived from the lyrics via duration_cap.py
#   (95th-percentile cap dur_cap = 111.1 + 0.3126*N_letters, rounded to 10 s;
#   covers ~94.8% -- an upper bound, not a mean). Pass an integer to override.
# Env overrides (used by generate.py, and usable directly):
#   OUT_DIR     output folder for this run's files (default: $ROOT/out)
#   STYLE_FILE  style text file (default: $ROOT/prompts/<Maqam>_style.txt)
#   LYRICS_FILE lyrics text file (default: $ROOT/prompts/<Maqam>_lyrics.txt)
#   COT         symbolic route: off | melody | full (default: off). melody/full
#               generate (or consume, with ABC_FILE) an ABC score first.
#   ABC_FILE    external ABC score; requires COT=melody|full
#   PLAN_DIR    pass --out-dir here: when COT != off and no ABC_FILE is given,
#               the model's planned score.abc is written into this folder
#   LORA_AR     AR adapter (default: $ROOT/loras/arabmaqamrock-v3-ar.safetensors)
#   LORA_NAR    NAR adapter (default: $ROOT/loras/arabmaqamrock-v3-nar.safetensors)
#   LORA_AR_SCALE / LORA_NAR_SCALE  per-expert adapter strength, default 1.0.
#               Scale 0 switches that expert's adapter off (base weights).
# Writes everything under $OUT so each run is self-contained:
#   $OUT/<Maqam>_<seed>.wav        audio
#   $OUT/<Maqam>_<seed>.log        CLI --log (TRACE/TIMING, errors)
#   $OUT/<Maqam>_<seed>_time.txt   /usr/bin/time -v (wall, max RSS, CPU%)
#   $OUT/<Maqam>_<seed>_gpu.csv    1 Hz: util, mem_used, power, temp
#   $OUT/_runs_status.log          one START/END line per run (always)
set -u
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$SCRIPT_DIR"
M="${1:?usage: run_one.sh <Maqam> <seed> [cap|auto]}"
S="${2:?usage: run_one.sh <Maqam> <seed> [cap|auto]}"
CAP_ARG="${3:-auto}"
BIN="$ROOT/bin/audiocpp_cli"

# The prebuilt binary links CUDA 12 (libcublas.so.12/libcudart.so.12); on a host
# where those live only in the pip nvidia-*-cu12 wheels, put them on the loader
# path so the binary loads (no-op when already OK).
# shellcheck source=cuda_loader_path.sh
. "$SCRIPT_DIR/cuda_loader_path.sh"
MODEL="$ROOT/models/Yue2-3B-GGUF"
OUT="${OUT_DIR:-$ROOT/out}"
mkdir -p "$OUT"

style="${STYLE_FILE:-$ROOT/prompts/${M}_style.txt}"
lyrics="${LYRICS_FILE:-$ROOT/prompts/${M}_lyrics.txt}"
LORA_AR="${LORA_AR:-$ROOT/loras/arabmaqamrock-v3-ar.safetensors}"
LORA_NAR="${LORA_NAR:-$ROOT/loras/arabmaqamrock-v3-nar.safetensors}"
# Per-expert scales; 0 switches that expert's adapter off (base weights).
LORA_AR_SCALE="${LORA_AR_SCALE:-1.0}"
LORA_NAR_SCALE="${LORA_NAR_SCALE:-1.0}"
wav="$OUT/${M}_${S}.wav"
log="$OUT/${M}_${S}.log"
tfile="$OUT/${M}_${S}_time.txt"
csv="$OUT/${M}_${S}_gpu.csv"
status="$OUT/_runs_status.log"

# Extra request options, space-separated key=value pairs (e.g.
# EXTRA_REQUEST_OPTS="guidance_scale=1.5 semantic_temperature=0.8").
extra_request=()
for kv in ${EXTRA_REQUEST_OPTS:-}; do
  extra_request+=(--request-option "$kv")
done

# Symbolic (CoT) route. External ABC scores need melody/full; cot=off ignores the
# score, so refuse the combination instead of silently rendering a cot=off take.
COT="${COT:-off}"
ABC_FILE="${ABC_FILE:-}"
PLAN_DIR="${PLAN_DIR:-}"
case "$COT" in
  off|melody|full) ;;
  *) echo "error: COT must be off|melody|full (got '$COT')" >&2; exit 2 ;;
esac
if [ -n "$ABC_FILE" ]; then
  [ -f "$ABC_FILE" ] || { echo "error: ABC_FILE not found: $ABC_FILE" >&2; exit 2; }
  [ "$COT" != "off" ] || { echo "error: ABC_FILE needs COT=melody|full (got COT=off)" >&2; exit 2; }
  extra_request+=(--request-option "abc_file=$ABC_FILE")
fi
[ -n "$PLAN_DIR" ] && extra_request+=(--out-dir "$PLAN_DIR")

if [ "$CAP_ARG" = "auto" ]; then
  CAP=$(python3 "$SCRIPT_DIR/duration_cap.py" "$lyrics")
else
  CAP="$CAP_ARG"
fi

: > "$csv"
( while :; do nvidia-smi --query-gpu=utilization.gpu,memory.used,power.draw,temperature.gpu \
    --format=csv,noheader,nounits >> "$csv" 2>/dev/null; sleep 1; done ) &
SM=$!

line="=== START ${M} seed=${S} cap=${CAP} (${CAP_ARG}) cot=${COT} abc=${ABC_FILE:-none} ar_lora=${LORA_AR} nar_lora=${LORA_NAR} $(date -u +%FT%TZ) ==="
echo "$line"; echo "$line" >> "$status"

/usr/bin/time -v -o "$tfile" \
  "$BIN" --task gen --family yue2 --model "$MODEL" --backend cuda --threads 8 \
  --session-option yue2.model_gguf=yue2-3b-bf16.gguf \
  --session-option yue2.vae_gguf=yue2-vae-f16.gguf \
  --session-option yue2.ar_lora="$LORA_AR" \
  --session-option yue2.ar_lora_scale="$LORA_AR_SCALE" \
  --session-option yue2.nar_lora="$LORA_NAR" \
  --session-option yue2.nar_lora_scale="$LORA_NAR_SCALE" \
  --session-option yue2.attention=flash \
  --lyrics "$(cat "$lyrics")" \
  --request-option style="$(cat "$style")" \
  --request-option cot="$COT" \
  --request-option semantic_max_tokens="$CAP" \
  "${extra_request[@]}" \
  --seed "$S" \
  --out "$wav" \
  --log > "$log" 2>&1
rc=$?
kill $SM 2>/dev/null; wait $SM 2>/dev/null

line="=== END ${M} seed=${S} exit=${rc} cap=${CAP} $(date -u +%FT%TZ) ==="
echo "$line"; echo "$line" >> "$status"
exit "$rc"
