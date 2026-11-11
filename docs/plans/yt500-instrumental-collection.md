# YT500 instrumental — legitimate-track dataset (audio + lyrics + style)

**Status:** built and published 2026-11-11 — 460 tracks at
`gs://akbar-december-2024-backup/DATASET/yt500_instrumental/`;
`--verify --remote` reports 460 folders / 460 audio files / 0 problems.
**Inputs:** the finished 489-song run (see
[quality audit](yt500-instrumental-quality-audit.md)) and the frozen corpus
(`outputs/YT500/generation/index.json`, `manifests/yt500_instrumental_489.json`).
**Target:** `gs://akbar-december-2024-backup/DATASET/yt500_instrumental/`
— one dataset prefix, one self-contained folder per track.
**Goal:** every track that passes the quality gate is published with its own
audio, section tag plan, style prompt, score and metadata, so a consumer can
take one folder and have everything that produced that take.

---

## 0. TL;DR

- **Default set: the 460 takes that pass the ±15% duration gate.** The 7
  `short_severe` takes are always excluded; the 22 gray takes
  (15 `short` + 7 `long`) can be added through an explicit accept file without
  touching code (→ 482).
- **Audio volume: 3.02 GB** for 460 MP3s (3.17 GB for 482). No WAV masters
  exist in GCS; the dataset is MP3-only, matching the trial policy.
- **Layout is per track**, not per artifact type:
  `tracks/<name>/{audio.mp3, lyrics.txt, style.txt, score.abc, track.json}`.
  Each folder is portable and self-describing.
- **There is exactly one style** in the corpus (`style_sha256`
  `bddaf3f9…`, the manifest-18 string) and **150 unique section/tag plans**
  across 489 songs. The canonical style lives once at `recipe/style.txt`, and
  every track folder carries its own copy for portability (992 bytes each).
- **"Lyrics" in this corpus are section tag plans, not sung words**
  (`[intro] [verse] [chorus] …`, derived from the score's `% section`
  comments). The dataset labels them `kind: "section_tags"`. Real Arabic words
  are a separate data-acquisition task; the ABC corpus has none.
- Build metadata locally (small, no GPU), upload metadata, then copy audio
  **GCS→GCS** into the same folders. Nothing is re-rendered.

---

## 1. Which tracks are "legit"

The dataset set is a **selection over the audit**, never a hand-copied list.

| Set | Rule | Count |
|---|---|---:|
| `pass` (default) | `generation_status == ready` **and** absent from `quality_audit_duration.json` | **460** |
| `accepted` | `pass` + names in `work/yt500_gen/accepted_gray.txt` | 460–482 |
| Excluded always | audit bucket `short_severe` | 7 |
| Out of scope | 4 `no-abc` + 2 `inline-key` (never generated) | 6 |

Rules:

1. A name is included only if it has a kept take (MP3 exists, sidecar
   `status: ok`, `exit: 0`, `abc_sha256` matches the corpus).
2. A `short_severe` name is rejected even if it appears in the accept file.
3. The accept file, if present, is one name per line, `#` comments allowed.
   It is committed so the set is reproducible.
4. The set is computed from the audit + index, not from directory listings.

---

## 2. Dataset layout

### 2.1 Canonical GCS dataset

```
gs://akbar-december-2024-backup/DATASET/yt500_instrumental/
  DATASET_CARD.md                 # counts, gate definition, recipe, how to fetch
  README.md                       # same card (bucket-convention alias)
  manifest.json                   # version, counts, source runs, file hashes
  _SUCCESS                        # written last; marks a complete build
  catalog.jsonl                   # one row per track, all metadata + inline tag plan
  tracks.jsonl                    # alias of catalog.jsonl for ML loaders
  tracks.parquet                  # flattened view for analytics
  catalog.csv                     # flat spreadsheet view
  catalog.md                      # human-readable table, ordered by rank
  playlist.m3u                    # track folders in rank order
  recipe/
    style.txt                     # the exact manifest-18 style prompt
    recipe.json                   # defaults/loras/scales/cot + hashes
  tracks/
    yt500-0001-fbK2ySlxAW4/
      audio.mp3                   # the kept take (192k MP3)
      lyrics.txt                  # section tag plan used for this take
      style.txt                   # exact style used (copy of recipe/style.txt)
      score.abc                   # instrumental ABC actually rendered
      track.json                  # ids, hashes, seed, provenance, artifacts map
    yt500-0002-…/
      …
```

Why per-track folders:

- **Portable:** copy one folder and you have the audio, the conditioning text,
  the score and the provenance. No joins across directories.
- **Clearly named:** the folder is the track id; the file names are the artifact
  roles. A human or a loader can find `lyrics.txt` without a manifest lookup.
- **Flat-friendly:** `catalog.jsonl` still gives a one-line-per-track view; a
  loader never needs to walk folders if it does not want to.
- **Stable:** the take seed lives in `track.json`, not the folder name, so a
  re-render does not rename the track folder.

### 2.2 Local build tree

```
outputs/YT500/generation/collection/
  DATASET_CARD.md / README.md / manifest.json / _SUCCESS
  catalog.jsonl / tracks.jsonl / tracks.parquet
  catalog.csv / catalog.md / playlist.m3u
  recipe/style.txt / recipe/recipe.json
  tracks/<name>/track.json, lyrics.txt, style.txt, score.abc
  .build.json                     # input hashes, counts, built_at
```

Audio is **not** stored locally unless `--download-dir` is used. The local tree
mirrors the dataset minus `audio.mp3`, so `gsutil rsync -r` publishes it
directly.

### 2.3 Git policy

- Commit: `catalog.jsonl`, `catalog.csv`, `catalog.md`, `recipe/*`, the accept
  file, and `.gitignore` additions.
- Do not commit: `tracks/**` (derived), audio, and any local download dir.

---

## 3. Per-track metadata — `track.json`

```json
{
  "name": "yt500-0001-fbK2ySlxAW4",
  "rank": 1,
  "video_id": "fbK2ySlxAW4",
  "title": "…",
  "artist": "…",
  "country": "…",
  "tier": "…",
  "gate": "pass",
  "nominal_s": 276.3,
  "wav_s": 271.9,
  "delta_pct": -1.6,
  "sections": ["intro", "verse", "chorus", "outro"],
  "artifacts": {
    "audio": "audio.mp3",
    "lyrics": "lyrics.txt",
    "style": "style.txt",
    "score": "score.abc"
  },
  "generation": {
    "run": "20261110-095521_yt500inst",
    "seed": 391847,
    "cap": 7023,
    "engine": "batch",
    "status": "ok",
    "exit": 0,
    "end_utc": "2026-11-10T…Z"
  },
  "lyrics": {"kind": "section_tags", "sha256": "…"},
  "style": {"sha256": "bddaf3f9…", "id": "manifest18"},
  "recipe": {
    "cot": "full", "lora": "instrumental_v9",
    "ar_scale": 0.85, "nar_scale": 1.0, "trigger": false,
    "model": "Yue2-3B-GGUF"
  },
  "score": {
    "abc_sha256": "…",
    "source": "gs://…/runs/<run>/scores/<name>.abc"
  },
  "audio": {
    "mp3_sha256": null,
    "mp3_bytes": 6712044,
    "source": "gs://…/runs/<run>/<name>_<seed>.mp3",
    "wav_sha256": "…"
  },
  "provenance": {
    "audit_bucket": "pass",
    "takes": ["<name>_<seed>", "…"]
  }
}
```

`catalog.jsonl` is `track.json` flattened plus the tag-plan text inline; it is
the single-file index for loaders. `catalog.csv` and `catalog.md` are views of
the same rows.

---

## 4. Joins and identity

| Key | From | Used for |
|---|---|---|
| `name` | `yt500-<rank>-<video_id>` | track identity and folder name |
| `seed` | sidecar + filename | take identity; lives in `track.json` |
| `abc_sha256` | sidecar / run manifest / corpus | rejects a take made from another score |
| `lyrics_sha256` | run `batch_manifest.json` | proves the published tag plan is the one rendered |
| `style_sha256` | run `batch_manifest.json` | proves the published style is the one rendered |
| `wav_sha256` | sidecar | provenance even though only MP3 is shipped |

The compiler **fails closed**: a missing sidecar, missing prompt, hash
mismatch, or missing MP3 aborts the build (or, with `--skip-broken`, records the
row under `rejected.jsonl` and continues). It never invents lyrics or a style.

Duplicate takes: `yt500-0129` and `yt500-0159` were rendered three times each
after the first MP3 upload failed. The dataset keeps **one** take per song — the
newest run that has an MP3 — and lists all three in `provenance.takes[]`.

---

## 5. Compiler — `plumbing/compile_yt500_collection.py`

Pure Python + `gsutil`; no torch, no GPU.

### 5.1 Modes

```bash
python3 plumbing/compile_yt500_collection.py --refresh-meta --build
python3 plumbing/compile_yt500_collection.py --build --accept work/yt500_gen/accepted_gray.txt
python3 plumbing/compile_yt500_collection.py --verify
python3 plumbing/compile_yt500_collection.py --publish
python3 plumbing/compile_yt500_collection.py --download-dir local_workspace/dataset/yt500
```

| Flag | Effect |
|---|---|
| `--build` | resolve the set, join metadata, write the local tree; no audio |
| `--refresh-meta` | re-sync run metadata from GCS first (no audio) |
| `--accept PATH` | add gray names; `short_severe` still rejected |
| `--strict` (default) | any missing/garbled take fails the build; `--skip-broken` demotes it to `rejected.jsonl` |
| `--publish` | upload the local tree, then copy audio GCS→GCS into `tracks/<name>/audio.mp3` |
| `--download-dir` | copy the published `audio.mp3` files locally |
| `--verify [--remote]` | re-hash local metadata; with `--remote`, count objects under the dataset prefix |
| `--dry-run` | print counts and copy lists; write nothing |

### 5.2 Selection and take resolution

1. Load `index.json` (ready names) and `quality_audit_duration.json`.
2. `pass = ready − audit.failing`; add accepted names; subtract `short_severe`.
3. List `<run>/*.mp3` once per session run to know which take stems exist.
4. For each name, gather every take across run manifests.
5. Keep the newest take (by `end_utc`, then run name) that has an MP3 and a
   valid marker; record the rest in `provenance.takes[]`.
6. Cross-check `abc_sha256`, `lyrics_sha256`, `style_sha256` before writing.

### 5.3 Styles and lyrics

- `recipe/style.txt` holds the single manifest-18 style blob; every
  `tracks/<name>/style.txt` is a copy (992 bytes) so the folder is standalone.
  `recipe.json` records `style_sha256`, `defaults`, `loras`, scales and `cot`.
- If a later corpus introduces style variants, add `recipe/styles/<sha>.txt` and
  keep the per-track copy; `track.json.style.sha256` identifies the variant.
- `lyrics.txt` is the section tag plan, not words. `track.json` records
  `kind: "section_tags"` and the hash. A future `--lyrics-source PATH` can join
  real lyrics by track name and switch `kind` to `sung_lyrics`.

### 5.4 Idempotence and publish semantics

- All local writes are atomic (`*.tmp` + rename); the build is deterministic
  except `.build.json.built_at`.
- Metadata publish: `gsutil -m rsync -r outputs/.../collection/ gs://…/DATASET/yt500_instrumental/`
  (no `-d`, so existing audio is never deleted).
- Audio publish: a bounded thread pool runs `gsutil cp -n <source> <dest>`
  per track. Server-side copies, no local staging. `-n` makes a rerun cheap.
- `--download-dir` reads from the dataset prefix, not the old run dirs, so it
  verifies what was actually published.

---

## 6. Publish and README

`--publish` writes the prefix from §2.1. `DATASET_CARD.md` / `README.md` state:

- counts: 460 tracks, 22 accepted-later, 7 excluded severe, 6 out of scope;
- the gate formula and audit date;
- that `lyrics.txt` is a section tag plan, not words;
- the exact style text and the LoRA recipe (cot, aliases, scales);
- how to fetch one track, the catalog, or everything;
- provenance: run names, seeds, score hashes;
- the licence/credit note for the YT500 source and artists.

Mirror `catalog.jsonl` to
`gs://akbar-december-2024-backup/GENERATION/YT500_INSTRUMENTAL/generation_index.jsonl`
so the generation plan §11 links keep working.

---

## 7. Validation gates

| Check | Pass condition |
|---|---|
| Set size | `460` by default; `460 + len(accept)` when used; never includes `short_severe` |
| Coverage | every `ready` name is in the set or in `rejected.jsonl` with a reason |
| Uniqueness | one folder and one `catalog.jsonl` row per `name` |
| Dataset envelope | `manifest.json`, `_SUCCESS`, `tracks.jsonl` and `tracks.parquet` exist and agree with the catalogue |
| Folder completeness | every `tracks/<name>/` has all five files |
| Audio | every `audio.mp3` object exists, > 100 KB, sidecar `status/exit` ok |
| Score | `score.abc` sha == corpus hash |
| Lyrics | `lyrics.txt` non-empty, sha == `lyrics_sha256` in the take's run manifest, ≥1 `[tag]` |
| Style | exactly one `style_sha256`, equals manifest 18; every `style.txt` re-hashes to it |
| Recipe | `cot=full`, `lora=instrumental_v9`, `ar=0.85`, `nar=1.0`, `trigger=false` |
| Determinism | rebuild produces identical catalogue/CSV/M3U |
| Publish | `tracks/*/` count == rows and `tracks/*/audio.mp3` count == rows |

---

## 8. Tests (pure Python, no GPU, no network)

`tests/test_compile_yt500_collection.py`:

1. Selector: fixture audit with 5 pass, 2 gray, 1 severe → default 5; accept
   adds 2; severe still excluded.
2. Take resolution: a name with three takes (two without MP3) → picks the
   newest MP3 take; provenance lists all three.
3. Hash guards: wrong `abc_sha256`, `lyrics_sha256` or `style_sha256` fails.
4. Broken take: `--strict` fails; `--skip-broken` writes `rejected.jsonl`.
5. Determinism: two builds → byte-identical catalogue (ignore `built_at`).
6. Folder writer: five files per track, artifact names exact.
7. Catalogue/CSV/M3U consistency: same names, same order, same seeds.
8. Style copies: one distinct style; every `style.txt` hashes to it.
9. Real-corpus snapshot (read-only, skipped if inputs absent): 460 rows,
   29 excluded, 489 accounted for, style sha `bddaf3f9…`.

---

## 9. Operator quick reference

```bash
# 1. metadata build from the current audit + synced GCS metadata
python3 plumbing/run_yt500_generation.py --status --work-dir /tmp/yt500_status
python3 plumbing/compile_yt500_collection.py --refresh-meta --build
python3 plumbing/compile_yt500_collection.py --verify

# 2. publish the dataset (metadata rsync, audio GCS->GCS)
python3 plumbing/compile_yt500_collection.py --publish

# 3. optional local copy (≈3 GB), read back from the dataset itself
python3 plumbing/compile_yt500_collection.py --download-dir local_workspace/dataset/yt500

# 4. later, accept the gray takes and republish (no re-render)
printf '%s\n' yt500-0259-UeL9kJ4uGyY … > work/yt500_gen/accepted_gray.txt
python3 plumbing/compile_yt500_collection.py --build --verify --publish
```

Expected: 460 folders under `tracks/`, each with five files; `catalog.jsonl`
with 460 rows; `recipe/style.txt` plus 460 identical per-track copies.

---

## 9.1 Implementation status (2026-11-11)

Done:

- `plumbing/compile_yt500_collection.py` implements `--build`, `--verify`,
  `--publish`, `--download-dir`, `--accept`, `--refresh-meta`, `--dry-run`.
- Local build: 460 rows, `pass=460`, `accepted=0`, `rejected=0`; style
  `bddaf3f9…`; 142 unique tag plans.
- Published to `gs://akbar-december-2024-backup/DATASET/yt500_instrumental/`
  (metadata rsync + 460 server-side MP3 copies, ~2m15s).
- `--verify --remote`: **460 folders, 460 audio files, 0 problems**.
- Dataset envelope matches the sibling `DATASET/fadhl_shaker_instrumental_18`
  conventions: `DATASET_CARD.md`, `manifest.json`, `tracks.jsonl`,
  `tracks.parquet`, `_SUCCESS`.
- `.gitignore` excludes `collection/tracks/`, `.build.json`, `rejected.jsonl`;
  the catalogue and recipe remain committable.

Not done: the accept-file republish to 482 and the offline unit tests in §8.
The 7 severe-short takes remain excluded by construction.

---

## 10. Open decisions

1. **Strict 460 or 482?** Default 460; accepting the 22 gray takes is one file
   and one republish, no audio work.
2. **Keep the seed out of the folder name?** Recommended yes — the folder is the
   song identity; the take seed is in `track.json` and in provenance.
3. **Ship a per-track `style.txt` copy?** Recommended yes (992 bytes × 460) so
   each folder is standalone; `recipe/style.txt` is the canonical copy.
4. **Do the tag plans count as "lyrics"?** They are what the model was
   conditioned on. Recommended: ship them, labelled `section_tags`, and add
   real words later only from a real source.
5. **Include the ABC score?** Recommended yes — it is the only record of
   melody/maqam/section structure, and it is tiny.
6. **Commit the catalogue?** Recommended yes; audio and `tracks/**` stay out of
   git.

---

## 11. Risks

| Risk | Mitigation |
|---|---|
| "Lyrics" turns out to mean sung words | Explicit `kind: section_tags`; separate acquisition task, never invent |
| A take's prompt changed after render | Hard-fail on `lyrics_sha256`/`style_sha256` mismatch with the run manifest |
| Duplicate takes leak into the dataset | One folder per `name`; provenance keeps the rest; uniqueness gate |
| 3 GB copy is slow/expensive | Server-side GCS→GCS, 16-way, `cp -n`; no local staging |
| Later audit revision changes the set | `.build.json` pins input hashes; rebuild is explicit |
| Per-track copy drifts from canonical style | Every `style.txt` is re-hashed during `--build`/`--verify` |
| Broken take silently accepted | `--strict` default; `rejected.jsonl` is the only escape hatch |

---

## See also

- [yt500-instrumental-generation.md](yt500-instrumental-generation.md) §11 (final audit and collection)
- [yt500-instrumental-quality-audit.md](yt500-instrumental-quality-audit.md) (29 failures and the 460/22/7 split)
- [yt500-instrumental-run-log.md](yt500-instrumental-run-log.md) (run provenance)
- `outputs/YT500/generation/quality_audit_duration.json`, `index.json`
- `manifests/yt500_instrumental_489.json` (style + LoRA recipe)
