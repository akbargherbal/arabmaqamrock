#!/usr/bin/env bash
# Build the isolated SheetSage2 environment used by ./transcribe.sh.
#
#   ./plumbing/setup_transcribe.sh              # CPU wheels (default)
#   ./plumbing/setup_transcribe.sh --cuda       # CUDA 12.6 torch wheels
#   ./plumbing/setup_transcribe.sh --doctor     # build/reuse, then diagnostics
#   ./plumbing/setup_transcribe.sh --force      # recreate the venv
#
# Why a separate env: the repo's system Python is 3.13 / transformers 5.x, which
# is incompatible with SheetSage2's custom code. Upstream pins Python 3.10/3.11,
# torch 2.8.0 and transformers 4.45.2. The venv lives in the repo and is ignored
# by git. CPU is the default because transcription should not hold the GPU that
# generation needs; CUDA is opt-in. With CUDA wheels installed, `--device auto`
# (the default) uses the GPU, so pass `--device cpu` to keep it free.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="${TRANSCRIBE_VENV:-$REPO_ROOT/.venv-sheetsage2}"
PY="$VENV/bin/python"
TORCH_INDEX="https://download.pytorch.org/whl/cpu"
TORCH_SPEC="2.8.0+cpu"
DOCTOR=0
FORCE=0
WARM=0

usage() {
  awk 'NR>1 && /^set -euo/{exit} NR>1{print}' "$0"
}

while [ $# -gt 0 ]; do
  case "$1" in
    --cpu)       TORCH_INDEX="https://download.pytorch.org/whl/cpu"; TORCH_SPEC="2.8.0+cpu"; shift ;;
    --cuda)      TORCH_INDEX="https://download.pytorch.org/whl/cu126"; TORCH_SPEC="2.8.0+cu126"; shift ;;
    --doctor)    DOCTOR=1; shift ;;
    --force)     FORCE=1; shift ;;
    --warm)      WARM=1; shift ;;
    -h|--help)   usage; exit 0 ;;
    *) echo "unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

echo "== prerequisites =="
command -v uv >/dev/null 2>&1 || {
  echo "[fail] uv not found on PATH" >&2
  echo "  install it with: python3 -m pip install -U uv" >&2
  exit 1
}
command -v python3 >/dev/null 2>&1 || { echo "[fail] python3 not found" >&2; exit 1; }
if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "[fail] ffmpeg not found; SheetSage2 decodes audio through it" >&2
  echo "  Debian/Ubuntu: apt-get install -y ffmpeg" >&2
  exit 1
fi
echo "  uv:     $(uv --version)"
echo "  ffmpeg: $(ffmpeg -version 2>/dev/null | head -n1)"

echo "== venv =="
if [ -z "$VENV" ] || [ "$VENV" = "/" ] || [ "$VENV" = "$HOME" ] || [ "$VENV" = "$REPO_ROOT" ]; then
  echo "[fail] refusing unsafe TRANSCRIBE_VENV: $VENV" >&2
  exit 1
fi
if [ "$FORCE" = 1 ] && [ -d "$VENV" ]; then
  case "$VENV" in
    "$REPO_ROOT"/*) ;;
    *)
      echo "[fail] --force only removes a venv under $REPO_ROOT; remove $VENV manually" >&2
      exit 1
      ;;
  esac
  echo "  removing existing $VENV (--force)"
  rm -rf "$VENV"
fi
if [ ! -x "$PY" ]; then
  echo "  creating $VENV (Python 3.11)"
  uv venv "$VENV" --python 3.11
else
  echo "  reusing $VENV"
fi

echo "== torch =="
echo "  index: $TORCH_INDEX"
# `torch==2.8.0` is already satisfied by a `+cpu` local build, so uv would
# silently keep CPU wheels when switching to --cuda. Compare versions and
# force a reinstall when the flavor differs.
INSTALLED=$("$PY" -c "import torch; print(torch.__version__)" 2>/dev/null || true)
if [ "$INSTALLED" = "$TORCH_SPEC" ]; then
  echo "  already $TORCH_SPEC"
else
  echo "  installing $TORCH_SPEC (installed: ${INSTALLED:-none})"
  uv pip install --python "$PY" -q --reinstall \
    "torch==$TORCH_SPEC" "torchaudio==$TORCH_SPEC" --index-url "$TORCH_INDEX"
fi

echo "== SheetSage2 dependencies =="
uv pip install --python "$PY" -q \
  transformers==4.45.2 huggingface-hub==0.36.0 safetensors==0.5.3 \
  numpy==1.24.3 scipy==1.13.1 mir_eval==0.8.2 pretty_midi==0.2.10 \
  mido==1.3.3 setuptools==78.1.1

"$PY" - <<'PYCHECK'
import torch, transformers
print(f"  [ok] torch {torch.__version__} | transformers {transformers.__version__}")
PYCHECK

if [ "$WARM" = 1 ]; then
  echo "== warming SheetSage2 model cache =="
  "$PY" - <<'PYWARM'
from huggingface_hub import snapshot_download
for repo in ("m-a-p/SheetSage2", "m-a-p/MERT-v2-FullSong"):
    path = snapshot_download(repo)
    print(f"  [ok] {repo} -> {path}")
PYWARM
fi

if [ "$DOCTOR" = 1 ]; then
  echo "== doctor =="
  exec "$PY" "$REPO_ROOT/transcribe.py" --doctor
fi

echo
echo "[done] $VENV ready"
echo "  ./transcribe.sh out/latest --dry-run"
echo "  ./transcribe.sh out/latest --smoke"
echo "  ./transcribe.sh out/latest"
