# YT500 instrumental — legitimate-track dataset

460 instrumental takes from the YT500 corpus, each in its own folder with the
audio, the section tag plan, the style prompt, the score and the take metadata.

## What "legit" means

A take is included when its rendered duration is within ±15% of the score's
nominal length, its sidecar says `status: ok` / `exit: 0`, and its score hash
matches the frozen corpus. The 7 severe-short takes are excluded; 22 borderline
takes can be added later through an accept file. The full audit is
`quality_audit_duration.json` in the generation outputs.

## Layout

```
tracks/<name>/
  audio.mp3     the kept take (3.02 GB total)
  lyrics.txt    section tag plan used for this take
  style.txt     exact style prompt used
  score.abc     instrumental ABC score
  track.json    ids, hashes, seed, provenance
catalog.jsonl   one row per track, tag plan inlined
catalog.csv     spreadsheet view
catalog.md      human-readable table
playlist.m3u    rank order
recipe/         canonical style + LoRA/scales/CoT
```

## Important: the "lyrics" are section tags

`lyrics.txt` is the tag plan derived from the score's `% section` comments
(`[intro]`, `[verse]`, `[chorus]`, …). It is what the LoRA was conditioned on,
not sung words. `track.json` records `"kind": "section_tags"` so consumers are
not misled.

## Recipe

- Style: `recipe/style.txt`, sha256 `bddaf3f9071ec2f15cbc28c19514361b0eaa73784a19670262e0fa90575fd8b5`
- CoT: `full`
- LoRA: `instrumental_v9` (AR scale 0.85,
  NAR scale 1.0)
- Trigger: `False`

The style prompt:

```
Arabic instrumental fusion, oriental ensemble, cinematic Arabic orchestral feel, Arabic instrumental cover, studio band session, musicians tracked together in one room, real acoustic oud with plucked pick attack and finger slides, violin and cello sections supporting the oud, played by hand with bow noise and vibrato, full ensemble swelling together like a small orchestra, fretted bass guitar, acoustic drum kit with natural ghost notes, darbuka, riq, daf with skin and jingle detail, expressive ornamented melody passed between oud, violin and cello in call and response, plucked oud answering the bowed strings, microtonal inflections, human timing with slight push and pull, breathing dynamics, dramatic dynamic builds and releases, spacious studio room, medium natural reverb, warm analog tape saturation, close-miked with room mics for ensemble width, clean and clear recording, polished studio mix, no audience, no applause, no crowd noise, no stage ambience, not a concert recording
```

## Fetch

```bash
# one track
gsutil -m cp -r gs://akbar-december-2024-backup/DATASET/yt500_instrumental/tracks/<name> .

# the catalogue
gsutil cp gs://akbar-december-2024-backup/DATASET/yt500_instrumental/catalog.jsonl .

# all audio (≈3.0 GB)
gsutil -m cp gs://akbar-december-2024-backup/DATASET/yt500_instrumental/tracks/*/audio.mp3 .
```

Built 2026-11-11T16:19:45Z.
