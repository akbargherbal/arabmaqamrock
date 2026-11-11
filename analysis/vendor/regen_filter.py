#!/usr/bin/env python3
"""
regen_filter.py - decide which instrumental tracks drift too far from the original
and should be regenerated.

Decision per track:  KEEP | REVIEW | REGENERATE   (+ the reasons that triggered it)

Rules (all thresholds are CLI-tunable):
  HARD gates  -> any one triggers REGENERATE
      no_chords        instrumental ABC has zero chord symbols
      duration         duration_sim        < --min-duration     (truncated / overlong)
      note_count       note-count ratio    < --min-notes        (sparse / mostly empty)
      tempo            tempo_sim           < --min-tempo        (octave-folded, so 2x/0.5x is fine)
      key              key_sim             < --min-key          (key-signature distance >= 3 fifths)
      dimension_floor  any of global/harmony/melody/rhythm < --min-group
      composite        composite           < --min-composite
      not_distinctive  (batch >= 5 only) true original ranks worse than --max-rank
                       among all originals, or lift over mismatched originals < --min-lift
  SOFT band   -> composite < --review-below, or any metric group < --review-group => REVIEW

Usage:
    python regen_filter.py comparison_abc_score_inst_vs_original.json --out decisions
    # exit code 0 = nothing to regenerate, 2 = at least one REGENERATE (handy in pipelines)
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

import abc_similarity as S


def evaluate(df: pd.DataFrame) -> pd.DataFrame:
    """One row per track: all sub-metrics, group scores, composite, chord count, rank, lift."""
    ids = df[S.COL_ID].tolist()
    P_o = [S.parse_abc(t) for t in df[S.COL_ORIG]]
    P_i = [S.parse_abc(t) for t in df[S.COL_INST]]
    F_o, F_i = [S.features(p) for p in P_o], [S.features(p) for p in P_i]

    rows = []
    for i in range(len(ids)):
        r = S.compare_features(F_o[i], F_i[i])
        r.update(track_id=ids[i], inst_chords=len(P_i[i].chords))
        for g in S.GROUPS:
            r[f"grp_{g}"] = float(np.mean([r[m] for m in S.GROUPS[g]]))
        r["composite"] = sum(w * r[f"grp_{g}"] for g, w in S.WEIGHTS.items())
        rows.append(r)
    out = pd.DataFrame(rows)

    # distinctiveness vs. the other originals (only meaningful with a decent batch)
    ranks, lifts = [], []
    if len(ids) >= 5:
        for i in range(len(ids)):
            comps = []
            for j in range(len(ids)):
                r = S.compare_features(F_o[j], F_i[i])
                comps.append(sum(w * np.mean([r[m] for m in S.GROUPS[g]]) for g, w in S.WEIGHTS.items()))
            comps = np.array(comps)
            ranks.append(int((comps > comps[i]).sum()) + 1)
            lifts.append(float(comps[i] - np.delete(comps, i).mean()))
        out["retrieval_rank"], out["lift"] = ranks, lifts
    return out


def decide(out: pd.DataFrame, a) -> pd.DataFrame:
    decisions, reasons = [], []
    for _, r in out.iterrows():
        hard, soft = [], []
        if r.inst_chords == 0:
            hard.append("no_chords: instrumental has no chord symbols")
        if r.duration_sim < a.min_duration:
            hard.append(f"duration: similarity {r.duration_sim:.2f} < {a.min_duration}")
        if r.diag_note_count_ratio < a.min_notes:
            hard.append(f"note_count: ratio {r.diag_note_count_ratio:.2f} < {a.min_notes}")
        if r.tempo_sim < a.min_tempo:
            hard.append(f"tempo: octave-folded similarity {r.tempo_sim:.2f} < {a.min_tempo}")
        if r.key_sim < a.min_key:
            hard.append(f"key: similarity {r.key_sim:.2f} < {a.min_key}")
        for g in S.GROUPS:
            v = r[f"grp_{g}"]
            if v < a.min_group:
                hard.append(f"{g}_floor: {v:.2f} < {a.min_group}")
            elif v < a.review_group:
                soft.append(f"{g} weak ({v:.2f})")
        if r.composite < a.min_composite:
            hard.append(f"composite: {r.composite:.2f} < {a.min_composite}")
        elif r.composite < a.review_below:
            soft.append(f"composite borderline ({r.composite:.2f})")
        if "retrieval_rank" in r and not pd.isna(r.retrieval_rank):
            if r.retrieval_rank > a.max_rank:
                hard.append(f"not_distinctive: true original ranks #{int(r.retrieval_rank)} among originals")
            elif r.lift < a.min_lift:
                hard.append(f"not_distinctive: lift {r.lift:.2f} < {a.min_lift}")
        decisions.append("REGENERATE" if hard else "REVIEW" if soft else "KEEP")
        reasons.append("; ".join(hard + soft))
    out = out.copy()
    out["decision"], out["reasons"] = decisions, reasons
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("json_path")
    ap.add_argument("--out", default="decisions")
    ap.add_argument("--min-composite", type=float, default=0.65)
    ap.add_argument("--review-below", type=float, default=0.75)
    ap.add_argument("--min-group", type=float, default=0.50)
    ap.add_argument("--review-group", type=float, default=0.70)
    ap.add_argument("--min-duration", type=float, default=0.80)
    ap.add_argument("--min-notes", type=float, default=0.60)
    ap.add_argument("--min-tempo", type=float, default=0.50)
    ap.add_argument("--min-key", type=float, default=0.50)
    ap.add_argument("--max-rank", type=int, default=3)
    ap.add_argument("--min-lift", type=float, default=0.10)
    a = ap.parse_args()

    df = pd.read_json(a.json_path)
    res = decide(evaluate(df), a)

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    cols = ["track_id", "decision", "composite"] + [f"grp_{g}" for g in S.GROUPS] + \
           [c for c in ("retrieval_rank", "lift") if c in res] + ["reasons"]
    res[cols].round(3).to_csv(out / "decisions.csv", index=False)
    regen = res.loc[res.decision == "REGENERATE", "track_id"].tolist()
    (out / "regenerate_ids.json").write_text(json.dumps(regen, indent=2))

    pd.set_option("display.width", 250, "display.max_colwidth", 110)
    print(res[["track_id", "decision", "composite"] + [f"grp_{g}" for g in S.GROUPS]].round(2).to_string(index=False))
    print()
    for _, r in res[res.decision != "KEEP"].iterrows():
        print(f"[{r.decision}] {r.track_id}: {r.reasons}")
    print(f"\nKEEP {sum(res.decision=='KEEP')} | REVIEW {sum(res.decision=='REVIEW')} | REGENERATE {len(regen)}"
          f"  -> {out/'regenerate_ids.json'}")
    sys.exit(2 if regen else 0)


if __name__ == "__main__":
    main()
