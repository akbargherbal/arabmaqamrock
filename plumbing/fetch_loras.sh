#!/usr/bin/env bash
#
# Stage the YuE2 LoRA adapters declared in plumbing/loras.manifest.
#
# The manifest is the single source of truth: repo, target directory, file name
# and sha256 live there, and the `enabled` column decides what install.sh /
# setup_colab.sh stage. Adding or retiring a set is a one-line edit — no script
# surgery.
#
# Usage:
#   ./plumbing/fetch_loras.sh                     # stage the enabled (on) rows
#   ./plumbing/fetch_loras.sh --all               # also stage the opt-in (off) rows
#   ./plumbing/fetch_loras.sh --only v3,blend-a0.1   # just these sets (on or off)
#   ./plumbing/fetch_loras.sh --check             # verify what is on disk, no network
#   ./plumbing/fetch_loras.sh --list              # print the table with local paths
#   ./plumbing/fetch_loras.sh --verify            # re-hash cached files too (slow)
#   ./plumbing/fetch_loras.sh --dry-run           # print the plan, do nothing
#
# Rows marked `off` stay one flag away; rows commented with `#` are retired and
# are never staged, not even by --all.
set -euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/env.sh"

MANIFEST="$PLUMBING_DIR/loras.manifest"
DRY=0; CHECK=0; LIST=0; ALL=0; VERIFY=0; ONLY=""
while [ $# -gt 0 ]; do
  case "$1" in
    --all)     ALL=1; shift ;;
    --only)    ONLY="${2:?--only needs a comma-separated set list}"; shift 2 ;;
    --check)   CHECK=1; shift ;;
    --list)    LIST=1; shift ;;
    --verify)  VERIFY=1; shift ;;
    --dry-run) DRY=1; shift ;;
    -h|--help) sed -n '3,21p' "$0"; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

log() { printf '[fetch_loras] %s\n' "$*"; }
# $RUN: execute, or print when --dry-run.
RUN() { if [ "$DRY" = 1 ]; then echo "  dry-run: $*"; else "$@"; fi; }

[ -f "$MANIFEST" ] || { log "missing manifest: $MANIFEST"; exit 1; }

[ "$LIST" = 1 ] && {
  awk -F'\t' '
    /^[[:space:]]*$/ || /^[[:space:]]*#/ { next }
    NF < 6 { next }
    {
      for (i = 1; i <= NF; i++) gsub(/^[[:space:]]+|[[:space:]]+$/, "", $i)
      if ($1 != "on" && $1 != "off") next
      printf "%-6s %-24s %s/%s\n", $1, $2, $4, $5
    }
  ' "$MANIFEST"
  exit 0
}

# --- HF CLI ------------------------------------------------------------------
if command -v hf >/dev/null 2>&1; then HF=hf
elif command -v huggingface-cli >/dev/null 2>&1; then HF=huggingface-cli
else echo "MISSING: the 'hf' CLI — pip install -U 'huggingface_hub[cli]'" >&2; exit 1; fi

# --- selection ---------------------------------------------------------------
# on rows always; off rows only with --all or an explicit --only.
selected() {
  awk -F'\t' -v all="$ALL" -v only="$ONLY" '
    BEGIN { n = split(only, want, ","); for (i = 1; i <= n; i++) keep[want[i]] = 1 }
    /^[[:space:]]*$/ || /^[[:space:]]*#/ { next }
    NF < 6 { next }
    {
      for (i = 1; i <= NF; i++) gsub(/^[[:space:]]+|[[:space:]]+$/, "", $i)
      if ($1 != "on" && $1 != "off") next
      if (!all && $1 != "on" && !($2 in keep)) next
      if (length(only) && !($2 in keep)) next
      print $1 "\t" $2 "\t" $3 "\t" $4 "\t" $5 "\t" $6
    }
  ' "$MANIFEST"
}

hash_ok() {  # file, expected
  [ -n "$2" ] && [ "$2" != "-" ] || return 0
  echo "$2  $1" | sha256sum -c - >/dev/null 2>&1
}

report_sha() {  # file, expected
  [ -n "$2" ] && [ "$2" != "-" ] || { log "  [--] unpinned: $(basename "$1")"; return 0; }
  # Hashing multi-hundred-MB adapters on every idempotent re-run is the slowest
  # part of a restart, so cached files are skipped unless --verify/--check.
  if [ "$CHECK" = 0 ] && [ "$VERIFY" = 0 ] && [ "$DRY" = 0 ] \
     && [ $(( $(date +%s) - $(stat -c %Y "$1") )) -gt 300 ]; then
    log "  [skip] sha256 (cached): $(basename "$1") — use --verify to re-hash"
    return 0
  fi
  if hash_ok "$1" "$2"; then
    log "  [ok] sha256: $(basename "$1")"
  else
    log "  [WARN] sha256 mismatch: $1 (expected $2)"
  fi
}

# --- stage / verify ----------------------------------------------------------
n_stage=0; n_ok=0; n_missing=0; n_bad=0; staged_sets=""; seen=" "
while IFS=$'\t' read -r state set repo dest remote sha; do
  [ -n "$state" ] || continue
  local_path="$REPO_ROOT/$dest/$remote"
  case "$seen" in
    *" $set "*) : ;;
    *) seen="$seen$set "; staged_sets="$staged_sets${staged_sets:+, }$set" ;;
  esac

  if [ "$CHECK" = 1 ]; then
    if [ -f "$local_path" ]; then
      n_ok=$((n_ok + 1))
      log "[ok] $local_path"
      report_sha "$local_path" "$sha"
    else
      n_missing=$((n_missing + 1))
      log "[MISSING] $local_path"
    fi
    continue
  fi

  mkdir -p "$REPO_ROOT/$dest/$(dirname "$remote")"
  log "$set: $repo → $dest/$remote"
  if out="$(RUN "$HF" download "$repo" "$remote" --local-dir "$REPO_ROOT/$dest" 2>&1)"; then
    n_stage=$((n_stage + 1))
  else
    n_bad=$((n_bad + 1))
    printf '%s\n' "$out" | tail -n 5 >&2
    log "[FAIL] download: $repo/$remote"
    continue
  fi
  [ "$DRY" = 1 ] || report_sha "$local_path" "$sha"
done < <(selected)

if [ "$CHECK" = 1 ]; then
  log "checked: $n_ok present, $n_missing missing"
  [ "$n_missing" = 0 ] || exit 1
  exit 0
fi

if [ "$DRY" = 1 ]; then
  log "would stage $n_stage file(s) from: $staged_sets"
else
  log "staged $n_stage file(s) from: $staged_sets"
fi
[ "$n_bad" = 0 ] || { log "$n_bad download(s) failed"; exit 1; }

# Tell the user what is intentionally not staged, so a manifest that needs it
# fails loudly here rather than in generate.py's preflight.
skipped="$(awk -F'\t' -v staged="$staged_sets" '
  BEGIN { n = split(staged, s, ", "); for (i = 1; i <= n; i++) have[s[i]] = 1 }
  /^[[:space:]]*$/ || /^[[:space:]]*#/ { next }
  NF < 6 { next }
  $1 == "off" && !($2 in have) { print $2 }
' "$MANIFEST" | sort -u | paste -sd, - | sed 's/,/, /g')"
[ -z "$skipped" ] || log "opt-in, not staged: $skipped (use --only <set> or --all)"
