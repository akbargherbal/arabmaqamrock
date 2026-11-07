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
| `controls.example.json` | 4 | Control sweep: same seed/score-free `cot=full` plan, one variable per take (`guidance_scale`, `semantic_temperature`, adapter scale). |
| `easygoing-eagle.json` | 9 | Nahawand melody-only control sweep on `VAR_A`, one seed (`2020610301`), one variable per take; plus one score-free plan take for `abc_*`. |
| `04.json` | 3 | Nahawand `VAR_A/B/C` takes on the dated scores in `scores/30102026/`, `cot=melody`. |
| `1332683623_baghdad_moon_formatted.json` | 3 | Track 01 takes on `scores/1332683623_refined_score.abc`. |
| `baghdad_moon_formatted.json` | 2 | Track 02 `v1`/`v2`, octave-fix scores, `cot=full`. |
| `baghdad_moon_spec.json` | 6 | Original A/B spec for tracks 01–03: score vs vanilla. |
| `moon_edit.json` | 9 | Round 1: `clean`/`v1`/`v2` x 3 seeds, `cot=melody`. |
| `moon_edit2.json` | 6 | Round 2: `clean`/`mid` x 3 seeds, `cot=melody`. |
| `pragmatic-grasshopper_ibn_zuraiq_formatted.json` | 4 x 3 | Four-song Ibn Zuraiq batch, no score. |
| `tarab_test_01.json` | 5 | Tarab A/B listening test on `moon_101_v2`. |
| `fadhl_shaker_instrumental_01.json` | 23 | Base model (LoRA scale 0), `cot=melody`, `[Instrumental]`, full-instrumental captions from the Fadhl Shaker shortlist; see the companion `.md`. |
| `fadhl_shaker_instrumental_02.json` | 23 | Round 02: same recipe on scores converted with the official YuE2 Vocal → Ins instrumental workflow (no vocal melody left to sing). |
| `fadhl_shaker_instrumental_03_prompts.json` | 8 | Round 03: caption sweep on one song (`أنا من آخرها`), from the original full-instrumental caption to a one-word `instrumental` prompt; same instrumentalized score and seed. |
| `fadhl_shaker_instrumental_04_lora_habeetak.json` | 6 | Round 04: third-party instrumental AR LoRA on one song (`حبيتك`); original vs Vocal → Ins score, AR scale 1.0 vs 0.75, a base-model control, and a text-only LoRA diagnostic. |

Validate any manifest without a GPU:

```bash
python3 generate.py manifests/<name>.json --dry-run
```
