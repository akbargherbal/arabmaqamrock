#!/usr/bin/env python3
"""Unit tests for the adapted docs-reconciler scope and verifier.

No network, no model. Uses a temporary mini-repo so the assertions do not drift
when the project's real docs change.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "skills" / "docs-reconciler" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import claims_common  # noqa: E402
import extract_claims  # noqa: E402
import verify_claims  # noqa: E402


class ScopeTests(unittest.TestCase):
    def test_live_and_frozen_paths(self):
        excluded = claims_common.is_excluded
        self.assertFalse(excluded(Path("README.md")))
        self.assertFalse(excluded(Path("docs/base-prompt.md")))
        self.assertFalse(excluded(Path("manifests/README.md")))
        self.assertTrue(excluded(Path("manifests/fadhl_shaker_instrumental_01.md")))
        self.assertTrue(excluded(Path("docs/plans/yt500-instrumental-run-log.md")))
        self.assertTrue(excluded(Path("docs/sessions/2026-10-24_baghdad_moon_abc_guide.md")))
        self.assertTrue(excluded(Path("cases/002_abu01_ajdad/RUN3.md")))
        self.assertTrue(excluded(Path("out/2026-11-15_run/notes.md")))
        self.assertTrue(excluded(Path("plumbing/yue2_instrumental/README.md")))


class ExtractAndVerifyTests(unittest.TestCase):
    def test_scope_extraction_and_flag_verification(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text(
                "Run `--known` or `--unknown`. See `missing.md`.\n", encoding="utf-8"
            )
            (root / "tool.py").write_text(
                'parser.add_argument("--known")\n', encoding="utf-8"
            )
            (root / "docs" / "plans").mkdir(parents=True)
            (root / "docs" / "plans" / "old.md").write_text(
                "Frozen: `frozen-only.md`\n", encoding="utf-8"
            )
            (root / "manifests").mkdir()
            (root / "manifests" / "README.md").write_text(
                "Live index\n", encoding="utf-8"
            )
            (root / "manifests" / "run.md").write_text(
                "Frozen: `run-only.md`\n", encoding="utf-8"
            )

            payload = extract_claims.extract(root)
            self.assertEqual(
                sorted(payload["files_scanned"]),
                ["README.md", "manifests/README.md"],
            )

            summary = verify_claims.verify(payload, root)
            missing = {item["raw"] for item in summary["details"]["missing_path"]}
            unknown = {item["raw"] for item in summary["details"]["unknown_flag"]}
            self.assertEqual(missing, {"missing.md"})
            self.assertEqual(unknown, {"--unknown"})
            self.assertFalse(summary["structural_warning"])


if __name__ == "__main__":
    unittest.main()
