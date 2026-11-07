# حبيتك — melody-only vs full transcription (round 05)

**Goal:** on one song, compare three score layouts under the same instrumental AR
LoRA, to see whether a **melody-only** score gives a denser or less "stem-like"
arrangement than the full transcription, while keeping the vocal melody intact.

- Song: **حبيتك** (`habeetak`) — 269.703 s, Gm, 101 BPM, 4/4 (one 3/4 bar).
- Base model: YuE2 3B GGUF (`yue2-3b-bf16.gguf`) in `audiocpp_cli`.
- AR adapter: `Mothersuperior/YuE2-instrumental-cot-full-loras`
  (`ar_lora_inst_v3abc.bf16.safetensors`, rank 64, 392 tensors, 28 layers).
- NAR adapter: `arabmaqamrock-v3-nar.safetensors` loaded at **scale 0**.
- Seed `20261106`, `cap=6993`, `repeat=1`, `trigger=false`, `[instrumental]`.

## Score provenance (important)

The canonical `scores/fadhl_shaker/habeetak.abc` was produced with
`transcribe.py --full`: it has **both staves and chord symbols**. No
re-transcription was done for this round; doing so would change the note set and
break comparability with rounds 01–04.

- `--melody-only` in this repo is **not** "lead vocal only": it keeps the Vocal
  and Ins staves and only omits chord symbols.
- Therefore **M2 is the effective `--melody-only` + surgery case** (same notes as
  the full score, chords removed).
- **M1 is a further reduction**: it keeps only the 438-note Vocal melody and
  discards the original 459-note Ins line. No transcribe mode produces this.

The uploaded audio (`/content/fadhl_shaker_selected/حبيتك.mp3`, 266.256 s) is
3.4 s shorter than the canonical score; the repository score was kept for
consistency.

## The three layouts

| | Full | No-chords surgery | Melody-only |
|---|---|---|---|
| Vocal staff | empty (moved to Ins) | empty | empty |
| Ins staff | original Ins + Vocal, overlaps resolved by Vocal priority | same 897 notes as full | **Vocal melody only, 438 notes** |
| Chords | kept (182 source events; 185 parsed after bar-start restatement) | **removed** | **removed** |
| `cot` | `full` | `melody` | `melody` |
| Score file | `scores/fadhl_shaker_instrumental/habeetak.abc` | `scores/fadhl_shaker_nocords_habeetak/habeetak.abc` | `scores/fadhl_shaker_melody_habeetak/habeetak.abc` |
| sha256 | `792718a7…` | `9b5d9645…` | `5846cb6c…` |

## Score verification

| Score | Vocal notes | Ins notes | Chords | Bars | Key | BPM | Duration |
|---|---|---|---|---|---|---|---|
| Source (`--full`) | 438 | 459 | 182 | 114 | Gm | 101 | 269.703 s |
| Full transcription (M3) | 0 | 897 | 185 parsed | 114 | Gm | 101 | 269.703 s |
| No-chords (M2) | 0 | 897 | 0 | 114 | Gm | 101 | 269.703 s |
| Melody-only (M1/M4) | 0 | 438 | 0 | 114 | Gm | 101 | 269.703 s |

Independent checks (via the repo's `abc_tools` parser, the same one the
generator uses):

- **Melody-only**: `Ins.notes` is exactly equal to the source `Vocal.notes` (all
  438 onsets, pitches, durations); no original Ins note leaked in; bar grid and
  key timeline equal to the source; monophonic, no overlaps; all 7 section
  markers preserved (intro, verse, chorus, interlude, verse, chorus, interlude).
- **No-chords**: `Ins.notes` is exactly equal to the full score's Ins line
  (897 notes); only the 185 parsed chord events were removed.
- `check_abc.py` could not run in this checkout because its `measure` module
  (`datasets/five_stars/measure`) is absent; `abc_tools` round-trip validation
  was used instead.

Melody provenance is recorded in
`scores/fadhl_shaker_melody_habeetak/report.json`:
"derived from a `--full` transcription (Vocal staff only; the original Ins line
and chord symbols are discarded); not a melody-only re-transcription".

## Run

```bash
python3 generate.py manifests/fadhl_shaker_instrumental_05_melody_habeetak.json \
  --label fadhl_inst_05_melody_habeetak
```

Run dir:
`out/20261107-142849_fadhl_inst_05_melody_habeetak/`

Command: `cot=melody/melody/full/melody`, AR `1/1/1/0.75`, NAR `0`, cap 6993.

## Results

| # | Name | Score | cot | AR | WAV | Duration | exit | wall | truncated |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `m1_melody_lora100` | melody | melody | 1.0 | `m1_melody_lora100_20261106.wav` | 279.719 s | 0 | 534.0 s | **true** (`duration_heuristic`; `yue2.semantic.truncated 1`) |
| 2 | `m2_nocords_lora100` | no-chords | melody | 1.0 | `m2_nocords_lora100_20261106.wav` | 240.039 s | 0 | 486.6 s | false |
| 3 | `m3_full_lora100` | full | full | 1.0 | `m3_full_lora100_20261106.wav` | 266.279 s | 0 | 558.9 s | false |
| 4 | `m4_melody_lora075` | melody | melody | 0.75 | `m4_melody_lora075_20261106.wav` | 223.519 s | 0 | 446.4 s | false |

All WAVs are in the run dir above. Per-track sidecars (the `result.json`
equivalent) are `<name>_20261106.json`; logs are `<name>_20261106.log`, GPU
samples `<name>_20261106_gpu.csv`, timing `<name>_20261106_time.txt`.

- Batch: **4 ok, 0 failed, 0 skipped**, total wall 33:46.
- **M1 hit the semantic cap**: `yue2.semantic.truncated 1`; 6993 frames =
  279.719 s, above the 269.703 s score. This is a real cap hit, not a decode
  failure. Re-run with a larger cap if the ending matters.
- M2 ended early at 240.0 s and M4 at 223.5 s (model stop before the score
  length, no truncation flag). M3 is 266.3 s.
- No errors in any log. M3 reproduces the round-04 `v2_surgery_lora100`
  configuration (full score, AR 1.0, same seed/cap) and serves as the baseline.

## Log excerpts

```
[1/4] m1_melody_lora100 ... cot=melody ... wall=8:54 ok dur=279.7s
[2/4] m2_nocords_lora100 ... cot=melody ... wall=8:07 ok dur=240.0s
[3/4] m3_full_lora100 ... cot=full ... wall=9:19 ok dur=266.3s
[4/4] m4_melody_lora075 ... cot=melody ... wall=7:26 ok dur=223.5s
ok: 4  failed: 0  skipped: 0  total wall: 33:46
possibly truncated: m1_melody_lora100 (duration_heuristic)
```

## Suggested listening order

1. **M3 `m3_full_lora100`** — baseline (full transcription + chords, AR 1.0).
2. **M2 `m2_nocords_lora100`** — same notes as M3, chords removed (`melody`).
3. **M1 `m1_melody_lora100`** — the actual melody-only reduction (single line).
4. **M4 `m4_melody_lora075`** — melody-only at AR 0.75.

Questions to judge by ear: Is the vocal melody still recognizable? Is the
arrangement denser or sparser than M3? Does it sound more like a separated stem?
Are there vocals (M1/M2 should have none because the melody sits on Ins)? Does
M1's 279.7 s ending run past the song? Audio-level vocal detection was not run
here (Demucs is out of scope), so the vocal check is by listening.

## Constraints observed

- No ACE-Step, no Demucs.
- No base-model takes without the instrumental LoRA.
- `cot="full"` only on the chord-bearing M3 score; M1/M2/M4 use `melody`.
- The melody was never placed back on the Vocal staff.
- Round-04 manifests/scores untouched.
- NAR `lora_nar_scale: 0` in every take.
- No settings were silently reduced after a failure (there were no failures).
