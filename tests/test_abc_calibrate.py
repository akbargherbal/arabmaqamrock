#!/usr/bin/env python3
"""Tests for cohort calibration, flags and the permutation test."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from analysis import abc_calibrate as C
from analysis import abc_scale as S


def test_offdiag_mean_is_exact():
    M = np.array([[1.0, 0.2, 0.4],
                  [0.6, 1.0, 0.8],
                  [0.0, 0.5, 1.0]], dtype=np.float32)
    assert C.offdiag_mean(M) == pytest.approx((0.2 + 0.4 + 0.6 + 0.8 + 0.0 + 0.5) / 6)


def test_adjustment_is_clipped():
    rng = np.random.default_rng(0)
    M = {m: rng.random((4, 4)).astype(np.float32) for m in S.CHEAP_METRICS}
    for m in S.CHEAP_METRICS:
        np.fill_diagonal(M[m], 1.0)
    base = C.baseline_matrix(M)
    adj = C.adjusted(M, base)
    for m in S.CHEAP_METRICS:
        assert np.all(adj[m] >= 0)
        assert np.all(adj[m] <= 1)


def test_exact_rank_and_lift():
    comp = np.array([[1.0, 0.2, 0.3],
                     [0.9, 0.5, 0.4],
                     [0.1, 0.2, 1.0]], dtype=np.float32)
    M = {m: comp.copy() for m in S.CHEAP_METRICS}
    groups = {g: comp.copy() for g in S.CHEAP_GROUPS}
    rows = C.matched_rows(["a", "b", "c"], M, groups, comp)
    assert rows["retrieval_rank"].tolist() == [1, 2, 1]
    assert rows.loc[1, "lift_vs_mismatched"] == pytest.approx(0.5 - (0.9 + 0.4) / 2)


def test_sign_flip_permutation_detects_positive_lift():
    rng = np.random.default_rng(1)
    d = 0.2 + 0.02 * rng.standard_normal(200)
    res = C.paired_permutation(d, permutations=2000, seed=2)
    assert res["mean_d"] > 0
    assert res["dz"] > 5
    assert res["p_value"] < 0.01
    assert res["frac_positive"] == pytest.approx(1.0)


def test_permutation_null_is_not_significant():
    rng = np.random.default_rng(3)
    d = 0.02 * rng.standard_normal(200)
    res = C.paired_permutation(d, permutations=2000, seed=4)
    assert res["p_value"] > 0.05


def test_spearman_perfect_and_monotone():
    a = np.array([1, 2, 3, 4, 5], float)
    assert C.spearman(a, a) == pytest.approx(1.0)
    assert C.spearman(a, a ** 3) == pytest.approx(1.0)
    assert C.spearman(a, -a) == pytest.approx(-1.0)


def test_flag_reason_codes():
    n = 20
    rng = np.random.default_rng(5)
    comp = np.linspace(0.6, 0.95, n)
    frame = pd.DataFrame({
        "name": [f"t{i:02d}" for i in range(n)],
        "composite": comp,
        "grp_global": comp, "grp_harmony": comp,
        "grp_melody": comp, "grp_rhythm": comp,
        "duration_sim": np.full(n, 0.95),
        "note_count_ratio": np.full(n, 0.95),
        "n_chords_out": np.full(n, 10),
        "key_sim": np.full(n, 0.9),
        "tempo_sim": np.full(n, 0.9),
        "retrieval_rank": np.ones(n, dtype=int),
        "lift_vs_mismatched": np.full(n, 0.3),
        "deep_composite": np.full(n, 0.8),
    })
    # force one row into each hard code
    frame.loc[0, "duration_sim"] = 0.5
    frame.loc[1, "note_count_ratio"] = 0.2
    frame.loc[2, "n_chords_out"] = 0
    frame.loc[3, "key_sim"] = 0.2
    frame.loc[4, "tempo_sim"] = 0.2
    stats = C.cohort_stats({k: frame[k].values for k in
                            ("composite",) + tuple(f"grp_{g}" for g in S.CHEAP_GROUPS)})
    flags = C.flag_cohort(frame, stats)
    by = flags.set_index("name")
    assert "truncated" in by.loc["t00", "codes"]
    assert "sparse" in by.loc["t01", "codes"]
    assert "no-chords" in by.loc["t02", "codes"]
    assert "key-drift" in by.loc["t03", "codes"]
    assert "tempo-drift" in by.loc["t04", "codes"]
    # hard invariant + deep 0.8 (>= 0.65) is not REGENERATE by itself
    assert by.loc["t00", "decision"] in ("KEEP", "REVIEW")


def test_flag_regenerate_needs_deep_below_threshold():
    frame = pd.DataFrame({
        "name": ["x"], "composite": [0.8],
        "grp_global": [0.8], "grp_harmony": [0.8],
        "grp_melody": [0.8], "grp_rhythm": [0.8],
        "duration_sim": [0.5], "note_count_ratio": [1.0],
        "n_chords_out": [5], "key_sim": [1.0], "tempo_sim": [1.0],
        "retrieval_rank": [1], "lift_vs_mismatched": [0.3],
        "deep_composite": [0.4],
    })
    stats = C.cohort_stats({k: frame[k].values for k in
                            ("composite",) + tuple(f"grp_{g}" for g in S.CHEAP_GROUPS)})
    flags = C.flag_cohort(frame, stats)
    assert flags.loc[0, "decision"] == "REGENERATE"
