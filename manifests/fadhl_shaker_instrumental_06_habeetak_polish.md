# حبيتك — polish the winning take (round 06)

**Context:** round 05 compared full transcription, no-chords surgery, and
melody-only on `حبيتك`. The winner was **`m3_full_lora100`**:

- full transcription (`scores/fadhl_shaker_instrumental/habeetak.abc`)
- Vocal → Ins surgery, chords kept
- `cot="full"`
- instrumental AR LoRA `ar_lora_inst_v3abc` at **1.0**
- NAR stock (arabmaqamrock NAR at scale 0)
- `[instrumental]`, seed `20261106`, cap `6993`

Melody-only and no-chords were worse. The remaining issue is **production /
arrangement density**: the take can sound thin or stem-like. Round 06 keeps the
score and surgery fixed and changes only the renderer.

## Levers

| Lever | Why | Variant |
|---|---|---|
| **NAR LoRA v9** | AR only shapes the plan; the stock NAR renders the timbre. The adapter author recommends pairing with the real-audio NAR LoRA for production-quality output. | `p1`, `p2` |
| **Arabic NAR at low scale** | The project's own NAR is trained on the Arabic material; a low scale may add the right timbre without the vocal texture. | `p3` |
| **Section tags** | The instrumental LoRA was trained on section plans. Bare `[instrumental]` lets it choose; the score's sections keep the arrangement continuous. `interlude` is mapped to `instrumental` (the LoRA does not accept `[interlude]`). | `p4`, `p5` |
| **Compact style** | The LoRA's style field is a normal tag string. A dense tag list is closer to that form than the long prose caption. | `p4`, `p5`, `p6` |
| **32 ODE steps** | More NAR flow-matching steps; the HF Space calls this the "Best" render quality. | `p6` |

## Variants

All takes use `cot="full"`, the same full score, `cap=6993`, seed `20261106`,
`trigger: false`, and AR scale `1.0`.

| # | Name | NAR | NAR scale | Lyrics | Style | Steps |
|---|---|---|---|---|---|---|
| 1 | `p0_m3_baseline` | arabmaqamrock | 0.0 | `[instrumental]` | long prose | default |
| 2 | `p1_nar_v9_100` | NAR v9 | 1.0 | `[instrumental]` | long prose | default |
| 3 | `p2_nar_v9_050` | NAR v9 | 0.5 | `[instrumental]` | long prose | default |
| 4 | `p3_nar_arab_030` | arabmaqamrock | 0.3 | `[instrumental]` | long prose | default |
| 5 | `p4_nar_v9_100_sections_style` | NAR v9 | 1.0 | sections | compact | default |
| 6 | `p5_nar_v9_050_sections_style` | NAR v9 | 0.5 | sections | compact | default |
| 7 | `p6_nar_v9_100_sections_style_steps32` | NAR v9 | 1.0 | sections | compact | 32 |

Section plan used for `p4`–`p6`:

```
[intro]
[verse]
[chorus]
[instrumental]
[verse]
[chorus]
[instrumental]
```

## NAR v9 caveat

`nar_lora_joint_v9.bf16.safetensors` contains:

- 392 NAR A/B LoRA tensors (`nar_self_attn`, `nar_mlp`, 28 layers, rank 32);
- **4 full replacement weights** for `vae2llm` and `llm2vae`.

The full replacements are **not scaled** by `lora_nar_scale`. Therefore:

- the NAR v9 is used only through the `instrumental_v9` alias;
- the baseline `p0` uses the plain `arabmaqamrock-v3-nar` at scale 0;
- never load NAR v9 at scale 0 expecting the stock decoder.

## Download and check

`setup_colab.sh` now downloads both adapters and verifies their sha256:

```bash
./setup_colab.sh
```

By hand:

```bash
mkdir -p loras/nar
hf download Mothersuperior/yue2-mothersuperior-realaudio-tokenizer-v4 \
  nar_lora_joint_v9.bf16.safetensors --local-dir loras/nar

python3 plumbing/check_lora.py \
  loras/nar/nar_lora_joint_v9.bf16.safetensors \
  --kind nar --expect-rank 32
```

Expected: 396 tensors, 28 layers, rank 32, OK.

## Run

```bash
python3 generate.py \
  manifests/fadhl_shaker_instrumental_06_habeetak_polish.json --dry-run

# Phase A first: baseline + three NAR candidates (4 takes, ~26 min)
python3 generate.py \
  manifests/fadhl_shaker_instrumental_06_habeetak_polish.json \
  --limit 4 --label fadhl_inst_06_nar

# Phase B: re-run the full manifest; the first four are skipped
python3 generate.py \
  manifests/fadhl_shaker_instrumental_06_habeetak_polish.json \
  --label fadhl_inst_06_polish
```

`--limit 4` keeps the NAR A/B honest: `p0`–`p3` differ only in the NAR adapter
and its scale. Phase B then tests structure/style/steps on top of the better NAR.

## How to judge

Listen in this order:

1. `p0` — the known-good M3 baseline.
2. `p1` vs `p2` vs `p3` — which NAR gives the best production/timbre?
3. `p4` vs `p5` — does the section plan + compact style help?
4. `p6` — does 32 steps improve fidelity?

For each: vocals (should be clean), melody clarity, arrangement density, glue,
looping, and `truncated`.

## If the take is truncated

Check:

```bash
grep -i truncated \
  out/<run>/p0_m3_baseline_20261106.log
```

If `truncated=true`, raise the caps from `6993` to `7493` or `7993` in the next
manifest. The score is 269.7 s; `6993` is 279.3 s, only 250 frames of headroom.

## After round 06

- If `p1` wins: promote NAR v9 to the full 23-song batch.
- If `p3` wins: the Arabic NAR is the timbre path; test 0.3–0.5 on a second song.
- If `p4`/`p5` wins: make the section plan the default for covers.
- If `p6` wins: set `num_inference_steps: 32` in the production manifest.
- Then run **best-of-3 seeds** on the winning recipe and keep the cleanest take.
