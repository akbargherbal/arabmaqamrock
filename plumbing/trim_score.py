#!/usr/bin/env python3
"""Trim an ABC score to a target duration without breaking its voice pairing.

Why
---
`abc_file` conditions the AR on a token prefix whose length is the score's
duration. When the score asks for more sung time than the lyrics can fill, the
model pads the surplus by re-singing the last line (see
`analysis/last_bayt_repeat/REPORT.md` §3.2). This tool cuts the score down so a
render can test that mechanism with one variable changed.

What it does
------------
* parses the file as *sections* (`%` comments) and *steps* (one `V:` block per
  voice that covers the same time span; usually a Vocal step then an Ins step);
* keeps whole steps from the top until the next step would pass `--target-s`;
* never cuts inside a step, so the two voices stay bar-aligned;
* appends one rest bar per voice if the cut lands on sounding notes;
* renames the final kept section to `outro` (a cosmetic comment; the runtime
  ignores ABC comments).

The duration model is `generate.abc_duration_s` (max of the per-voice totals),
so the printed numbers are in the same units the pipeline uses.

Usage
-----
    python3 plumbing/trim_score.py scores/harith_hat/hat_01.abc \
        --target-s 270 --out scores/harith_hat/hat_01_short270.abc
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from generate import _abc_bar_units, _frac, abc_duration_s  # noqa: E402


@dataclass
class Step:
    """One time interval covered by one or more voice blocks."""
    blocks: list[list[str]] = field(default_factory=list)   # [[V: line, music...], ...]
    seconds: float = 0.0
    sounding: bool = False                                  # any non-rest note
    unit: float = 0.0                                       # header state at this step
    meter: float = 0.0
    tempo: int = 0


@dataclass
class Section:
    label: str
    steps: list[Step] = field(default_factory=list)


def _block_seconds(block: list[str], unit: float, meter: float, tempo: int) -> float:
    dur = 0.0
    for music in block[1:]:
        for bar in music.split("|"):
            if not bar.strip():
                continue
            sec = _bar_seconds(bar, unit, meter, tempo)
            if sec is None:
                raise SystemExit(f"unsupported ABC construct in: {bar!r}")
            dur += sec
    return dur


def _bar_seconds(bar: str, unit: float, meter: float, tempo: int) -> float | None:
    m = re.fullmatch(r"([Zz])(\d*)", bar.strip())
    if m:
        return meter * (int(m.group(2)) if m.group(2) else 1) * 4 * 60 / tempo
    units = _abc_bar_units(bar.strip(), unit)
    return None if units is None else units * 4 * 60 / tempo


def parse(text: str) -> tuple[list[str], list[Section], float, float, int]:
    """Split into (header lines, sections, unit, meter, tempo)."""
    header: list[str] = []
    sections: list[Section] = []
    unit = meter = None
    tempo: int | None = None
    body: list[str] = []
    seen_key = False
    for raw in text.splitlines():
        line = raw.rstrip()
        s = line.strip()
        if not seen_key:
            # ABC header runs through K: (the V: lines above it are voice
            # declarations, not switches)
            header.append(line)
            m = re.match(r"^L:\s*(\d+/\d+)", s)
            if m:
                unit = _frac(m.group(1))
                continue
            m = re.match(r"^M:\s*(\d+/\d+)", s)
            if m:
                meter = _frac(m.group(1))
                continue
            m = re.match(r"^Q:.*?=\s*(\d+)", s)
            if m:
                tempo = int(m.group(1))
                continue
            if s.startswith("K:"):
                seen_key = True
            continue
        body.append(line)

    if unit is None or meter is None or tempo is None:
        raise SystemExit("score is missing L:/M:/Q: headers")

    cur_section: Section | None = None
    cur_block: list[str] | None = None
    cur_step: Step | None = None
    step_voices: set[str] = set()
    for line in body:
        s = line.strip()
        if not s or s.startswith("%%"):
            continue
        if s.startswith("%"):
            cur_section = Section(s.lstrip("%").strip() or "section")
            sections.append(cur_section)
            cur_block = None
            cur_step = None
            step_voices = set()
            continue
        if s.startswith("V:"):
            if cur_section is None:
                cur_section = Section("score")
                sections.append(cur_section)
            voice = s[2:].strip().split()[0]
            if cur_step is None or voice in step_voices:
                # a voice repeating means the previous step is closed: the two
                # (or more) voices that share a span are adjacent blocks
                cur_step = Step(unit=unit, meter=meter, tempo=tempo)
                cur_section.steps.append(cur_step)
                step_voices = set()
            step_voices.add(voice)
            cur_block = [s]
            cur_step.blocks.append(cur_block)
            continue
        if cur_block is None or cur_step is None:
            continue
        # inline header changes inside the body
        m = re.match(r"^M:\s*(\d+/\d+)", s)
        if m:
            meter = _frac(m.group(1))
            continue
        m = re.match(r"^L:\s*(\d+/\d+)", s)
        if m:
            unit = _frac(m.group(1))
            continue
        m = re.match(r"^Q:.*?=\s*(\d+)", s)
        if m:
            tempo = int(m.group(1))
            continue
        if re.match(r"^[A-Za-z]:", s):
            continue
        cur_block.append(s)
        dur = 0.0
        for bar in s.split("|"):
            if not bar.strip():
                continue
            sec = _bar_seconds(bar, unit, meter, tempo)
            if sec is None:
                raise SystemExit(f"unsupported ABC construct in: {bar!r}")
            dur += sec
        cur_step.seconds = max(cur_step.seconds, dur)
        if re.search(r"[A-Ga-g]", re.sub(r'"[^"]*"', "", s)):
            cur_step.sounding = True
    return header, sections, unit, meter, tempo


def _step_unequal(step: Step) -> bool:
    durs = [_block_seconds(b, step.unit, step.meter, step.tempo) for b in step.blocks]
    return bool(durs) and (max(durs) - min(durs)) > 1e-6


def vocal_sung_seconds(sections: list[Section]) -> float:
    """Sung (non-rest) vocal seconds — the budget that fights the lyric text."""
    total = 0.0
    for sec in sections:
        for step in sec.steps:
            v = next((b for b in step.blocks if b[0][2:].strip().lower().startswith("vocal")), None)
            if not v:
                continue
            music = re.sub(r'"[^"]*"', "", " ".join(v[1:]))
            if not re.search(r"[A-Ga-g]", music):
                continue
            # a step's duration is shared by its voices; count the sung ones
            total += step.seconds
    return total


def trim(text: str, target_s: float) -> tuple[str, dict]:
    header, sections, unit, meter, tempo = parse(text)
    before = abc_duration_s(text) or 0.0
    sung_before = vocal_sung_seconds(sections)

    kept: list[Section] = []
    total = 0.0
    for sec in sections:
        keep_steps = []
        for step in sec.steps:
            if total + step.seconds > target_s + 1e-6:
                break
            keep_steps.append(step)
            total += step.seconds
        if not keep_steps:
            break
        kept.append(Section(sec.label, keep_steps))
        if len(keep_steps) != len(sec.steps):
            break

    if not kept:
        raise SystemExit(f"target {target_s:.1f}s is shorter than the first step")

    # The cut has to leave both voices the same length.  A step whose blocks
    # disagree (a voice resting while the other sounds) is dropped until the
    # final step is balanced; then an explicit outro of rests is appended so the
    # score ends on a bar both voices share.
    while len(kept[-1].steps) > 1 and _step_unequal(kept[-1].steps[-1]):
        kept[-1].steps.pop()
    while _step_unequal(kept[-1].steps[-1]) and len(kept) > 1:
        kept.pop()
    if _step_unequal(kept[-1].steps[-1]):
        raise SystemExit("cannot balance the two voices at this cut point")

    outro_bars = 2
    kept.append(Section("outro", [Step(blocks=[["V: Vocal", f"Z{outro_bars}|"],
                                                 ["V: Ins", f"Z{outro_bars}|"]],
                                          seconds=outro_bars * meter * 4 * 60 / tempo,
                                          unit=unit, meter=meter, tempo=tempo)]))

    lines: list[str] = list(header)
    for i, sec in enumerate(kept):
        label = "outro" if i == len(kept) - 1 and len(kept) > 1 else sec.label
        lines.append(f"% {label}")
        for step in sec.steps:
            for block in step.blocks:
                lines.extend(block)
    out = "\n".join(lines) + "\n"

    after = abc_duration_s(out) or 0.0
    sung_after = vocal_sung_seconds(parse(out)[1])
    return out, {
        "duration_before": round(before, 1),
        "duration_after": round(after, 1),
        "sung_before": round(sung_before, 1),
        "sung_after": round(sung_after, 1),
        "target": target_s,
        "sections_before": len(sections),
        "sections_kept": len(kept),
        "outro_bars": outro_bars,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("abc", type=Path)
    ap.add_argument("--target-s", type=float, required=True,
                    help="keep whole steps while the total stays at or below this")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    text = args.abc.read_text(encoding="utf-8")
    out, info = trim(text, args.target_s)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(out, encoding="utf-8")
    for k, v in info.items():
        print(f"{k}: {v}")
    print(f"wrote {args.out} ({len(out.splitlines())} lines)")
    if info["duration_after"] < 0.85 * args.target_s:
        print("warning: could not reach the target — the cut is limited by step size",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
