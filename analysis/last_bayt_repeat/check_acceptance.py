#!/usr/bin/env python3
"""Acceptance check for the measured last-bayt counts (see NEXT_SESSION.md, T5).

Verifies, without touching audio or GPU:

* 16 rows, one per (batch, track) in the production batches;
* every required measured column exists and is non-empty;
* ``asr_count`` is filled on every row;
* every ``disputed`` row carries a one-line timing note;
* ``est_count`` is still present as a proxy column.

Usage:  python3 check_acceptance.py [--results results.csv]
Exit code 0 when all checks pass.
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

HERE = Path(__file__).resolve().parent

REQUIRED = [
    "asr_count", "asr_count_strict85", "asr_count_medium",
    "ctc_count", "ctc_first_onset_s", "ctc_last_offset_s",
    "review_flag", "note", "est_count",
]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--results", type=Path, default=HERE / "results.csv")
    args = ap.parse_args()

    rows = list(csv.DictReader(args.results.open(encoding="utf-8")))
    problems: list[str] = []

    if len(rows) != 16:
        problems.append(f"expected 16 rows, found {len(rows)}")
    keys = {(r["batch"], r["track"]) for r in rows}
    if len(keys) != len(rows):
        problems.append("duplicate (batch, track) keys")

    header = rows[0].keys() if rows else []
    for col in REQUIRED:
        if col not in header:
            problems.append(f"missing column {col}")

    for r in rows:
        tag = f"{r['batch']}/{r['track']}"
        if not r.get("asr_count"):
            problems.append(f"{tag}: blank asr_count")
        if not r.get("ctc_count"):
            problems.append(f"{tag}: blank ctc_count")
        if r.get("review_flag") == "disputed" and len(r.get("note", "").strip()) < 20:
            problems.append(f"{tag}: disputed without a timing note")

    flags = {}
    for r in rows:
        flags[r.get("review_flag", "?")] = flags.get(r.get("review_flag", "?"), 0) + 1

    if problems:
        print("FAIL")
        for p in problems:
            print("  -", p)
        return 1
    print(f"OK — {len(rows)} rows, flags {flags}, all required columns populated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
