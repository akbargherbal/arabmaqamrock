# Fadhl Shaker — full instrumental from ABC (round 02)

**Goal:** round 01 proved the melody is right but the model still sang gibberish.
Round 02 uses the **official YuE2 instrumental conversion** so the score has no
vocal melody left to sing.

**Input:** the same 23 songs and `full_instrumental` captions as round 01, but
with transformed scores.

## Why round 01 had vocals

YuE2 has no native instrumental mode. It always plans a **Vocal** melody and an
**Ins** line, even when the lyrics are empty or just `[Instrumental]`; the model
then sings or hums that Vocal line. Writing "no vocals" in the style is not
enough on its own.

The official YuE2 instrumental workflow is **score surgery**, not prompt
engineering:

1. move every **Vocal** note (pitch, onset, duration) into **Ins**;
2. leave only rests and chord symbols on **Vocal**;
3. keep the original Ins notes that do not overlap the vocal melody;
4. Ins stays monophonic; on overlap, Vocal wins.

The score is then rendered normally. With no notes on the Vocal staff, there is
no vocal melody to sing.

Sources:
- <https://github.com/multimodal-art-projection/YuE/tree/main/skills/yue2-music/instrumental>
- <https://github.com/multimodal-art-projection/YuE/issues/18>

## What was converted

| | |
|---|---|
| Original scores | `scores/fadhl_shaker/*.abc` (unchanged) |
| Instrumental scores | `scores/fadhl_shaker_instrumental/*.abc` |
| Conversion reports | `scores/fadhl_shaker_instrumental/reports/*.json` |
| Converter | `plumbing/instrumentalize_scores.py` + vendored official helpers in `plumbing/yue2_instrumental/` |

Checks across all 23 scores:

- every Vocal note is present in Ins (pitch + onset + duration);
- Vocal has **0** sounding notes and keeps its chord symbols;
- Ins is monophonic; **0** original Ins notes overlapped Vocal in this batch, so
  all intro/interlude/fill notes were kept unchanged;
- duration, tempo, meter and key are unchanged;
- caps are unchanged from round 01 (`headroom 250` in the dry-run);
- `ما خلاص` had a `% silence` section label; it was normalized to `% outro`
  (recorded in its report).

## Recipe

Same as round 01 except the score files:

| | |
|---|---|
| Manifest | `manifests/fadhl_shaker_instrumental_02.json` |
| Style | each song's `full_instrumental` caption, verbatim |
| Lyrics | `[Instrumental]` only |
| Score | the **instrumentalized** ABC (`Vocal` = rests, `Ins` = melody) |
| `cot` | `melody` |
| LoRA | `lora_ar_scale: 0`, `lora_nar_scale: 0` |
| Trigger | `false` |
| Seed | `20261106` |

## Commands

```bash
# validate (no GPU)
python3 generate.py manifests/fadhl_shaker_instrumental_02.json --dry-run

# smoke test: first song only (أنا من آخرها)
python3 generate.py manifests/fadhl_shaker_instrumental_02.json \
  --limit 1 --label fadhl_inst_02_smoke

# compare against the six you already have from round 01
python3 generate.py manifests/fadhl_shaker_instrumental_02.json \
  --limit 6 --label fadhl_inst_02_first6

# full batch (~23 x 6.5 min ≈ 2.5 h on a T4)
python3 generate.py manifests/fadhl_shaker_instrumental_02.json \
  --label fadhl_inst_02
```

The round 01 run can be stopped; its first 6 takes are still useful as the
"before" condition.

## What to listen for

- **No sung words / no gibberish vocal lead.** The score has no Vocal notes.
- **The lead instrument carries the original melody** (it is the old Vocal line,
  now on Ins).
- **Intros, interludes and fills survive** (they were already on Ins and were
  not overlapped, so they were kept).
- **Section timing and length** should match round 01; the score duration is
  unchanged.

If a take still has a faint vocal texture, that is a model artifact, not a
planned vocal line. The next fallback is source separation on the finished WAV
(keep the instrumental stem), but try the score surgery first.
