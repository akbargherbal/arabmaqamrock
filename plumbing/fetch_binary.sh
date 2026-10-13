#!/usr/bin/env bash
#
# Stage `audiocpp_cli` into ./bin/ for the machine you are on.
#
# Priority: fetch the prebuilt for the local GPU's arch from this repo's GCS
# prefix (fast — no compile), and fall back to building from source.
#
# A build needs NO GPU: nvcc cross-compiles device code for an explicit
# --cuda-arch. It does need the CUDA toolkit + cmake + ccache installed, and
# takes ~21 min cold (see the parent repo's docs/audiocpp_gpu_arch_builds.md).
#
# Usage:
#   ./plumbing/fetch_binary.sh                  # fetch the prebuilt for the local GPU
#   ./plumbing/fetch_binary.sh --cuda-arch 75   # explicit arch (needed to build with no GPU)
#   ./plumbing/fetch_binary.sh --build          # build from source instead of fetching
#   ./plumbing/fetch_binary.sh --publish        # after a build, upload it (+ sha256 + manifest) to GCS
#   ./plumbing/fetch_binary.sh --force          # re-stage even if bin/audiocpp_cli exists
#   ./plumbing/fetch_binary.sh --dry-run        # print the plan, do nothing
#
# The binary is arch + CUDA-suite + audio.cpp-commit specific; binaries/<tag>/
# carries a manifest.json recording those. `--build` honours plumbing/audio_cpp.pin
# when set (a commit sha), else tracks audio.cpp main.
set -euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/env.sh"
. "$PLUMBING_DIR/arch.sh"

BIN_DIR="$REPO_ROOT/bin"
BIN="$BIN_DIR/audiocpp_cli"
ARCH_FILE="$BIN_DIR/.arch"        # the tag the staged binary came from
PIN_FILE="$PLUMBING_DIR/audio_cpp.pin"
AUDIO_CPP_REPO="https://github.com/0xShug0/audio.cpp"

FORCE=0; DO_BUILD=0; DO_PUBLISH=0; DRY=0; CC=""
while [ $# -gt 0 ]; do
  case "$1" in
    --cuda-arch) CC="${2:?--cuda-arch needs a value}"; shift 2 ;;
    --build)     DO_BUILD=1; shift ;;
    --publish)   DO_PUBLISH=1; shift ;;
    --force)     FORCE=1; shift ;;
    --dry-run)   DRY=1; shift ;;
    -h|--help)   sed -n '3,18p' "$0"; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

log() { printf '[fetch_binary] %s\n' "$*"; }
# $RUN: execute, or print when --dry-run.
RUN() { if [ "$DRY" = 1 ]; then echo "  dry-run: $*"; else "$@"; fi; }

# --- resolve the target arch -------------------------------------------------
[ -n "$CC" ] || CC="$(detect_compute_cap)"
TAG="$(arch_tag_for_cc "$CC")"

if [ -x "$BIN" ] && [ "$FORCE" != 1 ]; then
  log "bin/audiocpp_cli already staged (arch: $(cat "$ARCH_FILE" 2>/dev/null || echo '?')); --force to re-stage"
  exit 0
fi

# --- 1. prebuilt from GCS (default) ------------------------------------------
fetch_prebuilt() {
  if [ -z "$TAG" ]; then
    log "no GPU detected and no --cuda-arch: cannot choose a prebuilt"
    return 1
  fi
  local remote="$GCP_PREFIX/binaries/$TAG"
  log "fetching prebuilt $TAG  <-  $remote/audiocpp_cli"
  if [ "$DRY" = 1 ]; then echo "  dry-run: would fetch + sha256-verify, then stage $BIN"; return 0; fi

  mkdir -p "$BIN_DIR"
  local tmp; tmp="$(mktemp "$BIN_DIR/.audiocpp_cli.XXXXXX")"
  if ! gcs_cp "$remote/audiocpp_cli" "$tmp" >/dev/null 2>&1; then
    log "no prebuilt there (or no GCS access) — will build"
    rm -f "$tmp"; return 1
  fi
  if gcs_cat "$remote/audiocpp_cli.sha256" > "$tmp.sha256" 2>/dev/null; then
    local want have
    want="$(awk '{print $1}' "$tmp.sha256")"
    have="$(sha256sum "$tmp" | awk '{print $1}')"
    if [ "$want" != "$have" ]; then
      log "sha256 MISMATCH (want $want, got $have) — discarding, will build"
      rm -f "$tmp" "$tmp.sha256"; return 1
    fi
    log "sha256 ok: $have"
  else
    log "WARNING: no .sha256 published for $TAG — staging unverified"
  fi
  rm -f "$tmp.sha256"
  mv "$tmp" "$BIN"; chmod +x "$BIN"
  printf '%s\n' "$TAG" > "$ARCH_FILE"
  log "staged $BIN  ($TAG)"
  return 0
}

# --- 2. build from source (fallback / --build) -------------------------------
build_from_source() {
  if [ -z "$CC" ]; then
    log "--build needs --cuda-arch <CC> (no GPU here to detect it)"
    exit 2
  fi
  for tool in git cmake nvcc ccache; do
    command -v "$tool" >/dev/null 2>&1 || {
      log "MISSING '$tool' — a build needs the CUDA toolkit, cmake and ccache"
      log "  (apt-get install git cmake ccache + the NVIDIA CUDA toolkit)"
      exit 1
    }
  done
  local ac="$REPO_ROOT/audio.cpp" pin
  pin="$(grep -v '^[[:space:]]*#' "$PIN_FILE" 2>/dev/null | tr -d '[:space:]' | head -n1 || true)"
  if [ -d "$ac/.git" ]; then
    log "updating audio.cpp checkout at $ac"
    RUN git -C "$ac" fetch --depth 1 origin
    if [ -n "$pin" ]; then RUN git -C "$ac" fetch --depth 1 origin "$pin" || true; fi
  else
    log "cloning audio.cpp"
    RUN git clone --quiet "$AUDIO_CPP_REPO" "$ac"
  fi
  if [ -n "$pin" ]; then
    log "checking out pinned audio.cpp commit $pin"
    RUN git -C "$ac" checkout --quiet "$pin"
  else
    log "no pin (plumbing/audio_cpp.pin empty) — tracking audio.cpp main"
    RUN git -C "$ac" reset --hard FETCH_HEAD 2>/dev/null || true
  fi
  log "building audiocpp_cli (--cuda-arch $CC) — cold build ~21 min"
  ( cd "$ac" && RUN scripts/build_linux.sh --backend cuda --cuda-arch "$CC" --ccache \
        --model-set custom --models yue2 --target audiocpp_cli )
  RUN mkdir -p "$BIN_DIR"
  RUN cp "$ac/build/linux-cuda-release/bin/audiocpp_cli" "$BIN"
  RUN chmod +x "$BIN"
  RUN sh -c "printf '%s\n' '$TAG' > '$ARCH_FILE'"
  log "built $BIN  ($TAG, audio.cpp $(git -C "$ac" rev-parse --short HEAD 2>/dev/null || echo '?'))"
}

publish_binary() {
  [ -x "$BIN" ] || { log "--publish: no bin/audiocpp_cli to publish"; exit 1; }
  [ -n "$TAG" ] || { log "--publish: unknown arch tag"; exit 2; }
  local ac="$REPO_ROOT/audio.cpp" commit cuda
  commit="$(git -C "$ac" rev-parse HEAD 2>/dev/null || echo unknown)"
  cuda="$( { nvcc --version 2>/dev/null | grep -oE 'release [0-9.]+' | head -n1 | cut -d' ' -f2; } || echo unknown)"
  local remote="$GCP_PREFIX/binaries/$TAG"
  log "publishing $BIN -> $remote/  (audio.cpp ${commit:0:12}, cuda $cuda)"
  if [ "$DRY" = 1 ]; then echo "  dry-run: would upload binary + sha256 + manifest.json"; return 0; fi
  local h size; h="$(sha256sum "$BIN" | awk '{print $1}')"; size="$(stat -c %s "$BIN")"
  gcs_cp "$BIN" "$remote/audiocpp_cli" >/dev/null
  printf '%s  audiocpp_cli\n' "$h" > "$BIN.sha256"
  gcs_cp "$BIN.sha256" "$remote/audiocpp_cli.sha256" >/dev/null
  python3 - "$TAG" "$CC" "$h" "$size" "$commit" "$cuda" "$remote" > "$BIN.manifest.json" <<'PY'
import json, sys, datetime
tag, cc, h, size, commit, cuda, src = sys.argv[1:8]
print(json.dumps({
    "arch_tag": tag, "cuda_arch": cc,
    "audio_cpp_commit": commit, "ggml_commit": "see build log",
    "cuda_toolkit": cuda,
    "build_flags": f"--backend cuda --cuda-arch {cc} --ccache --model-set custom --models yue2 --target audiocpp_cli",
    "size_bytes": int(size), "sha256": h,
    "built_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "source": src,
}, indent=2) + "\n")
PY
  gcs_cp "$BIN.manifest.json" "$remote/manifest.json" >/dev/null
  rm -f "$BIN.sha256" "$BIN.manifest.json"
  log "published $TAG (sha256 $h)"
}

# --- dispatch ----------------------------------------------------------------
if [ "$DRY" = 1 ]; then
  log "arch=$CC tag=${TAG:-?} build=$DO_BUILD publish=$DO_PUBLISH"
  [ "$DO_BUILD" = 1 ] && { build_from_source; exit 0; }
  fetch_prebuilt || { log "(dry-run) would fall back to building from source"; }
  exit 0
fi

if [ "$DO_BUILD" = 1 ]; then
  build_from_source
  [ "$DO_PUBLISH" = 1 ] && publish_binary
elif ! fetch_prebuilt; then
  log "falling back to a source build"
  build_from_source
  [ "$DO_PUBLISH" = 1 ] && publish_binary
elif [ "$DO_PUBLISH" = 1 ]; then
  publish_binary
fi

"$BIN" --version 2>/dev/null || true
