#!/usr/bin/env python3
"""Verified push/pull of SheetSage2 output transcripts for the YT500 run.

Naming contract (plan §1 / §7.3, commit 4facb4a)
------------------------------------------------
* The only file called ``score.abc`` is the read-only **input** in the dataset.
* Local working tree keeps transcribe.py's layout: ``transcripts/<name>/score.abc``.
* Published objects are role-labelled::

      <prefix>/<name>.output.abc
      <prefix>/<name>.output.meta.json        # role=output_transcript + hashes
      <prefix>/archives/<name>.output-transcript.tar.gz
      <prefix>/archives/_archive_index.json
      <prefix>/sessions/<utc>/{_driver.log,_timings.csv,transcribe_manifest.json}

A transcript directory is pushed only when ``meta.json`` says ``status == "ok"``
and ``sha256(score.abc) == meta.abc_sha256``.  Archives are built by the
existing, tested ``plumbing/transcript_archive.py`` and contain the full
directory (score.abc, MIDI, labs, events.json, tokens, notation).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "plumbing"))
import transcript_archive as TA  # noqa: E402

DATASET = "gs://akbar-december-2024-backup/DATASET/yt500_instrumental"
PREFIX = "gs://akbar-december-2024-backup/DATASET/yt500_instrumental_transcripts"
ANALYSIS_PREFIX = "gs://akbar-december-2024-backup/ANALYSIS/yt500_instrumental_abc"
DEFAULT_TRANSCRIPTS = Path("/content/yt500/transcripts")


def sha256_file(path: Path) -> str:
    return TA.sha256_file(path)


def read_json(path: Path) -> dict | None:
    return TA._read_json(path)


def write_json_atomic(path: Path, obj: dict) -> None:
    TA._write_json_atomic(path, obj)


def verified_pair(tdir: Path) -> tuple[bool, str, str | None]:
    ok, why = TA.is_complete(tdir)
    return (ok, why, sha256_file(tdir / "score.abc") if ok else None)


def gsutil(args: list[str], check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["gsutil", "-q", *args], check=check,
                          capture_output=True, text=True)


def remote_sha(uri: str) -> str | None:
    """Read the sha256 we store in object metadata (cheap idempotency check)."""
    r = subprocess.run(["gsutil", "-q", "stat", uri],
                       capture_output=True, text=True)
    if r.returncode != 0:
        return None
    for line in r.stdout.splitlines():
        line = line.strip()
        if line.lower().startswith("x-goog-meta-sha256:"):
            return line.split(":", 1)[1].strip()
    return None


def upload(uri: str, local: Path, sha: str | None = None) -> bool:
    """Upload unless the remote object already carries the same sha256."""
    sha = sha or sha256_file(local)
    if remote_sha(uri) == sha:
        return False
    gsutil(["-h", f"x-goog-meta-sha256:{sha}", "cp", str(local), uri])
    return True


def load_inventory(path: Path) -> dict[str, dict]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    rows = obj["tracks"] if isinstance(obj, dict) and "tracks" in obj else obj
    return {r["name"]: r for r in rows}


def enrich_meta(tdir: Path, name: str, inv: dict | None) -> dict:
    meta = read_json(tdir / "meta.json") or {}
    rec = inv.get(name, {}) if inv else {}
    meta.update({
        "role": "output_transcript",
        "name": name,
        "input_sha256": rec.get("input_sha256") or rec.get("sha256"),
        "input_uri": f"{DATASET}/tracks/{name}/score.abc",
        "audio_sha256": meta.get("source_wav_sha256"),
        "audio_uri": f"{DATASET}/tracks/{name}/audio.mp3",
        "output_abc": f"{name}.output.abc",
        "published_prefix": PREFIX,
    })
    return meta


def state_path(args) -> Path:
    return Path(args.state)


def load_state(path: Path) -> dict:
    return read_json(path) or {}


def cmd_push(args) -> int:
    root = Path(args.transcripts)
    prefix = args.prefix.rstrip("/")
    inv = load_inventory(Path(args.inventory)) if Path(args.inventory).is_file() else {}
    state_file = state_path(args)
    state = load_state(state_file)

    if not root.is_dir():
        print(f"push: no transcripts at {root}")
        return 0

    # 1. build deterministic archives for every complete transcript directory
    report = TA.archive_transcripts(root, compression="gzip", logger=None)
    print(f"archive: {report.summary()}", flush=True)

    dirs = sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith((".", "_")))
    pushed, unchanged, bad = 0, 0, []
    publish_dir = Path(args.publish_dir)
    for tdir in dirs:
        name = tdir.name
        ok, why, abc_sha = verified_pair(tdir)
        if not ok:
            bad.append({"name": name, "reason": why})
            continue
        meta = enrich_meta(tdir, name, inv)
        meta_path = publish_dir / f"{name}.output.meta.json"
        write_json_atomic(meta_path, meta)
        meta_sha = sha256_file(meta_path)
        archive = root / f"{name}.tar.gz"
        if not archive.is_file():
            bad.append({"name": name, "reason": "archive missing after archive_transcripts"})
            continue
        arch_sha = sha256_file(archive)

        key = f"{abc_sha}:{meta_sha}:{arch_sha}"
        if state.get(name) == key and not args.force:
            unchanged += 1
            continue
        try:
            changed = upload(f"{prefix}/{name}.output.abc", tdir / "score.abc", abc_sha)
            changed |= upload(f"{prefix}/{name}.output.meta.json", meta_path, meta_sha)
            changed |= upload(f"{prefix}/archives/{name}.output-transcript.tar.gz",
                              archive, arch_sha)
        except subprocess.CalledProcessError as exc:
            bad.append({"name": name, "reason": f"upload failed: {exc.stderr.strip()[:200]}"})
            continue
        state[name] = key
        write_json_atomic(state_file, state)
        pushed += changed
        if args.verbose:
            print(f"pushed {name} ({abc_sha[:12]})", flush=True)

    # 2. archive index
    index = root / TA.INDEX_NAME
    if index.is_file():
        upload(f"{prefix}/archives/{TA.INDEX_NAME}", index)

    # 3. session logs
    session = args.session or time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    for fname in ("_driver.log", "_timings.csv", "transcribe_manifest.json"):
        f = root / fname
        if f.is_file():
            upload(f"{prefix}/sessions/{session}/{fname}", f)

    write_json_atomic(state_file, state)
    out = Path(args.report) if args.report else root / "push_report.json"
    report_obj = {"utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                  "session": session,
                  "verified_dirs": len(dirs) - len(bad), "objects_written": pushed,
                  "unchanged_tracks": unchanged, "invalid": bad}
    write_json_atomic(out, report_obj)
    print(json.dumps({k: v for k, v in report_obj.items() if k != "invalid"}))
    if bad:
        print(f"invalid/unpushed: {len(bad)} (see {out})")
    return 0 if not bad else 1


def cmd_pull(args) -> int:
    root = Path(args.transcripts)
    root.mkdir(parents=True, exist_ok=True)
    prefix = args.prefix.rstrip("/")
    flat = Path(args.flat_dir)
    if flat.exists():
        shutil.rmtree(flat)
    flat.mkdir(parents=True)

    r = gsutil(["-m", "cp", f"{prefix}/*.output.abc", f"{prefix}/*.output.meta.json",
                str(flat)], check=False)
    if r.returncode != 0:
        # gsutil returns non-zero when a wildcard has no matches; that is not
        # fatal for an empty dataset.
        print(f"pull: {r.stderr.strip()[:300]}", flush=True)
    abcs = sorted(flat.glob("*.output.abc"))
    if not abcs:
        print(json.dumps({"pulled": 0, "already_verified": 0,
                          "unverified_or_incomplete": 0}))
        return 0

    already = replaced = 0
    for abc in abcs:
        name = abc.name[: -len(".output.abc")]
        tdir = root / name
        good, _, _ = verified_pair(tdir) if tdir.is_dir() else (False, "", None)
        if good:
            already += 1
            continue
        tdir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(abc, tdir / "score.abc")
        meta = flat / f"{name}.output.meta.json"
        if meta.is_file():
            m = read_json(meta) or {}
            # transcribe.py needs these exact keys at meta.json
            write_json_atomic(tdir / "meta.json", m)
        replaced += 1

    ok = bad = 0
    for tdir in sorted(p for p in root.iterdir() if p.is_dir()):
        good, _, _ = verified_pair(tdir)
        ok += good
        bad += not good
    print(json.dumps({"pulled": replaced, "already_verified": already,
                      "verified_total": ok, "unverified_or_incomplete": bad}))
    return 0


def cmd_verify(args) -> int:
    root = Path(args.transcripts)
    tx = TA.verify_all(root) if (root / TA.INDEX_NAME).is_file() else (0, 0)
    rows = []
    for tdir in sorted(p for p in root.iterdir() if p.is_dir()):
        ok, why, sha = verified_pair(tdir)
        rows.append({"name": tdir.name, "verified": ok, "reason": why,
                     "output_sha256": sha})
    report = {"utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
              "total": len(rows), "verified": sum(r["verified"] for r in rows),
              "archives_ok": tx[0], "archives_bad": tx[1], "rows": rows}
    out = Path(args.report) if args.report else root / "verify_report.json"
    write_json_atomic(out, report)
    print(json.dumps({k: report[k] for k in
                      ("total", "verified", "archives_ok", "archives_bad")}))
    return 0 if report["verified"] == report["total"] and not tx[1] else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("push", "pull", "verify"):
        p = sub.add_parser(name)
        p.add_argument("--transcripts", default=str(DEFAULT_TRANSCRIPTS))
        p.add_argument("--prefix", default=PREFIX)
        p.add_argument("--inventory", default=str(REPO / "work/yt500_abc/inventory.json"))
        p.add_argument("--state", default=str(REPO / "work/yt500_abc/sync_state.json"))
        p.add_argument("--publish-dir", default=str(REPO / "work/yt500_abc/publish"))
        p.add_argument("--flat-dir", default="/content/yt500/.pull_flat")
        p.add_argument("--report", default=None)
        p.add_argument("--session", default=None)
        p.add_argument("--verbose", action="store_true")
        p.add_argument("--force", action="store_true")
    args = ap.parse_args(argv)
    return {"push": cmd_push, "pull": cmd_pull, "verify": cmd_verify}[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
