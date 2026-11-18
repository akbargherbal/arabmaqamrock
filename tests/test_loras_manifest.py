#!/usr/bin/env python3
"""Offline checks for plumbing/loras.manifest.

The table is the single source of truth for what install.sh / setup_colab.sh
stage, so a typo here costs a multi-hundred-MB download or a missing adapter.
No network, no GPU: this only parses the table and runs `--list`.
"""
from __future__ import annotations

import re
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST = REPO_ROOT / "plumbing" / "loras.manifest"
sys.path.insert(0, str(REPO_ROOT))

import generate  # noqa: E402

FIELDS = ("state", "set", "repo", "dest", "remote", "sha256")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def rows() -> list[dict[str, str]]:
    out = []
    for raw in MANIFEST.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in raw.split("\t")]
        if len(parts) != len(FIELDS):
            raise AssertionError(f"not {len(FIELDS)} tab-separated fields: {raw!r}")
        row = dict(zip(FIELDS, parts))
        if row["state"] not in {"on", "off"}:
            raise AssertionError(f"state must be on/off: {raw!r}")
        out.append(row)
    return out


class ManifestTest(unittest.TestCase):
    def test_default_stack_is_blend_a015_plus_instrumental(self):
        enabled = {r["set"] for r in rows() if r["state"] == "on"}
        self.assertEqual(enabled, {"blend-a0.15", "instrumental"})

    def test_enabled_paths_match_generate_defaults(self):
        staged = {
            (REPO_ROOT / r["dest"] / r["remote"]).resolve()
            for r in rows() if r["state"] == "on"
        }
        self.assertIn(generate.DEFAULT_LORA_AR.resolve(), staged)
        self.assertIn(generate.DEFAULT_LORA_NAR.resolve(), staged)

    def test_pins_are_sha256_or_unpinned(self):
        for row in rows():
            with self.subTest(set=row["set"], remote=row["remote"]):
                self.assertTrue(
                    row["sha256"] == "-" or SHA256_RE.match(row["sha256"]),
                    f"bad sha256 pin: {row['sha256']!r}",
                )

    def test_no_duplicate_targets(self):
        targets = [(r["dest"], r["remote"]) for r in rows()]
        self.assertEqual(len(targets), len(set(targets)))

    def test_list_prints_enabled_and_opt_in_rows(self):
        out = subprocess.run(
            ["bash", str(REPO_ROOT / "plumbing" / "fetch_loras.sh"), "--list"],
            capture_output=True, text=True, check=True,
        ).stdout
        self.assertIn("loras/blend/a0.15/v3instr_a0.15_ar.safetensors", out)
        self.assertIn("loras/arabic-instrumental/arabic-instrumental-ar.safetensors", out)
        self.assertIn("loras/arabmaqamrock-v3-ar.safetensors", out)  # opt-in, still listed


if __name__ == "__main__":
    unittest.main()
