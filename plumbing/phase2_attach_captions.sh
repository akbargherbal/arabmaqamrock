#!/usr/bin/env bash
# Phase 2 driver — attach the finished caption album to the YT500 dataset and
# publish it as v0.2.  CPU only, idempotent, resumable.
#
# This file is the canonical copy (tracked in git).  The run command uses the
# copy under logs/ (see docs/YT500_CAPTION_COMPLETION_PLAN.md, phase 2):
#
#   cd /content/arabmaqamrock && mkdir -p logs
#   setsid nohup bash logs/phase2.sh         > logs/phase2.out 2>&1 < /dev/null & disown
#   setsid nohup bash logs/backup_loop.sh    > logs/backup_loop.out 2>&1 < /dev/null & disown
#
# Resume after a VM restart: read gs://…/work/backup/status_phase2.json for the
# last completed step, then run it again.  Every step is idempotent; never
# --build, never re-caption.
set -uo pipefail
export PATH="$HOME/google-cloud-sdk/bin:/tools/google-cloud-sdk/bin:$PATH"
REPO=/content/arabmaqamrock
MC=/content/music_captioning
DS=gs://akbar-december-2024-backup/DATASET/yt500_instrumental
BK=gs://akbar-december-2024-backup/GENERATION/YT500_INSTRUMENTAL/work/backup
ALBUM_URI=gs://akbar-december-2024-backup/GENERATION/YT500_INSTRUMENTAL/work/caption_album.json
ALBUM_SHA=07aa645392a0996871efcc182769a96cbd9aed1fd5be213370417260123e29d9
L=$REPO/work/yt500_gen/attach_v02
LOG=$REPO/logs/phase2.log
STATUS=$REPO/logs/phase2.status.json
cd "$REPO" || exit 90
say(){ echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*" | tee -a "$LOG"; }
mark(){ printf '{"step":"%s","rc":%s,"utc":"%s"}\n' "$1" "$2" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$STATUS"; gcloud storage cp -q "$STATUS" "$BK/status_phase2.json" >>"$LOG" 2>&1; }
stop(){ say "FAILED step=$1 rc=$2"; mark "$1" "$2"; exit "$2"; }
retry(){ local n=3; while [ $n -gt 0 ]; do "$@" >>"$LOG" 2>&1 && return 0; n=$((n-1)); say "retrying ($n left): $*"; sleep 20; done; return 1; }
step(){ local n=$1; shift; say "== $n"; local t0=$SECONDS; retry "$@" || stop "$n" 1; say "-- $n ok in $((SECONDS-t0))s"; mark "$n" 0; }

mkdir -p "$L" logs
exec 9>"$REPO/logs/.phase2.lock"; flock -n 9 || { echo "already running"; exit 0; }

step pull_tree gcloud storage rsync -r -x '.*audio\.mp3$' "$DS" "$L"
say "local tree: $(find "$L" -type f | wc -l) files, $(du -sh "$L" | cut -f1)"
[ -z "$(find "$L/tracks" -name audio.mp3 -print -quit)" ] || stop audio_leaked 20
gcloud storage ls "$BK/dataset_v0.1_meta.tar.gz" >/dev/null 2>&1 || {
  tar -C "$L" -czf /tmp/v01.tgz . && step backup_v01 gcloud storage cp -q /tmp/v01.tgz "$BK/dataset_v0.1_meta.tar.gz"; }

step fetch_album gcloud storage cp -q "$ALBUM_URI" "$REPO/work/caption_album.v02.json"
[ "$(sha256sum "$REPO/work/caption_album.v02.json" | cut -d' ' -f1)" = "$ALBUM_SHA" ] || stop album_sha 21
gcloud storage ls "$DS/tracks/**/audio.mp3" > /tmp/audio_before.txt 2>/dev/null; mark audio_before 0

step attach python3 plumbing/compile_yt500_collection.py --attach-captions --local "$L" \
  --captions "$REPO/work/caption_album.v02.json" --allow-unpolished --min-caption-chars 150
tar -C "$L" -czf /tmp/v02.tgz . && step backup_v02 gcloud storage cp -q /tmp/v02.tgz "$BK/dataset_v0.2_meta.tar.gz"
step verify python3 plumbing/compile_yt500_collection.py --verify --local "$L" --allow-unpolished

say "dry run: $(gcloud storage rsync -r --dry-run "$L" "$DS" 2>&1 >/dev/null | grep -c 'Would copy') objects to publish"
step publish python3 plumbing/compile_yt500_collection.py --publish --local "$L" --no-audio

for suf in caption.json caption.txt; do
  n=$(gcloud storage ls "$DS/tracks/**/$suf" 2>/dev/null | wc -l); say "remote $suf=$n"
  [ "$n" -eq 460 ] || stop "remote_$suf" 31
done
n=$(gcloud storage rsync -r --dry-run "$L" "$DS" 2>&1 >/dev/null | grep -c 'Would copy'); say "still to copy=$n"
[ "$n" -eq 0 ] || stop resync_mismatch 33
gcloud storage ls "$DS/tracks/**/audio.mp3" > /tmp/audio_after.txt 2>/dev/null
diff -q /tmp/audio_before.txt /tmp/audio_after.txt >/dev/null || stop audio_changed 34
mark audio_unchanged 0

# bank the album in git (this is why the driver, not the chat, does it)
say "== bank_album"
mkdir -p "$MC/work/yt500/captions/arabmaqamrock"
cp "$REPO/work/caption_album.v02.json" "$MC/work/yt500/captions/arabmaqamrock/YT500_INSTRUMENTAL.json"
cp "$REPO/work/caption_album.v02.json" "$MC/work/yt500/caption_album.json"
gcloud storage cp -q "$BK/../captions.jsonl" "$MC/work/yt500/captions.jsonl" >>"$LOG" 2>&1
( cd "$MC" && git add work/yt500 \
  && { git diff --cached --quiet || git commit -q -m "yt500: captions snapshot (467 tracks, polished) $(date -u +%Y-%m-%dT%H:%M:%SZ)"; } \
  && git push -q origin main ) >>"$LOG" 2>&1 || stop bank_album 40
mark bank_album 0

python3 - <<'PY' > /tmp/summary.json
import json
m = json.load(open("/content/arabmaqamrock/work/yt500_gen/attach_v02/manifest.json"))
c = [json.loads(l) for l in open("/content/arabmaqamrock/work/yt500_gen/attach_v02/captions.jsonl")]
print(json.dumps({"dataset_version": m["dataset_version"], "counts": m["counts"],
                  "captions": m.get("captions"), "caption_rows": len(c),
                  "utc": __import__("datetime").datetime.utcnow().isoformat() + "Z"}, indent=2))
PY
step summary gcloud storage cp -q /tmp/summary.json "$BK/phase2_summary.json"
touch logs/DONE
say "DONE rc=0"
