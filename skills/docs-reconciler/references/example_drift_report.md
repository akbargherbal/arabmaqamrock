# Drift report — 2026-11-15

> Trimmed example from the first adaptation run, kept to show the shape of a
> report. The real report is written to `.reconcile/drift_report.md`. Item
> counts are historical, not a guarantee.

Source: `.reconcile/claims.json` — 650 claims across 19 live docs. Checkable: 529; flagged: 11 (2.1%).

## Missing paths (3; example)

- `analysis/vendor/README.md:18` — `analysis/abc_scale.py` — tried: `analysis/vendor/analysis/abc_scale.py`, `analysis/abc_scale.py`
- `analysis/vendor/README.md:19` — `analysis/abc_calibrate.py` — tried: `analysis/vendor/analysis/abc_calibrate.py`, `analysis/abc_calibrate.py`
- `analysis/vendor/README.md:19` — `analysis/run_yt500_similarity.py` — tried: `analysis/vendor/analysis/run_yt500_similarity.py`, `analysis/run_yt500_similarity.py`

## Flags not found anywhere in repo code (4; example)

- `skills/maqam-edit/SKILL.md:92` — `--phrases`
- `skills/maqam-edit/SKILL.md:94` — `--edit`
- `skills/maqam-edit/SKILL.md:95` — `--against`
- `docs/suno-generation-controls.md:439` — `--from-run`

## Not verified (counts only)

- gs_uri: 4
- runtime_path: 4
- matched `skills/docs-reconciler/references/unverifiable.txt` (known external/runtime/example tokens): 113

## After reconciliation (2026-11-15)

The same run against the reconciled docs, so this is the expected clean shape:

```text
667 claims from 19 files
checkable=529 flagged=0 (0.0%) ignored=130

No drift found among checkable claims.
```

The 11 items above were resolved by labelling them as planned/unimplemented,
not by deleting the prose: `analysis/vendor/README.md` now says the production
modules are not in the repo, `skills/maqam-edit/SKILL.md` marks the `maqam` CLI
as a target interface, and `docs/suno-generation-controls.md` marks §7.3 as not
implemented.
