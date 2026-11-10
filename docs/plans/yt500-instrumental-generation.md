# YT500 instrumental generation — 489 scores, A100 batch, resumable across Colab sessions

**Status:** CPU side implemented; A100 pilot pending
**Implemented:** 2026-11-10 — corpus builder, 489-score manifest, GCS bundle,
resume/batch driver, `generate.py --requests-out`, offline tests.
**Source corpus:** `gs://akbar-december-2024-backup/TRANSCRIPTS/YT500/`
**Reference recipe:** `manifests/fadhl_shaker_instrumental_18.json`
**Goal:** turn every usable YT500 ABC score into an instrumental track using
exactly the Fadl Shaker round-18 prompt, LoRA pair and scales; run without a
time cap on an **A100**; survive a Colab disconnect without restoring the old
run env.

---

## 0. TL;DR

- The transcription finished: **495 tracks, 491 with a parsed ABC**, 4 failed.
- **489 scores are ready to generate.** Two are deferred for an inline-key
  conversion problem; the other 4 have no ABC at all (see §1).
- **A100 target.** VRAM is not the issue; the per-process model load is. The
  existing per-track path pays ~4 min of load per song (~34 h across 489).
  Use `audiocpp_cli --request-sequence` to keep one session loaded and render
  the whole pending set in one process. That is the shortest path; the
  per-track `generate.py` path remains the fallback.
- **One session is possible only if batch mode works well.** The A100 decode
  rate is measured by a 4-track A/B pilot. Optimistic: 8–16 GPU-hours (1–2
  sessions). Pessimistic: 24–33 h (2–4 sessions). The plan never imposes a time
  cap.
- **Resume is GCS-driven, not run-dir-driven.** The existing
  `plumbing/backup_to_gcp.py` uploads each take's `_time.txt` and sidecar.
  A small driver reads those markers from GCS, filters the 489-song master
  manifest down to the songs that are not done yet, and starts a **new** session
  run dir. It never downloads the old audio and never restores the old Colab
  environment.
- The Fadl recipe is copied programmatically from manifest 18, so the style,
  CoT mode, LoRA aliases, adapter scales and trigger setting cannot drift.

---

## 1. What is actually in the corpus

Verified against `_index.json` and the 25 packed shard JSONs on 2026-11-10.

| Item | Count |
|---|---:|
| Frozen source tracks | 495 |
| Tracks with a parsed ABC | **491** (487 pack-ok + 4 flagged) |
| Failed transcription (`no-abc`) | 4 |
| ABC scores recoverable by the key normalizer | 3 |
| ABC scores deferred (inline key change) | 2 |
| **Ready to generate** | **489** |
| Source audio of the 489 | **37.73 h** (median 276 s) |
| Duplicate-title groups | 5 groups / 10 tracks (all distinct audio) |

The 4 `no-abc` failures (no score, nothing to generate):

| Track | Duration | Shard |
|---|---:|---|
| `yt500-0006-INJSYLVA_fg` | 345.1 s | shard-03 |
| `yt500-0176-h9BH8M5ot2c` | 360.6 s | shard-20 |
| `yt500-0552-AsE0VyQX1B0` | 341.7 s | shard-24 |
| `yt500-0655-dcxCOzupe00` | 305.2 s | shard-01 |

The 4 pack-level `flagged` tracks are **included**; all are `octave_suspect`
and still parse `.abc`:

- `yt500-0012-vFGGMYhzvIg` — Marwan Khoury, Ya Rabb
- `yt500-0053-DEFJ9PI4qgc` — Wael Kfoury, Bahebak Ana Ktear
- `yt500-0136-pUnEijzCb1c` — Wael Kfoury, Khodnie Leek
- `yt500-0449-IOjljEMuA2Y` — Kadim Al Sahir, Enni Ouhibouki

The 2 deferred scores (all other tracks are unaffected):

- `yt500-0460-WYMdfrp_sGs` — inline `[K:F]` after pitched notes inside a bar
- `yt500-0495-DXJhlamah70` — inline `[K:G#m]` after pitched notes inside a bar

Both can be made to convert by deleting the inline key change, but that changes
the sounding key of the following section, so it is **not** an automatic fix.
Leave them out of the first pass; treat a manual re-spelling as a later,
separate job.

The 3 recovered scores (key token moved to the bar start; rests precede it):

- `yt500-0071-UO5jte9NP-U`
- `yt500-0378-iMZ1skkbUWI`
- `yt500-0439-lt_pQqHYZSY`

---

## 2. A100: the shortest path is batch mode, not more sessions

The target GPU is now an **A100 (sm80, 40 or 80 GB)**. VRAM is not the
constraint; the dominant cost is the **per-process model load**. The project's
own notes measure that fixed cost on a T4 at ~4 min per `audiocpp_cli` process
(AR init ~68 s, NAR LoRA merge ~117 s, NAR init ~64 s). An A100 loads faster,
but the shape of the problem does not change: `generate.py` starts one process
per track (`run_one.sh`), so the load is paid 489 times.

The binary supports `--request-sequence`, which keeps the session loaded and
renders a list of requests in one process. The A100 plan therefore has two paths:

| Path | Fixed cost | 489 tracks |
|---|---|---|
| Per-track `generate.py` (fallback) | one model load per track (T4 ≈ 4 min; A100 lower) | load paid 489×; on T4 alone ≈ **34 h** |
| **Batch `--request-sequence` (preferred)** | one model load per process/chunk | load paid ~1–10×; total dominated by decode |

The A100 decode rate is not yet measured. If it is 1–2 min/track in batch mode,
the whole corpus is **8–16 GPU-hours**, i.e. **1–2 A100 sessions**. If it is
3–4 min/track, expect **24–33 h**, i.e. **2–4 sessions**. The pilot in §8
measures this before the bulk run; do not trust the estimate until then.

Either way the design has **no `--max-minutes`, no `--limit` and no session
timer**. It runs all pending songs until the VM dies or the user stops it.

> The batch path is conditional: the A100 prebuilt must expose
> `--request-sequence`, and a 4-track A/B test must produce equivalent audio.
> If either check fails, use the per-track `generate.py` path. The resume and
> backup contracts are the same for both.

---

## 3. Architecture

```
TRANSCRIPTS/YT500/YT500/abc/shard-*.json        (source, frozen)
        |
        |  corpus builder (CPU, once, no GPU)
        v
GENERATION/YT500_INSTRUMENTAL/                  (derived, frozen)
  scores.tar.gz       489 instrumental ABC files
  corpus.json         489-song manifest
  index.json          source -> score -> hashes -> flags
  exclusions.json     4 no-abc + 2 deferred
  SHA256SUMS
        |
        |  fetch + verify (one command on every fresh VM)
        v
Colab: scores/yt500_instrumental/ + manifests/yt500_instrumental_489.json
        |
        |  pending driver: read GCS done markers -> write session requests
        v
A100 fast path:  audiocpp_cli --request-sequence  (one loaded session)
   or fallback:  generate.py -> run_one.sh         (one process per track)
        |
        v
out/<UTC>_yt500inst/  ->  WAV + per-take _time.txt + sidecar + MP3
        |
        |  plumbing/backup_to_gcp.py (concurrent daemon, MP3 policy)
        v
gs://akbar-december-2024-backup/arabmaqamrock/runs/<UTC>_yt500inst/
        |
        |  next VM: read only batch_manifest.json + *_time.txt
        v
pending set shrinks; repeat
```

Two processes per session, exactly like the transcription run:

| Process | Role |
|---|---|
| `plumbing/run_yt500_generation.py` | GCS-aware driver: computes pending, writes the session manifest or request list, runs the A100 batch or the per-track fallback. |
| `plumbing/backup_to_gcp.py` | Uploads finished takes and metadata every few minutes. Never transcodes, never deletes remote. |

### 3.1 A100 fast path — batch the requests

The repo's happy-accident notes record the fixed cost of one `audiocpp_cli`
process on a T4: **AR init ~68 s, NAR LoRA merge ~117 s, NAR init ~64 s**
(~4.1 min). `run_one.sh` starts a new process for every track, so on a T4 the
per-track path spends roughly **34 hours on model loading alone** across 489
tracks; an A100 loads faster but still pays it once per track.
`--request-sequence` keeps the loaded session and renders a list of requests,
paying that cost once per batch.

Preflight on the A100:

```bash
nvidia-smi -L
nvidia-smi --query-gpu=name,compute_cap,memory.total --format=csv,noheader
./plumbing/fetch_binary.sh --dry-run    # expect the sm80-a100 tag
./bin/audiocpp_cli --help | grep -E -- '--request-sequence|--task'
```

The prebuilt for `sm80-a100` is already published under
`gs://akbar-december-2024-backup/arabmaqamrock/binaries/sm80-a100/`.
`setup_colab.sh` stages it automatically.

A request record is:

```json
{
  "id": "yt500-0001-fbK2ySlxAW4_391847",
  "lyrics": "[intro]\n[verse]\n[chorus]\n[outro]",
  "seed": 391847,
  "options": {
    "style": "<the exact manifest-18 style string>",
    "cot": "full",
    "semantic_max_tokens": 8450,
    "abc_file": "/content/arabmaqamrock/scores/yt500_instrumental/yt500-0001-fbK2ySlxAW4.abc"
  }
}
```

The session options are the same for every request and match `run_one.sh`:
model + VAE GGUF, the instrumental AR LoRA, the NAR v9 LoRA, their scales
(0.85 / 1.0), and `yue2.attention=flash`.

```bash
./bin/audiocpp_cli --task gen --family yue2 --model models/Yue2-3B-GGUF \
  --backend cuda --threads 8 \
  --session-option yue2.model_gguf=yue2-3b-bf16.gguf \
  --session-option yue2.vae_gguf=yue2-vae-f16.gguf \
  --session-option yue2.ar_lora=/content/arabmaqamrock/loras/instrumental/ar_lora_inst_v3abc.bf16.safetensors \
  --session-option yue2.ar_lora_scale=0.85 \
  --session-option yue2.nar_lora=/content/arabmaqamrock/loras/nar/nar_lora_joint_v9.bf16.safetensors \
  --session-option yue2.nar_lora_scale=1.0 \
  --session-option yue2.attention=flash \
  --request-sequence work/yt500_gen/session_<utc>/requests.json \
  --out-dir out/<utc>_yt500inst --log
```

The binary writes `<out-dir>/<id>.wav` (and per-request artifacts in
`<out-dir>/<id>/`). The batch wrapper then writes the same per-take files that
`run_one.sh` would have written — `_time.txt` with `Exit status: 0`, a `.json`
sidecar with `status: ok`, `wav_sha256`, seed, score hash and wall time — so the
existing MP3 export, backup and resume scanner work unchanged. The wrapper must
watch the output directory and write each marker **as the WAV appears and its
size settles**, not only when the process exits; otherwise a killed batch would
lose every completed request in the chunk.

Implementation note: add a small `--requests-out PATH` mode to `generate.py`
that runs the existing manifest/score/cap/lyrics resolution, writes
`batch_manifest.json`, dumps one request per track, and exits without a GPU.
The batch driver consumes that file. This keeps a single source of truth for
caps, tag plans, seeds and score hashes; do not re-implement the resolver in the
driver.

**A/B gate before trusting the batch path:**

1. Pick 4 tracks with fixed seeds.
2. Render them with the normal per-track `run_one.sh` into `out/ab_single/`.
3. Render the same 4 requests with `--request-sequence` into `out/ab_batch/`.
4. Compare durations and non-silence; with the same seed and options the audio
   should match. If it does not, or if `style`/`cot`/`abc_file` are silently
   ignored, stop and use the per-track path.
5. Measure wall time. Require batch ≤ 60% of the per-track wall (≥1.7× faster).
6. Run a 12–20-track batch once and watch VRAM and per-request failures. If the
   process grows or one failure kills the batch, chunk the request list (for
   example 20–50 tracks per process); the load cost is still paid per chunk,
   not per track.

The resume contract is identical: a completed `<id>.wav` plus its `_time.txt`
and sidecar is a done take; a missing marker is pending. On a fresh VM the
driver rebuilds the request list from the GCS done-set and starts a new batch.

---

## 4. Phase 0 — decisions and hard guards

1. **Same recipe as manifest 18.** Copy these fields verbatim and assert them in
   the builder: `defaults.style`, `lyrics_from_score: true`, `cot: "full"`,
   `lora: "instrumental_v9"`, `lora_ar_scale: 0.85`, `lora_nar_scale: 1.0`,
   `trigger: false`, and the whole `loras` block.
2. **Use the full ABC, not `abc_melody`.** Run the same
   `plumbing/instrumentalize_scores.py` workflow used for the Fadl set. This
   moves the sung Vocal line to Ins, keeps chords on Vocal, and preserves the
   `% section` comments. Verified byte-identical on
   `scores/fadhl_shaker/al_hal.abc` → `scores/fadhl_shaker_instrumental/al_hal.abc`.
3. **Do not edit the score text to make it fit.** The 3 recoverable inline-key
   scores are normalized by moving a key token to the bar start only when the
   preceding music is rests; the 2 ambiguous ones are excluded.
4. **One generator per VM.** Two sessions reading the same GCS done-set would
   duplicate work; there is no distributed lock. The driver takes a local
   `flock`; the operator must not launch a second VM at the same time.
5. **Never `--force`, never delete a run dir, never delete a GCS object.**
6. **MP3 is the default trial policy.** WAV masters are an explicit later
   (`plumbing/mark_production.py out/<run> --all`) if the corpus is accepted.
7. **Keep the repo prefix.** Use the default backup run name
   `arabmaqamrock`; name each generation run with the label `yt500inst` so the
   resume scanner can find it without touching the Fadl/experiment runs.

---

## 5. Phase 1 — build the frozen generation corpus (no GPU)

### 5.1 New script

`plumbing/yt500_generation_corpus.py` (pure Python + network, no torch).

```
python3 plumbing/yt500_generation_corpus.py --build
python3 plumbing/yt500_generation_corpus.py --verify
python3 plumbing/yt500_generation_corpus.py --fetch      # on a fresh VM
```

`--build` does:

1. Download `TRANSCRIPTS/YT500/_index.json` and the 25
   `TRANSCRIPTS/YT500/YT500/abc/shard-*.json` (about 5 MB total).
2. Verify the frozen source (`_index.json` says 495 tracks, 25 albums) and
   select tracks with `transcribe_status == "ok"` and a non-empty `abc` → 491.
3. Write the source ABCs to a temporary `scores/yt500_src/<name>.abc`, where
   `name = yt500-<source_rank:04d>-<video_id>` (ASCII, unique).
4. Apply the key normalizer to any score with an inline `[K:...]` inside a bar:
   - if everything before the key token in that bar is rests, move the token to
     the bar start (recovers 3 of 5);
   - otherwise leave it untouched and record it in `exclusions.json` (2 of 5).
5. Run `plumbing/instrumentalize_scores.py` on the resulting directory.
6. For every output, require the converter report to say:
   - `vocal_notes_after == 0`
   - `chords == "preserved"`
   - `vocal_pitch_onset_duration_preserved == true`
   - `meter_and_tempo_preserved == true`
   - `nominal_seconds` within ~5% of the source `duration_s`
7. Check every instrumental score with `generate.score_section_tags()`; all 489
   must yield at least one tag.
8. Build `manifests/yt500_instrumental_489.json` (see §6), copying
   `defaults` and `loras` from `manifests/fadhl_shaker_instrumental_18.json`.
9. Write `outputs/YT500/generation/index.json` with one row per source track:
   name, rank, video_id, title, source_artist, country, tier, duration_s,
   source shard, pack QC flags, source `abc_sha256`, instrumental `abc_sha256`,
   `nominal_seconds`, `generation_status` (`ready`/`excluded_no_abc`/
   `excluded_inline_key`), and the reason if excluded.
10. Write `outputs/YT500/generation/exclusions.json` and a `SHA256SUMS`.
11. Upload the bundle to
    `gs://akbar-december-2024-backup/GENERATION/YT500_INSTRUMENTAL/`
    (`scores.tar.gz`, `corpus.json`, `index.json`, `exclusions.json`,
    `SHA256SUMS`).

`--fetch` downloads that bundle, extracts the 489 scores to
`scores/yt500_instrumental/`, writes the manifest, and verifies every hash. It
is the only preparation a fresh VM needs.

### 5.2 Expected result

| Item | Value |
|---|---:|
| Ready scores | 489 |
| Excluded `no-abc` | 4 |
| Excluded inline-key | 2 |
| Total source audio | 37.73 h |
| Median score | 276 s |
| Explicit caps required | **0** |

All 489 *converted* scores parse their own length with `abc_duration_s`, so the
cap comes from the score exactly as in manifest 18
(`ceil(score_s * 25) + 60*25`). The source scores for `0071`, `0378` and `0439`
failed the parser because of the inline key token; the instrumentalizer rewrites
them and the converted score parses. Defensive fallback only: if a converted
score ever fails to parse, set `cap = ceil((nominal_seconds + 60) * 25)` on that
song and record it in the index.

### 5.3 Gate

```bash
python3 generate.py manifests/yt500_instrumental_489.json --dry-run > /tmp/yt500_dryrun.txt
head -2 /tmp/yt500_dryrun.txt          # "plan: 489 song(s), 489 track(s)"
grep -c 'cot=full' /tmp/yt500_dryrun.txt   # expect 489
grep -c 'length not parsed' /tmp/yt500_dryrun.txt  # expect 0
```

The dry run needs no GPU. It must show 489 tracks, no score-tag errors, no
missing caps, and the same `cot`/LoRA aliases/scales on every row. It prints a
projected T4 time of ~53 h (`389.6 s/track`); the A100 pilot replaces that with
a measured number.

---

## 6. Phase 2 — manifest shape

`manifests/yt500_instrumental_489.json`:

```json
{
  "base_dir": "..",
  "loras": { "...": "copied verbatim from manifest 18" },
  "scores": {
    "yt500-0001-fbK2ySlxAW4": "scores/yt500_instrumental/yt500-0001-fbK2ySlxAW4.abc",
    "...": "..."
  },
  "defaults": {
    "style": "copied verbatim from manifest 18",
    "lyrics_from_score": true,
    "cot": "full",
    "lora": "instrumental_v9",
    "lora_ar_scale": 0.85,
    "lora_nar_scale": 1.0,
    "trigger": false
  },
  "songs": [
    {"name": "yt500-0001-fbK2ySlxAW4", "score": "yt500-0001-fbK2ySlxAW4"}
  ]
}
```

Rules:

- No per-song `style`, `lyrics`, `lora`, or scale overrides. The score is the
  only per-song input; the cap is derived from the converted score.
- No `repeat`; the reference default is one take per song.
- Names are `yt500-<rank>-<video_id>` so they are unique, ASCII and shell-safe.
  The index carries the Arabic title and artist for listening.
- `lyrics_from_score` turns the `% intro/% verse/% chorus/...` comments into the
  LoRA tag plan. The converter preserves them; the validation in §5.1 step 7
  guarantees every score has at least one usable tag.
- The manifest is committed; the 489 ABC files are **not** committed (they are
  generated data, per the project rule). A fresh clone materializes them with
  `--fetch`.

Update `manifests/README.md` with one row: 489 songs, the YT500 source, the
instrumental-v9 recipe, and the exclusions.

---

## 7. Phase 3 — runtime and backup

### 7.1 Bootstrap a Colab VM

```bash
cd /content/arabmaqamrock
git pull --ff-only
./setup_colab.sh
```

`setup_colab.sh` is idempotent and already does the right things:

- stages the `audiocpp_cli` binary for the GPU architecture;
- downloads the GGUF model, the instrumental AR LoRA and the NAR v9 LoRA;
- installs GNU `time` (without it every take exits 127);
- starts `plumbing/backup_to_gcp.py` detached with the default MP3 policy.

Preflight:

```bash
nvidia-smi -L
nvidia-smi --query-gpu=name,compute_cap,memory.total --format=csv,noheader
./plumbing/fetch_binary.sh --dry-run    # expect the sm80-a100 tag
./bin/audiocpp_cli --help | grep -E -- '--request-sequence|--task'
command -v gsutil && echo "gsutil OK"
python3 plumbing/backup_to_gcp.py --once --dry-run | tail -20
df -h /content
```

- `compute_cap` must be `8.0` on an A100. If the prebuilt tag is not
  `sm80-a100`, stop and check `plumbing/fetch_binary.sh` before generating.
- `--request-sequence` must appear in the binary help. If it does not, use the
  per-track `generate.py` fallback.
- `gsutil` must exist; the backup daemon uses `gsutil rsync`. If only `gcloud`
  is present, install `gsutil` before generating.
- At least ~50 GB free on `/content` for a long session (WAVs are ~50 MB each
  and stay local until the session ends); ~30 GB is enough for ~100 tracks.
  Run `backup_to_gcp.py --once`, then remove an already-backed-up old
  `out/<run>` if space is tight.
- If the daemon is not running, start it:

```bash
setsid nohup python3 plumbing/backup_to_gcp.py --interval-minutes 3 \
  > logs/gcp_backup_stdout.log 2>&1 < /dev/null &
disown || true
```

The default target is `gs://akbar-december-2024-backup/arabmaqamrock/runs/`.
Every generation run dir in `out/` is mirrored there. The script is append/update
only; it never deletes remote objects.

### 7.2 Corpus fetch

```bash
python3 plumbing/yt500_generation_corpus.py --fetch
python3 plumbing/yt500_generation_corpus.py --verify
```

Expected: 489 scores, hashes OK, 4 + 2 exclusions listed.

---

## 8. Phase 4 — pilot and resume round-trip (do this before the full run)

### 8.1 A/B test — batch vs per-track (4 tracks)

The batch path is only worth using if it is both correct and materially faster.
Build a 4-song pilot manifest with **explicit seeds** (the master manifest has
no seeds), then render it twice:

```bash
mkdir -p work/yt500_gen
python3 - <<'PY'
import json, pathlib
m = json.load(open("manifests/yt500_instrumental_489.json"))
idx = {r["name"]: r for r in
       json.load(open("outputs/YT500/generation/index.json"))["tracks"]}
ready = sorted((r for r in idx.values()
                if r["generation_status"] == "ready"),
               key=lambda r: r["duration_s"])
names = ["yt500-0071-UO5jte9NP-U", "yt500-0136-pUnEijzCb1c"]
for r in (ready[0], ready[-1]):
    if r["name"] not in names:
        names.append(r["name"])
names = names[:4]
pilot = {**m,
         "base_dir": str(pathlib.Path.cwd()),
         "scores": {n: m["scores"][n] for n in names},
         "songs": [{"name": n, "score": n, "seed": 1000 + i}
                   for i, n in enumerate(names)]}
json.dump(pilot, open("work/yt500_gen/pilot4.json", "w"), indent=2)
print(names)
PY

# A: per-track baseline (one process per song, same seeds)
python3 generate.py work/yt500_gen/pilot4.json \
  --out-dir out/ab_single

# B: one loaded session, same 4 requests
python3 plumbing/run_yt500_generation.py --run --batch \
  --corpus work/yt500_gen/pilot4.json --max-songs 4 \
  --out-root out --label ab_batch
```

The 4 tracks cover a normal score, a long score, an `octave_suspect` flagged
score, and one key-normalized score (`yt500-0071-UO5jte9NP-U`).

Gate:

- same seed and options produce equivalent audio (durations match; if the
  pipeline is deterministic, the WAVs match). If `style`, `cot`, `abc_file` or
  the LoRA are silently ignored, stop.
- batch wall time ≤ 60% of the per-track wall time (≥1.7× faster). Record the
  measured min/track for each path.

If the A/B fails, use the per-track `generate.py` path for the rest of this plan.

### 8.2 Batch stability pilot (12 tracks)

Add 8 more edge cases to the 4 above: a short score, a long score, a score with
many section changes, a score containing `% interlude` (mapped to `bridge`), a
member of a duplicate-title group, and 3 ordinary tracks. Run them in one
`--request-sequence` process:

```bash
setsid nohup python3 plumbing/run_yt500_generation.py --run --batch \
  --max-songs 12 > logs/yt500_pilot.out 2>&1 < /dev/null &
disown || true
```

One liveness check, then end the turn. The wrapper writes
`logs/yt500_pilot_done.txt` and a per-run `requests.json` plus `batch_manifest.json`.

Watch:

- VRAM over the whole batch (`nvidia-smi` / the per-run `_gpu.csv` if written);
- per-request completion: every request has a WAV + `_time.txt` + sidecar;
- one failed request does not kill the batch; if it does, chunk the request list
  into 20–50-track processes for the full run.

### 8.3 Gate

| Check | Pass condition |
|---|---|
| Generation | 12/12 sidecars `status: ok`, `exit: 0` |
| Audio | 12 non-empty WAVs; MP3s exported |
| Length | duration within ±15% of the score nominal, no `truncated: true` |
| Vocals | listening check: no sung vocal, no vocal chops |
| Arrangement | oud/strings/darbuka audible; sections follow the score |
| Backup | 12 MP3s + `_time.txt` + sidecars visible under the GCS run dir |
| Score copy | each run dir has `scores/<name>.abc` matching the corpus hash |
| Model | `batch_manifest.json` has one unique `style_sha256`, `lora_ar_sha256`, `lora_nar_sha256`, `cot=full` |
| Speed | measured A100 batch min/track updates the session estimate |

If the pilot sings, the score conversion is the first suspect: inspect
`reports/<name>.json` for `vocal_notes_after > 0`. If the arrangement is wrong,
stop before the bulk run.

### 8.4 Resume round-trip test

This is the important test:

```bash
# flush the backup for the 12 pilot takes
python3 plumbing/backup_to_gcp.py --once

# simulate a fresh VM: remove the local run, keep GCS
mv out/<pilot-run> /tmp/<pilot-run>.local

# the driver must now see 12 done from GCS and 477 pending
python3 plumbing/run_yt500_generation.py --status
python3 plumbing/run_yt500_generation.py --plan-only | tail -20
```

Expected: `done=12 pending=477`, and a new session request list that does **not**
contain the 12 pilot names. Do not launch the full run until this passes.

---

## 9. Phase 5 — the uncapped full run

Use `--batch` once the A/B gate passes; omit it if the batch path failed.

```bash
setsid nohup python3 plumbing/run_yt500_generation.py --run --batch \
  --batch-chunk 50 \
  > logs/yt500_gen_$(date +%Y%m%d_%H%M).out 2>&1 < /dev/null &
disown || true
```

`--batch-chunk 50` bounds the loss if one request kills the process; each chunk
still pays the load cost once, so 489 tracks cost about 10 loads, not 489. Use
`--batch-chunk 0` for a single process if the 12-track stability pilot is clean.

The wrapper writes a completion marker
`logs/yt500_gen_<utc>_done.txt` and a summary of done/pending.

One immediate liveness check:

```bash
pgrep -af "run_yt500_generation.py|audiocpp_cli|generate.py" | head
tail -30 logs/yt500_gen_*.out
gsutil ls gs://akbar-december-2024-backup/arabmaqamrock/runs/ | tail
```

Then end the turn. There is no `sleep`, no poll loop and no time cap. The user
returns when the marker exists or when they decide to stop.

If the VM dies mid-chunk, only the in-flight request is lost. The per-take
`_time.txt`, sidecar and MP3 of every completed song are uploaded by the daemon.

---

## 10. Phase 6 — resume on a fresh VM (the core answer)

Nothing from the old Colab environment is needed. The steps are always the same:

```bash
# 1. code + GPU environment (idempotent; starts the backup daemon)
cd /content/arabmaqamrock && git pull --ff-only
./setup_colab.sh

# 2. materialize the frozen corpus from GCS (scores are not in git)
python3 plumbing/yt500_generation_corpus.py --fetch
python3 plumbing/yt500_generation_corpus.py --verify

# 3. see where we are
python3 plumbing/run_yt500_generation.py --status

# 4. continue, detached, uncapped (batch fast path)
setsid nohup python3 plumbing/run_yt500_generation.py --run --batch \
  --batch-chunk 50 \
  > logs/yt500_gen_$(date +%Y%m%d_%H%M).out 2>&1 < /dev/null &
disown || true
```

`--status` prints something like:

```
corpus       489
gcs done     100   (14 session runs)
pending      389
in-flight    0
next         out/20261110-141502_yt500inst
```

### 10.1 How "done" is decided (no audio download)

The driver lists the GCS run tree and downloads **metadata only**:

```bash
gsutil -m rsync -r -x '.*\.(wav|mp3|log|csv)$' \
  gs://akbar-december-2024-backup/arabmaqamrock/runs/ \
  work/yt500_gen/gcs_meta/
```

For each run's `batch_manifest.json` it knows every `(name, seed)` and the
`abc_sha256` that was rendered. A song counts as done only when:

1. there is a `batch_manifest.json` track for it;
2. its `abc_sha256` matches the frozen corpus (prevents skipping a take made
   from a different score);
3. `<name>_<seed>_time.txt` exists and contains `Exit status: 0`.

No MP3/WAV is downloaded. A song finished in the last few minutes before an
unclean disconnect may not have its marker in GCS yet; it is simply regenerated
next session. The loss window is at most the backup interval (3–5 min, about one
track).

### 10.2 Why not use `generate.py --out-dir` resume directly?

`generate.py` skips a take only when the **WAV and `_time.txt` are local**
(`_succeeded`). `backup_to_gcp.py` uploads MP3 by default and excludes WAV, so a
fresh VM would have no WAV and would regenerate everything. Restoring the whole
run dir is exactly the "download it from GCS" chore the user wants to avoid.

Two alternatives, for the record:

| Alternative | Cost | Verdict |
|---|---|---|
| `--audio-upload wav` + restore the run dir | ~25 GB GCS, full download on resume | works, but heavy |
| Modify `generate.py` to accept a sidecar/MP3 as proof and restore metadata | code change in the resume gate | unnecessary for this plan |
| **Pending-set driver (this plan)** | metadata only, ~a few MB | **chosen** |

### 10.3 Flush before a deliberate disconnect

If the user plans to stop, run one final pass and wait for it:

```bash
python3 plumbing/backup_to_gcp.py --once
```

Then disconnect. If the VM dies unexpectedly, do nothing; the last pass is the
recovery point.

---

## 11. Phase 7 — final audit and collection

When `--status` reports `done=489 pending=0`:

1. **Completeness.** 489 rows, no missing names, no duplicates.
2. **Recipe audit.** For every session's `batch_manifest.json`, assert one
   unique `style_sha256`, `lora_ar_sha256`, `lora_nar_sha256`, `cot == "full"`,
   and the expected scales (`ar=0.85`, `nar=1.0`). Compare the session
   `input.json` `defaults`/`loras` to manifest 18.
3. **Take audit.** List `truncated: true` / `truncated: maybe`; re-render those
   with an explicit higher cap if needed (one at a time, never `--force` in
   bulk).
4. **Audio audit.** Every MP3 non-zero and > ~100 KB; optional random listen of
   10 tracks.
5. **Publish.** Write
   `outputs/YT500/generation/generation_index.jsonl` with one row per song:
   name, title, artist, video_id, source rank, score hashes, session run, seed,
   status, duration, `truncated`, MP3 URI, WAV URI (if production).
   Mirror it to
   `gs://akbar-december-2024-backup/GENERATION/YT500_INSTRUMENTAL/generation_index.jsonl`.
6. **Optional WAV masters.** `python3 plumbing/mark_production.py out/<run> --all`
   before a backup pass, if the corpus is accepted. That is ~25 GB.

---

## 12. Failure handling

| Symptom | Action |
|---|---|
| VM dies mid-song | relaunch the §10 command; the in-flight song is pending again |
| Backup lag / no marker for a finished song | one extra regeneration; acceptable |
| Two VMs running | stop one. There is no cross-VM lock; the done-set is only as fresh as the last backup pass |
| Disk under ~30 GB | stop, run `backup_to_gcp.py --once`, remove local `out/<old-run>` (already backed up), resume |
| OOM / driver crash | check `nvidia-smi`; lower nothing in the recipe; resume. The 3B GGUF fits an A100 comfortably |
| A take sings | inspect the converter report; the score was not fully instrumentalized. Do not retry with `--force` blindly |
| Truncated take | re-render that song with an explicit `cap` from its nominal length + 60 s |
| `gsutil` missing | the daemon cannot run; install `gsutil` (Colab usually has it) |
| GCS auth expired | `gcloud auth login` is interactive; ask the user, do not block the chat |
| Score hash mismatch on resume | the corpus bundle changed or is stale; re-run `--fetch --verify`; do not skip the track |
| Append-only conflict | the driver never overwrites; a conflict means a manual/mixed run. Stop and report |

---

## 13. Code changes and tests

New files:

| File | Purpose |
|---|---|
| `plumbing/yt500_generation_corpus.py` | build / fetch / verify the 489-score corpus and manifest |
| `plumbing/run_yt500_generation.py` | GCS done-set scanner, pending manifest/request writer, detached session driver; `--status`/`--plan-only`/`--max-songs`, and `--batch`/`--batch-chunk` for the A100 fast path |
| `docs/plans/yt500-instrumental-generation.md` | this plan |
| `manifests/yt500_instrumental_489.json` | generated; committed |
| `outputs/YT500/generation/index.json` + `exclusions.json` | generated audit; committed if small |

No change is needed to `run_one.sh`, `instrumentalize_scores.py` or
`backup_to_gcp.py`. The batch path needs two small code additions:

1. `generate.py --requests-out PATH`: run the existing resolution and manifest
   write, dump the request list, exit without a GPU. This is the only change to
   an existing script, and it does not alter the normal generation path.
2. `plumbing/run_yt500_generation.py --batch`: consume the request list, invoke
   `audiocpp_cli --request-sequence`, and write the per-take `_time.txt` and
   sidecar that `run_one.sh` would have written.

`.gitignore` additions:

```
/scores/yt500_src/
/scores/yt500_instrumental/
/work/yt500_gen/
```

Tests (pure Python, no GPU):

- corpus builder: 489 ready, 4 `no-abc`, 2 inline-key, 3 key-normalized, unique names,
  reference defaults equal to manifest 18;
- every ready score has a section tag and a parsed duration;
- done-set parser: a synthetic run with 2 ok and 1 failed marker → 2 done;
- score-hash mismatch → not done;
- `--plan-only` excludes done names and never emits `--force`;
- batch request writer: one request per pending take, stable `<name>_<seed>` ids,
  `style`/`cot`/`semantic_max_tokens`/`abc_file` present, LoRAs only as session
  options;
- batch marker writer: a completed WAV produces `_time.txt` + sidecar, and the
  done-set parser counts it.

Run:

```bash
python3 -m pytest tests/test_yt500_generation_corpus.py \
  tests/test_run_yt500_generation.py -q
python3 generate.py manifests/yt500_instrumental_489.json --dry-run
```

### 13.1 Implementation status (2026-11-10)

Done on CPU and pushed:

- `plumbing/yt500_generation_corpus.py` builds, verifies, uploads and fetches
  the corpus. `--build --upload` produced the bundle at
  `gs://akbar-december-2024-backup/GENERATION/YT500_INSTRUMENTAL/`.
- `manifests/yt500_instrumental_489.json`: 489 songs, exact manifest-18
  `defaults`/`loras`, no per-song caps.
- `outputs/YT500/generation/index.json`: 495 rows (489 ready, 4 no-abc,
  2 inline-key).
- `plumbing/run_yt500_generation.py`: GCS done-set scan, session manifest,
  per-track fallback, `--batch`/`--batch-chunk`, marker writer.
- `generate.py --requests-out`: request-list generation without inference.
- Offline gates: `--fetch` + `--verify` = 489/489; `generate.py --dry-run` =
  489 songs, 0 unparsed, 489 `cot=full`; full test suite 137 passed.

Still A100-only: `--request-sequence` presence, the 4-track A/B, the 12-track
stability pilot, and the measured decode rate.

---

## 14. Open decisions

1. **Batch or per-track?** Use `--batch` only if the 4-track A/B passes
   (equivalent audio, ≥1.7× faster). Otherwise the per-track fallback is the
   safe default and the plan still resumes correctly.
2. **Batch chunk size.** Start with 50 requests per process; use 0 (one process)
   only if the 12-track stability pilot is clean. Smaller chunks cost more model
   loads but lose less on a crash.
3. **MP3 or WAV masters?** The plan uses the repo's default MP3 trial policy
   (~2.5 GB for 489 tracks). WAV masters are ~25 GB and can be marked later.
4. **The 2 deferred scores.** Leave them out for now, or schedule a manual
   re-spelling pass. They are 0.4% of the corpus.
5. **Pilot size.** 4 A/B + 12 stability tracks is recommended; 24 is also
   reasonable but costs more before the bulk run.
6. **Listening sample.** How many tracks to audition before accepting the
   corpus; 10 stratified by duration/flags is the default.
7. **Where the operator runs the one-time corpus build.** Any machine with
   Python + `gcloud` works; it needs no GPU and uploads the bundle to GCS.

---

## 15. Operator quick reference

```bash
# one-time, any machine (no GPU): build the 489-score bundle and upload it
python3 plumbing/yt500_generation_corpus.py --build --upload

# fresh Colab VM, every session
cd /content/arabmaqamrock && git pull --ff-only
./setup_colab.sh
python3 plumbing/yt500_generation_corpus.py --fetch
python3 plumbing/run_yt500_generation.py --status

# continue, uncapped, detached (batch fast path)
setsid nohup python3 plumbing/run_yt500_generation.py --run --batch \
  --batch-chunk 50 \
  > logs/yt500_gen_$(date +%Y%m%d_%H%M).out 2>&1 < /dev/null &
disown || true

# deliberate disconnect: flush, then close the VM
python3 plumbing/backup_to_gcp.py --once
```
