#!/usr/bin/env python3
"""Convert native YuE2/SheetSage2 scores to instrumental form (Vocal -> Ins).

This is the batch wrapper around the official YuE2 `instrumentalize.py` helper
(vendored in `plumbing/yue2_instrumental/`). It implements the official
instrumental workflow:

  * every Vocal note is moved to Ins;
  * Vocal keeps only rests and chord symbols;
  * original Ins notes are kept unless they overlap a Vocal note (Vocal wins).

Usage:
    python3 plumbing/instrumentalize_scores.py scores/fadhl_shaker/*.abc \
        --out-dir scores/fadhl_shaker_instrumental

Each input `<slug>.abc` becomes `<out-dir>/<slug>.abc` plus a JSON report in
`<out-dir>/reports/<slug>.json`. The source score is never modified.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "yue2_instrumental"))

from instrumentalize import convert_score  # noqa: E402

# SheetSage2 can emit section labels the official converter does not know. A
# trailing "silence" marker is just an outro for conditioning purposes; map it
# instead of refusing the whole score. Recorded in every report.
SECTION_ALIASES = {"silence": "outro"}


def normalize_section_labels(text: str) -> tuple[str, list[str]]:
    changes: list[str] = []
    lines = []
    for line in text.splitlines():
        if line.startswith("% "):
            label = line[2:].strip()
            if label in SECTION_ALIASES:
                new = SECTION_ALIASES[label]
                changes.append(f"% {label} -> % {new}")
                line = f"% {new}"
        lines.append(line)
    return "\n".join(lines) + ("\n" if text.endswith("\n") else ""), changes


def main() -> int:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("inputs", nargs="+", type=Path,
                     help="native score.abc files (or a single directory)")
    cli.add_argument("--out-dir", required=True, type=Path)
    cli.add_argument("--overlap", choices=("vocal", "error"), default="vocal",
                     help="vocal priority on overlap (default) or fail")
    cli.add_argument("--drop-chords", action="store_true",
                     help="do not keep chord symbols on the Vocal staff")
    args = cli.parse_args()

    paths: list[Path] = []
    for item in args.inputs:
        if item.is_dir():
            paths.extend(sorted(item.glob("*.abc")))
        else:
            paths.append(item)
    if not paths:
        cli.error("no .abc inputs found")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    reports = args.out_dir / "reports"
    reports.mkdir(exist_ok=True)

    failures = 0
    for src in paths:
        try:
            text = src.read_text(encoding="utf-8")
            text, changes = normalize_section_labels(text)
            converted, check = convert_score(
                text, overlap=args.overlap, keep_chords=not args.drop_chords)
            if changes:
                check = dict(check, section_normalizations=changes)
            dst = args.out_dir / f"{src.stem}.abc"
            dst.write_text(converted, encoding="utf-8")
            (reports / f"{src.stem}.json").write_text(
                json.dumps(check, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8")
            print(
                f"{src.name:28} -> {dst.name:28} "
                f"vocal={check['vocal_notes_before']:4} "
                f"ins={check['original_ins_notes']:4} "
                f"out={check['output_ins_notes']:4} "
                f"overlap={len(check['affected_ins_notes']):3}"
                + (f"  normalized={len(changes)}" if changes else ""))
        except Exception as exc:  # noqa: BLE001 - report every file, keep going
            failures += 1
            print(f"{src.name:28} FAILED: {type(exc).__name__}: {exc}",
                  file=sys.stderr)
    if failures:
        print(f"{failures} file(s) failed", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
