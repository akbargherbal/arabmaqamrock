# حبيتك — instrumental LoRA, one-song experiment (round 04)

**Goal:** answer two questions on one song before touching the 23-song batch:

1. Does the third-party **instrumental AR LoRA** actually suppress vocals in our
   runtime (`audiocpp_cli`, GGUF model)?
2. Does it need the **Vocal → Ins score surgery**, or can it render the original
   `Vocal` melody instrumental by itself?

The song is **حبيتك** (`habeetak`): 269.7 s, Gm, 101 BPM, 438 Vocal notes in the
original score and 459 Ins notes.

## What changes vs round 02/03

Round 02/03 used the base model (`lora_*_scale: 0`) and a caption sweep. Round 04
loads a different **AR adapter**:

| | Round 02/03 | Round 04 |
|---|---|---|
| AR adapter | base | `ar_lora_inst_v3abc.bf16.safetensors` |
| NAR adapter | base | `arabmaqamrock-v3-nar` at **scale 0** |
| `cot` | `melody` | `full` (the LoRA's intended mode) |
| Lyrics | `[Instrumental]` | `[instrumental]` (the LoRA's bare form) |
| Score | instrumentalized | **original vs instrumentalized** (A/B) |

The score surgery is still in the experiment, but it is now a **variable**, not a
fixed assumption. Both scores are supplied verbatim; the LoRA cannot edit an
external ABC, so the A/B tells us which voice layout the adapter expects.

## Variants

All takes use the same style caption, `[instrumental]`, `cap=6993`, seed
`20261106`, `trigger: false`, and `cot=full`.

| # | Name | Score | Vocal notes | AR scale |
|---|---|---|---|---|
| 1 | `v1_original_lora100` | `scores/fadhl_shaker/habeetak.abc` | 438 (original) | 1.0 |
| 2 | `v2_surgery_lora100` | `scores/fadhl_shaker_instrumental/habeetak.abc` | 0 | 1.0 |
| 3 | `v0_base_surgery_full` | instrumentalized | 0 | 0.0 (control) |
| 4 | `v3_original_lora075` | original | 438 | 0.75 |
| 5 | `v4_surgery_lora075` | instrumentalized | 0 | 0.75 |
| 6 | `v5_lora_text_only` | **no ABC** (model plans) | — | 1.0 |

`v0` isolates the LoRA effect: same score and `cot` as `v2`, LoRA off.
`v5` is the LoRA's documented use (text-to-instrumental, model writes its own
score). If `v5` also leaks vocals, the adapter is not effective in this runtime;
if `v5` is clean, the ABC path is the only open question.

## Download the adapter

The setup script fetches it to `loras/instrumental/` and verifies the sha256. To
do it by hand:

```bash
mkdir -p loras/instrumental
hf download Mothersuperior/YuE2-instrumental-cot-full-loras \
  ar_lora_inst_v3abc.bf16.safetensors \
  --local-dir loras/instrumental

python3 plumbing/check_lora.py \
  loras/instrumental/ar_lora_inst_v3abc.bf16.safetensors \
  --expect-rank 64
```

The file is 139,502,088 bytes, sha256
`e408fd3148b75b1165f7ddbf63db575d83bb6402a0b5f876fcb767dbcb2c5414`.

> The manifest's `instrumental` alias points its **NAR** side at the existing
> `arabmaqamrock-v3-nar.safetensors` with `lora_nar_scale: 0`. That is the
> no-code-change path: the NAR adapter loads but its delta is zero. The AR side is
> the new adapter.

## Commands

```bash
# validate (no GPU)
python3 generate.py manifests/fadhl_shaker_instrumental_04_lora_habeetak.json --dry-run

# core question first: original vs surgery vs control (3 takes, ~20 min)
python3 generate.py manifests/fadhl_shaker_instrumental_04_lora_habeetak.json \
  --limit 3 --label fadhl_inst_04_habeetak_core

# all six, including scale 0.75 and the text-only diagnostic (~39 min)
python3 generate.py manifests/fadhl_shaker_instrumental_04_lora_habeetak.json \
  --label fadhl_inst_04_habeetak_full
```

## How to judge

Listen to each take in this order:

1. **Vocals** — words, syllables, humming, wordless voice, choir?
2. **Melody** — is the original `habeetak` tune clearly carried by the lead
   instrument?
3. **Lead vs accompaniment** — is the melody in front, or buried under the
   arrangement?
4. **Looping** — does the music repeat itself instead of ending?
5. **Length / truncation** — check `result.json` `truncated` flags.

## Decision tree

| Result | Meaning | Decision |
|---|---|---|
| `v5` clean | adapter works in our runtime | continue with the ABC variants |
| `v1` clean, melody clear | LoRA plays the original `Vocal` line instrumentally | **drop the surgery** for this adapter |
| `v1` has vocals | LoRA does not override an explicit Vocal line | **keep the surgery** |
| `v1` clean but melody buried, `v2` better | LoRA treats `Ins` as the lead | **keep the surgery** |
| `v2` clean, melody clear | surgery is in-distribution | **keep the surgery** |
| `v1` and `v2` both leak | LoRA alone is not enough | surgery + scale 1.0 + Demucs |
| `v2` loops at 1.0 | known side effect | use `v4` (0.75) |

## Notes and caveats

- The LoRA is **AR-only**. The NAR decoder is stock (the arabmaqamrock NAR is
  loaded at scale 0). If the AR output is instrumental but the timbre still has a
  vocal texture, the optional NAR LoRA from
  [`yue2-mothersuperior-realaudio-tokenizer-v4`](https://huggingface.co/Mothersuperior/yue2-mothersuperior-realaudio-tokenizer-v4)
  is the next lever. It includes `vae2llm`/`llm2vae` replacements; `audio.cpp`
  supports them, but it is a separate variable.
- The LoRA is CC BY-NC 4.0, same as the YuE2 base weights.
- The adapter was trained on ~2.7k instrumental tracks with SheetSage2 ABC. Its
  behavior on an **external** ABC is not documented; round 04 is the test.
- `[interlude]` is not in the LoRA's allowed tag list. The bare `[instrumental]`
  used here avoids that. A later section-tag variant should map `interlude` to
  `[instrumental]` or `[bridge]`.
- If `v2` wins, keep `scores/fadhl_shaker_instrumental/` as the production
  scores. If `v1` wins, the original `scores/fadhl_shaker/` can be used directly
  and the surgery becomes optional.
