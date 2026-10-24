# Session — Baghdad Moon ABC guide (2026-10-24)

Worked example for the optional transcription tool: transcribe an accepted
track, then use its ABC score to generate new renditions.

**Status:** complete. Four planned variants plus a vocal-only replacement
finished; the hard-prefix attempt was a no-op on this binary and is recorded as
such.

## Source

`gs://akbar-december-2024-backup/arabmaqamrock/runs/20261020_baghdad_moon_final_fix_v2/`

| | |
|---|---|
| source WAV | `output/FINAL_e1_ar_s03_s13_41.wav` |
| source SHA-256 | `9b8fdb2125b72d2bddd091ff5e5248b84ab9f715d9121452e3020e185c86311c` |
| duration | 215.878667 s, 48 kHz stereo PCM_16 |
| original cap | **6750** tokens (`q=0.95`, 507 letters) |
| original truncated | `false` |

The original cap comes from the original batch sidecar:

`runs/20261018-162827_batch_12_variants_backing_vocals/02-استيداع-قمر-بغداد-ولوعة-الوداع-B_1712905618.json`

## Transcription

Both scores were produced from the same source WAV on CPU.

| Score | File | Size | Time | SHA-256 |
|---|---|---:|---:|---|
| melody-only (`--melody-only`) | `out/20261020_baghdad_moon_final_fix_v2/transcripts/FINAL_e1_ar_s03_s13_41/score.abc` | 2,603 B | 417.1 s | `9f57b30c528bf25480325715cfd7864cd1b97708c601b25889f0eb8dc294010e` |
| full/chords (`--full`) | `out/20261020_baghdad_moon_final_fix_v2/transcripts_full/FINAL_e1_ar_s03_s13_41/score.abc` | 3,327 B | 381.9 s | `8f4f5c7d43bbe81f043036b6e4661c8b1036bc8924a224ecb868e57d4944c18e` |

Both are 223 lines, key `Gm`, and contain Vocal + Ins voices. The full score adds
chord symbols such as `"Gm"`.

## First guide render (v1)

| | |
|---|---|
| run | `out/20261024_baghdad_moon_abc_guide/` |
| ABC | melody-only, Vocal + Ins |
| `cot` | `melody` |
| seed | `20261024` |
| cap | **5397** — length-matched (`215.879 × 25`), **not** the original cap |
| output | `BaghdadMoonABCGuide_20261024.wav` |
| SHA-256 | `79073688567a645db4a9cf635551bdaafd4448758e17604feb26f9433b60a552` |
| duration | 215.878667 s |
| wall | 7:02 |
| semantic tokens | 5397 |
| semantic truncated | **true** — the length-matched cap was hit |

The tail fades rather than cutting abruptly, but this is not a like-for-like cap
comparison. The original 6750-token run ended naturally with
`truncated=false`.

## Variant matrix

All variants use:

- the same source WAV, style, lyrics, and v3 AR/NAR LoRA;
- seed `20261024`;
- the **original cap 6750**;
- `out/20261024_baghdad_moon_abc_variants/<variant>/`.

| Variant | ABC | `cot` | Extra | Status |
|---|---|---|---|---|
| `combined_cap6750` | melody-only, Vocal + Ins | `melody` | — | done |
| `skeleton_cap6750` | vocal-only, thinned to ~one note per bar | `melody` | — | done |
| `full_chords_cap6750` | full/chords, Vocal + Ins | `full` | — | done |
| `prefix3933_cap6750` | melody-only, Vocal + Ins | `melody` | `semantic_prefix_file` (3933 frames ≈ 157 s) | **no-op** |
| `temp07_cap6750` | melody-only, Vocal + Ins | `melody` | `semantic_temperature=0.7` | done |
| `vocal_only_cap6750` | vocal-only, Vocal voice | `melody` | — | done (replacement) |

Notes:

- The skeleton was derived from the vocal-only score by keeping roughly the
  first pitched note of each bar and replacing the rest with rests. It is a
  deliberately loose guide.
- The prefix variant was **not applied**: the current `bin/audiocpp_cli` has no
  `semantic_prefix` / `semantic_prefix_file` support. Its output is byte-identical
  to `combined_cap6750` (same SHA-256), so it does not test a hard lock.
- The temperature variant changes sampling only, not the ABC.
- `vocal_only_cap6750` replaces the failed prefix test as the fifth meaningful
  variant.

## Results

Final results:

| Variant | WAV | SHA-256 | Duration | Wall | Truncated |
|---|---|---|---|---|---|
| `combined_cap6750` | `BaghdadMoonGuide_combined_20261024.wav` | `9fa0d224c6b59dd9b53c3e740ae8a2675f8e1cb640cdc9b48901baacc5643bbc` | 215.679 s | 6:52 | false (5392 tokens) |
| `skeleton_cap6750` | `BaghdadMoonGuide_skeleton_20261024.wav` | `cde8686859ec1b6b24899cf0e0d4d7ef8b5820db260e7d794b2c08bcf6366291` | 227.239 s | 6:58 | false (5681 tokens) |
| `full_chords_cap6750` | `BaghdadMoonGuide_full_20261024.wav` | `060767d07f7f0c0b2c1afdfbdae794b8d510ccf3e7c1c6295b2d07d4647f89ab` | 215.879 s | 7:11 | false (5397 tokens) |
| `prefix3933_cap6750` | `BaghdadMoonGuide_prefix3933_20261024.wav` | `9fa0d224c6b59dd9b53c3e740ae8a2675f8e1cb640cdc9b48901baacc5643bbc` | 215.679 s | 6:51 | false; **no-op** |
| `temp07_cap6750` | `BaghdadMoonGuide_temp07_20261024.wav` | `3b0bc580bdcb038bd1f03fd7f44e6ebefe502057f6985e6d5a1f37f5ef72be3c` | 214.559 s | 6:35 | false (5364 tokens) |
| `vocal_only_cap6750` | `BaghdadMoonGuide_vocal_20261024.wav` | `51cb89e1a2b79c03b9993b752ae50b0cbca10cd0cde15bcfad2224d5ba73056e` | 169.319 s | 5:37 | false (4233 tokens) |

### What the results show

- `combined` at 6750 no longer truncates: 5392 tokens, 215.679 s.
- `skeleton` is looser and runs longer: 5681 tokens, 227.239 s.
- `full/chords` stays closest to the source length: 5397 tokens, 215.879 s.
- `temp07` is shorter: 5364 tokens, 214.559 s.
- `prefix3933` is invalid as a hard-lock test: the binary ignored
  `semantic_prefix_file`. The current binary has **no `semantic_prefix` strings**;
  the output is bit-identical to `combined`.
- `vocal_only` is the most aggressive change: it drops the Ins voice and ends at
  169.319 s (4233 tokens), much shorter than the source. Vocal-only is not a
  length-preserving control.

## Where it lives

Local:

```
out/20261020_baghdad_moon_final_fix_v2/
  transcripts/FINAL_e1_ar_s03_s13_41/score.abc          melody-only
  transcripts_full/FINAL_e1_ar_s03_s13_41/score.abc     full/chords
out/20261024_baghdad_moon_abc_guide/                   v1 (cap 5397)
out/20261024_baghdad_moon_abc_variants/                five meaningful runs, cap 6750
```

GCS:

```
gs://akbar-december-2024-backup/arabmaqamrock/runs/20261020_baghdad_moon_final_fix_v2/
  transcripts/FINAL_e1_ar_s03_s13_41/score.abc
  transcripts_full/FINAL_e1_ar_s03_s13_41/score.abc
gs://akbar-december-2024-backup/arabmaqamrock/runs/20261024_baghdad_moon_abc_guide/
gs://akbar-december-2024-backup/arabmaqamrock/runs/20261024_baghdad_moon_abc_variants/
```

The backup sidecar mirrors `out/`; `python3 plumbing/backup_to_gcp.py --once`
forces a pass.

## Reproduce

One variant:

```bash
./out/20261024_baghdad_moon_abc_variants/combined_cap6750/run_variant.sh
```

All five:

```bash
./out/20261024_baghdad_moon_abc_variants/run_all_variants.sh
```

Each run is one GPU render (~7 min on a T4). Runs are sequential.

## Caveats

- ABC guidance is symbolic, not audio-to-audio. Outputs are new renders, not
  edits of the source.
- The v3 adapter was trained `cot=off`; every ABC run is off-distribution.
- The style says “Maqam Hijaz” while SheetSage2 detected `K:Gm`; that mismatch is
  a known confound for ABC adherence.
- `guidance_scale` is not an ABC-strength control; it amplifies style/lyrics.
- With an external ABC, the `abc_*` sampling options are ignored.
- The hard semantic-prefix control is blocked by the current binary. Check with
  `strings bin/audiocpp_cli | grep semantic_prefix`; it returns nothing. Testing
  it needs a newer audio.cpp build that advertises `semantic_prefix` /
  `semantic_prefix_file`.
