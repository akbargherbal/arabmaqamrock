#!/usr/bin/env python3
"""Cohort calibration for the scalable ABC similarity matrices.

All functions are pure numpy/pandas.  The semantics follow
``docs/plans/yt500-instrumental-abc-similarity.md`` §9.3–§9.5:

* baseline = mean over every off-diagonal pair (exact, not a decoy sample);
* ``*_adj = clip((x - base) / (1 - base), 0, 1)``;
* retrieval rank is exact 1..N;
* cohort centre/scale = median/MAD and empirical percentiles;
* corpus verdict = sign-flip permutation test on per-track lift.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from analysis import abc_scale as S

# --------------------------------------------------------------------------- #
# Baseline / adjustment / exact ranks
# --------------------------------------------------------------------------- #
def offdiag_mean(M: np.ndarray) -> float:
    n = M.shape[0]
    if n < 2:
        return 0.0
    return float((M.sum(dtype=np.float64) - np.trace(M)) / (n * n - n))


def baseline_matrix(M: dict[str, np.ndarray]) -> dict[str, float]:
    return {m: offdiag_mean(M[m]) for m in S.CHEAP_METRICS}


def adjusted(M: dict[str, np.ndarray], base: dict[str, float]) -> dict[str, np.ndarray]:
    out = {}
    for m in S.CHEAP_METRICS:
        den = max(1.0 - base[m], 1e-6)
        out[m] = np.clip((M[m] - base[m]) / den, 0.0, 1.0).astype(np.float32)
    return out


def composite_from_matrix(M: dict[str, np.ndarray]) -> np.ndarray:
    return S.composite_matrix(M)


def matched_rows(names: list[str], M: dict[str, np.ndarray],
                 groups: dict[str, np.ndarray], comp: np.ndarray) -> pd.DataFrame:
    n = len(names)
    diag = np.arange(n)
    rows = []
    for i, name in enumerate(names):
        row = {"name": name}
        for m in S.CHEAP_METRICS:
            row[m] = float(M[m][i, i])
        for g in S.CHEAP_GROUPS:
            row[f"grp_{g}"] = float(groups[g][i, i])
        row["composite"] = float(comp[i, i])
        other = np.delete(comp[i], i)
        row["retrieval_rank"] = int((other > comp[i, i]).sum()) + 1
        row["lift_vs_mismatched"] = float(comp[i, i] - other.mean()) if len(other) else 0.0
        rows.append(row)
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- #
# Robust cohort statistics
# --------------------------------------------------------------------------- #
def _mad(x: np.ndarray) -> float:
    med = np.median(x)
    return float(np.median(np.abs(x - med)))


def cohort_stats(values: dict[str, np.ndarray]) -> dict:
    out = {}
    for k, x in values.items():
        x = np.asarray(x, dtype=np.float64)
        x = x[np.isfinite(x)]
        if not len(x):
            out[k] = {}
            continue
        med, mad = float(np.median(x)), _mad(x)
        scale = mad if mad > 0 else (float(np.std(x)) or 1.0)
        out[k] = {
            "n": int(len(x)),
            "median": med,
            "mad": mad,
            "mean": float(np.mean(x)),
            "std": float(np.std(x, ddof=1)) if len(x) > 1 else 0.0,
            "min": float(np.min(x)),
            "max": float(np.max(x)),
            "p01": float(np.percentile(x, 1)),
            "p05": float(np.percentile(x, 5)),
            "p10": float(np.percentile(x, 10)),
            "p50": float(np.percentile(x, 50)),
            "p90": float(np.percentile(x, 90)),
            "p95": float(np.percentile(x, 95)),
            "p99": float(np.percentile(x, 99)),
            "robust_scale": scale,
        }
    return out


def robust_z(x: np.ndarray, med: float, scale: float) -> np.ndarray:
    if scale <= 0:
        return np.zeros_like(x, dtype=np.float64)
    return 0.6745 * (np.asarray(x, dtype=np.float64) - med) / scale


def stratum_medians(df: pd.DataFrame, value: str,
                    strata: dict[str, pd.Series]) -> dict:
    out = {}
    for label, labels in strata.items():
        frame = pd.DataFrame({"v": df[value].values, "s": labels.values})
        out[label] = {str(k): float(np.median(g["v"]))
                      for k, g in frame.groupby("s", dropna=False)}
    return out


# --------------------------------------------------------------------------- #
# Permutation test
# --------------------------------------------------------------------------- #
def paired_permutation(lift: np.ndarray, permutations: int = 10000,
                       seed: int = 20261111) -> dict:
    d = np.asarray(lift, dtype=np.float64)
    d = d[np.isfinite(d)]
    n = len(d)
    if n == 0:
        return {"n": 0, "mean_d": 0.0, "dz": 0.0, "p_value": 1.0,
                "frac_positive": 0.0, "permutations": permutations}
    mean_d = float(d.mean())
    sd = float(d.std(ddof=1)) if n > 1 else 0.0
    dz = mean_d / sd if sd > 0 else 0.0
    rng = np.random.default_rng(seed)
    signs = rng.choice(np.array([-1.0, 1.0]), size=(permutations, n))
    perm_means = (signs * d).mean(axis=1)
    # one-sided: matched beats chance
    p = float((1 + np.sum(perm_means >= mean_d)) / (permutations + 1))
    return {
        "n": int(n),
        "mean_d": mean_d,
        "sd_d": sd,
        "dz": float(dz),
        "p_value": p,
        "frac_positive": float((d > 0).mean()),
        "permutations": int(permutations),
        "seed": int(seed),
    }


# --------------------------------------------------------------------------- #
# Flags and decisions
# --------------------------------------------------------------------------- #
DEFAULT_THRESHOLDS = {
    "truncated": 0.80,
    "sparse": 0.60,
    "key_drift": 0.50,
    "tempo_drift": 0.50,
    "outlier_z": -3.0,
    "max_rank": 100,
    "min_lift": 0.10,
    "regen_deep": 0.65,
}

HARD_CODES = {"truncated", "sparse", "no-chords", "key-drift", "tempo-drift"}


def flag_cohort(frame: pd.DataFrame, stats: dict, thresholds: dict | None = None,
                missing: list[dict] | None = None,
                parse_errors: list[dict] | None = None) -> pd.DataFrame:
    """One row per track with reason codes, decision and human reasons."""
    t = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
    comp_stats = stats.get("composite", {})
    p05 = comp_stats.get("p05", 0.0)
    p10 = comp_stats.get("p10", 0.0)
    med = comp_stats.get("median", 0.0)
    scale = comp_stats.get("robust_scale", 1.0)

    rows = []
    if missing:
        for m in missing:
            rows.append({
                "name": m.get("name"), "status": "missing-output",
                "codes": "missing-output", "decision": "REVIEW",
                "reasons": m.get("error", "no verified transcript"),
                "composite": np.nan,
            })
    if parse_errors:
        for m in parse_errors:
            rows.append({
                "name": m.get("name"), "status": "parse-error",
                "codes": "parse-error", "decision": "REVIEW",
                "reasons": m.get("error", "parse_abc returned 0 notes"),
                "composite": np.nan,
            })

    for _, r in frame.iterrows():
        codes, reasons = [], []
        if r.get("duration_sim", 1.0) < t["truncated"]:
            codes.append("truncated")
            reasons.append(f"duration_sim {r['duration_sim']:.2f} < {t['truncated']}")
        note_ratio = r.get("note_count_ratio", 1.0)
        if note_ratio < t["sparse"]:
            codes.append("sparse")
            reasons.append(f"note ratio {note_ratio:.2f} < {t['sparse']}")
        if r.get("n_chords_out", 1) == 0:
            codes.append("no-chords")
            reasons.append("output has zero chord symbols")
        if r.get("key_sim", 1.0) < t["key_drift"]:
            codes.append("key-drift")
            reasons.append(f"key_sim {r['key_sim']:.2f} < {t['key_drift']}")
        if r.get("tempo_sim", 1.0) < t["tempo_drift"]:
            codes.append("tempo-drift")
            reasons.append(f"tempo_sim {r['tempo_sim']:.2f} < {t['tempo_drift']}")
        if r.get("n_notes_in", 1) == 0:
            codes.append("empty-input")
            reasons.append("input score has zero melody notes")
        z = float(robust_z(np.array([r["composite"]]), med, scale)[0])
        low_group = any(r.get(f"grp_{g}", 1.0) < stats.get(f"grp_{g}", {}).get("p05", -1)
                        for g in S.CHEAP_GROUPS)
        if r["composite"] < p05 or low_group or z < t["outlier_z"]:
            codes.append("cohort-outlier")
            reasons.append(f"cohort outlier (composite {r['composite']:.2f}, z {z:.2f})")
        if (r["retrieval_rank"] > t["max_rank"]
                or r["lift_vs_mismatched"] < t["min_lift"]):
            codes.append("not-distinctive")
            reasons.append(f"rank {r['retrieval_rank']}, lift {r['lift_vs_mismatched']:.3f}")

        hard = [c for c in codes if c in HARD_CODES]
        deep = r.get("deep_composite", np.nan)
        if hard and np.isfinite(deep) and deep < t["regen_deep"]:
            decision = "REGENERATE"
        elif "cohort-outlier" in codes or r["composite"] < p10:
            decision = "REVIEW"
        else:
            decision = "KEEP"
        rows.append({
            "name": r["name"], "status": "ok",
            "codes": ";".join(codes) or "-", "decision": decision,
            "reasons": "; ".join(reasons) or "within cohort norms",
            "composite": r["composite"], "composite_z": z,
            "retrieval_rank": r["retrieval_rank"],
            "lift_vs_mismatched": r["lift_vs_mismatched"],
        })

    out = pd.DataFrame(rows)
    if len(out) and "composite" in out:
        out = out.sort_values("composite", ascending=True, na_position="last")
    return out.reset_index(drop=True)


# --------------------------------------------------------------------------- #
# Rank correlation (audit)
# --------------------------------------------------------------------------- #
def _rankdata(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=np.float64)
    order = np.argsort(x, kind="mergesort")
    ranks = np.empty(len(x), dtype=np.float64)
    ranks[order] = np.arange(1, len(x) + 1, dtype=np.float64)
    # average ties
    sx = x[order]
    i = 0
    while i < len(sx):
        j = i + 1
        while j < len(sx) and sx[j] == sx[i]:
            j += 1
        if j - i > 1:
            ranks[order[i:j]] = (i + 1 + j) / 2.0
        i = j
    return ranks


def spearman(a, b) -> float:
    a, b = np.asarray(a, np.float64), np.asarray(b, np.float64)
    ok = np.isfinite(a) & np.isfinite(b)
    a, b = a[ok], b[ok]
    if len(a) < 3:
        return float("nan")
    ra, rb = _rankdata(a), _rankdata(b)
    if ra.std() == 0 or rb.std() == 0:
        return float("nan")
    return float(np.corrcoef(ra, rb)[0, 1])


def pearson(a, b) -> float:
    a, b = np.asarray(a, np.float64), np.asarray(b, np.float64)
    ok = np.isfinite(a) & np.isfinite(b)
    a, b = a[ok], b[ok]
    if len(a) < 2 or a.std() == 0 or b.std() == 0:
        return float("nan")
    return float(np.corrcoef(a, b)[0, 1])


def iqr(x) -> float:
    x = np.asarray(x, dtype=np.float64)
    x = x[np.isfinite(x)]
    if not len(x):
        return float("nan")
    return float(np.percentile(x, 75) - np.percentile(x, 25))


def atomic_write_json(path, obj) -> None:
    import json
    from pathlib import Path
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, sort_keys=True, default=float))
    tmp.replace(p)


def wilson_ci(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (max(0.0, centre - half), min(1.0, centre + half))
