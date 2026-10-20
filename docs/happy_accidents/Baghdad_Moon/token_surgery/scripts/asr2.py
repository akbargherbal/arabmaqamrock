#!/usr/bin/env python3
"""faster-whisper helper with word timestamps (HANDOFF section 4).

RECONSTRUCTED 2026-10-20 (the original asr2.py was lost with the VM).

Reminder from the handoff: Whisper large-v3 on the *full mix* hallucinates
("subscribe to the channel"). Use it on demucs vocal stems, and never as the
only judge of a fix - pair it with Arabic CTC on the two error windows.

Usage:
    python3 asr2.py AUDIO.wav [--model large-v3] [--device cuda] [--json out.json]
                              [--window 150 165] [--language ar]
"""
from __future__ import annotations

import argparse
import json
import sys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("audio")
    ap.add_argument("--model", default="large-v3")
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--compute-type", default="float16")
    ap.add_argument("--language", default="ar")
    ap.add_argument("--window", nargs=2, type=float, default=None,
                    help="only transcribe this [start end] second range")
    ap.add_argument("--json", default=None)
    args = ap.parse_args()

    from faster_whisper import WhisperModel

    device = args.device
    try:
        model = WhisperModel(args.model, device=device, compute_type=args.compute_type)
    except Exception as exc:  # no GPU / no fp16 support
        print(f"[asr2] falling back to cpu/int8: {exc}", file=sys.stderr)
        model = WhisperModel(args.model, device="cpu", compute_type="int8")

    segments, info = model.transcribe(
        args.audio,
        language=args.language,
        word_timestamps=True,
        vad_filter=False,
    )

    out = {"audio": args.audio, "model": args.model, "segments": []}
    lo, hi = args.window if args.window else (None, None)
    for seg in segments:
        if lo is not None and seg.end < lo:
            continue
        if hi is not None and seg.start > hi:
            continue
        words = [{"start": round(w.start, 2), "end": round(w.end, 2), "word": w.word}
                 for w in (seg.words or [])]
        out["segments"].append({
            "start": round(seg.start, 2),
            "end": round(seg.end, 2),
            "text": seg.text.strip(),
            "words": words,
        })
        print(f"[{seg.start:7.2f}-{seg.end:7.2f}] {seg.text.strip()}")
        for w in words:
            print(f"    {w['start']:7.2f}-{w['end']:7.2f} {w['word']}")

    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2, ensure_ascii=False)
        print(f"wrote {args.json}")


if __name__ == "__main__":
    main()
