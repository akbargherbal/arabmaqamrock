#!/usr/bin/env python3
"""Score a candidate's vocal stem by CTC likelihood of the correct vs wrong word.

Greedy CTC on 2-4 s windows is noisy (see evaluate.py). This compares the same
acoustic window against the competing word hypotheses and reports the normalized
log-likelihood margin. A candidate that actually sings the right word should give
correct_ll > wrong_ll.

Usage:
    python3 ctc_score.py MIDI_WAV [--start S --end E --correct TEXT --wrong TEXT]
    python3 ctc_score.py --batch RUN_DIR      # score every <id>/eval vocals stem
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

CTC_MODEL = "jonatasgrosman/wav2vec2-large-xlsr-53-arabic"

TARGETS = {
    "e1": {"window": (156.5, 159.2), "correct": "عَلَيْهِ", "wrong": "عَلِيمْ"},
    "e2": {"window": (201.0, 205.5), "correct": "فَإِنَّ", "wrong": "بِأَنَّ"},
}


def ctc_logprob(log_probs, token_ids, blank_id):
    """CTC forward log-probability (log-sum-exp over alignments)."""
    T = log_probs.shape[0]
    S = 2 * len(token_ids) + 1
    ext = [blank_id] * S
    for i, t in enumerate(token_ids):
        ext[2 * i + 1] = t
    NEG = -1e30
    alpha = np.full(S, NEG, dtype=np.float64)
    alpha[0] = log_probs[0, ext[0]]
    if S > 1:
        alpha[1] = log_probs[0, ext[1]]
    for t in range(1, T):
        prev = alpha.copy()
        for s in range(S):
            a = prev[s]
            if s > 0:
                a = np.logaddexp(a, prev[s - 1])
            if s > 1 and ext[s] != blank_id and ext[s] != ext[s - 2]:
                a = np.logaddexp(a, prev[s - 2])
            alpha[s] = a + log_probs[t, ext[s]]
    if S > 1:
        return float(np.logaddexp(alpha[S - 1], alpha[S - 2]))
    return float(alpha[0])


def score_window(y, sr, model, processor, device, correct, wrong):
    import torch
    try:
        inputs = processor(audio=y, sampling_rate=sr, return_tensors="pt")
    except TypeError:
        inputs = processor(y, sampling_rate=sr, return_tensors="pt")
    with torch.no_grad():
        logits = model(inputs.input_values.to(device)).logits[0]
    lp = logits.log_softmax(-1).cpu().numpy().astype(np.float64)
    tok = processor.tokenizer
    blank = tok.pad_token_id if tok.pad_token_id is not None else 0
    ids_c = tok(correct, add_special_tokens=False).input_ids
    ids_w = tok(wrong, add_special_tokens=False).input_ids
    lc = ctc_logprob(lp, ids_c, blank) / max(len(ids_c), 1)
    lw = ctc_logprob(lp, ids_w, blank) / max(len(ids_w), 1)
    return {
        "correct_ll_per_tok": round(lc, 3),
        "wrong_ll_per_tok": round(lw, 3),
        "margin": round(lc - lw, 3),
        "n_tok_correct": len(ids_c),
        "n_tok_wrong": len(ids_w),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("wav", nargs="?")
    ap.add_argument("--batch", default=None, help="run dir with <id>/eval vocals stems")
    ap.add_argument("--ref-stem", default=None, help="original vocals stem for control")
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    import librosa
    import torch
    from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor

    device = a.device if (a.device != "cuda" or torch.cuda.is_available()) else "cpu"
    processor = Wav2Vec2Processor.from_pretrained(CTC_MODEL)
    model = Wav2Vec2ForCTC.from_pretrained(CTC_MODEL).to(device).eval()

    jobs = []
    if a.batch:
        for name in sorted(os.listdir(a.batch)):
            stem = os.path.join(a.batch, name, "eval", "demucs", "htdemucs",
                                name, "vocals.wav")
            if os.path.exists(stem):
                jobs.append((name, stem))
    if a.ref_stem:
        jobs.insert(0, ("ORIGINAL", a.ref_stem))
    if a.wav:
        jobs.append((os.path.splitext(os.path.basename(a.wav))[0], a.wav))

    rows = []
    for name, path in jobs:
        y_full, sr = librosa.load(path, sr=16000, mono=True)
        row = {"id": name}
        for key, spec in TARGETS.items():
            lo, hi = spec["window"]
            seg = y_full[int(lo * sr):int(hi * sr)]
            row[key] = score_window(seg, sr, model, processor, device,
                                    spec["correct"], spec["wrong"])
        rows.append(row)
        print(json.dumps(row, ensure_ascii=False))

    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=2)
        print(f"\nwrote {a.out}")


if __name__ == "__main__":
    main()
