#!/usr/bin/env python3
"""Mirror this repo's generation outputs to GCS on a timer.

Ported from the parent project's `backup_to_gcp.py` (same loop, manifest
logic, and CLI), narrowed to what this repo produces:

    gs://akbar-december-2024-backup/arabmaqamrock/
      runs/   <-  ./out/     (one folder per generation run, from generate.py)
      logs/   <-  ./logs/    (setup + this daemon's own log)

`gsutil rsync` is append/update-only (no `-d`): nothing is ever deleted
remote. If a pass catches a WAV mid-write, the next pass re-uploads it once
its size settles, so a torn upload self-heals.

By default this sidecar treats every run as a trial: finished WAVs are
transcoded to MP3 (cached under `.cache/gcs_mp3/`) and only the MP3 is
uploaded. A run can opt into WAV upload with `UPLOAD_POLICY.json` (see
`plumbing/mark_production.py`). Finished per-song transcript directories are
archived to `<take>.tar.gz` before upload. Both behaviours have escape hatches:
`--audio-upload wav` and `--legacy-transcripts`.

A `run_manifest.json` is written at the prefix root so the prefix identifies
itself and refuses to be shared by a different `--run-name`.

Usage:
    python plumbing/backup_to_gcp.py                 # daemon, 5-min passes
    python plumbing/backup_to_gcp.py --once          # one pass, for cron
    python plumbing/backup_to_gcp.py --dry-run --once
    python plumbing/backup_to_gcp.py --interval-minutes 10

    # mirror an arbitrary folder INSTEAD of the defaults (drops them)
    python plumbing/backup_to_gcp.py --watch ~/my_songs --run-name my_songs
    # add one folder ON TOP of the defaults
    python plumbing/backup_to_gcp.py --extra ~/my_songs
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent      # plumbing/ -> repo root

try:  # package import (tests) and script import (CLI)
    from .audio_export import (
        DEFAULT_BITRATE, cache_run_dir, export_run,
    )
    from .transcript_archive import archive_transcripts
except ImportError:  # pragma: no cover - script mode
    from audio_export import (  # type: ignore
        DEFAULT_BITRATE, cache_run_dir, export_run,
    )
    from transcript_archive import archive_transcripts  # type: ignore

# Runtime-supplied, like the API keys. Format: a bucket ROOT
# (gs://<bucket>); the prefix is <base>/<run-name> (= gs://…/arabmaqamrock).
# Read from GCP_ROOT (this repo's own variable) — deliberately NOT the parent
# project's GCP_BACKUP_BASE, which is a project prefix, so exporting one never
# silently relocates the other. Override per invocation with --base.
DEFAULT_BASE = os.environ.get("GCP_ROOT", "gs://akbar-december-2024-backup")
DEFAULT_RUN_NAME = "arabmaqamrock"
RESERVED_SUBFOLDERS = {"binaries"}          # never usable as a --run-name
DEFAULT_LOG = REPO_ROOT / "logs" / "gcp_backup.log"
DEFAULT_MP3_CACHE = REPO_ROOT / ".cache" / "gcs_mp3"
OUT_ROOT = REPO_ROOT / "out"
WAV_EXCLUDE = r".*\.wav$"
TRANSCRIPT_RAW_EXCLUDE = r".*transcripts/[^/]+/.*"

# (source folder, remote subfolder, wait-for-settle-before-sync)
TARGETS = [
    (REPO_ROOT / "out", "runs", False),
    (REPO_ROOT / "logs", "logs", False),
]
DEFAULT_EXCLUDES = [r".*\.tmp$"]


def parse_watch_specs(specs: list[str]) -> list[tuple[Path, str]]:
    """`LOCAL` or `LOCAL:SUB` -> (expanded path, remote subfolder, "" = root)."""
    out: list[tuple[Path, str]] = []
    for spec in specs:
        local, sub = spec.split(":", 1) if ":" in spec else (spec, "")
        out.append((Path(local).expanduser(), sub.strip("/")))
    return out


def run_name_from_path(path: Path) -> str:
    """A GCS-safe run name derived from a watched folder's basename."""
    name = re.sub(r"[^A-Za-z0-9._-]+", "-", path.name).strip("-")
    return name or "watch"


def parse_extra_specs(specs: list[str]) -> list[tuple[Path, str]]:
    """`LOCAL` or `LOCAL:SUB` for targets ADDED to the current set. No `:SUB`
    uses the folder's basename; `LOCAL:` mirrors at the prefix root."""
    out: list[tuple[Path, str]] = []
    for spec in specs:
        local, sub = spec.split(":", 1) if ":" in spec else (spec, None)
        path = Path(local).expanduser()
        out.append((path, run_name_from_path(path) if sub is None else sub.strip("/")))
    return out


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument(
        "--run-name", default=None,
        help=f"This run's subfolder under <base> (default: {DEFAULT_RUN_NAME!r}).",
    )
    p.add_argument(
        "--watch", action="append", default=None, metavar="LOCAL[:SUB]",
        help="Mirror this local folder (repeatable) INSTEAD of the defaults "
             "(out/, logs/) — DROPS them; use --extra to keep them. LOCAL is "
             "~-expanded; SUB is the remote subfolder and defaults to the prefix "
             "root for a single --watch (give each its own :SUB when watching "
             "several). With no --run-name the name derives from the first folder.",
    )
    p.add_argument(
        "--extra", action="append", default=None, metavar="LOCAL[:SUB]",
        help="ADD this local folder (repeatable) on top of the current targets "
             "— unlike --watch, the defaults are kept. SUB defaults to the "
             "folder's basename; `LOCAL:` mirrors at the prefix root.",
    )
    p.add_argument(
        "--base", default=None,
        help="GCS bucket root to mirror into (gs://<bucket>); the prefix is "
             "<base>/<run-name>. Defaults to $GCP_ROOT; required if that is unset.",
    )
    p.add_argument("--interval-minutes", type=float, default=5.0,
                   help="Minutes between passes (default: 5).")
    p.add_argument("--once", action="store_true", help="Run one pass and exit.")
    p.add_argument("--dry-run", action="store_true",
                   help="Log the sync commands but upload nothing.")
    p.add_argument("--gsutil", default="gsutil", help="gsutil executable to use.")
    p.add_argument("--log-file", default=str(DEFAULT_LOG),
                   help=f"Log file (default: {DEFAULT_LOG}).")
    p.add_argument("--exclude", action="append", default=[],
                   help="Extra gsutil -x regex to exclude (repeatable).")
    p.add_argument("--audio-upload", choices=("mp3", "wav"), default="mp3",
                   help="Upload format for finished WAV takes: 'mp3' (default) "
                        "transcodes and uploads MP3; 'wav' is the old behaviour. "
                        "UPLOAD_POLICY.json can select WAV per take/run.")
    p.add_argument("--mp3-bitrate", default=DEFAULT_BITRATE,
                   help=f"MP3 bitrate (default: {DEFAULT_BITRATE}).")
    p.add_argument("--mp3-cache", default=str(DEFAULT_MP3_CACHE),
                   help=f"MP3 cache root (default: {DEFAULT_MP3_CACHE}).")
    p.add_argument("--transcode-unverified", action="store_true",
                   help="Transcode WAVs even when no successful _time.txt exists "
                        "(for restored/copied WAVs).")
    p.add_argument("--legacy-transcripts", action="store_true",
                   help="Upload raw transcript song directories instead of "
                        "archiving complete ones to <take>.tar.gz.")
    p.add_argument("--compression", choices=("gzip", "xz", "none"),
                   default="gzip",
                   help="Transcript archive compression (default: gzip).")
    p.add_argument("--require-run-manifest", action="store_true",
                   help="Only archive tracks that transcribe_manifest.json "
                        "lists as done.")
    return p.parse_args()


def setup_logging(log_file: str) -> logging.Logger:
    logger = logging.getLogger("gcp_backup")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s",
                            "%Y-%m-%d %H:%M:%S")
    stream = logging.StreamHandler(sys.stdout)
    stream.setFormatter(fmt)
    logger.addHandler(stream)
    path = Path(log_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    fh = logging.FileHandler(path, encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    return logger


def sync(src: Path, dst: str, args: argparse.Namespace, logger: logging.Logger,
         *, exclude: list[str] | tuple[str, ...] = ()) -> bool:
    # gsutil honours only the last -x flag, so combine every pattern.
    patterns = DEFAULT_EXCLUDES + list(args.exclude) + list(exclude)
    cmd = [args.gsutil, "-m", "rsync", "-r", "-x",
           "(" + "|".join(patterns) + ")", str(src), dst.rstrip("/") + "/"]
    logger.info("syncing %s -> %s", src, dst)
    if args.dry_run:
        logger.info("dry-run: %s", " ".join(cmd))
        return True
    started = time.perf_counter()
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error("sync failed (exit %d): %s", result.returncode,
                     (result.stderr or result.stdout).strip()[-2000:])
        return False
    logger.info("ok: %s in %.1fs", src, time.perf_counter() - started)
    return True


def read_remote_json(remote: str, args: argparse.Namespace,
                     logger: logging.Logger) -> dict | None:
    result = subprocess.run([args.gsutil, "cat", remote],
                            capture_output=True, text=True)
    if result.returncode != 0 or not result.stdout.strip():
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        logger.warning("could not parse %s; treating it as absent", remote)
        return None


def ensure_manifest(prefix: str, run_name: str, targets, args: argparse.Namespace,
                    logger: logging.Logger) -> bool:
    """Write the run marker, refusing to write into a prefix owned by another run."""
    remote = f"{prefix.rstrip('/')}/run_manifest.json"
    existing = read_remote_json(remote, args, logger)
    if existing is not None and existing.get("run_name") != run_name:
        if existing.get("prefix", "").rstrip("/") == prefix.rstrip("/"):
            logger.error("run prefix %s already belongs to run %r; refusing to mix.",
                         prefix, existing.get("run_name"))
            return False
        logger.warning("adopting prefix %s: manifest names run %r but records prefix "
                       "%r; rewriting it for run %r",
                       prefix, existing.get("run_name"), existing.get("prefix"), run_name)
    stamp = dt.datetime.now().isoformat(timespec="seconds")
    manifest = {
        "run_name": run_name,
        "created": (existing or {}).get("created", stamp),
        "updated": stamp,
        "base": args.base,
        "prefix": prefix,
        "audio_upload": args.audio_upload,
        "mp3_bitrate": args.mp3_bitrate if args.audio_upload == "mp3" else None,
        "transcript_archives": not args.legacy_transcripts,
        "transcript_compression": (args.compression
                                    if not args.legacy_transcripts else None),
        "targets": [{"source": str(src), "subfolder": sub} for src, sub, _ in targets],
    }
    payload = json.dumps(manifest, indent=2) + "\n"
    if args.dry_run:
        logger.info("dry-run: would write manifest %s", remote)
        return True
    result = subprocess.run([args.gsutil, "cp", "-", remote],
                            input=payload, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error("could not write manifest %s: %s", remote,
                     (result.stderr or result.stdout).strip()[-2000:])
        return False
    logger.info("run manifest: %s", remote)
    return True


def copy_file(src: Path, dst_dir: str, args: argparse.Namespace,
              logger: logging.Logger) -> bool:
    """Upload one file (used for selected production WAVs and out/latest)."""
    if not src.is_file():
        logger.error("cannot copy missing file: %s", src)
        return False
    dst = dst_dir.rstrip("/") + "/" + src.name
    cmd = [args.gsutil, "cp", str(src), dst]
    logger.info("copying %s -> %s", src, dst)
    if args.dry_run:
        logger.info("dry-run: %s", " ".join(cmd))
        return True
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error("copy failed (exit %d): %s", result.returncode,
                     (result.stderr or result.stdout).strip()[-2000:])
        return False
    return True


def run_excludes(args: argparse.Namespace, *,
                 compress_transcripts: bool) -> list[str]:
    """The per-run rsync excludes for the current audio/transcript policy."""
    excludes: list[str] = []
    if args.audio_upload != "wav":
        excludes.append(WAV_EXCLUDE)
    if not args.legacy_transcripts and compress_transcripts:
        excludes.append(TRANSCRIPT_RAW_EXCLUDE)
    return excludes


def archive_pass(out_root: Path, args: argparse.Namespace,
                 logger: logging.Logger) -> set[Path]:
    """Archive completed transcript dirs. Returns runs where it failed."""
    failed: set[Path] = set()
    if args.legacy_transcripts:
        return failed
    try:
        transcript_dirs = sorted(p for p in out_root.glob("*/transcripts")
                                 if p.is_dir())
    except OSError as exc:
        logger.error("could not scan %s for transcripts: %s", out_root, exc)
        return failed
    for tdir in transcript_dirs:
        run = tdir.parent.resolve()
        try:
            report = archive_transcripts(
                tdir, compression=args.compression, dry_run=args.dry_run,
                require_run_manifest=args.require_run_manifest, logger=logger)
        except Exception as exc:  # noqa: BLE001 - fall back to raw upload
            logger.error("transcript archive failed for %s: %s", tdir, exc)
            failed.add(run)
            continue
        if report.blocked_reason:
            logger.warning("transcripts %s: not archiving: %s", tdir,
                           report.blocked_reason)
        if report.failed:
            logger.error("transcripts %s: %d archive(s) failed", tdir,
                         len(report.failed))
            failed.add(run)
        else:
            logger.info("transcripts %s: %s", tdir, report.summary())
    return failed


def sync_run(run_dir: Path, remote_dir: str, args: argparse.Namespace,
             logger: logging.Logger, *, compress_transcripts: bool) -> bool:
    """Mirror one run, applying the audio and transcript policies."""
    if not compress_transcripts and not args.legacy_transcripts:
        logger.warning("%s: uploading raw transcript dirs because archiving "
                       "failed for this run", run_dir)
    if args.audio_upload == "wav":
        return sync(run_dir, remote_dir, args, logger,
                    exclude=run_excludes(args,
                                         compress_transcripts=compress_transcripts))

    try:
        report = export_run(
            run_dir, Path(args.mp3_cache).expanduser(),
            bitrate=args.mp3_bitrate,
            require_finished=not args.transcode_unverified,
            dry_run=args.dry_run, logger=logger)
    except Exception as exc:  # noqa: BLE001 - never lose the backup
        logger.error("audio policy failed for %s: %s; uploading WAVs as "
                     "a safe fallback", run_dir, exc)
        return sync(run_dir, remote_dir, args, logger)

    logger.info("audio %s: %s", run_dir, report.summary())

    ok = sync(run_dir, remote_dir, args, logger,
              exclude=run_excludes(args,
                                   compress_transcripts=compress_transcripts))

    # The cache mirrors the run's relative audio paths, so this lands each
    # MP3 at runs/<run>/<take>.mp3.
    cache_dir = cache_run_dir(Path(args.mp3_cache).expanduser(), run_dir)
    if cache_dir.is_dir() and any(cache_dir.rglob("*.mp3")):
        ok = sync(cache_dir, remote_dir, args, logger,
                  exclude=[r".*\.json$"]) and ok

    for wav in report.wavs + report.fallbacks:
        ok = copy_file(wav, remote_dir, args, logger) and ok

    if report.fallbacks:
        logger.warning("%s: %d WAV(s) uploaded because MP3 export failed",
                       run_dir, len(report.fallbacks))
    return ok


def is_runs_root(path: Path) -> bool:
    """True when ``path`` looks like a folder of generation runs."""
    if path.resolve() == OUT_ROOT.resolve():
        return True
    try:
        children = list(path.iterdir())
    except OSError:
        return False
    for child in children:
        if not child.is_dir():
            continue
        if (child / "batch_manifest.json").is_file():
            return True
        try:
            if any(child.glob("*.wav")):
                return True
        except OSError:
            pass
    return False


def sync_out_root(out_root: Path, remote_root: str, args: argparse.Namespace,
                  logger: logging.Logger) -> tuple[int, int]:
    """Sync every run under out/, archiving transcripts first."""
    remote_root = remote_root.rstrip("/")
    failed_runs = archive_pass(out_root, args, logger)
    synced = 0
    runs = sorted(p for p in out_root.iterdir() if p.is_dir())
    for run_dir in runs:
        remote = f"{remote_root}/{run_dir.name}"
        if sync_run(run_dir, remote, args, logger,
                    compress_transcripts=run_dir.resolve() not in failed_runs):
            synced += 1
    # Top-level files (out/latest and friends) keep their old location.
    top_files = sorted(p for p in out_root.iterdir() if p.is_file())
    for path in top_files:
        copy_file(path, remote_root, args, logger)
    return synced, len(runs)


def main() -> int:
    args = parse_args()
    logger = setup_logging(args.log_file)

    gsutil = shutil.which(args.gsutil)
    if not gsutil:
        logger.error("could not find '%s' on PATH", args.gsutil)
        return 2
    args.gsutil = gsutil

    args.base = (args.base or DEFAULT_BASE).rstrip("/")
    if not args.base:
        logger.error("no GCS base: pass --base or set GCP_BACKUP_BASE")
        return 3

    watch = parse_watch_specs(args.watch) if args.watch else None
    extra = parse_extra_specs(args.extra) if args.extra else None
    missing = [str(p) for p, _ in (watch or []) + (extra or []) if not p.is_dir()]
    if missing:
        logger.error("target path is not a directory: %s", ", ".join(missing))
        return 3
    if watch and sum(1 for _, sub in watch if not sub) > 1:
        logger.error("multiple --watch targets need an explicit :SUB")
        return 3

    if not args.run_name:
        args.run_name = run_name_from_path(watch[0][0]) if watch else DEFAULT_RUN_NAME
    if args.run_name in RESERVED_SUBFOLDERS:
        logger.error("%r is a reserved folder under %s; pick another run name.",
                     args.run_name, args.base)
        return 3

    prefix = f"{args.base}/{args.run_name}"
    base_targets = ([(p, s, False) for p, s in watch] if watch else list(TARGETS))
    targets = base_targets + [(p, s, False) for p, s in (extra or [])]

    subs = [s for _, s, _ in targets]
    collisions = sorted({s for s in subs if subs.count(s) > 1})
    if collisions:
        logger.error("duplicate remote subfolder(s): %s; give a distinct :SUB.",
                     ", ".join(repr(s) for s in collisions))
        return 3

    logger.info("backup run %r -> %s/%s every %.0f min (once=%s, dry-run=%s)",
                args.run_name, args.base, args.run_name, args.interval_minutes,
                args.once, args.dry_run)
    logger.info("audio upload: %s (mp3 bitrate=%s, cache=%s)",
                args.audio_upload, args.mp3_bitrate, args.mp3_cache)
    logger.info("transcript archives: %s (compression=%s, require-manifest=%s)",
                not args.legacy_transcripts, args.compression,
                args.require_run_manifest)
    for src, sub, _ in targets:
        logger.info("  watching %s -> %s/%s", src, prefix, sub)

    if not ensure_manifest(prefix, args.run_name, targets, args, logger):
        return 3

    try:
        while True:
            synced = 0
            attempted = 0
            for src, sub, _ in targets:
                if not src.is_dir():
                    logger.warning("skipping missing folder %s", src)
                    continue
                attempted += 1
                remote = f"{prefix}/{sub}"
                if is_runs_root(src):
                    done, run_total = sync_out_root(src, remote, args, logger)
                    if done == run_total:
                        synced += 1
                elif sync(src, remote, args, logger):
                    synced += 1
            logger.info("pass complete: %d/%d folders synced", synced, attempted)
            if args.once:
                break
            time.sleep(max(1.0, args.interval_minutes * 60.0))
    except KeyboardInterrupt:
        logger.info("interrupted; last completed pass is what is in GCS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
