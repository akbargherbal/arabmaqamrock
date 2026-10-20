# RESTORE — Baghdad Moon B token surgery (start here on a fresh runtime)

Everything the next session needs is in **GCS** and **GitHub**. This page is the
one-shot restore + "what to do first".

GCS root:
`gs://akbar-december-2024-backup/arabmaqamrock/runs/20261019_baghdad_moon_token_surgery/`

GitHub docs (tracked):
`docs/happy_accidents/Baghdad_Moon/token_surgery/`

Last verified: 2026-10-20 ~05:10 UTC, from a CPU-only Colab runtime that is about
to be discarded.

> **2026-10-20 ~06:55 UTC — execution is past this runbook.** The T4 session
> restored everything, passed both §7.1 gates exactly, rendered all 13 splices,
> built the local-comp hybrids and handed the listening pack to the user.
> **Current state and next steps: `CHECKPOINT.md` in this folder.**

---

## 1. What is already done (do not redo)

| item | state | where |
|---|---|---|
| baseline semantic, 5397 frames | **exact**, sha256 `1b1aa3e2…` | GCS `baseline/semantic.json` |
| A / C donor semantic | done, 5874 / 6192 frames | GCS `variants/{A,C}_semantic.json` |
| exact lyrics + style | sha256 `7bd3b6e1…` / `248af8e7…` | GCS `prompts/` |
| prefix-capable sm75 binary | **built**, sha256 `4e1534f3…` | GCS `bin/audiocpp_cli_prefix_sm75` |
| patched source diff | saved (code + full) | GCS `patches/` |
| splice token files (13 variants, all 5397) | **pre-computed** | GCS `tokens/` |
| evaluation scripts | **reconstructed** (see §5) | GCS `scripts/` + repo |
| GPU smoke test + §7.1 baseline | **done, both exact** (2026-10-20) | GCS `gates/` |
| 13 candidate renders + local comps | **done** | GCS `candidates/v2/` |
| listening pack + Arabic scorecard | **done, awaiting user** | GCS `deliverables/` |

---

## 2. Restore on the T4

```bash
# 0. repo
cd /content && git clone https://github.com/akbargherbal/arabmaqamrock.git 2>/dev/null || true
cd /content/arabmaqamrock && git pull --ff-only

# 1. model + VAE + LoRAs (downloads, verifies hashes)
./setup_colab.sh          # or ./install.sh

# 2. the prefix-capable binary
B=gs://akbar-december-2024-backup/arabmaqamrock/runs/20261019_baghdad_moon_token_surgery
mkdir -p bin
gsutil cp $B/bin/audiocpp_cli_prefix_sm75      bin/
gsutil cp $B/bin/audiocpp_cli_prefix_sm75.sha256 bin/
cd bin && sha256sum -c audiocpp_cli_prefix_sm75.sha256   # must say OK (4e1534f3…)
mv audiocpp_cli_prefix_sm75 audiocpp_cli_prefix && chmod +x audiocpp_cli_prefix
cd /content/arabmaqamrock && . ./cuda_loader_path.sh
./bin/audiocpp_cli_prefix --version                      # expect git: 58caf774
strings ./bin/audiocpp_cli_prefix | grep semantic_prefix  # expect the option names

# 3. workspace: prompts, baseline semantic, A/C, tokens, scripts
mkdir -p happy_accident
gsutil -m cp -r $B/workspace/happy_accident/* happy_accident/   # if present
# otherwise the individual pieces:
#   gsutil -m cp -r $B/prompts $B/baseline $B/variants $B/tokens $B/scripts happy_accident/
```

Rebuild the local layout if you copied pieces rather than the tarball:

```bash
cd /content/arabmaqamrock/happy_accident
mkdir -p prompts runs/baseline_semantic runs/variants_semantic/A_4161609852 \
         runs/variants_semantic/C_927142839 runs/token_surgery/tokens backup/patches
mv prompts/02B_*.txt prompts/ 2>/dev/null || true
mv baseline/semantic.json runs/baseline_semantic/semantic.json
mv baseline/run.log      runs/baseline_semantic/run.log
mv variants/A_semantic.json runs/variants_semantic/A_4161609852/semantic.json
mv variants/C_semantic.json runs/variants_semantic/C_927142839/semantic.json
mv variants/run.log          runs/variants_semantic/run.log
mv tokens/* runs/token_surgery/tokens/
mv scripts/* . 2>/dev/null || true
```

Fastest path: the whole small workspace (no audio) is in
`$B/workspace/happy_accident_workspace.tar.gz` (~200 KB). Just:

```bash
cd /content/arabmaqamrock
gsutil cp $B/workspace/happy_accident_workspace.tar.gz /tmp/
tar -xzf /tmp/happy_accident_workspace.tar.gz -C /content/arabmaqamrock
```

The original B WAV and the A/C variant WAVs stay in the render bucket:

```
gs://akbar-december-2024-backup/arabmaqamrock/runs/20261018-162827_batch_12_variants_backing_vocals/
  02-…-B_1712905618.wav   (sha256 dbc00722…)
  02-…-A_4161609852.wav
  02-…-C_927142839.wav
```

Fetch the B WAV (and optionally A/C) into `happy_accident/original/` and
`happy_accident/variants/`; demucs stems are cheap to regenerate.

---

## 3. First thing on the T4 — HANDOFF §7.1

Do not touch token Surgery until both checks pass.

```bash
cd /content/arabmaqamrock && . ./cuda_loader_path.sh
BIN=./bin/audiocpp_cli_prefix
OUT=happy_accident/runs/baseline_audio_check && mkdir -p "$OUT"

# 3a. semantic-only re-run (no prefix) -> must equal 1b1aa3e2…, 5397 frames, 1079/12
#     (see HANDOFF §7.1 step 2; reuse the §8 template with stop_after=semantic)
# 3b. full baseline from the exact token stream -> must equal dbc00722…
$BIN --task gen --family yue2 --model models/Yue2-3B-GGUF --backend cuda --threads 8 \
  --session-option yue2.model_gguf=yue2-3b-bf16.gguf \
  --session-option yue2.vae_gguf=yue2-vae-f16.gguf \
  --session-option yue2.ar_lora=/content/arabmaqamrock/loras/arabmaqamrock-v3-ar.safetensors \
  --session-option yue2.ar_lora_scale=1.0 \
  --session-option yue2.nar_lora=/content/arabmaqamrock/loras/arabmaqamrock-v3-nar.safetensors \
  --session-option yue2.nar_lora_scale=1.0 \
  --session-option yue2.attention=flash \
  --lyrics "$(cat happy_accident/prompts/02B_lyrics.txt)" \
  --request-option style="$(cat happy_accident/prompts/02B_style.txt)" \
  --request-option cot=off \
  --request-option semantic_prefix_file=/content/arabmaqamrock/happy_accident/runs/token_surgery/tokens/tokens_baseline.json \
  --request-option semantic_min_tokens=5397 \
  --request-option semantic_max_tokens=5397 \
  --seed 1712905618 \
  --out "$OUT/baseline.wav" --out-dir "$OUT/artifacts" --log
sha256sum "$OUT/baseline.wav"     # expect dbc00722534d5ee763ae54a048cd704eaa4c927e37834cd54542eaf379e0de42
```

If it is not `dbc00722…`: stop, record the actual hash, and report. The build
used CUDA 12.0.140 + gcc 12.4.0 (same toolkit as the original prebuilt), so a
mismatch would point at something else (driver/cuBLAS version, arch flags).

---

## 4. Then render the pre-computed splices

All files in `happy_accident/runs/token_surgery/tokens/` are exactly 5397 frames
and are drop-in for `semantic_prefix_file` + `min=max=5397`.

| file | change | changed frames |
|---|---|---|
| `tokens_e1_A_note.json` | e1 final 8 frames from B Outro | 7 |
| `tokens_e1_B_word.json` | e1 whole 31-frame word from B Outro | 29 |
| `tokens_e1_C_A.json` | e1 from A Verse 2 (15→31 resampled) | 31 |
| `tokens_e1_C_C.json` | e1 from C Verse 2 (16→31 resampled) | 31 |
| `tokens_e2_A_onset.json` | e2 first 13 frames from B Verse 2 | 13 |
| `tokens_e2_A_onset_C.json` | e2 first 13 frames from C Outro | 13 |
| `tokens_e2_A_onset_A.json` | e2 first 13 frames from A Outro | 13 |
| `tokens_e2_B_word.json` | e2 first 26 frames from B Verse 2 | 26 |
| `tokens_combo_e1_A_note__e2_A_onset.json` | e1 note + e2 onset | 20 |
| `tokens_combo_e1_A_note__e2_B_word.json` | e1 note + e2 word | 33 |
| `tokens_combo_e1_B_word__e2_A_onset.json` | e1 word + e2 onset | 42 |
| `tokens_combo_e1_B_word__e2_A_onset_C.json` | e1 word + e2 onset (C) | 42 |
| `tokens_combo_e1_B_word__e2_B_word.json` | e1 word + e2 word | 55 |

`tokens_baseline.json` is the untouched stream (for the §7.1 check) and
`manifest.json` has sha256 + changed-frame ranges for every file.

Batch them with `--request-sequence` (HANDOFF §8) to pay the load cost once.
Evaluate with:

```bash
python3 happy_accident/evaluate.py happy_accident/runs/token_surgery/v2/<id>.wav
```

Still open after that: §7.2 D (AR resample of e1) and §7.3 C (tail resample from
frame 5056 with a seed sweep) — those need the GPU.

---

## 5. Honest status notes

- **The binary has now run on the T4** (2026-10-20). Both §7.1 gates passed:
  semantic byte-identical `1b1aa3e2…`; full WAV bit-identical `dbc00722…`.
- `evaluate.py`, `align.py`, `asr2.py` are **reconstructions**. They have now
  been run on audio. Two real bugs were found and fixed: `evaluate.py` compared
  the reference full mix against the candidate's vocal stem (now full-mix vs
  full-mix), and both scripts used the pre-transformers-v5 processor call (now
  `audio=`, with a fallback). Their numbers are comparable across candidates
  rendered in the same session, but are not a continuation of any earlier
  numeric series. CTC is not reliable at single-consonant resolution; see
  `report.md` §2 and `APPROACH.md`.
- The build's local commit is `58caf774`, not the `42bb0a88` named in older
  notes; the code diff is byte-identical to the saved patch.
- 13 candidate WAVs and 13 local comps exist; see `CHECKPOINT.md` §4.
