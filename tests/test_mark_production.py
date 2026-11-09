#!/usr/bin/env python3
"""Unit tests for plumbing/mark_production.py."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "plumbing"))

import mark_production  # noqa: E402
from audio_export import POLICY_NAME  # noqa: E402


class MarkProductionTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.run_dir = Path(self.tmpdir.name) / "run"
        self.run_dir.mkdir()
        (self.run_dir / "a_1.wav").write_bytes(b"x")
        (self.run_dir / "b_2.wav").write_bytes(b"x")

    def policy(self) -> dict:
        return json.loads((self.run_dir / POLICY_NAME).read_text(encoding="utf-8"))

    def test_take_selection(self):
        mark_production.mark(self.run_dir, takes=["a_1"], all_takes=False,
                             reason="final", reset=False, dry_run=False)
        data = self.policy()
        self.assertEqual(data["audio"], "wav")
        self.assertEqual(data["takes"], ["a_1"])

    def test_takes_merge(self):
        mark_production.mark(self.run_dir, takes=["a_1"], all_takes=False,
                             reason=None, reset=False, dry_run=False)
        mark_production.mark(self.run_dir, takes=["b_2"], all_takes=False,
                             reason=None, reset=False, dry_run=False)
        self.assertEqual(self.policy()["takes"], ["a_1", "b_2"])

    def test_all_takes_overrides_list(self):
        mark_production.mark(self.run_dir, takes=["a_1"], all_takes=False,
                             reason=None, reset=False, dry_run=False)
        mark_production.mark(self.run_dir, takes=[], all_takes=True,
                             reason=None, reset=False, dry_run=False)
        data = self.policy()
        self.assertEqual(data["audio"], "wav")
        self.assertEqual(data["takes"], [])

    def test_reset_writes_positive_mp3_policy(self):
        mark_production.mark(self.run_dir, takes=["a_1"], all_takes=False,
                             reason=None, reset=False, dry_run=False)
        mark_production.mark(self.run_dir, takes=[], all_takes=False,
                             reason=None, reset=True, dry_run=False)
        data = self.policy()
        self.assertEqual(data["audio"], "mp3")
        self.assertEqual(data["takes"], [])

    def test_dry_run_writes_nothing(self):
        mark_production.mark(self.run_dir, takes=["a_1"], all_takes=False,
                             reason=None, reset=False, dry_run=True)
        self.assertFalse((self.run_dir / POLICY_NAME).exists())


if __name__ == "__main__":
    unittest.main()
