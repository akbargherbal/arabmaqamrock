#!/usr/bin/env bash
#
# Fresh Colab VM -> ready to generate, in one command.
#
#   ./setup_colab.sh
#   ./setup_colab.sh --with-transcribe   # also build the optional CPU transcription env
#
# Does, in order:
#   1. sanity-check tooling (nvidia-smi, gcloud/gsutil auth, hf, python3) and
#      install GNU time if absent (run_one.sh wraps the binary in /usr/bin/time)
#   2. stage the prebuilt audiocpp_cli for this GPU's arch (./plumbing/fetch_binary.sh)
#   3. download the YuE2 GGUF model + LoRA from Hugging Face
#   4. start the GCS backup sidecar (detached)
#
# Idempotent: re-running skips what is already present. Nothing here needs a build
# unless the prebuilt is missing (then fetch_binary.sh falls back to a source build).
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
. plumbing/env.sh

WITH_TRANSCRIBE=0
while [ $# -gt 0 ]; do
  case "$1" in
    --with-transcribe) WITH_TRANSCRIBE=1; shift ;;
    -h|--help)         awk 'NR>1 && /^set -euo/{exit} NR>1{print}' "$0"; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

MODELS="$REPO_ROOT/models/Yue2-3B-GGUF"
LORAS="$REPO_ROOT/loras"
LOG_DIR="$REPO_ROOT/logs"
mkdir -p "$MODELS" "$LORAS" "$LOG_DIR"

HF_GGUF_REPO="audio-cpp/Yue2-3B-GGUF"
HF_LORA_REPO="akbargherbal/arabmaqamrock-yue2-lora"
LORA_AR="arabmaqamrock-v3-ar.safetensors"
LORA_NAR="arabmaqamrock-v3-nar.safetensors"

ok()   { printf '  [ok]   %s\n' "$*"; }
warn() { printf '  [warn] %s\n' "$*"; }
die()  { printf '  [FAIL] %s\n' "$*" >&2; exit 1; }

echo "== 1. tooling =="
command -v nvidia-smi >/dev/null 2>&1 && ok "nvidia-smi: $(nvidia-smi --query-gpu=name --format=csv,noheader | head -n1)" || die "no nvidia-smi (no GPU?)"
[ -n "$GCS_CLI" ] && ok "gcs cli: $GCS_CLI" || die "need gcloud or gsutil on PATH (and gcloud auth login)"
command -v hf >/dev/null 2>&1 && ok "hf cli present" || die "hf missing: pip install -U 'huggingface_hub[cli]'"
[ -n "${HF_TOKEN:-}" ] && ok "HF_TOKEN set" || warn "HF_TOKEN not set in this shell (public repos only)"
command -v gsutil >/dev/null 2>&1 && ok "gsutil present (backup daemon)" || warn "gsutil missing — backup daemon will not run"

# run_one.sh wraps the binary in /usr/bin/time -v -o for its wall/RSS metrics; the
# bash builtin cannot do that. Colab images don't always ship the time package, and
# when it is missing every track fails as an instant exit=127 before any model loads.
if [ -x /usr/bin/time ]; then
  ok "GNU time present"
else
  warn "GNU time missing — installing (run_one.sh needs it)"
  if [ "$(id -u)" -eq 0 ]; then APT=(apt-get); else APT=(sudo apt-get); fi
  "${APT[@]}" update -qq || true
  "${APT[@]}" install -y -qq time >/dev/null 2>&1 || true
  # Verify the file, not apt's exit code: `apt-get install time` returns 0 even
  # when the package is registered but /usr/bin/time is actually absent.
  [ -x /usr/bin/time ] && ok "GNU time installed" \
    || die "could not install GNU time (apt-get install time)"
fi

echo "== 2. binary =="
./plumbing/fetch_binary.sh

echo "== 3. model + LoRA =="
hf download "$HF_GGUF_REPO" yue2-3b-bf16.gguf yue2-vae-f16.gguf --local-dir "$MODELS" >/dev/null && ok "ggufs"
hf download "$HF_GGUF_REPO" --include "sidecars/*" --local-dir "$MODELS" >/dev/null && ok "sidecars"
hf download "$HF_LORA_REPO" "$LORA_AR" "$LORA_NAR" --local-dir "$LORAS" >/dev/null && ok "LoRA"

echo "== 4. backup sidecar =="
if pgrep -f 'plumbing/backup_to_gcp.py' >/dev/null; then
  warn "backup daemon already running"
else
  setsid nohup python3 plumbing/backup_to_gcp.py \
    > "$LOG_DIR/gcp_backup_stdout.log" 2>&1 & disown
  sleep 2
  pgrep -f 'plumbing/backup_to_gcp.py' >/dev/null && ok "backup daemon started (logs/gcp_backup.log)" || warn "backup daemon did not start"
fi

if [ "$WITH_TRANSCRIBE" = 1 ]; then
  echo "== 5. optional transcription env =="
  "$REPO_ROOT/plumbing/setup_transcribe.sh"
fi

echo
echo "Ready. Validate then generate:"
echo "  python3 generate.py songs.example.json --dry-run"
echo "  python3 generate.py songs.example.json"
if [ "$WITH_TRANSCRIBE" = 1 ]; then
  echo "  ./transcribe.sh out/latest --dry-run"
else
  echo "Optional symbolic transcription: ./plumbing/setup_transcribe.sh"
fi
echo "Backup verify:  ${GCS_CLI} ls ${GCP_PREFIX}/runs/"
