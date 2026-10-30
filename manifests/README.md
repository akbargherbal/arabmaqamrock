# Manifests

Batch inputs for `generate.py`. Each file is one run: its `songs` list becomes the
tracks in `out/<timestamp>_<label>/`.

## Paths

Asset paths (`scores`, `abc_file`, `style_file`, `lyrics_file`, `loras`) are
resolved against `base_dir`. The manifests here set:

```json
"base_dir": ".."
```

so paths stay written from the repo root (`scores/...`, `prompts/...`) even though
the manifest lives in `manifests/`. A manifest with assets next to it can omit
`base_dir`; relative paths then resolve beside the JSON, as before.

## Index

| Manifest | Songs / takes | Notes |
|---|---:|---|
| `songs.example.json` | 2 | Quickstart example: inline lyrics + `lyrics_file`, no score. |
| `04.json` | 3 | Nahawand `VAR_A/B/C` takes on the dated scores in `scores/30102026/`, `cot=melody`. |
| `1332683623_baghdad_moon_formatted.json` | 3 | Track 01 takes on `scores/1332683623_refined_score.abc`. |
| `baghdad_moon_formatted.json` | 2 | Track 02 `v1`/`v2`, octave-fix scores, `cot=full`. |
| `baghdad_moon_spec.json` | 6 | Original A/B spec for tracks 01–03: score vs vanilla. |
| `moon_edit.json` | 9 | Round 1: `clean`/`v1`/`v2` x 3 seeds, `cot=melody`. |
| `moon_edit2.json` | 6 | Round 2: `clean`/`mid` x 3 seeds, `cot=melody`. |
| `pragmatic-grasshopper_ibn_zuraiq_formatted.json` | 4 x 3 | Four-song Ibn Zuraiq batch, no score. |
| `tarab_test_01.json` | 5 | Tarab A/B listening test on `moon_101_v2`. |

Validate any manifest without a GPU:

```bash
python3 generate.py manifests/<name>.json --dry-run
```
