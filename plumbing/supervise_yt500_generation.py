#!/usr/bin/env python3
"""Run the YT500 generator until the corpus is complete, unattended.

The supervisor is the unattended bulk wrapper around
``plumbing/run_yt500_generation.py``:

  1. ask the driver for the pending count;
  2. run one driver session (batch or per-track);
  3. flush ``plumbing/backup_to_gcp.py --once``;
  4. repeat until pending == 0 or a bounded number of attempts make no progress.

It never asks for confirmation and has no time cap. It writes
``logs/yt500_supervisor_done.txt`` only when it finishes or gets stuck, so the
operator can leave the VM running and come back to a single marker.

If batch mode stalls, the supervisor can fall back to the per-track path once.
Use ``--no-fallback`` to disable that.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DRIVER = ROOT / "plumbing" / "run_yt500_generation.py"
BACKUP = ROOT / "plumbing" / "backup_to_gcp.py"
PENDING_RE = re.compile(r"^pending\s+(\d+)\s*$", re.MULTILINE)


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    tmp.replace(path)


def parse_pending(output: str) -> int | None:
    match = PENDING_RE.search(output)
    return int(match.group(1)) if match else None


def status(driver: Path) -> tuple[int | None, str]:
    proc = subprocess.run([sys.executable, str(driver), "--status"],
                          capture_output=True, text=True)
    text = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode != 0:
        return None, text
    return parse_pending(proc.stdout), text


def ensure_backup() -> None:
    running = subprocess.run(
        ["pgrep", "-f", "plumbing/backup_to_gcp.py"],
        capture_output=True, text=True)
    if running.returncode == 0:
        return
    log = ROOT / "logs" / "gcp_backup_stdout.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a", encoding="utf-8") as fh:
        subprocess.Popen(
            [sys.executable, str(BACKUP), "--interval-minutes", "3"],
            stdout=fh, stderr=subprocess.STDOUT, start_new_session=True)
    print(f"[supervisor] started backup daemon -> {log}")


def flush_backup() -> int:
    proc = subprocess.run([sys.executable, str(BACKUP), "--once"])
    if proc.returncode != 0:
        print(f"[supervisor] backup flush exit={proc.returncode}")
    return proc.returncode


def run_driver(driver: Path, mode: str, batch_chunk: int) -> int:
    cmd = [sys.executable, str(driver), "--run"]
    if mode == "batch":
        cmd += ["--batch", "--batch-chunk", str(batch_chunk)]
    print(f"[supervisor] running: {' '.join(cmd)}", flush=True)
    return subprocess.run(cmd).returncode


def advance_stall(stall: int, before: int | None, after: int | None) -> int:
    """Reset the stall counter when the pending count actually falls."""
    if after is None:
        return stall + 1
    if before is not None and after < before:
        return 0
    return stall + 1


def write_marker(path: Path, *, exit_code: int, pending: int | None,
                 mode: str, attempts: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"exit={exit_code} pending={pending} mode={mode} "
        f"attempts={attempts} {utcnow()}\n",
        encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mode", choices=("batch", "per-track"), default="batch")
    ap.add_argument("--batch-chunk", type=int, default=50)
    ap.add_argument("--interval", type=float, default=60.0,
                    help="base sleep between attempts (seconds)")
    ap.add_argument("--max-interval", type=float, default=600.0)
    ap.add_argument("--stall-attempts", type=int, default=3,
                    help="no-progress attempts before fallback/stop")
    ap.add_argument("--max-attempts", type=int, default=20,
                    help="hard retry budget; not a time cap")
    ap.add_argument("--no-fallback", action="store_true",
                    help="do not switch batch -> per-track after a stall")
    ap.add_argument("--driver", type=Path, default=DRIVER)
    ap.add_argument("--marker", type=Path,
                    default=ROOT / "logs" / "yt500_supervisor_done.txt")
    ap.add_argument("--status-json", type=Path,
                    default=ROOT / "work" / "yt500_gen" / "supervisor_status.json")
    args = ap.parse_args(argv)

    mode = args.mode
    stall = 0
    attempts = 0
    last_pending: int | None = None

    ensure_backup()
    while attempts < args.max_attempts:
        attempts += 1
        pending, output = status(args.driver)
        if pending is None:
            print(f"[supervisor] attempt {attempts}: status failed\n{output[-2000:]}")
            stall += 1
        elif pending == 0:
            print(f"[supervisor] complete: 489/489 done (attempt {attempts})")
            write_marker(args.marker, exit_code=0, pending=0, mode=mode,
                         attempts=attempts)
            write_json(args.status_json, {
                "utc": utcnow(), "exit": 0, "pending": 0,
                "mode": mode, "attempts": attempts})
            return 0
        else:
            if last_pending is not None and pending < last_pending:
                stall = 0
            last_pending = pending
            print(f"[supervisor] attempt {attempts}: pending={pending} "
                  f"mode={mode} stall={stall}", flush=True)
            ensure_backup()
            rc = run_driver(args.driver, mode, args.batch_chunk)
            flush_backup()
            after, _ = status(args.driver)
            if after == 0:
                print(f"[supervisor] complete: 489/489 done (attempt {attempts})")
                write_marker(args.marker, exit_code=0, pending=0, mode=mode,
                             attempts=attempts)
                write_json(args.status_json, {
                    "utc": utcnow(), "exit": 0, "pending": 0,
                    "mode": mode, "attempts": attempts, "last_rc": rc})
                return 0
            stall = advance_stall(stall, pending, after)
            print(f"[supervisor] driver exit={rc} pending={after} "
                  f"stall={stall}", flush=True)

        write_json(args.status_json, {
            "utc": utcnow(), "pending": last_pending, "mode": mode,
            "attempts": attempts, "stall": stall})

        if stall >= args.stall_attempts:
            if mode == "batch" and not args.no_fallback:
                print("[supervisor] batch stalled; switching to per-track")
                mode = "per-track"
                stall = 0
            else:
                print(f"[supervisor] stalled at pending={last_pending}; stopping")
                write_marker(args.marker, exit_code=2, pending=last_pending,
                             mode=mode, attempts=attempts)
                return 2

        delay = min(args.interval * (2 ** min(stall, 4)), args.max_interval)
        print(f"[supervisor] sleeping {delay:.0f}s", flush=True)
        time.sleep(delay)

    print(f"[supervisor] attempt budget exhausted at pending={last_pending}")
    write_marker(args.marker, exit_code=2, pending=last_pending, mode=mode,
                 attempts=attempts)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
