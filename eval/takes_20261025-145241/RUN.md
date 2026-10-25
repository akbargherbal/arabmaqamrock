# Baghdad Moon A/B takes — 2026-10-25

- **Run dir:** `out/20261025-145241_baghdad_moon_spec`
- **Date:** 2026-10-25
- **Transcriber:** SheetSage2 `m-a-p/SheetSage2` @ `b83c3d79a6d98bcffaf8f9ed112c90aa887887bc`, melody-only, CUDA (Tesla T4)
- **Source score:** `scores/baghdad_moon_spec_v1.abc` (alias `spec_v1`, used by the `cot=melody` arms)

## Takes

| Take | Seed | CoT | Score file | WAV duration | Truncation flag |
|---|---|---:|---|---:|---|
| `baghdad_moon_claude_score_01_101` | 101 | melody | `scores/baghdad_moon_spec_v1.abc` | 268.76 s | no |
| `baghdad_moon_vanilla_01_101` | 101 | off | — | 217.32 s | no |
| `baghdad_moon_claude_score_02_313` | 313 | melody | `scores/baghdad_moon_spec_v1.abc` | 237.32 s | no |
| `baghdad_moon_vanilla_02_313` | 313 | off | — | 242.88 s | no |
| `baghdad_moon_claude_score_03_577` | 577 | melody | `scores/baghdad_moon_spec_v1.abc` | 213.12 s | no |
| `baghdad_moon_vanilla_03_577` | 577 | off | — | 237.84 s | no |

`batch_summary.txt` records `exit 0` and `trunc=no` for all six takes.
The score is 270.55 s long; every take is shorter than that target (213–269 s),
but none was flagged as truncated by the generation run. Durations are reported
as-is; the four takes in the 213–243 s range are natural end-of-sequence
completions, not duration-cap truncations.

## Transcripts

| File | Bytes | Lines | Bars (`\|`) |
|---|---:|---:|---:|
| `baghdad_moon_claude_score_01_101.abc` | 2961 | 161 | 196 |
| `baghdad_moon_vanilla_01_101.abc` | 2457 | 169 | 174 |
| `baghdad_moon_claude_score_02_313.abc` | 2387 | 143 | 166 |
| `baghdad_moon_vanilla_02_313.abc` | 2513 | 135 | 170 |
| `baghdad_moon_claude_score_03_577.abc` | 1851 | 122 | 132 |
| `baghdad_moon_vanilla_03_577.abc` | 1711 | 97 | 96 |

Per-track GPU inference time (seconds): 52.6, 43.3, 28.9, 32.9, 42.7, 33.3.
`./transcribe.sh <run> --verify` reported 6/6 OK.

`GENERATION_SUMMARY.txt` is a verbatim copy of the run's `batch_summary.txt`.
