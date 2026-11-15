---
name: docs-reconciler
description: Reconcile live project docs against actual code/config and resolve contradictions between them, without an unscoped rewrite. Use when asked to clean up docs, fix stale or outdated documentation, audit the docs, or make the docs match the code. Mechanical extraction and verification run first; proposed edits are surgical and each needs human approval before being written.
---

# Docs reconciliation

"Clean up the docs" is unbounded. This splits it: scripts find *candidate*
problems cheaply, model judgment is spent only on flagged items, and the user
approves every edit. Do not skip to "just fix everything" — that is the failure
mode this exists to prevent.

## Scope: live vs frozen (this repo)

Reconcile (editable):

- `README.md`, `MODEL_CARD.md`, `SOURCE_OF_TRUTH.md`
- `skills/*/SKILL.md`
- `prompts/*.md` (the ABC specs)
- `docs/base-prompt.md`, `docs/transcription.md`,
  `docs/suno-generation-controls.md`, `docs/easygoing-eagle-controls-ar.md`
- `docs/guides/**`, `docs/mockups/README.md`
- `manifests/README.md`, `plumbing/README.md`, `scores/fadhl_shaker/README.md`,
  `analysis/vendor/README.md`

Frozen (read-only; never "corrected"): `cases/**`, `eval/**`,
`docs/sessions/**`, `docs/plans/**`, `docs/happy_accidents/**`, every
`manifests/*.md` except `README.md`, `ROUND06_RESUME.md`, `ROUND10_RESUME.md`,
`scores/CHANGES.md`, `RECONCILIATION_LOG.md` (append-only),
the vendored `plumbing/yue2_instrumental/README.md`, generated dataset cards
under `outputs/**`, and generated/runtime trees (`out/`, `logs/`, `datasets/`,
`local_workspace/`, `bin/`, `models/`, `loras/`). The scripts exclude these by
default.

History stays history: add a dated entry, don't rewrite it. Dated plans are
evidence of what was intended then; a stale plan is not drift. If a frozen
record needs a correction, append a note to `RECONCILIATION_LOG.md` and name the
record — never edit the record itself.

Authority when two docs disagree: code and its `--help`/argparse output outrank
`docs/` runbooks, which outrank `README.md`. For manifests, the strict schema in
`generate.py` is the authority (`SONG_KEYS`, `DEFAULT_KEYS`, `CONTROL_SPECS`);
validate with `python3 generate.py <manifest> --dry-run`, do not maintain a
second schema. `SOURCE_OF_TRUTH.md` is the map of which file owns which topic.

## Step 0 — Source-of-truth map

`SOURCE_OF_TRUTH.md` exists at the repo root. Keep it current; if a topic has no
row, add one rather than deciding authority ad hoc. Every future pass reuses it.

## Step 1 — Extract claims (scripted)

```bash
python3 skills/docs-reconciler/scripts/extract_claims.py --root .
```

Writes `.reconcile/claims.json`: repo paths, `file:line` citations, CLI flags,
runtime/GCS paths, date stamps. No model judgment here. `--include-all` scans
frozen history too — only for an explicitly scoped audit, never as the default.

## Step 2 — Verify mechanically

```bash
python3 skills/docs-reconciler/scripts/verify_claims.py --root .
```

Writes `.reconcile/drift_report.md` with only the failures: missing paths,
out-of-range citations, flags defined nowhere in repo code. Runtime paths, GCS
URIs and date stamps are counted, not judged. If it prints the **structural
warning** (>30% of checkable claims flagged), stop and tell the user the corpus
needs a scoped rewrite, not a reconciliation pass.

## Step 3 — Batch

Group flagged items by file or topic; never send more than ~10–15 to judgment in
one batch. Missing paths are often examples or runtime artifacts — check the
ignore list before treating one as drift.

## Step 4 — Propose minimal diffs

Per item: quote the contradiction, state what the authority says is correct, and
give the smallest edit — never rewrite surrounding prose. Check freshness with
`git log -1 --format=%cs -- <file>` against the source file the doc describes.
For manifests and controls, prefer a `--dry-run` result as the evidence.

A flag that exists only in a plan ("7.3 `--from-run`") is not automatically drift:
say whether the text describes shipped behaviour or a proposal, and fix the
status/tense rather than deleting the plan.

## Step 5 — Human checkpoint

Present diffs per file/topic; apply only what the user approves. Prompt text,
sampler defaults and manifest fields are the user's call. Nothing is written
before this checkpoint.

## Step 6 — Apply and log

Targeted replacements only. Append to `RECONCILIATION_LOG.md` (root; create on
first run) one dated entry per pass:

```text
YYYY-MM-DD — <file> — <one-line what changed> — authority: <code/CLI/file>
```

## Guardrails

- Steps 1–2 are script-only; never pull whole documents into context for them.
- Suppress missing-path noise only by curating
  `references/unverifiable.txt` with review — a broad glob there hides real
  drift.
- Never rewrite a frozen doc to match today's code.
- Never accept "clean up all the docs" as one pass; scope it first.
- Never edit vendored code or vendor READMEs (`plumbing/yue2_instrumental/`,
  `analysis/vendor/*.py`) as part of a docs pass.
- Nothing is written before the Step 5 checkpoint.

## Bundled resources

- `scripts/extract_claims.py`, `scripts/verify_claims.py` — run directly, don't reimplement.
- `references/example_drift_report.md` — expected report shape.
- `references/source_of_truth_template.md` — Step 0 starting map.
- `references/unverifiable.txt` — curated tokens that legitimately live outside the repo (runtime artifacts, downloaded weights, external source trees, example inputs, per-case working files). Scope a token to one doc with `path/to/doc.md :: glob`.
