# Round 10 — the Fadl Shaker pilot (23 songs)

**Written:** 2026-11-08
**Source:** `gs://akbar-december-2024-backup/DISCOGRAPHY/fadhl_shaker_selected`
**Purpose:** the last check before the ~488-song corpus. Same string, 23 songs,
nothing per-song.

## What is ready

`fadhl_shaker_selected` has **24** items. Scores for **23** already exist in
`scores/fadhl_shaker_instrumental/` — they went through the Vocal → Ins surgery
and are byte-frozen in the repo. Only one song has no score:

| missing | duration | action |
|---|---|---|
| القصة وما فيها | 319.0 s | transcribe + instrumentalize before running the pilot, or accept a 23-song pilot |

There is no other gap: every other title in the manifest matches a score slug.

Overlap with the 488-song corpus: **one song** (`فين لياليك`). The pilot is
independent work, not a preview of the batch.

## Style string

Currently the `g4` string, as the current best. **Replace the single line in
`defaults.style` with the round-09 winner before running** — this manifest is a
container, the style is decided elsewhere.

## Sizes

| | |
|---|---|
| songs / takes | 23 / 23 |
| projected | ~149 min on T4, ≈80 min on L4 |
| seed | 20261106 everywhere (one take each, comparable to `habeetak`) |
| cap | `ceil(score_s * 25) + 250`, per song |
| trigger | false (permanent, see round 09 note) |

## Pass criteria

The pilot is a gate, not a deliverable. It passes only if, across 23 songs and
several keys:

1. the Arabic idiom survives without the word `Arabic` being repeated per song;
2. no song collapses into the `g2` dark/boxy signature;
3. fewer than ~20 % of takes have an unusable sudden ending;
4. at least 20 of 23 are worth keeping.

Anything less and the 488-song batch waits.
