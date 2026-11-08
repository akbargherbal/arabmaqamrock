# Round 15 — القصة وما فيها: the section plan comes from the score

**Written:** 2026-11-08
**Based on:** `fadhl_shaker_instrumental_14.json` (same style, same seeds)
**Score:** `scores/fadhl_shaker_instrumental/al_qissa_wama_fiha.abc` (319.1 s, Cm, 91 BPM, 2/4)
**Seed:** paired with round 14 — the only variable is the lyrics.

## 0. What is being tested

One thing: **the lyrics form**. The style prompt and the adapters are frozen at
round 14's winning take, and the seed is identical to a take we already have, so
the comparison is paired.

| | round 14 `c2_studio_v9_ar085_neg` | round 15 `c3_sections_a/b` |
|---|---|---|
| style | studio band session (with the neg tail) | **identical** |
| AR / NAR | 0.85 / v9 @1.0 | **identical** |
| lyrics | `[intro] [instrumental] [outro]` | **the score's own sections** |
| cap | 9200 | **score + 60 s = 9479** (computed, see §3) |
| seeds | 1206942805, 96443261 | **the same two** |

Round 14 at those seeds produced **294.1 s** and **300.0 s** against a 319.1 s
score — both arrived 19–25 s early, with a 3-tag plan that says nothing about
where the sections are. Round 15 asks the score to say it instead.

## 1. The score already knows its own sections

Every `% label` line in the ABC is the transcriber's own segmentation. The tags
are read straight out of the score, so this works for all 488 songs with no
per-song editing:

```json
"defaults": { "lyrics_from_score": true, "cot": "full", "lora": "instrumental_v9" }
```

`al_qissa_wama_fiha` yields eleven sections:

| start | length | transcriber says | tag sent |
|---|---|---|---|
| 0.0 s | 13.2 s | intro | `[intro]` |
| 13.2 s | 56.7 s | chorus | `[chorus]` |
| 69.9 s | 21.1 s | interlude | `[bridge]` |
| 91.0 s | 30.3 s | verse | `[verse]` |
| 121.3 s | 7.9 s | chorus | `[chorus]` |
| 129.2 s | 21.1 s | interlude | `[bridge]` |
| 150.3 s | 30.3 s | verse | `[verse]` |
| 180.7 s | 7.9 s | chorus | `[chorus]` |
| 188.6 s | 21.1 s | interlude | `[bridge]` |
| 209.7 s | 30.3 s | verse | `[verse]` |
| 240.0 s | **79.1 s** | chorus | **`[outro]`** |

That last row is the point: the transcriber labelled 79 s of Vocal-rest-only
melody "chorus", but it is the instrumental ending of the song. The last comment
becomes `[outro]` — exactly the END signal the bare form never carried.

The plan that goes into the prompt:

```
[intro]
[chorus]
[bridge]
[verse]
[chorus]
[bridge]
[verse]
[chorus]
[bridge]
[verse]
[outro]
```

### Mapping rules (implemented in `generate.py`)

- one tag per line, untimed, nothing inside the brackets — the ABC already owns
  the timing;
- labels are lower-cased and a trailing take number is dropped (`verse 2` →
  `verse`, `chorus 1a` → `chorus`);
- `interlude` → `bridge` (a contrast section between sung ones), `silence` /
  `ending` / `end` → `outro`;
- a label repeated in place is one section, not two;
- labels outside the six-tag vocabulary (`intro, verse, pre-chorus, chorus,
  bridge, outro`) are dropped with a warning — a batch is not failed over one
  odd comment;
- **the last section always becomes `outro`**;
- a score with no usable labels is an error, because then there is no plan.

`--dry-run` prints the resulting plan per score, so a 488-song batch can be
audited before any GPU time.

## 2. Why this and not another hand-written plan

`[intro] / [instrumental] / [outro]` was a constant: three tags for every song
regardless of structure. It was adopted because it beat the bare form, not
because it described any song. The score's comments describe *this* song, and
they cost nothing to extract.

## 3. The cap is computed from the length of the piece

The cap was the last hand-maintained number in every instrumental manifest. It is
gone: with no `cap` and no `quantile`, a song with a score takes
`cap = ceil(score_s × 25) + 60 s × 25`.

This does not touch the quantile fit. `quantile` is the maqamrock path — it sizes
a song by how much Arabic text it has, and it still wins whenever it is written,
alone or in `defaults`. The instrumental path has no Arabic text at all (a tag
plan counts as zero letters, and the fit's floor is 110 s), so its length can
only come from the piece it is covering: the score. That is the whole rule.

The 60 s is measured, not chosen. Across the 16 takes on this score in rounds
11–14, the ones that finished landed between **−79 s and +43 s** of the score:

| overshoot vs score | takes |
|---|---|
| −79 … −7 s (ends early) | 11 |
| −5 … +3 s (matches the score) | 4 |
| +32, +42.5 s (long, still finished) | 2 |
| **+48.9 s → hit the cap at 368.0 s** | 1, truncated |

So the old built-in suggestion `need + 10 s` would have cut two takes that were
worth keeping, and 49 s was where the margin started costing takes. 60 s is that
margin rounded to a number with no decimals left to argue about.

Worth stating plainly: the same rule explains the earlier "sudden endings" on
this song. `cap 8229` was exactly `score + 10.0 s`, and the take ended at
329.158 s = 8229 / 25. The model was not stopping; it ran out of tokens at full
level.

A take that still reaches 379 s is a runaway and worth rejecting on its own
merits — the cap bounds it, it does not create the ending.

### Two margins, not one

- **Score vs source audio** — 24/24 Fadl Shaker scores against the download
  manifest's `duration_s`: mean **+1.91 s**, median +1.80 s, max **+5.83 s**
  (+2.0%), and only one score is shorter than its audio. A 5–10 s excess is
  normal (bar quantisation plus the last note's tail) and is **not** a
  transcription error; it is also the safe direction for a cap.
- **Cap headroom** — 60 s over the score, because *generation* drifts past the
  score by up to +43 s even when the score is exact. This number is about the
  model, not about the transcription.

## 4. Run

```bash
cd /content/arabmaqamrock && git pull
python3 generate.py manifests/fadhl_shaker_instrumental_15.json \
  --label fadhl_shaker_instrumental_15
```

2 takes, ~13 min on a T4, ~9 min on an L4.

## 5. Judging

A/B each take against its round-14 twin (same seed, same style, same adapters):

| seed | round 14 (3 tags) | round 15 (score plan) |
|---|---|---|
| 1206942805 | 294.1 s | ? |
| 96443261 | 300.0 s | ? |

- **Ending.** Duration vs 319.1 s, sidecar `truncated`, and last-10 s RMS (a real
  close fades below −30 dB; a cut sits near −15).
- **Does it reach the outro?** The `[outro]` tag lands at 240.0 s and the ending
  runs to 319.1 s. A take that stops near 240 s means the model read the tag as
  "end now".
- **Cadence.** The last phrase should resolve, not stop mid-bar.
- **Vocal leakage.** The style says *Arabic instrumental cover* and no tag is a
  lyric line; any words, syllables, humming or choir in a take is a regression.
- **Level-match** before any taste call.

If the 11-tag plan makes the model rush sections, the fallback is one new option
on the same extractor (first section + last section only: `[intro] [chorus]
[outro]`), not another style experiment.
