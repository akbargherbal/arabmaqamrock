# YT500 instrumental bulk — A100 run notes

Living restart note. Only findings that are hard to rediscover from a fresh VM.
Plan: [`yt500-instrumental-generation.md`](yt500-instrumental-generation.md).
GCS run tree is the source of truth; nothing local must survive.

## State

| Item | Value |
|---|---|
| Corpus | 489 ready (4 `no-abc` + 2 `inline-key` excluded); 158 songs >300 s, 40 >350 s, 6 >400 s |
| Mode | **batch**, `--batch-chunk 50` (deviation from the 1.7× gate — approved) |
| Bulk | launched 2026-11-10T08:58:38Z, supervisor PID 124626: `supervise_yt500_generation.py --mode batch --batch-chunk 50`; **interrupted at 09:37:15Z (SIGTERM, exit 143)** |
| Last GCS state | **22 done / 467 pending**, 3 `*_yt500inst` session runs (12 pilot + 10 bulk) |
| Completion | **not reached**; no `logs/yt500_supervisor_done.txt` was written |
| Backup | daemon every **2 min** (user request; PID 129551), plus `--once` after every chunk session; audio uploaded as MP3 192k |
| Started at HEAD | `2e48cdb`; A100-SXM4-80GB, CC 8.0, UUID `GPU-d4da84f7-5872-e2ec-3273-257b7d7cdb43`; binary sha `78f478…d023` (`sm80-a100`) |
| Pilot | 12/12 `ok`, no crash, durations −7.9%…+15.1% vs score; resume `done=12 pending=477`; batch **1.63×** normalized (3.46 vs 2.12 audio-s per wall-s) |

## What stopped it (2026-11-10)

- The **pilot's first resume check failed** with `done=0` because `gcloud storage ls`
  returns objects, not run folders; every run's metadata was flattened and
  `scan_done` saw no `batch_manifest.json`. Fixed in `ee21fb9` with a regression
  test. After the fix, the 12 pilot tracks count normally.
- The serial bulk launched at 08:58, reached 20 done, and was paused for a
  user-authorized 8-way concurrency trial. The trial was negative (0/64 takes in
  ~8 min; batch-1 decode is latency-bound), so it was stopped and reverted.
- The serial supervisor was relaunched at 09:36:41; at **09:37:15 it received
  SIGTERM (exit 143)** — consistent with the Colab VM being shut down, not a
  generation error. The last backup pass saw `out/` missing, but GCS already
  held the 22 completed takes.
- `exit=143` is not a task failure: relaunch the supervisor and it resumes from
  GCS. Use `--status --work-dir /tmp/yt500_status` while a supervisor is alive.

## Insights worth keeping

1. **Batch is bit-exact.** Batch and per-track WAVs for the same seed had
   identical SHA-256. Batch changes speed only; style/CoT/ABC/LoRA are honored.
   Batch sidecars still carry `abc_sha256`, `cot=full`, `lora_alias`, scales.
2. **Batch saves the model load, nothing else.** ~70 s/song batch vs
   ~114 s/song per-track (each per-track take reloads the model). Measured
   4-track speedup **1.52×**; asymptotic **~1.6×**, not the 1.7× gate.
   At 489 songs: ~9.5–10 h batch vs ~15.5 h per-track.
3. **Length varies with seed; `truncated` does not catch it.** The same 416 s
   score rendered **276 s at seed 1003** and **478 s at seed 1992596191**.
   Early EOS is silent. The 12-track pilot was clean (all within −8%…+15%), so
   this is occasional, not systematic. Post-run action: audit `wav_duration_s`
   vs score and re-render outliers with an explicit cap/seed.
4. **Seeds are random and frozen.** `secrets.randbelow(2**32)`, one take/song,
   written into `batch_manifest.json` and filenames before generation.
   Done-detection is score-hash + `Exit status: 0`, seed-agnostic: finished
   songs are never re-seeded, pending songs get fresh seeds each session.
5. **GPU is compute-saturated, not VRAM-starved.** Median 87% util (p90 99%)
   during takes, mean 49% because of idle seams; peak VRAM 10.6 GB of 82 GB.
   More throughput needs overlapping sessions in the seams, not a bigger model.
   Concurrency is deferred: the driver is serial (`run.lock`, no shard flag).
6. **Resume bug found and fixed here.** `gcloud storage ls <glob>` returns
   *objects*, not run folders. The driver fed those to `sync_meta`, so every
   run's files landed in one flat metadata dir and `scan_done` saw no
   `batch_manifest.json` — a fully uploaded run reported **done=0**. Fixed in
   `list_remote_runs()` (collapse each object to its run prefix) with a
   regression test. If a fresh VM reports `0 session runs` despite GCS having
   runs, check that this fix is in `plumbing/run_yt500_generation.py`.
7. **A/B listening PASS** (user, 2026-11-10). Listening set kept at
   `gs://akbar-december-2024-backup/arabmaqamrock/listen/ab_20261110/`
   with `COMPARE.txt` proving batch == per-track.
8. **Per-take cost is AR decode.** One 270 s take: prefill **1.5 s**, AR decode
   **48.4 s** (6,751 tokens ≈ 139 tok/s), sampling 1.2 s, NAR synth **12.3 s**,
   the rest VAE/export. Decode moves ~3.4 GB of weights per token ≈ 470 GB/s,
   only ~23% of the A100's ~2 TB/s — so it is **latency/occupancy-bound**, not
   bandwidth-bound. That is why 8 parallel processes gave no aggregate gain
   (they share the same SMs) and why the only real levers are batching decode
   across songs (engine has batched KV/attention internally, but only for CFG;
   it is not exposed across requests) or quantized weights. More VRAM/RAM does
   nothing for this.

## Restart

```bash
cd /content/arabmaqamrock && git pull --ff-only
./setup_colab.sh
python3 plumbing/yt500_generation_corpus.py --fetch
python3 plumbing/run_yt500_generation.py --status --work-dir /tmp/yt500_status   # done/pending from GCS
setsid nohup python3 plumbing/supervise_yt500_generation.py \
  --mode batch --batch-chunk 50 \
  > logs/yt500_supervisor.out 2>&1 < /dev/null &
disown || true
```

Never delete runs/scores/objects; never `--force` in bulk. Flush before a
deliberate disconnect: `python3 plumbing/backup_to_gcp.py --once`.

## Concurrency experiment (user-requested, 2026-11-10 09:10Z)

Serial supervisor paused at `done=20 pending=469`. User explicitly authorized an
**8 concurrent sessions** trial and accepted the crash risk in writing
("if it crashes it's me not you"). This is a deliberate deviation from the
serial/one-generator rule, on the user's call.

- 8 disjoint shards × 8 songs = 64 takes; each worker has its own `--work-dir`
  lock, label `conc0..conc7`, `--threads 4`; all write under `out/` so the
  backup daemon still sees them.
- Measures: aggregate throughput vs serial, peak VRAM, per-take `status`,
  duration sanity, crash behaviour.
- Fallback: any OOM, corrupted take or throughput regression → stop all 8,
  verify GCS, restart the serial supervisor.
- Result: **negative — stopped after ~8 min.** All 8 loaded and shared the GPU
  (100% util, 48–57 GB VRAM, no OOM), but **0/64 takes completed** in the time
  serial produced ~5 per worker. Aggregate throughput was flat: batch-1
  autoregressive decode is latency-bound, so concurrent workers time-slice the
  same SMs instead of multiplying them. Parallel model load also cost ~4.5 min
  vs ~30 s for one process. Reverted to the serial supervisor. Do not retry
  concurrency on this model; real speedups would need batched decoding inside
  the engine, quantization, or fewer steps — not more VRAM.

## Speed probes (quality-preserving only)

User constraint: no quality degradation. Probes run on one real request, then
reverted:

- **q8_0 weights** (`--load-option yue2.weight_type=q8_0`): 8,308 tokens in
  123.5 s = **66 tok/s vs 139 tok/s bf16 — 2× slower** (likely on-the-fly
  dequant). Rejected on speed *and* because it changes weights.
- **`mem_saver=0`**: 66 tok/s, but that run overlapped an orphaned second
  driver that had survived an earlier cleanup, so it is **confounded, not a
  validated gain**. Not adopted.
- Lesson: `--status` must use its own `--work-dir` (e.g.
  `--work-dir /tmp/yt500_status`) while the supervisor runs. Two drivers
  sharing `work/yt500_gen/meta` produce `OSError: Directory not empty`.
- Batched decode exists in the binary only for CFG (positive/negative passes);
  there is no CLI knob to batch separate songs. A real multi-x needs engine
  work, not VM resources.
- Conclusion: keep bf16 + serial. ~70 s/take is the honest floor at this
  recipe/quality; the A100 is already ~3× the L4 baseline.

## Open items

- Post-bulk: length audit + outlier re-render; 2-vs-4-worker concurrency
  benchmark to see whether the idle seams are worth ~2× on the next corpus.
- Duration-gate outliers found mid-run (27/457, 6 severe short) are documented
  with names, seeds, caps and GCS paths in
  [yt500-instrumental-quality-audit.md](yt500-instrumental-quality-audit.md);
  the machine-readable list is
  `outputs/YT500/generation/quality_audit_duration.json`.
