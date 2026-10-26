#!/usr/bin/env python3
"""Check an ABC score against the arabmaqamrock melody specification.

Three jobs, all aimed at things a language model cannot reliably check itself:

1. **Structure** — complete bars, one voice, one metre, line/phrase budget.
2. **Texture** — line length in beats, how much of the score is rests, how many
   note starts fall off the beat, phrase contour, register span, and whether
   adjacent phrases repeat each other. These are the properties that decide
   whether a score sounds like this style or like a slow hymn; they are
   measured, not asserted, because a model writing melody cannot count them.
3. **Originality** — longest run of identical melodic movement shared with any
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

# Texture thresholds, from the 177 reference tracks (see the spec's table).
# A phrase is a line of lyrics: notes separated by rests of a beat or more.
PHRASE_GAP = 1.0            # beats of rest that end a phrase
# One lyric line occupies about 10 beats in 4/4 and 6 in 2/4 (78 of the 177
# reference tracks are 2/4). The band must scale with the meter, not assume 4/4.
def line_beats(beats_per_bar: float) -> tuple[float, float]:
    target = 6.0 if beats_per_bar < 3.0 else 10.0
    return (0.7 * target, 1.4 * target)


MIN_SILENCE = 0.25          # rests as a share of the sung span (corpus 30%)
MIN_OFFBEAT = 0.25          # note starts not on a beat (corpus 64%)
MAX_PHRASE_OVERLAP = 0.35   # shared 3-interval material between neighbours (corpus 5%)
MIN_REGISTER_SPAN = 12      # p95-p05 in semitones (corpus 16)
MIN_DESCENDING = 0.40       # share of phrases that open high and cadence low (corpus 62%)


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


def beats_per_bar(sc) -> float:
    """Quarter-note beats in one bar of the score's (single) meter."""
    value = sc.meter_changes[0][0] if sc.meter_changes else "4/4"
    try:
        num, den = (int(x) for x in value.split("/"))
        return 4.0 * num / den
    except (ValueError, ZeroDivisionError):
        return 4.0


def phrases(notes, gap: float = PHRASE_GAP) -> list[list]:
    """Split a vocal line into phrases the way the corpus is measured.

    A phrase ends where a rest of `gap` beats or more appears, or where the
    section changes. Returns only groups long enough to be melodic.
    """
    out, cur = [], []
    for n in notes:
        if cur and (n.rest_before >= gap or n.section != cur[-1].section):
            out.append(cur)
            cur = []
        cur.append(n)
    if cur:
        out.append(cur)
    return [p for p in out if len(p) >= 3]


def phrase_beats(p) -> float:
    return (p[-1].onset + p[-1].dur) - p[0].onset


def contour(p) -> str:
    """Shape of a phrase, judged by where its highest note sits."""
    ps = [n.pitch for n in p]
    lo, hi = min(ps), max(ps)
    if hi - lo <= 2:
        return "flat"
    at = ps.index(hi) / (len(ps) - 1)
    if at <= 0.35:
        return "falling"
    if at >= 0.65:
        return "rising"
    if ps[0] >= hi - 2 or ps[-1] >= hi - 2:
        return "other"
    return "arch"


def median(xs: list[float]) -> float:
    s = sorted(xs)
    n = len(s)
    if not n:
        return 0.0
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def silence_share(notes) -> float:
    """Share of the sung span that is rest, from first note to last note end."""
    span = max(n.onset + n.dur for n in notes) - min(n.onset for n in notes)
    if span <= 0:
        return 0.0
    return 1.0 - sum(n.dur for n in notes) / span


def offbeat_share(notes, tol: float = 0.02) -> float:
    """Share of note starts that are not on a quarter-note beat."""
    off = 0
    for n in notes:
        r = n.onset % 1.0
        if min(abs(r), abs(1.0 - r)) > tol:
            off += 1
    return off / len(notes) if notes else 0.0


def phrase_overlap(ph: list[list]) -> float:
    """Median share of 3-interval material shared by neighbouring phrases."""
    def grams(p):
        iv = [b.pitch - a.pitch for a, b in zip(p, p[1:])]
        return {tuple(iv[i:i + 3]) for i in range(len(iv) - 2)}

    sims = []
    for a, b in zip(ph, ph[1:]):
        A, B = grams(a), grams(b)
        if A and B:
            sims.append(len(A & B) / len(A | B))
    return median(sims) if sims else 0.0


def register_span(notes) -> tuple[int, int]:
    ps = sorted(n.pitch for n in notes)
    lo = ps[int(0.05 * len(ps))]
    hi = ps[min(len(ps) - 1, int(0.95 * len(ps)))]
    return lo, hi


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
    if not vocal:
        print("FAIL  no Vocal notes in the score")
        return 1
    bpb = beats_per_bar(sc)
    bars = sc.n_bars
    score_beats = bars * bpb
    budget_beats = (111.1 + 0.3126 * ly["letters"]) * bpm / 60.0
    line_range = line_beats(bpb)
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
    check("bar budget", abs(score_beats - budget_beats) <= BUDGET_TOLERANCE * budget_beats,
          f"{score_beats:.0f} beats ({bars} bars) vs budget {budget_beats:.0f} beats")
    check("notes per line", ly["lines"] and 12 <= len(vocal) / ly["lines"] <= 22,
          f"{len(vocal) / ly['lines']:.1f} notes/line over {ly['lines']} lines")
    check("syllabic setting",
          ly["syllables"] and 1.0 <= len(vocal) / ly["syllables"] <= 1.6,
          f"{len(vocal) / ly['syllables']:.2f} notes/syllable")

    # texture: what separates this style from a slow hymn
    ph = phrases(vocal)
    if ph:
        med_beats = median([phrase_beats(p) for p in ph])
        check("line length", line_range[0] <= med_beats <= line_range[1],
              f"median phrase {med_beats:.1f} beats over {len(ph)} phrase(s)"
              f" (need {line_range[0]:.1f}-{line_range[1]:.1f})")
    else:
        check("line length", False,
              "no phrase boundaries: add a rest of a beat or more between lines")

    sil = silence_share(vocal)
    check("silence", sil >= MIN_SILENCE,
          f"{sil:.0%} rests (need >= {MIN_SILENCE:.0%})")

    off = offbeat_share(vocal)
    check("off-beat starts", off >= MIN_OFFBEAT,
          f"{off:.0%} of note starts off the beat (need >= {MIN_OFFBEAT:.0%})")

    if len(ph) >= 2:
        ov = phrase_overlap(ph)
        check("adjacent phrases differ", ov <= MAX_PHRASE_OVERLAP,
              f"median shared material {ov:.2f} (need <= {MAX_PHRASE_OVERLAP:.2f})")
    else:
        check("adjacent phrases differ", False,
              f"{len(ph)} phrase(s): the melody never breaks")

    lo, hi = register_span(vocal)
    check("register span", hi - lo >= MIN_REGISTER_SPAN,
          f"p05-p95 {lo}-{hi} = {hi - lo} semitones (need >= {MIN_REGISTER_SPAN})")

    if ph:
        desc = sum(1 for p in ph if contour(p) == "falling") / len(ph)
        check("descending phrases", desc >= MIN_DESCENDING,
              f"{desc:.0%} descending (need >= {MIN_DESCENDING:.0%})")

    # melody: large leaps, at most LEAP_ALLOWANCE_PER_SECTION per section.
    # Measure inside phrases, as the corpus does: a leap across a rest of a beat
    # or more starts a new phrase and is not a melodic leap.
    leaps = []
    for a, b in zip(vocal, vocal[1:]):
        if (a.section == b.section and b.rest_before < PHRASE_GAP
                and abs(b.pitch - a.pitch) > MAX_LEAP):
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
