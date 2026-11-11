#!/usr/bin/env python3
"""Verified push/pull of SheetSage2 transcripts for the YT500 run.

A transcript directory is uploaded only when it is a complete, verified pair:

* ``meta.json`` exists and ``status == "ok"``;
* ``meta.abc_sha256`` exists and equals ``sha256(score.abc)``.

Half-written directories are therefore never pushed.  ``pull`` rsyncs the same
prefix back at session start, so ``transcribe.py`` sees a verified pair and
reports ``skipped`` rather than ``skipped-unverified``.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import tarfile
import time
from pathlib import Path

PREFIX = "gs://akbar-december-2024-backup/ANALYSIS/yt500_instrumental_abc"
DEFAULT_TRANSCRIPTS = Path("/content/yt500/transcripts")
REPO = Path(__file__).resolve().parent.parent


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def verified_pair(tdir: Path) -> tuple[bool, str, str | None]:
    abc, meta = tdir / "score.abc", tdir / "meta.json"
    if not abc.is_file() or not meta.is_file():
        return False, "missing score.abc/meta.json", None
    m = read_json(meta)
    if not m:
        return False, "meta.json unreadable", None
    if m.get("status") != "ok":
        return False, f"meta status={m.get('status')!r}", None
    want = m.get("abc_sha256")
    if not want:
        return False, "meta.abc_sha256 missing", None
    got = sha256_file(abc)
    if got != want:
        return False, "score.abc does not match meta.abc_sha256", got
    return True, "ok", got


def gsutil(args: list[str], check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["gsutil", "-q", *args], check=check,
                          capture_output=True, text=True)


def state_path(args) -> Path:
    return Path(args.state)


def load_state(path: Path) -> dict:
    if path.is_file():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            return {}
    return {}


def save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True))
    tmp.replace(path)


def cmd_push(args) -> int:
    root = Path(args.transcripts)
    prefix = args.prefix.rstrip("/")
    state_file = state_path(args)
    state = load_state(state_file)
    pushed, skipped, bad = 0, 0, []
    dirs = sorted(p for p in root.iterdir() if p.is_dir()) if root.is_dir() else []
    for tdir in dirs:
        name = tdir.name
        ok, why, sha = verified_pair(tdir)
        if not ok:
            bad.append({"name": name, "reason": why})
            continue
        meta_sha = sha256_file(tdir / "meta.json")
        key = f"{sha}:{meta_sha}"
        if state.get(name) == key and not args.force:
            skipped += 1
            continue
        dest = f"{prefix}/transcripts/{name}/"
        try:
            gsutil(["cp", str(tdir / "score.abc"), str(tdir / "meta.json"), dest])
        except subprocess.CalledProcessError as exc:
            bad.append({"name": name, "reason": f"upload failed: {exc.stderr.strip()[:200]}"})
            continue
        state[name] = key
        save_state(state_file, state)
        pushed += 1
        if args.verbose:
            print(f"pushed {name} ({sha[:12]})", flush=True)
    save_state(state_file, state)
    report = {"utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
              "verified_dirs": len(dirs) - len(bad), "pushed": pushed,
              "unchanged": skipped, "invalid": bad}
    out = Path(args.report) if args.report else root / "push_report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2))
    print(json.dumps({k: v for k, v in report.items() if k != "invalid"}))
    if bad:
        print(f"invalid/unpushed: {len(bad)} (see {out})")
    return 0 if not bad else 1


def cmd_pull(args) -> int:
    root = Path(args.transcripts)
    root.mkdir(parents=True, exist_ok=True)
    prefix = args.prefix.rstrip("/")
    r = gsutil(["rsync", "-r", f"{prefix}/transcripts", str(root)], check=False)
    if r.returncode != 0:
        print(f"pull: gsutil rsync failed: {r.stderr.strip()}", flush=True)
        return r.returncode
    ok = bad = 0
    for tdir in sorted(p for p in root.iterdir() if p.is_dir()):
        good, _, _ = verified_pair(tdir)
        ok += good
        bad += not good
    print(json.dumps({"pulled_verified": ok, "unverified_or_incomplete": bad,
                      "transcripts": str(root)}))
    return 0


def cmd_verify(args) -> int:
    root = Path(args.transcripts)
    rows = []
    for tdir in sorted(p for p in root.iterdir() if p.is_dir()):
        ok, why, sha = verified_pair(tdir)
        rows.append({"name": tdir.name, "verified": ok, "reason": why, "abc_sha256": sha})
    report = {"utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
              "total": len(rows), "verified": sum(r["verified"] for r in rows),
              "rows": rows}
    out = Path(args.report) if args.report else root / "verify_report.json"
    out.write_text(json.dumps(report, indent=2))
    print(json.dumps({k: report[k] for k in ("total", "verified")}))
    return 0 if report["verified"] == report["total"] else 1


def cmd_archive(args) -> int:
    root = Path(args.transcripts)
    names = [n.strip() for n in Path(args.names).read_text().splitlines() if n.strip()]
    prefix = args.prefix.rstrip("/")
    made = 0
    for name in names:
        tdir = root / name
        if not tdir.is_dir():
            continue
        dest = Path(args.archive_dir) / f"{name}.tar.gz"
        dest.parent.mkdir(parents=True, exist_ok=True)
        with tarfile.open(dest, "w:gz") as tf:
            for child in sorted(tdir.iterdir()):
                if child.name in ("score.abc", "meta.json"):
                    continue
                tf.add(child, arcname=f"{name}/{child.name}")
        gsutil(["cp", str(dest), f"{prefix}/artifacts/{name}.tar.gz"])
        made += 1
    print(f"archived {made} tracks -> {prefix}/artifacts/")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("push", "pull", "verify"):
        p = sub.add_parser(name)
        p.add_argument("--transcripts", default=str(DEFAULT_TRANSCRIPTS))
        p.add_argument("--prefix", default=PREFIX)
        p.add_argument("--state", default=str(REPO / "work/yt500_abc/sync_state.json"))
        p.add_argument("--report", default=None)
        p.add_argument("--verbose", action="store_true")
        p.add_argument("--force", action="store_true")
    ar = sub.add_parser("archive")
    ar.add_argument("--transcripts", default=str(DEFAULT_TRANSCRIPTS))
    ar.add_argument("--prefix", default=PREFIX)
    ar.add_argument("--names", required=True)
    ar.add_argument("--archive-dir", default="/content/yt500/artifact_archives")
    args = ap.parse_args(argv)
    return {"push": cmd_push, "pull": cmd_pull, "verify": cmd_verify,
            "archive": cmd_archive}[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
