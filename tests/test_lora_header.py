#!/usr/bin/env python3
"""Tests for the YuE2 AR LoRA header validator."""
from __future__ import annotations

import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "plumbing"))

import check_lora  # noqa: E402


def synthetic_header(rank: int = 64) -> dict:
    tensors = {}
    for key in check_lora.expected_keys():
        first = rank if key.endswith(".lora_A") else 2
        tensors[key] = {"dtype": "BF16", "shape": [first, 2],
                        "data_offsets": [0, 0]}
    return tensors


def write_header(path: Path, tensors: dict, metadata: dict | None = None) -> None:
    header = {"__metadata__": metadata or {}, **tensors}
    blob = json.dumps(header).encode("utf-8")
    path.write_bytes(struct.pack("<Q", len(blob)) + blob)


class LoraHeader(unittest.TestCase):
    def test_valid_ar_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "adapter.safetensors"
            write_header(path, synthetic_header(), {"intended_cot": "full",
                                                    "rank": "64"})
            metadata, tensors = check_lora.read_header(path)
            problems, rank, layers = check_lora.validate(
                metadata, tensors, expect_rank=64)
            self.assertEqual(problems, [])
            self.assertEqual(rank, 64)
            self.assertEqual(layers, 28)
            self.assertEqual(metadata["intended_cot"], "full")

    def test_missing_key_is_reported(self):
        tensors = synthetic_header()
        tensors.pop(next(iter(tensors)))
        problems, _, _ = check_lora.validate({}, tensors)
        self.assertTrue(any("missing" in p for p in problems))

    def test_wrong_rank_is_reported(self):
        problems, rank, _ = check_lora.validate({}, synthetic_header(64),
                                                expect_rank=32)
        self.assertEqual(rank, 64)
        self.assertTrue(any("expected 32" in p for p in problems))

    def test_short_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "broken.safetensors"
            path.write_bytes(b"\x01\x02")
            with self.assertRaises(ValueError):
                check_lora.read_header(path)


if __name__ == "__main__":
    unittest.main()
