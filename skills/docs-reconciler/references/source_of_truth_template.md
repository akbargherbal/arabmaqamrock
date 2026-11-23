# Source of truth

One authority per topic. When two documents disagree, the higher row wins.
History files are authoritative for what happened, never for what is true now.

| Topic | Authority | Notes |
|---|---|---|
| CLI flags / defaults | `python3 generate.py --help` and `generate.py` argparse | script flags beat prose |
| Manifest schema / field names | `generate.py` docstring + `SONG_KEYS` / `DEFAULT_KEYS` / `CONTROL_SPECS`; `manifests/README.md` | strict: unknown keys are errors; validate with `python3 generate.py <manifest> --dry-run` |
| Generation controls | `generate.py` `CONTROL_SPECS` + `manifests/controls.example.json` | `docs/suno-generation-controls.md` Appendix D explains semantics; code owns bounds |
| Install / stage the runtime | `install.sh`, `setup_colab.sh`, `plumbing/fetch_binary.sh --help` | `plumbing/README.md` describes the GCS prefix |
| Generate / resume / output layout | `README.md`, `generate.py` docstring, `run_one.sh` | `--dry-run` is the executable description |
| Backup / GCS layout | `plumbing/backup_to_gcp.py --help`, `plumbing/README.md` | script flags beat prose |
| Symbolic transcription | `transcribe.py`, `transcribe.sh`, `docs/transcription.md` | `--dry-run` / `--smoke` are the safe checks |
| ABC melody edit (output contract) | `prompts/arabmaqamrock_abc_edit_spec.md`, `prompts/arabmaqamrock_abc_spec.md` | the two specs define the output; `check_abc.py` is the tracked validator (needs the local `datasets/five_stars/measure/` parser) |
| Pronunciation repair (current procedure) | `docs/guides/repair_session_runbook.md`, `docs/guides/fixing_ai_music_mispronunciations.md` | case 002 RUN3 is the reference run, not current authority |
| Style prompt / trigger | `docs/base-prompt.md` + `manifests/space-stallion.json` | keep the maqam and Western scale names together |
| Weights, license, provenance | `MODEL_CARD.md` + `README.md` (§License, §Provenance) | weights are non-commercial |
| Manifest index | `manifests/README.md` | individual `manifests/*.md` are run records |
| Guide / session indexes | `docs/guides/README.md`, `docs/sessions/README.md` | indexes must list their live docs |
| Agent contract | `skills/*/SKILL.md` | `SOURCE_OF_TRUTH.md` resolves conflicts between them |
| Why a past choice was made | `docs/plans/**`, `docs/sessions/**`, `cases/**` | read-only; cite, don't rewrite |
| History / outcomes / measurements | `eval/**`, `cases/**`, `docs/sessions/**`, `scores/CHANGES.md` | read-only records |
| Archived / superseded | `ROUND06_RESUME.md`, `ROUND10_RESUME.md`, `docs/plans/**`, `docs/happy_accidents/**` | banners are correct; don't "fix" |
| Reconciliation history | `RECONCILIATION_LOG.md` | append-only; quotes past reports verbatim |
