#!/usr/bin/env python3
"""Unit tests for the upload policy in plumbing/backup_to_gcp.py."""
from __future__ import annotations

import argparse
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "plumbing"))

import audio_export  # noqa: E402
import backup_to_gcp  # noqa: E402


def make_args(**overrides) -> argparse.Namespace:
    values = dict(
        gsutil="gsutil", dry_run=True, exclude=[], audio_upload="mp3",
        mp3_bitrate="192k", mp3_cache="/tmp/mp3-cache",
        transcode_unverified=False, legacy_transcripts=False,
        compression="gzip", require_run_manifest=False,
    )
    values.update(overrides)
    return argparse.Namespace(**values)


class ExcludeTests(unittest.TestCase):
    def test_default_excludes_wav_and_raw_transcripts(self):
        args = make_args()
        self.assertEqual(
            backup_to_gcp.run_excludes(args, compress_transcripts=True),
            [backup_to_gcp.WAV_EXCLUDE, backup_to_gcp.TRANSCRIPT_RAW_EXCLUDE])

    def test_legacy_transcripts_keeps_wav_exclude(self):
        args = make_args(legacy_transcripts=True)
        self.assertEqual(
            backup_to_gcp.run_excludes(args, compress_transcripts=True),
            [backup_to_gcp.WAV_EXCLUDE])

    def test_wav_upload_keeps_only_transcript_exclude(self):
        args = make_args(audio_upload="wav")
        self.assertEqual(
            backup_to_gcp.run_excludes(args, compress_transcripts=True),
            [backup_to_gcp.TRANSCRIPT_RAW_EXCLUDE])

    def test_archive_failure_disables_transcript_exclude(self):
        args = make_args()
        self.assertEqual(
            backup_to_gcp.run_excludes(args, compress_transcripts=False),
            [backup_to_gcp.WAV_EXCLUDE])


class RootDetectionTests(unittest.TestCase):
    def test_run_root_with_wav(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run = root / "run"
            run.mkdir()
            (run / "take_1.wav").write_bytes(b"x")
            self.assertTrue(backup_to_gcp.is_runs_root(root))

    def test_plain_folder_is_not_a_run_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "notes.txt").write_text("x")
            self.assertFalse(backup_to_gcp.is_runs_root(root))


class SyncRunTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.tmp = Path(self.tmpdir.name)
        self.run_dir = self.tmp / "run"
        self.run_dir.mkdir()
        self.cache = self.tmp / "cache"
        self.cache.mkdir()

    def test_default_syncs_non_wav_then_cache(self):
        args = make_args(mp3_cache=str(self.cache))
        (self.cache / "take_1.mp3").write_bytes(b"mp3")
        report = audio_export.ExportReport(
            run_dir=self.run_dir,
            policy=audio_export.UploadPolicy(),
            mp3s=[self.cache / "take_1.mp3"],
        )
        calls = []

        def fake_sync(src, dst, *a, **kw):
            calls.append((Path(src), list(kw.get("exclude", []))))
            return True

        with mock.patch.object(backup_to_gcp, "export_run", return_value=report), \
             mock.patch.object(backup_to_gcp, "sync", side_effect=fake_sync), \
             mock.patch.object(backup_to_gcp, "cache_run_dir",
                               return_value=self.cache):
            ok = backup_to_gcp.sync_run(
                self.run_dir, "gs://b/runs/run", args, mock.Mock(),
                compress_transcripts=True)
        self.assertTrue(ok)
        self.assertEqual(len(calls), 2)
        self.assertIn(backup_to_gcp.WAV_EXCLUDE, calls[0][1])
        self.assertIn(backup_to_gcp.TRANSCRIPT_RAW_EXCLUDE, calls[0][1])
        self.assertEqual(calls[1][0], self.cache)

    def test_selected_wav_is_copied(self):
        args = make_args(mp3_cache=str(self.cache))
        wav = self.run_dir / "take_1.wav"
        wav.write_bytes(b"x")
        report = audio_export.ExportReport(
            run_dir=self.run_dir,
            policy=audio_export.UploadPolicy(audio="wav", takes=("take_1",)),
            wavs=[wav],
        )
        copied = []
        with mock.patch.object(backup_to_gcp, "export_run", return_value=report), \
             mock.patch.object(backup_to_gcp, "sync", return_value=True), \
             mock.patch.object(backup_to_gcp, "cache_run_dir",
                               return_value=self.cache), \
             mock.patch.object(backup_to_gcp, "copy_file",
                               side_effect=lambda src, dst, *a, **k:
                               copied.append(Path(src)) or True):
            backup_to_gcp.sync_run(
                self.run_dir, "gs://b/runs/run", args, mock.Mock(),
                compress_transcripts=True)
        self.assertEqual(copied, [wav])

    def test_policy_error_falls_back_to_legacy_sync(self):
        args = make_args()
        calls = []
        with mock.patch.object(backup_to_gcp, "export_run",
                               side_effect=audio_export.PolicyError("bad")), \
             mock.patch.object(backup_to_gcp, "sync",
                               side_effect=lambda *a, **k:
                               calls.append(k.get("exclude")) or True):
            ok = backup_to_gcp.sync_run(
                self.run_dir, "gs://b/runs/run", args, mock.Mock(),
                compress_transcripts=True)
        self.assertTrue(ok)
        self.assertEqual(calls, [None])


if __name__ == "__main__":
    unittest.main()
