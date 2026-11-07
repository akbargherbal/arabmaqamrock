#!/usr/bin/env python3
"""Tests for the YuE2 AR/NAR LoRA header validator."""
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


def synthetic_header(kind: str = "ar", rank: int = 64) -> dict:
    tensors = {}
    for key in check_lora.expected_keys(kind):
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
            write_header(path, synthetic_header("ar", 64),
                         {"intended_cot": "full", "rank": "64"})
            metadata, tensors = check_lora.read_header(path)
            problems, rank, layers = check_lora.validate(
                metadata, tensors, expect_rank=64, kind="ar")
            self.assertEqual(problems, [])
            self.assertEqual(rank, 64)
            self.assertEqual(layers, 28)
            self.assertEqual(len(tensors), 392)
            self.assertEqual(metadata["intended_cot"], "full")

    def test_valid_nar_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nar_adapter.safetensors"
            write_header(path, synthetic_header("nar", 32),
                         {"rank": "32", "pair_with": "tokenizer_head_joint_v9"})
            metadata, tensors = check_lora.read_header(path)
            problems, rank, layers = check_lora.validate(
                metadata, tensors, expect_rank=32, kind="nar")
            self.assertEqual(problems, [])
            self.assertEqual(rank, 32)
            self.assertEqual(layers, 28)
            self.assertEqual(len(tensors), 396)
            self.assertTrue(check_lora.NAR_IO_KEYS <= set(tensors))

    def test_ar_file_rejected_as_nar(self):
        problems, _, _ = check_lora.validate({}, synthetic_header("ar", 64),
                                             kind="nar")
        self.assertTrue(any("missing" in p for p in problems))

    def test_missing_key_is_reported(self):
        tensors = synthetic_header("ar")
        tensors.pop(next(iter(tensors)))
        problems, _, _ = check_lora.validate({}, tensors, kind="ar")
        self.assertTrue(any("missing" in p for p in problems))

    def test_wrong_rank_is_reported(self):
        problems, rank, _ = check_lora.validate(
            {}, synthetic_header("ar", 64), expect_rank=32, kind="ar")
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
