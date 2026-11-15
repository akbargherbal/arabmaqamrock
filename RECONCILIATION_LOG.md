# Reconciliation log

Append-only. One dated entry per approved docs pass: date — file/topic — what
changed — authority. Do not edit or delete old entries; they quote past drift
reports verbatim. See `skills/docs-reconciler/SKILL.md`.

## 2026-11-15 — first reconciliation pass

Approved after review of the first drift report (11 flagged: 3 missing paths,
4 flags not found in code; 650 claims, 19 live docs). Scope was the live-doc
allowlist in the skill; frozen/history docs untouched.

- 2026-11-15 — `analysis/vendor/README.md` — production modules
  (`analysis/abc_scale.py`, `analysis/abc_calibrate.py`,
  `analysis/run_yt500_similarity.py`) relabelled as planned and not in the repo;
  oracle reuse described as intended, not current — authority:
  `docs/plans/yt500-instrumental-abc-similarity.md` status line, repo file list.
- 2026-11-15 — `skills/maqam-edit/SKILL.md` — `maqam` CLI marked as the planned
  target interface with no executable in the repo; `check_abc.py` documented as
  the tracked validator and its local-only `datasets/five_stars/measure/`
  dependency stated; report step now allows validator/scratch output — authority:
  `docs/plans/model-and-tool-selection.md` §tool interface, `check_abc.py`
  argparse, import at `check_abc.py:32`.
- 2026-11-15 — `docs/suno-generation-controls.md` — §7.3 marked not implemented
  (no `--from-run`/`--set` in `generate.py`); §7.4 status split into the README
  sentence (present) and the `MODEL_CARD.md` provenance paragraph (open) —
  authority: `generate.py` argparse, `README.md` “Sampler and adapter controls”.
- 2026-11-15 — `SOURCE_OF_TRUTH.md` — ABC-edit row now names the planned CLI,
  the tracked validator and its local dependency — authority: same as above.
- 2026-11-15 — `generate.py` — docstring/`--help`/comment no longer cite the
  nonexistent `INFERENCE/run_one.sh`; reference is the root `run_one.sh` —
  authority: `generate.py:136-137`, `ls run_one.sh`.
- 2026-11-15 — `.gitignore` — added `/.reconcile/` for scratch claims/report
  output — authority: `skills/docs-reconciler/scripts/*`.

Post-pass audit: 667 claims, checkable 529, flagged 0 (0.0%), ignored 130.
`python3 -m unittest discover -s tests` — 150 tests, OK.
