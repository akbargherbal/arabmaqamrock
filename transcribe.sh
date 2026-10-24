#!/usr/bin/env bash
# Run the SheetSage2 transcriber inside the isolated Python 3.11 env.
#
#   ./transcribe.sh out/latest --dry-run
#   ./transcribe.sh out/latest --smoke
#
# The venv is built by ./plumbing/setup_transcribe.sh. `python3 transcribe.py`
# also works for --dry-run/--verify/--doctor without the venv; only the model
# path needs Python 3.11 + transformers 4.45.2.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

VENV="${TRANSCRIBE_VENV:-$PWD/.venv-sheetsage2}"
PY="$VENV/bin/python"

if [ ! -x "$PY" ]; then
  echo "transcribe.sh: SheetSage2 env not found at $VENV" >&2
  echo "  run ./plumbing/setup_transcribe.sh first" >&2
  echo "  (or use: python3 transcribe.py --dry-run / --verify / --doctor)" >&2
  exit 2
fi

exec "$PY" "$PWD/transcribe.py" "$@"
