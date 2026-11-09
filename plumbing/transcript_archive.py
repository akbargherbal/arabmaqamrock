#!/usr/bin/env python3
"""Archive finished per-song transcription directories before GCS upload.

A transcript song directory is archived only when its ``meta.json`` proves the
track finished: ``status == "ok"`` and ``sha256(score.abc)`` matches the
recorded ``abc_sha256``.  Failed, interrupted, or in-progress tracks are left
alone.

The output is one deterministic archive per song beside the source directory::

    transcripts/<take>/        local working copy, kept by default
    transcripts/<take>.tar.gz  uploaded instead of the directory
    transcripts/_archive_index.json

The archive contains ``<take>/`` as its top-level directory, so extracting it
inside ``transcripts/`` restores the original tree.

Usage::

    python plumbing/transcript_archive.py out/<run>/transcripts --dry-run
    python plumbing/transcript_archive.py out/<run>/transcripts
    python plumbing/transcript_archive.py out/<run>/transcripts --verify
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import logging
import lzma
import os
import tarfile
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

INDEX_NAME = "_archive_index.json"
TOOL = "transcript-archive/1"
DONE_STATUSES = {"ok", "skipped", "skipped-unverified"}
COMPRESSIONS = {"gzip": ".tar.gz", "xz": ".tar.xz", "none": ".tar"}

_LOG = logging.getLogger("transcript_archive")


class ArchiveError(RuntimeError):
    """A transcript directory could not be archived or verified."""


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            block = f.read(chunk)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def _log(logger: logging.Logger | None, level: str, msg: str, *args) -> None:
    (logger or _LOG).__getattribute__(level)(msg, *args)


def _read_json(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _write_json_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    os.replace(tmp, path)


def is_complete(tdir: Path) -> tuple[bool, str]:
    """Return (complete, reason) for one transcript song directory."""
    if not tdir.is_dir():
        return False, "not a directory"
    meta_path = tdir / "meta.json"
    meta = _read_json(meta_path)
    if meta is None:
        return False, "missing or invalid meta.json"
    status = meta.get("status")
    if status != "ok":
        return False, f"meta.json status is {status!r}"
    expected = meta.get("abc_sha256")
    if not expected:
        return False, "meta.json has no abc_sha256"
    abc = tdir / "score.abc"
    if not abc.is_file() or abc.stat().st_size <= 0:
        return False, "missing or empty score.abc"
    actual = sha256_file(abc)
    if actual != expected:
        return False, "score.abc does not match meta.json abc_sha256"
    return True, "ok"


def fingerprint(tdir: Path) -> str:
    """A cheap content fingerprint: names, sizes, and mtimes of the tree."""
    h = hashlib.sha256()
    for path in sorted(tdir.rglob("*")):
        rel = path.relative_to(tdir).as_posix()
        try:
            stat = path.stat()
        except OSError:
            continue
        if path.is_dir():
            h.update(f"D\0{rel}\n".encode("utf-8"))
        elif path.is_file():
            h.update(f"F\0{rel}\0{stat.st_size}\0{stat.st_mtime_ns}\n"
                     .encode("utf-8"))
    return h.hexdigest()


def _source_bytes(tdir: Path) -> int:
    total = 0
    for path in tdir.rglob("*"):
        if path.is_file():
            try:
                total += path.stat().st_size
            except OSError:
                pass
    return total


@dataclass
class ArchiveEntry:
    archive: str
    source_bytes: int
    archive_bytes: int
    file_count: int
    sha256: str
    source_fingerprint: str
    created_utc: str

    def to_dict(self) -> dict:
        return {
            "archive": self.archive,
            "source_bytes": self.source_bytes,
            "archive_bytes": self.archive_bytes,
            "ratio": round(self.archive_bytes / self.source_bytes, 3)
                     if self.source_bytes else None,
            "file_count": self.file_count,
            "sha256": self.sha256,
            "source_fingerprint": self.source_fingerprint,
            "created_utc": self.created_utc,
        }


def _open_compressed(raw, compression: str):
    if compression == "gzip":
        return gzip.GzipFile(filename="", mode="wb", compresslevel=9,
                             mtime=0, fileobj=raw)
    if compression == "xz":
        return lzma.LZMAFile(raw, mode="wb", preset=6)
    if compression == "none":
        return raw
    raise ArchiveError(f"unsupported compression: {compression!r}")


def build_archive(tdir: Path, dest: Path,
                  compression: str = "gzip",
                  logger: logging.Logger | None = None) -> ArchiveEntry:
    """Write a deterministic archive of ``tdir`` to ``dest``."""
    if compression not in COMPRESSIONS:
        raise ArchiveError(f"unsupported compression: {compression!r}")
    complete, reason = is_complete(tdir)
    if not complete:
        raise ArchiveError(f"{tdir}: not complete ({reason})")
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".tmp")
    file_count = 0
    try:
        with open(tmp, "wb") as raw:
            stream = _open_compressed(raw, compression)
            try:
                with tarfile.open(fileobj=stream, mode="w") as tar:
                    for path in sorted(tdir.rglob("*")):
                        rel = path.relative_to(tdir).as_posix()
                        arcname = f"{tdir.name}/{rel}"
                        info = tar.gettarinfo(str(path), arcname=arcname)
                        info.uid = 0
                        info.gid = 0
                        info.uname = ""
                        info.gname = ""
                        info.mtime = 0
                        if path.is_dir():
                            info.mode = 0o755
                            tar.addfile(info)
                        elif path.is_file():
                            info.mode = 0o644
                            file_count += 1
                            with open(path, "rb") as fh:
                                tar.addfile(info, fh)
            finally:
                if stream is not raw:
                    stream.close()
        if not tmp.is_file() or tmp.stat().st_size <= 0:
            raise ArchiveError(f"archive writer produced no file for {tdir}")
        os.replace(tmp, dest)
    finally:
        if tmp.exists():
            tmp.unlink()
    stat = dest.stat()
    entry = ArchiveEntry(
        archive=dest.name,
        source_bytes=_source_bytes(tdir),
        archive_bytes=stat.st_size,
        file_count=file_count,
        sha256=sha256_file(dest),
        source_fingerprint=fingerprint(tdir),
        created_utc=utcnow(),
    )
    _log(logger, "info", "archived %s -> %s (%.2f%% of source)",
         tdir.name, dest.name,
         100.0 * entry.archive_bytes / entry.source_bytes
         if entry.source_bytes else 0.0)
    return entry


def verify_archive(tdir: Path, archive: Path,
                   entry: ArchiveEntry | dict | None = None) -> bool:
    """Check that extracting ``archive`` reproduces ``tdir`` byte-for-byte."""
    try:
        if entry is not None:
            expected_sha = (entry.sha256 if isinstance(entry, ArchiveEntry)
                            else entry.get("sha256"))
            if expected_sha and sha256_file(archive) != expected_sha:
                return False
        expected: dict[str, str] = {}
        for path in tdir.rglob("*"):
            if path.is_file():
                rel = path.relative_to(tdir).as_posix()
                expected[f"{tdir.name}/{rel}"] = sha256_file(path)
        with tarfile.open(archive, mode="r:*") as tar:
            actual: dict[str, str] = {}
            for member in tar.getmembers():
                if not member.isfile():
                    continue
                fh = tar.extractfile(member)
                if fh is None:
                    return False
                h = hashlib.sha256()
                while True:
                    block = fh.read(1 << 20)
                    if not block:
                        break
                    h.update(block)
                actual[member.name] = h.hexdigest()
        return actual == expected
    except (OSError, tarfile.TarError, lzma.LZMAError, EOFError):
        return False


def _new_index(compression: str) -> dict:
    return {
        "version": 1,
        "tool": TOOL,
        "generated_utc": utcnow(),
        "compression": compression,
        "archives": {},
    }


def _load_index(path: Path, compression: str) -> dict:
    data = _read_json(path)
    if (not data
            or data.get("version") != 1
            or data.get("compression") != compression
            or not isinstance(data.get("archives"), dict)):
        return _new_index(compression)
    return data


def _archive_name(stem: str, compression: str) -> str:
    return f"{stem}{COMPRESSIONS[compression]}"


@dataclass
class ArchiveReport:
    transcripts_dir: Path
    index: dict = field(default_factory=dict)
    archived: list[str] = field(default_factory=list)
    would_archive: list[str] = field(default_factory=list)
    skipped_unchanged: list[str] = field(default_factory=list)
    skipped_incomplete: list[tuple[str, str]] = field(default_factory=list)
    failed: list[tuple[str, str]] = field(default_factory=list)
    blocked_reason: str | None = None

    def summary(self) -> str:
        return (f"archived={len(self.archived)} "
                f"planned={len(self.would_archive)} "
                f"unchanged={len(self.skipped_unchanged)} "
                f"incomplete={len(self.skipped_incomplete)} "
                f"failed={len(self.failed)}"
                + (f" blocked={self.blocked_reason}" if self.blocked_reason else ""))


def _manifest_status(transcripts_dir: Path) -> dict[str, str] | None:
    manifest = _read_json(transcripts_dir / "transcribe_manifest.json")
    if manifest is None:
        return None
    tracks = manifest.get("tracks")
    if not isinstance(tracks, list):
        return None
    out: dict[str, str] = {}
    for track in tracks:
        if isinstance(track, dict) and isinstance(track.get("stem"), str):
            out[track["stem"]] = str(track.get("status"))
    return out


def archive_transcripts(transcripts_dir: Path, *,
                        compression: str = "gzip",
                        dry_run: bool = False,
                        require_run_manifest: bool = False,
                        force: bool = False,
                        logger: logging.Logger | None = None) -> ArchiveReport:
    """Archive every complete song directory under ``transcripts_dir``."""
    if compression not in COMPRESSIONS:
        raise ArchiveError(f"unsupported compression: {compression!r}")
    report = ArchiveReport(transcripts_dir=transcripts_dir)
    if not transcripts_dir.is_dir():
        report.blocked_reason = "transcripts directory does not exist"
        return report

    manifest_status: dict[str, str] | None = None
    if require_run_manifest:
        manifest_status = _manifest_status(transcripts_dir)
        if manifest_status is None:
            report.blocked_reason = "transcribe_manifest.json missing or invalid"
            _log(logger, "warning", "%s: %s", transcripts_dir,
                 report.blocked_reason)
            return report

    index_path = transcripts_dir / INDEX_NAME
    index = _load_index(index_path, compression)
    report.index = index
    changed = not index_path.is_file()

    for child in sorted(transcripts_dir.iterdir()):
        if not child.is_dir() or child.name.startswith((".", "_")):
            continue
        if manifest_status is not None:
            status = manifest_status.get(child.name)
            if status not in DONE_STATUSES:
                report.skipped_incomplete.append(
                    (child.name, f"manifest status is {status!r}"))
                continue
        complete, reason = is_complete(child)
        if not complete:
            report.skipped_incomplete.append((child.name, reason))
            _log(logger, "info", "skip %s: %s", child.name, reason)
            continue

        archive = transcripts_dir / _archive_name(child.name, compression)
        fp = fingerprint(child)
        existing = index["archives"].get(child.name)
        if (not force and isinstance(existing, dict)
                and existing.get("source_fingerprint") == fp
                and existing.get("archive") == archive.name
                and archive.is_file()
                and archive.stat().st_size == existing.get("archive_bytes")):
            report.skipped_unchanged.append(child.name)
            continue

        if dry_run:
            report.would_archive.append(child.name)
            _log(logger, "info", "would archive %s -> %s", child.name,
                 archive.name)
            continue

        try:
            entry = build_archive(child, archive, compression, logger=logger)
        except Exception as exc:  # noqa: BLE001 - report and continue
            report.failed.append((child.name, str(exc)))
            _log(logger, "error", "archive failed for %s: %s", child.name, exc)
            continue
        index["archives"][child.name] = entry.to_dict()
        report.archived.append(child.name)
        changed = True

    if changed and not dry_run:
        index["tool"] = TOOL
        index["version"] = 1
        index["compression"] = compression
        index["generated_utc"] = utcnow()
        report.index = index
        _write_json_atomic(index_path, index)
    return report


def verify_all(transcripts_dir: Path, compression: str | None = None
               ) -> tuple[int, int]:
    """Verify every archive named by the index. Returns (ok, bad)."""
    index = _read_json(transcripts_dir / INDEX_NAME) or {}
    archives = index.get("archives", {})
    if not isinstance(archives, dict):
        archives = {}
    ok = bad = 0
    for stem, entry in sorted(archives.items()):
        if not isinstance(entry, dict):
            print(f"[BAD] {stem}: malformed index entry")
            bad += 1
            continue
        tdir = transcripts_dir / stem
        archive = transcripts_dir / str(entry.get("archive"))
        if not tdir.is_dir() or not archive.is_file():
            print(f"[MISSING] {stem}: source or archive missing")
            bad += 1
            continue
        if verify_archive(tdir, archive, entry):
            print(f"[OK] {stem}")
            ok += 1
        else:
            print(f"[BAD] {stem}: archive does not reproduce the source")
            bad += 1
    return ok, bad


def _cli(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("transcripts_dir", help="<run>/transcripts directory")
    ap.add_argument("--compression", choices=sorted(COMPRESSIONS),
                    default="gzip", help="archive compression (default: gzip)")
    ap.add_argument("--dry-run", action="store_true",
                    help="show what would be archived; write nothing")
    ap.add_argument("--force", action="store_true",
                    help="rebuild even when the fingerprint is unchanged")
    ap.add_argument("--verify", action="store_true",
                    help="verify existing archives and exit")
    ap.add_argument("--require-run-manifest", action="store_true",
                    help="require transcribe_manifest.json to list each track as done")
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    tdir = Path(args.transcripts_dir).expanduser().resolve()
    if not tdir.is_dir():
        print(f"not a directory: {tdir}", file=sys.stderr)
        return 2
    if args.verify:
        ok, bad = verify_all(tdir, args.compression)
        print(f"verify: {ok} ok, {bad} bad")
        return 0 if bad == 0 else 1
    report = archive_transcripts(
        tdir, compression=args.compression, dry_run=args.dry_run,
        require_run_manifest=args.require_run_manifest, force=args.force)
    print(report.summary())
    if report.blocked_reason:
        return 1
    return 1 if report.failed else 0


if __name__ == "__main__":
    raise SystemExit(_cli())
