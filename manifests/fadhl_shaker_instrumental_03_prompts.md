# Fadhl Shaker — instrumental prompt sweep (round 03)

**Question:** after the Vocal → Ins score surgery, the product is better but the
model still produces a vocal-like/gibberish line. Can a caption written by us —
or the smallest possible caption — suppress it?

**Design:** one song (`أنا من آخرها`), one instrumentalized score, one seed, one
cap; only the caption changes. `cot=melody`, LoRA 0, trigger off,
`[Instrumental]`, `guidance_scale` default 1.0 unless noted.

The score is the map. The caption only has to say "instruments, no voice".

## Variants

| # | Name | Caption strategy | Extra |
|---|---|---|---|
| 1 | `p0_original_caption` | the shortlist's `full_instrumental` caption (control) | — |
| 2 | `p1_one_word` | `instrumental` | — |
| 3 | `p2_minimal_negative` | `pure instrumental music, no vocals, no singing, no voice` | — |
| 4 | `p3_negative_list` | pure instrumental + a long list of `no vocals / no singing / no voice / no choir / no humming / no vocalizations / no lyrics / no ad-libs` | — |
| 5 | `p4_positive_only` | describes only the instruments (oud, darbuka, strings, bass) and **never uses the word vocal/voice** | — |
| 6 | `p5_tag_list` | tag list: `instrumental, Arabic pop, oud, darbuka, … no vocals, no singing` | — |
| 7 | `p6_negative_cfg15` | same as #4 | `guidance_scale: 1.5` |
| 8 | `p7_one_word_cfg15` | `instrumental` | `guidance_scale: 1.5` |

`generate.py` rejects an empty style, so `instrumental` is the closest we can get
to "no caption at all".

## Manifest

`manifests/fadhl_shaker_instrumental_03_prompts.json` — 8 takes, ~52 min on a T4.

```bash
# validate (no GPU)
python3 generate.py manifests/fadhl_shaker_instrumental_03_prompts.json --dry-run

# the five main caption strategies (control + one-word + minimal + negative + positive-only)
python3 generate.py manifests/fadhl_shaker_instrumental_03_prompts.json \
  --limit 5 --label fadhl_inst_03_prompts

# all eight, including the two guidance_scale=1.5 variants
python3 generate.py manifests/fadhl_shaker_instrumental_03_prompts.json \
  --label fadhl_inst_03_prompts_all
```

## How to judge

For each take, the only question is **vocal leakage**:

- any words, syllables, hums, "la-la", choir, or vocal-like timbre?
- if yes, is it a lead line or just a faint texture?
- does the take still follow the original melody and sections?

Keep the best clean take. If one caption strategy is clean, promote it to the
full 23-song batch.

## If none of them is clean

That would confirm the model's prior is stronger than the text prompt: YuE2 is a
song model and always allocates a vocal line. The practical fallback is source
separation on the best-sounding take:

```bash
pip install demucs
demucs --two-stems=vocals -o out/stems path/to/take.wav
# deliver out/stems/htdemucs/<take>/no_vocals.wav
```

This does not make the model instrumental; it removes the gibberish vocal stem
after the fact. Try the prompt sweep first because it is cheaper than a
separation pass and may solve the problem at the source.
