# Baghdad Moon — token-level repair of two mispronounced words

Target: `02-استيداع-قمر-بغداد-ولوعة-الوداع-B_1712905618` (take 0, idx 5).
Original: `gs://akbar-december-2024-backup/arabmaqamrock/runs/20261018-162827_batch_12_variants_backing_vocals/`.
All experiments are stored under `happy_accident/runs/` in the working tree and mirrored to GCS.

## Reference facts

| item | value |
|---|---|
| original WAV sha256 | `dbc00722534d5ee763ae54a048cd704eaa4c927e37834cd54542eaf379e0de42` |
| duration / frames | 215.8787 s / 5397 semantic frames (25 fps) |
| seed | 1712905618 |
| cap | 6750 |
| lyrics sha256 | `7bd3b6e1da3aa4e674d728cd24af4a3ffe6e89468b6b5714b543c6310513c46d` |
| style sha256 | `248af8e769501f2bb565129d781ea33d5672039d908286729d6f319066430b8e` |
| model / VAE sha256 | `4cf3fdf...` / `d4f4a05...` (match manifest) |
| LoRA AR / NAR sha256 | `3531bb9...` / `a7eabca...` (match manifest) |
| binary | `bin/audiocpp_cli`, sha256 `7ad69d1...`, sm75-t4 prebuilt, audio.cpp commit `eb8e21bd` (no semantic-prefix support) |
| GPU | Tesla T4, compute capability 7.5 |

## Error locations (by ear + CTC forced alignment + ASR of the demucs vocal stem)

| error | text | sung | approx. time | frame range |
|---|---|---|---|---|
| 1 | `عَلَيْهِ` | `عَلِيمْ` | 157.3–158.55 s | ~[3933, 3964) |
| 2 | `فَإِنَّ` | `بِأَنَّ` | 202.26–204.54 s | ~[5056, 5114) |

The same two words are sung correctly elsewhere in the same take:
- `عَلَيْهِ` in the Outro at 201.0–202.24 s (frames ~[5025, 5056)), same pitch contour (439→394→439→465 Hz).
- `فَإِنَّ` at the end of Verse 2 at 158.5–159.5 s (frames ~[3962, 3988)).

## Experiments

| # | what changed | path | result at 02:37 | result at 03:24 | similarity to baseline | wall time | notes |
|---|---|---|---|---|---|---|---|
| 0 | baseline semantic (`stop_after=semantic`) | `runs/baseline_semantic/` | — | — | token stream identical to original (5397 frames, sha256 `1b1aa3e...`) | 332 s | fingerprints 1079/12, 5397, not truncated |
| 1 | attempt with original binary + `semantic_prefix_file` | `runs/token_surgery/v1/` | — | — | — | aborted | original binary silently ignored the option and re-ran the AR; prefix support landed after the binary was built |
| 2 | rebuild audio.cpp `eb8e21bd` + cherry-pick `d32a6a01` (semantic prefix) | `/tmp/opencode/audio.cpp` | — | — | — | build | needed for token injection; baseline re-check pending |
| 3 | error-1 final-note splice (8 frames from Outro) | `runs/token_surgery/v2/` | pending | unchanged | pending | pending | |
| 4 | error-1 whole-word splice (31 frames from Outro) | `runs/token_surgery/v2/` | pending | unchanged | pending | pending | |
| 5 | error-1 + error-2 onset splice (13 frames from Verse 2) | `runs/token_surgery/v2/` | pending | pending | pending | pending | |
| 6 | error-1 + error-2 whole-word splice (26 frames from Verse 2) | `runs/token_surgery/v2/` | pending | pending | pending | pending | |
| 7 | tail resample from `tokens[:5056]`, seed sweep | `runs/tail/` | pending | pending | pending | pending | last ~13.6 s redrawn; likely the cleanest error-2 fix |

## Evaluation

For every rendered candidate:
- demucs `htdemucs` vocal stem, then Arabic CTC (`jonatasgrosman/wav2vec2-large-xlsr-53-arabic`) on the two windows; the original reads `…عَلْعَيِيمِ` (ends in م) and `…بِأَنَّ…` (starts with ب).
- waveform correlation with the original (overall and 5 s windows), and mel-spectrogram mean absolute difference, to quantify collateral change.
- the user decides by ear; candidates are ranked and exported as `runs/final/*.wav`.

