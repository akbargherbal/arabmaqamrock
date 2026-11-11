#!/usr/bin/env bash
# Finalize the YT500 input-vs-output ABC similarity study.
#
# Preconditions: at least 437 / 460 verified output transcripts.  The script
# pulls the published flat mirror, verifies hashes, runs the full analysis,
# publishes the durable + analysis bundles, and prints the headline numbers.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

OUT="${TRANSCRIPTS_DIR:-/content/yt500/transcripts}"
IN="${INPUT_DIR:-work/yt500_abc/input}"
INV="${INVENTORY:-work/yt500_abc/inventory.json}"
WORK="${WORK_DIR:-work/yt500_abc}"
SIM="$WORK/similarity"
TARGET="${TARGET:-437}"

verified=$(python3 - "$OUT" <<'PY'
import json, sys
from pathlib import Path
root = Path(sys.argv[1]); n = 0
for d in root.iterdir():
    if not d.is_dir():
        continue
    try:
        m = json.loads((d / "meta.json").read_text())
    except Exception:
        continue
    n += bool(m.get("status") == "ok" and (d / "score.abc").is_file())
print(n)
PY
)
echo "verified=$verified target=$TARGET"
if [ "$verified" -lt "$TARGET" ]; then
  echo "refusing to finalize: only $verified verified outputs" >&2
  exit 1
fi

RETRY_PY=".venv-sheetsage2/bin/python"
[ -x "$RETRY_PY" ] || RETRY_PY="python3"
"$RETRY_PY" plumbing/recover_yt500_abc.py --transcripts "$OUT" || true
python3 plumbing/yt500_transcribe_sync.py push || true
python3 plumbing/yt500_transcribe_sync.py verify || true
./transcribe.sh /content/yt500/audio --out-dir "$OUT" --verify \
  > logs/yt500_abc/verify_transcribe.log 2>&1 || true

python3 analysis/run_yt500_similarity.py run \
  --input-dir "$IN" \
  --transcripts "$OUT" \
  --inventory "$INV" \
  --out "$SIM" \
  --work "$WORK" \
  --audit 30 --permutations 10000 --blocks 256

COMMIT=$(git rev-parse HEAD)
python3 plumbing/publish_yt500_bundle.py dataset
python3 plumbing/publish_yt500_bundle.py analysis --commit "$COMMIT"

echo
echo "== headline =="
python3 - "$SIM" <<'PY'
import json, sys
from pathlib import Path
import pandas as pd
sim = Path(sys.argv[1])
s = json.loads((sim / "cohort_stats.json").read_text())
m = pd.read_csv(sim / "matched_pairs_scores.csv")
f = pd.read_csv(sim / "flags.csv")
print(json.dumps({"cohort": s["_cohort_size"], "commit": s["_commit"],
                  "median_composite": s["composite"]["median"],
                  "iqr": float(m["composite"].quantile(.75) - m["composite"].quantile(.25)),
                  "mean_d": s["_permutation"]["mean_d"],
                  "dz": s["_permutation"]["dz"],
                  "p": s["_permutation"]["p_value"],
                  "frac_d_positive": s["_permutation"]["frac_positive"],
                  "rank1_pct": float((m["retrieval_rank"] == 1).mean()),
                  "audit_rho": s["_audit"]["spearman"],
                  "audit_n": s["_audit"]["n"]}, indent=2))
print(f.loc[f.status == "ok", "decision"].value_counts().to_string())
PY
