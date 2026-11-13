# wolf_grid01 — cfg × NAR grid on «مشهد الذئاب»

**One poem, one seed, one take per cell.** Lyrics are `03-مشهد-الذئاب` from
`manifests/alshanfara_lamiyat.json`; the style is the one used in the previous
Abu al-Ala runs (Nahawand), as requested. Note the source song is Hijaz — the
style/lyrics maqam mismatch is deliberate here, not an accident.

| Fixed | Value |
|---|---|
| seed | `3285212580` |
| repeat | `1` |
| `cot` | `off` |
| `semantic_temperature` | 1.0 (default) |
| `num_inference_steps` | 8 (default) |
| `lora_ar_scale` | 1.0 (default) |
| `cap` | 7250 |

## Grid

`v3` is the control. `a01` = alpha 0.1, `a02` = alpha 0.2.

| LoRA | cfg | NAR 0.35 | NAR 0.65 | NAR 1.00 |
|---|---:|---|---|---|
| v3 | 1.0 | `wolf_v3_c10_n035` | `wolf_v3_c10_n065` | `wolf_v3_c10_n10` |
| v3 | 1.5 | `wolf_v3_c15_n035` | `wolf_v3_c15_n065` | `wolf_v3_c15_n10` |
| a0.2 | 1.0 | `wolf_a02_c10_n035` | `wolf_a02_c10_n065` | `wolf_a02_c10_n10` |
| a0.2 | 1.5 | `wolf_a02_c15_n035` | `wolf_a02_c15_n065` | `wolf_a02_c15_n10` |
| a0.1 | 1.0 | `wolf_a01_c10_n035` | `wolf_a01_c10_n065` | `wolf_a01_c10_n10` |
| a0.1 | 1.5 | `wolf_a01_c15_n035` | `wolf_a01_c15_n065` | `wolf_a01_c15_n10` |

Order in the manifest: **v3 (6) → a02 (6) → a01 (6)**. The first 12 tracks are
the primary round; the last 6 are the conservative alpha floor.

- 18 tracks, ~117 min at the nominal 390 s/track; cfg=1.5 rows run CFG and may
  take longer.
- `cfg=1.0` means CFG off. The omitted default with `cot=off` is 1.01, so 1.0 is
  written explicitly where needed.

## NAR caveat

`lora_nar_scale` scales the whole merged adapter, not just the donor:

- **0.35** — v3 NAR is weaker than the old production 0.5; a thin vocal may be
  the scale, not the LoRA.
- **0.65** — close to the old 0.5, with a little more donor.
- **1.00** — v3 NAR roughly doubles vs the old 0.5; the donor is at full alpha.

Always compare an arm against `v3` in the same cell, never against a different
NAR/cfg cell.

## Fetch and run

Only alpha 0.1 and 0.2 exist on GCS now; `a0.3`/`a0.5` were deleted.

```bash
B=gs://akbar-december-2024-backup/OSTRIS_Arabic_Suno_Finetuning/arabic_instrumental_lora/mix_v3
mkdir -p loras/experiments/mix_v3
gsutil cp "$B/MANIFEST.json" loras/experiments/mix_v3/
for a in 0.1 0.2; do
  mkdir -p "loras/experiments/mix_v3/a$a"
  gsutil -m cp "$B/a$a/"* "loras/experiments/mix_v3/a$a/"
done

python3 generate.py manifests/wolf_grid01.json --dry-run
python3 generate.py manifests/wolf_grid01.json --label wolf_grid01
```

Verify the six downloaded files against `MANIFEST.json` by SHA256. Ignore
`check_lora.py --kind nar` failing on the four v9 I/O keys; normal NAR LoRAs have
392 tensors, not 396.

## Read the result

1. `a02` vs `v3` at the same cfg/NAR: does the arm add anything?
2. `a01` vs `a02`: is 0.2 worth the extra donor?
3. `cfg` 1.0 vs 1.5: does text adherence help, or does it stiffen the delivery?
4. NAR 0.35 vs 0.65 vs 1.0: where does the vocal stay intact?

If no cell beats v3 clearly, the next levers are `semantic_temperature` and
`cot`, not a higher alpha — high alpha is already rejected.
