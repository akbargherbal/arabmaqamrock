# Five Stars — ABC composition corpus

Reference material for **ABC-first composition**: given new lyrics and a maqam,
write an ABC score in the manner of these tracks.

The 177 tracks here are the curated top of a 438-track pool (a mix of 4★ and 5★
listening ratings). The selection is already made — nothing downstream filters
on quality. What remains is **technical** QC: does the transcription parse, does
it agree with its maqam label, is it clean enough to imitate.

This directory holds the provenance layer only. No audio is redistributed from
here; `audio_path` points at the packaged layout used on Colab.

The end-to-end runbook lives in
[`docs/plans/five-stars-abc-corpus.md`](../../docs/plans/five-stars-abc-corpus.md).

## Where the data lives

```
gs://akbar-december-2024-backup/arabmaqamrock/datasets/five_stars/v1/
  audio/{Ajam,Hijaz,Kurd,Nahawand}.tar   deterministic, ~250 MB each
  audio/SHA256SUMS                       verify with `sha256sum -c`
  corpus/{manifest,lyrics,audit}.json(l)
```

Extract inside the dataset root and the paths in `manifest.jsonl` resolve as-is.
The tars are composite GCS objects, so `md5_hash` is null — verify with SHA-256.

## Files

| File | Contents |
|---|---|
| `build_manifest.py` | Regenerates everything below from the upstream pickle + audio tree |
| `stage_audio.sh` | Builds the packaged audio tree, per-maqam tars, and `SHA256SUMS` |
| `manifest.jsonl` | 177 rows, one per track — the join key for all downstream work |
| `lyrics.jsonl` | Per-track parsed lyrics, sections, and the original style prompt |
| `audit.json` | Corpus-level facts (durations, loudness, groups, style variance) |

Rebuild:

```bash
python3 datasets/five_stars/build_manifest.py --src ../Five_Stars_ArabMaqamRock
```

## `manifest.jsonl`

One JSON object per line. **`track_id` is the upstream `clip_id` and is the only
stable identifier** — filenames collide (157 unique filenames for 177 tracks),
so never join on `assigned_filename`.

| Field | Meaning |
|---|---|
| `track_id` | Upstream clip UUID; primary key |
| `maqam` | `Ajam` \| `Hijaz` \| `Kurd` \| `Nahawand` — the *prompted* maqam, not a measured one |
| `audio_path` | Packaged path, `audio/<maqam>/<track_id>.mp3` |
| `audio_sha256` | Content hash; guards against stale transcripts |
| `duration_s` `bytes` `bit_rate` `sample_rate` `channels` | Probed from the file |
| `mean_volume_db` `max_volume_db` | `volumedetect`; corpus peak is −0.1 dBFS, nothing clips |
| `original_title` | Upstream poem-section title, e.g. `07-يوم-بدر-الثاني-...` |
| `assigned_filename` | Upstream filename (ambiguous — informational only) |
| `poem_slug` | `original_title` minus the section number and any variant prefix |
| `section_no` | Leading `01`–`10`, or `null` |
| `take` | `SONG_A` … `SONG_H`, or `null` |
| `variant_prefix` | `RETAKE` / `CREMASTER` prefix, or `null` |
| `is_retake` | Convenience flag over the above two |
| `lyric_group_id` | Hash of the **consonantal** text — identical poem, any vocalisation |
| `lyric_group_copies` | Tracks sharing this group (1–4) |
| `group_diacritizations` | Distinct diacritised forms inside the group (1–3) |
| `n_lines` `n_sections` `n_chars` `has_harakat` | Lyrics shape |
| `prior_rating` | Earlier partial listening pass; **not** a filter |
| `created_at` `upstream_status` | Provenance passthrough |

## `lyrics.jsonl`

| Field | Meaning |
|---|---|
| `track_id` `maqam` `lyric_group_id` | Join keys |
| `sections` | `[{type, direction, lines[]}]` — `type` is `Intro`/`Verse 1`/`Chorus`/`Outro`/…; `direction` is the English performance note, kept but *not* sung |
| `plain` | Sung Arabic only, NFC-normalised, trailing `...` removed |
| `style_prompt` | The upstream generation prompt verbatim (genre/vocals/production/instrumentation/mood) |
| `exclude_styles` | Negative prompt, verbatim |

## Invariants

- 177 rows, `track_id` unique, every `audio_sha256` matches a file on disk.
- All text NFC-normalised. Six lyric groups contain 2–3 **different
  diacritisations of the same consonants** (e.g. `نَجُذَّ` / `نَجُذُّ`); that is a
  grammatical reading difference, not corruption, and the group id is defined on
  the consonants so takes still group correctly.
- `style_prompt` is **constant** by design: 1 unique `genre`, `production`, and
  `instrumentation` string, and 110 BPM on all 177. Only `mood` (92 values) and
  the maqam name vary. Do not expect the corpus to teach arrangement variety.
- `maqam` is the *requested* maqam. The repo's own hand analysis of a related
  track found a "Hijaz" score that was really G natural minor, so every
  transcribed track needs a pitch-profile check before it is used as an exemplar.

## Next layers (not built yet)

1. `transcripts/<track_id>/` — SheetSage2 melody-only output (`--melody-only`,
   Vocal + Ins voices), keyed by `track_id`.
2. `derived/<track_id>.json` — lint result, pitch-class profile, estimated
   tonic, maqam agreement verdict.
3. `exemplars/` — polished demonstrations: ABC + lyrics + maqam card, sized to a
   token budget.
4. `w:` lines — reserved slot for forced-alignment, added after the ABC run.

## Licensing

Audio is Suno-rendered and is **not** redistributed by this repository.
SheetSage2 and MERT-v2-FullSong are CC-BY-NC-4.0. Any derived artifact inherits
those constraints.
