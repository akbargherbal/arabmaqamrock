#!/usr/bin/env python3
"""Tests for the scalable ABC similarity core.

Run with::

    python3 -m pytest -q tests/test_abc_scale.py
"""
from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import pytest

from analysis import abc_scale as S
from analysis.vendor import abc_similarity as oracle

ABC_A = """X:1
T:test A
M:4/4
L:1/8
Q:1/4=120
K:C
V:Vocal
"C"z8|"F"z8|"G"z8|"C"z8|
V:Ins
C D E F G A B c|c B A G F E D C|C E G B d B G E|C4 z4|
"""

ABC_B = """X:2
T:test B
M:3/4
L:1/8
Q:1/4=90
K:G
V:Vocal
"G"z6|"D"z6|"Em"z6|
V:Ins
G A B c d e|f g a b c'|d'4 z2|
"""

ABC_CHORDLESS = """X:3
T:no chords
M:4/4
L:1/8
Q:1/4=100
K:Am
V:Ins
A B c d|e f g a|
"""


def _triplet():
    feats = [S.features_from_text(t) for t in (ABC_A, ABC_B, ABC_CHORDLESS)]
    FT = S.stack_features(feats)
    return feats, FT, S.cheap_matrices(FT), S.composite_matrix(S.cheap_matrices(FT))


def test_parser_and_features():
    f = S.features_from_text(ABC_A)
    assert f["n_notes"] > 0
    assert f["n_chords"] > 0
    assert f["total_sec"] > 0
    assert f["pc_hist"].shape == (12,)
    assert f["iv_hist"].shape == (25,)
    assert f["dur_hist"].shape == (16,)
    assert f["phases"].shape == (3, 8)


def test_identity_is_exactly_one():
    feats, _, M, comp = _triplet()
    for m in S.CHEAP_METRICS:
        d = np.diag(M[m])
        assert np.all(d == 1.0), (m, d)
    assert np.all(np.diag(comp) == 1.0)


def test_scalar_matrix_parity():
    feats, _, M, _ = _triplet()
    for i in range(len(feats)):
        for j in range(len(feats)):
            sc = S.cheap_scalar(feats[j], feats[i])
            for m in S.CHEAP_METRICS:
                assert abs(float(sc[m]) - float(M[m][i, j])) <= 1e-6, (m, i, j)


def test_chordless_identity_and_parity():
    f = S.features_from_text(ABC_CHORDLESS)
    sc = S.cheap_scalar(f, f)
    for m in S.CHEAP_METRICS:
        assert sc[m] == pytest.approx(1.0)


def test_metrics_are_bounded():
    _, _, M, comp = _triplet()
    for m in S.CHEAP_METRICS:
        assert np.all(M[m] >= 0.0)
        assert np.all(M[m] <= 1.0)
    assert np.all(comp >= 0.0) and np.all(comp <= 1.0)


def test_dissimilar_pair_below_identity():
    feats, _, M, _ = _triplet()
    # different key/tempo/meter should not be as similar as the identity
    assert M["composite"][0, 1] < 1.0 if "composite" in M else True
    comp = S.composite_matrix(M)
    assert comp[0, 1] < 1.0


def test_banded_dtw_identity_and_truncation():
    feats = S.features_from_text(ABC_A)
    a = S.chroma_frames(feats["score"], 0.5, "melody")
    b = S.chroma_frames(feats["score"], 0.5, "melody")
    assert S.banded_dtw(a, b) == pytest.approx(1.0, abs=1e-9)
    half = a[: max(1, len(a) // 2)]
    assert S.banded_dtw(a, half) < 0.9


def test_runtime_460_matrix_under_120s():
    """Build a synthetic 460-row feature table and time the matrix path."""
    base = S.features_from_text(ABC_A)
    rng = np.random.default_rng(0)
    feats = []
    for i in range(460):
        f = dict(base)
        f["tempo"] = float(base["tempo"] * (0.5 if i % 3 == 0 else 1.0))
        f["fifths"] = int(rng.integers(-6, 7))
        f["pc_hist"] = np.roll(base["pc_hist"], int(rng.integers(0, 12)))
        f["total_sec"] = float(base["total_sec"] * (0.8 + 0.4 * rng.random()))
        f["chord_shares"] = {k: v * (0.5 + rng.random())
                             for k, v in base["chord_shares"].items()}
        feats.append(f)
    t0 = time.monotonic()
    FT = S.stack_features(feats)
    M = S.cheap_matrices(FT)
    S.composite_matrix(M)
    elapsed = time.monotonic() - t0
    assert len(M["key_sim"]) == 460
    assert elapsed <= 120.0, elapsed
