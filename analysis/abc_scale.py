#!/usr/bin/env python3
"""Scalable ABC similarity: per-score features and vectorised cheap metrics.

The expensive oracle (``analysis/vendor/abc_similarity.py``) computes every pair
with two full DTWs.  This module keeps the oracle's parser and metric
definitions but splits the work:

* :func:`score_features` canonicalises one score into fixed-size arrays once;
* :func:`cheap_matrices` turns all 14 cheap metrics into BLAS/broadcast
  operations over an ``N x N`` grid (rows = instrumental/output, cols =
  original/input);
* :func:`banded_dtw` is the escalation-only alignment (2 s frames, Sakoe-Chiba
  band) used for flagged tracks.

The four deep metrics (two DTWs, two four-gram F1s) stay in the oracle and are
only computed by the audit/escalation paths.

Nothing here edits the vendored oracle.
"""
from __future__ import annotations

import math
from collections import Counter
from pathlib import Path

import numpy as np

from analysis.vendor import abc_similarity as oracle

# --------------------------------------------------------------------------- #
# Metric layout (cheap production path)
# --------------------------------------------------------------------------- #
CHEAP_GROUPS = {
    "global": ["key_sim", "tempo_sim", "bar_length_sim", "duration_sim"],
    "harmony": ["chord_vocab_wjaccard", "chord_transition_f1", "chord_chroma_cos"],
    "melody": ["pitch_class_cos", "interval_hist_cos", "register_sim"],
    "rhythm": ["density_sim", "silence_ratio_sim", "duration_hist_cos",
               "onset_phase_cos"],
}
CHEAP_METRICS = [m for g in CHEAP_GROUPS.values() for m in g]
WEIGHTS = oracle.WEIGHTS

# phase histograms are stored for these onset scalings (2**fold)
PHASE_KS = (0.5, 1.0, 2.0)
_PHASE_INDEX = {k: i for i, k in enumerate(PHASE_KS)}
DUR_BINS = np.arange(-5, 3.5, 0.5)          # 16 bins, as in the oracle
FRAME_SEC = oracle.FRAME_SEC


# --------------------------------------------------------------------------- #
# Feature extraction
# --------------------------------------------------------------------------- #
def score_features(score) -> dict:
    """Canonical feature vector for one parsed :class:`Score`."""
    line = score.primary_line()
    spq = score.spq
    total = float(score.total_sec)

    # --- melody: primary line only (Ins when present) --------------------- #
    midi = np.array([n.midi for n in line], dtype=np.int32)
    ivals = np.diff(midi) if len(midi) > 1 else np.array([], dtype=np.int32)
    onsets = np.array([n.onset for n in line], dtype=np.float64)
    ioi = np.diff(onsets)
    ioi = ioi[ioi > 0]
    rhythm_tok = [int(np.clip(round(math.log2(ioi[i] / ioi[i - 1])), -3, 3))
                  for i in range(1, len(ioi))]

    # --- pitch-class / interval histograms (oracle semantics) ------------- #
    pc_hist = np.zeros(12, dtype=np.float64)
    for n in score.notes:
        pc_hist[n.midi % 12] += n.dur * spq
    iv_hist = np.bincount(np.clip(ivals, -12, 12) + 12, minlength=25).astype(np.float64)

    # --- harmony ---------------------------------------------------------- #
    segs = oracle.chord_segments(score)
    chord_time = Counter()
    chord_chroma = np.zeros(12, dtype=np.float64)
    chord_seq = []
    for s, e, cls, chroma in segs:
        chord_time[cls] += max(e - s, 0.0)
        chord_chroma += max(e - s, 0.0) * chroma
        if not chord_seq or chord_seq[-1] != cls:
            chord_seq.append(cls)
    denom = max(total, 1e-9)
    chord_shares = {k: v / denom for k, v in chord_time.items()}

    # --- rhythm ----------------------------------------------------------- #
    dur_s = np.array([n.dur * spq for n in score.notes], dtype=np.float64)
    dur_hist = np.histogram(np.log2(dur_s[dur_s > 0]) if len(dur_s) else [],
                            bins=DUR_BINS)[0].astype(np.float64)
    frames = oracle.melody_chroma_frames(score, total, FRAME_SEC)
    silence_ratio = float((frames.sum(axis=1) <= 0).mean()) if len(frames) else 1.0
    phases = np.zeros((len(PHASE_KS), 8), dtype=np.float64)
    for ki, kk in enumerate(PHASE_KS):
        ph = [(n.onset / kk) % 1.0 for n in score.notes]
        phases[ki] = np.histogram(ph, bins=8, range=(0, 1))[0]

    return {
        "score": score,
        "fifths": int(score.fifths),
        "tempo": float(score.tempo),
        "bar_sec": float(score.bar_sec),
        "total_sec": total,
        "n_notes": len(score.notes),
        "n_chords": len(score.chords),
        "pc_hist": pc_hist,
        "iv_hist": iv_hist,
        "mean_pitch": float(np.average(midi)) if len(midi) else 0.0,
        "pitch_span": (float(np.percentile(midi, 95) - np.percentile(midi, 5))
                       if len(midi) else 0.0),
        "chord_shares": chord_shares,
        "chord_chroma": chord_chroma,
        "density": len(score.notes) / total if total else 0.0,
        "silence_ratio": silence_ratio,
        "dur_hist": dur_hist,
        "phases": phases,
        # audit-only set features
        "interval_4grams": oracle.ngrams(
            [int(np.clip(i, -12, 12)) for i in ivals], 4),
        "chord_bigrams": oracle.ngrams(chord_seq, 2),
        "rhythm_4grams": oracle.ngrams(rhythm_tok, 4),
        "boundaries": [t * spq for _, t in score.sections if t > 0],
    }


def features_from_text(text: str) -> dict:
    return score_features(oracle.parse_abc(text))


def features_from_file(path: str | Path) -> dict:
    return features_from_text(Path(path).read_text(encoding="utf-8", errors="replace"))


def stack_features(feats: list[dict]) -> dict:
    """Stack per-score dicts into dense arrays + a chord vocabulary."""
    if not feats:
        raise ValueError("stack_features: empty input")
    vocab = sorted({k for f in feats for k in f["chord_shares"]})
    vindex = {k: i for i, k in enumerate(vocab)}
    chord_share = np.zeros((len(feats), max(len(vocab), 1)), dtype=np.float32)
    for i, f in enumerate(feats):
        for k, v in f["chord_shares"].items():
            chord_share[i, vindex[k]] = v
    return {
        "fifths": np.array([f["fifths"] for f in feats], dtype=np.float32),
        "tempo": np.array([f["tempo"] for f in feats], dtype=np.float32),
        "bar_sec": np.array([f["bar_sec"] for f in feats], dtype=np.float32),
        "total_sec": np.array([f["total_sec"] for f in feats], dtype=np.float32),
        "n_notes": np.array([f["n_notes"] for f in feats], dtype=np.float32),
        "n_chords": np.array([f["n_chords"] for f in feats], dtype=np.float32),
        "pc_hist": np.stack([f["pc_hist"] for f in feats]).astype(np.float32),
        "iv_hist": np.stack([f["iv_hist"] for f in feats]).astype(np.float32),
        "mean_pitch": np.array([f["mean_pitch"] for f in feats], dtype=np.float32),
        "pitch_span": np.array([f["pitch_span"] for f in feats], dtype=np.float32),
        "chord_share": chord_share,
        "chord_chroma": np.stack([f["chord_chroma"] for f in feats]).astype(np.float32),
        "density": np.array([f["density"] for f in feats], dtype=np.float32),
        "silence_ratio": np.array([f["silence_ratio"] for f in feats], dtype=np.float32),
        "dur_hist": np.stack([f["dur_hist"] for f in feats]).astype(np.float32),
        "phases": np.stack([f["phases"] for f in feats]).astype(np.float32),
        "chord_vocab": vocab,
        # audit-only set features stay as Python sets
        "chord_bigrams": [f["chord_bigrams"] for f in feats],
        "interval_4grams": [f["interval_4grams"] for f in feats],
        "rhythm_4grams": [f["rhythm_4grams"] for f in feats],
        "boundaries": [f["boundaries"] for f in feats],
    }


# --------------------------------------------------------------------------- #
# Scalar cheap metrics (parity reference; mirrors the oracle formulas)
# --------------------------------------------------------------------------- #
def fold_of(tempo_orig: float, tempo_inst: float) -> int:
    if tempo_orig <= 0 or tempo_inst <= 0:
        return 0
    return int(max(-1, min(1, round(math.log2(tempo_inst / tempo_orig)))))


def cheap_scalar(fa: dict, fb: dict) -> dict:
    """Cheap metrics for one pair, ``fa`` = original/input, ``fb`` = output."""
    a, b = fa, fb
    fold = fold_of(a["tempo"], b["tempo"])
    lr = (math.log2(b["tempo"] / a["tempo"])
          if a["tempo"] > 0 and b["tempo"] > 0 else 0.0)
    r = {
        "key_sim": 1 - min(abs(a["fifths"] - b["fifths"]), 6) / 6,
        "tempo_sim": max(0.0, 1 - 2 * abs(lr - fold)),
        "bar_length_sim": oracle.ratio(a["bar_sec"], b["bar_sec"]),
        "duration_sim": oracle.ratio(a["total_sec"], b["total_sec"]),
    }

    keys = set(a["chord_shares"]) | set(b["chord_shares"])
    num = sum(min(a["chord_shares"].get(k, 0.0), b["chord_shares"].get(k, 0.0))
              for k in keys)
    den = sum(max(a["chord_shares"].get(k, 0.0), b["chord_shares"].get(k, 0.0))
              for k in keys)
    # 0/0 means both scores have no chords; they are identical on this axis.
    r["chord_vocab_wjaccard"] = num / den if den > 0 else 1.0
    r["chord_transition_f1"] = oracle.set_f1(a["chord_bigrams"], b["chord_bigrams"])
    r["chord_chroma_cos"] = oracle.cosine(a["chord_chroma"], b["chord_chroma"])

    r["pitch_class_cos"] = oracle.cosine(a["pc_hist"], b["pc_hist"])
    r["interval_hist_cos"] = oracle.cosine(a["iv_hist"], b["iv_hist"])
    reg = 1 - min(abs(a["mean_pitch"] - b["mean_pitch"]), 12) / 12
    r["register_sim"] = 0.5 * reg + 0.5 * oracle.ratio(a["pitch_span"], b["pitch_span"])

    r["density_sim"] = oracle.ratio(a["density"], b["density"])
    r["silence_ratio_sim"] = 1 - abs(a["silence_ratio"] - b["silence_ratio"])
    r["duration_hist_cos"] = oracle.cosine(a["dur_hist"], b["dur_hist"])
    pa = a["phases"][_PHASE_INDEX[1.0]]
    pb = b["phases"][_PHASE_INDEX[2.0 ** fold]]
    r["onset_phase_cos"] = oracle.cosine(pa, pb)
    return r


def composite_from_metrics(r: dict) -> float:
    return float(sum(w * np.mean([r[m] for m in CHEAP_GROUPS[g]])
                     for g, w in WEIGHTS.items()))


def group_scores(r: dict) -> dict:
    return {f"grp_{g}": float(np.mean([r[m] for m in ms]))
            for g, ms in CHEAP_GROUPS.items()}


# --------------------------------------------------------------------------- #
# Vectorised matrices (rows = output, cols = input)
# --------------------------------------------------------------------------- #
def _cos_matrix(X: np.ndarray) -> np.ndarray:
    X = np.asarray(X, dtype=np.float32)
    n = np.linalg.norm(X, axis=1)
    Xn = X / np.where(n > 0, n, 1.0)[:, None]
    S = Xn @ Xn.T
    zero = n <= 0
    S = np.where(zero[:, None] & zero[None, :], 1.0,
                 np.where(zero[:, None] | zero[None, :], 0.0, S))
    np.clip(S, 0.0, 1.0, out=S)
    np.fill_diagonal(S, 1.0)                 # exact identity by definition
    return S


def _cos_cross(A: np.ndarray, B: np.ndarray) -> np.ndarray:
    A = np.asarray(A, dtype=np.float32)
    B = np.asarray(B, dtype=np.float32)
    na = np.linalg.norm(A, axis=1)
    nb = np.linalg.norm(B, axis=1)
    An = A / np.where(na > 0, na, 1.0)[:, None]
    Bn = B / np.where(nb > 0, nb, 1.0)[:, None]
    S = An @ Bn.T
    za, zb = na <= 0, nb <= 0
    S = np.where(za[:, None] & zb[None, :], 1.0,
                 np.where(za[:, None] | zb[None, :], 0.0, S))
    return np.clip(S, 0.0, 1.0)


def _ratio_matrix(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    a = np.asarray(a, dtype=np.float32)[:, None]
    b = np.asarray(b, dtype=np.float32)[None, :]
    lo, hi = np.minimum(a, b), np.maximum(a, b)
    return np.where(hi > 0, lo / np.where(hi > 0, hi, 1.0), 1.0).astype(np.float32)


def _fold_matrix(tempo: np.ndarray) -> np.ndarray:
    """fold[i, j] for row tempo i (output) vs col tempo j (input)."""
    ti = np.asarray(tempo, dtype=np.float64)[:, None]
    tj = np.asarray(tempo, dtype=np.float64)[None, :]
    with np.errstate(divide="ignore", invalid="ignore"):
        lr = np.log2(ti / tj)
    lr = np.where(np.isfinite(lr), lr, 0.0)
    return np.clip(np.round(lr), -1, 1).astype(np.int8), lr


def _chord_vocab_matrix(C: np.ndarray, block: int = 256) -> np.ndarray:
    n = len(C)
    out = np.empty((n, n), dtype=np.float32)
    for s in range(0, n, block):
        e = min(s + block, n)
        Mi = np.minimum(C[s:e, None, :], C[None, :, :]).sum(axis=2)
        Ma = np.maximum(C[s:e, None, :], C[None, :, :]).sum(axis=2)
        out[s:e] = np.where(Ma > 0, Mi / np.where(Ma > 0, Ma, 1.0), 1.0)
    return out


def _set_f1_matrix(sets: list[set]) -> np.ndarray:
    vocab = sorted({x for s in sets for x in s})
    n = len(sets)
    if not vocab:
        return np.ones((n, n), dtype=np.float32)
    B = np.zeros((n, len(vocab)), dtype=np.float32)
    idx = {v: i for i, v in enumerate(vocab)}
    for i, s in enumerate(sets):
        for x in s:
            B[i, idx[x]] = 1.0
    inter = B @ B.T
    size = B.sum(axis=1)
    denom = size[:, None] + size[None, :]
    f1 = np.where(denom > 0, 2.0 * inter / np.where(denom > 0, denom, 1.0), 1.0)
    f1 = np.where((inter == 0) & (denom > 0), 0.0, f1)
    np.clip(f1, 0.0, 1.0, out=f1)
    np.fill_diagonal(f1, 1.0)
    return f1.astype(np.float32)


def cheap_matrices(FT: dict) -> dict[str, np.ndarray]:
    """All 14 cheap metrics as ``N x N`` float32 matrices (rows=output)."""
    fifths = np.asarray(FT["fifths"], dtype=np.float32)
    tempo = np.asarray(FT["tempo"], dtype=np.float32)
    fold, lr = _fold_matrix(tempo)

    M: dict[str, np.ndarray] = {}
    M["key_sim"] = (1.0 - np.minimum(np.abs(fifths[:, None] - fifths[None, :]), 6) / 6.0)
    M["tempo_sim"] = np.maximum(0.0, 1.0 - 2.0 * np.abs(lr - fold)).astype(np.float32)
    M["bar_length_sim"] = _ratio_matrix(FT["bar_sec"], FT["bar_sec"])
    M["duration_sim"] = _ratio_matrix(FT["total_sec"], FT["total_sec"])

    M["chord_vocab_wjaccard"] = _chord_vocab_matrix(
        np.asarray(FT["chord_share"], dtype=np.float32))
    M["chord_transition_f1"] = _set_f1_matrix(FT["chord_bigrams"])
    M["chord_chroma_cos"] = _cos_matrix(FT["chord_chroma"])

    M["pitch_class_cos"] = _cos_matrix(FT["pc_hist"])
    M["interval_hist_cos"] = _cos_matrix(FT["iv_hist"])
    mp, sp = np.asarray(FT["mean_pitch"], np.float32), np.asarray(FT["pitch_span"], np.float32)
    reg = 1.0 - np.minimum(np.abs(mp[:, None] - mp[None, :]), 12.0) / 12.0
    M["register_sim"] = (0.5 * reg + 0.5 * _ratio_matrix(sp, sp)).astype(np.float32)

    M["density_sim"] = _ratio_matrix(FT["density"], FT["density"])
    M["silence_ratio_sim"] = (1.0 - np.abs(
        np.asarray(FT["silence_ratio"], np.float32)[:, None]
        - np.asarray(FT["silence_ratio"], np.float32)[None, :])).astype(np.float32)
    M["duration_hist_cos"] = _cos_matrix(FT["dur_hist"])

    ph = np.asarray(FT["phases"], dtype=np.float32)
    p_one = ph[:, _PHASE_INDEX[1.0]]
    c_half = _cos_cross(ph[:, _PHASE_INDEX[0.5]], p_one)
    c_one = _cos_cross(p_one, p_one)
    c_two = _cos_cross(ph[:, _PHASE_INDEX[2.0]], p_one)
    M["onset_phase_cos"] = np.where(fold == -1, c_half,
                                    np.where(fold == 1, c_two, c_one)).astype(np.float32)

    for k in CHEAP_METRICS:
        np.clip(M[k], 0.0, 1.0, out=M[k])
    # exact self-similarity
    for k in CHEAP_METRICS:
        np.fill_diagonal(M[k], 1.0)
    return M


def composite_matrix(M: dict[str, np.ndarray]) -> np.ndarray:
    out = np.zeros_like(next(iter(M.values())), dtype=np.float32)
    for g, ms in CHEAP_GROUPS.items():
        out += WEIGHTS[g] * np.mean([M[m] for m in ms], axis=0)
    return out


def group_matrices(M: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    return {g: np.mean([M[m] for m in ms], axis=0).astype(np.float32)
            for g, ms in CHEAP_GROUPS.items()}


# --------------------------------------------------------------------------- #
# Banded DTW (escalation only)
# --------------------------------------------------------------------------- #
def banded_dtw(A: np.ndarray, B: np.ndarray, band_frac: float = 0.10) -> float:
    """Sakoe-Chiba banded DTW on chroma frames; same cost as the oracle DTW.

    Frames are expected at ~2 s (coarser than the oracle's 0.5 s), so a 5 min
    track is ~150 frames and the band is a handful of cells per row.
    """
    A = np.asarray(A, dtype=np.float64)
    B = np.asarray(B, dtype=np.float64)
    if len(A) == 0 or len(B) == 0:
        return 0.0
    na, nb = np.linalg.norm(A, axis=1), np.linalg.norm(B, axis=1)
    An = A / np.where(na > 0, na, 1.0)[:, None]
    Bn = B / np.where(nb > 0, nb, 1.0)[:, None]
    C = np.clip(1.0 - An @ Bn.T, 0.0, 1.0)
    za, zb = (na == 0)[:, None], (nb == 0)[None, :]
    C = np.where(za & zb, 0.0, np.where(za | zb, 1.0, C))
    n, m = C.shape
    band = max(1, int(math.ceil(band_frac * max(n, m))))
    INF = float("inf")
    prev = np.full(m + 1, INF)
    prev[0] = 0.0
    for i in range(n):
        lo = max(0, i - band)
        hi = min(m, i + band + 1)
        cur = np.full(m + 1, INF)
        for j in range(lo, hi):
            c = C[i, j]
            best = prev[j + 1] + c                 # vertical
            d = prev[j] + 2.0 * c                  # diagonal
            if d < best:
                best = d
            h = cur[j] + c                         # horizontal
            if h < best:
                best = h
            cur[j + 1] = best
        prev = cur
    return float(np.clip(1.0 - prev[m] / (n + m), 0.0, 1.0))


def chroma_frames(score, dt: float = 2.0, kind: str = "melody") -> np.ndarray:
    """Chroma frames at a coarse resolution for banded DTW."""
    if kind == "chord":
        return oracle.chord_chroma_frames(score, score.total_sec, dt)
    return oracle.melody_chroma_frames(score, score.total_sec, dt)
