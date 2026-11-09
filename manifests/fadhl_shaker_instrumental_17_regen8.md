# Round 17 — the 8-song prompt A/B

**Written:** 2026-11-09
**Manifest:** `manifests/fadhl_shaker_instrumental_17_regen8.json` — 8 songs, 8 tracks
**Baseline:** round 16 (`20261108-191143_fadhl_shaker_instrumental_16`) — the same
8 songs, the same seeds and caps, so every take here has a round-16 take of the
same song to A/B.

## 0. What is being tested

One variable only: the style prompt. Everything else is copied from round 16's
`batch_manifest.json`:

| | round 16 | round 17 |
|---|---|---|
| style | 881 chars, `layered violin ...`, `expressive ornamented melody` | **992 chars, violin/cello supporting the oud, call-and-response** (§1) |
| seeds | random at plan time | **same 8 seeds, pinned explicitly** |
| caps | score + 60 s | **same 8 caps, pinned explicitly** |
| scores | 8/8 unchanged (sha256 verified) | identical files |
| adapters | `instrumental_v9`, AR 0.85 / NAR 1.0 | identical |
| lyrics | each score's own section plan | identical |
| cot / trigger / quantile | `full` / off / default 0.95 | identical |

The seed and cap values were read from the round-16 run archive
(`local_workspace/20261108-191143_fadhl_shaker_instrumental_16.zip`,
`batch_manifest.json` + `batch_summary.txt`), not retyped from memory.

## 1. The new prompt

```json
"style": "Arabic instrumental fusion, oriental ensemble, cinematic Arabic
          orchestral feel, Arabic instrumental cover, studio band session,
          musicians tracked together in one room, real acoustic oud with plucked
          pick attack and finger slides, violin and cello sections supporting the
          oud, played by hand with bow noise and vibrato, full ensemble swelling
          together like a small orchestra, fretted bass guitar, acoustic drum kit
          with natural ghost notes, darbuka, riq, daf with skin and jingle
          detail, expressive ornamented melody passed between oud, violin and
          cello in call and response, plucked oud answering the bowed strings,
          microtonal inflections, human timing with slight push and pull,
          breathing dynamics, dramatic dynamic builds and releases, spacious
          studio room, medium natural reverb, warm analog tape saturation,
          close-miked with room mics for ensemble width, clean and clear
          recording, polished studio mix, no audience, no applause, no crowd
          noise, no stage ambience, not a concert recording"
```

Two phrase changes against round 16: `layered violin and cello sections` →
`violin and cello sections supporting the oud`, and `expressive ornamented
melody` → `expressive ornamented melody passed between oud, violin and cello in
call and response, plucked oud answering the bowed strings`.

## 2. The eight takes

| song | seed | cap |
|---|---|---|
| al_qissa_wama_fiha | 133650760 | 9479 |
| ana_min_akhiraha | 2920347328 | 7704 |
| awwal_ma_bashufak | 1225284918 | 7586 |
| hazak_ya_albi | 4024966470 | 10667 |
| lelheen_3ayesh | 1553864377 | 8692 |
| lissa_alhala_matasarish | 994615997 | 7280 |
| saneen_alshawq | 1406106439 | 8575 |
| ya_tkoon_habibi | 1024770459 | 9800 |

## 3. Run

```bash
python3 generate.py manifests/fadhl_shaker_instrumental_17_regen8.json --dry-run
python3 generate.py manifests/fadhl_shaker_instrumental_17_regen8.json \
    --label fadhl_shaker_instrumental_17_regen8
```

Dry-run: 8 songs / 8 tracks, no cap warnings, projected ~52 min on a T4.
Output: `out/<timestamp>_fadhl_shaker_instrumental_17_regen8/`.
