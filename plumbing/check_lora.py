#!/usr/bin/env python3
"""Validate a YuE2 AR or NAR LoRA safetensors header before a GPU run.

The runtime (audio.cpp) loads A/B adapters from a safetensors state dict. A
wrong file (AR vs NAR, ComfyUI fused layout, truncated download) otherwise
only fails after the model is loaded, which costs minutes. This reads the
header only.

AR layout: 28 layers x self_attn.{q,k,v,o}_proj + mlp.{gate,up,down}_proj,
           lora_A + lora_B (392 tensors).
NAR layout: the same with nar_self_attn / nar_mlp (392 tensors), plus full
           replacement weights for vae2llm / llm2vae (4 tensors) = 396.

Usage:
    python3 plumbing/check_lora.py path/to/adapter.safetensors \
        --kind ar --expect-rank 64
    python3 plumbing/check_lora.py path/to/nar_adapter.safetensors \
        --kind nar --expect-rank 32
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
NAR_BLOCKS = {
    "nar_self_attn": ("q_proj", "k_proj", "v_proj", "o_proj"),
    "nar_mlp": ("gate_proj", "up_proj", "down_proj"),
}
NAR_IO_KEYS = {"vae2llm.weight", "vae2llm.bias", "llm2vae.weight", "llm2vae.bias"}


def expected_keys(kind: str = "ar") -> set[str]:
    if kind not in ("ar", "nar"):
        raise ValueError("kind must be ar or nar")
    blocks = AR_BLOCKS if kind == "ar" else NAR_BLOCKS
    keys = {
        f"layers.{i}.{block}.{proj}.{ab}"
        for i in range(LAYERS)
        for block, projections in blocks.items()
        for proj in projections
        for ab in ("lora_A", "lora_B")
    }
    if kind == "nar":
        keys |= NAR_IO_KEYS
    return keys


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


def validate(metadata: dict, tensors: dict, expect_rank: int | None = None,
             kind: str = "ar") -> tuple[list[str], int | None, int]:
    """Return (problems, rank, layer_count)."""
    problems: list[str] = []
    expected = expected_keys(kind)
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
    cli.add_argument("--kind", choices=("ar", "nar"), default="ar")
    cli.add_argument("--expect-rank", type=int, default=None)
    args = cli.parse_args()

    try:
        metadata, tensors = read_header(args.path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 2

    problems, rank, layer_count = validate(
        metadata, tensors, args.expect_rank, args.kind)
    print(
        f"{args.path}: {len(tensors)} tensors, {layer_count} layers, "
        f"rank {rank}, kind {args.kind}"
    )
    if metadata:
        wanted = {k: metadata[k] for k in
                  ("intended_cot", "rank", "base_model", "pair_with")
                  if k in metadata}
        if wanted:
            print("metadata:", json.dumps(wanted, ensure_ascii=False))
    if problems:
        for problem in problems:
            print(f"FAIL: {problem}", file=sys.stderr)
        return 1
    print(f"OK: YuE2 {args.kind.upper()} LoRA header")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
