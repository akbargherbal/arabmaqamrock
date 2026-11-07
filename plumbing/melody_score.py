#!/usr/bin/env python3
"""Build a melody-only cover score: the Vocal line moved to Ins, no chords.

This is the round-05 variant of the official YuE2 instrumental workflow. It
keeps the native score's bar grid (meters, keys, section labels, tempo) and
drops everything except the vocal melody:

  * every Vocal note moves to Ins (the original Ins line is discarded);
  * Vocal keeps only rests;
  * chord symbols are removed.

The result is a single monophonic lead line with the original song form, which
is what `cot="melody"` expects.

Usage:
    python3 plumbing/melody_score.py scores/fadhl_shaker/habeetak.abc \
        --out-dir scores/fadhl_shaker_melody_habeetak
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "yue2_instrumental"))

from abc_tools import parse_abc  # noqa: E402
from compile_score import compile_events  # noqa: E402
from instrumentalize import section_starts  # noqa: E402


def melody_score(text: str, *, name: str = "habeetak") -> tuple[str, dict]:
    """Render the Vocal line as the only Ins melody, without chords."""
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Need a nonempty native score")
    source = parse_abc(text)
    vocal = source.voices["Vocal"]
    if not vocal.notes:
        raise ValueError("The score contains no vocal melody to move")
    ordered = sorted(vocal.notes)
    for a, b in zip(ordered, ordered[1:]):
        if a[0] + a[2] > b[0]:
            raise ValueError(
                f"Vocal melody overlaps at quarter {b[0]}; "
                "choose one lead line before compiling")
    if any(when not in {start for start, _, _ in vocal.bars} for when, _ in vocal.keys):
        raise ValueError(
            "An inline key change occurs inside a bar; normalize its spelling "
            "without changing pitches first")

    sections = section_starts(text, source)
    bars = []
    for start, _, (n, d) in vocal.bars:
        key = next(key for t, key in reversed(vocal.keys) if t <= start)
        bar = dict(meter=f"{n}/{d}", key=key)
        if start in sections:
            bar["section"] = sections[start]
        bars.append(bar)

    events = dict(
        bpm=source.bpm,
        key=vocal.keys[0][1],
        bars=bars,
        notes=[[str(t), str(d), p] for t, p, d in vocal.notes],
        chords=[],
    )
    converted, _ = compile_events(events)

    target = parse_abc(converted)
    target_vocal = target.voices["Vocal"]
    target_ins = target.voices["Ins"]
    if target_vocal.notes:
        raise ValueError("Melody-only output still has vocal notes")
    if target_ins.notes != vocal.notes:
        raise ValueError("Vocal melody was not preserved exactly on Ins")
    if target_ins.bars != source.voices["Ins"].bars:
        raise ValueError("Melody-only output changed the bar grid")
    if target.bpm != source.bpm:
        raise ValueError("Melody-only output changed the tempo")
    if target.voices["Vocal"].keys != source.voices["Vocal"].keys:
        raise ValueError("Melody-only output changed the key timeline")
    if target_vocal.chords:
        raise ValueError("Melody-only output still has chord symbols")

    seconds = float(target_ins.time * 60 / target.bpm)
    check = dict(
        source=name,
        mode="melody_only",
        source_transcription=(
            "derived from a --full transcription (Vocal staff only; the "
            "original Ins line and chord symbols are discarded); not a "
            "melody-only re-transcription"),
        vocal_notes_before=len(vocal.notes),
        vocal_notes_after=0,
        original_ins_notes=len(source.voices["Ins"].notes),
        output_ins_notes=len(target_ins.notes),
        chords_before=len(vocal.chords),
        chords_after=0,
        bpm_before=source.bpm,
        bpm_after=target.bpm,
        key_before=vocal.keys[0][1],
        key_after=target.voices["Vocal"].keys[0][1],
        bars=len(target_ins.bars),
        meter=target_ins.bars[0][2],
        duration_quarters=str(target_ins.time),
        duration_seconds=round(seconds, 3),
        vocal_pitch_onset_duration_preserved=True,
        bar_grid_preserved=True,
        nominal_seconds=round(seconds, 3),
    )
    return converted, check


def main() -> int:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("input", type=Path, help="native score.abc with a Vocal melody")
    cli.add_argument("--out-dir", required=True, type=Path,
                     help="directory for <slug>.abc and report.json")
    cli.add_argument("--slug", help="output basename (default: input stem)")
    args = cli.parse_args()

    try:
        text = args.input.read_text(encoding="utf-8")
        converted, check = melody_score(text, name=args.slug or args.input.stem)
    except (OSError, ValueError) as exc:
        print(f"Melody score failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    args.out_dir.mkdir(parents=True, exist_ok=True)
    slug = args.slug or args.input.stem
    target = args.out_dir / f"{slug}.abc"
    target.write_text(converted, encoding="utf-8")
    (args.out_dir / "report.json").write_text(
        json.dumps(check, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"{args.input.name:28} -> {target.name:28} "
        f"vocal={check['vocal_notes_before']:4} "
        f"ins=0 -> {check['output_ins_notes']:4} "
        f"chords={check['chords_after']} "
        f"seconds={check['duration_seconds']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
