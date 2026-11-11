#!/usr/bin/env python3
"""CLI for the YT500 input-vs-output ABC similarity study.

Subcommands
-----------
self-test    identity + scalar/matrix parity + N^2 runtime on local ABC files
build-pairs  assemble and validate the input/output manifest
run          full cohort analysis (all-pairs matrix, calibration, audit, report)
report       re-render summary.md from an existing run directory

The dataset itself is never modified.  See
``docs/plans/yt500-instrumental-abc-similarity.md``.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

# Allow `python3 analysis/run_yt500_similarity.py` from the repo root.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis import abc_scale as S            # noqa: E402
from analysis import abc_calibrate as C        # noqa: E402
from analysis.vendor import abc_similarity as oracle  # noqa: E402


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def load_inventory(path: Path | None) -> list[dict]:
    if path is None or not Path(path).is_file():
        return []
    obj = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(obj, dict):
        for key in ("tracks", "inventory", "rows"):
            if isinstance(obj.get(key), list):
                return obj[key]
        return [dict(v, name=v.get("name", k)) for k, v in obj.items()
                if isinstance(v, dict)]
    return obj


def abc_dir_map(directory: Path) -> dict[str, Path]:
    """Map track name -> input ABC.  Accepts the role-labelled name first."""
    out = {}
    directory = Path(directory)
    if not directory.is_dir():
        return out
    for p in sorted(directory.glob("*.input.abc")):
        out[p.name[: -len(".input.abc")]] = p
    for p in sorted(directory.glob("*.abc")):
        out.setdefault(p.stem, p)
    for p in sorted(directory.glob("*/score.abc")):
        out.setdefault(p.parent.name, p)
    return out


def transcript_map(directory: Path) -> dict[str, tuple[Path, Path | None]]:
    out = {}
    directory = Path(directory)
    if not directory.is_dir():
        return out
    for p in sorted(directory.glob("*/score.abc")):
        meta = p.parent / "meta.json"
        out[p.parent.name] = (p, meta if meta.is_file() else None)
    for p in sorted(directory.glob("*.abc")):
        out.setdefault(p.stem, (p, None))
    return out


def valid_abc(text: str) -> bool:
    import re
    return (len(text.strip()) >= 8
            and re.search(r"(?m)^\s*X\s*:", text) is not None
            and re.search(r"(?m)^\s*K\s*:", text) is not None)


def json_default(o):
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, Path):
        return str(o)
    return str(o)


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, sort_keys=True, default=json_default))
    tmp.replace(path)


def git_sha() -> str:
    import subprocess
    try:
        return subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"],
                              capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        return "unknown"


# --------------------------------------------------------------------------- #
# Pairs assembly
# --------------------------------------------------------------------------- #
def _rel(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _resolve(root: Path, value: str | None) -> Path:
    if not value:
        raise ValueError("missing path")
    p = Path(value)
    if p.is_absolute():
        return p
    candidate = Path(root) / p
    if candidate.exists():
        return candidate
    if p.exists():
        return p
    return candidate


def build_pairs(input_dir: Path, transcripts_dir: Path,
                inventory_path: Path | None,
                output_dir: Path | None = None,
                work_root: Path | None = None
                ) -> tuple[list[dict], list[dict], list[dict], list[str]]:
    inputs = abc_dir_map(input_dir)
    transcripts = transcript_map(transcripts_dir)
    inv = load_inventory(inventory_path)
    names = [r["name"] for r in inv] or sorted(inputs)
    inv_by = {r["name"]: r for r in inv}
    work_root = Path(work_root) if work_root else Path(input_dir).parent
    output_dir = Path(output_dir) if output_dir else work_root / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    pairs, missing, parse_errors, hash_violations = [], [], [], []
    for name in names:
        rec = inv_by.get(name, {})
        ip = inputs.get(name)
        tp = transcripts.get(name)
        row = {
            "name": name,
            "role": "matched_pair",
            "input_abc": _rel(ip, work_root) if ip else None,
            "output_abc": None,
            "status": "ok",
            "error": None,
            "input_sha256": sha256_file(ip) if ip else None,
            "output_sha256": None,
            "audio_sha256": None,
            "nominal_s": rec.get("nominal_s"),
            "wav_s": rec.get("wav_s"),
            "tier": rec.get("tier"),
            "country": rec.get("country"),
            "duration_quartile": rec.get("duration_quartile"),
        }
        if ip is None or not ip.is_file():
            row["status"] = "missing-input"
            row["error"] = "input <name>.input.abc missing"
        elif tp is None:
            row["status"] = "missing-output"
            row["error"] = "no transcript score.abc"
        else:
            text = read_text(tp[0])
            out_sha = sha256_file(tp[0])
            row["output_sha256"] = out_sha
            if not valid_abc(text):
                row["status"] = "parse-error"
                row["error"] = "output is not valid ABC (X:/K: missing)"
            elif tp[1] is not None:
                try:
                    meta = json.loads(tp[1].read_text(encoding="utf-8"))
                except Exception as exc:  # noqa: BLE001
                    meta = {}
                    row["error"] = f"meta.json unreadable: {exc}"
                row["audio_sha256"] = meta.get("source_wav_sha256")
                if meta.get("status") not in (None, "ok"):
                    row["status"] = "parse-error"
                    row["error"] = f"transcript meta status={meta.get('status')!r}"
                elif meta.get("abc_sha256") and meta["abc_sha256"] != out_sha:
                    row["status"] = "parse-error"
                    row["error"] = "score.abc does not match meta.abc_sha256"

        if row["status"] == "ok":
            try:
                score = oracle.parse_abc(read_text(tp[0]))
            except Exception as exc:  # noqa: BLE001
                score = None
                row["error"] = f"parse exception: {exc}"
            if score is None or not score.notes:
                row["status"] = "parse-error"
                row["error"] = row["error"] or "parse_abc returned 0 notes"

        if row["status"] == "ok":
            # Publish-side local copy under the role-labelled name.
            dest = output_dir / f"{name}.output.abc"
            tmp = dest.with_suffix(".abc.tmp")
            tmp.write_bytes(tp[0].read_bytes())
            tmp.replace(dest)
            row["output_abc"] = _rel(dest, work_root)
            row["output_sha256"] = sha256_file(dest)
            if not row["input_sha256"] or row["input_sha256"] == row["output_sha256"]:
                hash_violations.append(name)
                row["status"] = "hash-collision"
                row["error"] = "input_sha256 == output_sha256 (sides swapped?)"

        pairs.append(row)
        if row["status"] == "missing-output":
            missing.append({"name": name, "error": row["error"]})
        elif row["status"] == "parse-error":
            parse_errors.append({"name": name, "error": row["error"]})
    return pairs, missing, parse_errors, hash_violations


# --------------------------------------------------------------------------- #
# self-test
# --------------------------------------------------------------------------- #
def cmd_self_test(args) -> int:
    src = Path(args.inputs)
    files = sorted(Path(src).glob("*.abc")) if src.is_dir() else [Path(src)]
    if not files:
        print(f"self-test: no .abc files under {src}", file=sys.stderr)
        return 2
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    t0 = time.monotonic()
    feats, parse_fail, empty_scores = [], [], []
    for p in files:
        try:
            sc = oracle.parse_abc(read_text(p))
            if not sc.notes:
                # No melody notes (rests/chords only): features are still
                # well-defined, so include it and record the condition.
                empty_scores.append(str(p))
            feats.append(S.score_features(sc))
        except Exception as exc:  # noqa: BLE001
            parse_fail.append({"file": str(p), "error": str(exc)})
        if time.monotonic() - t0 > args.feature_budget and len(feats) >= 3:
            print(f"self-test: feature budget reached ({len(feats)} scores)", flush=True)
            break
    parse_seconds = time.monotonic() - t0
    if len(feats) < 2:
        print("self-test: fewer than 2 parseable scores", file=sys.stderr)
        return 2

    t0 = time.monotonic()
    FT = S.stack_features(feats)
    M = S.cheap_matrices(FT)
    comp = S.composite_matrix(M)
    matrix_seconds = time.monotonic() - t0
    n = len(feats)
    names = [p.stem for p in files[:n]]

    # (a) identity
    identity = {}
    for m in S.CHEAP_METRICS:
        d = np.diag(M[m])
        identity[m] = {"min": float(d.min()), "max": float(d.max()),
                       "all_one": bool(np.all(d == 1.0))}
    identity_ok = all(v["all_one"] for v in identity.values()) and bool(np.all(np.diag(comp) == 1.0))

    # (b) scalar <-> matrix parity
    rng = np.random.default_rng(args.seed)
    pairs = set()
    if n <= 40:
        pairs = {(i, j) for i in range(n) for j in range(n)}
    else:
        while len(pairs) < min(args.parity_pairs, n * n):
            pairs.add((int(rng.integers(n)), int(rng.integers(n))))
    parity = {m: 0.0 for m in S.CHEAP_METRICS}
    for i, j in pairs:
        sc = S.cheap_scalar(feats[j], feats[i])   # orig=j, inst=i
        for m in S.CHEAP_METRICS:
            parity[m] = max(parity[m], abs(float(sc[m]) - float(M[m][i, j])))
    parity_max = max(parity.values())

    deep = None
    if args.pairs and Path(args.pairs).is_file():
        deep = deep_parity(Path(args.pairs))

    gates = {
        "identity_all_one": bool(identity_ok),
        "parity_within_1e6": bool(parity_max <= 1e-6),
        f"matrix_{n}x{n}_under_120s": bool(matrix_seconds <= 120.0),
    }
    result = {
        "n_scores": n,
        "files": [str(f) for f in files[:n]],
        "parse_failures": parse_fail,
        "empty_scores": empty_scores,
        "feature_seconds": parse_seconds,
        "matrix_seconds": matrix_seconds,
        "identity": identity,
        "parity": parity,
        "parity_max": parity_max,
        "parity_pairs": len(pairs),
        "gates": gates,
        "passed": all(gates.values()),
        "deep_parity": deep,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "commit": git_sha(),
    }
    write_json(out / "self_test.json", result)

    lines = [
        "# ABC scale self-test", "",
        f"- scores: **{n}** (parse failures: {len(parse_fail)})",
        f"- feature extraction: {parse_seconds:.2f} s",
        f"- {n}x{n} matrix: **{matrix_seconds:.2f} s**",
        f"- identity all 1.0: **{identity_ok}**",
        f"- scalar->matrix parity max: **{parity_max:.3e}** ({len(pairs)} pairs)",
        "",
        "| gate | pass |", "|---|---|",
    ] + [f"| {k} | {v} |" for k, v in gates.items()]
    if deep:
        lines += ["", f"- deep parity: rho={deep.get('spearman')} r={deep.get('pearson')} "
                      f"(n={deep.get('n')})"]
    lines += ["", f"Overall: **{'PASS' if result['passed'] else 'FAIL'}**", ""]
    (out / "self_test.md").write_text("\n".join(lines))

    print("\n".join(lines))
    return 0 if result["passed"] else 1


def deep_parity(pairs_path: Path) -> dict:
    rows = json.loads(pairs_path.read_text(encoding="utf-8"))
    cheap, deep = [], []
    for r in rows:
        if not r.get("input_abc") or not r.get("output_abc"):
            continue
        try:
            fo = S.features_from_file(r["input_abc"])
            fi = S.features_from_file(r["output_abc"])
        except Exception:  # noqa: BLE001
            continue
        cr = S.cheap_scalar(fo, fi)
        cheap.append(S.composite_from_metrics(cr))
        deep.append(float(oracle.composite(pd.Series(oracle.compare_features(fo, fi)))))
    return {"n": len(cheap), "spearman": C.spearman(cheap, deep),
            "pearson": C.pearson(cheap, deep), "cheap": cheap, "deep": deep}


# --------------------------------------------------------------------------- #
# run
# --------------------------------------------------------------------------- #
def _stratified_audit(comp: np.ndarray, n_audit: int) -> list[int]:
    order = np.argsort(comp)
    bands = np.array_split(order, 3)
    per = max(1, n_audit // 3)
    picked = []
    for band in bands:
        if len(band) <= per:
            picked.extend(band.tolist())
        else:
            idx = np.linspace(0, len(band) - 1, per).round().astype(int)
            picked.extend(band[idx].tolist())
    return sorted(set(picked))


def _production_parity(feats_in: list[dict], feats_out: list[dict],
                       M: dict[str, np.ndarray], seed: int,
                       n_pairs: int = 50) -> float:
    """Scalar/matrix parity on real input/output rows (production guard)."""
    n = len(feats_in)
    rng = np.random.default_rng(seed)
    pairs = {(i, i) for i in range(n)}
    while len(pairs) < min(n_pairs, n * n):
        pairs.add((int(rng.integers(n)), int(rng.integers(n))))
    worst = 0.0
    for i, j in pairs:
        sc = S.cheap_scalar(feats_in[j], feats_out[i])
        for m in S.CHEAP_METRICS:
            worst = max(worst, abs(float(sc[m]) - float(M[m][i, j])))
    return worst


def cmd_run(args) -> int:
    t_start = time.monotonic()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    work_root = Path(args.work) if args.work else Path(args.input_dir).parent
    pairs, missing, parse_errors, hash_violations = build_pairs(
        Path(args.input_dir), Path(args.transcripts), Path(args.inventory),
        output_dir=Path(args.output_dir) if args.output_dir else work_root / "output",
        work_root=work_root)
    write_json(work_root / "pairs.json",
               {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "count": len(pairs), "hash_violations": hash_violations,
                "pairs": pairs})
    if hash_violations:
        print(f"run: ABORT — input_sha256 == output_sha256 for {len(hash_violations)} "
              f"rows: {hash_violations[:5]}", file=sys.stderr)
        return 2

    ok = [r for r in pairs if r["status"] == "ok"]
    if len(ok) < 3:
        print(f"run: only {len(ok)} valid pairs; need >=3", file=sys.stderr)
        return 2
    names = [r["name"] for r in ok]
    inv_by = {r["name"]: r for r in ok}

    # --- parse + features -------------------------------------------------- #
    feats_in, feats_out = [], []
    cohort, parse_fail = [], list(parse_errors)
    for r in ok:
        try:
            fi_score = oracle.parse_abc(read_text(_resolve(work_root, r["input_abc"])))
            fo_score = oracle.parse_abc(read_text(_resolve(work_root, r["output_abc"])))
        except Exception as exc:  # noqa: BLE001
            parse_fail.append({"name": r["name"], "error": f"parse exception: {exc}"})
            continue
        if not fo_score.notes:
            parse_fail.append({"name": r["name"], "error": "output parse: 0 notes"})
            continue
        cohort.append(r)
        feats_in.append(S.score_features(fi_score))
        feats_out.append(S.score_features(fo_score))
    if len(cohort) < 3:
        print("run: fewer than 3 parseable pairs", file=sys.stderr)
        return 2
    names = [r["name"] for r in cohort]
    N = len(cohort)
    print(f"cohort {N} / {len(pairs)} (missing={len(missing)}, parse errors={len(parse_fail)})",
          flush=True)

    # --- matrices ---------------------------------------------------------- #
    # Stack outputs and inputs into one table (2N rows) with a shared chord
    # vocabulary, compute the full metric grid, then keep the output x input
    # block.  Every metric formula is therefore identical to the scalar path.
    t0 = time.monotonic()
    FT_all = S.stack_features(feats_out + feats_in)
    M_all = S.cheap_matrices(FT_all)
    M = {m: np.ascontiguousarray(M_all[m][:N, N:]) for m in S.CHEAP_METRICS}
    comp = S.composite_matrix(M)
    groups = S.group_matrices(M)
    matrix_seconds = time.monotonic() - t0
    parity_max = _production_parity(feats_in, feats_out, M, args.seed)
    if parity_max > 1e-6:
        print(f"run: ABORT — scalar/matrix parity {parity_max:.3e} > 1e-6", file=sys.stderr)
        return 3
    print(f"features+matrix {matrix_seconds:.1f}s  parity={parity_max:.2e}", flush=True)

    # --- calibration ------------------------------------------------------- #
    base = C.baseline_matrix(M)
    adj = C.adjusted(M, base)
    comp_adj = S.composite_matrix(adj)
    matched = C.matched_rows(names, M, groups, comp)
    matched["composite_adj"] = np.diag(comp_adj)
    matched["n_notes_in"] = [f["n_notes"] for f in feats_in]
    matched["n_notes_out"] = [f["n_notes"] for f in feats_out]
    matched["note_count_ratio"] = matched["n_notes_out"] / np.maximum(matched["n_notes_in"], 1)
    matched["n_chords_in"] = [f["n_chords"] for f in feats_in]
    matched["n_chords_out"] = [f["n_chords"] for f in feats_out]
    matched["total_sec_in"] = [f["total_sec"] for f in feats_in]
    matched["total_sec_out"] = [f["total_sec"] for f in feats_out]
    matched["input_sha256"] = [r.get("input_sha256") for r in cohort]
    matched["output_sha256"] = [r.get("output_sha256") for r in cohort]
    matched["audio_sha256"] = [r.get("audio_sha256") for r in cohort]
    matched["tier"] = [r.get("tier") for r in cohort]
    matched["country"] = [r.get("country") for r in cohort]
    matched["duration_quartile"] = [r.get("duration_quartile") for r in cohort]
    matched["deep_composite"] = np.nan

    values = {m: np.diag(M[m]) for m in S.CHEAP_METRICS}
    values.update({f"grp_{g}": np.diag(groups[g]) for g in S.CHEAP_GROUPS})
    values["composite"] = np.diag(comp)
    values["composite_adj"] = np.diag(comp_adj)
    stats = C.cohort_stats(values)
    perm = C.paired_permutation(matched["lift_vs_mismatched"].values, args.permutations)

    strata = {}
    for label, col in (("tier", "tier"), ("country", "country"),
                       ("duration_quartile", "duration_quartile")):
        strata[label] = C.stratum_medians(
            matched, "composite", {label: matched[col]}).get(label, {})
    stats["_permutation"] = perm
    stats["_strata"] = strata

    # --- flags (pre-escalation) ------------------------------------------- #
    flags = C.flag_cohort(matched, stats, missing=missing, parse_errors=parse_fail)
    escalate_names = set(
        flags.loc[(flags["codes"].str.contains("truncated|sparse|no-chords|key-drift|"
                                               "tempo-drift|cohort-outlier"))
                  & (flags["status"] == "ok"), "name"])
    print(f"escalating {len(escalate_names)} flagged tracks", flush=True)

    # --- escalation ------------------------------------------------------- #
    esc_rows = []
    idx_by_name = {n: i for i, n in enumerate(names)}
    deep_by_name = {}
    t0 = time.monotonic()
    for name in sorted(escalate_names):
        i = idx_by_name[name]
        try:
            deep = oracle.compare_features(feats_in[i], feats_out[i])
            deep_comp = float(oracle.composite(pd.Series(deep)))
            band_mel = S.banded_dtw(S.chroma_frames(feats_in[i]["score"], 2.0, "melody"),
                                    S.chroma_frames(feats_out[i]["score"], 2.0, "melody"))
            band_ch = S.banded_dtw(S.chroma_frames(feats_in[i]["score"], 2.0, "chord"),
                                   S.chroma_frames(feats_out[i]["score"], 2.0, "chord"))
            deep_by_name[name] = deep_comp
            matched.loc[i, "deep_composite"] = deep_comp
            row = {"name": name, "deep_composite": deep_comp,
                   "banded_melody_dtw": band_mel, "banded_chord_dtw": band_ch}
            row.update({m: float(deep[m]) for m in oracle.METRICS})
            esc_rows.append(row)
        except Exception as exc:  # noqa: BLE001
            esc_rows.append({"name": name, "deep_composite": np.nan,
                             "banded_melody_dtw": np.nan,
                             "banded_chord_dtw": np.nan,
                             "error": str(exc)})
    escalation = pd.DataFrame(esc_rows)
    escalation_seconds = time.monotonic() - t0

    # final decisions now that deep composites exist
    flags = C.flag_cohort(matched, stats, missing=missing, parse_errors=parse_fail)

    # --- audit ------------------------------------------------------------- #
    t0 = time.monotonic()
    audit = audit_tracks(matched, feats_in, feats_out, names, args.audit, args.seed)
    if audit["n"] < (args.audit or 0) and audit["n"] > 0:
        pass
    if args.audit and (not np.isfinite(audit["spearman"]) or audit["spearman"] < 0.85):
        # widen once, as the plan permits
        audit = audit_tracks(matched, feats_in, feats_out, names, 60, args.seed)
    audit_seconds = time.monotonic() - t0
    audit_df = pd.DataFrame(audit.pop("rows"))

    # --- write tables ------------------------------------------------------ #
    matched.to_csv(out / "matched_pairs_scores.csv", index=False)
    flags.to_csv(out / "flags.csv", index=False)
    if len(escalation):
        escalation.to_csv(out / "escalation.csv", index=False)
    if len(audit_df):
        audit_df.to_csv(out / "audit_30.csv", index=False)
    pd.Series(base).rename("mismatched_mean").to_csv(out / "baseline_mismatched_mean.csv")

    all_pairs_rows = N * N
    write_all_pairs(out / "all_pairs.parquet", names, M, comp, groups,
                    block=args.blocks)

    stats["_audit"] = audit
    stats["_cohort_size"] = N
    stats["_total_pairs"] = len(pairs)
    stats["_missing"] = missing
    stats["_parse_errors"] = parse_fail
    stats["_matrix_seconds"] = matrix_seconds
    stats["_parity_max"] = parity_max
    stats["_escalation_seconds"] = escalation_seconds
    stats["_all_pairs_rows"] = all_pairs_rows
    stats["_commit"] = git_sha()
    stats["_generated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    write_json(out / "cohort_stats.json", stats)

    # cohort.json / failures.json next to pairs
    work = work_root
    write_json(work / "cohort.json",
               {"cohort_size": N, "total": len(pairs),
                "missing": missing, "parse_errors": parse_fail,
                "names": names})
    write_json(work / "failures.json",
               {"missing": missing, "parse_errors": parse_fail,
                "total": len(pairs), "cohort": N})

    plots(out, matched, flags, comp)
    summary = render_summary(out, matched, flags, stats, audit, escalation, names)
    (out / "summary.md").write_text(summary)

    print(f"\ncohort={N}  median composite={stats['composite']['median']:.3f}  "
          f"IQR={C.iqr(matched['composite']):.3f}")
    print(f"effect: mean d={perm['mean_d']:.3f}  dz={perm['dz']:.3f}  "
          f"p={perm['p_value']:.4g}  frac d>0={perm['frac_positive']:.3f}")
    print(f"rank-1: {(matched['retrieval_rank'] == 1).mean() * 100:.1f}%  "
          f"audit rho={audit['spearman']:.3f} n={audit['n']}")
    reasons = flags["codes"].str.split(";").explode().value_counts()
    print("reason codes:", ", ".join(f"{k}={v}" for k, v in reasons.items()))
    print(f"total {time.monotonic() - t_start:.1f}s -> {out}")
    return 0


def write_all_pairs(path: Path, names: list[str], M: dict, comp: np.ndarray,
                    groups: dict, block: int = 256) -> None:
    """Write the full N x N table, chunking rows if N is large."""
    N = len(names)
    names_arr = np.array(names, dtype=object)
    if N <= 2000:
        cols = {m: M[m].ravel().astype(np.float32) for m in S.CHEAP_METRICS}
        cols["composite"] = comp.ravel().astype(np.float32)
        for g in S.CHEAP_GROUPS:
            cols[g] = groups[g].ravel().astype(np.float32)
        df = pd.DataFrame(cols)
        df.insert(0, "input_id", np.tile(names_arr, N))
        df.insert(0, "output_id", np.repeat(names_arr, N))
        df["matched"] = df["output_id"].values == df["input_id"].values
        df.to_parquet(path, index=False)
        return

    import pyarrow as pa
    import pyarrow.parquet as pq
    writer = None
    try:
        for s in range(0, N, block):
            e = min(s + block, N)
            cols = {m: M[m][s:e].ravel().astype(np.float32) for m in S.CHEAP_METRICS}
            cols["composite"] = comp[s:e].ravel().astype(np.float32)
            for g in S.CHEAP_GROUPS:
                cols[g] = groups[g][s:e].ravel().astype(np.float32)
            df = pd.DataFrame(cols)
            df.insert(0, "input_id", np.tile(names_arr, e - s))
            df.insert(0, "output_id", np.repeat(names_arr[s:e], N))
            df["matched"] = df["output_id"].values == df["input_id"].values
            table = pa.Table.from_pandas(df, preserve_index=False)
            if writer is None:
                writer = pq.ParquetWriter(path, table.schema)
            writer.write_table(table)
    finally:
        if writer is not None:
            writer.close()


def audit_tracks(matched: pd.DataFrame, feats_in: list[dict], feats_out: list[dict],
                 names: list[str], n_audit: int, seed: int) -> dict:
    if not n_audit or n_audit <= 0:
        return {"n": 0, "spearman": float("nan"), "pearson": float("nan"), "rows": []}
    idx_by = {n: i for i, n in enumerate(names)}
    comp = matched.set_index("name").loc[names, "composite"].values
    picked = _stratified_audit(np.asarray(comp), n_audit)
    rows, cheap, deep = [], [], []
    for i in picked:
        name = names[i]
        try:
            r = oracle.compare_features(feats_in[i], feats_out[i])
            d = float(oracle.composite(pd.Series(r)))
        except Exception as exc:  # noqa: BLE001
            rows.append({"name": name, "cheap_composite": float(comp[i]),
                         "deep_composite": np.nan, "error": str(exc)})
            continue
        c = float(comp[i])
        cheap.append(c)
        deep.append(d)
        row = {"name": name, "cheap_composite": c, "deep_composite": d,
               "delta": c - d}
        row.update({m: float(r[m]) for m in oracle.METRICS})
        rows.append(row)
    return {"n": len(cheap), "spearman": C.spearman(cheap, deep),
            "pearson": C.pearson(cheap, deep), "rows": rows}


# --------------------------------------------------------------------------- #
# Plot + summary
# --------------------------------------------------------------------------- #
def plots(out: Path, matched: pd.DataFrame, flags: pd.DataFrame,
          comp: np.ndarray) -> None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:  # noqa: BLE001
        return
    fig, ax = plt.subplots(2, 2, figsize=(12, 9))
    ax[0, 0].hist(matched["composite"], bins=30, color="#4c72b0", alpha=.85)
    ax[0, 0].axvline(matched["composite"].median(), color="k", ls="--",
                     label=f"median {matched['composite'].median():.3f}")
    ax[0, 0].set_title("Matched composite")
    ax[0, 0].set_xlabel("composite")
    ax[0, 0].legend()
    for g in S.CHEAP_GROUPS:
        ax[0, 1].hist(matched[f"grp_{g}"], bins=25, alpha=.45, label=g)
    ax[0, 1].set_title("Group scores")
    ax[0, 1].legend(fontsize=8)
    ax[1, 0].hist(matched["retrieval_rank"], bins=40, color="#dd8452")
    ax[1, 0].set_title("Retrieval rank (1 = own input)")
    ax[1, 0].set_xlabel("rank")
    off = comp[~np.eye(len(comp), dtype=bool)]
    ax[1, 1].hist(off, bins=40, alpha=.55, label="mismatched", color="#999999")
    ax[1, 1].hist(np.diag(comp), bins=40, alpha=.75, label="matched", color="#55a868")
    ax[1, 1].set_title("Matched vs mismatched")
    ax[1, 1].legend()
    fig.tight_layout()
    fig.savefig(out / "distributions.png", dpi=140)
    plt.close(fig)


def render_summary(out: Path, matched: pd.DataFrame, flags: pd.DataFrame,
                   stats: dict, audit: dict, escalation: pd.DataFrame,
                   names: list[str]) -> str:
    comp = matched["composite"]
    perm = stats["_permutation"]
    ranks = matched["retrieval_rank"]
    reasons = flags["codes"].str.split(";").explode().value_counts()
    dec = flags["decision"].value_counts()
    lines = [
        "# YT500 instrumental — input-vs-output ABC similarity", "",
        "**Sides:** `input` = the conditioning score "
        "(`DATASET/yt500_instrumental/tracks/<name>/score.abc`, staged as "
        "`<name>.input.abc`); `output` = the SheetSage2 transcript of the "
        "generated audio (published as `<name>.output.abc`). No deliverable is "
        "named just `score`.", "",
        f"Generated {stats.get('_generated_at')} from commit `{stats.get('_commit')}`.",
        "",
        "## Cohort", "",
        f"- cohort: **{stats.get('_cohort_size')}** / {stats.get('_total_pairs', stats.get('_cohort_size', 0))} tracks",
        f"- missing output: **{len(stats.get('_missing', []))}**, parse errors: **{len(stats.get('_parse_errors', []))}**",
        f"- all-pairs rows: **{stats.get('_all_pairs_rows'):,}**",
        f"- feature+matrix time: {stats.get('_matrix_seconds', 0):.1f} s; escalation {stats.get('_escalation_seconds', 0):.1f} s; "
        f"scalar/matrix parity max {stats.get('_parity_max', 0):.2e}",
        "",
        "## Headline numbers", "",
        f"- median composite: **{comp.median():.3f}** (IQR {C.iqr(comp):.3f})",
    ]
    for g in S.CHEAP_GROUPS:
        lines.append(f"- {g}: median {matched[f'grp_{g}'].median():.3f}")
    lines += [
        f"- matched − chance: mean d = **{perm['mean_d']:.3f}**, Cohen dz = **{perm['dz']:.2f}**, "
        f"sign-flip p = **{perm['p_value']:.4g}** ({perm['permutations']:,} draws), "
        f"fraction d>0 = **{perm['frac_positive']:.1%}**",
        f"- retrieval rank 1: **{(ranks == 1).mean():.1%}** ({int((ranks == 1).sum())}/{len(ranks)}); "
        f"rank ≤ 10: {(ranks <= 10).mean():.1%}",
        f"- decisions: " + ", ".join(f"{k}={v}" for k, v in dec.items()),
        "",
        "## Reason codes", "",
        "| code | tracks |", "|---|---:|",
    ]
    lines += [f"| {k} | {v} |" for k, v in reasons.items()]
    lines += ["", "## Worst 20 matched tracks", "",
              "| name | composite | rank | lift | codes |",
              "|---|---:|---:|---:|---|"]
    for _, r in flags.head(20).iterrows():
        lines.append(f"| {r['name']} | {r.get('composite', float('nan')):.3f} | "
                     f"{r.get('retrieval_rank', 0)} | {r.get('lift_vs_mismatched', 0):.3f} | "
                     f"{r['codes']} |")
    lines += ["", "## Strata (median composite)", ""]
    for label, table in stats.get("_strata", {}).items():
        lines.append(f"- **{label}**: " + ", ".join(
            f"{k}={v:.3f}" for k, v in sorted(table.items())))
    lines += [
        "", "## Deep audit", "",
        f"- n = {audit.get('n')}, Spearman ρ = **{audit.get('spearman'):.3f}**, "
        f"Pearson r = **{audit.get('pearson'):.3f}** (gate ρ ≥ 0.85)",
        f"- escalated tracks: {len(escalation)}",
        "",
        "## Reproduce", "",
        "```bash",
        "python3 analysis/run_yt500_similarity.py run \\",
        "  --inputs work/yt500_abc/inputs --transcripts work/yt500_abc/transcripts \\",
        "  --inventory work/yt500_abc/inventory.json --out work/yt500_abc/similarity \\",
        "  --audit 30 --permutations 10000",
        "```",
        "",
    ]
    return "\n".join(lines) + "\n"


def cmd_build_pairs(args) -> int:
    work_root = Path(args.work) if args.work else Path(args.input_dir).parent
    pairs, missing, parse_errors, hash_violations = build_pairs(
        Path(args.input_dir), Path(args.transcripts), Path(args.inventory),
        output_dir=Path(args.output_dir) if args.output_dir else work_root / "output",
        work_root=work_root)
    out = Path(args.out)
    write_json(out, {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                     "count": len(pairs), "hash_violations": hash_violations,
                     "pairs": pairs})
    print(f"pairs: {len(pairs)} total, {sum(r['status']=='ok' for r in pairs)} ok, "
          f"{len(missing)} missing-output, {len(parse_errors)} parse-error, "
          f"{len(hash_violations)} hash-collisions -> {out}")
    if hash_violations:
        print(f"ABORT: input_sha256 == output_sha256 for {len(hash_violations)} rows: "
              f"{hash_violations[:5]}", file=sys.stderr)
        return 2
    return 0


def cmd_report(args) -> int:
    out = Path(args.out)
    if not (out / "cohort_stats.json").is_file():
        print(f"report: missing {out/'cohort_stats.json'}", file=sys.stderr)
        return 2
    stats = json.loads((out / "cohort_stats.json").read_text())
    matched = pd.read_csv(out / "matched_pairs_scores.csv")
    flags = pd.read_csv(out / "flags.csv") if (out / "flags.csv").is_file() else pd.DataFrame()
    esc = pd.read_csv(out / "escalation.csv") if (out / "escalation.csv").is_file() else pd.DataFrame()
    audit = stats.get("_audit", {})
    text = render_summary(out, matched, flags, stats, audit, esc,
                          matched["name"].tolist())
    (out / "summary.md").write_text(text)
    print(text)
    return 0


# --------------------------------------------------------------------------- #
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    st = sub.add_parser("self-test", help="identity + parity + runtime")
    st.add_argument("--inputs", "--input-dir", dest="inputs", required=True,
                    help="directory of .abc files (<name>.input.abc)")
    st.add_argument("--out", required=True)
    st.add_argument("--parity-pairs", type=int, default=200)
    st.add_argument("--seed", type=int, default=20261111)
    st.add_argument("--feature-budget", type=float, default=120.0)
    st.add_argument("--pairs", default=None, help="optional pairs.json for deep parity")
    st.set_defaults(func=cmd_self_test)

    bp = sub.add_parser("build-pairs", help="assemble/validate pairs.json")
    bp.add_argument("--input-dir", "--inputs", dest="input_dir", required=True)
    bp.add_argument("--transcripts", required=True)
    bp.add_argument("--inventory", required=True)
    bp.add_argument("--out", required=True)
    bp.add_argument("--output-dir", default=None)
    bp.add_argument("--work", default=None)
    bp.set_defaults(func=cmd_build_pairs)

    rn = sub.add_parser("run", help="full similarity run")
    rn.add_argument("--input-dir", "--inputs", dest="input_dir", required=True)
    rn.add_argument("--transcripts", required=True)
    rn.add_argument("--inventory", required=True)
    rn.add_argument("--out", required=True)
    rn.add_argument("--work", default=None, help="where pairs/cohort/failures go")
    rn.add_argument("--output-dir", default=None)
    rn.add_argument("--audit", type=int, default=30)
    rn.add_argument("--permutations", type=int, default=10000)
    rn.add_argument("--blocks", type=int, default=256)
    rn.add_argument("--seed", type=int, default=20261111)
    rn.set_defaults(func=cmd_run)

    rp = sub.add_parser("report", help="re-render summary.md")
    rp.add_argument("--out", required=True)
    rp.set_defaults(func=cmd_report)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
