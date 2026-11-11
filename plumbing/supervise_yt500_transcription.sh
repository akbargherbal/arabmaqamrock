#!/usr/bin/env bash
# Keep the YT500 transcription moving across --time-budget sessions.
#
# Usage:
#   setsid nohup bash -c 'exec plumbing/supervise_yt500_transcription.sh' \
#     < /dev/null > logs/yt500_abc/supervisor.log 2>&1 &
#
# It never uses --limit.  Each session relies on transcribe.py's source-hash
# skip, so a restart costs one model load plus a fast scan of finished tracks.
# It stops at TARGET verified outputs (default 437 = 95% of 460) or when a
# whole session makes no progress (failure loop guard).
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

AUDIO="${AUDIO_DIR:-/content/yt500/audio}"
OUT="${TRANSCRIPTS_DIR:-/content/yt500/transcripts}"
LOG="${TRANSCRIBE_LOG:-logs/yt500_abc/transcribe.log}"
TARGET="${TARGET:-437}"
BUDGET="${TIME_BUDGET:-7200}"

count_ok() {
  python3 - "$OUT" <<'PY'
import json, sys
from pathlib import Path
root = Path(sys.argv[1])
n = 0
if root.is_dir():
    for d in root.iterdir():
        if not d.is_dir():
            continue
        try:
            m = json.loads((d / "meta.json").read_text())
        except Exception:
            continue
        if m.get("status") == "ok" and (d / "score.abc").is_file():
            n += 1
print(n)
PY
}

mkdir -p "$(dirname "$LOG")" "$OUT"
while true; do
  n=$(count_ok)
  echo "$(date -u +%FT%TZ) supervisor: verified=$n target=$TARGET"
  if [ "$n" -ge "$TARGET" ]; then
    echo "$(date -u +%FT%TZ) supervisor: target reached"
    break
  fi
  if pgrep -f "transcribe.py ${AUDIO}" >/dev/null 2>&1; then
    sleep 60
    continue
  fi

  before=$n
  echo "$(date -u +%FT%TZ) supervisor: starting session (before=$before)"
  ./transcribe.sh "$AUDIO" --out-dir "$OUT" --full --device auto --threads 4 \
    --time-budget "$BUDGET" >> "$LOG" 2>&1 &
  child=$!
  echo "$child" > logs/yt500_abc/transcribe.pid
  wait "$child"
  rc=$?
  after=$(count_ok)
  echo "$(date -u +%FT%TZ) supervisor: session exit=$rc before=$before after=$after"
  if [ "$after" -le "$before" ]; then
    echo "$(date -u +%FT%TZ) supervisor: no progress; stopping so failures can be inspected"
    break
  fi
  sleep 10
done
