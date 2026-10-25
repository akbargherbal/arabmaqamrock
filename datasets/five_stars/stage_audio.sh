#!/usr/bin/env bash
# Stage the Five Stars audio into the packaged layout and build per-maqam tars.
#
#   ./datasets/five_stars/stage_audio.sh [--out DIR] [--src DIR]
#
# Layout produced under --out (default /tmp/opencode/five_stars_v1):
#
#   audio/<maqam>/<track_id>.mp3     real copies, not symlinks
#   audio/<maqam>.tar                deterministic: sorted, uid/gid 0, mtime 0
#   audio/SHA256SUMS                 sha256 of each tar
#   corpus/{manifest,lyrics,audit}.json(l)
#   README.md
#
# The tar member paths are `audio/<maqam>/...` so an extract inside the dataset
# root reproduces the layout that manifest.jsonl's `audio_path` expects.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SRC="$REPO_ROOT/../Five_Stars_ArabMaqamRock"
OUT="/tmp/opencode/five_stars_v1"
HERE="$REPO_ROOT/datasets/five_stars"

while [ $# -gt 0 ]; do
  case "$1" in
    --out) OUT="$2"; shift 2 ;;
    --src) SRC="$2"; shift 2 ;;
    -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

command -v gcloud >/dev/null || echo "warn: gcloud not on PATH (upload step will need it)"

echo "== staging tree =="
rm -rf "$OUT"
mkdir -p "$OUT/audio" "$OUT/corpus"

python3 - "$HERE/manifest.jsonl" "$SRC" "$OUT" <<'PY'
import json, shutil, sys
from pathlib import Path

manifest, src, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
n = 0
for line in manifest.read_text(encoding="utf-8").splitlines():
    row = json.loads(line)
    dest = out / row["audio_path"]
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src / "FIVE_STARS_DATASET" / row["maqam"] / f"{row['track_id']}.mp3", dest)
    n += 1
print(f"  copied {n} files")
PY

echo "== tars =="
for m in Ajam Hijaz Kurd Nahawand; do
  tar --sort=name --owner=0 --group=0 --numeric-owner --mtime='@0' \
      -cf "$OUT/audio/$m.tar" -C "$OUT" "audio/$m"
  printf '  %-9s %s\n' "$m" "$(du -h "$OUT/audio/$m.tar" | cut -f1)"
done

echo "== checksums =="
( cd "$OUT/audio" && sha256sum ./*.tar > SHA256SUMS )
cat "$OUT/audio/SHA256SUMS"

echo "== corpus =="
cp "$HERE/manifest.jsonl" "$HERE/lyrics.jsonl" "$HERE/audit.json" "$OUT/corpus/"
cp "$HERE/README.md" "$OUT/README.md"
cp "$REPO_ROOT/docs/plans/five-stars-abc-corpus.md" "$OUT/PLAN.md"

echo "== total =="
du -sh "$OUT"
echo "[done] $OUT"
