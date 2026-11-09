# Plan — SheetSage2 transcription of `yt_top_500_music_playlist`

**Status:** ready for the L4 pilot; inventory measured 2026-11-09, batch layer
implemented and unit-tested, no transcription run yet
**Date:** 2026-11-09
**Tool:** `arabmaqamrock/transcribe.py` (SheetSage2, pinned revision)
**Source:** `gs://akbar-december-2024-backup/yt_top_500_music_playlist`
**Batch driver:** `music_captioning/scripts/abc_batch.py`, now with
`--device`, `--per-track-timeout`, `--on-collision`, `--archive-every-track`,
`--restore-from-gcs`, `--manifest-sha256`, `--gcs-index` and `--no-commit`.
The new `music_captioning/scripts/yt500_manifest.py` freezes the 495-row JSONL
manifest, 25 shards, the 5 duplicate groups and the 10-track pilot set.
**Target:** one `--full` ABC score per unique audio object (495 measured), with
MIDI/label/event side artifacts, backed up to GCS and resumable from any VM.

**Repos and paths.** `transcribe.py`, `transcribe.sh` and `plumbing/` live in
`/content/arabmaqamrock`; `abc_batch.py`, `abcscore.py` and `abc_pack.py` live in
`/content/music_captioning`; `../youtube_playlist/manifest.json` is the local
playlist metadata used only as a cross-check. The batch driver is pointed at the
tool repo with `--amr-dir /content/arabmaqamrock`.

**Contents.** 0 Bottom line · 1 Scope · 2 What exists · 3 Freeze · 4 Storage /
compute · 5 Execution · 6 Guardrails · 7 Resume · 8 QC · 9 Done · 10 Timeline ·
11 Risks · 12 Decisions · Appendices.

---

## 0. Bottom line

Treat this as a **corpus migration**, not a loop over 500 files.

1. **Freeze the corpus first.** The bucket's `state/latest/manifest.json` is
   already a complete, measured manifest: **495 tracks, all `done`**, 495 unique
   video IDs and 495 unique SHA-256s. Copy it, hash it, and never re-list the
   source into the transcription manifest. Nothing is transcribed from a live
   `gsutil ls`.
2. **Deduplicate in the manifest, but do not drop audio.** There are **zero**
   byte-identical and zero same-video duplicates. There are **5 same-artist +
   same-title groups (10 tracks)** with different audio; they look like
   different edits/performances (one is a live 2020 performance). Transcribe all
   **495** by default and mark `duplicate_of`; the extra 5 jobs cost ~2 minutes
   of GPU and preserve evidence. Only byte-identical/same-video rows are
   skipped.
3. **Use the measured RTF, not a guess.** The prior 236-track Elissa/Fadl run
   measured **4.57–6.87× realtime** (`--full`), median **5.42×**. The bucket has
   **38.27 h** of actual audio, so the central GPU estimate is **~7.1 h**, or
   **~9–10 h** with downloads, QC, retries and uploads.
4. **Shard for loss, not for speed.** 25 shards of ~20 tracks (last shard 15).
   Each shard is a checkpoint, a commit, and a remote archive.
5. **Resume is already per-track; add per-shard and per-run layers.** The
   existing `meta.json` source/ABC hash guard is the atomic commit point.
   Never bulk-`--force`, never delete a track directory to retry.
6. **A shard is not done until its archive is in GCS and its hash is verified.**
   A failed upload is a hard stop, not a warning.
7. **Pilot 10 tracks and gate on RTF, VRAM and ABC QC before spending a
   session.** If the gate fails, stop.
8. **The source is read-only.** All writes go to a new versioned prefix; the
   bucket's original audio and manifests are never modified.

### Measured inventory (2026-11-09)

| Item | Value |
|---|---:|
| Audio objects | **495** (`.m4a`, AAC, ~129.4 kbps) |
| Metadata objects | 495 `*.info.json` |
| Unique `video_id` | 495 |
| Unique `sha256` | 495 |
| Byte-identical duplicates | **0** |
| Same artist + title groups | **5 groups / 10 tracks**, all different audio |
| Total actual duration | **38.27 h** (137,991 s expected) |
| Total bytes | **2.08 GiB** (2,228,785,610 B) |
| Duration min / median / max | 142.3 / 276.6 / 415.7 s |
| Tracks > 300 s / > 360 s / > 420 s | 163 / 31 / **0** |
| Artists / countries | 30 / 10 |
| Tiers | 348 / 134 / 13 |
| Manifest | `state/latest/manifest.json`, `sha256:b5280de9…` |
| Status | 495/495 `done` |

The bucket also carries `state/latest/report.json`, `state/snapshots/`,
`metadata/*.info.json` and four session logs. The five same-title groups are
listed in §3.4; the eight *title-only* groups across different artists are
different songs and are not duplicates.

> **Auth note.** The WSL `gcloud` still returns `invalid_grant`; the inventory
> above was read with the Windows `gcloud` token. Before the run, either
> `gcloud auth login` inside WSL or use a service account. Do not paste the
> token into a shell history or a committed file.

---

## 1. Scope and definitions

| | |
|---|---|
| **In scope** | Audio → SheetSage2 `--full` transcription: `score.abc` (Vocal + Ins + chord symbols), `transcription.mid`, `melody_vocal.mid`, `melody_instrumental.mid`, `chords.mid`, `events.json`, `*.lab`, `notation/`, `meta.json`. |
| **Out of scope** | Lyrics/ASR, lyric-to-note alignment, maqam labelling, score editing, re-rendering. The `maqam-edit` workflow is a later, human-driven pass over selected scores. |
| **Unit of work** | One **unique audio object**. All 495 measured objects are transcribed; `duplicate_of` is a metadata link. Only byte-identical/same-video rows are aliases and skipped. |
| **Success** | Every one of the 495 tracks has `meta.json.status ∈ {ok, flagged}` and a verified remote archive, or a written exception with a reason. |

If the intended meaning was "transcribe lyrics" rather than "transcribe melody
to ABC", this plan does not cover it; that is a separate ASR/alignment
pipeline.

---

## 2. What already exists (do not rebuild it)

| Component | What it gives us |
|---|---|
| `transcribe.py` | Per-track resume with `source_wav_sha256` + `abc_sha256` + `status: ok`; `--verify`; `--time-budget`; `--per-track-timeout`; `--on-collision`; `--limit`; `--smoke`; `--dry-run`. |
| `transcript_archive.py` | Deterministic `<stem>.tar.gz` from a **complete** track only; refuses incomplete/failed tracks; `--verify` compares extracted bytes. |
| `backup_to_gcp.py` | Append-only `gsutil rsync`; archives complete transcript dirs; never deletes remote. |
| `music_captioning/scripts/abc_batch.py` | Per-group download → transcribe → QC → archive → upload → verify → pack → commit; hard-stops on upload/commit failure (exit 2). |
| `music_captioning/scripts/abcscore.py` | `qc_track()`: parse, voices, vocal note count, coverage, key/chord, tempo, octave, range; `strip_chords()`. |
| `music_captioning/scripts/abc_pack.py` | Packs raw transcripts into per-group JSON + `abc_index.json`; preserves QC and derived melody-only ABC. |

The prior 236-track run is the calibration set. The GPU model was not recorded
in the index below, so the pilot re-measures it on the actual target; the RTF
is still the right planning constant until then.

| Fact | Measured |
|---|---:|
| Tracks | 236 |
| Audio | 19.19 h |
| GPU wall | 3.54 h |
| RTF | 4.57 / 5.42 / 6.87 (min / median / max) |
| Outcomes | 224 `ok`, 3 `flagged`, 9 `failed` |

That **~3.8 % failure rate** is the reason for the retry/quarantine policy in
§6.7: plan for 15–25 flagged/failed tracks in 495, not zero.

---

## 3. Phase 0 — freeze the corpus (CPU only, no GPU)

### 3.1 Authenticate and snapshot

```bash
gcloud auth login
gcloud config set project <project>
export BUCKET=gs://akbar-december-2024-backup/yt_top_500_music_playlist
export VER=2026-11-09
mkdir -p work/yt500/inventory work/yt500/$VER

# The bucket already has the authoritative manifest and report.
gcloud storage cp "$BUCKET/state/latest/manifest.json" \
  work/yt500/inventory/manifest.json
gcloud storage cp "$BUCKET/state/latest/report.json" \
  work/yt500/inventory/report.json
gcloud storage cp "$BUCKET/state/latest/meta/config.yaml" \
  work/yt500/inventory/config.yaml

# Snapshot the audio listing once; the manifest is the primary source.
gcloud storage ls -l "$BUCKET/audio/" > work/yt500/inventory/audio_listing.txt
wc -l work/yt500/inventory/audio_listing.txt
sha256sum work/yt500/inventory/manifest.json \
          work/yt500/inventory/report.json \
  | tee work/yt500/inventory/SHA256SUMS
```

Expected: `495` audio objects (`gcloud storage ls` may add a `TOTAL:` line, so
`wc -l` can read 496); `manifest.json` 698,112 B,
`sha256 b5280de9c5a7718b59d825d7d568edcad66e53ff3ff9abf492ed8bfedde143ef`;
`report.json` 198,232 B,
`sha256 998b058bc4960acd3e6a077e6d292788c66a763be69ba961e8ac513fee077137`.
Record these in the frozen manifest; a later mismatch means a new `VER`.

Build the driver's JSONL manifest once:

```bash
mkdir -p outputs/YT500
python3 scripts/yt500_manifest.py \
  --bucket "$BUCKET" \
  --report work/yt500/inventory/report.json \
  --out outputs/YT500/manifest.jsonl
sha256sum outputs/YT500/manifest.jsonl | tee outputs/YT500/manifest.sha256
```

Commit `outputs/YT500/manifest.jsonl` (small) and upload it to
`"$BUCKET/transcripts/$VER/_manifest.jsonl"`. If it is ever regenerated, the
new file is a new `VER`.

If the bucket uses a service account for unattended runs, create one with
`roles/storage.objectViewer` on the source prefix and
`roles/storage.objectAdmin` on the output prefix; keep the key outside the repo
and set `GOOGLE_APPLICATION_CREDENTIALS`. Never commit it.

### 3.2 Use the bucket manifest as the primary source

The bucket's `state/latest/manifest.json` is authoritative for **what audio
exists** and is complete enough to skip a join: each track already carries
`track_id`, `video_id`, `rank`, `artist`, `title`, `youtube_title`, `country`,
`tier`, `duration_seconds`, `status`, `file_bytes`, `sha256`, `codec`,
`bitrate`, `actual_duration`, `gcs_uri`, and `info_json_uri`.

The local `../youtube_playlist/manifest.json` is only a cross-check for
`rank`/`views`/`published`. Join by `video_id` if you use it; never join by
filename. The bucket's `rank` is the original playlist rank and is **not**
contiguous 1..495 (it ranges 1..705 because the upstream 500 rows were selected
from the top-1000 list after removing five `video_id` duplicates).

If the bucket manifest is ever missing, derive identity from the audio listing
and `ffprobe`, and **stop** if two objects cannot be distinguished. A synthetic
`track_id` must never be ambiguous.

### 3.3 The frozen manifest (`manifest.jsonl`)

Two kinds of line: a header row, then one track row per source object. This
file is immutable for the life of `VER`.

```json
{"record":"header","corpus":"yt_top_500_music_playlist","corpus_version":"2026-11-09","source_prefix":"gs://akbar-december-2024-backup/yt_top_500_music_playlist","source_manifest":"gs://.../state/latest/manifest.json","source_manifest_sha256":"b5280de9c5a7718b59d825d7d568edcad66e53ff3ff9abf492ed8bfedde143ef","created_utc":"2026-11-09T..."}
{"record":"track","artist":"YT500","album":"shard-03","source_artist":"Elissa","file":"0001_fbK2ySlxAW4.m4a","track_id":"YT500/shard-03/0001_fbK2ySlxAW4","source_rank":1,"video_id":"fbK2ySlxAW4","title":"Maktooba Leek","youtube_title":"Elissa - Maktooba Leek | ...","country":"Lebanon","tier":"Tier 1","title_normalized":"maktooba leek","source_uri":"gs://.../audio/0001_fbK2ySlxAW4.m4a","source_bytes":5128611,"source_sha256":"bf655e8bf1467f2ab4a4874d864afc992aab5d4b3c358b950f77df6f4c03e8f1","duration_s":317.068481,"bitrate_kbps":129,"format":"m4a","duplicate_group":null,"duplicate_of":null,"canonical":true,"shard":"shard-03","output_stem":"0001_fbK2ySlxAW4","status":"pending"}
```

Rules:

- `artist: "YT500"` and `album: "<shard>"` are the existing driver's group key;
  the shard is the checkpoint. `source_artist` is the real artist and must be
  preserved in the packed JSON (a small `abc_pack.py` change: prefer
  `source_artist` for the track row; keep the group key as `YT500/shard-XX`).
- Carry the bucket's 16-hex `track_id` as `source_track_id` for provenance; the
  driver's `track_id` is the synthetic `YT500/shard-XX/<stem>`.
- `file` is the unique download name and must match `output_stem` so the tool's
  stem, the QC lookup and the archive name are the same string.
- The driver should pass `--on-collision error`. With unique `output_stem`s a
  collision is a manifest bug, not something to silently suffix.
- **Sort order is stable**: `(source_rank, video_id)`, or `(artist, title,
  video_id)` if the bucket has no rank.
- **`output_stem` is ASCII and unique**: use the bucket stem
  `<rank4>_<video_id>` (e.g. `0001_fbK2ySlxAW4`). The bucket filenames are
  already safe, so `file` is the bucket basename and `output_stem` is its stem.
  This removes Arabic filename, bracket, wildcard and collision problems from
  the toolchain. The original title stays in `title`/`youtube_title`.
- **Mutable state lives elsewhere**: `status`, attempts, QC and hashes go in
  `ledger.jsonl` and `state/status.json`; `manifest.jsonl` is not rewritten.

### 3.4 Duplicate policy

Run the dedupe report **before** any GPU work:

```bash
python3 scripts/yt500_manifest.py --check outputs/YT500/manifest.jsonl
```

Measured on the bucket manifest:

| Check | Measured |
|---|---:|
| Audio objects | 495 |
| Unique `video_id` | 495 |
| Unique `sha256` | 495 |
| Byte-identical duplicate groups | **0** |
| Same-video duplicate groups | **0** |
| Same artist + title groups | **5 groups / 10 tracks** |
| Title-only groups across different artists | 8 groups / 16 tracks (different songs) |
| Tracks to transcribe | **495** |
| Total actual audio | **38.27 h** |
| Longest track | **415.7 s** |

The five same-artist + same-title groups are different audio, so they are
**not** byte duplicates. They look like different edits/performances:

| Artist | Title | Tracks (rank, video, seconds) |
|---|---|---|
| Majid Al Mohandis | Ana Blayak | 54 `Pz59wizOqLw` 415.6 / 181 `QS0v8uxzfJM` 340.1 |
| Majid Al Mohandis | Yhizak Al Shooq | 70 `WtmVYOtqz98` 256.3 (duet) / 413 `ikcfOn9VzYo` 361.5 (live 2020) |
| Majid Al Mohandis | Ensaa | 220 `nzbd8Zra2cY` 322.8 / 637 `t58Atvs7e1k` 276.2 |
| Amr Diab | Lealy Nahary | 261 `byK0dlhokOA` 271.8 / 299 `xF5MexEUoOQ` 246.1 |
| Hussain Al Jassmi | Qoul Regaat Leah | 339 `PiPu_1FSrhQ` 229.1 / 613 `yQMn7cOmnYs` 225.4 |

The eight title-only groups are different artists/songs (e.g. *Hala Hala* by
Waleed Al Shami vs Abdul Majeed Abdullah). They are not duplicates.

Policy:

1. **`source_sha256`** — byte-identical: canonical + alias, zero extra GPU.
   Measured here: **0 groups**.
2. **`video_id`** — same video twice: canonical + alias. Measured: **0 groups**
   (the upstream downloader already removed 5 such rows from 500).
3. **Same artist + same title, different audio** — **transcribe all by
   default**, and record `duplicate_group` + `duplicate_of` for downstream
   dedupe. Five extra jobs cost ~2 minutes of GPU; one pair is a live
   performance, so skipping it would silently lose a different arrangement.
4. **Title-only across different artists** — not a duplicate; no action.

Rules:

- Never delete a row. All **495** source objects get an ABC in this plan.
- `duplicate_of` is a metadata link, not a skip instruction. A downstream
  dataset builder may collapse groups; the transcription corpus does not.
- If a future run does want to skip near-duplicates, use
  `--skip-near-duplicates` and record the skipped rows as `aliased`; it is not
  the default.
- Produce `outputs/YT500/duplicates.json` with every group and a one-line
  reason. The five groups above are already reviewed; no hash groups exist.

### 3.5 Acceptance gate before spending GPU time

All must pass, or stop:

- [ ] Every audio object appears exactly once in the manifest.
- [ ] Every row has `source_uri`, `source_bytes`, `duration_s`, `video_id`, and
      a unique `output_stem`.
- [ ] `n_objects == n_transcribed == 495`; `n_alias == 0`;
      `n_duplicate_groups == 5` with `duplicate_of` links, not skips.
- [ ] `total_audio_h` is within 1 % of **38.27 h**; `sum(file_bytes)` is within
      1 % of **2,228,785,610 B**; `max_duration_s ≤ 420`.
- [ ] `source_uri` resolves for a random sample of 20 rows.
- [ ] The bucket manifest's `sha256` is recorded
      (`b5280de9…`); if it changes later, that is a new `VER`, not an edit.
- [ ] No row has a `source_uri` containing a wildcard character; if present,
      the driver must use the GCS JSON API download path (the existing
      `abc_batch.py` already handles this).

---

## 4. Storage, compute and sharding

### 4.1 Layout

```
outputs/YT500/                    small, committable / GCS-mirrored
  manifest.jsonl                 frozen source of truth (495 rows)
  manifest.sha256
  duplicates.json                the 5 groups + duplicate links
  shards.json                    shard assignment + audio seconds per shard
  abc/<shard>.json               packed ABC + derived melody ABC + QC
  abc_index.json                 run index

work/yt500/                       ephemeral cache
  inventory/                     listing + bucket manifest/report (immutable)
  <VER>/
    ledger.jsonl                 append-only event log
    state/status.json            derived cache (rebuildable)
  audio/<shard>/                 downloaded audio (cache; deletable)
  out/YT500/<shard>/<stem>/      transcribe.py output (one dir per track)
  archives/<shard>/<stem>.tar.gz local archives before upload
  logs/
  qc/

gs://akbar-december-2024-backup/yt_top_500_music_playlist/
  transcripts/<VER>/
    _manifest.jsonl              frozen manifest (495 rows, with hash)
    duplicates.json              the 5 duplicate groups
    _index.json                  run index (written after each shard)
    _index-<utc>.json            versioned copies of the same index
    YT500/
      shard-03/<stem>.tar.gz     one complete track per archive
      abc/shard-03.json          packed ABC + derived melody ABC + QC
```

Per-shard `_timings.csv` / `_driver.log` stay local in `work/yt500/logs/`;
the packed JSON is the durable QC record. The driver writes the GCS index as
`_index-<utc>.json` first, then `_index.json`.

The source prefix is not touched. A new run is a new `VER`; old versions stay
readable.

### 4.2 Budget

| Item | Measured / estimate |
|---|---:|
| Audio to transcribe | **38.27 h** (495 tracks) |
| Raw transcripts | ~0.8 MB/track × 495 ≈ **396 MB** |
| Gzipped archives | ~100–150 MB |
| Packed ABC text | ~2 MB |
| Audio cache | **2.08 GiB** if fully downloaded |
| Venv + model | ~4–5 GB |
| Working disk per shard | ~1 GB |
| GPU wall | **~7.1 h** at 5.42× (range 5.6–8.4 h) |
| With downloads/QC/retries/uploads | **~9–10 h** |
| Shards | 25 × 20 tracks (last shard 15) |

Use **L4 or A100** if available; the prior measured numbers are already
acceptable, but the pilot decides on the actual device. Do not transcribe 495
songs on the local CPU box unless the budget is days (CPU baseline is
~1.6–1.9 CPU-seconds per audio-second, i.e. ~61–73 CPU-hours).

### 4.3 Sharding

- Target **20 tracks per shard** → 25 shards.
- Assign deterministically by duration: sort descending, place each track in the
  currently lightest shard; tie-break by `track_id`. Write `shards.json` once.
- One shard is one checkpoint, one archive set, one commit. It is small enough
  to lose (~1.5 h audio, ~17 min GPU at the median RTF) and large enough that
  per-shard overhead is negligible.
- If per-track upload is enabled (§7.3), a shard can be 25–30 tracks; the loss
  window becomes one track rather than one shard.

---

## 5. Execution phases

### Phase 1 — pilot (10 tracks, one GPU session, ~30 min)

Pick deliberately, not randomly:

| # | Track | Why |
|---|---|---|
| 1 | shortest (142 s) | lower bound |
| 2 | median (277 s) | typical |
| 3 | p95 (367 s) | long |
| 4 | max (416 s, `Pz59wizOqLw`) | window stitching |
| 5 | alternate `Ana Blayak` (`QS0v8uxzfJM`, 340 s) | duplicate-pair path |
| 6 | live `Yhizak Al Shooq` 2020 (`ikcfOn9VzYo`, 362 s) | different performance |
| 7 | a Tier 3 track | repertoire spread |
| 8 | a different artist (e.g. Elissa) | repertoire spread |
| 9 | a short track (<180 s) | lower bound / decode |
| 10 | a `video_id` with `-` or `_` | filename safety |

The frozen builder already writes `outputs/YT500/pilot.json`. Download it with
the hash check built in:

```bash
python3 scripts/yt500_manifest.py --download-pilot \
  outputs/YT500/pilot.json --pilot-dir work/yt500/pilot

./transcribe.sh work/yt500/pilot --full --device cuda \
  --out-dir work/yt500/pilot_out --fail-fast
```

Both members of the `Ana Blayak` pair are included on purpose: this plan
transcribes every unique audio object, so the pilot must prove that two
near-duplicate rows produce two independent, valid outputs.

Measure and write `work/yt500/pilot/report.json`:

- `meta.json.status` for all 10;
- `seconds`, `duration_s`, **RTF**;
- peak VRAM (sample `nvidia-smi` from a second shell);
- `score.abc` bytes, `notes_vocal`, `notes_ins`, `coverage`, `has_chords`;
- `abc2midi` parse exit;
- the duplicate pair: two output dirs, two distinct `abc_sha256`s, both `ok`.

**Gate** (all must pass):

- [ ] 10/10 `status: ok`;
- [ ] 10/10 ABC parse;
- [ ] ≥9/10 `coverage ≥ 0.80`;
- [ ] no `voice_missing` on a sung track;
- [ ] `has_chords` true (this is the `--full` marker);
- [ ] peak VRAM < 11 GB on T4, < 20 GB on L4/A100;
- [ ] RTF ≥ 4× on L4/A100, ≥ 2.5× on T4;
- [ ] the duplicate pair produced two independent `ok` outputs.

If the gate fails, do not start the bulk. Investigate dtype, windowing, disk,
or move to a larger GPU.

### Phase 2 — bulk, detached, shard by shard

```bash
cd /content/music_captioning
export BUCKET=gs://akbar-december-2024-backup/yt_top_500_music_playlist
export VER=2026-11-09
export MANIFEST=outputs/YT500/manifest.jsonl
export MANIFEST_SHA=$(cut -d' ' -f1 outputs/YT500/manifest.sha256)

setsid nohup python3 -u scripts/abc_batch.py \
  --manifest "$MANIFEST" \
  --manifest-sha256 "$MANIFEST_SHA" \
  --index outputs/YT500/abc_index.json \
  --gcs-index \
  --no-commit \
  --gcs-transcripts "$BUCKET/transcripts/$VER" \
  --device cuda \
  --on-collision error \
  --per-track-timeout 1800 \
  --archive-every-track \
  --restore-from-gcs \
  --assumed-rtf 5.0 \
  --max-minutes 150 \
  --amr-dir /content/arabmaqamrock \
  --work-dir work/yt500 \
  --repo /content/music_captioning \
  > logs/yt500_$(date +%Y%m%d_%H%M).out 2>&1 < /dev/null &
disown || true
```

`--on-collision error` is safe because every `output_stem` is unique. The
driver hard-codes `--full`; do not pass it here. `--no-commit --gcs-index` makes
GCS the durable index, so a fresh VM does not depend on git push access.

The driver must do exactly this per shard:

1. Acquire the shard lock.
2. Download only that shard's missing audio (skip-if-present; verify hash).
3. Restore any missing local transcripts from the remote `<stem>.tar.gz`.
4. Run `transcribe.py` on the shard directory with `--full`,
   `--on-collision error`, `--per-track-timeout`, `--time-budget`.
5. Run `qc_track()` per track; write `qc/<stem>.json`.
6. Archive each complete track; upload; verify size + md5; write
   `shard-XX/_timings.csv` and `_driver.log`.
7. Pack `abc/<shard>.json`; upload and verify.
8. Write `_shard-XX.json` and only then mark the shard `done`.
9. Commit `outputs/abc_index.json`, `outputs/YT500/` (`manifest.jsonl`,
   `manifest.sha256`, `duplicates.json`, `shards.json`), `scripts/`, `docs/`
   (never audio, never ABC text unless the repo is private) and push; verify
   `HEAD == @{u}`.

The run loop stops cleanly between shards when `--max-minutes` is reached, so a
session never dies mid-shard by design.

### Phase 3 — QC and retries

- First pass: `--retry-failed` is **off**; a poison track must not loop every
  session.
- After the first full pass, run a second pass with `--retry-failed` and
  `--max-download-failures` raised.
- Retry only **transient** failures automatically (network, 5xx, timeout).
- Deterministic failures (`no-abc`, `invalid-abc`) get one retry, then
  `quarantined` with the log tail.
- `octave_suspect`, `vocal_sparse`, `coverage_low`, `vocal_range` are **flags**,
  not failures; they travel with the row and are never auto-corrected.
- A 20-track listening check (stratified by duration/artist/flag) is required
  before calling the corpus done.

### Phase 4 — pack, index, verify, restore drill

- `abc_pack.py` builds `outputs/YT500/abc/<shard>.json` and the run index.
- `_index.json` is derived: `n_source` (495), `n_transcribed` (495),
  `n_duplicate_groups` (5), `n_ok`, `n_flagged`, `n_failed`, `n_quarantined`,
  total audio/GPU seconds, RTF, model revision, shard list, and each shard's
  archive hashes.
- Remote `_index.json` is written **last**, as `_index-<utc>.json` plus a small
  `LATEST` pointer; a reader never sees a half-written index.
- Restore drill: pick 3 random archives, download, extract to `/tmp`, run
  `transcribe.py --verify` against the manifest, compare `abc_sha256`, delete
  the temp tree. Do this after shard 1 and again at the end.

---

## 6. Guardrails (the part that makes 495 safe)

### 6.1 Source is immutable

- Record `source_sha256`, `source_bytes`, `source_md5`, `source_updated` and
  `source_uri` at freeze time.
- Download to `<dest>.part`, hash, then `os.replace`. Never transcribe a
  `.part`.
- Re-hash before and after transcription. If the source changed, mark
  `source_changed` and **do not overwrite** the existing ABC.
- Never write to the source prefix. If the bucket manifest changes, create a
  new `VER`; old outputs remain valid for the old version.

### 6.2 Three-level resume

| Level | Commit point | Rebuild from |
|---|---|---|
| **Track** | `meta.json` with `status: ok`, matching `source_wav_sha256` and `abc_sha256` | local `out/` or remote archive |
| **Shard** | `_shard-XX.json` written only after every track in the shard is `ok|flagged` and its archive is verified remotely | GCS `transcripts/<VER>/` |
| **Run** | `_index.json` lists done shards | remote `_index-*.json` + `_shard-*.json` |

The tool's `existing_decision()` already enforces the track rule:

- all three hashes match → `skipped`;
- source hash differs → `stale` (exit 1); `--force` only after a verified,
  intentional source change;
- previous status not `ok` → retried;
- no `meta.json` → `skipped-unverified` (warn; do not silently trust);
- ABC hash mismatch → `invalid` (exit 1); `--force` only after audit.

Additional rules:

- `_timings.csv` is **not** a commit point; the tool overwrites it per run.
  Copy it to `reports/<shard>/<timestamp>_timings.csv` and to GCS.
- Never delete a track directory to "retry". Use `--force` on that track or
  `--retry-failed` for the shard.
- A re-run of the same command must be a no-op for completed tracks. Test this
  in the pilot: run the pilot twice; the second run should skip all 10.

### 6.3 Checkpoint and backup policy

Order of durability: **GCS archive > git index > local disk > nothing.**

- After each track (or every N=5 tracks), archive the complete directory and
  upload it. Per-track is cheap (~1 s of upload per track) and bounds the loss
  window to one track.
- A shard is not `done` until every archive is uploaded and verified.
- Keep local track directories until the shard's remote verification passes.
  Then the audio cache may be deleted, but keep the local archive until the
  run index is committed.
- GCS is append-only: no `rsync -d`, no `cp` over an existing differing object.
  If a remote object exists with a different hash, **fail loudly**; do not
  overwrite.
- Enable Object Versioning on the bucket if policy allows; otherwise use a new
  `VER` prefix for every run.
- Optional second copy: a second bucket/region for `transcripts/<VER>/`.
- Git is the third copy of the small artifacts only: manifest, `duplicates.json`,
  `shards.json`, `outputs/abc_index.json`, QC summaries, runbooks. Never audio,
  never raw ABC text in a public repo. Put the frozen manifest at
  `outputs/YT500/manifest.jsonl` (small, committable) and also upload it to
  `transcripts/<VER>/_manifest.jsonl`; `work/` is a cache, not a durable store.

### 6.4 Upload verification

- Compare local size to remote size.
- Compare local MD5 (base64) to the GCS `md5_hash` from
  `gcloud storage hash`; the existing `abc_batch.verify_archive()` does this.
- For composite/resumable objects where MD5 is not the object MD5, compare
  CRC32C instead; record which hash was used.
- Verify the packed JSON the same way.
- A failed verification is a hard stop (`exit 2`); the supervisor must not
  restart into the next shard.

### 6.5 Locking and single writer

- `flock` on `work/yt500/locks/<shard>.lock` before download/transcribe/upload.
- `flock` on `work/yt500/locks/run.lock` around index/pack/commit.
- If a lock is held, exit 0 with "another worker owns this shard"; do not kill
  the other process.
- Never run two `transcribe.py` processes against the same `--out-dir`.

### 6.6 Atomic writes

- Local JSON: write `<name>.tmp`, `fsync`, `os.replace`.
- Archives: write `.tmp`, verify size, `os.replace`.
- GCS: object creation is atomic; readers see the complete object or nothing.
- The run index is the exception: write `_index-<utc>.json` then update the
  tiny `LATEST` pointer; never edit `_index.json` in place.

### 6.7 Failure taxonomy and retries

| Status | Meaning | Action |
|---|---|---|
| `pending` | not started | normal work |
| `running` | in progress | crash recovery: treat as pending |
| `ok` | hashes match | skip forever |
| `flagged` | ABC valid, QC flags | success for resume; report |
| `failed` | tool error | one retry, then quarantine |
| `timeout` | per-track timeout | retry with CPU or longer timeout, then quarantine |
| `no-abc` | model produced none | one retry, then quarantine |
| `invalid-abc` | ABC does not parse | one retry, then quarantine |
| `stale` | source audio changed | **stop**; new `VER` or explicit `--force` |
| `source_changed` | changed during the run | stop; re-freeze |
| `download_failed` | one object | retry; >3 per shard = systemic stop |
| `quarantined` | gave up | keep row, log tail, no silent drop |

Hard stops (`exit 2`): auth/permission, disk full, upload mismatch, commit not
landed, manifest hash drift. The supervisor must **not** restart after exit 2.

### 6.8 Session, disk, auth

Preflight (every session):

```bash
./transcribe.sh --doctor                 # venv, torch, transformers, ffmpeg, cuda
df -h /content /tmp                      # > 15 GB free
nvidia-smi --query-gpu=name,memory.used,memory.total --format=csv
gcloud storage ls "$BUCKET/state/latest/manifest.json" >/dev/null   # read test
gcloud storage ls "$BUCKET/transcripts/$VER/" >/dev/null # write-prefix read test
abc2midi --version                        # QC gate dependency
```

- Run detached: `setsid nohup … & disown`; write a PID/heartbeat file.
- Supervisor restarts on transient non-zero exits, with a cap on quick
  failures; it must not restart on `exit 2`.
- At session end: `gcloud storage ls -l -r` the shard, verify, `git push`, and
  write `state/session-<timestamp>.json` with the last completed shard.
- Never leave a shard only in local disk.

### 6.9 Audit trail

`ledger.jsonl` is append-only, one JSON object per event:

```json
{"utc":"2026-11-09T12:00:00Z","run":"...","shard":"shard-03","track_id":"...",
 "event":"transcribe_end","status":"ok","attempt":1,"seconds":31.4,
 "source_sha256":"...","abc_sha256":"...","model_revision":"...","tool":"..."}
```

Events: `manifest_frozen`, `download`, `download_failed`, `transcribe_start`,
`transcribe_end`, `qc`, `archive`, `upload`, `verify`, `quarantine`,
`shard_done`, `session_end`. Status is rebuilt by replaying the ledger; the
ledger is never edited.

### 6.10 Security and licensing

- Bucket is private. Least-privilege service account; credentials outside the
  repo; rotate after the run.
- Do not commit audio, raw ABC text of commercial recordings, or credentials to
  a public repo. Commit hashes, manifests and reports.
- SheetSage2 and MERT-v2-FullSong are **CC-BY-NC-4.0**; transcription outputs
  are non-commercial. The source audio rights are separate; do not redistribute.

---

## 7. Resume runbook

### 7.1 Fresh VM after a disconnect

```bash
# 1. Environment (idempotent)
cd /content/arabmaqamrock && git pull --ff-only
./plumbing/setup_transcribe.sh --cuda --warm
cd /content/music_captioning && git pull --ff-only

# 2. Auth and identity
gcloud auth login
gcloud config set project <project>
export BUCKET=gs://akbar-december-2024-backup/yt_top_500_music_playlist
export VER=2026-11-09
export MANIFEST=outputs/YT500/manifest.jsonl
export MANIFEST_SHA=$(cut -d' ' -f1 outputs/YT500/manifest.sha256)

# 3. Verify the frozen manifest (committed small file; work/ is ephemeral)
sha256sum "$MANIFEST"   # must equal $MANIFEST_SHA

# 4. Rebuild local state from GCS (not from memory)
python3 scripts/abc_batch.py --list \
  --manifest "$MANIFEST" \
  --manifest-sha256 "$MANIFEST_SHA" \
  --index outputs/YT500/abc_index.json \
  --gcs-index \
  --gcs-transcripts "$BUCKET/transcripts/$VER" \
  --amr-dir /content/arabmaqamrock

# 5. Run the same command; nothing else
setsid nohup python3 -u scripts/abc_batch.py \
  --manifest "$MANIFEST" \
  --manifest-sha256 "$MANIFEST_SHA" \
  --index outputs/YT500/abc_index.json \
  --gcs-index --no-commit \
  --gcs-transcripts "$BUCKET/transcripts/$VER" \
  --device cuda --on-collision error --per-track-timeout 1800 \
  --archive-every-track --restore-from-gcs --assumed-rtf 5.0 \
  --max-minutes 150 --amr-dir /content/arabmaqamrock \
  > logs/yt500_$(date +%Y%m%d_%H%M).out 2>&1 < /dev/null &
disown || true
```

The driver skips done shards, restores missing local transcripts from remote
archives, and re-transcribes only tracks whose `meta.json` is absent or not
`ok`. `--force` is not needed and must not be used.

### 7.2 Event → recovery matrix

| Event | What is lost | Recovery |
|---|---|---|
| One track crashes | that track | re-run the shard; hash guard skips the rest |
| VM dies mid-shard | local audio + un-uploaded outputs | re-run; restore uploaded archives; redo ≤1 shard, or ≤1 track if per-track upload |
| GCS upload fails | nothing (local kept) | retry; shard not marked done; hard stop if hash mismatch |
| Archive corrupt | one archive | `transcript_archive.py --verify`; re-archive from local; else re-transcribe |
| Index commit fails | one commit | retry push; hard stop if `HEAD != @{u}` |
| Bucket manifest changes | freeze | new `VER`; old outputs remain |
| Auth expires | uploads | `gcloud auth login`; resume |
| Disk full | current shard | clean `work/audio` for completed shards; never delete `out/` before verification |
| Model/venv lost | environment | rebuild; outputs unaffected |

### 7.3 Restore drill (do not skip)

```bash
# Pick 3 random archives from the shard index.
python3 plumbing/transcript_archive.py work/yt500/out/YT500/<shard> --verify
mkdir -p /tmp/restore && tar -xzf <archive> -C /tmp/restore
python3 transcribe.py /tmp/restore/<stem> --verify
```

The archive must reproduce `score.abc` byte-for-byte and the `abc_sha256` must
match `meta.json`. Then delete `/tmp/restore`. Run this after the first shard
and again at the end.

---

## 8. QC gates

Use the existing `abcscore.qc_track()`; do not write a second parser.

| Check | Threshold | On failure |
|---|---|---|
| ABC parse (`abc2midi`) | exit 0, no incomplete-bar warnings | `parse_fail`; retry once, then quarantine |
| Voices | `V: Vocal` and `V: Ins` present | `voice_missing`; flag |
| Vocal presence | ≥ 50 pitched notes | `vocal_sparse`; flag |
| Duration coverage | last beat ≥ 0.80 × audio duration | `coverage_low`; flag |
| Vocal range | median in E3–A5 | `vocal_range`; flag |
| Key/chord labels | `key.lab` and `chord.lab` non-empty | `key_chord_missing`; flag |
| Tempo | 40–200 BPM | `tempo_out_of_range`; flag |
| Octave | phrase-level ±12 on ≥10 notes | `octave_suspect`; **never auto-correct** |
| Chords | `has_chords` true for `--full` | flag; check the `--full` flag reached the model |

`flagged ≠ failed`. Flags travel with the row; downstream decides. Nothing is
edited in this plan; the `maqam-edit` workflow is a separate, later pass over
selected scores.

Listening check: 20 tracks, stratified. Answer only:

1. Does the vocal line follow the singer?
2. Is the phrase structure plausible?
3. Is the octave where you hear it?

Record the verdicts in `docs/yt500-results.md`.

---

## 9. Definition of done

- [ ] All **495** source rows are accounted for and all **495** are transcribed
      (`n_objects == n_transcribed == 495`); `duplicate_of` is metadata, not a
      skip.
- [ ] Every track has `meta.json.status ∈ {ok, flagged}` with matching
      source/ABC hashes, or a written exception with a reason.
- [ ] Each of the 5 duplicate groups has a `duplicate_of` link between two
      transcribed rows; both outputs exist and differ.
- [ ] 25/25 shard archives, 495 track archives, and `abc/<shard>.json` in
      `gs://.../yt_top_500_music_playlist/transcripts/<VER>/`.
- [ ] `_index.json` counts match the ledger: `n_ok`, `n_flagged`, `n_failed`,
      `n_quarantined`, `total_audio_h`, `total_gpu_h`, `rtf`.
- [ ] `transcribe.py --verify` is clean against a restored sample.
- [ ] Restore drill passes for 3 random archives.
- [ ] QC report: parse rate, flag histogram, note-count distribution, coverage,
      measured RTF and peak VRAM.
- [ ] 20-track listening check recorded.
- [ ] No source object modified; no audio, raw ABC or secrets in git.
- [ ] One honest paragraph on what SheetSage2 gets wrong on this repertoire,
      written from the listening check, not from the model card.

---

## 10. Timeline

| Day | Work | Wall |
|---|---|---|
| D0 | Auth, inventory, manifest, dedupe report, acceptance gate | 2–3 h CPU |
| D0 | Pilot (10 tracks) + gate | 30–45 min GPU |
| D1 | Shards 01–08 | 2.5–3 h GPU |
| D2 | Shards 09–17 | 2.5–3 h GPU |
| D3 | Shards 18–25 + retries | 2.5–3 h GPU |
| D3 | Pack, index, verify, restore drill, listening check | 2–3 h CPU |

On a single L4/T4 this is **3–4 GPU sessions**. On CPU it is **~61–73 hours**;
do not schedule it that way.

---

## 11. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Bucket manifest/audio changes after freeze | medium | stale plan or mixed corpus | record the manifest `sha256`; a change is a new `VER`; re-hash every download |
| Near-duplicate group is actually a different performance | medium | one version under-represented | transcribe all 495 and keep `duplicate_of` as metadata; the 5 extra jobs are cheap |
| VM killed mid-shard | high | ≤1 shard lost | per-track archive/upload; shard index; same-command resume |
| Upload silently truncated | low | corrupt backup | size + MD5 verify; hard stop |
| Auth expires mid-run | medium | uploads fail | re-auth; local outputs kept; hard stop |
| Disk fills with audio | medium | shard stops | clean verified shards' audio; preflight >15 GB |
| Octave transposition | certain (~4 % of tracks) | bad training targets | QC flag, never auto-correct |
| Western key/chord labels on maqam | certain | metadata only | record; do not "fix"; do not use key as maqam |
| Public repo redistributes ABC | policy | legal | GCS-only ABC; commit hashes/manifests only |
| One poison track loops forever | medium | session wasted | retry once, then quarantine; `--retry-failed` only in a second pass |
| Model revision drift | low | non-reproducible | pin `b83c3d79…`; record in every `meta.json` and the index |

---

## 12. Open decisions

1. **GPU target.** L4/A100 preferred; T4 is acceptable if the pilot confirms
   ≥2.5×. **Recommendation: L4 if available, T4 fallback; CPU only for the
   pilot if no GPU is free.**
2. **`--full` vs `--melody-only`.** The production pipeline needs chords
   (round 05). **Recommendation: `--full` once; derive melody-only with
   `strip_chords()` for free.**
3. **Where does ABC text live?** Raw ABC of 495 commercial recordings is a
   redistribution risk. **Recommendation: GCS-only for raw archives and packed
   ABC; commit only manifests, hashes and reports. If the repo is made private,
   packed ABC JSON can be committed.**
4. **Duplicate policy.** **Recommendation: transcribe all 495 unique audio
   objects; skip only byte-identical/same-video duplicates (none here); mark the
   5 same-title groups with `duplicate_of` for downstream dedupe.**
5. **Output prefix.** **Recommendation: a new
   `.../yt_top_500_music_playlist/transcripts/<VER>/` prefix; never write into
   the source audio tree.**
6. **Lyrics/ASR.** Out of scope. If needed, it is a separate phase after the
   ABC corpus exists.

---

## Appendix A — status enum

`pending`, `running`, `ok`, `flagged`, `failed`, `timeout`, `no-abc`,
`invalid-abc`, `stale`, `source_changed`, `download_failed`, `quarantined`.

Resume success = `ok` + `flagged`. A `skipped-unverified` row is a warning, not
a success; audit it before the final index.

## Appendix B — one-track checklist

- [ ] source hash matches the manifest;
- [ ] download is complete (`.part` gone);
- [ ] `meta.json.status == ok`;
- [ ] `abc_sha256` matches the file;
- [ ] `qc.parse == ok`;
- [ ] archive exists, is non-empty, and verifies;
- [ ] remote object exists with matching size + hash;
- [ ] ledger has `archive`, `upload`, `verify` events.

## Appendix C — useful commands

```bash
# Inventory (the bucket already has the authoritative manifest)
mkdir -p work/yt500/inventory outputs/YT500
gcloud storage cp "$BUCKET/state/latest/manifest.json" work/yt500/inventory/manifest.json
gcloud storage cp "$BUCKET/state/latest/report.json" work/yt500/inventory/report.json
gcloud storage ls -l "$BUCKET/audio/" > work/yt500/inventory/audio_listing.txt

# Freeze + checks
python3 scripts/yt500_manifest.py --bucket "$BUCKET" \
  --report work/yt500/inventory/report.json \
  --out outputs/YT500/manifest.jsonl
python3 scripts/yt500_manifest.py --check outputs/YT500/manifest.jsonl

# Pilot (10 tracks, hash-checked)
python3 scripts/yt500_manifest.py --download-pilot \
  outputs/YT500/pilot.json --pilot-dir work/yt500/pilot
./transcribe.sh work/yt500/pilot --full --device cuda \
  --out-dir work/yt500/pilot_out --fail-fast

# Dry-run the batch plan (no GPU)
python3 scripts/abc_batch.py --list \
  --manifest outputs/YT500/manifest.jsonl \
  --index outputs/YT500/abc_index.json --gcs-index \
  --gcs-transcripts "$BUCKET/transcripts/$VER" \
  --amr-dir /content/arabmaqamrock

# One shard, detached (replace shard-03)
setsid nohup python3 -u scripts/abc_batch.py \
  --manifest outputs/YT500/manifest.jsonl \
  --index outputs/YT500/abc_index.json \
  --gcs-index --no-commit \
  --gcs-transcripts "$BUCKET/transcripts/$VER" \
  --device cuda --on-collision error --per-track-timeout 1800 \
  --archive-every-track --restore-from-gcs --assumed-rtf 5.0 \
  --album shard-03 --max-minutes 150 \
  --amr-dir /content/arabmaqamrock \
  > logs/yt500_shard.out 2>&1 < /dev/null &
disown || true

# Verify without a GPU
python3 transcribe.py work/yt500/out/YT500/<shard> --verify
python3 plumbing/transcript_archive.py work/yt500/out/YT500/<shard> --verify

# Pack + index
python3 scripts/abc_pack.py --outputs outputs \
  --manifest outputs/YT500/manifest.jsonl --raw-dir work/yt500/out
```
