#!/usr/bin/env python3
"""Check an ABC score against the arabmaqamrock melody specification.

Two jobs, both aimed at things a language model cannot reliably check itself:

1. **Structure** — complete bars, one voice, one metre, line/phrase budget.
2. **Originality** — longest run of identical melodic movement shared with any
   of the 177 reference tracks. "Do not copy" is only a real constraint if
   something measures it.

    ./check_abc.py score.abc --lyrics local_workspace/baghdad_moon_lyrics.txt
    ./check_abc.py score.abc --lyrics ... --corpus-dir /path/to/transcripts

Exit code 0 if every hard check passes, 1 otherwise. Warnings do not fail.
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "datasets" / "five_stars"))

from measure import abc as abcmod  # noqa: E402

VOWEL_MARKS = "\u064e\u064f\u0650\u064b\u064c\u064d\u0670"
MAX_LEAP = 7
LEAP_ALLOWANCE_PER_SECTION = 1
BUDGET_TOLERANCE = 0.10
ORIGINALITY_K = 8


MUSIC_LINE = re.compile(r"^[\s{}|:A-Ga-gzZ0-9/,.'^_=\-\[\]!\"()><&%]+$")


def extract_abc(text: str) -> str:
    """Pull the score out of whatever a chat interface wrapped it in.

    Handles markdown fences, a sentence before the score, and a sentence after
    it. Anything that cannot be an ABC line (header, comment, or music) ends the
    score.
    """
    m = re.search(r"```[A-Za-z]*\n(.*?)```", text, flags=re.S)
    if m and "X:" in m.group(1):
        text = m.group(1)
    m = re.search(r"^X:", text, flags=re.M)
    if m:
        text = text[m.start():]
    keep = []
    for line in text.splitlines():
        if not line.strip():
            continue
        if line.startswith("%") or re.match(r"^[A-Za-z]:", line) or MUSIC_LINE.match(line):
            keep.append(line)
        else:
            break
    return "\n".join(keep) + "\n"


def lyric_stats(path: pathlib.Path) -> dict:
    text = path.read_text()
    body = [l for l in text.splitlines() if l.strip() and not l.lstrip().startswith("[")]
    letters = sum(1 for ch in "".join(body) if ch.isalpha())
    syll = sum(1 for ch in "".join(body) if ch in VOWEL_MARKS)
    return {"lines": len(body), "letters": letters, "syllables": syll}


def tempo(sc) -> float:
    m = re.search(r"1/4=(\d+)", sc.headers.get("Q", ""))
    return float(m.group(1)) if m else 110.0


def interval_sequence(notes) -> list[tuple[int, float]]:
    """(signed semitone step, duration) pairs — the melodic fingerprint."""
    out = []
    for a, b in zip(notes, notes[1:]):
        if a.section != b.section:
            continue
        out.append((b.pitch - a.pitch, round(b.dur, 4)))
    return out


def kgram_set(seq, k):
    return {tuple(seq[i:i + k]) for i in range(len(seq) - k + 1)}


def originality(cand_notes, corpus_dir: pathlib.Path | None) -> dict:
    if not corpus_dir or not corpus_dir.is_dir():
        return {"skipped": True}
    cand = kgram_set(interval_sequence(cand_notes), ORIGINALITY_K)
    if not cand:
        return {"skipped": True}
    best, best_track = 0, None
    for d in corpus_dir.iterdir():
        f = d / "score.abc"
        if not f.is_file():
            continue
        try:
            sc = abcmod.parse(str(f), f.read_text())
        except Exception:
            continue
        notes = sc.notes_of("Vocal")
        if len(notes) < ORIGINALITY_K:
            continue
        shared = cand & kgram_set(interval_sequence(notes), ORIGINALITY_K)
        if len(shared) > best:
            best, best_track = len(shared), d.name
    return {"skipped": False, "shared_kgrams": best, "worst_track": best_track,
            "k": ORIGINALITY_K}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("abc", type=pathlib.Path)
    ap.add_argument("--lyrics", type=pathlib.Path, required=True)
    ap.add_argument("--corpus-dir", type=pathlib.Path, default=None)
    args = ap.parse_args(argv)

    text = extract_abc(args.abc.read_text())
    try:
        sc = abcmod.parse(str(args.abc), text)
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL  unparseable: {exc}")
        return 1

    ly = lyric_stats(args.lyrics)
    bpm = tempo(sc)
    vocal = sc.notes_of("Vocal")
    bars = vocal[-1].bar if vocal else 0
    budget = round((111.1 + 0.3126 * ly["letters"]) * bpm / 240 / 4) * 4
    results = []

    def check(name, ok, detail="", hard=True):
        results.append((name, bool(ok), detail, hard))

    check("bars complete", not sc.bars_incomplete,
          f"{len(sc.bars_incomplete)} incomplete" if sc.bars_incomplete
          else "all complete")
    check("single metre", len(sc.meter_changes) == 1,
          f"{len(sc.meter_changes)} M: fields")
    check("one voice", len([v for v in sc.voices if v != "default"]) == 1,
          f"voices={sc.voices}")
    check("bar budget", abs(bars - budget) <= BUDGET_TOLERANCE * budget,
          f"{bars} bars vs budget {budget}")
    check("notes per line", ly["lines"] and 12 <= len(vocal) / ly["lines"] <= 22,
          f"{len(vocal) / ly['lines']:.1f} notes/line over {ly['lines']} lines")
    check("syllabic setting",
          ly["syllables"] and 1.0 <= len(vocal) / ly["syllables"] <= 1.6,
          f"{len(vocal) / ly['syllables']:.2f} notes/syllable")

    # melody: large leaps, at most LEAP_ALLOWANCE_PER_SECTION per section
    leaps = []
    for a, b in zip(vocal, vocal[1:]):
        if a.section == b.section and abs(b.pitch - a.pitch) > MAX_LEAP:
            leaps.append((a.section, a.bar, b.pitch - a.pitch))
    per_sec = {}
    for s, _, _ in leaps:
        per_sec[s] = per_sec.get(s, 0) + 1
    check("leaps <= 7 semitones", all(v <= LEAP_ALLOWANCE_PER_SECTION for v in per_sec.values()),
          "clean" if not leaps else f"{len(leaps)} large leaps {leaps[:3]}")

    # register / chorus lift
    vs = [n.pitch for n in vocal if n.section == "verse"]
    ch = [n.pitch for n in vocal if n.section == "chorus"]
    check("chorus at least as high as verse", not (vs and ch) or max(ch) >= max(vs),
          f"verse max {max(vs) if vs else '-'}, chorus max {max(ch) if ch else '-'}",
          hard=False)

    # cadence
    last = vocal[-1].pc if vocal else None
    check("ends on tonic", last == sc.key_tonic_pc,
          f"final pitch class {last}, key tonic {sc.key_tonic_pc}", hard=False)

    # forbidden constructs
    music = "\n".join(l for l in text.splitlines()
                      if l.strip() and not l.startswith("%")
                      and not re.match(r"^[A-Za-z]:", l))
    bad = [tok for tok in ('"', "{", "(", "[", "w:") if tok in music]
    check("no chords/tuplets/grace/lyrics", not bad, f"found {bad}" if bad else "clean")

    orig = originality(vocal, args.corpus_dir)
    if not orig.get("skipped"):
        check("originality", orig["shared_kgrams"] == 0,
              f"{orig['shared_kgrams']} shared {orig['k']}-gram(s)"
              f" (worst: {str(orig['worst_track'])[:8]})", hard=False)

    width = max(len(n) for n, _, _, _ in results)
    failed = 0
    for name, ok, detail, hard in results:
        tag = "PASS" if ok else ("FAIL" if hard else "WARN")
        if not ok and hard:
            failed += 1
        print(f"{tag}  {name:<{width}}  {detail}")
    print(f"\n{bars} bars, {len(vocal)} vocal notes, {len(sc.sections)} sections, "
          f"{bpm:.0f} BPM, key {sc.key_name}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
