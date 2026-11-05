# Base prompt

**Status:** adopted 2026-11-05. The canonical style text for new manifests is the
`english` condition of [`manifests/space-stallion.json`](../manifests/space-stallion.json):
the Arabic maqam name **plus its Western scale name**, written side by side.

The winning variable in that batch was the English scale name. Five poems were
rendered twice at the same NAR/CFG (`0.5 / 1.5`); the only difference was whether
the style ended with `Maqam Hijaz, mood: ...` or
`Maqam Hijaz, Phrygian Dominant, mood: ...`. The English-name variant was judged
better by ear. That is a listening finding, not a blind measurement (`n = 5`
pairs), so keep testing it, but it is now the default.

## Trigger word

`arabmaqamrock` is the LoRA trigger word, not a genre label. Its meaning is
exactly this:

```text
arabmaqamrock: LoRA trigger word.
arabmaqamrock: The music feels like a grand, solemn symphonic-rock ballad driven by a commanding, deeply resonant Arabic male vocal delivering ornate, hymn-like melodies over heavy guitars and sweeping orchestral strings.
```

Keep it at the start of the style text. `generate.py` prepends it automatically
when a style lacks it (disable with `--no-trigger`), but manifests normally carry
it explicitly.

## Template

```text
arabmaqamrock, classical arabic, melismatic, microtonal ornaments, belting, tarab, Khaliji, emotive expressive delivery, symphonic metal, powerful operatic performance, rhythm guitar, electric oud, epic, clear enunciation, vocal-forward mix, crisp consonants, audiophile, call and response, backing vocals, rich layered vocal harmonies, massive choir, Maqam <Maqam>, <Western scale>, mood: "<mood>"
```

## Example — Hijaz

```text
arabmaqamrock, classical arabic, melismatic, microtonal ornaments, belting, tarab, Khaliji, emotive expressive delivery, symphonic metal, powerful operatic performance, rhythm guitar, electric oud, epic, clear enunciation, vocal-forward mix, crisp consonants, audiophile, call and response, backing vocals, rich layered vocal harmonies, massive choir, Maqam Hijaz, Phrygian Dominant, mood: "longing, nostalgic, lush beauty"
```

## Maqam dictionary

| Maqam | Write beside it | Notes |
|---|---|---|
| Hijaz | `Phrygian Dominant` | augmented second between the 2nd and 3rd degrees |
| Kurd | `Phrygian Mode` | lowered 2nd gives the dark, tense colour |
| Nahawand | `Natural Minor Scale (Aeolian)` | closest Western relative |
| Ajam | `Major Scale (Ionian)` | closest Western relative |

These are **prompt hints, not theory claims.** A maqam is a melodic practice
with sayr, ajnas and ornamentation; the Western scale is only the nearest
familiar frame. Write both, and let the maqam name carry the idiom.

Current mood strings (they vary by poem, not by maqam):

| Maqam | Mood used in `space-stallion` |
|---|---|
| Hijaz | `"longing, nostalgic, lush beauty"` |
| Nahawand | `"melancholy, reflective, desolate journey"` |
| Ajam | `"heroic resolve, steady momentum, pride"` |
| Kurd | `"solemn majesty, nocturnal awe, stately power"` |

## Field order

The order is part of the recipe; keep it stable when editing.

| # | Segment | Example | Role |
|---:|---|---|---|
| 1 | Trigger | `arabmaqamrock` | LoRA trigger; must survive at the front |
| 2 | Idiom | `classical arabic, melismatic, microtonal ornaments, belting, tarab` | the Arabic vocal tradition |
| 3 | Region | `Khaliji` | regional colour; comes after `tarab` |
| 4 | Delivery | `emotive expressive delivery` | performance intent |
| 5 | Genre | `symphonic metal, powerful operatic performance` | the rock/metal frame |
| 6 | Instruments | `rhythm guitar, electric oud` | `electric oud` comes after `rhythm guitar` |
| 7 | Production | `epic, clear enunciation, vocal-forward mix, crisp consonants, audiophile` | clarity and mix |
| 8 | Vocal arrangement | `call and response, backing vocals, rich layered vocal harmonies, massive choir` | now part of the base, not an experiment |
| 9 | Mode | `Maqam Hijaz, Phrygian Dominant` | Arabic name first, Western name second |
| 10 | Mood | `mood: "..."` | always last |

## What is *not* in the base

These were tested and are not adopted:

- `mawwal` — removed.
- `a cappella` — removed.
- `antiphon` — removed.

`massive choir` is the opposite case: it started as an experiment and is now a
fixed part of the base.

Sampler settings are a separate axis from the prompt. `space-stallion` used
`lora_nar_scale: 0.5` and `guidance_scale: 1.5`, but those are not part of the
style text; change them only as a deliberate settings experiment.

## Where this is used

- Manifests: inline `style` strings, as in
  [`manifests/space-stallion.json`](../manifests/space-stallion.json) and
  [`manifests/cinnamon-bull-grid.json`](../manifests/cinnamon-bull-grid.json).
- [`README.md`](../README.md) — short version and the maqam table.
- [`docs/suno-generation-controls.md`](suno-generation-controls.md) — the
  Suno-side controls and prompt-rewriter findings; not this base prompt.
- [`prompts/`](../prompts/) — the older full-caption `*_style.txt` templates
  used by `run_one.sh`. They are an alternative to the tag-list base, not the
  base itself.
