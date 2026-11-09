#!/usr/bin/env python3
"""Unit tests for plumbing/audio_export.py. No network, no real GCS."""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
import wave
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "plumbing"))

import audio_export  # noqa: E402
import transcribe  # noqa: E402

HAVE_FFMPEG = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


def make_wav(path: Path, seconds: float = 0.5, fill: int = 0) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(8000)
        frame = bytes([fill % 256, (fill + 1) % 256])
        w.writeframes(frame * int(8000 * seconds))
    return path


def write_time(wav: Path, status: int = 0) -> Path:
    path = wav.with_name(f"{wav.stem}_time.txt")
    path.write_text(f"Exit status: {status}\n", encoding="utf-8")
    return path


class Base(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.tmp = Path(self.tmpdir.name)
        self.run_dir = self.tmp / "run"
        self.run_dir.mkdir()
        self.cache = self.tmp / "cache"

    def take(self, name: str = "song_1", *, seconds: float = 0.5,
             fill: int = 0, finished: bool = True) -> Path:
        wav = make_wav(self.run_dir / f"{name}.wav", seconds=seconds, fill=fill)
        if finished:
            write_time(wav)
        return wav


class TakeTests(Base):
    def test_finished_requires_exit_zero(self):
        wav = self.take()
        self.assertEqual(audio_export.is_finished_take(wav)[0], True)
        write_time(wav, status=1)
        self.assertEqual(audio_export.is_finished_take(wav)[0], False)

    def test_missing_time_file_is_not_finished(self):
        wav = self.take(finished=False)
        ok, reason = audio_export.is_finished_take(wav)
        self.assertFalse(ok)
        self.assertIn("time.txt", reason)

    def test_find_wavs_is_top_level_only(self):
        self.take("root_1")
        nested = self.run_dir / "derived"
        nested.mkdir()
        make_wav(nested / "nested_1.wav")
        self.assertEqual([p.name for p in audio_export.find_wavs(self.run_dir)],
                         ["root_1.wav"])


class PolicyTests(Base):
    def test_missing_policy_defaults_to_mp3(self):
        policy = audio_export.read_policy(self.run_dir)
        self.assertEqual(policy.audio, "mp3")
        self.assertEqual(policy.takes, ())

    def test_wav_policy_round_trip(self):
        audio_export.write_policy(self.run_dir, "wav", ["a_1"], "final")
        policy = audio_export.read_policy(self.run_dir)
        self.assertEqual(policy.audio, "wav")
        self.assertEqual(policy.takes, ("a_1",))
        self.assertEqual(policy.reason, "final")

    def test_malformed_policy_raises(self):
        (self.run_dir / audio_export.POLICY_NAME).write_text(
            json.dumps({"audio": "flac"}), encoding="utf-8")
        with self.assertRaises(audio_export.PolicyError):
            audio_export.read_policy(self.run_dir)

    def test_bad_bitrate_rejected(self):
        with self.assertRaises(audio_export.AudioExportError):
            audio_export.validate_bitrate("192")

    def test_cache_lives_outside_the_run(self):
        wav = self.take()
        mp3 = audio_export.mp3_cache_path(self.cache, self.run_dir, wav)
        self.assertNotEqual(mp3.parent, self.run_dir)
        self.assertEqual(mp3.suffix, ".mp3")
        self.assertNotIn(str(self.run_dir), str(mp3.parent))
        self.assertTrue(mp3.name.startswith("song_1"))


class ExportTests(Base):
    def test_default_policy_exports_mp3_only(self):
        self.take("a_1")
        self.take("b_2")
        with mock.patch.object(audio_export, "ensure_mp3",
                               side_effect=lambda *a, **k: audio_export.Mp3Result(
                                   a[1], k.get("mp3", self.tmp / "x.mp3"),
                                   "cached")) as fake:
            report = audio_export.export_run(
                self.run_dir, self.cache, require_finished=True)
        self.assertEqual(report.policy.audio, "mp3")
        self.assertEqual(len(report.mp3s), 2)
        self.assertEqual(report.wavs, [])
        self.assertEqual(fake.call_count, 2)

    def test_production_take_keeps_wav_and_mp3s_the_rest(self):
        self.take("a_1")
        self.take("b_2")
        audio_export.write_policy(self.run_dir, "wav", ["a_1"])
        with mock.patch.object(audio_export, "ensure_mp3",
                               side_effect=lambda run, wav, *a, **k:
                               audio_export.Mp3Result(wav, self.tmp / "x.mp3",
                                                      "cached")):
            report = audio_export.export_run(
                self.run_dir, self.cache, require_finished=True)
        self.assertEqual([p.name for p in report.wavs], ["a_1.wav"])
        self.assertEqual(len(report.mp3s), 1)

    def test_unfinished_take_is_skipped(self):
        self.take("a_1", finished=False)
        report = audio_export.export_run(
            self.run_dir, self.cache, require_finished=True)
        self.assertEqual(report.mp3s, [])
        self.assertEqual(len(report.skipped), 1)

    def test_unverified_flag_accepts_restored_wav(self):
        self.take("a_1", finished=False)
        with mock.patch.object(audio_export, "ensure_mp3",
                               side_effect=lambda run, wav, *a, **k:
                               audio_export.Mp3Result(wav, self.tmp / "x.mp3",
                                                      "cached")):
            report = audio_export.export_run(
                self.run_dir, self.cache, require_finished=False)
        self.assertEqual(len(report.mp3s), 1)

    def test_encode_failure_falls_back_to_wav(self):
        wav = self.take("a_1")
        with mock.patch.object(audio_export, "ensure_mp3",
                               side_effect=audio_export.AudioExportError("no ffmpeg")):
            report = audio_export.export_run(
                self.run_dir, self.cache, require_finished=True)
        self.assertEqual(report.mp3s, [])
        self.assertEqual(report.fallbacks, [wav])
        self.assertEqual(len(report.errors), 1)


@unittest.skipUnless(HAVE_FFMPEG, "ffmpeg/ffprobe not installed")
class EncodeTests(Base):
    def test_mp3_is_created_verified_and_reused(self):
        wav = self.take("a_1", seconds=0.5)
        result = audio_export.ensure_mp3(self.run_dir, wav, self.cache,
                                         "128k")
        self.assertEqual(result.status, "created")
        self.assertTrue(result.mp3.is_file())
        self.assertGreater(result.mp3.stat().st_size, 0)
        self.assertGreater(result.mp3_sha256 and len(result.mp3_sha256), 0)
        # No second ffmpeg call on an unchanged source.
        with mock.patch.object(audio_export, "_run_command",
                               side_effect=AssertionError("must not re-encode")):
            again = audio_export.ensure_mp3(self.run_dir, wav, self.cache,
                                            "128k")
        self.assertEqual(again.status, "cached")
        self.assertEqual(again.mp3, result.mp3)

    def test_changed_source_reencodes(self):
        wav = self.take("a_1", seconds=0.5, fill=0)
        first = audio_export.ensure_mp3(self.run_dir, wav, self.cache, "128k")
        make_wav(wav, seconds=0.5, fill=100)
        second = audio_export.ensure_mp3(self.run_dir, wav, self.cache, "128k")
        self.assertEqual(second.status, "created")
        self.assertNotEqual(first.source_sha256, second.source_sha256)

    def test_dry_run_writes_nothing(self):
        wav = self.take("a_1")
        result = audio_export.ensure_mp3(self.run_dir, wav, self.cache,
                                         "128k", dry_run=True)
        self.assertEqual(result.status, "planned")
        self.assertFalse(result.mp3.exists())

    def test_corrupt_mp3_is_rejected(self):
        wav = self.take("a_1")
        with mock.patch.object(audio_export, "_run_command") as run:
            # Simulate ffmpeg succeeding but writing an empty file.
            run.side_effect = lambda cmd, **kw: Path(cmd[-1]).write_bytes(b"")
            with self.assertRaises(audio_export.AudioExportError):
                audio_export.ensure_mp3(self.run_dir, wav, self.cache, "128k")
        mp3 = audio_export.mp3_cache_path(self.cache, self.run_dir, wav)
        self.assertFalse(mp3.exists())

    def test_index_records_wav_size_not_mp3_size(self):
        wav = self.take("a_1", seconds=0.5)
        audio_export.ensure_mp3(self.run_dir, wav, self.cache, "128k")
        path = audio_export.cache_index_path(self.cache, self.run_dir)
        entry = json.loads(path.read_text(encoding="utf-8"))["takes"]["a_1.wav"]
        self.assertEqual(entry["source_bytes"], wav.stat().st_size)
        self.assertNotEqual(entry["source_bytes"], entry["mp3_bytes"])

    def test_derived_mp3_never_lands_in_run_dir(self):
        wav = self.take("a_1")
        audio_export.ensure_mp3(self.run_dir, wav, self.cache, "128k")
        self.assertEqual([p.name for p in self.run_dir.glob("*.mp3")], [])

    def test_transcribe_does_not_discover_cached_mp3(self):
        wav = self.take("a_1")
        cached = audio_export.mp3_cache_path(self.cache, self.run_dir, wav)
        cached.parent.mkdir(parents=True, exist_ok=True)
        cached.write_bytes(b"mp3")
        found = transcribe.expand_tracks([self.run_dir], recursive=True,
                                         exclude=None)
        self.assertEqual(found, [wav])


if __name__ == "__main__":
    unittest.main()
