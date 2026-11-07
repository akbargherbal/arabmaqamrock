#!/usr/bin/env python3
"""Validate a YuE2 AR LoRA safetensors header before a GPU run.

The runtime (audio.cpp) loads A/B adapters from a safetensors state dict. A
wrong file (NAR adapter, ComfyUI fused layout, truncated download) otherwise
only fails after the model is loaded, which costs minutes. This reads the
header only and checks the YuE2 AR layout:

  * 28 layers, layers 0..27;
  * self_attn.{q,k,v,o}_proj and mlp.{gate,up,down}_proj, lora_A + lora_B;
  * one rank across every lora_A.

Usage:
    python3 plumbing/check_lora.py path/to/adapter.safetensors [--expect-rank 64]
"""
from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path

LAYERS = 28
AR_BLOCKS = {
    "self_attn": ("q_proj", "k_proj", "v_proj", "o_proj"),
    "mlp": ("gate_proj", "up_proj", "down_proj"),
}


def expected_keys() -> set[str]:
    return {
        f"layers.{i}.{block}.{proj}.{ab}"
        for i in range(LAYERS)
        for block, projections in AR_BLOCKS.items()
        for proj in projections
        for ab in ("lora_A", "lora_B")
    }


def read_header(path: Path) -> tuple[dict, dict]:
    """Return (metadata, tensor header) without reading tensor data."""
    with Path(path).open("rb") as stream:
        raw = stream.read(8)
        if len(raw) != 8:
            raise ValueError("not a safetensors file: missing 8-byte header length")
        length = struct.unpack("<Q", raw)[0]
        if length <= 0 or length > 100 * 1024 * 1024:
            raise ValueError(f"implausible safetensors header length: {length}")
        header = json.loads(stream.read(length))
    metadata = header.pop("__metadata__", {}) or {}
    return metadata, header


def validate(metadata: dict, tensors: dict, expect_rank: int | None = None
             ) -> tuple[list[str], int | None, int]:
    """Return (problems, rank, layer_count)."""
    problems: list[str] = []
    expected = expected_keys()
    missing = sorted(expected - set(tensors))
    extra = sorted(set(tensors) - expected)
    if missing:
        problems.append(f"missing {len(missing)} keys, e.g. {missing[:3]}")
    if extra:
        problems.append(f"unexpected {len(extra)} keys, e.g. {extra[:3]}")

    layers = sorted({
        int(key.split(".")[1])
        for key in tensors
        if key.startswith("layers.") and len(key.split(".")) > 1
        and key.split(".")[1].isdigit()
    })
    if layers != list(range(LAYERS)):
        problems.append(
            f"layers {layers[:3]}..{layers[-3:]} (expected 0..{LAYERS - 1})"
        )

    ranks = {
        value.get("shape", [None])[0]
        for key, value in tensors.items()
        if key.endswith(".lora_A")
    }
    rank = next(iter(ranks)) if len(ranks) == 1 else None
    if len(ranks) != 1:
        problems.append(f"mixed ranks: {sorted(r for r in ranks if r is not None)}")
    if expect_rank is not None and rank != expect_rank:
        problems.append(f"rank {rank} (expected {expect_rank})")

    return problems, rank, len(layers)


def main() -> int:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("path", type=Path)
    cli.add_argument("--expect-rank", type=int, default=None)
    args = cli.parse_args()

    try:
        metadata, tensors = read_header(args.path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 2

    problems, rank, layer_count = validate(metadata, tensors, args.expect_rank)
    print(
        f"{args.path}: {len(tensors)} tensors, {layer_count} layers, "
        f"rank {rank}"
    )
    if metadata:
        wanted = {k: metadata[k] for k in ("intended_cot", "rank", "base_model")
                  if k in metadata}
        if wanted:
            print("metadata:", json.dumps(wanted, ensure_ascii=False))
    if problems:
        for problem in problems:
            print(f"FAIL: {problem}", file=sys.stderr)
        return 1
    print("OK: YuE2 AR LoRA header")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
