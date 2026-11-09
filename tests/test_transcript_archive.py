#!/usr/bin/env python3
"""Unit tests for plumbing/transcript_archive.py. No network, no GCS."""
from __future__ import annotations

import hashlib
import json
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "plumbing"))

import transcript_archive  # noqa: E402

ABC = "X:1\nT:test\nM:4/4\nL:1/4\nK:D\nD E F G|\n"


def make_take(transcripts: Path, stem: str, *, status: str = "ok",
              abc: str = ABC, hash_ok: bool = True) -> Path:
    tdir = transcripts / stem
    tdir.mkdir(parents=True)
    (tdir / "score.abc").write_text(abc, encoding="utf-8")
    digest = hashlib.sha256(abc.encode("utf-8")).hexdigest()
    (tdir / "meta.json").write_text(json.dumps({
        "status": status,
        "abc_sha256": digest if hash_ok else "0" * 64,
    }), encoding="utf-8")
    (tdir / "events.json").write_text('{"events": []}\n', encoding="utf-8")
    (tdir / "melody_vocal.lab").write_text("0.0 1.0 note\n", encoding="utf-8")
    return tdir


class Base(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.tmp = Path(self.tmpdir.name)
        self.transcripts = self.tmp / "transcripts"
        self.transcripts.mkdir()


class CompletionTests(Base):
    def test_complete_take(self):
        tdir = make_take(self.transcripts, "song_1")
        self.assertEqual(transcript_archive.is_complete(tdir), (True, "ok"))

    def test_failed_status(self):
        tdir = make_take(self.transcripts, "song_1", status="failed")
        ok, reason = transcript_archive.is_complete(tdir)
        self.assertFalse(ok)
        self.assertIn("failed", reason)

    def test_hash_mismatch(self):
        tdir = make_take(self.transcripts, "song_1", hash_ok=False)
        ok, reason = transcript_archive.is_complete(tdir)
        self.assertFalse(ok)
        self.assertIn("abc_sha256", reason)

    def test_missing_abc(self):
        tdir = make_take(self.transcripts, "song_1")
        (tdir / "score.abc").unlink()
        self.assertFalse(transcript_archive.is_complete(tdir)[0])


class ArchiveTests(Base):
    def test_archive_round_trip(self):
        tdir = make_take(self.transcripts, "song_1")
        dest = self.transcripts / "song_1.tar.gz"
        entry = transcript_archive.build_archive(tdir, dest)
        self.assertTrue(dest.is_file())
        self.assertEqual(entry.archive, "song_1.tar.gz")
        self.assertTrue(transcript_archive.verify_archive(tdir, dest, entry))

        extract = self.tmp / "extract"
        extract.mkdir()
        with tarfile.open(dest, "r:*") as tar:
            tar.extractall(extract, filter="data")
        restored = extract / "song_1"
        self.assertEqual(
            {p.relative_to(restored): p.read_bytes()
             for p in restored.rglob("*") if p.is_file()},
            {p.relative_to(tdir): p.read_bytes()
             for p in tdir.rglob("*") if p.is_file()})

    def test_archive_is_deterministic(self):
        tdir = make_take(self.transcripts, "song_1")
        a = self.transcripts / "a.tar.gz"
        b = self.transcripts / "b.tar.gz"
        transcript_archive.build_archive(tdir, a)
        transcript_archive.build_archive(tdir, b)
        self.assertEqual(hashlib.sha256(a.read_bytes()).hexdigest(),
                         hashlib.sha256(b.read_bytes()).hexdigest())

    def test_verify_detects_corruption(self):
        tdir = make_take(self.transcripts, "song_1")
        dest = self.transcripts / "song_1.tar.gz"
        entry = transcript_archive.build_archive(tdir, dest)
        dest.write_bytes(dest.read_bytes()[:-16])
        self.assertFalse(transcript_archive.verify_archive(tdir, dest, entry))

    def test_incomplete_take_is_not_archived(self):
        make_take(self.transcripts, "song_1", status="failed")
        make_take(self.transcripts, "song_2")
        report = transcript_archive.archive_transcripts(self.transcripts)
        self.assertEqual(report.archived, ["song_2"])
        self.assertEqual([name for name, _ in report.skipped_incomplete],
                         ["song_1"])
        self.assertFalse((self.transcripts / "song_1.tar.gz").exists())

    def test_index_and_unchanged_shortcut(self):
        make_take(self.transcripts, "song_1")
        first = transcript_archive.archive_transcripts(self.transcripts)
        self.assertEqual(first.archived, ["song_1"])
        self.assertTrue((self.transcripts / "_archive_index.json").is_file())
        second = transcript_archive.archive_transcripts(self.transcripts)
        self.assertEqual(second.archived, [])
        self.assertEqual(second.skipped_unchanged, ["song_1"])

    def test_changed_take_rebuilds(self):
        tdir = make_take(self.transcripts, "song_1")
        transcript_archive.archive_transcripts(self.transcripts)
        (tdir / "events.json").write_text('{"events": [1]}\n', encoding="utf-8")
        again = transcript_archive.archive_transcripts(self.transcripts)
        self.assertEqual(again.archived, ["song_1"])

    def test_dry_run_writes_nothing(self):
        make_take(self.transcripts, "song_1")
        report = transcript_archive.archive_transcripts(
            self.transcripts, dry_run=True)
        self.assertEqual(report.would_archive, ["song_1"])
        self.assertFalse((self.transcripts / "song_1.tar.gz").exists())
        self.assertFalse((self.transcripts / "_archive_index.json").exists())

    def test_manifest_gate(self):
        make_take(self.transcripts, "song_1")
        make_take(self.transcripts, "song_2")
        (self.transcripts / "transcribe_manifest.json").write_text(json.dumps({
            "n_failed": 1,
            "tracks": [
                {"stem": "song_1", "status": "ok"},
                {"stem": "song_2", "status": "failed"},
            ],
        }), encoding="utf-8")
        report = transcript_archive.archive_transcripts(
            self.transcripts, require_run_manifest=True)
        self.assertEqual(report.archived, ["song_1"])
        self.assertEqual([name for name, _ in report.skipped_incomplete],
                         ["song_2"])

    def test_manifest_gate_missing_blocks(self):
        make_take(self.transcripts, "song_1")
        report = transcript_archive.archive_transcripts(
            self.transcripts, require_run_manifest=True)
        self.assertIn("transcribe_manifest.json", report.blocked_reason or "")
        self.assertEqual(report.archived, [])

    def test_xz_round_trip(self):
        tdir = make_take(self.transcripts, "song_1")
        dest = self.transcripts / "song_1.tar.xz"
        entry = transcript_archive.build_archive(tdir, dest, "xz")
        self.assertTrue(transcript_archive.verify_archive(tdir, dest, entry))


if __name__ == "__main__":
    unittest.main()
