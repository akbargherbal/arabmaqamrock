#!/usr/bin/env python3
"""Cheap, CPU-only proxy for "how many times did the model repeat the last bayt?".

Why this exists
---------------
The ground-truth counter is ``count_last_bayt.py`` (Whisper + Arabic
normalisation + fuzzy matching).  Running Whisper on a whole batch is heavy, so
this script reads the *karaoke forced-alignment* artifacts that the pipeline
already writes (``karaoke/<track>.words.json``) and derives a proxy count from
the geometry of the final chorus.

What the alignment can and cannot tell us
-----------------------------------------
The aligner is forced to place every lyric word exactly once.  When the model
sings the same bayt several extra times, the aligner cannot create new words,
so it stretches the surrounding cues: the final chorus block becomes much
longer than the lyric sheet implies, and the last word often absorbs many
seconds of repeated audio.  The alignment therefore **cannot count repeats
directly**; it can only measure how much extra sung time sits in the final
chorus.

Proxy definition
----------------
``est_count = round(chorus_span_s / rendition_s)``

* ``chorus_span_s`` = last aligned word end - first word of the final
  contiguous chorus block.
* ``rendition_s`` = seconds per rendition of the last bayt.  Default 10.97 s,
  measured from Whisper on ``hac_01_1114111`` (7 occurrences, 250.74-328.62).
  Override with ``--rendition-s`` once more ASR rows exist.

Calibration: on ``hac_01_1114111`` this proxy gives 74.26 / 10.97 = 6.77 ->
7, matching the validated ASR count exactly.  Treat it as +/-1 on other
tracks; use it to rank takes, not to certify an exact number.

Also reported: ``last_word_ratio`` = duration of the final word / median word
duration.  Values >> 1 are the fingerprint of the aligner dumping unaligned
repeated audio onto the last word.

Output
------
``results.csv`` in the current directory (override with ``--out``), one row per
track, plus a summary table on stdout.

Usage
-----
    python3 analysis/last_bayt_repeat/measure_alignment.py \
        --karaoke-dir /tmp/opencode/karaokeA \
        --runs-dir    /tmp/opencode/hacA \
        --manifest    manifests/harith_hac_A.json \
        --batch       A \
        --out         /tmp/results_A.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
import sys
from pathlib import Path

# ``Chorus`` only as the section name; a bare substring match would also hit
# ``Pre-Chorus`` and inflate the expected count.
CHORUS_RE = re.compile(r"^\s*chorus\b|layered vocal", re.IGNORECASE)
TAG_RE = re.compile(r"^\[([^|\]]+)")
DEFAULT_RENDITION_S = 10.97

_DIACRITICS = "\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06ed\u0640"
_DIAC_RE = re.compile(f"[{_DIACRITICS}]")
_DIAC_TRANS = str.maketrans({
    "أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ى": "ي", "ئ": "ي",
    "ؤ": "و", "ة": "ه",
})


def _normalize(text: str) -> str:
    text = _DIAC_RE.sub("", text).translate(_DIAC_TRANS)
    text = re.sub(r"[^\u0621-\u064a\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


# --------------------------------------------------------------------------- #
# lyrics: how many times is the last bayt written in the input?
# --------------------------------------------------------------------------- #
def expected_chorus_renditions(lyrics: str) -> int:
    """How many times the *last sung bayt* is written in the lyric sheet.

    Counted by text, not by physical line: batch B re-breaks every phrase onto
    its own line, so a line count would report 7-14 renditions where the sheet
    only asks for 2.  The reference is the last Arabic-bearing block; we then
    count non-overlapping occurrences of it in the tag-stripped lyrics.
    """
    body = "\n".join(ln for ln in lyrics.splitlines() if not ln.strip().startswith("["))
    blocks = [b for b in re.split(r"\n\s*\n", body) if _normalize(b)]
    if not blocks:
        return 0
    ref = _normalize(blocks[-1])
    if not ref:
        return 0
    haystack = _normalize(body)
    count = 0
    pos = 0
    while True:
        hit = haystack.find(ref, pos)
        if hit < 0:
            break
        count += 1
        pos = hit + len(ref)
    return count


# --------------------------------------------------------------------------- #
# alignment geometry
# --------------------------------------------------------------------------- #
def final_chorus_block(lines: list[dict]) -> list[dict]:
    """Return the last contiguous run of chorus/layered-vocal lines."""
    if not lines:
        return []
    end = len(lines) - 1
    while end >= 0 and not CHORUS_RE.search(lines[end].get("section", "")):
        end -= 1
    if end < 0:
        return []
    start = end
    while start - 1 >= 0 and CHORUS_RE.search(lines[start - 1].get("section", "")):
        start -= 1
    return lines[start : end + 1]


def measure(words_doc: dict, rendition_s: float) -> dict:
    lines = words_doc.get("lines", [])
    words = words_doc.get("words", [])
    block = final_chorus_block(lines)
    if not block:
        return {"error": "no chorus block"}

    block_ids = {ln["i"] for ln in block}
    block_words = [w for w in words if w.get("line") in block_ids]
    if not block_words:
        return {"error": "chorus block has no aligned words"}

    chorus_start = min(w["start"] for w in block_words)
    chorus_end = max(w["end"] for w in block_words)
    span = chorus_end - chorus_start

    last_word = block_words[-1]
    last_dur = last_word["end"] - last_word["start"]

    # median duration of ordinary (non-stretched) words; ignore pauses >= 3 s
    ordinary = [w["end"] - w["start"] for w in words if 0 < w["end"] - w["start"] < 3]
    med = statistics.median(ordinary) if ordinary else 0.0

    est = span / rendition_s if rendition_s > 0 else 0.0
    return {
        "chorus_start_s": round(chorus_start, 2),
        "chorus_end_s": round(chorus_end, 2),
        "chorus_span_s": round(span, 2),
        "last_word": last_word.get("word", ""),
        "last_word_dur_s": round(last_dur, 2),
        "median_word_s": round(med, 2),
        "last_word_ratio": round(last_dur / med, 1) if med else 0.0,
        "est_rendition_s": rendition_s,
        "est_renditions": round(est, 2),
        "est_count": int(round(est)),
    }


# --------------------------------------------------------------------------- #
# batch metadata
# --------------------------------------------------------------------------- #
def load_track_meta(runs_dir: Path) -> dict[str, dict]:
    meta = {}
    if not runs_dir or not runs_dir.is_dir():
        return meta
    for path in sorted(runs_dir.glob("*.json")):
        if path.name in {"batch_manifest.json", "input.json"}:
            continue
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if "seed" in doc and "name" in doc:
            meta[f"{doc['name']}_{doc['seed']}"] = doc
    return meta


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--karaoke-dir", required=True, help="directory containing <track>.words.json")
    ap.add_argument("--runs-dir", help="run dir containing per-track <track>.json metadata")
    ap.add_argument("--manifest", help="batch manifest with inline lyrics (for expected count)")
    ap.add_argument("--batch", default="", help="batch label written to CSV")
    ap.add_argument("--rendition-s", type=float, default=DEFAULT_RENDITION_S,
                    help=f"seconds per bayt rendition (default {DEFAULT_RENDITION_S}, ASR-calibrated)")
    ap.add_argument("--asr-json", help="optional count_last_bayt JSON result to attach as ground truth")
    ap.add_argument("--score-gap", help="optional score_gap.csv to merge lyric_fit/score surplus by song")
    ap.add_argument("--out", default="results.csv", help="output CSV (default: results.csv)")
    ap.add_argument("--append", action="store_true", help="append rows to an existing CSV (skip header)")
    args = ap.parse_args(argv)

    karaoke_dir = Path(args.karaoke_dir)
    docs = sorted(karaoke_dir.glob("*.words.json"))
    if not docs:
        print(f"error: no *.words.json under {karaoke_dir}", file=sys.stderr)
        return 2

    meta = load_track_meta(Path(args.runs_dir)) if args.runs_dir else {}

    lyrics_by_song: dict[str, str] = {}
    if args.manifest:
        man = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
        for song in man.get("songs", []):
            if song.get("name") and song.get("lyrics"):
                lyrics_by_song[song["name"]] = song["lyrics"]

    asr_count = ""
    asr_reference = ""
    if args.asr_json:
        asr = json.loads(Path(args.asr_json).read_text(encoding="utf-8"))
        asr_count = asr.get("occurrences", "")
        asr_reference = Path(asr.get("audio", "")).name

    gap_by_song: dict[str, dict] = {}
    if args.score_gap:
        with Path(args.score_gap).open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                gap_by_song[row.get("song", "")] = row

    rows = []
    for path in docs:
        track = path.name[: -len(".words.json")]
        doc = json.loads(path.read_text(encoding="utf-8"))
        m = measure(doc, args.rendition_s)
        if "error" in m:
            print(f"warning: {track}: {m['error']}", file=sys.stderr)
            continue

        tm = meta.get(track, {})
        song = tm.get("name", track.rsplit("_", 1)[0])
        expected = expected_chorus_renditions(lyrics_by_song[song]) if song in lyrics_by_song else ""

        row = {
            "batch": args.batch,
            "track": track,
            "song": song,
            "seed": tm.get("seed", ""),
            "cot": tm.get("cot", ""),
            "abc_file": tm.get("abc_file", ""),
            "cap": tm.get("cap", ""),
            "truncated": tm.get("truncated", ""),
            "audio_duration_s": round(doc.get("duration_s", tm.get("wav_duration_s", 0.0)), 2),
            "score_s": tm.get("score_s", ""),
            **m,
            "expected_count": expected,
            "excess_repeats": (m["est_count"] - expected) if isinstance(expected, int) else "",
            "lyric_fit_s": gap_by_song.get(song, {}).get("lyric_fit_s", ""),
            "score_minus_fit_s": gap_by_song.get(song, {}).get("score_minus_fit_s", ""),
            "asr_count": asr_count if asr_reference == f"{track}.mp3" else "",
        }
        rows.append(row)

    if not rows:
        print("error: nothing measured", file=sys.stderr)
        return 1

    fields = list(rows[0].keys())
    out = Path(args.out)
    write_header = not (args.append and out.exists() and out.stat().st_size > 0)
    mode = "a" if args.append else "w"
    with out.open(mode, newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        if write_header:
            w.writeheader()
        w.writerows(rows)

    # console summary
    hdr = f"{'track':22} {'dur':>6} {'span':>6} {'est':>4} {'exp':>3} {'exc':>3} {'last':>7} {'ratio':>6} {'asr':>4}"
    print(hdr)
    print("-" * len(hdr))
    for r in rows:
        print(
            f"{r['track']:22} {r['audio_duration_s']:6.1f} {r['chorus_span_s']:6.1f} "
            f"{r['est_count']:4d} {str(r['expected_count']):>3} {str(r['excess_repeats']):>3} "
            f"{r['last_word_dur_s']:7.2f} {r['last_word_ratio']:6.1f} {str(r['asr_count']):>4}"
        )
    print(f"\nwrote {out} ({len(rows)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
