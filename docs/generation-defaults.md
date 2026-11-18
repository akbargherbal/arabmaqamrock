# Generation defaults

**Status:** adopted 2026-11-16, reviewable. This is the default recipe for new
generation from now until further notice. The exemption is explicit: test,
sweep and experiment manifests may override any value, but they should state
what changed and why.

**Authority:** the listening verdict on the 15-track batch
[`20261116-121703_imru_al_qais_sama_laka_shawqun_mix_grid`](https://console.cloud.google.com/storage/browser/akbar-december-2024-backup/arabmaqamrock/runs/20261116-121703_imru_al_qais_sama_laka_shawqun_mix_grid)
(`manifests/imru_al_qais_sama_laka_shawqun_mix_grid.json`). This is an ear
verdict, not an automated quality score; §Reviewing records what that means.

The runnable reference (the winning arm, five poems, same seeds) is
[`manifests/imru_al_qais_sama_laka_shawqun_a015.json`](../manifests/imru_al_qais_sama_laka_shawqun_a015.json).

## The preset

| Axis | Default | Notes |
|---|---|---|
| Model | `YuE2-3B-GGUF` bf16 + `yue2-vae-f16.gguf` | checkpoint step 5000; the batch assets are pinned in its `batch_manifest.json` |
| AR adapter | `loras/blend/a0.15/v3instr_a0.15_ar.safetensors` | sha256 `fef2104e13560700e118af92b7be139f7711df59e2a68ddde4691a0e5a5fecc3` |
| NAR adapter | `loras/blend/a0.15/v3instr_a0.15_nar.safetensors` | sha256 `e1696863534e330b290ad92fbe16d904b69b8e5eebf208b9ba738778447a1fb7` |
| `lora_ar_scale` | `0.75` | vocal/plan adapter strength |
| `lora_nar_scale` | `1.0` | NAR rendered-audio adapter strength |
| `guidance_scale` | `1.5` | text + tag adherence |
| `cot` | `off` | score-free vocal generation; no ABC score |
| `quantile` | `0.95` | lyrics-fit cap; the winning caps were 7250–8250 frames |
| `repeat` | `1` | one take per song; use 2–3 only for a deliberate seed sweep |
| Seed | one memorable prime per song | same seed across arms when comparing settings |
| Style | the tag-list base prompt | [`docs/base-prompt.md`](base-prompt.md); `arabmaqamrock` first, Arabic maqam + Western scale, mood last |
| Lyrics | section tags + inline delivery notes | `///***///` first line and `...` at phrase ends, as in the winning run |
| Attention | `flash` | `run_one.sh` passes it |

Only the axes above were set. Everything else stayed on the runtime defaults:

| Control | Value in the winning run |
|---|---|
| `semantic_temperature` | 1.0 (runtime default) |
| `semantic_top_p` / `semantic_top_k` | 0.95 / 100 |
| `semantic_repetition_penalty` | 1.2 |
| `num_inference_steps` | 8 |
| `abc_*` | unused (`cot=off` rejects them) |

The built-in adapter pair in `generate.py` and `run_one.sh` is this blend
`a0.15` pair, and `install.sh` / `setup_colab.sh` stage it (plus the own
Arabic-instrumental donor pair), as declared in
[`plumbing/loras.manifest`](../plumbing/loras.manifest). A manifest that sets no
`lora` therefore gets the default pair without CLI flags.

## Copy-paste preset

```json
{
  "base_dir": "..",
  "defaults": {
    "repeat": 1,
    "lora": "a015",
    "cot": "off",
    "quantile": 0.95,
    "guidance_scale": 1.5,
    "lora_ar_scale": 0.75,
    "lora_nar_scale": 1.0,
    "trigger": true
  },
  "loras": {
    "a015": {
      "ar": "loras/blend/a0.15/v3instr_a0.15_ar.safetensors",
      "nar": "loras/blend/a0.15/v3instr_a0.15_nar.safetensors"
    }
  },
  "songs": [
    {
      "name": "my_song",
      "seed": 7347437,
      "style": "arabmaqamrock, classical arabic, ... Maqam Hijaz, Phrygian Dominant, mood: \"...\"",
      "lyrics": "///***///\n[Intro | ...]\n..."
    }
  ]
}
```

Keep the `defaults` block intact for production runs. A song may still override
a key (for example a `repeat` or a seed), but the override is then part of that
run's record, not a change to the default.

## Evidence

The batch compared three blend arms on the same five poems, with one memorable
seed per poem shared by all three arms. Only the arm changed. All 15 tracks
exited 0 and none was truncated.

| Poem | Maqam | Seed | `a0.1` duration | `a0.15` duration | `a0.2` duration |
|---|---|---|---:|---:|---:|
| `p01` | Hijaz | 7347437 | 267.4 s | 222.4 s | 264.8 s |
| `p02` | Nahawand | 7949497 | 247.1 s | 262.1 s | 283.4 s |
| `p03` | Ajam | 3913193 | 249.8 s | 249.8 s | 212.3 s |
| `p04` | Kurd | 55354333 | 262.4 s | 252.8 s | 235.0 s |
| `p05` | Ajam | 98798789 | 274.9 s | 311.5 s | 294.9 s |

- **Record:** [`eval/blend_a015_default_20261116/VERDICT.md`](../eval/blend_a015_default_20261116/VERDICT.md).
- **Verdict:** `a0.15` was judged the best of the three arms on this material.
  `a0.1` was the conservative floor and `a0.2` the most donor-heavy; `a0.2`
  remains available for experiments but is not the default.
- **Not blind:** the listener knew which arm was which, and the comparison is
  five poems, one take per arm. Treat it as a strong working default, not a
  proven universal ranking.
- **Scope:** the run is score-free, `cot=off`, vocal generation with this LoRA
  family. Instrumental runs, third-party adapters and `cot=melody|full` runs
  have their own recipes and are not covered by this verdict.

## Deliberate deviations

Use a different value when the run is an experiment; record the axis, the
before/after and the verdict. The useful places to start:

- **A new blend arm** (for example a re-merge): compare it against `a0.15` with
  the same seeds, `repeat: 2`, and the same prompts.
- **Instrumentals:** use the third-party/own instrumental recipes, not this
  preset; see the `fadhl_shaker_instrumental_*` manifests.
- **Score/CoT runs:** `cot=melody|full` adds the ABC stage and its `abc_*`
  knobs; the adapter pair can stay `a0.15`, but the plan settings are a
  separate decision.
- **Pronunciation repair:** use the preservation-first procedure in
  [`docs/guides/repair_session_runbook.md`](guides/repair_session_runbook.md);
  do not "fix" diction by changing the default preset.

## Reviewing this decision

To challenge it, run the same five poems (or a fresh set) with `a0.15` and the
challenger arm, same seeds, 2 takes each, and listen blind. Record the outcome
in `eval/` and in an append-only entry in
[`RECONCILIATION_LOG.md`](../RECONCILIATION_LOG.md). If a challenger wins,
update this file and the reference manifest in the same pass; the old verdict
stays in the log, not silently replaced.
