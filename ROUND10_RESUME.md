# Round 10 — L4 run brief (copy-paste)

**Written:** 2026-11-08
**HEAD at write time:** `3134d8d` (`manifests: adopt h2_maqam style, Fadl Shaker pilot with verified scores`)
**Purpose:** the pilot has 23 of 24 scores; one song (القصة وما فيها) was never
scored, and the 24-song generation has to run detached on the L4 VM while the
user listens next session.

Paste everything inside the block below into the chat session on the L4 VM.
It is self-contained: state, investigation, transcription, manifest, detached
run, GCS mirror, and what to report back.

---

```text
You are the agent on the L4 VM that already ran this project's rounds 07 and 09.
Repo: /content/arabmaqamrock (git remote: github.com/akbargherbal/arabmaqamrock,
branch main). The user may reply in Arabic; keep repo artifacts in English.

ONE JOB, FOUR PARTS
  A. Find out why one song never got a score (evidence, not a guess).
  B. Produce that score, instrument it, push it.
  C. Launch the 24-song pilot generation fully detached, and make sure its
     outputs reach GCS.
  D. Report back. The user listens to all 24 WAVs next session.

HARD RULES
- Do NOT change defaults.style in any manifest. The adopted line is the round-09
  winner `h2_maqam` (202 chars) and must stay exactly:
  "Arabic instrumental cover, full band ensemble, layered arrangement, clear
   lead melody, continuous accompaniment, rich full production, maqam,
   Middle Eastern scales, no vocals, no singing, no vocal chops"
  If you find a different string, STOP and report it; do not "fix" it.
- Never use or add the LoRA trigger word `arabmaqamrock` (product decision).
- Never commit audio. `out/`, `logs/`, `models/`, `loras/` are gitignored.
- Do not re-transcribe or edit the 23 existing scores; they are frozen.
- The generation must outlive your turn: no foreground runs, no long sleep/poll
  loops. Start it, verify it once, end your turn.

STEP 0 — state
  cd /content/arabmaqamrock
  git fetch && git log --oneline -1 && git status --porcelain
  Expected HEAD: 3134d8d "manifests: adopt h2_maqam style, Fadl Shaker pilot
  with verified scores". Then `git pull --ff-only`. If the tree is dirty, report
  what it is before touching anything.

STEP 1 — environment (report, don't silently repair)
  nvidia-smi --query-gpu=name,memory.total --format=csv
  ls -l bin/audiocpp_cli; ls models/ | head; ls loras/instrumental/
  .venv-sheetsage2/bin/python -c "import torch,transformers;print(torch.__version__, transformers.__version__)"
  ./transcribe.sh --doctor

STEP 2 — why is the 24th score missing?
  Source set: gs://akbar-december-2024-backup/DISCOGRAPHY/fadhl_shaker_selected
  (24 CD-rip mp3s, ~258 kbps). The repo has 23 raw transcriptions in
  scores/fadhl_shaker/ and 23 surgically converted scores in
  scores/fadhl_shaker_instrumental/ (each with a reports/*.json).

  Missing song:  القصة وما فيها  (video qcpbb4sFyY4, 319.0 s).
  This is verified, not assumed: all 23 score durations (reports/*.json
  nominal_seconds) match the manifest durations to within 5.83 s, and this one
  matches nothing.

  Look for evidence of a prior attempt before concluding anything:
    - any transcript dir, transcribe_manifest.json, _timings.csv, *_driver.log
      under out/, logs/, scores/, /tmp, or the user's home
    - any GCS object under gs://akbar-december-2024-backup/arabmaqamrock/runs/
      whose name suggests a transcription pass
    - shell history or notebook cells mentioning the filename, if present
  Candidate causes to check, in this order: never attempted / download or decode
  error (mp3, Unicode filename) / model-load error / OOM / per-track timeout /
  output collision. Report the file and line that proves it. If there is no
  trace, say exactly that: "no prior attempt found".

STEP 3 — transcribe it
  mkdir -p /tmp/fadl_qissa
  gsutil cp "gs://akbar-december-2024-backup/DISCOGRAPHY/fadhl_shaker_selected/القصة وما فيها.mp3" /tmp/fadl_qissa/
  ffprobe -v error -show_entries format=duration,bit_rate /tmp/fadl_qissa/*.mp3
  ./transcribe.sh /tmp/fadl_qissa --full --device cuda --out-dir /tmp/fadl_qissa_out

  `--full` is mandatory. The default `--melody-only` drops chord symbols, and
  the production pipeline needs them (chords lost = a worse score; that variant
  was already tested and rejected in round 05).
  If CUDA transcription errors, retry once with `--device cpu` (4-6 min, fine).
  Then sanity-check before using it: duration near 319 s, key/tempo present,
  a plausible number of melody notes, no empty score. If it is degenerate, stop
  and report instead of generating from it.
  Copy the accepted score to: scores/fadhl_shaker/al_qissa_wama_fiha.abc

STEP 4 — instrumental surgery
  python3 plumbing/instrumentalize_scores.py \
      scores/fadhl_shaker/al_qissa_wama_fiha.abc \
      --out-dir scores/fadhl_shaker_instrumental
  Verify in scores/fadhl_shaker_instrumental/reports/al_qissa_wama_fiha.json:
  vocal_notes_after == 0, chords == "preserved", meter/tempo preserved. The new
  .abc must have both a V: Ins staff and a V: Vocal staff carrying chord symbols.

STEP 5 — complete the manifest
  Rename manifests/fadhl_shaker_instrumental_10_pilot23.json -> ..._10_pilot24.json
  (and the matching .md), so the name matches the content.
  Add the score alias and one song entry:
    name al_qissa_wama_fiha, seed 20261106, lyrics "[instrumental]",
    score al_qissa_wama_fiha, cap = ceil(score_s * 25) + 250
  Compute the cap from the dry-run's "score_s -> frames, cap, headroom" line and
  keep headroom >= 250. `[instrumental]` has no Arabic letters, so the automatic
  cap falls back to 110 s and would halve the song — the explicit cap is
  mandatory for every song in this manifest.
  python3 generate.py manifests/fadhl_shaker_instrumental_10_pilot24.json --dry-run
  Expect: 24 songs / 24 tracks, no cap warnings.

STEP 6 — commit and push (small files only)
  git add scores/fadhl_shaker/al_qissa_wama_fiha.abc \
          scores/fadhl_shaker_instrumental/al_qissa_wama_fiha.abc \
          scores/fadhl_shaker_instrumental/reports/al_qissa_wama_fiha.json \
          manifests/fadhl_shaker_instrumental_10_pilot24.json \
          manifests/fadhl_shaker_instrumental_10_pilot24.md
  git commit -m "scores: add al_qissa_wama_fiha; pilot is 24 songs"
  git push origin main

STEP 7 — launch the generation detached (this is the point)
  cd /content/arabmaqamrock && mkdir -p logs
  setsid nohup bash -c '
    cd /content/arabmaqamrock
    python3 generate.py manifests/fadhl_shaker_instrumental_10_pilot24.json \
      --label fadhl_inst_10_pilot24
    echo "exit=$? $(date -Is)" >> logs/run10_done.txt
    python3 plumbing/backup_to_gcp.py --once >> logs/backup.out 2>&1
    echo "wavs=$(ls $(cat out/latest)/*.wav 2>/dev/null | wc -l)" >> logs/run10_done.txt
  ' > logs/run10.out 2>&1 < /dev/null &
  disown || true

  Then start the 5-minute mirror so partial takes are safe:
  setsid nohup python3 plumbing/backup_to_gcp.py --interval-minutes 5 \
      >> logs/backup.out 2>&1 < /dev/null &
  disown || true

  One liveness check after ~60 s only: `ps -o pid,etime,cmd -p $(pgrep -f
  generate.py | head -1)` and confirm out/latest/batch_manifest.json exists.
  Then stop. Do not wait for the run.

STEP 8 — report in chat
  - Why the 24th score was missing: evidence, or "no prior attempt found".
  - The new score: duration, key, tempo, note count, and the report fields.
  - Dry-run: 24 tracks, projected time. On this L4 budget ~200 s/track, so
    expect roughly 80-90 minutes for 24 takes.
  - PID, log path (logs/run10.out), run dir (out/latest), and the completion
    marker (logs/run10_done.txt).
  - The GCS prefix where the WAVs will land:
    gs://akbar-december-2024-backup/arabmaqamrock/runs/<run dir>/
  - Anything abnormal you saw in step 1/2.

TRAPS
- Resume is safe: re-running generate.py with the same --out-dir skips a take
  only when the WAV is non-empty AND its _time.txt says "Exit status: 0". If you
  must restart, use --out-dir out/latest's target, never a fresh directory.
- Do not add "busy instrumentation" or "no empty space" back into the style.
  Round 09 measured them as harmful (a 94.8 % -> 85.2 % occupancy drop when
  removed alone, but the words were also what forced `g2`'s dark, squashed mix).
- Do not use `[intro]/[verse]/[chorus]` lyrics; that pushes the model toward
  electronic pop and was rejected in round 07.
- If the GPU is busy with another process, report it instead of killing it.
```

---

## Why the three constraints in that brief matter

1. **`--full` in transcription.** The default `--melody-only` drops chord
   symbols. The no-chords variant was already tested in round 05 and lost, so a
   `--melody-only` score would quietly produce a worse track.
2. **An explicit `cap` per song.** `lyrics: "[instrumental]"` has no Arabic
   letters, so the automatic duration cap falls back to 110 s and would cut every
   song in half. `cap = ceil(score_s * 25) + 250`.
3. **Detachment.** `setsid nohup … & disown`, a log, a completion marker
   (`logs/run10_done.txt`), and a 5-minute GCS mirror. The run must survive the
   chat session ending.
