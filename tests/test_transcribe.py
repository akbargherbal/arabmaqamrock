#!/usr/bin/env python3
"""Unit tests for transcribe.py. No model, no network, no GPU."""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import sys
import tempfile
import unittest
import wave
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import transcribe  # noqa: E402


def make_wav(path: Path, seconds: float = 0.05, fill: int = 0) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(8000)
        frame = bytes([fill % 256, (fill + 1) % 256])
        w.writeframes(frame * int(8000 * seconds))
    return path


class FakeModel:
    def __init__(self, fail_stems: set[str] | None = None, tag: str = "one"):
        self.fail_stems = fail_stems or set()
        self.tag = tag
        self.calls: list[str] = []
        self.dtypes: list[str] = []

    def transcribe(self, src, output_dir, melody_only=True, dtype="bf16"):
        stem = Path(src).stem
        self.calls.append(stem)
        self.dtypes.append(dtype)
        if stem in self.fail_stems:
            raise RuntimeError(f"fake failure for {stem}")
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        abc = f"X:1\nT:{stem}\nK:C\nC D E F|\n% {self.tag}\n"
        (out / "score.abc").write_text(abc, encoding="utf-8")
        return {"abc": abc}


def runtime(cfg):
    return {
        "python": "test", "torch": "test", "transformers": "test",
        "device": cfg.device, "dtype": cfg.dtype, "threads": cfg.threads,
        "load_seconds": 0.0,
    }


@contextlib.contextmanager
def captured():
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        yield out, err


class Base(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.tmp = Path(self.tmpdir.name)
        self.run_dir = self.tmp / "run"
        self.run_dir.mkdir()
        self.out_dir = self.tmp / "transcripts"
        # Keep tests away from the repo-local HF module cache.
        p = mock.patch("transcribe.prepare_environment", lambda cfg: None)
        p.start()
        self.addCleanup(p.stop)

    def write(self, name: str, *, seconds: float = 0.05, fill: int = 0,
              directory: Path | None = None) -> Path:
        return make_wav((directory or self.run_dir) / name,
                        seconds=seconds, fill=fill)

    def model_patch(self, fake: FakeModel):
        return mock.patch(
            "transcribe.load_model",
            side_effect=lambda cfg: (fake, runtime(cfg)))

    def run_cli(self, *args: str) -> tuple[int, str, str]:
        with captured() as (out, err):
            rc = transcribe.main([str(a) for a in args])
        return rc, out.getvalue(), err.getvalue()


class DiscoveryTests(Base):
    def test_dry_run_lists_real_take_markers_and_writes_nothing(self):
        self.write("song_3_123.wav")
        self.write("song_2_456.wav")
        with mock.patch("transcribe.load_model",
                        side_effect=AssertionError("model must not load")):
            rc, out, _ = self.run_cli(self.run_dir, "--out-dir", self.out_dir,
                                      "--dry-run")
        self.assertEqual(rc, 0)
        self.assertIn("song_3_123.wav", out)
        self.assertIn("song_2_456.wav", out)
        self.assertFalse(self.out_dir.exists())

    def test_exclusion_is_opt_in(self):
        self.write("song_3_123.wav")
        self.write("song_4_456.wav")
        rc, out, _ = self.run_cli(self.run_dir, "--out-dir", self.out_dir,
                                  "--dry-run")
        self.assertEqual(rc, 0)
        self.assertIn("song_3_123.wav", out)

        rc, out, _ = self.run_cli(self.run_dir, "--out-dir", self.out_dir,
                                  "--exclude", r"_3_", "--dry-run")
        self.assertEqual(rc, 0)
        self.assertNotIn("song_3_123.wav", out)
        self.assertIn("song_4_456.wav", out)

    def test_unicode_and_spaces_survive(self):
        name = "03-تجرع مرارة البين_3_810750224.wav"
        self.write(name)
        rc, out, _ = self.run_cli(self.run_dir, "--out-dir", self.out_dir,
                                  "--dry-run")
        self.assertEqual(rc, 0)
        self.assertIn("03-تجرع مرارة البين_3_810750224.wav", out)

    def test_latest_pointer(self):
        run = self.tmp / "out" / "20261024-000000_demo"
        run.mkdir(parents=True)
        make_wav(run / "demo_1.wav")
        (self.tmp / "out" / "latest").write_text(str(run) + "\n", encoding="utf-8")
        with mock.patch.object(transcribe, "ROOT", self.tmp):
            rc, out, _ = self.run_cli("--dry-run")
        self.assertEqual(rc, 0)
        self.assertIn("demo_1.wav", out)
        self.assertIn(str(run / "transcripts"), out)

    def test_missing_latest_is_actionable(self):
        with mock.patch.object(transcribe, "ROOT", self.tmp):
            rc, _, err = self.run_cli("--dry-run")
        self.assertEqual(rc, 1)
        self.assertIn("out/latest", err)

    def test_dtype_defaults_to_auto(self):
        self.write("song.wav")
        rc, out, _ = self.run_cli(self.run_dir, "--dry-run")
        self.assertEqual(rc, 0)
        self.assertIn("dtype=auto", out)

    def test_duplicate_stem_default_error_and_suffix(self):
        a = self.tmp / "a"
        b = self.tmp / "b"
        make_wav(a / "same.wav")
        make_wav(b / "same.wav")
        rc, _, err = self.run_cli(a, b, "--out-dir", self.out_dir, "--dry-run")
        self.assertEqual(rc, 1)
        self.assertIn("duplicate output stem", err)

        rc, out, _ = self.run_cli(a, b, "--out-dir", self.out_dir,
                                  "--on-collision", "suffix", "--dry-run")
        self.assertEqual(rc, 0)
        self.assertIn("same", out)


class TranscribeTests(Base):
    def test_dtype_is_forwarded_and_recorded(self):
        self.write("take_dtype.wav")
        fake = FakeModel()
        with self.model_patch(fake):
            rc, out, _ = self.run_cli(self.run_dir, "--out-dir", self.out_dir,
                                      "--dtype", "fp32")
        self.assertEqual(rc, 0, out)
        self.assertEqual(fake.dtypes, ["fp32"])
        meta = json.loads(
            (self.out_dir / "take_dtype" / "meta.json").read_text())
        self.assertEqual(meta["dtype"], "fp32")

    def test_transcribe_resume_and_provenance(self):
        wav = self.write("take_1.wav")
        (self.run_dir / "batch_manifest.json").write_text(
            '{"tracks": [{"name": "take", "seed": 1}]}\n', encoding="utf-8")
        fake = FakeModel(tag="first")
        with self.model_patch(fake):
            rc, out, _ = self.run_cli(self.run_dir, "--out-dir", self.out_dir)
        self.assertEqual(rc, 0, out)
        stem = "take_1"
        abc = self.out_dir / stem / "score.abc"
        meta = json.loads((self.out_dir / stem / "meta.json").read_text())
        manifest = json.loads(
            (self.out_dir / "transcribe_manifest.json").read_text())
        timings = (self.out_dir / "_timings.csv").read_text()

        self.assertTrue(abc.is_file())
        self.assertIn("first", abc.read_text())
        self.assertEqual(meta["status"], "ok")
        self.assertEqual(meta["source_wav_sha256"],
                         hashlib.sha256(wav.read_bytes()).hexdigest())
        self.assertEqual(meta["model"], transcribe.DEFAULT_MODEL)
        self.assertEqual(meta["model_revision"], transcribe.DEFAULT_REVISION)
        self.assertEqual(manifest["n"], 1)
        self.assertEqual(manifest["n_ok"], 1)
        self.assertEqual(manifest["tracks"][0]["status"], "ok")
        self.assertIsNotNone(manifest["batch_manifest_sha256"])
        self.assertIn("take_1", timings)

        # A second run must skip, not call the model.
        fake2 = FakeModel(tag="second")
        with self.model_patch(fake2):
            rc, out, _ = self.run_cli(self.run_dir, "--out-dir", self.out_dir)
        self.assertEqual(rc, 0, out)
        self.assertEqual(fake2.calls, [])
        self.assertIn("skipped", out)
        self.assertIn("first", abc.read_text())

    def test_stale_guard_and_force(self):
        wav = self.write("take_2.wav", fill=1)
        with self.model_patch(FakeModel(tag="first")):
            rc, _, _ = self.run_cli(self.run_dir, "--out-dir", self.out_dir)
        self.assertEqual(rc, 0)
        abc = self.out_dir / "take_2" / "score.abc"
        before = abc.read_text()

        make_wav(wav, fill=2)
        fake = FakeModel(tag="second")
        with self.model_patch(fake):
            rc, out, _ = self.run_cli(self.run_dir, "--out-dir", self.out_dir)
        self.assertEqual(rc, 1)
        self.assertEqual(fake.calls, [])
        self.assertIn("STALE", out)
        self.assertEqual(abc.read_text(), before)

        fake = FakeModel(tag="forced")
        with self.model_patch(fake):
            rc, out, _ = self.run_cli(self.run_dir, "--out-dir", self.out_dir,
                                      "--force")
        self.assertEqual(rc, 0, out)
        self.assertEqual(fake.calls, ["take_2"])
        self.assertIn("forced", abc.read_text())

    def test_failed_force_run_is_retried_not_treated_as_done(self):
        wav = self.write("take_5.wav", fill=1)
        with self.model_patch(FakeModel(tag="first")):
            rc, _, _ = self.run_cli(self.run_dir, "--out-dir", self.out_dir)
        self.assertEqual(rc, 0)
        abc = self.out_dir / "take_5" / "score.abc"
        before = abc.read_text()

        make_wav(wav, fill=2)
        with self.model_patch(FakeModel(fail_stems={"take_5"})):
            rc, out, _ = self.run_cli(self.run_dir, "--out-dir", self.out_dir,
                                      "--force")
        self.assertEqual(rc, 1)
        meta = json.loads((self.out_dir / "take_5" / "meta.json").read_text())
        self.assertEqual(meta["status"], "failed")
        self.assertEqual(abc.read_text(), before)

        rc, out, _ = self.run_cli(self.run_dir, "--out-dir", self.out_dir,
                                  "--verify")
        self.assertEqual(rc, 1)
        self.assertIn("[FAILED] take_5", out)

        # The previous failed status must trigger a retry without --force.
        fake = FakeModel(tag="retry")
        with self.model_patch(fake):
            rc, out, _ = self.run_cli(self.run_dir, "--out-dir", self.out_dir)
        self.assertEqual(rc, 0, out)
        self.assertEqual(fake.calls, ["take_5"])
        self.assertIn("retry", abc.read_text())

    def test_tampered_abc_fails_verification_and_requires_force(self):
        self.write("take_6.wav")
        with self.model_patch(FakeModel(tag="first")):
            rc, _, _ = self.run_cli(self.run_dir, "--out-dir", self.out_dir)
        self.assertEqual(rc, 0)
        abc = self.out_dir / "take_6" / "score.abc"
        abc.write_text("X:1\nT:tampered\nK:C\nG A B c|\n", encoding="utf-8")

        rc, out, _ = self.run_cli(self.run_dir, "--out-dir", self.out_dir,
                                  "--verify")
        self.assertEqual(rc, 1)
        self.assertIn("[CHANGED] take_6", out)

        fake = FakeModel(tag="second")
        with self.model_patch(fake):
            rc, out, _ = self.run_cli(self.run_dir, "--out-dir", self.out_dir)
        self.assertEqual(rc, 1)
        self.assertEqual(fake.calls, [])
        self.assertIn("INVALID", out)

        fake = FakeModel(tag="forced")
        with self.model_patch(fake):
            rc, out, _ = self.run_cli(self.run_dir, "--out-dir", self.out_dir,
                                      "--force")
        self.assertEqual(rc, 0, out)
        self.assertIn("forced", abc.read_text())

    def test_missing_meta_is_unverified_skip(self):
        self.write("take_3.wav")
        with self.model_patch(FakeModel(tag="first")):
            rc, _, _ = self.run_cli(self.run_dir, "--out-dir", self.out_dir)
        self.assertEqual(rc, 0)
        (self.out_dir / "take_3" / "meta.json").unlink()

        fake = FakeModel(tag="second")
        with self.model_patch(fake):
            rc, out, _ = self.run_cli(self.run_dir, "--out-dir", self.out_dir)
        self.assertEqual(rc, 0)
        self.assertEqual(fake.calls, [])
        self.assertIn("skipped-unverified", out)
        manifest = json.loads(
            (self.out_dir / "transcribe_manifest.json").read_text())
        self.assertEqual(manifest["tracks"][0]["status"], "skipped-unverified")

    def test_failure_isolation(self):
        for name in ("a.wav", "b.wav", "c.wav"):
            self.write(name)
        fake = FakeModel(fail_stems={"b"})
        with self.model_patch(fake):
            rc, out, _ = self.run_cli(self.run_dir, "--out-dir", self.out_dir)
        self.assertEqual(rc, 1)
        self.assertEqual(fake.calls, ["a", "b", "c"])
        manifest = json.loads(
            (self.out_dir / "transcribe_manifest.json").read_text())
        statuses = {t["stem"]: t["status"] for t in manifest["tracks"]}
        self.assertEqual(statuses, {"a": "ok", "b": "failed", "c": "ok"})
        self.assertEqual(manifest["n_failed"], 1)
        self.assertTrue((self.out_dir / "a" / "score.abc").is_file())
        self.assertTrue((self.out_dir / "c" / "score.abc").is_file())

    def test_time_budget_stops_before_next_track(self):
        for name in ("a.wav", "b.wav"):
            self.write(name)
        fake = FakeModel()
        with self.model_patch(fake):
            rc, out, _ = self.run_cli(self.run_dir, "--out-dir", self.out_dir,
                                      "--time-budget", "0.0001")
        self.assertEqual(rc, 0)
        self.assertEqual(fake.calls, ["a"])
        self.assertIn("budget", out)
        manifest = json.loads(
            (self.out_dir / "transcribe_manifest.json").read_text())
        self.assertTrue(manifest["stopped_early"])
        self.assertEqual(manifest["tracks"][1]["status"], "pending")

    def test_fail_fast_stops(self):
        for name in ("a.wav", "b.wav", "c.wav"):
            self.write(name)
        fake = FakeModel(fail_stems={"b"})
        with self.model_patch(fake):
            rc, out, _ = self.run_cli(self.run_dir, "--out-dir", self.out_dir,
                                      "--fail-fast")
        self.assertEqual(rc, 1)
        self.assertEqual(fake.calls, ["a", "b"])
        self.assertIn("stopping on first failure", out)

    def test_smoke_and_limit(self):
        for name in ("a.wav", "b.wav", "c.wav"):
            self.write(name)
        fake = FakeModel()
        with self.model_patch(fake):
            rc, _, _ = self.run_cli(self.run_dir, "--out-dir", self.out_dir,
                                    "--smoke")
        self.assertEqual(rc, 0)
        self.assertEqual(fake.calls, ["a"])

        fake = FakeModel()
        with self.model_patch(fake):
            rc, _, _ = self.run_cli(self.run_dir, "--out-dir", self.out_dir,
                                    "--limit", "2", "--force")
        self.assertEqual(rc, 0)
        self.assertEqual(fake.calls, ["a", "b"])

    def test_verify_detects_stale_without_model(self):
        wav = self.write("take_4.wav", fill=1)
        with self.model_patch(FakeModel()):
            rc, _, _ = self.run_cli(self.run_dir, "--out-dir", self.out_dir)
        self.assertEqual(rc, 0)

        with mock.patch("transcribe.load_model",
                        side_effect=AssertionError("model must not load")):
            rc, out, _ = self.run_cli(self.run_dir, "--out-dir", self.out_dir,
                                      "--verify")
        self.assertEqual(rc, 0)
        self.assertIn("[OK] take_4", out)

        make_wav(wav, fill=2)
        rc, out, _ = self.run_cli(self.run_dir, "--out-dir", self.out_dir,
                                  "--verify")
        self.assertEqual(rc, 1)
        self.assertIn("[STALE] take_4", out)


class ParsingTests(Base):
    def test_doctor_needs_no_input(self):
        with mock.patch.object(transcribe, "ROOT", self.tmp):
            cfg, tracks = transcribe.parse_args(["--doctor"])
        self.assertTrue(cfg.doctor)
        self.assertEqual(tracks, [])

    def test_abc_validation(self):
        p = self.tmp / "score.abc"
        p.write_text("X:1\nT:x\nK:C\nC D E|\n", encoding="utf-8")
        self.assertTrue(transcribe.abc_is_valid(p))
        p.write_text("not abc\n", encoding="utf-8")
        self.assertFalse(transcribe.abc_is_valid(p))

    def test_read_pointer_rejects_missing_run(self):
        p = self.tmp / "latest"
        p.write_text(str(self.tmp / "nope"), encoding="utf-8")
        with self.assertRaises(transcribe.PlanError):
            transcribe.read_pointer(p)


if __name__ == "__main__":
    unittest.main()
