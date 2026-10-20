#!/usr/bin/env python3
"""CTC forced alignment for Arabic windows (HANDOFF section 4).

RECONSTRUCTED 2026-10-20 (the original align.py was lost with the VM). It does
standard CTC Viterbi alignment of a known Arabic string against the acoustic
frames of a window, and prints per-character and per-word time spans.

Usage:
    python3 align.py AUDIO.wav "عَلَيْهِ" --start 156.8 --end 158.9 [--vocals]
    python3 align.py vocals.wav "فَإِنَّ" --start 195.0 --end 200.0

--vocals is a reminder flag only: always align on the demucs vocal stem, never
the full mix.
"""
from __future__ import annotations

import argparse
import json
import sys

CTC_MODEL = "jonatasgrosman/wav2vec2-large-xlsr-53-arabic"


def load_window(path, start, end, sr=16000):
    import librosa
    y, _ = librosa.load(path, sr=sr, mono=True, offset=start, duration=end - start)
    return y, sr


def logits_for(y, sr, device):
    import torch
    from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor

    processor = Wav2Vec2Processor.from_pretrained(CTC_MODEL)
    model = Wav2Vec2ForCTC.from_pretrained(CTC_MODEL).to(device).eval()
    try:  # transformers >=5 renamed the positional audio arg to `audio`
        inputs = processor(audio=y, sampling_rate=sr, return_tensors="pt")
    except TypeError:
        inputs = processor(y, sampling_rate=sr, return_tensors="pt")
    with torch.no_grad():
        logits = model(inputs.input_values.to(device)).logits
    return logits[0].log_softmax(-1).cpu(), processor


def ctc_align(log_probs, token_ids, blank):
    """Monotonic CTC Viterbi. Returns one (start, end) frame pair per token."""
    import torch

    T = log_probs.shape[0]
    S = 2 * len(token_ids) + 1
    states = [blank] * S
    for i, t in enumerate(token_ids):
        states[2 * i + 1] = t

    NEG = float("-inf")
    dp = torch.full((T, S), NEG)
    back = torch.zeros((T, S), dtype=torch.int8)

    dp[0, 0] = log_probs[0, states[0]]
    if S > 1:
        dp[0, 1] = log_probs[0, states[1]]

    for t in range(1, T):
        for s in range(S):
            best, arg = dp[t - 1, s], 0
            if s > 0 and dp[t - 1, s - 1] > best:
                best, arg = dp[t - 1, s - 1], 1
            if (s > 1 and states[s] != blank and states[s] != states[s - 2]
                    and dp[t - 1, s - 2] > best):
                best, arg = dp[t - 1, s - 2], 2
            dp[t, s] = best + log_probs[t, states[s]]
            back[t, s] = arg

    # backtrack from the best legal final state
    if S > 1 and dp[T - 1, S - 1] >= dp[T - 1, S - 2]:
        s = S - 1
    else:
        s = S - 2
    path = [0] * T
    for t in range(T - 1, -1, -1):
        path[t] = s
        s -= int(back[t, s])
        if s < 0:
            s = 0

    spans = []
    for i in range(len(token_ids)):
        st = 2 * i + 1
        frames = [t for t, cur in enumerate(path) if cur == st]
        spans.append((frames[0], frames[-1] + 1) if frames else (None, None))
    return spans, T


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("audio")
    ap.add_argument("text")
    ap.add_argument("--start", type=float, required=True)
    ap.add_argument("--end", type=float, required=True)
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--vocals", action="store_true",
                    help="acknowledge that the input is a demucs vocal stem")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if not args.vocals:
        print("[align] warning: pass --vocals only if this file is a demucs vocal "
              "stem; full-mix alignment is unreliable", file=sys.stderr)

    import torch
    device = args.device if (args.device != "cuda" or torch.cuda.is_available()) else "cpu"

    y, sr = load_window(args.audio, args.start, args.end)
    log_probs, processor = logits_for(y, sr, device)
    tokenizer = processor.tokenizer
    ids = tokenizer(args.text, add_special_tokens=False).input_ids
    blank = processor.tokenizer.pad_token_id
    if blank is None:
        blank = 0

    spans, T = ctc_align(log_probs, ids, blank)
    dur = args.end - args.start
    sec_per_frame = dur / max(T, 1)

    chars = []
    for tid, (a, b) in zip(ids, spans):
        piece = tokenizer.decode([tid])
        chars.append({
            "token": piece,
            "start_s": None if a is None else round(args.start + a * sec_per_frame, 3),
            "end_s": None if b is None else round(args.start + b * sec_per_frame, 3),
        })

    # group characters into words on whitespace boundaries of the source string
    words, cur = [], []
    for ch, tok in zip(args.text, chars):
        if ch.isspace():
            if cur:
                words.append(cur)
                cur = []
        else:
            cur.append(tok)
    if cur:
        words.append(cur)

    word_out = []
    for w in words:
        starts = [c["start_s"] for c in w if c["start_s"] is not None]
        ends = [c["end_s"] for c in w if c["end_s"] is not None]
        word_out.append({
            "text": "".join(c["token"] for c in w),
            "start_s": min(starts) if starts else None,
            "end_s": max(ends) if ends else None,
        })

    result = {
        "audio": args.audio,
        "text": args.text,
        "window_s": [args.start, args.end],
        "frames": T,
        "seconds_per_frame": round(sec_per_frame, 4),
        "words": word_out,
        "chars": chars,
    }
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for w in word_out:
            print(f"{w['start_s']:>8} - {w['end_s']:>8}  {w['text']}")
        print()
        for ch, c in zip(args.text, chars):
            if not ch.isspace():
                print(f"  {ch}  {c['start_s']} - {c['end_s']}")


if __name__ == "__main__":
    main()
