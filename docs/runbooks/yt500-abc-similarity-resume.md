# YT500 ABC similarity — resume notes

Branch: `feat/yt500-abc-similarity`
Durable transcripts: `gs://akbar-december-2024-backup/DATASET/yt500_instrumental_transcripts/`
Analysis products: `gs://akbar-december-2024-backup/ANALYSIS/yt500_instrumental_abc/`
Dataset (read-only): `gs://akbar-december-2024-backup/DATASET/yt500_instrumental/`

## Naming contract (commit 4facb4a)

- `score.abc` exists **only** as the read-only input inside the dataset.
- Local analysis input: `work/yt500_abc/input/<name>.input.abc`
- Local analysis output: `work/yt500_abc/output/<name>.output.abc`
- Published output: `<name>.output.abc` + `<name>.output.meta.json`
  (`role: output_transcript`, `input_sha256`, `audio_sha256`, input/audio URIs)
- Published archive: `archives/<name>.output-transcript.tar.gz`
  (internally keeps transcribe.py's `score.abc`; marked by the archive name
  and the output sidecar).
- `build-pairs` aborts if `input_sha256 == output_sha256`.

## After a VM death

```bash
cd /content/arabmaqamrock
git pull --ff-only
mkdir -p logs/yt500_abc /content/yt500/{audio,input,transcripts}

# 1. CUDA SheetSage2 env (idempotent)
setsid nohup bash -c 'exec ./plumbing/setup_transcribe.sh --cuda > logs/yt500_abc/setup_cuda.log 2>&1' < /dev/null &
echo $! > logs/yt500_abc/setup_cuda.pid; disown

# 2. Inventory (460 sha256 checked)
python3 plumbing/stage_yt500_transcription.py --inventory-only --force \
  --tracks work/yt500_abc/tracks.jsonl --inputs work/yt500_abc/input \
  --inventory work/yt500_abc/inventory.json

# 3. Audio + input scores (byte-exact, resumable, flattened names)
setsid nohup bash -c 'exec python3 plumbing/stage_yt500_transcription.py \
  --inventory work/yt500_abc/inventory.json \
  --audio-dir /content/yt500/audio --input-dir /content/yt500/input \
  --skip-size-check > logs/yt500_abc/stage.log 2>&1' < /dev/null &
echo $! > logs/yt500_abc/stage.pid; disown

# 4. Pull verified flat outputs into transcribe.py's layout
python3 plumbing/yt500_transcribe_sync.py pull

# 5. Resume transcription (hash-skip; no --limit)
setsid nohup bash -c 'exec ./transcribe.sh /content/yt500/audio \
  --out-dir /content/yt500/transcripts --full --device auto --threads 4 \
  --time-budget 7200 > logs/yt500_abc/transcribe.log 2>&1' < /dev/null &
echo $! > logs/yt500_abc/transcribe.pid; disown

# 6. Recovery + verified push loop every 5 minutes
#    (repairs deterministic no-abc exporter edge cases with the model's own
#    exporter; then archives + role-labelled flat mirror + dataset docs)
setsid nohup bash -c 'while true; do .venv-sheetsage2/bin/python plumbing/recover_yt500_abc.py --transcripts /content/yt500/transcripts; python3 plumbing/yt500_transcribe_sync.py push; python3 plumbing/publish_yt500_bundle.py dataset; sleep 300; done \
  > logs/yt500_abc/push.log 2>&1' < /dev/null &
echo $! > logs/yt500_abc/push.pid; disown
```

## Status checks

```bash
grep -c ' ok ' logs/yt500_abc/transcribe.log
tail -n 20 logs/yt500_abc/transcribe.log
ps -o pid,etime,%cpu,%mem,cmd -p "$(cat logs/yt500_abc/transcribe.pid)"
nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv
python3 plumbing/yt500_transcribe_sync.py verify
```

## Phase 3–5 (after >=95% verified)

```bash
python3 analysis/run_yt500_similarity.py run \
  --input-dir work/yt500_abc/input \
  --transcripts /content/yt500/transcripts \
  --inventory work/yt500_abc/inventory.json \
  --out work/yt500_abc/similarity \
  --work work/yt500_abc \
  --audit 30 --permutations 10000 --blocks 256
```

## Known data facts

- All 460 input scores sha256 match `outputs/YT500/generation/index.json`
  (`instrumental_abc_sha256`).
- 4 input scores have zero melody notes (only rests/chords):
  `yt500-0071-UO5jte9NP-U`, `yt500-0378-iMZ1skkbUWI`,
  `yt500-0439-lt_pQqHYZSY`, `yt500-0603-NPqmoCio0Nw`; kept in the cohort and
  flagged `empty-input`.
- Phase 0 self-test on the 460 inputs: identity 1.0, parity 3.68e-7,
  460² matrix 0.09 s.
- Phase 1 probe: 3/3 ok, 34.7/40.2/59.5 s, chords 3/3, duration +0.2–2.2%.
- Probe outputs were published first and seed the bulk run (hash-skipped).
