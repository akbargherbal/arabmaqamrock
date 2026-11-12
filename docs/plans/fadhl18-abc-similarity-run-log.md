# Fadl Shaker Instrumental 18 — ABC similarity run log

Branch: `feat/fadhl18-abc-shortlist`
Started: 2026-11-12
Dataset (read-only): `gs://akbar-december-2024-backup/DATASET/fadhl_shaker_instrumental_18/`
Source run: `20261110-050958_fadhl_shaker_instrumental_18`
Plan: `docs/plans/fadhl18-abc-similarity-shortlist.md`

## Cohort

- **24 tracks**, each with:
  - `abc/<stem>.abc` — reference ABC used as the generation conditioner (input side)
  - `abc_transcription/<stem>.abc` — SheetSage2 `--full` transcript (output side)
  - `captions/<stem>.json`, `tracks.jsonl`, `manifest.json`
- 24/24 reference and 24/24 transcription SHA-256s match `tracks.jsonl`;
  24/24 parse as valid ABC; no input file equals its output.
- 23 tracks carry `vocal_sparse` (expected for an instrumental run); ignored
  for similarity.

## Provenance verification

The output side was independently reproduced, not assumed:

- Shortest / median / longest tracks re-transcribed from their MP3s with a
  fresh SheetSage2 run (`m-a-p/SheetSage2` revision `b83c3d79…`, `--full`,
  CUDA, bf16): all three published ABCs were **byte-identical** to the fresh
  output (`fustan_alhelwa` 2,873 B, `al_hal` 4,507 B,
  `hazak_ya_albi` 6,110 B).
- Rename control (`renamed_control_0001.mp3`): still byte-identical → not a
  filename lookup.
- Pitch-shift control (+2 semitones): output changed (3,103 B; key `Cm` →
  `G#m`) → the model is audio-dependent.
- Input-vs-output note-token Jaccard: 0.23–0.86, median 0.64 → the outputs
  are not score copies. Shared `X:/T:/M:/L:/Q:`, `V:` and `% section`
  scaffold is the model's canonical format.
- Full-cohort re-transcription of all 24 tracks: **24/24 byte-identical**,
  0 failures, 671 s wall (see `similarity/reproducibility.json`).

## Analysis

`python3 analysis/run_yt500_similarity.py run` on the 24 staged pairs:

- cohort **24 / 24**; missing 0, parse errors 0, hash collisions 0
- median composite **0.931** (IQR 0.028)
- median deep composite **0.895**
- matched − chance: mean d **0.305**, dz **4.862**, sign-flip p **9.999e-05**,
  fraction d>0 **1.000**
- retrieval rank-1 **100%**
- deep-audit Spearman **ρ 0.894** (n=24; all tracks audited)
- decision codes: KEEP **18**, REVIEW **6**, REGENERATE **0**

## Shortlist

Absolute floors are primary at N=24:

- `qualify`: not REGENERATE, composite ≥ 0.85, deep ≥ 0.65
- `borderline`: not REGENERATE, composite ≥ 0.75
- `reject`: REGENERATE, composite < 0.75, or deep < 0.65

Result: **22 qualify, 2 borderline, 0 reject** (24 accounted).

- Qualify: 22 tracks (18 KEEP + 4 REVIEW).
- Borderline: `lelheen_3ayesh_562555061` (0.832 / deep 0.781),
  `ya_tkoon_habibi_2757273608` (0.825 / deep 0.764).

Artifacts:

- `work/fadhl18/shortlist_keep_review.json`
- `docs/plans/fadhl18-abc-shortlist-keep-review.json`
- `work/fadhl18/similarity/reproducibility.json` (24/24 comparison)
- analysis bundle:
  `gs://akbar-december-2024-backup/ANALYSIS/fadhl_shaker_instrumental_18_abc/`

## Status

- [x] dataset inspected and hashes verified
- [x] provenance spot-check (3 tracks + rename + pitch-shift controls)
- [x] full 24/24 re-transcription comparison (all byte-identical)
- [x] staging, inventory, pair build, analysis
- [x] shortlist JSON (22 qualify / 2 borderline / 0 reject)
- [x] publish analysis bundle; SHA256SUMS 39/39 OK
- [x] commit and push (code commit `d9c437c`; shortlist + this log follow)

## Final

- **22 / 24 qualify** (18 KEEP + 4 REVIEW); **2 borderline**, **0 reject**.
- Qualifying composite range **0.884–0.983**, deep **0.843–0.947**.
- Borderline: `lelheen_3ayesh_562555061` (0.832 / 0.781),
  `ya_tkoon_habibi_2757273608` (0.825 / 0.764).
- Analysis bundle `_SUCCESS` commit `d9c437c`, 40 objects, SHA256SUMS 39/39 OK.
- Shortlist: `docs/plans/fadhl18-abc-shortlist-keep-review.json` and
  `ANALYSIS/fadhl_shaker_instrumental_18_abc/similarity/shortlist_keep_review.json`.
- Provenance: all 24 published transcriptions reproduced byte-for-byte from
  audio (`similarity/reproducibility.json`); no re-transcription was needed for
  the comparison, but the full check was run anyway.
