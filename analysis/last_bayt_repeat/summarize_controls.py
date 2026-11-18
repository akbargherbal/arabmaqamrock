#!/usr/bin/env python3
"""Compare last-bayt repeat counts across batches with one instrument.

The 16 HAC takes were rendered with `cot=full` + an external ABC score +
`cap=9000`.  Everything else in the repo was rendered with `cot=off` and no
score (508 of 970 manifest entries; ``generate.py`` refuses an ABC without a
CoT mode, so `abc_file` is not an independent switch).  This script puts the
two groups on the **same** counter — faster-whisper `small`, word timestamps,
Demucs vocal stem, fuzzy match of the last sung bayt — so the only thing that
differs between the groups is the generation recipe.

Inputs (produced by ``count_last_bayt_words.py --run-dir`` over a directory of
stem symlinks, see ``NEXT_SESSION.md``):

    work/asr_OFF_small.csv    imru al-qais, 5 maqamat x 3 adapters, cot=off
    work/asr_WOLF_small.csv   al-shanfara wolf grid, cot=off
    work/asr_KURD_small.csv   ibn zuraiq kurd grid, cot=off
    analysis/last_bayt_repeat/results.csv   the 16 HAC takes (cot=full)

Usage
-----
    python3 summarize_controls.py --out work/controls_vs_hac.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import statistics
from collections import Counter
from pathlib import Path

CONTROLS = {
    "OFF": Path("work/asr_OFF_small.csv"),
    "WOLF": Path("work/asr_WOLF_small.csv"),
    "KURD": Path("work/asr_KURD_small.csv"),
}


def load(path: Path) -> list[dict]:
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    for r in rows:
        r["count"] = int(float(r["occurrences"]))
        r["count85"] = int(float(r["occurrences_strict85"]))
        r["times"] = [round(o["start"], 1) for o in json.loads(r["occurrence_times"])]
    return rows


def describe(name: str, counts: list[int]) -> str:
    return (f"{name:14s} n={len(counts):2d}  mean={statistics.mean(counts):4.2f}  "
            f"median={statistics.median(counts):4.1f}  range={min(counts)}-{max(counts)}  "
            f"dist={dict(sorted(Counter(counts).items()))}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--hac-results", type=Path,
                    default=Path("analysis/last_bayt_repeat/results.csv"))
    ap.add_argument("--out", type=Path, default=Path("work/controls_vs_hac.csv"))
    args = ap.parse_args()

    out_rows = []
    groups: dict[str, list[int]] = {}
    for name, path in CONTROLS.items():
        if not path.exists():
            print(f"skip {name}: {path} missing")
            continue
        rows = load(path)
        groups[name] = [r["count"] for r in rows]
        for r in rows:
            out_rows.append({
                "group": "control", "batch": name, "track": r["track"],
                "cot": r.get("cot") or "off", "abc": bool(r.get("abc_file")),
                "duration_s": r["duration_s"], "count": r["count"],
                "count85": r["count85"], "times": json.dumps(r["times"]),
            })

    hac = list(csv.DictReader(args.hac_results.open(encoding="utf-8")))
    hac_counts = [int(float(r["asr_count"])) for r in hac]
    groups["HAC"] = hac_counts
    for r in hac:
        out_rows.append({
            "group": "hac", "batch": r["batch"], "track": r["track"],
            "cot": r["cot"], "abc": bool(r["abc_file"]),
            "duration_s": r["audio_duration_s"], "count": int(float(r["asr_count"])),
            "count85": int(float(r["asr_count_strict85"])),
            "times": r["ctc_onsets_s"],
        })

    print("One instrument (Whisper small, word timestamps, vocal stem):\n")
    for name, counts in groups.items():
        print("  " + describe(name, counts))

    control = [c for n in CONTROLS if n in groups for c in groups[n]]
    print(f"\n  controls pooled: mean={statistics.mean(control):.2f} "
          f"max={max(control)}  tracks>2: {sum(1 for c in control if c > 2)}/{len(control)}")
    print(f"  HAC:             mean={statistics.mean(hac_counts):.2f} "
          f"min={min(hac_counts)}  tracks>2: {sum(1 for c in hac_counts if c > 2)}/{len(hac_counts)}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out_rows[0]))
        w.writeheader()
        w.writerows(out_rows)
    print(f"\nwrote {args.out} ({len(out_rows)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
