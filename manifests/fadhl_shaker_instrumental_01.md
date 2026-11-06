# Fadhl Shaker — full instrumental from ABC (round 01)

**Goal:** test the **base YuE2** (v3 LoRA switched off) at turning the original
song's transcribed ABC into a complete **instrumental cover** — not just any
Arabic instrumental. This is the first round; later rounds change one variable
at a time to push fidelity to the original.

**Input:** `local_workspace/fadhl_shaker_selected_scores.zip` +
`local_workspace/full_instrumental_fadhl_shaker_shortlist.json`.

## Recipe

| | |
|---|---|
| Manifest | `manifests/fadhl_shaker_instrumental_01.json` |
| Songs | 23 (one take each) |
| Style | each song's `full_instrumental` caption, verbatim — **not** the normal vocal caption |
| Lyrics | `[Instrumental]` only |
| Score | the song's `score.abc`, extracted to `scores/fadhl_shaker/` |
| `cot` | `melody` (the cover path: melody staves, no chord symbols) |
| LoRA | `lora_ar_scale: 0`, `lora_nar_scale: 0` |
| Seed | `20261106` for every song (one controlled seed) |
| Cap | explicit per song = score duration × 25 + 250 frames |

### Why `lora_*_scale: 0` is the right way to switch the LoRA off

Yes — your assumption is correct. The runtime applies the adapter as a
weight-space interpolation per expert (`lora.cpp`): **1.0 = full adapter,
0.0 = base model** (`docs/suno-generation-controls.md` §D.10, and
`run_one.sh` says the same at the top). The adapter files still get loaded, but
their contribution is zero. Nothing needs to be deleted or renamed.

### Why the cap is explicit

The automatic cap is derived from the number of Arabic letters in the lyrics.
`[Instrumental]` has zero Arabic letters, so the auto cap would fall back to the
~111 s floor and truncate almost every song. The manifest sets the cap from each
score's own length instead. Dry-run reports `headroom 250` (10 s) for all 23.

### Why the trigger is off

`arabmaqamrock` is the **LoRA trigger word**, not a genre label. With the LoRA at
scale 0 it is noise, so the style must stay exactly the `full_instrumental`
caption. The manifest sets `"trigger": false` in `defaults`; `generate.py` then
leaves the style untouched. (`--no-trigger` is still available as a batch-wide
override, but it is no longer required here.)

## Commands

```bash
# validate the manifest (no GPU, writes nothing)
python3 generate.py manifests/fadhl_shaker_instrumental_01.json --dry-run

# smoke test: only the first song (أنا من آخرها), then listen before the batch
python3 generate.py manifests/fadhl_shaker_instrumental_01.json \
  --limit 1 --label fadhl_inst_01_smoke

# real run (~23 x 6.5 min ≈ 2.5 h on a T4)
python3 generate.py manifests/fadhl_shaker_instrumental_01.json \
  --label fadhl_inst_01
```

Outputs land in `out/<timestamp>_fadhl_inst_01/`. Each take has a sidecar with
the resolved seed, cap, cot, adapter scales, score hash and duration.

## Songs

| Song | Score alias | Score length | Cap |
|---|---|---:|---:|
| أنا من آخرها | `ana_min_akhiraha` | 248s | 6454 |
| أول مابشوفك | `awwal_ma_bashufak` | 243s | 6336 |
| الحال | `al_hal` | 249s | 6467 |
| الدور على مين | `al_dawr_ala_meen` | 243s | 6336 |
| بديت أطيب | `badeet_atib` | 220s | 5761 |
| بفكر بالساعات | `bafakker_bil_sa3at` | 303s | 7824 |
| حبيتك | `habeetak` | 270s | 6993 |
| حظك ياقلبي | `hazak_ya_albi` | 367s | 9417 |
| سنين الشوق | `saneen_alshawq` | 283s | 7325 |
| سهرني الشوق | `saharni_alshawq` | 256s | 6652 |
| غيب | `ghayb` | 237s | 6169 |
| فستان الحلوة | `fustan_alhelwa` | 202s | 5302 |
| فين لياليك | `feen_layalik` | 283s | 7336 |
| لسه الحاله ماتسرش | `lissa_alhala_matasarish` | 231s | 6030 |
| للحين عايش | `lelheen_3ayesh` | 288s | 7442 |
| ليه الجرح | `leh_aljarh` | 295s | 7619 |
| ما خلاص | `ma_khalas` | 288s | 7441 |
| متى حبيبي متى | `mata_habibi_mata` | 289s | 7463 |
| مع السلامة | `ma3_alsalama` | 217s | 5665 |
| من كثر حبي فيك | `min_kothr_hobbi_feek` | 367s | 9436 |
| وينك حبيب | `waynak_habib` | 234s | 6095 |
| يا تكون حبيبي | `ya_tkoon_habibi` | 332s | 8550 |
| يا هوى الغالين | `ya_hawa_alghaleen` | 363s | 9331 |

## The one missing song

`القصة وما فيها` is in the shortlist but **has no `score.abc` in the zip**. Its
`result.json` records `abc_error: "Measure 154 (beat rows 308-310):
non-consecutive beat IDs [1, 2, 2]"`, so SheetSage2 failed to export the ABC.
It is excluded from round 01. To add it later, re-transcribe the source MP3
(`./transcribe.sh <run>`) or repair the beat rows and re-export.

## Notes on tags (for the next round)

The scores already carry section markers as ABC comments
(`% intro`, `% verse`, `% chorus`, `% interlude`, `% outro`, sometimes `% bridge`
or `% pre-chorus`). This round deliberately uses only `[Instrumental]` because
`[Verse]`/`[Chorus]` may bias the model toward singing.

Round 02 can compare, at the same seed and score:

1. `cot=melody` + `[Instrumental]` (this round's recipe) —
2. `cot=full` (uses the chord symbols as well) —
3. mapped section tags, e.g. `[Instrumental | Intro]`, `[Instrumental | Verse]`, …
4. a score whose voice labels are neutralised (`V: Vocal` → `V: Lead`) to test
   whether the ABC's `Vocal` label pulls the model toward vocals.

## Fidelity to the original (the actual goal)

The target is a **recognizable instrumental cover of the original song**, not a
generic Arabic instrumental. The score is what carries the song's identity:

| The ABC carries | The ABC does not carry |
|---|---|
| tempo (`Q`), key (`K`), meter (`M`) | timbre and exact instrumentation |
| section order (`% intro`, `% verse`, `% chorus`, `% interlude`, `% outro`) | mix, reverb, production |
| `V: Vocal` — the original lead melody | drums, bass, and parts not transcribed |
| `V: Ins` — the original instrumental line | vocal ornaments that are not notes |
| note timing and density | — |

`cot=melody` keeps **both** melody staves and omits chord symbols. That is
deliberate: the project's transcription decision is melody-only because
SheetSage2's chord labels are Western-tonal and wrong for maqam
(`docs/plans/five-stars-abc-corpus.md` §3). So the score preserves the maqam
melody, not a Western chord grid.

The model cannot hear the original MP3. This is a symbolic guide, not
audio-to-audio (`docs/transcription.md`): it can reproduce the melody, key,
tempo and structure; it has to *invent* the arrangement from the caption.

### Fidelity levers, in order of expected effect

1. **Clean the score first.** Octave jumps, stray bars and obvious SheetSage2
   artifacts are reproduced faithfully. Fix them without rewriting the melody
   (the `maqam-edit` CLEAN pass, not the MID edit).
2. **Best-of-N seeds with a tighter sampler.** `semantic_temperature: 0.8` and
   `semantic_top_p: 0.9` make the output tighter and more repeatable
   (`docs/transcription.md`, “Controlling ABC influence”). Render 3 seeds and
   keep the take that tracks the melody.
3. **Keep both voices** (`Vocal` + `Ins`). The Ins line carries the original
   instrumental hook; do not strip it.
4. **Keep `cot=melody`.** `cot=full` adds the chord symbols; use it as a
   controlled comparison, not the default.
5. **Test neutral voice labels** (`V: Vocal` → `V: Lead`) as a controlled
   variable, to see whether the ABC label pulls the model toward singing.

## Round 02 shape (after round 01)

Pick 3 songs from round 01 (one ballad, one upbeat, one cinematic). For each:

- raw score vs CLEAN score;
- × 3 seeds at `semantic_temperature: 0.8`, `semantic_top_p: 0.9`;
- same `[Instrumental]`, LoRA 0, `cot=melody`.

That is 3 × 2 × 3 = 18 takes (~2 h). If that is too much, 2 songs × 2 × 2 =
8 takes still answers the main question: does cleaning the score beat a sampler
tweak?

## What to listen for

- **Vocal leakage** — the main risk. Any words, hums, or vocal-like lead?
- **Melody recognition** — can you hum the original over the generated lead?
- **Score following** — does the lead trace the transcribed melody, and do the
  section boundaries land at the right times?
- **Arabic idiom** — maqam colour, ornaments, oud/strings/percussion rather than
  generic Western pop.
- **Length/truncation** — sidecars record `truncated`; the longest scores are
  6+ minutes, so watch the tail.
- **Which songs work** — keep the score/song, not just a global pass/fail.

### Fidelity scorecard (1–5 per song)

| Criterion | Question |
|---|---|
| Melody recognition | Can you hum the original over the generated lead? |
| Section alignment | Do intro / verse / chorus / interlude land at the right times? |
| Instrumental purity | Any words, hums, vocal-like lead, or choir? |
| Arrangement match | Does it match the `full_instrumental` caption (oud, strings, darbuka, …)? |
| Overall | Would you call this a cover of the original, or just a new instrumental? |
