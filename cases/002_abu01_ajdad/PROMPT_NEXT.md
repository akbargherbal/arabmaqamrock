Respond in English only; the VM terminal does not support Arabic.

## Task

You are on Google Colab (Tesla T4, sm75). The repo is at `/content/arabmaqamrock`.
`gsutil` and `hf` are authenticated.

Produce a copy of **`repro_abc_cfg15.wav`** in which the word **`مِلَّتِي`** in
the **opening verse** (first occurrence) has a clean initial **/m/**, and **no
seam is audible**.

The word is currently heard as **“لتي”** — the initial **م** is missing. The
same word in the **repeated verse** (second occurrence) is **correct**; do not
touch it.

**Acceptance requires both conditions:**

1. the **م** is audible at the start of `مِلَّتِي`;
2. the user cannot hear where the edit is.

If only one holds — correct sound with an audible seam, or a smooth join with the
missing **م** — **keep the original CFG 1.5 take and stop.** Do not replace one
defect with another. The original file is never modified; work on copies.

**Success is also time.** Target ~30 minutes. Record the wall time of every phase
from the first command, and report a timing table at the end.

**Your role:** you cannot hear. Measurement, generation, comp and verification
are yours; the audio verdict is the user's. Do not ask technical questions —
technical decisions are yours. Ask only: “Do you hear a seam?” or “Which version
is better?”

## Read first — do not redo previous analysis

1. `cases/002_abu01_ajdad/CHECKPOINT.md` — **authoritative** for this task
   (§0, §6B, §6C, §7).
2. `cases/002_abu01_ajdad/intake/defect_card_cfg15.md` — the closed defect card.
3. `cases/002_abu01_ajdad/intake/measure_cfg15.json` — the measured map and
   generation window.
4. `cases/002_abu01_ajdad/intake/words_cfg15.json` — the CFG 1.5 alignment.
5. `cases/002_abu01_ajdad/STEPS.md` — the plain-language procedure (its old
   numbers are for the original L4 take only).
6. `cases/002_abu01_ajdad/RUN2.md` — the session-3 report (token gate, ABC
   experiments).

**If anything conflicts with this prompt, this prompt wins.** Do not re-derive
the semantic tokens, do not run the old token gate, and do not use the original
L4 take as the base. The active take is the T4 CFG 1.5 ABC take.

## 0) Preflight — verify assets before any GPU work (~5 min)

```bash
cd /content/arabmaqamrock && git pull
./setup_colab.sh
```

Fetch the active take and its provenance:

```bash
RUN=gs://akbar-december-2024-backup/arabmaqamrock/runs/20261114-191700_abc_cfg15
mkdir -p work/cfg15 loras/experiments/mix_v3/a0.1
gsutil -m cp \
  "$RUN/repro_abc_cfg15.wav" \
  "$RUN/tokens/abc_cfg15_semantic.json" \
  "$RUN/session/repro.log" \
  "$RUN/score.abc" \
  work/cfg15/
gsutil -m cp \
  "gs://akbar-december-2024-backup/OSTRIS_Arabic_Suno_Finetuning/arabic_instrumental_lora/mix_v3/a0.1/*.safetensors" \
  loras/experiments/mix_v3/a0.1/
```

- WAV: `repro_abc_cfg15.wav`
- tokens: `abc_cfg15_semantic.json`
- log: `repro.log`
- score: `score.abc` (also in `cases/002_abu01_ajdad/abc/score.abc`)

Expected:

| asset | expected |
|---|---|
| WAV sha256 | `4f9006defa5390c001ce5d3c3a742350c2ab8c3c80c5e400b13ac54919f95b4a` |
| WAV duration / format | **224.238667 s**, 48 kHz stereo PCM_16 |
| tokens | **5606** frames @ 25 fps; file sha `c218c41c77faf879a9f2d079fcae0cc6b155cb6fa8d18a24c47e54596213b9e0` |
| token check | `5606 / 25 ≈ 224.24 s` — must match the WAV |
| model / VAE | `4cf3fdff…` / `d4f4a05d…` |
| LoRA a01 AR / NAR | `d48109b3…` / `88f00bcb…` |
| prefix binary | `4117a46a…` (T4 only) |
| GPU | T4 / compute capability 7.5 |

Stage the prefix-capable binary (setup_colab.sh stages the ordinary one):

```bash
gsutil cp \
  gs://akbar-december-2024-backup/arabmaqamrock/binaries/sm75-t4/prefix/audiocpp_cli_prefix_sm75 \
  bin/audiocpp_cli_prefix
chmod +x bin/audiocpp_cli_prefix
sha256sum bin/audiocpp_cli_prefix
strings bin/audiocpp_cli_prefix | grep semantic_prefix
```

The sha must be `4117a46a…`, and the prefix option must be present; it must not
be silently ignored.

**G0 — token check (30 s):** count + duration + sha. **No re-derive and no full
render.** If the count/duration/sha do not match, stop: wrong token file.

Show the user a one-screen asset table and **wait for approval** before any GPU
run. Then play the first ~40 s of `repro_abc_cfg15.wav` and confirm this is the
CFG 1.5 take the user means (there are other takes in the bucket; `abu01_orig`
is also CFG 1.5 but is L4 and has no tokens — not this one).

## 1) Verify the localized defect (~5 min)

The localization is already done; do not re-invent it. The card is in
`intake/defect_card_cfg15.md`.

**Card:**

- line: `غَيْرُ مُجْدٍ فِي مِلَّتِي وَاعْتِقَادِي` — opening verse, lyrics line 1
  (aligner line 0)
- target: **`مِلَّتِي`**, occurrence **1 of 2**
- heard: **“لتي”** — initial **م** missing
- repeated verse (lyrics line 3 / aligner line 2): **correct**
- previous word `فِي`: correct; next word `وَاعْتِقَادِي`: correct.

**Measured map (CFG 1.5 vocal stem, Demucs 4.1.0, 44.1 kHz):**

| marker | time |
|---|---|
| aligner box for `مِلَّتِي` | 27.782 – 28.902 (**late; not a cut**) |
| actual word start | **~27.52** |
| `فِي`: /f/ onset / vowel | 27.00 / 27.15–27.48 |
| actual word end | **~28.90** |
| `وَاعْتِقَادِي` onset | **~29.00** |
| comp B (default) | **27.50 – 28.95** |
| comp D (fallback) | **27.00 – 28.95** |
| comp A (historical; **not used**) | 27.10 – 28.95 |
| correct occurrence 2 | aligner 41.423 – 42.244; actual ~**41.13 – 42.55** |

Pitch contour of `مِلَّتِي`: **220 → 247 → /t/ closure → 247 → 221 → 200 Hz**.
The 197 Hz segment before 27.52 is the vowel of `فِي`, not the target word.

Do this once on the VM:

- play **B 27.50–28.95** and **D 27.00–28.95** in a loop; the user confirms
  they contain `مِلَّتِي` and that the **م** is missing;
- play **41.13–42.55** as the correct reference;
- if the local stem is absent, install Demucs and run it:
  `pip install -q "demucs==4.1.0"` then
  `python3 -m demucs -n htdemucs --two-stems=vocals -d cuda \
   -o work/cfg15/stems work/cfg15/repro_abc_cfg15.wav`;
  re-check the same windows.

If the loop does not match the card, stop and re-localize before any GPU batch.

## 2) Batch — re-sing the unit (~5–10 min GPU)

Use the take's **own** token stream (5606 frames). Do not re-derive.

- Create the prefix file from the first **672** tokens (**26.88 s**). This is
  ~120 ms before the /f/ of `فِي`, so the model enters the phrase naturally and
  the same render covers B and D.

```bash
mkdir -p work/cfg15
python3 - <<'PY'
import json
t = json.load(open('work/cfg15/abc_cfg15_semantic.json'))
assert len(t) == 5606, len(t)
json.dump(t[:672], open('work/cfg15/tokens_prefix_672.json', 'w'))
print('prefix', 672, 'of', len(t))
PY
```
- `semantic_min_tokens = semantic_max_tokens = 775` (**31.00 s**). The line ends
  ~30.68 s; this covers it with margin. The comp ends at the candidate's word
  end, not at 31 s.
- Seeds: `3285212580 + 0..3` first. **16 is a ceiling, not a target.**
- **Sequential only.** Use `--request-sequence` or a shell loop that waits for
  each run; never `&`, never two `audiocpp_cli_prefix` processes, and never a
  second model load while the first is alive. Two concurrent GPU runs can OOM a
  T4. Generate **one seed first**; if it succeeds, run the other three
  sequentially.
- Before generation: `free -h`, `nvidia-smi`, `pgrep -af audiocpp_cli`; kill any
  stale process. Do **not** install/run Demucs or SheetSage2 before generation;
  run them after. If Demucs must run first, use `-d cpu` and let it exit.
- Use the prefix-capable binary (`bin/audiocpp_cli_prefix`).

**Request must match the take** (only the prefix + continuation bounds are
added):

```
lyrics   = cases/002_abu01_ajdad/intake/lyrics.txt
style    = cases/002_abu01_ajdad/intake/style.txt
guidance_scale=1.5
cot=full
abc_file=/content/arabmaqamrock/cases/002_abu01_ajdad/abc/score.abc
num_inference_steps=8
context=24576
nar_noise=generated
# sampler: temperature 1, top_p 0.95, top_k 100,
#          repetition_penalty 1.2, penalty_window 50
# end-token bounds for this batch (default floor is 200; set both to 775):
semantic_min_tokens=775
semantic_max_tokens=775
# the take was generated with cap 7250; this batch overrides max to 775
export_semantic=true
LoRA a01 AR/NAR scale=1.0
attention=flash
```

`semantic_min_tokens` is the end-token floor (default 200) and
`semantic_max_tokens` is the hard budget. Set **both to 775**; do not leave the
floor at 200, or the model may stop before 31 s.

**Important:** keep the existing `abc/score.abc` as `abc_file`. Do **not**
replace it with a new transcription of the CFG 1.5 take; that would change the
conditioning and produce a third performance.

Before any coordinate math, check whether the output is the **full timeline**
(0–31 s) or only the **tail after the prefix** (26.88–31 s). If tail-only,
subtract **26.88 s** from every coordinate.

**Memory check — read the log before launching seeds 2–4:**

- `yue2.request ... max_tokens=775` (not 7250, not 5606);
- final `semantic.tokens` = **775**; if the log reports new tokens separately,
  `emitted_tokens` = **103** (775 − 672);
- `truncated 0`.

If the log says 7250 or 5606, stop: the cap/prefix bounds were not applied, and
the run is much longer than intended.

## 3) Demucs + filter (~5–10 min)

Run Demucs **4.1.0 / htdemucs** on every candidate (same version as the take).

Reject a candidate if:

- the initial **/m/** is not audible before the vowel (nasal murmur or
  closure+release); compare with the correct occurrence's /m/ at 41.13–41.20;
- its `مِلَّتِي` ends after **28.98** (would collide with `وَاعْتِقَادِي`);
- its pitch contour differs from **220 → 247 → 247 → 221 → 200 Hz** in the used
  span;
- |Δf0| > 20 cents or |ΔRMS| > 1 dB at the seam;
- a new defect appears.

Do **not** use CTC to distinguish /m/ or to “prove” the consonant. The ear
decides. Keep at most **3** candidates for listening.

## 4) Comp — vocal only (~5 min)

Never use `no_vocals + candidate`. The correct formula is:

```
new_mix = mix + (candidate_vocals − original_vocals)
```

inside the comp region only; compute the difference at 44.1 kHz and resample to
48 kHz.

Prepare two comps from the **same** best candidate:

- **B (default):** candidate’s **/m/ onset (~27.50)** → candidate word end
  (≤28.98). Keeps `فِي` byte-identical. Do not start before ~27.45.
- **D (fallback):** **27.00** → candidate word end. Starts at the /f/ onset of
  `فِي`; replaces one correct word but gives a consonant-word join. Use it if
  B's join is audible.

Do not touch `وَاعْتِقَادِي` — its onset is ~29.00.

Verify and print the numbers:

- outside the comp region: **byte-identical** to the original CFG 1.5 WAV;
- duration unchanged: **224.238667 s**;
- original `فِي` / `وَاعْتِقَادِي` byte-identical where kept;
- no f0/RMS jump at the seam; no click;
- candidate word end ≤28.98.

## 5) Listening — the user decides (~5–10 min)

Prepare:

- `listen/01_line_original.wav` — the opening phrase from the unedited CFG 1.5;
- `listen/02_line_B.wav` — comp B;
- `listen/03_line_D.wav` — comp D;
- then the **full track** for the version the user prefers;
- a **blind A/B**: original vs repaired, random order, key in a text file the
  user does not open until after listening.

Use `IPython.display.Audio` in the notebook and upload the files to GCS.

Do not judge the seam yourself and do not hide a candidate that sounds bad.

If the user hears a seam → **stop**; the original CFG 1.5 take remains the
deliverable. If both are transparent → the user picks B or D.

## 6) Optional — full-track ABC map

If time permits **after** the repair batch, transcribe the full
`repro_abc_cfg15.wav` once with SheetSage2 (`./transcribe.sh`, ~1 min GPU /
~140 s CPU; if the env is missing, `./plumbing/setup_transcribe.sh` or skip) and
store it under `abc_cfg15/`.

Use it only as a **map**: structure, beats, long notes, melody reference for
filtering. Do **not** use its timestamps as cuts and do **not** feed it back as
`abc_file`. Skip it if the repair is transparent or the session is tight.

## 7) Outputs

**GCS** — `gs://akbar-december-2024-backup/arabmaqamrock/runs/<UTC>_repair002_cfg15/`:

```
inputs/      asset hashes + copies of lyrics/style/score
tokens/      abc_cfg15_semantic.json + the 672-token prefix + sha
candidates/  all candidates (WAV + vocals), including rejected ones
comp/        comp.json (points, params, decisions) + B and D
final/       chosen WAV + sha + blind A/B + key
session/     timing.tsv + notes + logs
abc_cfg15/   optional full-track transcription
```

**GitHub** — create `cases/002_abu01_ajdad/RUN3.md`, then commit and push to
`main`:

- the actual timing table vs the 30-minute budget;
- what worked, what failed, and the traps;
- whether “no audible seam” was achieved and how it was judged;
- any change to the comp points or the unit;
- update `CHECKPOINT.md` §6B/§6C/§7 only if the result changes the plan.

## Stop rules

- **G0 fails** (count/duration/sha) → stop; do not re-derive.
- **Generation crashes even with one seed and `max_tokens=775`** → diagnose:
  host RAM OOM (`Killed`, exit 137, Colab “used all available RAM”) vs CUDA OOM
  (`CUDA out of memory`). Try a **high-RAM T4** runtime once; if it repeats, try
  `cot=off` (prefix only) once as a diagnostic. If it still crashes, stop — do
  not grind.
- **4 candidates fail the same way** → widen the window once (earlier start /
  later end), then stop.
- **Audible seam** → stop; the original CFG 1.5 take remains the deliverable.
- **Two rounds** → stop.

## Do not violate

- The original `repro_abc_cfg15.wav` is never modified; all work is on copies.
- No token re-derivation and no full token gate; the tokens exist and are
  verified by count + duration + sha.
- **No parallel GPU runs.** One `audiocpp_cli_prefix` process at a time; seeds
  are sequential. Two concurrent runs can OOM a T4.
- **No Demucs or ABC transcription during generation.** Do them after the
  generation process exits; Demucs on CPU if RAM is tight.
- No donor splice from the correct occurrence (41.13–42.55); it is a reference
  only.
- No new ABC transcription as `abc_file`; the batch keeps
  `cases/002_abu01_ajdad/abc/score.abc`.
- No fixed cut point; the seam follows the candidate's own word end, ≤28.98.
- No cut inside `فِي` or `وَاعْتِقَادِي`.
- No `no_vocals + candidate`.
- No judging from the isolated 1.4 s word; listen to the whole opening phrase,
  then the full track.
- If the user hears a seam, do not deliver the repair; keep the original.

**Start with Step 0. Show the asset table, then wait for approval.**
