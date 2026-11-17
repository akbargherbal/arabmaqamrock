#!/usr/bin/env python3
"""Describe how much score-conditioned vocal the ABC asks for vs the lyrics.

This is the static half of the diagnosis: before any ASR, compare

  * the 95th-percentile lyric duration fit (duration_cap.py),
  * the parsed ABC duration (generate.abc_duration_s),
  * the number of vocal blocks in the ABC that actually contain notes,
  * the number of Arabic lyric lines.

A score whose sung-vocal budget is much larger than the lyric block count gives
the model nothing to sing after the last line; the observed failure mode is that
it repeats that line until the score's vocal phrases are consumed.

Usage:
    python3 analyze_score_gap.py manifests/*.json --out score_gap.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from duration_cap import arabic_letters, duration_cap  # noqa: E402
from generate import _abc_bar_units, _frac, abc_duration_s  # noqa: E402

TAG = re.compile(r"\[[^\]]*\]")
ARABIC = re.compile(r"[\u0621-\u064a]")


def parse_abc_vocal(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    unit = meter = tempo = None
    voice = None
    section = "pre"
    blocks: list[tuple[str, float, bool]] = []

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("%"):
            section = line
            continue
        if line.startswith("L:"):
            unit = _frac(line[2:])
            continue
        if line.startswith("M:"):
            meter = _frac(line[2:])
            continue
        if line.startswith("Q:"):
            m = re.search(r"=\s*(\d+)", line)
            tempo = int(m.group(1)) if m else tempo
            continue
        if line.startswith("V:"):
            voice = line[2:].split()[0]
            continue
        if re.match(r"^[A-Za-z]:", line):
            continue

        notes = re.sub(r'"[^"]*"', "", line)  # chord symbols are not notes
        dur = 0.0
        for bar in line.split("|"):
            bar = bar.strip()
            if not bar:
                continue
            m = re.fullmatch(r"([Zz])(\d*)", bar)
            if m:
                dur += meter * (int(m.group(2)) if m.group(2) else 1)
            else:
                units = _abc_bar_units(bar, unit)
                dur += units if units is not None else 0.0
        if voice == "Vocal" and unit and meter and tempo:
            blocks.append((section, dur * 4 * 60 / tempo,
                           bool(re.search(r"[A-Ga-g]", notes))))

    sung = [b for b in blocks if b[2]]
    return {
        "score_s": round(abc_duration_s(text), 2) if abc_duration_s(text) else None,
        "score_vocal_blocks": len(blocks),
        "score_sung_blocks": len(sung),
        "score_sung_s": round(sum(b[1] for b in sung), 1),
        "score_total_vocal_s": round(sum(b[1] for b in blocks), 1),
    }


def lyric_lines(text: str) -> int:
    body = TAG.sub("", text)
    return sum(1 for line in body.splitlines() if ARABIC.search(line))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("manifests", nargs="+", type=Path)
    ap.add_argument("--out", type=Path, default=Path("score_gap.csv"))
    args = ap.parse_args()

    rows = []
    for manifest in args.manifests:
        data = json.loads(manifest.read_text(encoding="utf-8"))
        base = Path(data.get("base_dir", "."))
        if not base.is_absolute():
            base = (manifest.parent / base).resolve()
        for song in data.get("songs", []):
            lyrics = song.get("lyrics")
            if lyrics is None and song.get("lyrics_file"):
                lyrics = (base / song["lyrics_file"]).read_text(encoding="utf-8")
            if lyrics is None:
                continue
            score_ref = song.get("abc_file") or song.get("score")
            if not score_ref:
                continue
            score = (base / score_ref).resolve()
            n_letters = arabic_letters(lyrics)
            _, fit_s, fit_cap, _ = duration_cap(n_letters, 0.95)
            stats = parse_abc_vocal(score)
            lines = lyric_lines(lyrics)
            rows.append({
                "manifest": manifest.name,
                "song": song.get("name"),
                "n_letters": n_letters,
                "lyric_lines": lines,
                "lyric_fit_s": fit_s,
                "lyric_fit_cap": fit_cap,
                **stats,
                "score_minus_fit_s": round((stats["score_s"] or 0) - fit_s, 1),
                "sung_blocks_per_lyric_line": round(
                    stats["score_sung_blocks"] / lines, 2) if lines else None,
                "score_sung_s_per_letter": round(
                    stats["score_sung_s"] / n_letters, 3) if n_letters else None,
            })

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    for r in rows:
        print(f"{r['manifest']:28s} {r['song']:8s} score={r['score_s']:6.1f}s "
              f"fit={r['lyric_fit_s']:3.0f}s gap={r['score_minus_fit_s']:+6.1f}s "
              f"vocal_blocks={r['score_sung_blocks']:2d} lines={r['lyric_lines']:2d} "
              f"ratio={r['sung_blocks_per_lyric_line']}")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
