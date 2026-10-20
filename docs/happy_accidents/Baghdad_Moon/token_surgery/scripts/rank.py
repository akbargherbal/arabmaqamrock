#!/usr/bin/env python3
"""Aggregate evaluate.py outputs into a ranked table.

Usage:
    python3 rank.py RUN_DIR [--out RUN_DIR/rank.md]

Reads RUN_DIR/<id>/eval.json (written by evaluate.py) and prints/writes a table
with the CTC verdicts for both error windows plus waveform/mel similarity.
Ranking is heuristic and only meant to order candidates for listening; the final
choice is by ear.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import unicodedata

DIACRITICS = re.compile(r"[\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06ed\u0640]")
NON_ARABIC = re.compile(r"[^\u0621-\u064a]")


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s or "")
    s = DIACRITICS.sub("", s)
    s = s.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    s = s.replace("ة", "ه").replace("ى", "ي")
    return NON_ARABIC.sub("", s)


def verdict_e1(text: str) -> str:
    """Original mis-sings عَلِيمْ (ends م). Fix should end ه."""
    n = norm(text)
    if not n:
        return "?"
    if n.endswith("ه"):
        return "FIXED(ه)"
    if n.endswith("م"):
        return "BAD(م)"
    return "other:" + n[-2:]


def verdict_e2(text: str) -> str:
    """Original mis-sings بِأَنَّ (starts ب). Fix should start ف."""
    n = norm(text)
    if not n:
        return "?"
    if n.startswith("ف"):
        return "FIXED(ف)"
    if n.startswith("ب"):
        return "BAD(ب)"
    return "other:" + n[:2]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    rows = []
    for name in sorted(os.listdir(a.run_dir)):
        p = os.path.join(a.run_dir, name, "eval.json")
        if not os.path.isfile(p):
            continue
        d = json.load(open(p, encoding="utf-8"))
        ctc = d.get("ctc", {})
        sim = d.get("similarity", {})
        f0 = d.get("f0", {})
        rows.append({
            "id": name,
            "e1": ctc.get("e1", {}).get("greedy", ""),
            "e2": ctc.get("e2", {}).get("greedy", ""),
            "v1": verdict_e1(ctc.get("e1", {}).get("greedy", "")),
            "v2": verdict_e2(ctc.get("e2", {}).get("greedy", "")),
            "corr": sim.get("overall_corr"),
            "mean5": sim.get("mean_5s_corr"),
            "worst5": sim.get("worst_5s_window_corr"),
            "mel_out": sim.get("mel_mean_abs_db_outside_edits"),
            "mel_in": sim.get("mel_mean_abs_db_inside_edits"),
            "f0_1": f0.get("e1", {}).get("median_hz"),
            "f0_2": f0.get("e2", {}).get("median_hz"),
        })

    def score(r):
        return (r["v1"].startswith("FIXED"), r["v2"].startswith("FIXED"),
                -(r["mel_out"] if r["mel_out"] is not None else 1e9))

    rows.sort(key=score, reverse=True)

    lines = ["| id | e1 CTC | e1 | e2 CTC | e2 | corr | mean5s | worst5s | melΔ out | melΔ in | f0 e1/e2 |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(
            f"| {r['id']} | `{r['e1']}` | {r['v1']} | `{r['e2']}` | {r['v2']} | "
            f"{r['corr']} | {r['mean5']} | {r['worst5']} | {r['mel_out']} | {r['mel_in']} | "
            f"{r['f0_1']}/{r['f0_2']} |")
    table = "\n".join(lines)
    print(table)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(table + "\n")
        print(f"\nwrote {a.out}")


if __name__ == "__main__":
    main()
