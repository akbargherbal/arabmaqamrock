# HANDOFF — Baghdad Moon B: token-level repair of two mispronounced words

**This document supersedes `happy_accident.zip` / `agent_prompt_fix_two_words.md`.**
It was written after working the problem on the actual T4 environment. Read this
first; use the Claude prompt only as background.

Last updated: 2026-10-19 ~21:45 UTC (Colab session may be ephemeral).

---

## 0. TL;DR for the next agent

- Goal: re-render `02-استيداع-قمر-بغداد-ولوعة-الوداع-B_1712905618` **as close as
  possible to the original**, fixing exactly two sung words:
  - `عَلَيْهِ` → was sung `عَلِيمْ` at **157.3–158.55 s** (Verse 2).
  - `فَإِنَّ` → was sung `بِأَنَّ` at **202.26–204.54 s** (Outro).
- Do **not** change lyrics words, style, LoRA, seed, sampler settings, or GPU
  type. Original is a T4 / sm75 / flash attention.
- We have the **original 5397-frame semantic token stream** and a **byte-identical
  semantic baseline**. We also have semantic streams for variants A and C
  (same poem, words sung correctly).
- The original prebuilt binary (`bin/audiocpp_cli`, audio.cpp `eb8e21bd`) **does
  not support `semantic_prefix` / `semantic_prefix_file`**. It silently ignores
  the option and re-runs the AR. Token surgery requires a patched binary.
- **Build status: DONE (2026-10-20 ~04:52 UTC, CPU-only runtime).** `eb8e21bd` +
  cherry-picked `d32a6a01` built for `sm75` with **CUDA 12.0.140** (the original
  prebuilt's toolkit) and gcc 12.4.0. Binary + sha256 + manifest + build log are
  on GCS under `.../bin/`; sha256 `4e1534f3…`. `semantic_prefix` and
  `semantic_prefix_file` are present in `strings`. See §6.7.
- **Hardware smoke test is still pending.** The build host had no GPU, so the
  binary has not executed on sm75 yet and no WAV has been produced with it.
- Next concrete step: on the **T4**, fetch the binary, verify its sha256, then
  run **§7.1** (baseline semantic, then full baseline WAV → expect `dbc00722…`).
  Only after that does token surgery start.
- After the binary is staged: run the baseline render with `min=max=5397` and the
  original token stream, and check the WAV is bit-identical to
  `dbc00722534d5ee763ae54a048cd704eaa4c927e37834cd54542eaf379e0de42`.
  If it is not, stop and investigate the toolchain (CUDA version; see §6.4).
- No repaired candidate WAV has been rendered yet (as of this writing).

---

## 1. Canonical paths and artifacts

Working tree: `/content/arabmaqamrock`
Task workspace: `/content/arabmaqamrock/happy_accident`

| artifact | path | notes |
|---|---|---|
| original WAV | `happy_accident/original/02-...-B_1712905618.wav` | sha256 `dbc00722...` |
| original sidecar | `..._1712905618.json` | seed, cap, hashes, duration |
| original log | `..._1712905618.log` | fingerprints |
| original time/GPU CSV | `..._time.txt`, `..._gpu.csv` | |
| exact lyrics | `happy_accident/prompts/02B_lyrics.txt` | sha256 `7bd3b6e1...` |
| exact style | `happy_accident/prompts/02B_style.txt` | sha256 `248af8e7...` |
| baseline semantic | `happy_accident/runs/baseline_semantic/semantic.json` | 5397 frames, sha256 `1b1aa3e...` |
| baseline log | `happy_accident/runs/baseline_semantic/run.log` | |
| A semantic (donor) | `happy_accident/runs/variants_semantic/A_4161609852/semantic.json` | 5874 frames |
| C semantic (donor) | `happy_accident/runs/variants_semantic/C_927142839/semantic.json` | 6192 frames |
| A/C inputs + logs | `happy_accident/runs/variants_semantic/` | requests, run.log, time |
| variant WAVs | `happy_accident/variants/` | A and C original WAVs |
| variant stems | `happy_accident/stems/variants/` | demucs vocals |
| B stems | `happy_accident/stems/htdemucs/...` | demucs vocals / no_vocals |
| evaluation script | `happy_accident/evaluate.py` | demucs + CTC + similarity (**reconstructed 2026-10-20**, see RESTORE.md §5) |
| alignment script | `happy_accident/align.py` | CTC forced alignment (**reconstructed**) |
| ASR helper | `happy_accident/asr2.py` | faster-whisper (**reconstructed**) |
| splice generator | `happy_accident/token_surgery.py` | writes the length-preserving token variants |
| patched audio.cpp | clone of `eb8e21bd` + `d32a6a01` | local commit `58caf774`; patches in GCS `patches/` |
| build log | GCS `.../bin/build_audio_cpp_20261020.log` | durable (the `/tmp/opencode` one is gone) |
| prefix-capable binary | GCS `.../bin/audiocpp_cli_prefix_sm75` | sha256 `4e1534f3…`; stage as `bin/audiocpp_cli_prefix` |
| pre-computed splices | `happy_accident/runs/token_surgery/tokens/` | 13 variants + baseline, all 5397 frames, + `manifest.json` |
| restore runbook | `docs/.../token_surgery/RESTORE.md` | **read this first on a fresh runtime** |
| docs | `docs/happy_accidents/Baghdad_Moon/token_surgery/` | this file, experiments, report, scripts |

GCS originals:
`gs://akbar-december-2024-backup/arabmaqamrock/runs/20261018-162827_batch_12_variants_backing_vocals/`

Prior GCS work (important, already had a bit-identical repro + semantic):
`gs://akbar-december-2024-backup/arabmaqamrock/runs/20261019_baghdad_cover_hacks/`
- `ref_full/ref_full/semantic.json` (same as our baseline semantic)
- `repro/reproB_1712905618.wav` (sha256 = original)
- `notes/` (comparison scripts, batch_test notes)

---

## 2. Hard facts (verified)

### 2.1 Original request / recipe

- Track: `02-استيداع-قمر-بغداد-ولوعة-الوداع-B`, take 0, idx 5.
- Seed: `1712905618`.
- Cap: `6750` (n_letters 507, quantile 0.95; duration heuristic 269.6 s → 270 s).
- `cot=off`, `guidance_scale=1.01`, `num_inference_steps=8`, context 24576.
- Semantic sampling defaults: temperature 1, top_p 0.95, top_k 100,
  repetition_penalty 1.2, penalty_window 50, min_tokens 200.
- `stop_after=audio`, `export_semantic=true` (for token recovery).
- AR LoRA + NAR LoRA scale 1.0; `yue2.attention=flash`.
- Model: `yue2-3b-bf16.gguf`; VAE `yue2-vae-f16.gguf`.
- Duration: 215.8787 s; 5397 semantic frames at 25 fps.
- WAV: 48 kHz, stereo, 16-bit PCM, 10,362,176 frames.
- WAV sha256: `dbc00722534d5ee763ae54a048cd704eaa4c927e37834cd54542eaf379e0de42`.
- Sidecar `wav_sha256` matches; `truncated=false`.

### 2.2 Hashes

| item | sha256 |
|---|---|
| model GGUF | `4cf3fdffbaaed2d8e30a3122ac7cd27d0c96f8921805f173da9758c685b3c7d6` |
| VAE GGUF | `d4f4a05d8f291ae820cd1e43609da3fa91b56465810091a2b08c3350b751719d` |
| LoRA AR | `3531bb9106d2292eefe58eabe11ec08bb7dddc69554f2b016dc9f13f711fab18` |
| LoRA NAR | `a7eabcadb22146048bcb5e65d04828ee9454559523ca161bd38c06060deb0cae` |
| lyrics | `7bd3b6e1da3aa4e674d728cd24af4a3ffe6e89468b6b5714b543c6310513c46d` |
| style | `248af8e769501f2bb565129d781ea33d5672039d908286729d6f319066430b8e` |
| baseline semantic | `1b1aa3e26ed81f07323e18a2c48ccff0d4fa72b7f6ebad6447705ba28d481b59` |
| original binary | `7ad69d1ccfe432b8c5e100009188b56013e48dc117ae391958b1000439caa93c` |
| batch input JSON | `73566c1b433485241a8194288aacd827e00aa43fa38d7e28efbf94f543a52483` |

Lyrics/style were extracted byte-for-byte from the run's `--lyrics` /
`--request-option style=`. **No trailing newline.** First lyric line is the
literal `///***///`. Style starts with `arabmaqamrock,`.

### 2.3 Baseline reproduction (already done)

`runs/baseline_semantic/`:
- `stop_after=semantic`, `export_semantic=true`, original prompts/seed/cap.
- Log fingerprints: `positive_prefix_tokens 1079`, `negative_prefix_tokens 12`,
  `semantic.tokens 5397`, `truncated 0`.
- `semantic.json` is **identical** to the previously exported original
  (`sha256 1b1aa3e...`).
- Wall time 331.7 s on the T4.

Full audio baseline: prior GCS `repro/reproB_1712905618.wav` is **bit-identical**
to the original (same sha256). Our own full render with the rebuilt binary is
still pending; that is the next check.

---

## 3. The two errors and the donor instances

Times from demucs vocal stem + faster-whisper + Arabic CTC forced alignment.
Frame = seconds × 25.

| error | correct | sung | time | frames | note |
|---|---|---|---|---|---|
| 1 | `عَلَيْهِ` | `عَلِيمْ` | 157.3–158.55 s | ~[3933, 3964) | only in Verse 2 |
| 2 | `فَإِنَّ` | `بِأَنَّ` | 202.26–204.54 s | ~[5056, 5114) | only in Outro |

**Same-take donors (best first route):**

| donor | text | time | frames | why |
|---|---|---|---|---|
| B Outro | `عَلَيْهِ` correct | 201.0–202.24 s | [5025, 5056) | same take, same singer, **same pitch contour** 439→394→439→465 Hz; 31 frames = same length as Verse 2 word |
| B Verse 2 | `فَإِنَّ` correct | 158.5–159.5 s | [3962, 3988) | same take; word is shorter than Outro's stretched climax word |
| A Verse 2 | `عَلَيْهِ` correct | 165.94–166.52 s | [4148, 4163)* | same model/poem; full-band Verse 2 context |
| A Outro | `فَإِنَّ` correct | 221.32–223.56 s | [5533, 5589)* | A's Outro arrangement is closer to B's Outro |
| C Verse 2 | `عَلَيْهِ` correct | 175.86–176.46 s | [4396, 4412)* | pitch 439→465, matches B |
| C Outro | `فَإِنَّ` correct | 235.92–237.90 s | [5898, 5948)* | C's Outro |

*A/C frame ranges are derived from ASR word timestamps, not yet CTC-aligned; treat as approximate (±5 frames).*

**Important nuance:** the semantic tokens encode the **full mix** (vocals +
arrangement), not just the voice. A 1-second token splice from the Outro into
Verse 2 can drag the Outro's clean-guitar timbre into the full-band verse. The
NAR may smooth it, but it must be measured. Prefer donors from the same section
type (Verse 2 → Verse 2, Outro → Outro) and/or short windows.

**The rhyme-contamination hypothesis in the Claude prompt is weakened:** both
occurrences are preceded by `ثَوْبَ النَّعِيمِ`, but only Verse 2 sings
`عَلِيمْ`; the Outro sings `عَلَيْهِ` correctly. So the error is stochastic /
context-dependent, not a deterministic rhyme pull.

---

## 4. Evaluation method (no ears)

Whisper on the full mix hallucinates (“subscribe to the channel”), and even on
the Outro vocal stem it often fails. What works:

1. **Demucs** `htdemucs --two-stems=vocals` on the candidate WAV.
2. **Arabic CTC** `jonatasgrosman/wav2vec2-large-xlsr-53-arabic`:
   - Window e1: 156.8–158.9 s. Original greedy output ends in `م`
     (`…عَلْعَيِيمِ`). A fixed candidate should end in `ه` (`…عَلَى يَلِه` or similar).
   - Window e2: 201.6–205.1 s. Original output starts with `ب` (`…بِأَنَّ…`);
     a fixed candidate should start with `ف`.
3. **F0 contour** via `librosa.pyin` to check the donor melody matches.
4. **Waveform correlation** overall and in 5 s windows; **mel-spectrogram mean
   absolute difference** to quantify collateral change outside the edited windows.
5. The user decides the final take **by ear**. We cannot.

`happy_accident/evaluate.py` implements 1–4 (demucs + CTC + correlation + mel
distance). `happy_accident/align.py` implements CTC forced alignment.

Original full mix CTC (no demucs) is useless: `الجُّوكِّرْيَدْعَلَ هِيقِي`
for e1. Always demucs first.

---

## 5. What has been tried

| # | experiment | result |
|---|---|---|
| 0 | baseline semantic, original binary | **success**: 5397 tokens, exact match, fingerprints 1079/12 |
| 1 | original binary + `semantic_prefix_file` + `min=max=5397` | **failed/aborted**: option silently ignored; binary re-ran the AR. `strings` shows no `semantic_prefix`; `--version` says `git eb8e21b 2026-09-21`. |
| 2 | A/C semantic exports (`stop_after=semantic`) | **success**: A 5874 frames, C 6192 frames; request wall 275 s each. |
| 3 | rebuild `eb8e21bd` + cherry-pick `d32a6a01` | **done 2026-10-20** on a CPU-only runtime: CUDA 12.0.140, gcc 12.4.0, sm75, sha256 `4e1534f3…`, `semantic_prefix` present, staged to GCS. GPU smoke test + §7.1 still pending. |
| 4 | local baseline audio with original binary (GPU) | **aborted** before WAV (killed with the build); use the GCS `repro/reproB` WAV or re-run later. |
| 4b | baseline audio render with new binary | **pending** |
| 5 | token splices (e1 note/word; e2 onset/word) | **pending** |
| 6 | error-2 tail resample seed sweep | **pending** |

The aborted v1 batch is at `runs/token_surgery/v1/` (no WAVs).

---

## 6. The binary problem and the rebuild

### 6.1 Why the original binary cannot do the task

`bin/audiocpp_cli` is the sm75-t4 prebuilt, sha256 `7ad69d1...`, built
2026-09-22T09:49:52Z. Its `--version` prints `git: eb8e21b 2026-09-21`; CMake sets that string from `git rev-parse --short HEAD` of the audio.cpp checkout, so this is the audio.cpp commit, not the ggml submodule.
`semantic_prefix` support landed in `d32a6a01` on 2026-09-22 14:42 EDT,
**after** the binary was built. `strings bin/audiocpp_cli | grep semantic_prefix`
returns nothing. Passing the option does not error; it is ignored.

### 6.2 What we built

- Base: `eb8e21bd7b71dc104d6be7a88f5641bcd5373617` (the original prebuilt’s source).
- Cherry-picked: `d32a6a0186a47f783b7415e3e48ebb1d917df742`
  (“yue2: continue a song from given semantic tokens”).
- Local commit: `42bb0a88` on branch `prefix-on-orig` in the 2026-10-19 attempt;
  the 2026-10-20 CPU rebuild is **`58caf774`** (same tree, different committer
  identity/time — verified byte-identical code diff).
- Only YuE2 files changed by the cherry-pick: `ar_runtime.cpp/h`, `pipeline.cpp`,
  `request.cpp`, `types.h`, `model_specs/yue2.json` (+ docs/examples). Normal
  requests without a prefix should render as before.
- Save the patch: `git diff eb8e21bd..42bb0a88` (should be mirrored to GCS).

### 6.3 Build command

```bash
cd /tmp/opencode/audio.cpp
scripts/build_linux.sh --backend cuda --cuda-arch 75 --ccache \
  --model-set custom --models yue2 --target audiocpp_cli
```

Needs `ccache` (it was installed with apt in this session). Output:
`/tmp/opencode/audio.cpp/build/linux-cuda-release/bin/audiocpp_cli`.
**Do not overwrite `bin/audiocpp_cli` until the baseline check passes.** Stage the
new one as `bin/audiocpp_cli_prefix` or `happy_accident/bin/audiocpp_cli_prefix`.

### 6.4 Toolchain caveat

**Resolved in the 2026-10-20 CPU build:** the build used CUDA **12.0.140** — the
same toolkit as the original prebuilt — with gcc 12.4.0 on Ubuntu 24.04, so the
CUDA-13 numerics concern below no longer applies. Bit-identity of the *rendered
WAV* is still unproven until §7.1 is run on the T4.

Original prebuilt: CUDA **12.0.140**, gcc 13.3.0. The 2026-10-19 GPU image had
CUDA **13.0.88**, gcc 13.3.0, which would have risked changing float numerics.
Test baseline first (§7.1) regardless.
If the baseline WAV is not bit-identical:
- try `apt-get install cuda-toolkit-12-5` and rebuild with `/usr/local/cuda-12.5`
  on `PATH`/`CUDA_HOME` (12.5 is available from the configured NVIDIA repo);
- or accept a non-bit-identical baseline and quantify the difference, but say so
  clearly. Do not claim bit-identity if it is not.

### 6.5 If the VM is wiped

1. Recreate the repo/environment (`./setup_colab.sh` or `./install.sh`) so the
   model, VAE and both LoRA files are staged; verify hashes in §2.2.
2. Clone `https://github.com/0xShug0/audio.cpp` and check out `eb8e21bd`,
   `git cherry-pick d32a6a01` (or apply the saved patch).
3. Build as in §6.3.
4. Download the token/prompt artifacts from GCS (§10) so you do not need to
   re-run the baseline or A/C exports.
5. If a built sm75 token-surgery binary was backed up, prefer it and verify its
   sha256 before use.

### 6.6 CPU build runbook (next session, no GPU)

The build is **CPU-only** (`nvcc` cross-compiles for `sm75`). Do this on a
CPU-only Colab runtime; do not occupy a T4 for it. Full copy-paste runbook:
`CPU_BUILD.md` in this folder.

Summary:
1. Install `git cmake g++ ccache wget` and a CUDA toolkit. Prefer **CUDA 12.5**
   (or 12.0 if you can get it) over 13.0, because the original prebuilt used
   CUDA 12.0.140 and bit-identity is the goal. `nvcc --version` must work; no GPU
   is required.
2. Clone `https://github.com/0xShug0/audio.cpp`, check out `eb8e21bd`, and
   cherry-pick `d32a6a01` (or apply the saved patch from GCS). This yields local
   commit `42bb0a88`.
3. Build:
   ```bash
   scripts/build_linux.sh --backend cuda --cuda-arch 75 --ccache \
     --model-set custom --models yue2 --target audiocpp_cli
   ```
4. Verify the binary:
   ```bash
   ./build/linux-cuda-release/bin/audiocpp_cli --version
   strings ./build/linux-cuda-release/bin/audiocpp_cli | grep semantic_prefix
   ```
   It must show `semantic_prefix`/`semantic_prefix_file`.
5. Save it outside the ephemeral VM:
   ```bash
   cp build/linux-cuda-release/bin/audiocpp_cli /content/audiocpp_cli_prefix
   sha256sum /content/audiocpp_cli_prefix
   tar -czf /content/audiocpp_cli_prefix_sm75.tar.gz -C /content audiocpp_cli_prefix
   ```
   Upload the binary + sha256 + a small manifest to GCS (or Google Drive) before
   the CPU runtime dies.
6. On the T4 runtime, fetch that binary, `chmod +x`, verify sha256, and run
   §7.1. Do **not** rebuild on the GPU VM.

If CUDA 12.5 is unavailable, try 12.0; if neither works on the CPU image, build
with 13.0 and explicitly test baseline bit-identity before claiming success.

### 6.7 Build result (DONE — 2026-10-20 ~04:52 UTC, CPU-only runtime)

The CPU build succeeded. **The prefix-capable binary exists and is backed up.**

| item | value |
|---|---|
| GCS binary | `gs://akbar-december-2024-backup/arabmaqamrock/runs/20261019_baghdad_moon_token_surgery/bin/audiocpp_cli_prefix_sm75` |
| sha256 | `4e1534f3e6fde456198ed5404313a832029193bf7ea47c817086a24a5aa3849c` |
| size | 351,848,224 bytes |
| tarball | `.../bin/audiocpp_cli_prefix_sm75.tar.gz` (sha256 `5e8d16b5…`) |
| manifest | `.../bin/audiocpp_cli_prefix_sm75.manifest.json` |
| build log | `.../bin/build_audio_cpp_20261020.log` |
| local commit | `58caf774` (cherry-pick of `d32a6a01` on `eb8e21bd`) |
| CUDA | **12.0.140** (exactly the original prebuilt's toolkit) |
| host compiler | gcc/g++ **12.4.0** (gcc-13 is rejected by CUDA 12.0) |
| cmake / ccache | 3.31.10 / 4.9.1 |
| arch | `CMAKE_CUDA_ARCHITECTURES=75`, cubins verified `sm_75` |

`--version` on the GPU-less build host (with a stub `libcuda.so.1`) prints:

```
audio.cpp dev
git: 58caf774 2026-10-20
build: RelWithDebInfo, gcc 12.4.0, Linux x86_64
backends: cpu,cuda
```

`strings` contains `semantic_prefix`, `semantic_prefix_file`,
`parse_semantic_prefix`, `semantic_prefix_from_options`. So CPU_BUILD.md §6
passes.

Notes:
- Local commit is `58caf774`, not `42bb0a88`; the commit hash differs only by
  committer identity/time. `git diff eb8e21bd..HEAD -- src include model_specs`
  is **byte-identical** to the saved
  `backup/patches/semantic_prefix_on_eb8e21bd_code.patch` (verified, 0 diff
  lines). Fresh patches are saved as `rebuild_58caf774_{code,full}.patch`.
- No GPU was used or needed for the build.
- Still **unverified on hardware**: no smoke test on sm75 yet, and the baseline
  render (§7.1) has not been run. Next session must do §7.1 on the T4 before any
  token surgery.

---

## 7. Remaining plan (do in this order)

### 7.1 Verify the new binary

1. `--version` and `strings` should show the prefix option.
2. Run the original recipe with `stop_after=semantic` (no prefix) and compare
   tokens to `runs/baseline_semantic/semantic.json`. Expected: identical.
3. Render the full original token stream:
   `semantic_prefix_file=baseline.json`, `semantic_min_tokens=5397`,
   `semantic_max_tokens=5397`, original seed/style/lyrics, `stop_after=audio`.
   Compare WAV sha256 to the original. Expected: `dbc00722...`.
   If not, stop and report the difference before doing any surgery.

### 7.2 Error 1 (Verse 2, `عَلَيْهِ`)

Try, in order:
- **A. Final-note splice:** replace frames `[3956, 3964)` with the Outro donor
  `[5048, 5056)` (8 frames). Both are the 465 Hz final note; this changes the
  final consonant `/m/` → `/h/` with minimal collateral.
- **B. Whole-word splice:** replace `[3933, 3964)` with `[5025, 5056)` (31
  frames, same length, same pitch contour). More of the word changes; may be
  cleaner or may drag Outro timbre.
- **C. A/C Verse 2 donor:** replace with A `[4148, 4163)` or C `[4396, 4412)`
  (15–16 frames vs 31; length mismatch — pad/trim at a vowel boundary, or
  resample the window with AR first). Only if A/B fail.
- **D. AR resample:** prefix `tokens[:3933]`, `max_tokens=3964`, seed sweep,
  `semantic_temperature` 1.0 (and optionally 0.9), pick candidates whose CTC
  ends in `ه` and whose length is 31 frames, then splice.

### 7.3 Error 2 (Outro, `فَإِنَّ`)

The word is stretched (~57 frames); the correct Verse 2 word is only 26 frames.
Options:
- **A. Onset-only splice:** replace the first ~13 frames `[5056, 5069)` with
  Verse 2 `[3962, 3975)`. This changes the `/b/` onset to `/f/` while preserving
  the long climax melisma. Check F0: Verse 2 onset is ~466 Hz; Outro onset is
  ~432→394 Hz, so the pitch may jump. If it does, try C's onset
  `[5898, 5911)` (~452 Hz) or A's `[5533, 5546)` (~335 Hz; probably too low).
- **B. Whole-word splice:** replace `[5056, 5082)` with Verse 2 `[3962, 3988)`
  (26 frames), leaving the rest of the melisma. More likely to sound like the
  whole word, but a bigger melodic change.
- **C. Tail resample (preferred if A/B are audible):** prefix
  `tokens[:5056]`, `semantic_max_tokens=5397`, original seed + seed sweep
  (e.g. `1712905618 + 0..15`), `stop_after=semantic`, then render the candidates.
  Only the last ~13.6 s changes. Choose by CTC (`ف` onset) + F0/melody similarity
  to the original tail + your ear.
- The Claude prompt suggested a prefix at frame ~5100 (03:24). **Do not use
  5100**: that cuts inside `فَإِنَّ`. Use **5056** (or a little earlier, e.g.
  5040, if more context is needed).

### 7.4 Combine and deliver

- Apply the best e1 fix and best e2 fix to the same token stream.
- Render with `min=max=5397`, original seed.
- Verify both errors with demucs + CTC; measure waveform correlation and mel
  distance outside the edited windows.
- Produce top 3 candidates as WAVs; do not overwrite the original.
- Write `report.md` and `experiments.md`; back up everything to GCS.

---

## 8. Exact command templates

Use absolute LoRA paths: relative paths resolve under the **model root**
(`models/Yue2-3B-GGUF/`), not the repo root. This bit us once.

```bash
cd /content/arabmaqamrock
. ./cuda_loader_path.sh
BIN=./bin/audiocpp_cli_prefix   # or the new build path
OUT=happy_accident/runs/<name>
mkdir -p "$OUT"
"$BIN" --task gen --family yue2 --model models/Yue2-3B-GGUF --backend cuda --threads 8 \
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
  --request-option semantic_prefix_file=/abs/path/tokens.json \
  --request-option semantic_min_tokens=5397 \
  --request-option semantic_max_tokens=5397 \
  --seed 1712905618 --out "$OUT/fixed.wav" --out-dir "$OUT/artifacts" --log
```

Batch mode (keeps the session loaded; the old binary supports it too):

```bash
"$BIN" ... --request-sequence happy_accident/runs/<name>/requests.json \
  --out-dir "$OUT" --log
```

Each request: `{"id","lyrics","seed","options":{...}}`; per-request
`semantic_prefix_file`, `semantic_min_tokens`, `semantic_max_tokens`,
`export_semantic`. Outputs: `<out-dir>/<id>.wav`, `<out-dir>/<id>/semantic.json`.

For AR-only candidate generation, use `stop_after=semantic` (no NAR/VAE; fast).
For exact given tokens, `min=max=N` skips the AR stage (per `d32a6a01`).

---

## 9. Gotchas / lessons

- `bin/audiocpp_cli` needs `libcublas.so.12`; source `cuda_loader_path.sh` before
  running it (also for Python if using CUDA).
- LoRA paths: absolute, or relative to the **model root**, not the repo root.
- Unknown request options are silently ignored by the old binary; “no error” is
  not proof of support. Use `strings`/behavior tests.
- `--request-sequence` is the cheap way to sweep seeds; fixed cost is ~4 min
  (AR init ~68 s, NAR LoRA merge ~117 s, NAR init ~64 s). AR decode ~24 tok/s.
- Sequential runs only; two concurrent GPU runs can OOM a T4. The build is CPU,
  not GPU, but compiling while AR runs starves the 2 vCPUs; `renice`/pause if
  needed.
- Demucs on T4 is fast (~15 s/song); Whisper large-v3 is unreliable on this mix.
- Original full mix CTC is useless; demucs first.
- Semantic tokens encode the full mix, not just vocals.
- The original audio is 16-bit PCM 48 kHz stereo; NAR/VAE outputs the same
  length for 5397 frames.
- `happy_accident/` is **not** part of the original repo layout; it is our
  workspace. The repo itself is `/content/arabmaqamrock`.
- The `docs/happy_accidents/Baghdad_Moon/` folder contains the case study and the
  original zip; do not overwrite them.

---

## 10. Backups (Colab safety)

**Status 2026-10-20: complete.** Everything needed to resume on a fresh runtime is
under
`gs://akbar-december-2024-backup/arabmaqamrock/runs/20261019_baghdad_moon_token_surgery/`.
Full restore steps: `RESTORE.md` in this folder.

Inventory (verified present):

| path | contents |
|---|---|
| `bin/audiocpp_cli_prefix_sm75` (+ `.sha256`, `.tar.gz`, `.manifest.json`) | prefix-capable sm75 binary |
| `bin/build_audio_cpp_20261020.log` | build log |
| `patches/` | `semantic_prefix_on_eb8e21bd_{code,full}.patch`, `rebuild_58caf774_{code,full}.patch` |
| `prompts/` | `02B_lyrics.txt`, `02B_style.txt` |
| `baseline/` | `semantic.json` (5397), `run.log` |
| `variants/` | `A_semantic.json` (5874), `C_semantic.json` (6192), `run.log` |
| `tokens/` | 13 splice variants + `tokens_baseline.json` + `manifest.json` |
| `scripts/` | `evaluate.py`, `align.py`, `asr2.py`, `token_surgery.py`, `render_tokens.sh` |
| `workspace/` | `happy_accident_workspace.tar.gz` (prompts + tokens + semantic, no audio) |
| root | `HANDOFF.md`, `CPU_BUILD.md`, `RESTORE.md`, `experiments.md`, `evidence.md`, `state.json`, `README.md` |

Not in this prefix, by design: the original/variant WAVs (in
`runs/20261018-162827_batch_12_variants_backing_vocals/`), model/VAE/LoRA
(re-downloaded by `setup_colab.sh`), demucs stems (regenerable).

When you produce something new, append to this prefix; do not overwrite the
binary or the baseline.

---

## 11. What *not* to redo

- Do not re-derive the original hashes/timings; use §2 and §3.
- Do not re-run the baseline semantic; it is exact and saved.
- Do not re-run A/C semantic exports; they are saved (A 5874, C 6192).
- Do not try `semantic_prefix_file` on `bin/audiocpp_cli`; it is ignored.
- Do not use Whisper alone to judge the fix; use demucs + CTC + F0.
- Do not cut error 2 at frame 5100; use 5056.
- Do not assume the Outro `عَلَيْهِ` is wrong; it is correct and is a donor.
- Do not overwrite the original WAV or the original run directory.

---

## 12. Open questions / decisions for the user

1. If the rebuilt binary’s baseline is **not** bit-identical due to CUDA 13, is a
   close-but-not-bit-identical render acceptable, or should we install CUDA 12.5
   and rebuild? (The user cares about “as identical as possible”.)
2. Error 2: is a changed final ~13.6 s tail acceptable, or must the original
   ending be preserved with a short splice? (Tail resample is cleaner
   linguistically but changes more music.)
3. Error 1: if the whole-word donor splice drags Outro timbre, is a slightly
   different vowel acceptable, or should we prefer the minimal final-note splice?
4. Final choice is by ear; the agent can only rank candidates.

---

## 13. Minimal “future agent” prompt

> Work in `/content/arabmaqamrock`. Read
> `docs/happy_accidents/Baghdad_Moon/token_surgery/RESTORE.md` and then
> `HANDOFF.md`; they supersede the old `happy_accident.zip` prompt and record the
> finished CPU build. The goal is to fix exactly two sung words in the B take
> (`عَلَيْهِ` at 157.3–158.55 s, `فَإِنَّ` at 202.26–204.54 s) by token-level
> surgery on the original 5397-frame semantic stream, using the prefix-capable
> binary at GCS `.../bin/audiocpp_cli_prefix_sm75` (sha256 `4e1534f3…`).
> Do not change style/lyrics/seed/LoRA/sampler/GPU, and do not rebuild on the T4.
> Baseline semantic is exact at `happy_accident/runs/baseline_semantic/semantic.json`;
> baseline WAV must be `dbc00722…` before any surgery. Donors: B Outro
> `[5025,5056)` for e1; B Verse 2 `[3962,3988)` for e2; A/C tokens in
> `runs/variants_semantic/`. The length-preserving splices are already generated in
> `runs/token_surgery/tokens/` — render them first. Verify with `evaluate.py`
> (demucs + Arabic CTC) and waveform/mel similarity. Back up to GCS before long
> runs. Report honestly if the rebuilt baseline is not bit-identical.

