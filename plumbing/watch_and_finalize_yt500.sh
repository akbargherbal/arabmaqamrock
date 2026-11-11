#!/usr/bin/env bash
# Wait for the transcription cohort, then run the finalizer once.
#
# Stops waiting when either (a) >= TARGET verified outputs exist, or (b) both
# the transcription supervisor and transcribe.py have exited.  In case (b) the
# analysis still runs, with failures reported, because the mission is to
# report the cohort even when it falls short of 95%.
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

TARGET="${TARGET:-437}"
OUT="${TRANSCRIPTS_DIR:-/content/yt500/transcripts}"

count_ok() {
  python3 - "$OUT" <<'PY'
import json, sys
from pathlib import Path
n = 0
for d in Path(sys.argv[1]).iterdir():
    if not d.is_dir():
        continue
    try:
        m = json.loads((d / "meta.json").read_text())
    except Exception:
        continue
    n += bool(m.get("status") == "ok" and (d / "score.abc").is_file())
print(n)
PY
}

while true; do
  n=$(count_ok)
  echo "$(date -u +%FT%TZ) watcher: verified=$n target=$TARGET"
  if [ "$n" -ge "$TARGET" ]; then
    break
  fi
  if ! pgrep -f "supervise_yt500_transcription.sh" >/dev/null 2>&1 \
     && ! pgrep -f "transcribe.py ${OUT%/transcripts}/audio" >/dev/null 2>&1; then
    echo "$(date -u +%FT%TZ) watcher: transcription jobs stopped at $n"
    break
  fi
  sleep 120
done

echo "$(date -u +%FT%TZ) watcher: finalizing"
TARGET=0 exec plumbing/finalize_yt500_similarity.sh
