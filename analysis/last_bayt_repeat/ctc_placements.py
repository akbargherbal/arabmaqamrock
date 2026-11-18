#!/usr/bin/env python3
"""Count last-bayt renditions with CTC placement on a demucs vocal stem.

Why this exists
---------------
Whisper is good at transcribing the bayt but unreliable at *counting* it: on a
music bed it merges two renditions into one segment, and on some stems it skips
whole repetitions.  CTC alignment against the known text is the independent
check asked for in ``NEXT_SESSION.md`` (T3).

Method
------
A rendition is ~10-11 s long.  Slide a fixed-length window over the final
chorus, run a CTC forward + Viterbi pass for the single bayt in every window,
and keep windows where

* the marginal CTC score is above the track's median (the window actually
  contains bayt-like acoustics), and
* the Viterbi span is a plausible rendition length (7-13 s).

Windows belonging to the same rendition produce the same Viterbi span, so
non-maximum suppression on the *span* (not the window) collapses each rendition
to one placement.  Placements closer than ``--min-separation`` to a stronger
one are reported as ``reprise`` (a cadential echo/partial restatement) rather
than counted as another full rendition.

The model is XLSR-53 Arabic, the same family used by the project's karaoke
alignment.  Pass the **undiacritized** bayt: the tokenizer drops harakat and
the alignment is character/token one-to-one.

Usage
-----
    python3 ctc_placements.py --results analysis/last_bayt_repeat/results.csv \\
        --stems-root work/stems --out-dir work/ctc --device cuda
"""
from __future__ import annotations

import argparse
import csv
import json
import statistics
from pathlib import Path

import numpy as np

CTC_MODEL = "jonatasgrosman/wav2vec2-large-xlsr-53-arabic"
DEFAULT_REFERENCE = "اتلهي بها الهواجر اذ كل ابن هم بليه عمياء"


def load_logits(audio: Path, start_s: float, end_s: float, processor, model,
                device: str, sr: int = 16000):
    import librosa
    import torch

    y, _ = librosa.load(str(audio), sr=sr, mono=True, offset=start_s,
                        duration=end_s - start_s)
    try:
        inputs = processor(audio=y, sampling_rate=sr, return_tensors="pt")
    except TypeError:
        inputs = processor(y, sampling_rate=sr, return_tensors="pt")
    with torch.no_grad():
        logits = model(inputs.input_values.to(device)).logits[0]
    return logits.log_softmax(-1).cpu().numpy().astype(np.float64)


def forward_viterbi(log_probs: np.ndarray, token_ids: list[int], blank: int):
    """Return (marginal log-prob / token, (first_frame, last_frame))."""
    T = log_probs.shape[0]
    S = 2 * len(token_ids) + 1
    ext = np.full(S, blank, dtype=int)
    for i, tok in enumerate(token_ids):
        ext[2 * i + 1] = tok
    NEG = -1e30

    # forward (marginal)
    alpha = np.full(S, NEG)
    alpha[0] = log_probs[0, ext[0]]
    if S > 1:
        alpha[1] = log_probs[0, ext[1]]

    # viterbi
    dp = np.full((T, S), NEG)
    back = np.zeros((T, S), dtype=np.int8)
    dp[0] = alpha

    for t in range(1, T):
        prev = alpha.copy()
        beta = np.empty(S)
        beta[0] = prev[0]
        beta[1:] = np.logaddexp(prev[1:], prev[:-1])
        same = (ext[2:] != blank) & (ext[2:] != ext[:-2])
        beta[2:][same] = np.logaddexp(beta[2:][same], prev[:-2][same])
        alpha = beta + log_probs[t, ext]

        row = dp[t - 1]
        c1 = np.empty(S)
        c1[0] = NEG
        c1[1:] = row[:-1]
        c2 = np.empty(S)
        c2[:2] = NEG
        c2[2:] = row[:-2]
        legal = (ext != blank) & (ext != np.concatenate(([blank, blank], ext[:-2])))
        c2 = np.where(legal, c2, NEG)
        stack = np.stack([row, c1, c2])
        arg = np.argmax(stack, axis=0)
        dp[t] = stack[arg, np.arange(S)] + log_probs[t, ext]
        back[t] = arg

    fwd = float(np.logaddexp(alpha[-1], alpha[-2])) if S > 1 else float(alpha[0])

    state = S - 1 if (S > 1 and dp[-1, S - 1] >= dp[-1, S - 2]) else S - 2
    path = np.zeros(T, dtype=int)
    for t in range(T - 1, -1, -1):
        path[t] = state
        state = max(state - int(back[t, state]), 0)
    frames = np.where((path % 2) == 1)[0]
    span = (int(frames[0]), int(frames[-1]) + 1) if len(frames) else (None, None)
    return fwd / len(token_ids), span


def place_bayt(log_probs: np.ndarray, token_ids: list[int], blank: int,
               offset_s: float, fps: float, window_s: float, step_s: float,
               min_span: float, max_span: float):
    n = log_probs.shape[0]
    win = int(round(window_s * fps))
    candidates = []
    start = 0.0
    while start + window_s <= n / fps + 1e-6:
        i0 = int(round(start * fps))
        i1 = i0 + win
        if i1 > n:
            break
        score, (a, b) = forward_viterbi(log_probs[i0:i1], token_ids, blank)
        if a is not None:
            span = (b - a) / fps
            if min_span <= span <= max_span:
                candidates.append({
                    "score": round(float(score), 4),
                    "onset_s": round(offset_s + start + a / fps, 2),
                    "offset_s": round(offset_s + start + b / fps, 2),
                    "span_s": round(span, 2),
                    "window_s": round(offset_s + start, 2),
                })
        start += step_s
    return candidates


def nms_placements(candidates: list[dict], overlap: float, min_separation: float):
    """Collapse duplicate spans; mark close weaker placements as reprises."""
    accepted: list[dict] = []
    for cand in sorted(candidates, key=lambda c: -c["score"]):
        dup = False
        for kept in accepted:
            inter = max(0.0, min(cand["offset_s"], kept["offset_s"])
                        - max(cand["onset_s"], kept["onset_s"]))
            union = max(cand["offset_s"], kept["offset_s"]) - min(cand["onset_s"], kept["onset_s"])
            if inter > 0 and inter / union >= overlap:
                dup = True
                break
            if abs(cand["onset_s"] - kept["onset_s"]) < min_separation:
                dup = True
                break
        if not dup:
            accepted.append(dict(cand))
    accepted.sort(key=lambda c: c["onset_s"])
    return accepted


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--results", default="analysis/last_bayt_repeat/results.csv")
    ap.add_argument("--stems-root", default="work/stems",
                    help="root containing <batch>/htdemucs/<track>/vocals.wav")
    ap.add_argument("--out-dir", default="work/ctc")
    ap.add_argument("--text", default=DEFAULT_REFERENCE,
                    help="undiacritized last bayt")
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--window-s", type=float, default=11.0)
    ap.add_argument("--step-s", type=float, default=0.25)
    ap.add_argument("--min-span", type=float, default=7.0)
    ap.add_argument("--max-span", type=float, default=13.0)
    ap.add_argument("--min-separation", type=float, default=7.5)
    ap.add_argument("--nms-overlap", type=float, default=0.10)
    ap.add_argument("--margin", type=float, default=0.25,
                    help="score threshold above the median window score")
    args = ap.parse_args()

    import torch
    from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor

    device = args.device if (args.device != "cuda" or torch.cuda.is_available()) else "cpu"
    processor = Wav2Vec2Processor.from_pretrained(CTC_MODEL)
    model = Wav2Vec2ForCTC.from_pretrained(CTC_MODEL).to(device).eval()
    tokenizer = processor.tokenizer
    token_ids = tokenizer(args.text, add_special_tokens=False).input_ids
    blank = tokenizer.pad_token_id if tokenizer.pad_token_id is not None else 0

    rows = list(csv.DictReader(Path(args.results).open(encoding="utf-8")))
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = []

    for row in rows:
        batch, track = row["batch"], row["track"]
        audio = Path(args.stems_root) / batch / "htdemucs" / track / "vocals.wav"
        if not audio.exists():
            print(f"warning: missing stem {audio}", flush=True)
            continue
        cs = float(row["chorus_start_s"])
        dur = float(row["audio_duration_s"])
        region_start = max(0.0, cs - 12.0)
        log_probs = load_logits(audio, region_start, dur, processor, model, device)

        def count_with(window_s: float):
            cands = place_bayt(log_probs, token_ids, blank, region_start, 50.0,
                               window_s, args.step_s, args.min_span, args.max_span)
            med = statistics.median(c["score"] for c in cands) if cands else 0.0
            keep = nms_placements(
                [c for c in cands if c["score"] >= med + args.margin],
                args.nms_overlap, args.min_separation)
            return cands, med, keep

        candidates, median, kept = count_with(args.window_s)

        # Stability check: the count should not depend on the window length
        # (renditions are ~8-11 s, so 10-13 s windows all contain one).
        stability = {}
        for w in (10.0, 11.0, 12.0, 13.0):
            if abs(w - args.window_s) < 1e-6:
                stability[w] = len(kept)
            else:
                stability[w] = len(count_with(w)[2])
        stable = len(set(stability.values())) == 1

        doc = {
            "batch": batch,
            "track": track,
            "audio": str(audio),
            "reference": args.text,
            "region_s": [round(region_start, 2), round(dur, 2)],
            "fps": 50.0,
            "window_s": args.window_s,
            "step_s": args.step_s,
            "median_score": round(float(median), 4),
            "n_candidates": len(candidates),
            "stability": {str(k): v for k, v in stability.items()},
            "stable": stable,
            "placements": kept,
            "candidates": candidates,
        }
        (out_dir / f"{batch}_{track}.json").write_text(
            json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")

        onsets = [p["onset_s"] for p in kept]
        summary.append({
            "batch": batch,
            "track": track,
            "ctc_count": len(kept),
            "ctc_onsets": json.dumps(onsets),
            "ctc_first_onset_s": onsets[0] if onsets else "",
            "ctc_last_offset_s": kept[-1]["offset_s"] if kept else "",
            "ctc_last_span_s": kept[-1]["span_s"] if kept else "",
            "ctc_scores": json.dumps([p["score"] for p in kept]),
            "ctc_median_score": round(float(median), 3),
            "ctc_window_stability": json.dumps({str(k): v for k, v in stability.items()}),
            "ctc_stable": stable,
        })
        print(f"{batch} {track}: ctc={len(kept)} stable={stable} "
              f"windows={stability} onsets={onsets}", flush=True)

    if summary:
        out = out_dir / "ctc_summary.csv"
        with out.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(summary[0]))
            writer.writeheader()
            writer.writerows(summary)
        print(f"wrote {out} ({len(summary)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
