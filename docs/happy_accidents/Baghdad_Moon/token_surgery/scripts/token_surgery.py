#!/usr/bin/env python3
"""Generate length-preserving semantic-token splices for Baghdad Moon B.

Every output is exactly 5397 frames, so it can be rendered with
    semantic_prefix_file=<file> semantic_min_tokens=5397 semantic_max_tokens=5397
and the NAR/VAE sees the same timeline as the original take.

Donor windows are from docs/happy_accidents/Baghdad_Moon/token_surgery/HANDOFF.md
sections 3, 7.2 and 7.3. A/C windows are approximate (+-5 frames).

Usage:
    python3 token_surgery.py [--out runs/token_surgery/tokens]

Each output file is a flat JSON array of ints in [0, 32768), 25 fps.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BASELINE = os.path.join(HERE, "runs/baseline_semantic/semantic.json")
A_PATH = os.path.join(HERE, "runs/variants_semantic/A_4161609852/semantic.json")
C_PATH = os.path.join(HERE, "runs/variants_semantic/C_927142839/semantic.json")

EXPECTED_FRAMES = 5397
EXPECTED_BASELINE_SHA = "1b1aa3e26ed81f07323e18a2c48ccff0d4fa72b7f6ebad6447705ba28d481b59"

# --- error windows (frames) -------------------------------------------------
E1 = (3933, 3964)   # Verse 2 "عَلِيمْ" (wrong) -> 31 frames
E2 = (5056, 5114)   # Outro  "بِأَنَّ" (wrong)  -> 58 frames

# --- donors (frames) --------------------------------------------------------
D_B_OUTRO_E1 = (5025, 5056)   # same take, correct عَلَيْهِ, 31 frames
D_B_V2_E2 = (3962, 3988)      # same take, correct فَإِنَّ, 26 frames
D_A_V2_E1 = (4148, 4163)      # variant A, 15 frames
D_A_OUTRO_E2 = (5533, 5546)   # variant A, 13 frames
D_C_V2_E1 = (4396, 4412)      # variant C, 16 frames
D_C_OUTRO_E2 = (5898, 5911)   # variant C, 13 frames


def load(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def stretch(seq, n):
    """Nearest-neighbour resample a token window to exactly n frames."""
    if n <= 0:
        raise ValueError("n must be positive")
    if len(seq) == n:
        return list(seq)
    if len(seq) == 1:
        return [seq[0]] * n
    return [seq[min(len(seq) - 1, (i * len(seq)) // n)] for i in range(n)]


def splice(tokens, window, donor):
    """Replace tokens[start:end] with donor, keeping total length fixed."""
    start, end = window
    n = end - start
    if len(donor) != n:
        donor = stretch(donor, n)
    out = list(tokens)
    out[start:end] = donor
    assert len(out) == len(tokens), "splice must be length-preserving"
    return out


def changed(tokens, base):
    idx = [i for i, (a, b) in enumerate(zip(tokens, base)) if a != b]
    if not idx:
        return {"count": 0}
    return {"count": len(idx), "first": idx[0], "last": idx[-1]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "runs/token_surgery/tokens"))
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    b = load(BASELINE)
    a = load(A_PATH)
    c = load(C_PATH)

    if len(b) != EXPECTED_FRAMES:
        sys.exit(f"baseline is {len(b)} frames, expected {EXPECTED_FRAMES}")
    bsha = sha256_file(BASELINE)
    if bsha != EXPECTED_BASELINE_SHA:
        sys.exit(f"baseline sha256 {bsha} != expected {EXPECTED_BASELINE_SHA}")

    def win(t, r):
        return t[r[0]:r[1]]

    # error-2 sub-windows: onset-only (13 frames) and whole word (26 frames)
    E2_ONSET = (E2[0], E2[0] + 13)          # [5056, 5069)
    E2_WORD = (E2[0], E2[0] + 26)           # [5056, 5082)
    D_B_V2_ONSET = (D_B_V2_E2[0], D_B_V2_E2[0] + 13)   # [3962, 3975)

    def apply_e1(tokens, name):
        if name == "e1_A_note":
            return splice(tokens, (E1[1] - 8, E1[1]), win(b, (D_B_OUTRO_E1[1] - 8, D_B_OUTRO_E1[1])))
        if name == "e1_B_word":
            return splice(tokens, E1, win(b, D_B_OUTRO_E1))
        if name == "e1_C_A":
            return splice(tokens, E1, win(a, D_A_V2_E1))   # 15 -> 31 resampled
        if name == "e1_C_C":
            return splice(tokens, E1, win(c, D_C_V2_E1))   # 16 -> 31 resampled
        raise KeyError(name)

    def apply_e2(tokens, name):
        if name == "e2_A_onset":
            return splice(tokens, E2_ONSET, win(b, D_B_V2_ONSET))
        if name == "e2_B_word":
            return splice(tokens, E2_WORD, win(b, D_B_V2_E2))
        if name == "e2_A_onset_C":
            return splice(tokens, E2_ONSET, win(c, D_C_OUTRO_E2))
        if name == "e2_A_onset_A":
            return splice(tokens, E2_ONSET, win(a, D_A_OUTRO_E2))
        raise KeyError(name)

    variants = {}
    for name in ("e1_A_note", "e1_B_word", "e1_C_A", "e1_C_C"):
        variants[name] = apply_e1(b, name)
    for name in ("e2_A_onset", "e2_B_word", "e2_A_onset_C", "e2_A_onset_A"):
        variants[name] = apply_e2(b, name)

    # combined (HANDOFF 7.4): apply the e1 fix, then the e2 fix, same stream
    for e1_name in ("e1_A_note", "e1_B_word"):
        for e2_name in ("e2_A_onset", "e2_B_word"):
            variants[f"combo_{e1_name}__{e2_name}"] = apply_e2(apply_e1(b, e1_name), e2_name)
    variants["combo_e1_B_word__e2_A_onset_C"] = apply_e2(apply_e1(b, "e1_B_word"), "e2_A_onset_C")

    manifest = {
        "baseline": {
            "path": os.path.relpath(BASELINE, HERE),
            "frames": len(b),
            "sha256": bsha,
        },
        "frame_rate": 25,
        "variants": {},
    }

    # baseline copy for convenience (same bytes)
    base_out = os.path.join(args.out, "tokens_baseline.json")
    with open(base_out, "w", encoding="utf-8") as f:
        json.dump(b, f)
    manifest["baseline"]["copy"] = os.path.basename(base_out)
    manifest["baseline"]["copy_sha256"] = sha256_file(base_out)

    for name, toks in sorted(variants.items()):
        assert len(toks) == EXPECTED_FRAMES
        assert all(isinstance(x, int) and 0 <= x < 32768 for x in toks), name
        path = os.path.join(args.out, f"tokens_{name}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(toks, f)
        ch = changed(toks, b)
        manifest["variants"][name] = {
            "file": os.path.basename(path),
            "frames": len(toks),
            "sha256": sha256_file(path),
            "changed_frames": ch.get("count", 0),
            "changed_first": ch.get("first"),
            "changed_last": ch.get("last"),
        }
        print(f"{name:34s} frames={len(toks)} changed={ch.get('count', 0):3d} "
              f"[{ch.get('first')}..{ch.get('last')}]  {manifest['variants'][name]['sha256'][:12]}")

    mpath = os.path.join(args.out, "manifest.json")
    with open(mpath, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print(f"\nwrote {len(variants) + 1} token files + manifest to {args.out}")


if __name__ == "__main__":
    main()
