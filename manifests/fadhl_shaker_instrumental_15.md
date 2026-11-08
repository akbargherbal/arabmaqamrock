# Round 15 — the 24 Fadl Shaker songs, one recipe

**Written:** 2026-11-08
**Manifest:** `manifests/fadhl_shaker_instrumental_15.json` — 24 songs, 24 tracks
**Scores:** `scores/fadhl_shaker_instrumental/*.abc` (24/24 parse)
**Baseline:** round 10 (`20261108-062853_fadhl_inst_10_pilot24`) — same 24 songs,
same seed, so every take here is a paired A/B against a take we already have.

## 0. What is being tested

Not one song. The whole pilot set, with the four things we settled on since:

| | round 10 (baseline) | round 15 |
|---|---|---|
| style | `h2_maqam`, 202 chars | **studio band session**, 654 chars (§1) |
| lyrics | `[instrumental]` on all 24 | **each score's own sections** (§2) |
| adapters | `instrumental` alias, NAR off | **`instrumental_v9`, AR 0.85 / NAR 1.0** |
| cap | `ceil(score×25) + 250` (10 s) | **score + 60 s, computed** (§3) |
| seed | 20261106 | **20261106 — unchanged** |
| takes | 1 per song | 1 per song |

One take per song is deliberate: the seed is fixed, so track *N* here and track
*N* in round 10 are the same song at the same seed, differing only in the recipe.
24 songs, 24 comparisons, no per-song tuning anywhere.

## 1. The recipe, written once

```json
"defaults": {
  "style": "Arabic instrumental cover, studio band session, musicians tracked
            together in one room, real acoustic oud with plucked pick attack and
            finger slides, violin and cello played by hand with bow noise and
            vibrato, fretted bass guitar, acoustic drum kit with natural ghost
            notes, darbuka, riq, daf with skin and jingle detail, expressive
            ornamented melody, microtonal inflections, human timing with slight
            push and pull, breathing dynamics, intimate studio room, short
            natural reverb, warm analog tape saturation, close-miked, clean and
            clear recording, polished studio mix, no audience, no applause,
            no crowd noise, no stage ambience, not a concert recording",
  "lyrics_from_score": true,
  "cot": "full",
  "lora": "instrumental_v9",
  "lora_ar_scale": 0.85,
  "lora_nar_scale": 1.0,
  "seed": 20261106,
  "trigger": false
}
```

Every song is two lines: its name and its score alias. No style, no lyrics, no
cap, no seed — nothing that could drift between songs.

`defaults.seed` is new: one seed for the whole batch, so a 24- or 488-song run is
reproducible and pairable. A per-song `seed` still wins.

## 2. The lyrics: each score's own section plan

`lyrics_from_score` reads the transcriber's `% label` comments:

- one tag per line, untimed, nothing inside the brackets (the ABC owns timing);
- `interlude` → `bridge`, `silence`/`ending`/`end` → `outro`;
- a label repeated in place is one section;
- the **last section always becomes `[outro]`** — the END signal the bare form
  never carried;
- labels outside `intro, verse, pre-chorus, chorus, bridge, outro` are dropped
  with a warning; a score with no usable labels is an error.

All 24 scores give a plan; 194 tags, 6–14 per song (mean 8.1):

| song | plan |
|---|---|
| `al_dawr_ala_meen` | intro verse chorus bridge verse chorus **outro** |
| `al_hal` | intro verse chorus bridge verse chorus **outro** |
| `al_qissa_wama_fiha` | intro chorus bridge verse chorus bridge verse chorus bridge verse **outro** |
| `ana_min_akhiraha` | intro verse chorus bridge verse **outro** |
| `awwal_ma_bashufak` | intro verse chorus bridge chorus verse **outro** |
| `badeet_atib` | intro verse chorus bridge verse **outro** |
| `bafakker_bil_sa3at` | intro verse chorus bridge verse chorus **outro** |
| `feen_layalik` | intro verse chorus bridge verse chorus bridge chorus **outro** |
| `fustan_alhelwa` | intro verse chorus bridge verse chorus **outro** |
| `ghayb` | intro verse chorus bridge verse chorus **outro** |
| `habeetak` | intro verse chorus bridge verse chorus **outro** |
| `hazak_ya_albi` | intro chorus verse chorus bridge verse chorus bridge verse **outro** |
| `leh_aljarh` | intro verse chorus bridge verse chorus verse **outro** |
| `lelheen_3ayesh` | intro verse chorus bridge verse **outro** |
| `lissa_alhala_matasarish` | intro verse chorus bridge verse chorus **outro** |
| `ma3_alsalama` | intro verse chorus bridge verse chorus **outro** |
| `ma_khalas` | intro verse chorus bridge verse chorus bridge verse chorus **outro** |
| `mata_habibi_mata` | intro verse chorus bridge verse chorus bridge verse chorus **outro** |
| `min_kothr_hobbi_feek` | intro verse chorus bridge verse bridge verse chorus **outro** |
| `saharni_alshawq` | intro verse chorus bridge verse chorus **outro** |
| `saneen_alshawq` | intro verse bridge verse bridge verse chorus **outro** |
| `waynak_habib` | intro verse pre-chorus chorus bridge verse chorus **outro** |
| `ya_hawa_alghaleen` | intro verse chorus verse chorus bridge verse chorus bridge verse chorus bridge chorus **outro** |
| `ya_tkoon_habibi` | intro verse chorus bridge verse chorus bridge verse **outro** |

`--dry-run` prints these per song, so the plans can be audited before the run.

## 3. The cap: computed from the length of the piece

No `cap` and no `quantile` in this manifest: a song with a score takes
`cap = ceil(score_s × 25) + 60 s × 25`. Here that is **6551 … 10685** tokens
(262 … 427 s) for scores of 202.0 … 367.4 s.

The `quantile` fit is the maqamrock path (lyrics → length) and is untouched: it
still wins whenever it is written. The instrumental path has no Arabic text at
all — a tag plan counts as zero letters, and the fit's floor is 110 s — so its
length can only come from the score.

The 60 s is measured, not chosen. Across the 16 takes on `al_qissa_wama_fiha`
in rounds 11–14, finishing takes landed between −79 s and +43 s of the score:

| overshoot vs score | takes |
|---|---|
| −79 … −7 s (ends early) | 11 |
| −5 … +3 s (matches the score) | 4 |
| +32, +42.5 s (long, still finished) | 2 |
| +48.9 s → hit the cap at 368.0 s | 1, truncated |

### Two margins, not one

- **Score vs source audio** — 24/24 scores against the download manifest's
  `duration_s`: mean **+1.91 s**, median +1.80 s, max **+5.83 s** (+2.0%), and
  only one score is shorter than its audio. A 5–10 s excess is normal (bar
  quantisation plus the last note's tail) and is **not** a transcription error;
  it is also the safe direction for a cap.
- **Cap headroom** — 60 s over the score, because *generation* drifts past the
  score by up to +43 s even when the score is exact. This number is about the
  model, not about the transcription.

A take that still reaches its cap is a runaway and worth rejecting on its own
merits; the cap bounds it, it does not create the ending.

## 4. Sizes and the run

| | |
|---|---|
| songs / tracks | 24 / 24 |
| source length | 110 min total (202.0–367.4 s, median 276.3 s) |
| projected | ~156 min on a T4; ~80–90 min on an L4 (round 10 measured 191 s/track) |

```bash
cd /content/arabmaqamrock && git pull
python3 generate.py manifests/fadhl_shaker_instrumental_15.json \
  --label fadhl_shaker_instrumental_15
```

## 5. Judging: 24 paired A/Bs

The round-10 take for each song is `<slug>_20261106.wav` in
`runs/20261108-062853_fadhl_inst_10_pilot24/`; round 15 writes the same
filename. Level-match before comparing (v9 is hotter).

**Acceptance test — the six structural failures of round 10 must be gone:**

| song | score | round 10 | failure |
|---|---|---|---|
| `saharni_alshawq` | 256.1 | **120.7** | ended 135 s early |
| `ya_tkoon_habibi` | 332.0 | **240.0** | ended 92 s early |
| `ya_hawa_alghaleen` | 363.2 | 297.6 | ended 66 s early |
| `lelheen_3ayesh` | 287.7 | **240.0** | ended 48 s early |
| `al_qissa_wama_fiha` | 319.1 | 329.2 | cap cut at `score + 10.0` |
| `min_kothr_hobbi_feek` | 367.4 | 377.4 | cap cut at `score + 10.0` |

Per song, in order:

1. **Ending.** Duration vs the score, sidecar `truncated`, last-10 s RMS (a real
   close fades below −30 dB; a cut sits near −15).
2. **Does it reach the outro?** Each plan's `[outro]` starts where its score's
   last comment sits, not at the end; a take that stops there read the tag as
   "stop now".
3. **Band or box.** Bass guitar vs synth sub, kit vs loop, a player vs a preset.
4. **Vocal leakage.** No `no vocals` clause in this style; any words, syllables,
   humming or choir is a regression.

## 6. What this decides for the 488

If it holds across 24 songs and several keys, then the corpus batch needs
nothing per song: the style, the adapters, the section plan and the cap all come
from three `defaults` lines and the score. The only remaining unknowns for 488
are the sources themselves (AAC 128 kbps vs these CD rips) and transcription
throughput.
