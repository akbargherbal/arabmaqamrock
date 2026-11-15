# Start here

> **Historical case study (2026-10-20).** This was the learning run, not the
> recommended workflow. It took several sessions and hours, partly because the
> take had no exported tokens and the cross-architecture gate failed, and partly
> because the unit/donor experiments were expensive. The current guide is
> [`docs/guides/fixing_ai_music_mispronunciations.md`](../../../guides/fixing_ai_music_mispronunciations.md)
> v2.0 and the reference run is
> [`cases/002_abu01_ajdad/RUN3.md`](../../../../cases/002_abu01_ajdad/RUN3.md).
> Read this folder for evidence and lessons, not as the procedure to follow.

**Read `CHECKPOINT.md` first — it is the historical state.** `PROGRESS.md` is the
multi-session summary (what was tried, what was proven, what is still open).

**Delivered v2:** `FINAL_e1_ar_s03_s13_41.wav`, sha256 `9b8fdb21…` — both words
fixed, outro join fixed, original final `ه` melisma untouched.

**Historical reproducible run:** `gs://akbar-december-2024-backup/arabmaqamrock/runs/20261020_baghdad_moon_final_fix_v2/`
— self-contained inputs, stems, scripts, QC, manifest, and a one-command
rebuild. It is preserved as evidence; do **not** copy its path as the workflow.

- `CHECKPOINT.md` — current state, artifacts, next steps.
- `PROGRESS.md` — 6-session progress summary; S2-join issue is resolved.
- `LESSONS.md` — retrospective across the case study, Claude prompt, the
  iteration, the Suno comparison, and the final 9.5–9.7/10 milestone.
- `../../../guides/fixing_ai_music_mispronunciations.md` — the **current** field
  guide (v2.0, based on case 002 / RUN3). This Baghdad folder is the historical
  case study behind several of its rules.
- `WORKFLOW_VS_SUNO.md` — how this repair differs from Suno cover influence and
  Studio section regeneration (revised after the melisma finding).
- `report.md` — measurements for every round, including the final track.
- `HANDOFF.md` — earlier handoff (historical; §0.5 is annotated).
- `evidence.md` — CTC/ASR/F0 evidence for the two words and the donors.
- `experiments.md` — experiment table.
- `CPU_BUILD.md` — build the prefix-capable binary on a CPU-only machine.
- `render_tokens.sh` — render an exact semantic token stream with the
  prefix-capable binary.

Backup: `gs://akbar-december-2024-backup/arabmaqamrock/runs/20261019_baghdad_moon_token_surgery/`
