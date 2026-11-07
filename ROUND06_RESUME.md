# Round 06 handoff — resume here

**Written:** 2026-11-07 16:35 UTC
**Purpose:** The VM was disconnected on purpose after Phase A take 3 of 4.
This file is the exact state and the next commands. Read this first, then
continue.

Do **not** restart Phase A from scratch unless the outputs below are missing:
`p0`, `p1`, `p2` are finished and backed up, and only `p3` is missing.

---

## TL;DR

| Item | State |
|---|---|
| Repo | `/content/arabmaqamrock`, branch `main`, HEAD `4228519` |
| Phase A | **3 of 4 done** (`p0`, `p1`, `p2`); `p3` was killed ~1 min after start |
| Next step | finish `p3` only, then **stop** and let the user pick the best NAR |
| Phase B | **not started** — only after the user's NAR choice |
| GPU | stopped, no `generate.py`/`audiocpp_cli` processes running |
| Outputs | `out/20261107-160423_fadhl_inst_06_nar/` (local) + GCS backup |
| Code changes | none this session; only this doc is added |

---

## 1. What was verified before Phase A

Repo updated with `git pull` to:

```
4228519 manifests: add round 06 NAR/structure polish for habeetak
```

NAR v9 downloaded (was absent):

```bash
mkdir -p loras/nar
hf download Mothersuperior/yue2-mothersuperior-realaudio-tokenizer-v4 \
  nar_lora_joint_v9.bf16.safetensors --local-dir loras/nar
```

- Path: `loras/nar/nar_lora_joint_v9.bf16.safetensors`
- Size: 70,301,896 bytes
- sha256: `ce57f98e9e0e65c724c2a00aa23dea2568952590504a428c588d82f00bc61c55`
  (matches `setup_colab.sh`)

Adapter checks:

```
AR  loras/instrumental/ar_lora_inst_v3abc.bf16.safetensors
    392 tensors, 28 layers, rank 64, kind ar -> OK
    metadata: intended_cot=full, rank=64, base_model=m-a-p/YuE2-3B
NAR loras/nar/nar_lora_joint_v9.bf16.safetensors
    396 tensors, 28 layers, rank 32, kind nar -> OK
    metadata: rank=32, pair_with=tokenizer_head_joint_v9
```

Dry-run of the manifest: **7 songs / 7 tracks**, all `cot=full`,
`cap=6993` (6743 required frames, 250 headroom), score sha `792718a7`,
controls `ar=1 nar=0 / ar=1 nar=1 / ar=1 nar=0.5 / ar=1 nar=0.3 / ...`.

The dry-run printed a harmless warning for every track:
`lyrics contain no Arabic letters; the auto cap falls back to the quantile
floor`. That is expected for `[instrumental]` / section-only lyrics.

---

## 2. Phase A — exact state

Run dir:

```
/content/arabmaqamrock/out/20261107-160423_fadhl_inst_06_nar/
```

Command used:

```bash
python3 generate.py manifests/fadhl_shaker_instrumental_06_habeetak_polish.json \
  --limit 4 --label fadhl_inst_06_nar
```

| # | Take | NAR / scale | status | wall | WAV duration | semantic tokens | truncated |
|---|---|---|---|---|---|---|---|
| 1 | `p0_m3_baseline` | arabmaqamrock / 0.0 | ok, exit 0 | 8:36 | 266.279 s | 6657 | false |
| 2 | `p1_nar_v9_100` | v9 / 1.0 | ok, exit 0 | 10:01 | 266.279 s | 6657 | false |
| 3 | `p2_nar_v9_050` | v9 / 0.5 | ok, exit 0 | 10:03 | 266.279 s | 6657 | false |
| 4 | `p3_nar_arab_030` | arabmaqamrock / 0.3 | **aborted by hand** | ~1 min | — | — | — |

WAV paths:

```
out/20261107-160423_fadhl_inst_06_nar/p0_m3_baseline_20261106.wav
out/20261107-160423_fadhl_inst_06_nar/p1_nar_v9_100_20261106.wav
out/20261107-160423_fadhl_inst_06_nar/p2_nar_v9_050_20261106.wav
```

WAV sha256:

```
p0  cb0fcb284085620f68f7ef8ed31fdd750f59642bc896191793f1e15c51068696
p1  6a08a42fa42c64ada131dc56625f82e42097066584a6b0a170ac06a7b87f7ac2
p2  38cc6bab9393003cba3d09e68a267f7e207183487796a8adab8fc1fa6eb05cfc
```

**Important:** `p0`'s WAV hash is byte-identical to round 05
`m3_full_lora100` (`cb0fcb28…`). The baseline is reproducible.

All three have the **same 6657 semantic tokens and 266.279 s**. That is
expected: the AR stage (score, surgery, AR LoRA, seed, cap, `cot=full`) is
identical; only the NAR decoder differs, so the takes differ in timbre /
production, not in note plan. Judge them by ear, not by duration.

`p3` was killed deliberately to free the GPU before the VM disconnect. It had
just started model loading, so there is no audio.

### p3 partial files (safe to leave, but clean if resuming misbehaves)

```
p3_nar_arab_030_20261106.json       (status: "started")
p3_nar_arab_030_20261106.log        (startup only)
p3_nar_arab_030_20261106_gpu.csv
p3_nar_arab_030_20261106_time.txt   (0 bytes)
scores/p3_nar_arab_030.abc          (valid; generated in dry-run/plan)
```

There is **no** `p3_nar_arab_030_20261106.wav`.

Resume is automatic: `generate.py` skips a take only when the WAV is non-empty
**and** `_time.txt` contains `Exit status: 0`. `p3` has neither, so it will
re-run. If a skip is ever reported wrongly, delete the four `p3_*` sidecars
(not the score) and run again.

---

## 3. Backups (the VM may be reclaimed)

The background backup daemon mirrored `out/` and `logs/` before shutdown:

```
gs://akbar-december-2024-backup/arabmaqamrock/runs/20261107-160423_fadhl_inst_06_nar/
```

At shutdown, 23 objects / 146.37 MiB were present, including all three WAVs
(`p0` uploaded 16:14, `p1` 16:23, `p2` 16:35) plus sidecars/logs/GPU CSVs.

Restore after a fresh clone / new VM:

```bash
cd /content/arabmaqamrock
mkdir -p out
gsutil -m rsync -r \
  gs://akbar-december-2024-backup/arabmaqamrock/runs/20261107-160423_fadhl_inst_06_nar \
  out/20261107-160423_fadhl_inst_06_nar
```

If a local download is wanted for listening, a partial zip was also created at:

```
out/20261107-160423_fadhl_inst_06_nar/phaseA_partial.zip   (133 MB)
```

It contains `p0`, `p1`, `p2` WAV + JSON + LOG. It will be picked up by the next
backup pass if it was created after the last sync.

If both local `out/` and GCS are unavailable, re-running Phase A costs about
35–40 minutes on the T4 (p0 8:36, p1 10:01, p2 10:03, p3 ~10:00).

---

## 4. Resume procedure

### Step 0 — environment

```bash
cd /content/arabmaqamrock
git pull
git log -1 --oneline          # expect 4228519 or newer
./setup_colab.sh              # installs/verifies GGUF, AR LoRA, NAR v9
```

If `setup_colab.sh` is not desired, at minimum re-run the two adapter checks:

```bash
python3 plumbing/check_lora.py \
  loras/instrumental/ar_lora_inst_v3abc.bf16.safetensors --kind ar --expect-rank 64
python3 plumbing/check_lora.py \
  loras/nar/nar_lora_joint_v9.bf16.safetensors --kind nar --expect-rank 32
```

Expected: `392 tensors, 28 layers, rank 64` and `396 tensors, 28 layers,
rank 32`, both `OK`.

### Step 1 — finish Phase A (only p3)

```bash
python3 generate.py manifests/fadhl_shaker_instrumental_06_habeetak_polish.json \
  --limit 4 --label fadhl_inst_06_nar
```

`p0`, `p1`, `p2` will be skipped (or restored from GCS first, see section 3).
Only `p3_nar_arab_030` runs (~10 min). Then **stop** and report:

- WAV path, duration, `truncated` from the sidecar/log, any errors.

### Step 2 — user listens and picks the NAR

Order: `p0` (reference) -> `p1` vs `p2` vs `p3` (which NAR gives the best
production/timbre). Do not run Phase B until the user chooses.

### Step 3 — Phase B (only after the choice)

```bash
python3 generate.py manifests/fadhl_shaker_instrumental_06_habeetak_polish.json \
  --label fadhl_inst_06_polish
```

The full manifest is 7 tracks; `p0`–`p3` are skipped, so `p4`–`p6` run
(~30 min):

| Take | NAR | Lyrics | Style | Steps |
|---|---|---|---|---|
| `p4_nar_v9_100_sections_style` | v9 @ 1.0 | section tags | compact tags | default |
| `p5_nar_v9_050_sections_style` | v9 @ 0.5 | section tags | compact tags | default |
| `p6_nar_v9_100_sections_style_steps32` | v9 @ 1.0 | section tags | compact tags | 32 |

Section plan used by `p4`–`p6`:

```
[intro]
[verse]
[chorus]
[instrumental]
[verse]
[chorus]
[instrumental]
```

**If the user picks the Arabic NAR at 0.3 (`p3`) instead of v9:** do **not**
edit the manifest. Report back; a separate manifest must be made for
`p4`–`p6` with the Arabic NAR. The current `p4`–`p6` entries use
`instrumental_v9` and will ignore an Arabic-NAR choice.

### Step 4 — delivery

For every take report: WAV path, duration, `truncated`, errors. Then:

```bash
cd out/<run_dir>
zip -r /content/habeetak_round06.zip *.wav *.json *.log
```

No `git push` is needed for the WAVs (they are local/GCS); the manifest is
already pushed.

---

## 5. Constraints that still apply

- No ACE-Step.
- No Demucs (so no automatic vocal detection; judge vocals by ear).
- Do not change the score, the Vocal -> Ins surgery, or `cot=full`.
- NAR v9 contains 4 full replacement weights for `vae2llm` / `llm2vae` that
  are **not** scaled by `lora_nar_scale`. Never load NAR v9 at scale 0 and
  expect the stock decoder. `p0`/`p3` intentionally use the Arabic NAR.
- Never run the base model without the instrumental AR LoRA.
- Do not silently lower settings after a failure; report the log.
- Do not reuse round-04/05 manifests or scores for this round.

---

## 6. Gotchas / notes

- **Truncation:** cap `6993` = 279.3 s; the score is 269.7 s, only 250 frames
  of headroom. Check `yue2.semantic.truncated` in each log. If a take is
  truncated, raise caps to `7493` or `7993` in a new manifest (do not edit the
  current one silently).
- **All Phase A takes stop at 6657 tokens / 266.279 s**, not at the score end.
  That is the model's stop, not truncation; the flag is `0` in all three logs.
- **p0 baseline:** NAR alias `instrumental` (Arabic NAR at scale 0). Do not
  confuse it with `instrumental_v9`.
- **Style:** `p0`–`p3` use the long prose caption (1343 chars); `p4`–`p6` use
  the 182-char compact tag string. That is intentional (isolates the style
  lever to Phase B).
- `num_inference_steps` flows through `generate.py` as the `steps` control; only
  `p6` sets it to 32.
- Logs: `logs/round06_phaseA.log` is the batch driver log; per-take logs are in
  the run dir.
- Backup daemon: `plumbing/backup_to_gcp.py`, every 5 min, prefix
  `gs://akbar-december-2024-backup/arabmaqamrock/`. Its log is
  `logs/gcp_backup.log`.

---

## 7. Command cheat sheet

```bash
# status
cd /content/arabmaqamrock
git log -1 --oneline
ls out/20261107-160423_fadhl_inst_06_nar/*.wav
grep -E '^\[[0-9]+/4\]' logs/round06_phaseA.log

# finish Phase A (p3 only; p0-p2 skip)
python3 generate.py manifests/fadhl_shaker_instrumental_06_habeetak_polish.json \
  --limit 4 --label fadhl_inst_06_nar

# Phase B (after the user's NAR choice)
python3 generate.py manifests/fadhl_shaker_instrumental_06_habeetak_polish.json \
  --label fadhl_inst_06_polish

# truncation check
grep -H 'semantic.truncated\|semantic.tokens' \
  out/<run_dir>/*_20261106.log

# durations
for w in out/<run_dir>/*.wav; do
  ffprobe -v error -show_entries format=duration -of csv=p=0 "$w"
done
```

---

## 8. Listening order for the user

1. `p0_m3_baseline` — the known-good M3 reference.
2. `p1` vs `p2` vs `p3` — pick the best NAR (production/timbre; vocals must
   stay absent).
3. `p4` vs `p5` — section tags + compact style on the winning NAR.
4. `p6` — same as `p4` but 32 ODE steps.

Judge: melody clarity, arrangement density/glue, no vocals, no looping, and
whether the ending is complete (not truncated).
