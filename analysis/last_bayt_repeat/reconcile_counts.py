#!/usr/bin/env python3
"""Reconcile the proxy table with the measured ASR and CTC counts.

Inputs (all produced by the analysis scripts in this directory):

* ``results.csv``            — the alignment proxy (``est_count`` and friends)
* ``../../work/asr_{A,B}_small.csv``  — word-level Whisper *small* on the vocal stem
* ``../../work/asr_{A,B}_medium.csv`` — word-level Whisper *medium* on the vocal stem
* ``../../work/ctc/ctc_summary.csv``  — CTC placement counts on the vocal stem

Output: ``results.csv`` rewritten in place with the measured columns appended,
plus a copy in ``work/results_asr_ctc.csv``.  Original proxy columns are kept
untouched; ``est_count`` stays as the (untrusted) proxy.

Column semantics
----------------
``asr_count``            Whisper-small word-level matches, fuzzy ratio >= 75
``asr_count_strict85``   same pass, fuzzy ratio >= 85
``asr_count_medium``     Whisper-medium word-level matches, ratio >= 75
``ctc_count``            CTC placements after NMS — an *upper bound*: on a
                         control take whose true count is 2, the same rule
                         returns 4, so ~1/3 of placements are false positives
``ctc_count_asr_ok``     CTC placements with a Whisper onset within 3 s — the
                         corroborated count, and the one ``review_flag`` uses
``ctc_first_onset_s``    onset of the first kept placement
``ctc_last_offset_s``    offset of the last kept placement
``review_flag``          ``agree`` if |asr_count - ctc_count| <= 1, else
                         ``disputed`` (CTC is an upper bound, so a gap means
                         "one instrument claims renditions the other missed")
``note``                 one-line timing evidence, required on disputed rows

Usage
-----
    python3 reconcile_counts.py            # rewrite results.csv
    python3 reconcile_counts.py --check     # print only
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
WORK = ROOT / "work"

MEASURED = [
    "asr_count", "asr_count_strict85", "asr_count_medium",
    "ctc_count", "ctc_count_asr_ok", "ctc_count_min", "ctc_count_max",
    "ctc_first_onset_s", "ctc_last_offset_s", "ctc_onsets_s",
    "ctc_onsets_asr_ok_s", "review_flag", "note",
]

# Hand-written evidence lines for rows where the numbers disagree or where the
# acoustics and the ear diverge.  Everything else gets an auto-generated note.
NOTES = {
    ("A", "hac_01_1114111"):
        "7 placements 250/260/274/283/296/305/314 s, identical at every window "
        "length; the 7th (314-325 s) is full-energy, so the heard '6' is the "
        "cadential reading rather than a bleed.",
    ("A", "hac_01_1212121"):
        "CTC adds two tail renditions (310.5 and 318.7 s) that both ASR passes "
        "stop short of; the first four onsets match ASR within 0.6 s.",
    ("A", "hac_02_3331333"):
        "5 placements 259/268/279/293/309 s; ASR skips 279 and 309, each sitting "
        "one ~10.7 s period after a rendition it did catch.",
    ("A", "hac_02_7772777"):
        "6 placements 258-318 s at ~11 s spacing; ASR stops at 293.5, and the "
        "proxy's 4 comes from a chorus window that starts at 269 and clips the "
        "first two renditions.",
    ("B", "hac_01_1114111"):
        "5 placements 251/260/277/295/313 s, all matched by ASR; the proxy's 7 "
        "over-reads a 71.5 s span whose last word is only 1.2 s long.",
    ("B", "hac_01_1212121"):
        "4 placements at 262/279/293/305 s; ASR's 2 hits are the middle two, so "
        "it drops the 262 s opener and the 305 s close of the run.",
    ("B", "hac_01_1616161"):
        "6 placements in 255-323 s, but this is the truncated take: the run is "
        "cut at 360 s, so the proxy's 9 is reading a stretched final word.",
    ("B", "hac_02_7772777"):
        "ASR collapses the run (1 match) and medium recovers 3; CTC places 5 at "
        "257/271/284/300/309 s, the last a short 7.2 s reprise.",
    ("B", "hac_02_7774777"):
        "6 placements 253-324 s at ~11 s spacing; ASR matches only 276 and 299, "
        "missing both ends of the run.",
}


def load_asr(path: Path, batch: str) -> dict[tuple[str, str], dict]:
    if not path.exists():
        return {}
    out = {}
    for row in csv.DictReader(path.open(encoding="utf-8")):
        out[(batch, f"{row['track']}_{row['seed']}")] = row
    return out


def load_ctc(path: Path) -> dict[tuple[str, str], dict]:
    if not path.exists():
        return {}
    out = {}
    for row in csv.DictReader(path.open(encoding="utf-8")):
        out[(row["batch"], row["track"])] = row
    return out


def auto_note(asr: int | None, ctc: int | None, onsets: list[float],
              first: float | None, last: float | None) -> str:
    if not onsets:
        return "no CTC placement survived NMS; timing unavailable."
    span = f"{onsets[0]:.1f}-{float(last):.1f} s" if last != "" else f"from {onsets[0]:.1f} s"
    return (f"CTC places {ctc} renditions in {span} "
            f"(onsets {', '.join(f'{o:.0f}' for o in onsets)}); "
            f"ASR heard {asr}.")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--results", type=Path, default=HERE / "results.csv")
    ap.add_argument("--out", type=Path, default=WORK / "results_asr_ctc.csv")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    rows = list(csv.DictReader(args.results.open(encoding="utf-8")))
    fieldnames = list(rows[0].keys())
    for col in MEASURED:
        if col not in fieldnames:
            fieldnames.append(col)
    # keep each corroborated column next to the one it qualifies
    for new, after in (("ctc_count_asr_ok", "ctc_count"),
                       ("ctc_onsets_asr_ok_s", "ctc_onsets_s")):
        if new in fieldnames:
            fieldnames.remove(new)
            fieldnames.insert(fieldnames.index(after) + 1, new)

    small = {}
    medium = {}
    for batch in ("A", "B"):
        small.update(load_asr(WORK / f"asr_{batch}_small.csv", batch))
        medium.update(load_asr(WORK / f"asr_{batch}_medium.csv", batch))
    ctc = load_ctc(WORK / "ctc" / "ctc_summary.csv")

    out_rows = []
    for row in rows:
        batch, track = row["batch"], row["track"]
        a = small.get((batch, track), {})
        m = medium.get((batch, track), {})
        c = ctc.get((batch, track), {})
        onsets = json.loads(c["ctc_onsets"]) if c.get("ctc_onsets") else []

        asr_n = int(a["occurrences"]) if a.get("occurrences") else None
        asr_s = int(a["occurrences_strict85"]) if a.get("occurrences_strict85") else None
        asr_m = int(m["occurrences"]) if m.get("occurrences") else None
        ctc_n = int(c["ctc_count"]) if c.get("ctc_count") else None

        row["asr_count"] = "" if asr_n is None else asr_n
        row["asr_count_strict85"] = "" if asr_s is None else asr_s
        row["asr_count_medium"] = "" if asr_m is None else asr_m
        row["ctc_count"] = "" if ctc_n is None else ctc_n
        stab = json.loads(c["ctc_window_stability"]) if c.get("ctc_window_stability") else {}
        row["ctc_count_min"] = min(stab.values()) if stab else ""
        row["ctc_count_max"] = max(stab.values()) if stab else ""
        row["ctc_first_onset_s"] = c.get("ctc_first_onset_s", "")
        row["ctc_last_offset_s"] = c.get("ctc_last_offset_s", "")
        row["ctc_onsets_s"] = c.get("ctc_onsets", "")

        # Corroborated count: keep only the placements Whisper also heard a bayt
        # word near.  CTC is a sensitive onset detector but not a counter — on a
        # control take with a known count of 2 it returns 4 — so the flag and the
        # report use this column, not ``ctc_count``.
        asr_times = (json.loads(a["occurrence_times"])
                     if a.get("occurrence_times") else [])
        asr_starts = [float(o["start"]) for o in asr_times if "start" in o]
        ok = [o for o in onsets if any(abs(o - s) <= 3.0 for s in asr_starts)]
        row["ctc_count_asr_ok"] = len(ok) if onsets else ""
        row["ctc_onsets_asr_ok_s"] = json.dumps(ok) if onsets else ""

        if asr_n is None or ctc_n is None:
            flag = "unmeasured"
        elif abs(asr_n - ctc_n) <= 1:
            flag = "agree"
        else:
            flag = "disputed"
        # The 6-vs-7 argument about this take is a genuine split even when the
        # two machines happen to agree on 7.
        if track == "hac_01_1114111":
            flag = "disputed"
        row["review_flag"] = flag

        note = NOTES.get((batch, track))
        if note is None and flag == "disputed":
            note = auto_note(asr_n, ctc_n, onsets, row["ctc_first_onset_s"],
                             row["ctc_last_offset_s"])
        row["note"] = note or ""
        out_rows.append(row)

    if args.check or args.out is None:
        for r in out_rows:
            print(f"{r['batch']} {r['track']:<20} asr={r['asr_count']:>2} "
                  f"strict={r['asr_count_strict85']:>2} med={r['asr_count_medium']:>2} "
                  f"ctc={r['ctc_count']:>2} est={r['est_count']:>2} {r['review_flag']:<9} {r['note'][:70]}")
        return 0

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(out_rows)
    print(f"wrote {args.out} ({len(out_rows)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
