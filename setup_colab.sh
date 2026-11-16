#!/usr/bin/env bash
#
# Fresh Colab VM -> ready to generate, in one command.
#
#   ./setup_colab.sh
#   ./setup_colab.sh --verify            # re-hash cached LoRAs too (default: only fresh)
#   ./setup_colab.sh --with-transcribe   # also build the optional CPU transcription env
#
# Does, in order:
#   1. sanity-check tooling (nvidia-smi, gcloud/gsutil auth, hf, python3) and
#      install GNU time if absent (run_one.sh wraps the binary in /usr/bin/time)
#   2. stage the prebuilt audiocpp_cli for this GPU's arch (./plumbing/fetch_binary.sh)
#   3. download the YuE2 GGUF model + the default ArabMaqamRock LoRA sets from
#      Hugging Face: the blend a0.15 pair (v3 x instrumental, alpha baked in)
#      and the own Arabic-instrumental pair. The scales, guidance and cot
#      settings are in docs/generation-defaults.md. The other own sets (v3
#      style pair, blend a0.1/a0.2) and the two third-party adapters
#      (round-04/06) are staged as commented-out downloads: uncomment when a
#      manifest needs them.
#   4. start the GCS backup sidecar (detached; MP3 trials + transcript archives)
#
# Idempotent: re-running skips what is already present. Nothing here needs a build
# unless the prebuilt is missing (then fetch_binary.sh falls back to a source build).
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
. plumbing/env.sh

WITH_TRANSCRIBE=0
FORCE_VERIFY=0       # 0 = sha256 only for files fetched in this run (fast restart)
while [ $# -gt 0 ]; do
  case "$1" in
    --with-transcribe) WITH_TRANSCRIBE=1; shift ;;
    --verify)          FORCE_VERIFY=1; shift ;;
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
# v3 style/voice pair — OPT-IN, not staged by default (the blend a0.15 pair
# already carries its character). The download block is commented in section 3.
LORA_AR="arabmaqamrock-v3-ar.safetensors"
LORA_NAR="arabmaqamrock-v3-nar.safetensors"
LORA_SHA256_AR="3531bb9106d2292eefe58eabe11ec08bb7dddc69554f2b016dc9f13f711fab18"
LORA_SHA256_NAR="a7eabcadb22146048bcb5e65d04828ee9454559523ca161bd38c06060deb0cae"
# Own Arabic-instrumental pair (no vocals; also the donor behind the blends).
# DEFAULT: staged by section 3.
# NB: the round-04 third-party adapter below is a DIFFERENT adapter, used by the
# fadhl_shaker_instrumental manifests — it is opt-in and commented out.
HF_INSTR_OWN_REPO="akbargherbal/arabic-instrumental-yue2-lora"
INSTR_OWN_AR="arabic-instrumental-ar.safetensors"
INSTR_OWN_NAR="arabic-instrumental-nar.safetensors"
INSTR_OWN_SHA256_AR="69517eea8bbc9fec2ace47c271f1bde7058881e89eabe9f9c0b10cb91ae97edb"
INSTR_OWN_SHA256_NAR="f84fdd4e9332c8be27e2d716fec9048f3d8ea3835c5e7582d6689322b6e0ea2f"
# Blends: rank-concat merges of the v3 pair with the instrumental pair; the
# alpha is baked into the files. DEFAULT: a0.15 only (the middle setting).
# a0.1 (conservative floor) and a0.2 (16.5% donor share) are OPT-IN below.
HF_BLEND_REPO="akbargherbal/arabmaqamrock-blend-yue2-lora"
BLEND_A1_AR="a0.1/v3instr_a0.1_ar.safetensors"
BLEND_A1_NAR="a0.1/v3instr_a0.1_nar.safetensors"
BLEND_A1_SHA256_AR="d48109b3117bf7851390ac9d4de86a45c5edd99cc5d17ddb97481e5c77ef64a0"
BLEND_A1_SHA256_NAR="88f00bcb1b60cb7638eff07d7f1a7ff1d19705e987a138bf82e0c36e84ea5b58"
BLEND_A15_AR="a0.15/v3instr_a0.15_ar.safetensors"
BLEND_A15_NAR="a0.15/v3instr_a0.15_nar.safetensors"
BLEND_A15_SHA256_AR="fef2104e13560700e118af92b7be139f7711df59e2a68ddde4691a0e5a5fecc3"
BLEND_A15_SHA256_NAR="e1696863534e330b290ad92fbe16d904b69b8e5eebf208b9ba738778447a1fb7"
BLEND_A2_AR="a0.2/v3instr_a0.2_ar.safetensors"
BLEND_A2_NAR="a0.2/v3instr_a0.2_nar.safetensors"
BLEND_A2_SHA256_AR="820f1ce90ab64965606a5a57451b2dcf255072ab4b9c7be182bc14b80bd86dd6"
BLEND_A2_SHA256_NAR="f9738e214361c02428f6baa01327ba42ce1208236d33868fd6c3d3a7b584225f"
# Third-party AR-only adapter for instrumental covers (round 04). It is loaded
# instead of the arabmaqamrock AR adapter; the NAR adapter stays off (scale 0).
HF_INST_LORA_REPO="Mothersuperior/YuE2-instrumental-cot-full-loras"
HF_INST_LORA="ar_lora_inst_v3abc.bf16.safetensors"
HF_INST_LORA_SHA256="e408fd3148b75b1165f7ddbf63db575d83bb6402a0b5f876fcb767dbcb2c5414"
# NAR decoder LoRA for round 06 (real-production timbre). It is optional:
# the instrumental AR adapter works with the stock NAR, but this is the
# author's recommended pairing for production-quality output.
HF_NAR_LORA_REPO="Mothersuperior/yue2-mothersuperior-realaudio-tokenizer-v4"
HF_NAR_LORA="nar_lora_joint_v9.bf16.safetensors"
HF_NAR_LORA_SHA256="ce57f98e9e0e65c724c2a00aa23dea2568952590504a428c588d82f00bc61c55"

ok()   { printf '  [ok]   %s\n' "$*"; }
warn() { printf '  [warn] %s\n' "$*"; }
die()  { printf '  [FAIL] %s\n' "$*" >&2; exit 1; }

echo "== 1. tooling =="
command -v nvidia-smi >/dev/null 2>&1 && ok "nvidia-smi: $(nvidia-smi --query-gpu=name --format=csv,noheader | head -n1)" || die "no nvidia-smi (no GPU?)"
[ -n "$GCS_CLI" ] && ok "gcs cli: $GCS_CLI" || die "need gcloud or gsutil on PATH (and gcloud auth login)"
command -v hf >/dev/null 2>&1 && ok "hf cli present" || die "hf missing: pip install -U 'huggingface_hub[cli]'"
command -v ffmpeg >/dev/null 2>&1 && ok "ffmpeg present (MP3 trial upload)" || warn "ffmpeg missing — backup will upload WAVs instead of MP3"
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

echo "== 3. model + LoRA (default: blend a0.15 + own instrumental) =="
hf download "$HF_GGUF_REPO" yue2-3b-bf16.gguf yue2-vae-f16.gguf --local-dir "$MODELS" >/dev/null && ok "ggufs"
hf download "$HF_GGUF_REPO" --include "sidecars/*" --local-dir "$MODELS" >/dev/null && ok "sidecars"
mkdir -p "$LORAS/arabic-instrumental"
hf download "$HF_INSTR_OWN_REPO" "$INSTR_OWN_AR" "$INSTR_OWN_NAR" --local-dir "$LORAS/arabic-instrumental" >/dev/null && ok "own instrumental LoRA"
mkdir -p "$LORAS/blend/a0.15"
hf download "$HF_BLEND_REPO" "$BLEND_A15_AR" "$BLEND_A15_NAR" --local-dir "$LORAS/blend" >/dev/null && ok "blend a0.15"

# --- optional LoRAs: NOT downloaded by default -------------------------------
# The blend a0.15 pair already carries the v3 style/voice character, so the
# standalone v3 pair, the a0.1/a0.2 blend arms and the two third-party adapters
# are staged only on demand. Uncomment a block (download + its sha256 line) when
# a manifest needs it.
#
# hf download "$HF_LORA_REPO" "$LORA_AR" "$LORA_NAR" --local-dir "$LORAS" >/dev/null && ok "v3 LoRA"
# mkdir -p "$LORAS/blend/a0.1" "$LORAS/blend/a0.2"
# hf download "$HF_BLEND_REPO" "$BLEND_A1_AR" "$BLEND_A1_NAR" --local-dir "$LORAS/blend" >/dev/null && ok "blend a0.1"
# hf download "$HF_BLEND_REPO" "$BLEND_A2_AR" "$BLEND_A2_NAR" --local-dir "$LORAS/blend" >/dev/null && ok "blend a0.2"
#
# Round-04 third-party AR-only instrumental adapter (fadhl_shaker_instrumental
# manifests; loaded instead of the arabmaqamrock AR adapter, NAR stays at 0):
# mkdir -p "$LORAS/instrumental"
# hf download "$HF_INST_LORA_REPO" "$HF_INST_LORA" --local-dir "$LORAS/instrumental" >/dev/null && ok "instrumental LoRA"
#
# Round-06 NAR decoder LoRA (the third-party adapter's recommended pairing):
# mkdir -p "$LORAS/nar"
# hf download "$HF_NAR_LORA_REPO" "$HF_NAR_LORA" --local-dir "$LORAS/nar" >/dev/null && ok "NAR v9 LoRA"

# sha256 pins for the default adapters (warn-only: a corrected upstream
# re-upload should not brick the setup). Cached files are skipped unless
# --verify is passed, so a re-run stays fast.
sha_warn() {  # file, expected, label
  [ -f "$1" ] || return 0
  if [ "$FORCE_VERIFY" = 0 ] \
     && [ $(( $(date +%s) - $(stat -c %Y "$1") )) -gt 300 ]; then
    echo "  [skip] sha256: $3 (cached — use --verify to re-hash)"
    return 0
  fi
  if echo "$2  $1" | sha256sum -c - >/dev/null 2>&1; then
    ok "sha256: $3"
  else
    warn "sha256 mismatch: $3 ($1)"
  fi
}
sha_warn "$LORAS/arabic-instrumental/$INSTR_OWN_AR" "$INSTR_OWN_SHA256_AR" "own instrumental AR"
sha_warn "$LORAS/arabic-instrumental/$INSTR_OWN_NAR" "$INSTR_OWN_SHA256_NAR" "own instrumental NAR"
sha_warn "$LORAS/blend/$BLEND_A15_AR" "$BLEND_A15_SHA256_AR" "blend a0.15 AR"
sha_warn "$LORAS/blend/$BLEND_A15_NAR" "$BLEND_A15_SHA256_NAR" "blend a0.15 NAR"
# Opt-in pins (enable together with the matching download block above):
# sha_warn "$LORAS/$LORA_AR" "$LORA_SHA256_AR" "v3 AR"
# sha_warn "$LORAS/$LORA_NAR" "$LORA_SHA256_NAR" "v3 NAR"
# sha_warn "$LORAS/blend/$BLEND_A1_AR" "$BLEND_A1_SHA256_AR" "blend a0.1 AR"
# sha_warn "$LORAS/blend/$BLEND_A1_NAR" "$BLEND_A1_SHA256_NAR" "blend a0.1 NAR"
# sha_warn "$LORAS/blend/$BLEND_A2_AR" "$BLEND_A2_SHA256_AR" "blend a0.2 AR"
# sha_warn "$LORAS/blend/$BLEND_A2_NAR" "$BLEND_A2_SHA256_NAR" "blend a0.2 NAR"
# if [ -f "$LORAS/instrumental/$HF_INST_LORA" ]; then
#   echo "$HF_INST_LORA_SHA256  $LORAS/instrumental/$HF_INST_LORA" | sha256sum -c - >/dev/null \
#     && ok "instrumental LoRA sha256" \
#     || warn "instrumental LoRA sha256 mismatch (round 04 may fail)"
# fi
# if [ -f "$LORAS/nar/$HF_NAR_LORA" ]; then
#   echo "$HF_NAR_LORA_SHA256  $LORAS/nar/$HF_NAR_LORA" | sha256sum -c - >/dev/null \
#     && ok "NAR v9 LoRA sha256" \
#     || warn "NAR v9 LoRA sha256 mismatch (round 06 may fail)"
# fi

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
echo "Ready. Validate then generate (the built-in adapter pair is blend a0.15):"
echo "  python3 generate.py manifests/songs.example.json --dry-run"
echo "  (drop --dry-run to render; loras/arabic-instrumental/ holds the"
echo "   instrumental-only pair; the v3 pair is opt-in — see the commented blocks above)"
if [ "$WITH_TRANSCRIBE" = 1 ]; then
  echo "  ./transcribe.sh out/latest --dry-run"
else
  echo "Optional symbolic transcription: ./plumbing/setup_transcribe.sh"
fi
echo "Backup verify:  ${GCS_CLI} ls ${GCP_PREFIX}/runs/"
echo "Upload plan (no writes): python3 plumbing/backup_to_gcp.py --once --dry-run"
echo "Keep a take as WAV:      python3 plumbing/mark_production.py out/<run> --take <name>_<seed>"
