# CPU build runbook — prefix-capable `audiocpp_cli` for sm75

**Why:** the build is CPU-only. `nvcc` cross-compiles for `sm75`; no GPU is
needed. Running it on a T4 wastes GPU time. Build on a CPU-only Colab runtime,
save the binary, then move to a T4 for the baseline and renders.

Target: audio.cpp `eb8e21bd` + cherry-picked `d32a6a01` (semantic prefix
support) → local commit `42bb0a88`.

---

## 1. Provision

Start a **CPU-only** Colab runtime (no GPU). Check:

```bash
nproc; free -g; df -h /content
nvcc --version || echo "no nvcc"
```

You need ~10 GB free disk, `git`, `cmake`, `g++`, `ccache`, and a CUDA toolkit.

## 2. Base packages

```bash
apt-get update
apt-get install -y git cmake g++ ccache wget
ccache --version | head -1
```

If `ccache` is missing, the build script aborts with
`--ccache was passed but ccache is not installed`.

## 3. CUDA toolkit (no GPU needed)

Prefer **CUDA 12.5** (closest practical to the original 12.0.140), or **12.0**
for the best chance of bit-identity. Use **13.0 only as a last resort**; then
you must prove baseline bit-identity before claiming success.

### Option A — runfile (no apt repo needed)

```bash
cd /tmp
# CUDA 12.5.0 (example; check NVIDIA's CUDA archive if the URL changes)
wget -q https://developer.download.nvidia.com/compute/cuda/12.5.0/local_installers/cuda_12.5.0_555.42.02_linux.run
sh cuda_12.5.0_555.42.02_linux.run --silent --toolkit --override
export PATH=/usr/local/cuda-12.5/bin:$PATH
export LD_LIBRARY_PATH=/usr/local/cuda-12.5/lib64:${LD_LIBRARY_PATH:-}
nvcc --version
```

For CUDA 12.0.1:
```bash
wget -q https://developer.download.nvidia.com/compute/cuda/12.0.1/local_installers/cuda_12.0.1_525.85.12_linux.run
sh cuda_12.0.1_525.85.12_linux.run --silent --toolkit --override
export PATH=/usr/local/cuda-12.0/bin:$PATH
```

### Option B — NVIDIA apt repo

If the image already has the NVIDIA CUDA repo configured:

```bash
apt-get install -y cuda-toolkit-12-5
export PATH=/usr/local/cuda-12.5/bin:$PATH
nvcc --version
```

If `nvcc` still points at 13.0, export `PATH`/`CUDA_HOME` explicitly and
confirm with `which nvcc`.

### GCC compatibility

CUDA 12.0/12.5 may reject gcc 13. If the build fails with an unsupported
compiler error:
```bash
apt-get install -y gcc-12 g++-12
export CC=/usr/bin/gcc-12 CXX=/usr/bin/g++-12
```
or add `-allow-unsupported-compiler` via the build flags. Record what you used.

## 4. Source + patch

```bash
cd /content
git clone https://github.com/0xShug0/audio.cpp.git
cd audio.cpp
git checkout eb8e21bd
git cherry-pick d32a6a01
git log --oneline -2
# expected top: the d32a6a01 cherry-pick; local SHA may differ (42bb0a88 here)
```

If the cherry-pick conflicts, apply the saved code patch instead:

```bash
# download from GCS first (see §7 for the bucket), then:
git apply /content/semantic_prefix_on_eb8e21bd_code.patch
git add -A && git commit -m "semantic prefix on eb8e21bd"
```

Confirm the expected files changed:
```bash
git diff --stat eb8e21bd..HEAD -- src include model_specs
# include/engine/models/yue2/ar_runtime.h, types.h
# model_specs/yue2.json
# src/models/yue2/ar_runtime.cpp, pipeline.cpp, request.cpp
```

## 5. Build

```bash
cd /content/audio.cpp
scripts/build_linux.sh --backend cuda --cuda-arch 75 --ccache \
  --model-set custom --models yue2 --target audiocpp_cli
```

Output:
`/content/audio.cpp/build/linux-cuda-release/bin/audiocpp_cli`.

The build needs no GPU and no model files. It is CPU-bound; expect ~20–40 min
on 2 vCPUs, faster with more cores. Use `ccache` for retries.

## 6. Verify the binary

```bash
BIN=/content/audio.cpp/build/linux-cuda-release/bin/audiocpp_cli
"$BIN" --version
# should print the cherry-picked commit, e.g. 42bb0a8
strings "$BIN" | grep -E 'semantic_prefix(_file)?'
# must print both option names
sha256sum "$BIN"
```

If `semantic_prefix` is absent, the cherry-pick did not apply or you built the
wrong tree. Do not proceed.

## 7. Save it before the CPU VM dies

```bash
cp "$BIN" /content/audiocpp_cli_prefix
chmod +x /content/audiocpp_cli_prefix
sha256sum /content/audiocpp_cli_prefix | tee /content/audiocpp_cli_prefix.sha256
tar -czf /content/audiocpp_cli_prefix_sm75.tar.gz -C /content audiocpp_cli_prefix
```

Upload the binary (or tarball) + sha256 to GCS:

```bash
P=gs://akbar-december-2024-backup/arabmaqamrock/runs/20261019_baghdad_moon_token_surgery/bin
gsutil cp /content/audiocpp_cli_prefix "$P/audiocpp_cli_prefix_sm75"
gsutil cp /content/audiocpp_cli_prefix.sha256 "$P/audiocpp_cli_prefix_sm75.sha256"
```

Write a tiny manifest (commit, CUDA version, gcc version, sha256) next to it.
If GCS auth is unavailable, put the tarball on Google Drive and record the link
in `HANDOFF.md`/`state.json`.

## 8. Move to the T4

On the GPU runtime:

```bash
# stage repo + model + LoRA as usual (setup_colab.sh / install.sh)
# then fetch the built binary, e.g.:
gsutil cp gs://.../bin/audiocpp_cli_prefix_sm75 /content/arabmaqamrock/bin/audiocpp_cli_prefix
sha256sum -c ...   # compare to the recorded hash
chmod +x /content/arabmaqamrock/bin/audiocpp_cli_prefix
```

Then follow `HANDOFF.md` §7.1: baseline semantic + full baseline render, compare
to the original `dbc00722…` WAV. Only then do token surgery.

## 9. Numerics decision tree

- **CUDA 12.5 or 12.0 build reproduces `dbc00722…`** → use it; claim bit-identity.
- **It does not** → try the other 12.x toolkit; check `--version`, gcc, and
  whether the normal (no-prefix) semantic stream is still exactly 5397 tokens
  with the 1079/12 fingerprints.
- **Only 13.0 is available and it does not reproduce** → report the difference
  honestly, quantify it (tokens, WAV hash, waveform/mel distance), and ask the
  user whether a close-but-not-bit-identical render is acceptable. Do not
  silently claim identity.

## 10. Troubleshooting

| symptom | cause | fix |
|---|---|---|
| `--ccache was passed but ccache is not installed` | missing ccache | `apt-get install -y ccache` |
| `nvcc: not found` | no CUDA toolkit | install 12.5/12.0 (§3) |
| unsupported gcc version | CUDA older than gcc | install gcc-12 and set `CC/CXX`, or add `-allow-unsupported-compiler` |
| `semantic_prefix` missing from `strings` | wrong tree / cherry-pick failed | re-check `git log`, `git diff eb8e21bd..HEAD` |
| build OOM | too many parallel jobs | `--parallel 2` or fewer; close other processes |
| binary won't start on GPU host | missing CUDA 12 runtime libs | `. ./cuda_loader_path.sh` before running |

---

## 11. What not to do

- Do not run the build on the T4.
- Do not run AR/NAR while the build is compiling on the same 2-vCPU box; they
  starve each other. Build first, then use the GPU.
- Do not overwrite the original `bin/audiocpp_cli` until the new binary’s
  baseline is verified.
- Do not proceed to token surgery if `semantic_prefix` is absent.
