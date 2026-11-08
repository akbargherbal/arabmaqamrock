# Round 10 — the Fadl Shaker pilot (24 songs)

**Written:** 2026-11-08
**Source:** `gs://akbar-december-2024-backup/DISCOGRAPHY/fadhl_shaker_selected`
**Purpose:** the last check before the ~488-song corpus. Same string, 24 songs,
nothing per-song.

## What is ready

`fadhl_shaker_selected` has **24** items. Scores for all **24** now exist in
`scores/fadhl_shaker_instrumental/` — they went through the Vocal → Ins surgery
and are byte-frozen in the repo. The last one, القصة وما فيها (319.0 s), was
transcribed with `--full` and instrumented for this manifest:

| song | duration | action |
|---|---|---|
| القصة وما فيها | 319.0 s | transcribed + instrumentalized (`al_qissa_wama_fiha`) |

There is no other gap: every other title in the manifest matches a score slug.

Overlap with the 488-song corpus: **one song** (`فين لياليك`). The pilot is
independent work, not a preview of the batch.

## Style string

Set to the **round 09 winner, `h2_maqam`** (202 chars):

```
Arabic instrumental cover, full band ensemble, layered arrangement, clear lead
melody, continuous accompaniment, rich full production, maqam, Middle Eastern
scales, no vocals, no singing, no vocal chops
```

## Score coverage — verified, not assumed

Every score's `nominal_seconds` (`scores/fadhl_shaker_instrumental/reports/`) was
matched against the manifest's `duration_s`: **24/24 pairs, worst delta 5.83 s**
(`bafakker_bil_sa3at`, score quantisation), most under 3 s. No extra scores, no
orphan scores.

| song | audio | video |
|---|---|---|
| القصة وما فيها | 319.0 s | `qcpbb4sFyY4` |

## Sizes

| | |
|---|---|
| songs / takes | 24 / 24 |
| projected | ~149 min on T4, ≈80-90 min on L4 |
| seed | 20261106 everywhere (one take each, comparable to `habeetak`) |
| cap | `ceil(score_s * 25) + 250`, per song |
| trigger | false (permanent, see round 09 note) |

## Pass criteria

The pilot is a gate, not a deliverable. It passes only if, across 24 songs and
several keys:

1. the Arabic idiom survives without the word `Arabic` being repeated per song;
2. no song collapses into the `g2` dark/boxy signature;
3. fewer than ~20 % of takes have an unusable sudden ending;
4. at least 20 of 24 are worth keeping.

Anything less and the 488-song batch waits.
