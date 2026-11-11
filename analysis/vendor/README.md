# Vendored oracle — ABC similarity (10-track study)

These two files are copied **verbatim** from
`local_workspace/abc_similarity.zip` (the 10-track Fadl Shaker study). They are
committed here because `local_workspace/` is gitignored and the Colab VM must be
able to import them.

- `abc_similarity.py` — `sha256 3c2d98ec9a32c2cf9aa80e64a7a2827b951bc088363a4a885e17b9fdd89fadda`
- `regen_filter.py` — `sha256 0cd7b9495bb261c4fc780e161157adf3bf3996315dfa748772e8dc30444fcf45`

Do **not** edit them. They are the audit oracle:

- `parse_abc`, `Score`, `Note`, `features`, `compare_features` are reused by
  the production path for parsing and by the deep audit / escalation.
- `regen_filter.py` is a threshold *reference* only; production decisions use
  cohort percentiles (see `docs/plans/yt500-instrumental-abc-similarity.md` §9.4).

The production implementation lives in `analysis/abc_scale.py`,
`analysis/abc_calibrate.py` and `analysis/run_yt500_similarity.py`; it imports
these modules read-only. If the oracle ever needs to change, bump the sha256
here and update the plan.
