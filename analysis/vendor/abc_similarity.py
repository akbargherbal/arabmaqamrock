#!/usr/bin/env python3
"""
abc_similarity.py
=================
Compare an *instrumental* ABC transcript against the *original* ABC score it was
generated from.

Pipeline
--------
1. parse_abc()        ABC text  ->  Score (notes, chords, key, tempo, sections)
2. compare_scores()   Score x Score -> ~17 sub-metrics, each in [0, 1]
3. build_report()     all (instrumental_i x original_j) pairs -> matched vs.
                      mismatched comparison, baseline-adjusted composite,
                      retrieval rank (does inst_i find its own original?)

Only numpy + pandas (+ matplotlib for the optional plots) are required.

Usage
-----
    python abc_similarity.py comparison_abc_score_inst_vs_original.json --out results
"""
from __future__ import annotations

import argparse
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
COL_ORIG, COL_INST, COL_ID = "ORIGINAL_ABC", "INST_ABC", "TRACK_ORIGINAL_ID"

FRAME_SEC = 0.5          # time resolution for chroma / DTW comparisons
BOUNDARY_TOL_SEC = 4.0   # tolerance for the (diagnostic) section-boundary F1

# metric -> group
GROUPS = {
    "global":  ["key_sim", "tempo_sim", "bar_length_sim", "duration_sim"],
    "harmony": ["chord_vocab_wjaccard", "chord_transition_f1", "chord_timeline_dtw"],
    "melody":  ["pitch_class_cos", "interval_hist_cos", "interval_4gram_f1",
                "melody_chroma_dtw", "register_sim"],
    "rhythm":  ["density_sim", "silence_ratio_sim", "duration_hist_cos",
                "onset_phase_cos", "rhythm_4gram_f1"],
}
WEIGHTS = {"global": 0.15, "harmony": 0.30, "melody": 0.35, "rhythm": 0.20}
METRICS = [m for g in GROUPS.values() for m in g]

# --------------------------------------------------------------------------- #
# 1. ABC parsing
# --------------------------------------------------------------------------- #
NOTE_BASE = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
FIFTHS_BASE = {"C": 0, "G": 1, "D": 2, "A": 3, "E": 4, "B": 5, "F": -1}
SHARP_ORDER, FLAT_ORDER = "FCGDAEB", "BEADGCF"
MODE_OFFSET = {"": 0, "maj": 0, "ion": 0, "mix": -1, "dor": -2, "m": -3, "min": -3,
               "aeo": -3, "phr": -4, "lyd": 1, "loc": -5}

TOKEN = re.compile(
    r'"(?P<chord>[^"]*)"'
    r"|(?P<acc>\^\^|__|\^|_|=)?(?P<letter>[A-Ga-g])(?P<oct>[',]*)(?P<len>\d*/*\d*)(?P<tie>-)?"
    r"|(?P<rest>[zZ])(?P<rlen>\d*/*\d*)"
    r"|(?P<bar>\|\]|\|\||\|:|:\||\|)"
)


def _len(s: str) -> float:
    """ABC length multiplier: '', '4', '/', '/2', '3/2', '//' ..."""
    if not s:
        return 1.0
    m = re.match(r"(\d*)(/*)(\d*)$", s)
    num = int(m.group(1)) if m.group(1) else 1
    slashes, den = len(m.group(2)), m.group(3)
    if slashes == 0:
        return float(num)
    return num / (int(den) if den else 2 ** slashes)


def key_signature(key: str):
    """'D#m' -> (fifths, tonic_pc, mode).  Returns accidentals per letter."""
    m = re.match(r"\s*([A-G])([#b]?)\s*([A-Za-z]*)", key)
    letter, acc, mode = m.group(1), m.group(2), m.group(3).lower()[:3] or ""
    mode = "m" if mode in ("m", "min") else mode
    fifths = FIFTHS_BASE[letter] + 7 * {"#": 1, "b": -1, "": 0}[acc] + MODE_OFFSET.get(mode, 0)
    tonic_pc = (NOTE_BASE[letter] + {"#": 1, "b": -1, "": 0}[acc]) % 12
    accs = {l: 0 for l in "ABCDEFG"}
    if fifths > 0:
        for i in range(fifths):
            accs[SHARP_ORDER[i % 7]] += 1
    elif fifths < 0:
        for i in range(-fifths):
            accs[FLAT_ORDER[i % 7]] -= 1
    return fifths, tonic_pc, ("minor" if mode == "m" else "major"), accs


@dataclass
class Note:
    onset: float   # quarter notes
    dur: float     # quarter notes
    midi: int
    voice: str


@dataclass
class Score:
    key: str
    fifths: int
    tonic_pc: int
    mode: str
    tempo: float                       # quarter-notes per minute
    meter: tuple                       # initial meter
    notes: list = field(default_factory=list)
    chords: list = field(default_factory=list)    # (onset_q, symbol)
    sections: list = field(default_factory=list)  # (label, onset_q)
    end_q: float = 0.0

    @property
    def spq(self) -> float:            # seconds per quarter note
        return 60.0 / self.tempo

    @property
    def total_sec(self) -> float:
        return self.end_q * self.spq

    @property
    def bar_sec(self) -> float:
        return self.meter[0] * 4 / self.meter[1] * self.spq

    def primary_line(self) -> list:
        """Main melodic line: voice 'Ins' if present, else the busiest voice."""
        by = Counter(n.voice for n in self.notes)
        if not by:
            return []
        voice = "Ins" if "Ins" in by else by.most_common(1)[0][0]
        return sorted((n for n in self.notes if n.voice == voice), key=lambda n: n.onset)


def _meter(s: str):
    s = s.strip()
    if s in ("C",):
        return (4, 4)
    if s in ("C|",):
        return (2, 2)
    a, b = s.split("/")
    return (int(a), int(b))


def parse_abc(text: str) -> Score:
    unit_q, meter, tempo, score = 0.5, (4, 4), 120.0, None
    accs, voices, cur = None, {}, None
    chords_by_voice, sections = {}, []

    def vs(name):
        if name not in voices:
            voices[name] = {"t": 0.0, "meter": meter, "acc": {}, "tie": None}
            chords_by_voice[name] = []
        return voices[name]

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("%"):
            sections.append((line.lstrip("% ").strip(),
                             max([v["t"] for v in voices.values()] or [0.0])))
            continue
        fld = re.match(r"^([A-Za-z]):\s*(.*)$", line)
        if fld and not (score and len(line) > 1 and line[1] != ":"):
            k, val = fld.group(1), fld.group(2)
            if k == "M":
                meter = _meter(val)
                if cur:
                    vs(cur)["meter"] = meter
            elif k == "L":
                a, b = val.split("/")
                unit_q = 4 * int(a) / int(b)
            elif k == "Q":
                m = re.match(r"(\d+)/(\d+)\s*=\s*(\d+)", val)
                tempo = float(m.group(3)) * 4 * int(m.group(1)) / int(m.group(2)) if m else 120.0
            elif k == "K":
                fifths, tpc, mode, accs = key_signature(val)
                score = Score(val.strip(), fifths, tpc, mode, tempo, meter)
            elif k == "V":
                name = val.split()[0] if val.split() else ""
                cur = name or None
                if cur:
                    vs(cur)
            continue
        if score is None or cur is None:
            continue
        v = vs(cur)
        for m in TOKEN.finditer(line):
            if m.group("chord") is not None:
                sym = m.group("chord").strip()
                if re.match(r"[A-G]", sym):
                    chords_by_voice[cur].append((v["t"], sym))
            elif m.group("letter"):
                letter = m.group("letter")
                octv = 72 if letter.islower() else 60
                nat = octv + NOTE_BASE[letter.upper()] + 12 * m.group("oct").count("'") - 12 * m.group("oct").count(",")
                acc = m.group("acc")
                if acc:
                    v["acc"][nat] = {"^^": 2, "^": 1, "=": 0, "_": -1, "__": -2}[acc]
                midi = nat + v["acc"].get(nat, accs[letter.upper()])
                dur = unit_q * _len(m.group("len"))
                if v["tie"] == midi and score.notes and score.notes[-1].voice == cur:
                    score.notes[-1].dur += dur                    # merge tied note
                else:
                    score.notes.append(Note(v["t"], dur, midi, cur))
                v["tie"] = midi if m.group("tie") else None
                v["t"] += dur
            elif m.group("rest"):
                n = _len(m.group("rlen"))
                if m.group("rest") == "Z":
                    v["t"] += v["meter"][0] * 4 / v["meter"][1] * n
                else:
                    v["t"] += unit_q * n
            elif m.group("bar"):
                v["acc"] = {}
    score.end_q = max([v["t"] for v in voices.values()] or [0.0])
    if chords_by_voice:
        score.chords = max(chords_by_voice.values(), key=len)
    score.sections = sections
    return score


# --------------------------------------------------------------------------- #
# 2. Chords
# --------------------------------------------------------------------------- #
_CH = re.compile(r"^([A-G])([#b]?)(.*?)(?:/([A-G][#b]?))?$")


def parse_chord(sym: str):
    """-> (root_pc, category, chroma[12]);  category in maj/min/dim/aug/sus"""
    m = _CH.match(sym)
    root = (NOTE_BASE[m.group(1)] + {"#": 1, "b": -1, "": 0}[m.group(2)]) % 12
    q = m.group(3)
    third, fifth, seventh = 4, 7, None
    cat = "maj"
    if "dim" in q or "m7b5" in q:
        third, fifth, cat = 3, 6, "dim"
        seventh = 9 if "dim7" in q else (10 if "m7b5" in q else None)
    elif "aug" in q or "+" in q:
        fifth, cat = 8, "aug"
    elif "sus2" in q:
        third, cat = 2, "sus"
    elif "sus4" in q:
        third, cat = 5, "sus"
    elif q.startswith("m") and not q.startswith("maj"):
        third, cat = 3, "min"
    if seventh is None:
        if "maj7" in q:
            seventh = 11
        elif "7" in q:
            seventh = 10
    pcs = [0, third, fifth] + ([seventh] if seventh is not None else []) + ([9] if "6" in q else [])
    chroma = np.zeros(12)
    for p in pcs:
        chroma[(root + p) % 12] = 1.0
    if m.group(4):
        b = (NOTE_BASE[m.group(4)[0]] + (1 if m.group(4)[1:] == "#" else -1 if m.group(4)[1:] == "b" else 0)) % 12
        chroma[b] += 0.5
    return root, cat, chroma


def chord_segments(score: Score):
    """[(start_s, end_s, chord_class, chroma)]"""
    out, total = [], score.total_sec
    for i, (onset, sym) in enumerate(score.chords):
        end = score.chords[i + 1][0] * score.spq if i + 1 < len(score.chords) else total
        root, cat, chroma = parse_chord(sym)
        out.append((onset * score.spq, max(end, onset * score.spq), (root, cat), chroma))
    return out


# --------------------------------------------------------------------------- #
# 3. Low-level similarity helpers
# --------------------------------------------------------------------------- #
def cosine(a, b) -> float:
    a, b = np.asarray(a, float), np.asarray(b, float)
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0 and nb == 0:
        return 1.0
    if na == 0 or nb == 0:
        return 0.0
    return float(np.clip(a @ b / (na * nb), 0, 1))


def ratio(a: float, b: float) -> float:
    if a == 0 and b == 0:
        return 1.0
    return float(min(a, b) / max(a, b)) if max(a, b) > 0 else 0.0


def set_f1(a: set, b: set) -> float:
    if not a and not b:
        return 1.0
    inter = len(a & b)
    if inter == 0:
        return 0.0
    p, r = inter / len(b), inter / len(a)
    return 2 * p * r / (p + r)


def ngrams(seq, n):
    return {tuple(seq[i:i + n]) for i in range(len(seq) - n + 1)}


def dtw_similarity(A: np.ndarray, B: np.ndarray) -> float:
    """
    Symmetric-step DTW between two chroma sequences (n x 12, m x 12).
    Frame cost = cosine distance (silent-vs-silent = 0, silent-vs-sound = 1).
    Returns 1 - (path cost / (n+m)) in [0, 1].  Row recurrence is vectorised.
    """
    if len(A) == 0 or len(B) == 0:
        return 0.0
    na, nb = np.linalg.norm(A, axis=1), np.linalg.norm(B, axis=1)
    An, Bn = A / np.where(na > 0, na, 1)[:, None], B / np.where(nb > 0, nb, 1)[:, None]
    C = np.clip(1 - An @ Bn.T, 0, 1)
    za, zb = (na == 0)[:, None], (nb == 0)[None, :]
    C = np.where(za & zb, 0.0, np.where(za | zb, 1.0, C))
    n, m = C.shape
    prev = np.full(m + 1, np.inf)
    prev[0] = 0.0
    for i in range(n):
        c = C[i]
        tmp = c + np.minimum(prev[:-1] + c, prev[1:])      # diag costs 2c, vertical c
        S = np.cumsum(c)
        cur = np.empty(m + 1)
        cur[0] = np.inf
        cur[1:] = S + np.minimum.accumulate(tmp - S)        # horizontal run
        prev = cur
    return float(np.clip(1 - prev[m] / (n + m), 0, 1))


# --------------------------------------------------------------------------- #
# 4. Per-score features
# --------------------------------------------------------------------------- #
def melody_chroma_frames(score: Score, T: float, dt: float = FRAME_SEC) -> np.ndarray:
    n = int(math.ceil(max(T, dt) / dt))
    X = np.zeros((n, 12))
    for nt in score.notes:                       # all voices
        s, e = nt.onset * score.spq, (nt.onset + nt.dur) * score.spq
        for i in range(int(s // dt), min(n, int((e - 1e-9) // dt) + 1)):
            X[i, nt.midi % 12] += min(e, (i + 1) * dt) - max(s, i * dt)
    return X


def chord_chroma_frames(score: Score, T: float, dt: float = FRAME_SEC) -> np.ndarray:
    n = int(math.ceil(max(T, dt) / dt))
    X = np.zeros((n, 12))
    for s, e, _, chroma in chord_segments(score):
        X[int(round(s / dt)):int(round(e / dt))] = chroma
    return X


def features(score: Score) -> dict:
    line = score.primary_line()
    spq = score.spq
    dur_s = np.array([n.dur * spq for n in score.notes]) if score.notes else np.array([])
    pc_hist = np.zeros(12)
    for n in score.notes:
        pc_hist[n.midi % 12] += n.dur * spq
    midi = np.array([n.midi for n in line])
    ivals = np.diff(midi) if len(midi) > 1 else np.array([], int)
    onsets = np.array([n.onset for n in line])
    ioi = np.diff(onsets)
    ioi = ioi[ioi > 0]
    rhythm_tok = [int(np.clip(round(math.log2(ioi[i] / ioi[i - 1])), -3, 3)) for i in range(1, len(ioi))]
    seg = chord_segments(score)
    chord_time = Counter()
    for s, e, cls, _ in seg:
        chord_time[cls] += e - s
    chord_seq = []
    for _, _, cls, _ in seg:
        if not chord_seq or chord_seq[-1] != cls:
            chord_seq.append(cls)
    dur_bins = np.histogram(np.log2(dur_s[dur_s > 0]) if len(dur_s) else [], bins=np.arange(-5, 3.5, 0.5))[0]
    return dict(
        score=score,
        pc_hist=pc_hist,
        ivals=ivals,
        iv_hist=np.bincount(np.clip(ivals, -12, 12) + 12, minlength=25),
        iv_grams=ngrams([int(np.clip(i, -12, 12)) for i in ivals], 4),
        rhythm_grams=ngrams(rhythm_tok, 4),
        mean_pitch=float(np.average(midi)) if len(midi) else 0.0,
        pitch_span=float(np.percentile(midi, 95) - np.percentile(midi, 5)) if len(midi) else 0.0,
        density=len(score.notes) / score.total_sec if score.total_sec else 0.0,
        dur_hist=dur_bins,
        chord_time=chord_time,
        chord_bigrams=ngrams(chord_seq, 2),
        boundaries=[t * spq for _, t in score.sections if t > 0],
    )


# --------------------------------------------------------------------------- #
# 5. Pairwise comparison
# --------------------------------------------------------------------------- #
def compare_features(fo: dict, fi: dict) -> dict:
    so, si = fo["score"], fi["score"]
    r = {}

    # ---- global ----
    d = abs(so.fifths - si.fifths)
    r["key_sim"] = 1 - min(d, 6) / 6                         # key-signature distance (relative keys = 0)
    lr = math.log2(si.tempo / so.tempo)
    fold = max(-1, min(1, round(lr)))                        # tempo-octave fold: 0.5x / 1x / 2x
    r["tempo_sim"] = max(0.0, 1 - 2 * abs(lr - fold))        # octave-aware (transcribers often double/halve)
    r["bar_length_sim"] = ratio(so.bar_sec, si.bar_sec)      # bar length in *seconds* (2/4@72 ~ 4/4@147)
    r["duration_sim"] = ratio(so.total_sec, si.total_sec)

    # ---- harmony ----
    keys = set(fo["chord_time"]) | set(fi["chord_time"])
    num = sum(min(fo["chord_time"][k] / max(so.total_sec, 1e-9), fi["chord_time"][k] / max(si.total_sec, 1e-9)) for k in keys)
    den = sum(max(fo["chord_time"][k] / max(so.total_sec, 1e-9), fi["chord_time"][k] / max(si.total_sec, 1e-9)) for k in keys)
    r["chord_vocab_wjaccard"] = num / den if den else 0.0
    r["chord_transition_f1"] = set_f1(fo["chord_bigrams"], fi["chord_bigrams"])
    r["chord_timeline_dtw"] = dtw_similarity(chord_chroma_frames(so, so.total_sec),
                                             chord_chroma_frames(si, si.total_sec))

    # ---- melody ----
    r["pitch_class_cos"] = cosine(fo["pc_hist"], fi["pc_hist"])
    r["interval_hist_cos"] = cosine(fo["iv_hist"], fi["iv_hist"])
    r["interval_4gram_f1"] = set_f1(fo["iv_grams"], fi["iv_grams"])
    r["melody_chroma_dtw"] = dtw_similarity(melody_chroma_frames(so, so.total_sec),
                                            melody_chroma_frames(si, si.total_sec))
    reg = 1 - min(abs(fo["mean_pitch"] - fi["mean_pitch"]), 12) / 12
    r["register_sim"] = 0.5 * reg + 0.5 * ratio(fo["pitch_span"], fi["pitch_span"])

    # ---- rhythm ----
    r["density_sim"] = ratio(fo["density"], fi["density"])
    occ = lambda s: (melody_chroma_frames(s, s.total_sec).sum(1) > 0).mean()
    r["silence_ratio_sim"] = 1 - abs(occ(so) - occ(si))
    r["duration_hist_cos"] = cosine(fo["dur_hist"], fi["dur_hist"])
    k = 2.0 ** fold                                          # put inst beats on the original's beat scale

    def phase_hist(s, kk):
        ph = [(n.onset / kk) % 1.0 for n in s.notes]
        return np.histogram(ph, bins=8, range=(0, 1))[0]

    r["onset_phase_cos"] = cosine(phase_hist(so, 1.0), phase_hist(si, k))
    r["rhythm_4gram_f1"] = set_f1(fo["rhythm_grams"], fi["rhythm_grams"])

    # ---- diagnostics (not in the composite) ----
    best = max(range(12), key=lambda s: cosine(fo["pc_hist"], np.roll(fi["pc_hist"], -s)))
    r["diag_best_transposition"] = best if best <= 6 else best - 12
    r["diag_pc_cos_transposed"] = cosine(fo["pc_hist"], np.roll(fi["pc_hist"], -best))
    r["diag_key_exact"] = float(so.key == si.key)
    r["diag_note_count_ratio"] = ratio(len(so.notes), len(si.notes))
    bo, bi = fo["boundaries"], fi["boundaries"]
    hit_o = sum(any(abs(a - b) <= BOUNDARY_TOL_SEC for b in bi) for a in bo)
    hit_i = sum(any(abs(a - b) <= BOUNDARY_TOL_SEC for a in bo) for b in bi)
    p, rc = (hit_i / len(bi) if bi else 0), (hit_o / len(bo) if bo else 0)
    r["diag_section_boundary_f1"] = 2 * p * rc / (p + rc) if p + rc else 0.0
    return r


def compare_scores(orig: Score, inst: Score) -> dict:
    return compare_features(features(orig), features(inst))


# --------------------------------------------------------------------------- #
# 6. Report over the whole dataframe (matched + mismatched pairs)
# --------------------------------------------------------------------------- #
def composite(row: pd.Series, weights=WEIGHTS, prefix="") -> float:
    return sum(w * np.mean([row[prefix + m] for m in GROUPS[g]]) for g, w in weights.items())


def build_report(df: pd.DataFrame):
    ids = df[COL_ID].tolist()
    F_o = [features(parse_abc(t)) for t in df[COL_ORIG]]
    F_i = [features(parse_abc(t)) for t in df[COL_INST]]

    rows = []
    for i, fi in enumerate(F_i):
        for j, fo in enumerate(F_o):
            rows.append({"inst_id": ids[i], "orig_id": ids[j], "matched": i == j,
                         **compare_features(fo, fi)})
    pairs = pd.DataFrame(rows)

    # baseline = average similarity of an instrumental to *other* songs' originals
    base = pairs.loc[~pairs.matched, METRICS].mean()
    for m in METRICS:
        pairs[m + "_adj"] = ((pairs[m] - base[m]) / np.maximum(1 - base[m], 0.05)).clip(0, 1)
    pairs["composite"] = pairs.apply(composite, axis=1)
    pairs["composite_adj"] = pairs.apply(lambda r: composite(r, prefix=""), axis=1)  # placeholder, replaced below
    pairs["composite_adj"] = pairs.apply(
        lambda r: sum(w * np.mean([r[m + "_adj"] for m in GROUPS[g]]) for g, w in WEIGHTS.items()), axis=1)
    for g in GROUPS:
        pairs[f"grp_{g}"] = pairs[GROUPS[g]].mean(axis=1)

    matched = pairs[pairs.matched].reset_index(drop=True)
    # retrieval sanity check
    ranks, margins = [], []
    for tid in ids:
        sub = pairs[pairs.inst_id == tid].sort_values("composite", ascending=False).reset_index(drop=True)
        ranks.append(int(sub.index[sub.orig_id == tid][0]) + 1)
        other = sub[sub.orig_id != tid].composite
        margins.append(float(sub.loc[sub.orig_id == tid, "composite"].iloc[0] - other.mean()))
    matched["retrieval_rank"] = ranks
    matched["lift_vs_mismatched"] = margins
    return pairs, matched, base


# --------------------------------------------------------------------------- #
def make_plots(pairs, matched, outdir: Path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ids = matched.inst_id.tolist()
    M = pairs.pivot(index="inst_id", columns="orig_id", values="composite").loc[ids, ids].values
    fig, ax = plt.subplots(1, 2, figsize=(15, 5.8), gridspec_kw={"width_ratios": [1, 1.1]})
    im = ax[0].imshow(M, cmap="viridis")
    ax[0].set_xticks(range(len(ids)), [f"{i+1}" for i in range(len(ids))])
    ax[0].set_yticks(range(len(ids)), [f"{i+1}" for i in range(len(ids))])
    ax[0].set_xlabel("original score (song #)")
    ax[0].set_ylabel("instrumental ABC (song #)")
    ax[0].set_title("Composite similarity: every instrumental vs every original\n(diagonal = true pair)")
    for i in range(len(ids)):
        for j in range(len(ids)):
            ax[0].text(j, i, f"{M[i, j]:.2f}", ha="center", va="center", fontsize=7,
                       color="white" if M[i, j] < M.max() * .8 else "black",
                       fontweight="bold" if i == j else None)
        ax[0].add_patch(plt.Rectangle((i - .5, i - .5), 1, 1, fill=False, ec="red", lw=2))
    fig.colorbar(im, ax=ax[0], fraction=.046)
    bottom = np.zeros(len(ids))
    for g, c in zip(GROUPS, ["#8da0cb", "#66c2a5", "#fc8d62", "#e5c494"]):
        vals = matched[f"grp_{g}"].values * WEIGHTS[g]
        ax[1].bar(range(len(ids)), vals, bottom=bottom, label=f"{g} (w={WEIGHTS[g]})", color=c)
        bottom += vals
    ax[1].plot(range(len(ids)), pairs[~pairs.matched].groupby("inst_id").composite.mean().loc[ids].values,
               "k--o", ms=4, label="mean vs mismatched originals")
    ax[1].set_xticks(range(len(ids)), [f"{i+1}" for i in range(len(ids))])
    ax[1].set_xlabel("song #")
    ax[1].set_ylabel("weighted composite")
    ax[1].set_title("Matched-pair composite, split by dimension")
    ax[1].legend(fontsize=8, loc="lower right")
    fig.tight_layout()
    fig.savefig(outdir / "similarity_overview.png", dpi=140)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("json_path")
    ap.add_argument("--out", default="results")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    df = pd.read_json(a.json_path)
    pairs, matched, base = build_report(df)
    pairs.to_csv(out / "all_pairs_metrics.csv", index=False)
    cols = ["inst_id", "composite", "composite_adj", "retrieval_rank", "lift_vs_mismatched"] \
        + [f"grp_{g}" for g in GROUPS] + METRICS + [c for c in matched.columns if c.startswith("diag_")]
    matched[cols].to_csv(out / "matched_pairs_scores.csv", index=False)
    base.rename("mismatched_mean").to_csv(out / "baseline_mismatched_mean.csv")
    make_plots(pairs, matched, out)
    pd.set_option("display.width", 250, "display.max_columns", 50)
    print(matched[["inst_id", "composite", "composite_adj", "retrieval_rank", "lift_vs_mismatched"]
                  + [f"grp_{g}" for g in GROUPS]].round(3).to_string())


if __name__ == "__main__":
    main()
