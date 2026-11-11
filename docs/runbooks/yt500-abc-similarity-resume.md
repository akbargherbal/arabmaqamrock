# YT500 ABC similarity — resume notes

## CURRENT STATE — clean stop for VM shutdown, 2026-11-11T22:02Z

- **317 / 460 verified transcripts**, all pushed and archived:
  local verified == remote `.output.abc` == remote archives == **317**.
- `verify`: total 323 dirs, 317 verified, 317 archives ok, **0 archives bad**.
- **5 failures**, all `no-abc` (recovery attempted, not recoverable):
  `yt500-0208-G8CygooGxFE`, `yt500-0277-89bDyAU6Wfg`,
  `yt500-0329-NlwSdL64lIc`, `yt500-0388-Gst0fsBDOUA`,
  `yt500-0457-Q7c_ExWZDRw`.
- **138 tracks still unprocessed** (the 5 failures will be retried and fail
  again). 1 track was in flight at the stop; it was not published.
- Session 2026-11-11 20:05–22:02Z: 246 new tracks, median **25.9 s/track**
  (13.0–82.8 s), no new failure class beyond `no-abc`.
- GCS dataset prefix: `_STATE.json`/`_PARTIAL.json` accounted **317**,
  `complete: false`, **no `_SUCCESS`** (correct). Analysis prefix holds
  `STABLE.json` from 20:23Z.
- The run was isolated in a git worktree because another agent shared the VM;
  `/content` and that worktree do **not** survive the shutdown. Everything
  needed is in GCS + this branch.

### Resume tomorrow (fresh VM, ~70 min of GPU left for 138 tracks)

```bash
cd /content
git clone https://github.com/akbargherbal/arabmaqamrock.git
cd arabmaqamrock
git checkout feat/yt500-abc-similarity && git pull --ff-only
git log -1 --oneline          # expect this doc's commit or newer

mkdir -p work/yt500_abc logs/yt500_abc /content/yt500/{audio,input,transcripts}
gsutil -q cp gs://akbar-december-2024-backup/DATASET/yt500_instrumental/tracks.jsonl \
  work/yt500_abc/tracks.jsonl
./plumbing/setup_transcribe.sh --cuda          # venv does not survive

# inputs (460 tiny files) + inventory
python3 - <<'PY'
import json,subprocess,os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
rows=[json.loads(l) for l in open("work/yt500_abc/tracks.jsonl") if l.strip()]
d=Path("work/yt500_abc/input"); d.mkdir(parents=True,exist_ok=True)
def one(r):
    n=r["name"]; o=d/f"{n}.input.abc"
    if o.is_file(): return
    t=o.with_suffix(".part")
    subprocess.run(["gsutil","-q","cp",
      f"gs://akbar-december-2024-backup/DATASET/yt500_instrumental/tracks/{n}/score.abc",str(t)],check=True)
    os.replace(t,o)
with ThreadPoolExecutor(max_workers=32) as ex: list(ex.map(one,rows))
PY
python3 plumbing/stage_yt500_transcription.py --inventory-only --force \
  --tracks work/yt500_abc/tracks.jsonl --inputs work/yt500_abc/input \
  --inventory work/yt500_abc/inventory.json

# restore the 317 verified outputs, then stage audio
python3 plumbing/yt500_transcribe_sync.py pull
python3 plumbing/yt500_transcribe_sync.py verify     # expect 317
python3 plumbing/stage_yt500_transcription.py \
  --inventory work/yt500_abc/inventory.json \
  --audio-dir /content/yt500/audio --input-dir /content/yt500/input --skip-size-check

# relaunch exactly one of each (logs + pids)
TARGET=460 TIME_BUDGET=7200 setsid nohup bash -c \
  'exec plumbing/supervise_yt500_transcription.sh' \
  < /dev/null >> logs/yt500_abc/supervisor.log 2>&1 &
echo $! > logs/yt500_abc/supervisor.pid; disown
setsid nohup bash -c 'while true; do
    .venv-sheetsage2/bin/python plumbing/recover_yt500_abc.py --transcripts /content/yt500/transcripts || true
    python3 plumbing/yt500_transcribe_sync.py push || true
    python3 plumbing/publish_yt500_bundle.py dataset --target 460 \
      --failures work/yt500_abc/failures.json || true
    sleep 120; done' < /dev/null >> logs/yt500_abc/push.log 2>&1 &
echo $! > logs/yt500_abc/push.pid; disown
TARGET=437 setsid nohup bash -c 'exec plumbing/watch_and_finalize_yt500.sh' \
  < /dev/null >> logs/yt500_abc/watcher.log 2>&1 &
echo $! > logs/yt500_abc/watcher.pid; disown
```

`transcribe.py` hash-skips the 317 restored tracks, so the run resumes at the
138 unprocessed ones. Then the watcher finalizes at ≥437 (analysis + both
bundles + `_SUCCESS` only when `ok+failed == 460`).

**Do not** delete the remote prefix, `--force` a published track, or publish
`_SUCCESS` before the cohort is accounted for.

---


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
