# Blend arm listening verdict — 2026-11-16

**Question:** which blend arm (`a0.1` / `a0.15` / `a0.2`, v3 × Arabic
instrumental) should be the default generation pair?

**Answer:** `a0.15`. Adopted in
[`docs/generation-defaults.md`](../../docs/generation-defaults.md); the
runnable reference is
[`manifests/imru_al_qais_sama_laka_shawqun_a015.json`](../../manifests/imru_al_qais_sama_laka_shawqun_a015.json).

## Run

- Batch: `gs://akbar-december-2024-backup/arabmaqamrock/runs/20261116-121703_imru_al_qais_sama_laka_shawqun_mix_grid/`
- Input: `manifests/imru_al_qais_sama_laka_shawqun_mix_grid.json`
  (sha256 `1e5d273e5e7623289bd15c2c5365b8f0e6c1514bf29ccf6b3c23ed1abc611273`)
- Design: five poems × three arms, one memorable-prime seed per poem shared
  across the arms; only the adapter pair changed.
- Settings held constant: `guidance_scale: 1.5`, `lora_ar_scale: 0.75`,
  `lora_nar_scale: 1.0`, `cot: off`, `quantile: 0.95`, `repeat: 1`.
- Hardware: Tesla T4; model `yue2-3b-bf16.gguf`, VAE `yue2-vae-f16.gguf`,
  checkpoint step 5000, flash attention.
- Result: 15/15 exit 0, 0 truncated; total wall 3:00:39.

## Tracks

| Poem | Maqam | Seed | `a0.1` | `a0.15` | `a0.2` |
|---|---|---|---:|---:|---:|
| `p01` | Hijaz | 7347437 | 267.4 s | 222.4 s | 264.8 s |
| `p02` | Nahawand | 7949497 | 247.1 s | 262.1 s | 283.4 s |
| `p03` | Ajam | 3913193 | 249.8 s | 249.8 s | 212.3 s |
| `p04` | Kurd | 55354333 | 262.4 s | 252.8 s | 235.0 s |
| `p05` | Ajam | 98798789 | 274.9 s | 311.5 s | 294.9 s |

Durations are `wav_duration_s` from the per-track sidecars. They show that no
arm was systematically cut off; they are not a quality metric.

## Verdict and limits

`a0.15` was judged the best of the three arms on this material. The comparison
was **not blind** and is **five poems, one take per arm**, so it is a working
default rather than a proven universal ranking. The scope is score-free,
`cot=off` vocal generation with this LoRA family; instrumentals, third-party
adapters and `cot=melody|full` runs keep their own recipes.

To challenge it, use the same five poems (or a fresh set), the same seeds,
`repeat: 2`, and a blind A/B against `a0.15`. Record the result here and append
an entry to `RECONCILIATION_LOG.md`.
