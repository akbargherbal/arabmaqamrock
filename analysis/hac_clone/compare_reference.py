#!/usr/bin/env python3
"""Score a take against the reference it is supposed to clone.

The repeat count answers "how many times", but a clone also has to *place* the
song where the reference puts it. This compares a candidate's karaoke
`words.json` with the reference's, word by word (both are aligned to the same
lyric text, so index i is the same word in both).

Reported per take:

``dur``          duration (s)
``pace``         slope of our_start ≈ pace · ref_start + offset, fitted on the
                 first 85 % of the words. 1.00 = the reference's tempo,
                 0.86 = 14 % faster (so the text runs out early)
``landmark_s``   signed drift at word 85 % — how many seconds early/late we are
                 when the text is nearly finished; negative = early
``text_s``       end of the last word before the repeated bayt (the landmark)
``tail_s``       duration − text_s: what fills the end (cadence, loop, silence)

Usage
-----
    python3 compare_reference.py \
        --reference /content/hac_01.words.json \
        --candidates /tmp/opencode/karaokeA --glob '*hac_01*' \
        --out ../../work/clone_fit.csv
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def load(path: Path) -> dict:
    d = json.loads(path.read_text(encoding="utf-8"))
    return {"duration": float(d["duration_s"]), "words": d["words"]}


def fit_pace(ref: list[dict], cand: list[dict], frac: float = 0.85) -> tuple[float, float]:
    """Least-squares slope/offset of candidate start times against reference."""
    limit = frac * ref[-1]["start"]
    xs = [a["start"] for a in ref if a["start"] <= limit]
    ys = [b["start"] for b in cand[:len(xs)]]
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    den = sum((x - mx) ** 2 for x in xs)
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den if den else float("nan")
    return slope, my - slope * mx


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--reference", type=Path, required=True)
    ap.add_argument("--candidates", type=Path, required=True,
                    help="a words.json, or a directory of them")
    ap.add_argument("--glob", default="*.words.json")
    ap.add_argument("--landmark-frac", type=float, default=0.85,
                    help="which fraction of the reference timeline to report drift at")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()

    ref = load(args.reference)
    if args.candidates.is_dir():
        files = sorted(args.candidates.glob(args.glob))
    else:
        files = [args.candidates]
    if not files:
        raise SystemExit(f"no candidate words.json under {args.candidates}")

    rows = []
    for f in files:
        cand = load(f)
        if len(cand["words"]) != len(ref["words"]):
            print(f"skip {f.name}: {len(cand['words'])} words vs {len(ref['words'])}")
            continue
        pace, offset = fit_pace(ref["words"], cand["words"], args.landmark_frac)
        # landmark = the word at --landmark-frac of the reference's last start
        lm = next(i for i, w in enumerate(ref["words"])
                  if w["start"] >= args.landmark_frac * ref["words"][-1]["start"])
        drift = cand["words"][lm]["start"] - ref["words"][lm]["start"]
        text_s = cand["words"][lm]["end"]
        rows.append({
            "take": f.name.replace(".words.json", ""),
            "dur": round(cand["duration"], 2),
            "dur_ref": round(ref["duration"], 2),
            "pace": round(pace, 3),
            "offset_s": round(offset, 2),
            "landmark_word": ref["words"][lm]["word"],
            "landmark_s": round(drift, 2),
            "text_s": round(text_s, 2),
            "tail_s": round(cand["duration"] - text_s, 2),
        })

    rows.sort(key=lambda r: (abs(r["landmark_s"]), abs(1 - r["pace"])))
    cols = ["take", "dur", "dur_ref", "pace", "offset_s", "landmark_word",
            "landmark_s", "text_s", "tail_s"]
    w = max(len(r["take"]) for r in rows) if rows else 10
    print(f"{'take'.ljust(w)}  dur    pace   landmark_s  text_s  tail_s")
    for r in rows:
        print(f"{r['take'].ljust(w)}  {r['dur']:6.1f} {r['pace']:6.3f} "
              f"{r['landmark_s']:+9.1f}  {r['text_s']:6.1f}  {r['tail_s']:6.1f}")

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("w", newline="", encoding="utf-8") as fh:
            wri = csv.DictWriter(fh, fieldnames=cols)
            wri.writeheader()
            wri.writerows(rows)
        print(f"\nwrote {args.out} ({len(rows)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
