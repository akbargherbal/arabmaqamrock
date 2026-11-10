#!/usr/bin/env python3
"""Offline tests for the unattended YT500 supervisor."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "plumbing"))

import supervise_yt500_generation as sup  # noqa: E402


class ParsePendingTest(unittest.TestCase):
    def test_reads_the_driver_status_line(self):
        text = ("reading metadata: gs://bucket/runs\n"
                "corpus       489\n"
                "gcs done     12   (1 session runs)\n"
                "pending      477\n"
                "mismatches   0\n")
        self.assertEqual(sup.parse_pending(text), 477)

    def test_missing_line_is_none(self):
        self.assertIsNone(sup.parse_pending("traceback\n"))


class StallTest(unittest.TestCase):
    def test_progress_resets(self):
        self.assertEqual(sup.advance_stall(2, 477, 430), 0)

    def test_same_count_stalls(self):
        self.assertEqual(sup.advance_stall(0, 477, 477), 1)

    def test_unknown_after_stalls(self):
        self.assertEqual(sup.advance_stall(1, 477, None), 2)


class MarkerTest(unittest.TestCase):
    def test_marker_is_single_line_and_parseable(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "done.txt"
            sup.write_marker(path, exit_code=0, pending=0,
                             mode="batch", attempts=3)
            text = path.read_text()
            self.assertIn("exit=0", text)
            self.assertIn("pending=0", text)
            self.assertEqual(len(text.strip().splitlines()), 1)


if __name__ == "__main__":
    unittest.main()


class SupervisorLoopTest(unittest.TestCase):
    def test_progress_continues_until_pending_zero(self):
        from unittest import mock
        statuses = [(3, ""), (3, ""), (2, ""), (2, ""), (2, ""), (0, "")]
        runs = []

        def fake_status(_driver):
            return statuses.pop(0)

        def fake_run(*_args):
            runs.append(1)
            return 0

        with tempfile.TemporaryDirectory() as td:
            marker = Path(td) / "done.txt"
            with mock.patch.object(sup, "ensure_backup", lambda: None), \
                    mock.patch.object(sup, "status", fake_status), \
                    mock.patch.object(sup, "run_driver", fake_run), \
                    mock.patch.object(sup, "flush_backup", lambda: 0), \
                    mock.patch.object(sup.time, "sleep", lambda _s: None):
                rc = sup.main([
                    "--interval", "0",
                    "--status-json", str(Path(td) / "status.json"),
                    "--marker", str(marker),
                ])
            self.assertEqual(rc, 0)
            self.assertEqual(len(runs), 3)
            self.assertIn("exit=0", marker.read_text())

    def test_bounded_stall_exits_two(self):
        from unittest import mock

        def fake_status(_driver):
            return 3, ""

        with tempfile.TemporaryDirectory() as td:
            marker = Path(td) / "done.txt"
            with mock.patch.object(sup, "ensure_backup", lambda: None), \
                    mock.patch.object(sup, "status", fake_status), \
                    mock.patch.object(sup, "run_driver", lambda *_: 0), \
                    mock.patch.object(sup, "flush_backup", lambda: 0), \
                    mock.patch.object(sup.time, "sleep", lambda _s: None):
                rc = sup.main([
                    "--interval", "0",
                    "--stall-attempts", "2",
                    "--no-fallback",
                    "--status-json", str(Path(td) / "status.json"),
                    "--marker", str(marker),
                ])
            self.assertEqual(rc, 2)
            self.assertIn("exit=2", marker.read_text())
