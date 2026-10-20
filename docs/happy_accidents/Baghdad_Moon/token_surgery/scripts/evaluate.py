#!/usr/bin/env python3
"""Evaluate a Baghdad Moon B candidate WAV (HANDOFF section 4).

RECONSTRUCTED 2026-10-20. The original evaluate.py lived only on the ephemeral
VM and was never backed up; this is a faithful re-implementation of the method
documented in HANDOFF.md section 4 (demucs -> Arabic CTC -> F0 -> similarity).
Treat its numbers as the same *kind* of measurement, not as a continuation of a
previous numeric series.

What it does, in order:
  1. Demucs htdemucs --two-stems=vocals (full mix CTC is useless; always demucs).
  2. Arabic CTC (jonatasgrosman/wav2vec2-large-xlsr-53-arabic) greedy decode on
     the two error windows, on the vocal stem.
       e1 156.8-158.9 s: original ends in م (عَلِيمْ); a fix should end in ه.
       e2 201.6-205.1 s: original starts with ب (بِأَنَّ); a fix should start with ف.
  3. F0 contour (librosa.pyin) for both windows.
  4. Waveform correlation (overall + 5 s windows) and mel-spectrogram mean
     absolute difference outside the edited windows, against the reference WAV.

Usage:
    python3 evaluate.py CANDIDATE.wav [--ref REF.wav] [--out DIR] [--device cuda]
                                     [--no-demucs] [--stems DIR]
Exit code 0 always unless something is structurally wrong; results go to
DIR/eval.json and DIR/eval.md.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys

WINDOWS = {
    "e1": (156.8, 158.9),
    "e2": (201.6, 205.1),
}
# regions touched by surgery; excluded from the "collateral change" metrics
EDIT_REGIONS = [(156.5, 159.2), (201.8, 205.2)]

CTC_MODEL = "jonatasgrosman/wav2vec2-large-xlsr-53-arabic"


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def demucs_vocals(wav, outdir, device="cuda"):
    """Run demucs and return the vocals stem path."""
    os.makedirs(outdir, exist_ok=True)
    track = os.path.splitext(os.path.basename(wav))[0]
    stem = os.path.join(outdir, "htdemucs", track, "vocals.wav")
    if os.path.exists(stem):
        return stem
    cmd = [sys.executable, "-m", "demucs", "--two-stems=vocals", "-d", device,
           "-o", outdir, wav]
    print("[evaluate] " + " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)
    if not os.path.exists(stem):
        raise RuntimeError(f"demucs did not produce {stem}")
    return stem


def load_mono(path, sr=16000):
    import librosa
    y, _ = librosa.load(path, sr=sr, mono=True)
    return y, sr


def ctc_decode(y, sr, model, processor, device):
    import numpy as np
    import torch

    try:  # transformers >=5 renamed the positional audio arg to `audio`
        inputs = processor(audio=y, sampling_rate=sr, return_tensors="pt")
    except TypeError:
        inputs = processor(y, sampling_rate=sr, return_tensors="pt")
    with torch.no_grad():
        logits = model(inputs.input_values.to(device)).logits
    ids = torch.argmax(logits, dim=-1)[0].cpu().numpy()
    text = processor.batch_decode([ids])[0]
    return text, ids, logits.cpu()


def f0_contour(y, sr, fmin=65, fmax=800):
    import librosa
    import numpy as np

    f0, voiced, _ = librosa.pyin(y, fmin=fmin, fmax=fmax, sr=sr, frame_length=2048)
    vals = f0[~np.isnan(f0)]
    if len(vals) == 0:
        return {"voiced_frames": 0}
    return {
        "voiced_frames": int(len(vals)),
        "median_hz": round(float(np.median(vals)), 1),
        "first_hz": round(float(vals[0]), 1),
        "last_hz": round(float(vals[-1]), 1),
        "min_hz": round(float(vals.min()), 1),
        "max_hz": round(float(vals.max()), 1),
    }


def similarity(ref, cand, sr):
    import librosa
    import numpy as np

    n = min(len(ref), len(cand))
    ref, cand = ref[:n], cand[:n]
    overall = float(np.corrcoef(ref, cand)[0, 1])

    win = 5 * sr
    per_window = []
    for start in range(0, n - win + 1, win):
        r = ref[start:start + win]
        c = cand[start:start + win]
        if np.std(r) < 1e-9 or np.std(c) < 1e-9:
            continue
        per_window.append({
            "start_s": round(start / sr, 1),
            "corr": round(float(np.corrcoef(r, c)[0, 1]), 4),
        })

    # mel distance, excluding the two edited regions
    mref = librosa.feature.melspectrogram(y=ref, sr=sr, n_mels=128)
    mcand = librosa.feature.melspectrogram(y=cand, sr=sr, n_mels=128)
    dref = librosa.power_to_db(mref, ref=np.max)
    dcand = librosa.power_to_db(mcand, ref=np.max)
    m = min(dref.shape[1], dcand.shape[1])
    dref, dcand = dref[:, :m], dcand[:, :m]
    times = librosa.frames_to_time(np.arange(m), sr=sr)
    mask = np.ones(m, dtype=bool)
    for lo, hi in EDIT_REGIONS:
        mask &= ~((times >= lo) & (times <= hi))
    inside = np.abs(dref[:, ~mask] - dcand[:, ~mask]).mean() if (~mask).any() else float("nan")
    outside = np.abs(dref[:, mask] - dcand[:, mask]).mean() if mask.any() else float("nan")

    return {
        "overall_corr": round(overall, 5),
        "worst_5s_window_corr": min(w["corr"] for w in per_window) if per_window else None,
        "mean_5s_corr": round(float(np.mean([w["corr"] for w in per_window])), 5) if per_window else None,
        "mel_mean_abs_db_outside_edits": round(float(outside), 3),
        "mel_mean_abs_db_inside_edits": round(float(inside), 3),
        "windows": per_window,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("candidate")
    ap.add_argument("--ref", default=os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "original/02-استيداع-قمر-بغداد-ولوعة-الوداع-B_1712905618.wav"))
    ap.add_argument("--out", default=None)
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--no-demucs", action="store_true")
    ap.add_argument("--stems", default=None, help="reuse this demucs vocals stem")
    args = ap.parse_args()

    if not os.path.exists(args.candidate):
        sys.exit(f"no such candidate: {args.candidate}")
    outdir = args.out or os.path.join(os.path.dirname(os.path.abspath(args.candidate)), "eval")
    os.makedirs(outdir, exist_ok=True)

    result = {
        "candidate": os.path.abspath(args.candidate),
        "candidate_sha256": sha256_file(args.candidate),
        "reference": os.path.abspath(args.ref) if os.path.exists(args.ref) else None,
        "ctc_model": CTC_MODEL,
    }

    if args.stems:
        vocals = args.stems
    elif args.no_demucs:
        vocals = args.candidate
    else:
        vocals = demucs_vocals(args.candidate, os.path.join(outdir, "demucs"), args.device)
    result["vocals_stem"] = vocals

    import torch
    from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor

    device = args.device if (args.device != "cuda" or torch.cuda.is_available()) else "cpu"
    processor = Wav2Vec2Processor.from_pretrained(CTC_MODEL)
    model = Wav2Vec2ForCTC.from_pretrained(CTC_MODEL).to(device).eval()

    yv, sr = load_mono(vocals)
    result["ctc"] = {}
    result["f0"] = {}
    for name, (lo, hi) in WINDOWS.items():
        seg = yv[int(lo * sr):int(hi * sr)]
        text, _, _ = ctc_decode(seg, sr, model, processor, device)
        result["ctc"][name] = {"window_s": [lo, hi], "greedy": text}
        result["f0"][name] = {"window_s": [lo, hi], **f0_contour(seg, sr)}

    if result["reference"]:
        # Similarity is measured on the full mix against the reference full mix.
        # (The demucs vocal stem is only for CTC/F0; comparing it to the reference
        # full mix would conflate separation artefacts with surgery collateral.)
        yr, sr_ref = load_mono(result["reference"])
        yc, sr_c = load_mono(args.candidate)
        result["similarity"] = similarity(yr, yc, min(sr_c, sr_ref))

    with open(os.path.join(outdir, "eval.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    md = [f"# eval — {os.path.basename(args.candidate)}", ""]
    md.append(f"- sha256: `{result['candidate_sha256']}`")
    md.append(f"- vocals: `{vocals}`")
    md.append("")
    md.append("| window | CTC greedy (vocal stem) | F0 median / first / last |")
    md.append("|---|---|---|")
    for name in WINDOWS:
        c = result["ctc"][name]["greedy"]
        f = result["f0"][name]
        md.append(f"| {name} | `{c}` | {f.get('median_hz')} / {f.get('first_hz')} / {f.get('last_hz')} Hz |")
    if "similarity" in result:
        s = result["similarity"]
        md += ["", "| metric | value |", "|---|---|",
               f"| overall corr | {s['overall_corr']} |",
               f"| mean 5 s corr | {s['mean_5s_corr']} |",
               f"| worst 5 s corr | {s['worst_5s_window_corr']} |",
               f"| mel Δ dB outside edits | {s['mel_mean_abs_db_outside_edits']} |",
               f"| mel Δ dB inside edits | {s['mel_mean_abs_db_inside_edits']} |"]
    with open(os.path.join(outdir, "eval.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")

    print("\n".join(md))
    print(f"\nwrote {outdir}/eval.json and {outdir}/eval.md")


if __name__ == "__main__":
    main()
