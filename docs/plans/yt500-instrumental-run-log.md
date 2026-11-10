# YT500 instrumental bulk — A100 run log

**Living document.** Updated at each checkpoint (preflight, A/B, pilot, bulk
launch, completion). Plan: [`yt500-instrumental-generation.md`](yt500-instrumental-generation.md).
**Last update:** 2026-11-10T08:55Z — 12-track pilot in progress; bulk not yet launched.

This file is the restart point. If the Colab VM dies, read §2 (what is done),
§7 (resume commands) and the plan's §7. The GCS run tree is the source of truth;
nothing local needs to survive.

---

## 1. Run identity

| Item | Value |
|---|---|
| Repo HEAD at start | `2e48cdb` (`gen(yt500): add unattended supervisor for the bulk run`) |
| Working tree | clean |
| GPU | NVIDIA A100-SXM4-80GB, compute cap 8.0, 81920 MiB |
| Host | 12 vCPU, 167 GB RAM, 227 GB free on `/content` |
| Binary | `bin/audiocpp_cli`, sha256 `78f478592acfca17046102b16b25b33adb3763eb8acda14f649a4a4f6dc9d023` |
| Binary tag | `sm80-a100` (verified), `--request-sequence` present in `--help` |
| Auth | `ghurbal.akbar@gmail.com` active |
| Backup daemon | `plumbing/backup_to_gcp.py` running (PID 2821 at start) |
| Corpus | `manifests/yt500_instrumental_489.json` |
| Recipe | `manifests/fadhl_shaker_instrumental_18.json` (style, cot=full, LoRA pair, AR 0.85 / NAR 1.0) |

## 2. Corpus verification

```
verified: 489 songs, 489 scores, hashes, tags and durations OK
corpus 489 | gcs done 0 | pending 489 | mismatches 0
```

Exclusions: 6 total — 4 `no-abc`, 2 `inline_key_change`. Matches the plan.
Corpus duration distribution: median 276 s, min 142 s, max 416 s;
**158 songs >300 s, 40 >350 s, 6 >400 s**.

## 3. A/B pilot — per-track vs batch (4 tracks, explicit seeds 1000–1003)

Tracks: `yt500-0071-UO5jte9NP-U`, `yt500-0136-pUnEijzCb1c`,
`yt500-0504-BWveNYQDmF4`, `yt500-0120-rjw-rOsZMis`.

| | per-track (`out/ab_single`) | batch (`out/20261110-082846_ab_batch`) |
|---|---|---|
| Wall | **7:36** total (2:02, 2:01, 1:23, 2:11) | **300.5 s** chunk (5:24 to last take) |
| Speedup | — | **1.52×** (batch = 65.9% of per-track) |
| Markers | 4/4 `status: ok` | 4/4 `status: ok`, `exit 0` |
| Audio | 4 WAVs | **byte-identical** to per-track (same SHA-256) |

Per-take durations vs score:

| Track | Score | WAV | Delta |
|---|---:|---:|---:|
| yt500-0071 | 288.7 s | 270.0 s | −6.5% |
| yt500-0136 | 282.3 s | 277.7 s | −1.6% |
| yt500-0504 | 142.3 s | 142.1 s | −0.1% |
| yt500-0120 | 415.7 s | 276.4 s | **−33.5%** (seed 1003) |

**Batch sidecar integrity:** `abc_sha256` matches the score
(`3782ad8f…`), `cot=full`, `lora_alias=instrumental_v9`, scales AR 0.85 /
NAR 1.0. Byte-identical WAVs prove style, CoT, ABC and LoRA were not silently
ignored.

**Listening:** user verdict **PASS** (2026-11-10 ~08:46Z), on the listening set
`gs://akbar-december-2024-backup/arabmaqamrock/listen/ab_20261110/`
(4 WAVs + `LISTEN_README.md`, `SHA256SUMS`, `COMPARE.txt`).

### A/B gate outcome

- Correctness: **PASS**.
- Speed: **1.52× vs the 1.7× gate — narrowly missed.** Marginal cost is
  ~70 s/song batch vs ~114 s/song per-track (which reloads the model every
  song), so the asymptotic ratio is ~61% (~1.6×), not 1.7×. At 489 songs that
  is still ~9.5–10 h batch vs ~15.5 h per-track.
- **Decision (user-approved, 2026-11-10):** proceed with **batch**,
  `--batch-chunk 50`, conditional on the 12-track pilot showing 12/12 ok and an
  at-scale speedup ≥1.55×. This is a documented deviation from the 1.7× gate.

## 4. Key findings / insights

1. **Batch is bit-exact, not approximate.** The four batch WAVs have the same
   SHA-256 as the per-track WAVs (`COMPARE.txt` on GCS). Batch changes speed
   only.
2. **The model load is the only thing batch saves.** Per-song decode is similar
   in both modes; per-track pays ~45–60 s of model load per song.
3. **Seeds are random** (`secrets.randbelow(2**32)`, one take per song), drawn
   at session preparation and frozen into `batch_manifest.json` and filenames.
   Done-detection is by score hash + `Exit status: 0`, not by seed, so finished
   songs are never re-seeded and pending songs get fresh seeds per session.
4. **Length is seed-dependent, not a hard ceiling.** The same 416 s score gave
   **276.4 s at seed 1003** (A/B) and **478 s at seed 1992596191** (pilot).
   Early EOS is therefore a per-take risk; it is not caught by `truncated`.
   Post-run action: audit `wav_duration_s` vs score, re-render outliers with an
   explicit cap/seed.
5. **GPU utilization profile:** median 87%, p90 99%, mean 49% (idle seams
   between takes), peak VRAM 10.6 GB of 82 GB. The box is compute-saturated
   while generating; the waste is fixed overhead, not VRAM. Concurrency is
   deferred to a post-bulk benchmark (driver is serial by design; `run.lock`,
   no shard/offset flag).

## 5. 12-track stability pilot + resume round-trip

- Run dir: `out/20261110-083615_yt500inst` (batch, default seeds).
- Gate: 12/12 `status: ok`, no crash, VRAM stable, one failed request must not
  kill the batch.
- Resume round-trip: `backup --once` → move run dir to `/tmp` → `--status`
  must show `done=12 pending=477` → `--plan-only` must not list the 12.
- Result: **pending — filled in at the gate.**
- Note: the pilot included `yt500-0120` again and rendered **478 s** (seed
  `1992596191`), confirming finding 4.

## 6. Bulk launch

- Command:
  ```bash
  python3 plumbing/supervise_yt500_generation.py --mode batch --batch-chunk 50
  ```
- Supervisor log: `logs/yt500_supervisor.out`
- Completion marker: `logs/yt500_supervisor_done.txt` (`exit=0 pending=0`)
- Status JSON: `work/yt500_gen/supervisor_status.json`
- Launch marker: `logs/yt500_bulk_launch.txt`
- **Result: pending.**

## 7. Restart on a fresh VM

```bash
cd /content/arabmaqamrock && git pull --ff-only
./setup_colab.sh
python3 plumbing/yt500_generation_corpus.py --fetch
python3 plumbing/run_yt500_generation.py --status      # done/pending from GCS
setsid nohup python3 plumbing/supervise_yt500_generation.py \
  --mode batch --batch-chunk 50 \
  > logs/yt500_supervisor.out 2>&1 < /dev/null &
disown || true
```

Do not delete runs, scores or remote objects. Never use `--force` in bulk.
Before a deliberate disconnect: `python3 plumbing/backup_to_gcp.py --once`.

## 8. Anomalies / open items

| Item | State |
|---|---|
| Speed gate 1.7× | missed at 1.52×; deviation approved, batch still ~1.6× at scale |
| Short take at seed 1003 (`yt500-0120`, −33.5%) | seed-dependent; same score rendered 478 s at another seed |
| Long-song length audit | required after bulk; re-render outliers with explicit cap |
| Concurrency / VRAM headroom | deferred to a post-bulk 2-vs-4-worker benchmark |
| `ffmpeg`, `gsutil`, auth, disk | all OK at preflight |

## 9. Update log

| UTC | Event |
|---|---|
| 08:20 | `setup_colab.sh` exit=0; all assets staged; backup daemon already running |
| 08:20 | Preflight green: A100 CC 8.0, binary sha match, `--request-sequence` present |
| 08:20 | Corpus verified: 489 songs / 489 scores, 0 done, 0 mismatches |
| 08:21 | A/B per-track leg started |
| 08:28 | A/B per-track leg done: 4/4 ok, 7:36 total |
| 08:34 | A/B batch leg done: 4/4 ok, 300.5 s chunk; 1.52×; WAVs identical |
| 08:36 | 12-track pilot started (`out/20261110-083615_yt500inst`) |
| 08:41 | A/B listening set uploaded to GCS |
| 08:46 | Listening verdict PASS (user) |
| 08:55 | This log created; pilot in progress; bulk auto-launch armed |
