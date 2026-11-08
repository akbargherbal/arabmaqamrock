# Round 08 — adopt `g4` and scale to ten songs

**Written:** 2026-11-08
**Round 07 run:** `gs://akbar-december-2024-backup/arabmaqamrock/runs/20261108-045356_fadhl_shaker_instrumental_07_prompt_sweep/`
**Verdict source:** the user, listening to the six round-07 takes on `حبيتك`.

## 1. The verdict

| take | verdict |
|---|---|
| `g0_bare` | rejected — "no feel", no Arabic character |
| `g1_cover` | rejected — "no feel" |
| `g2_dense` | rejected — "no feel" |
| `g3_prose` | better, but not enough; ending still abrupt |
| **`g4_arabic`** | **winner** — Arabic/Middle-Eastern feel, good ending, closest to the original song |
| `g5_sections` | good but "sounds more electronic" |

Decision: **`defaults.style` = the `g4_arabic` string**, i.e. the `g2` production
words plus the single corpus-level word `Arabic`:

```
Arabic instrumental cover, full band ensemble, layered arrangement, clear lead
melody, continuous accompaniment, busy instrumentation, no empty space, rich
full production, no vocals, no singing, no vocal chops
```

No instrument names, no tempo, no key. That matches the round-07 hard
constraint: it scales to ~500 songs unchanged.

### What the measurements said (they agree with the ears)

Level-free tonal balance relative to each take's own integrated LUFS, band
levels in `/tmp/opencode/r7/metrics.json`:

- `g0_bare` — lightest bass (−9.0 dB in 20–80 Hz), brightest top: thin, no weight.
- `g1_cover` — 6.3 dB quieter than `g3`, crest 20.6 (sparse), **30 s shorter**
  than the score (240.1 s vs 269.7 s): it dropped a section.
- `g2_dense` — most energy in 200–500 Hz but −7 to −8 dB above 1.2 kHz, crest
  13.0, 99.5 % frame occupancy: loud, dark and squashed = "busy but boxy".
- `g4_arabic` — forward mids, and the only take whose level sits between `g3`
  and `g2` without the dark roll-off.

So "no feel" was not a taste accident: `g0`/`g1` were thin, `g2` was dull.

### `g5` is rejected on purpose

`g5` = `g2` + score-derived section tags. The user heard it as "more electronic".
The `[intro]`/`[verse]`/`[chorus]` tags pull the model toward the pop/EDM
grammar it learned from the caption corpus. **Do not auto-generate section tags
for the batch** — this closes the `g5 > g2` branch of the round-07 decision
matrix. Section tags may still be useful for a single pop cover, never as a
corpus default.

## 2. The sudden outro — diagnosed, not yet fixed

Measured tail shape (last seconds, dB RMS):

| take | −5 s | −3 s | −2 s | −1 s |
|---|---|---|---|---|
| `g3_prose` | −20.0 | −29.8 | −37.5 | −79.5 |
| `g4_arabic` | −18.0 | −19.0 | −26.3 | −51.5 |
| `g5_sections` | −17.4 | −18.5 | −19.1 | −39.6 |
| `g0_bare` | −41.6 (long fade: −33 dB over the last 15 s) | −44.1 | −47.9 | −58.0 |

Cause, from the generation traces and the scores:

1. `g3`/`g4`/`g5` stop by themselves (`yue2.semantic.truncated 0`, 6474–6700
   tokens of a 6993 cap), i.e. the model chooses the end. `g0` is the only take
   flagged `truncated: true`.
2. It ends at the **last melodic bar**. `habeetak` is 269.7 s; four trailing
   bars (~9.5 s) carry chords and rests only → melody ends at ~260 s, and `g4`
   stops at 259.0 s.
3. That last melodic bar is a short note plus filler rest (`g4z24z4`), and the
   last chord of the score is `F` (♭VII in Gm), not the tonic. So the music is
   still at full level when the melody runs out, and the chord never resolves.

The same shape appears in every score in `scores/fadhl_shaker_instrumental/`:
the final Ins bar ends with `z24`/`z16`/`z12` and a `Z`-rest, while the chord
voice keeps playing 2–4 extra bars that the model ignores.

`g4` was judged "ending is good", so this is **not a blocker** — but it is a
systematic score defect worth one mechanical fix (hold the final tonic for a
bar and land the last chord on the tonic). That edit must be applied to the
**score**, not the prompt, and uniformly to all 23 scores. Deferred until the
ten-song batch shows how bad it is across keys.

## 3. This manifest

`manifests/fadhl_shaker_instrumental_08_g4_batch10.json` — ten songs, one take
each, the `g4` string in `defaults.style`, everything else per song is
`name` + `score` + `lyrics` + `cap` + `seed`.

Subset chosen for spread, not for comfort:

| song | key | BPM | score |
|---|---|---|---|
| `habeetak` | Gm | 101 | 269.7 s |
| `al_hal` | Gm | 90 | 248.7 s |
| `fustan_alhelwa` | Cm | 98 | 202.0 s |
| `ghayb` | Fm | 74 | 236.8 s |
| `ma_khalas` | Cm | 150 | 287.6 s |
| `ya_tkoon_habibi` | F | 90 | 332.0 s |
| `awwal_ma_bashufak` | C#m | 88 | 243.4 s |
| `ana_min_akhiraha` | Em | 125 | 248.2 s |
| `waynak_habib` | Gm | 87 | 233.8 s |
| `saharni_alshawq` | Em | 125 | 256.1 s |

`seed 20261106` everywhere, so `habeetak` must come out **byte-identical to
round 07's `g4_arabic`** — a free reproducibility check of the whole pipeline.

### `cap` is per song and must stay per song

`lyrics: "[instrumental]"` contains no Arabic letters, so the automatic
`duration_cap` falls back to the quantile floor — **110 s / 2750 tokens** — and
would chop every song in half. The cap must come from the score:

```
cap = ceil(abc_duration_s * 25) + 250
```

`python3 generate.py … --dry-run` prints `score_s -> frames, cap, headroom` and
warns when the headroom is gone, so a bad cap cannot pass silently.

## 4. Run

```bash
cd /content/arabmaqamrock && git pull
python3 generate.py manifests/fadhl_shaker_instrumental_08_g4_batch10.json \
  --label fadhl_inst_08_g4_batch10
```

≈65 min projected on a T4 (≈35 min on the L4 used for round 07).

Judge the batch on: does each song still read as Arabic (not the `g2` dark
boxiness), and how many sudden endings survive.
