#!/usr/bin/env python3
"""Mark selected takes (or a whole run) for WAV upload instead of MP3.

Generation always writes WAV.  By default ``backup_to_gcp.py`` uploads MP3 for
every finished take; this tool writes ``UPLOAD_POLICY.json`` so the backup
uploads the selected WAVs instead.

Examples::

    python plumbing/mark_production.py out/<run> --take song_391847
    python plumbing/mark_production.py out/<run> --all
    python plumbing/mark_production.py out/<run> --reset
    python plumbing/mark_production.py out/<run> --take song_391847 --dry-run
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:  # package import (tests) and script import (CLI)
    from .audio_export import (
        POLICY_MP3, POLICY_NAME, POLICY_WAV, PolicyError, UploadPolicy,
        read_policy, utcnow, write_policy,
    )
except ImportError:  # pragma: no cover - script mode
    from audio_export import (  # type: ignore
        POLICY_MP3, POLICY_NAME, POLICY_WAV, PolicyError, UploadPolicy,
        read_policy, utcnow, write_policy,
    )


def _existing_policy(run_dir: Path) -> UploadPolicy:
    path = run_dir / POLICY_NAME
    if not path.is_file():
        return UploadPolicy()
    return read_policy(run_dir)


def mark(run_dir: Path, *, takes: list[str], all_takes: bool,
         reason: str | None, reset: bool, dry_run: bool) -> dict:
    if reset:
        payload = {
            "audio": POLICY_MP3,
            "takes": [],
            "reason": reason or "reset to the trial MP3 default",
            "marked_utc": utcnow(),
        }
        if dry_run:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return payload
        # Write a positive MP3 policy rather than deleting the file: the daily
        # gsutil rsync is append-only, so a deleted local policy would leave the
        # old remote copy behind.
        write_policy(run_dir, POLICY_MP3, [], payload["reason"])
        print(f"wrote {run_dir / POLICY_NAME} (audio=mp3)")
        return payload

    if not all_takes and not takes:
        raise PolicyError("pass --take STEM (repeatable), --all, or --reset")

    existing = _existing_policy(run_dir)
    if all_takes:
        merged: list[str] = []
    else:
        merged = list(existing.takes)
        for take in takes:
            take = take.strip()
            if take and take not in merged:
                merged.append(take)

    payload = {
        "audio": POLICY_WAV,
        "takes": merged,
        "reason": reason if reason is not None else existing.reason,
        "marked_utc": utcnow(),
    }
    if dry_run:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return payload
    write_policy(run_dir, POLICY_WAV, merged, payload["reason"])
    print(f"wrote {run_dir / POLICY_NAME}")
    if merged:
        print("  WAV upload: " + ", ".join(merged))
    else:
        print("  WAV upload: the whole run")
    missing = [t for t in merged if not (run_dir / f"{t}.wav").is_file()]
    if missing:
        print("  [warn] no local WAV for: " + ", ".join(missing))
    return payload


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_dir", help="generation run directory (out/<run>)")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--take", action="append", default=[], metavar="STEM",
                   help="take stem to upload as WAV (repeatable)")
    g.add_argument("--all", action="store_true",
                   help="upload the whole run as WAV")
    g.add_argument("--reset", action="store_true",
                   help="write audio=mp3 (trial default) instead of WAV")
    ap.add_argument("--reason", default=None, help="free-text note for the policy")
    ap.add_argument("--dry-run", action="store_true", help="print, do not write")
    args = ap.parse_args(argv)

    run_dir = Path(args.run_dir).expanduser().resolve()
    if not run_dir.is_dir():
        print(f"not a directory: {run_dir}", file=sys.stderr)
        return 2
    try:
        mark(run_dir, takes=args.take, all_takes=args.all,
             reason=args.reason, reset=args.reset, dry_run=args.dry_run)
    except PolicyError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
