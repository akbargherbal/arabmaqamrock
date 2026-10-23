# PLAN — case 001: fix `فَأَدُّوهَا إِلَيْنَا`

**Goal:** one GPU session on Colab, one pronunciation error, the simplest route
first. If the wide route works, stop. If not, narrow one level.

**Principle:** the guide's "smallest unit" is a default, not a law. We start
with the **whole phrase** because it is easier, it has the cleanest joins, and
the user prefers it. We narrow only when the wider comp fails. The ear decides;
the rules are hypotheses until this take tests them.

---

## 1. The ladder

| level | comp (s) | what is replaced | joins | when |
|---|---|---|---|---|
| **L1 — phrase** | **126.60 – 129.18** | `فَأَدُّوهَا إِلَيْنَا`, including the continuous note | gap before, breath after | **first** |
| **L2 — word** | 126.60 – 127.72 | `فَأَدُّو`; keeps the original `هَا + إِلَيْنَا` note | gap before, note start after | if L1 fails |
| **L3 — syllable** | 127.18 – 127.65 | `دُّو` (closure + release + vowel) | closure before, release after | if L2 fails |

**Why L2 stops at 127.72:** `هَا` and `إِلَيْنَا` are one continuous note
(415→465 Hz from 127.76, descending to ≈368 Hz at 129.15). Cutting between the
words would cut inside that note. L2 keeps the whole note and replaces only the
run-up.

**Why L3 is the floor:** a single consonant cannot be comped on its own; it has
no pitch and no duration. The smallest stable unit is the syllable `دُّو`
(0.47 s), with the joins in the closure and the release. This is the
"microscopic" level.

**The three levels use the same render.** The model sings the whole phrase once;
we then comp a wider or narrower span of that same candidate. No new generation
between levels.

---

## 2. What the user hears

```text
L1: 3 shortlisted candidates, each on the full line (123.00–129.20)
      if one passes -> pick it, done
      if all fail   -> L2
L2: 2–3 candidates, same full line
      if one passes -> pick it, done
      if all fail   -> L3
L3: 1–2 candidates, same full line
      if one passes -> pick it, done
      if all fail   -> stop; change the route (respelling / donor / new take)
```

At most **6–8 listens**, and the session stops at the first success. The agent
filters the 8 raw candidates down before the user hears anything: f0, duration,
closure, CTC presence, edge steps. The user never hears the rejects.

---

## 3. The gate before any edit: tokens

This take was generated **without `export_semantic`**, so there is no token
stream. The prefix route needs the exact 5938-frame stream. Before any repair:

1. re-derive the semantic stream (AR only, ≈5.5 min);
2. render the full song from those tokens with `min=max=5938` (NAR+VAE,
   ≈4 min);
3. compare the WAV sha256 to `3981465c…`.

**Pass:** the tokens are the take's tokens; the ladder starts.
**Fail:** stop. Record the hash and the log fingerprints. Do not edit an
unproven stream.

Cheap checks first (from the re-derive log): `positive_prefix_tokens 1020`,
`negative_prefix_tokens 12`, `semantic.tokens 5938`, `truncated 0`.

---

## 4. Colab runbook (copy-paste)

### 4.1 Provision

```bash
cd /content
git clone https://github.com/akbargherbal/arabmaqamrock.git
cd arabmaqamrock
gcloud auth login
export HF_TOKEN=...                 # if needed
./setup_colab.sh                    # model + LoRA + the unpatched prebuilt
```

Stage the prefix-capable binary (do **not** overwrite `bin/audiocpp_cli`):

```bash
gsutil cp gs://akbar-december-2024-backup/arabmaqamrock/runs/20261019_baghdad_moon_token_surgery/bin/audiocpp_cli_prefix_sm75 \
  bin/audiocpp_cli_prefix
chmod +x bin/audiocpp_cli_prefix
sha256sum bin/audiocpp_cli_prefix     # 4e1534f3e6fde456198ed5404313a832029193bf7ea47c817086a24a5aa3849c
. ./cuda_loader_path.sh
```

### 4.2 Freeze the take

```bash
CASE=cases/001_harith03_faadduha
W=$CASE/work
mkdir -p $W/{inputs,rederive,candidates,stems,qc,output,review}
gsutil cp "gs://akbar-december-2024-backup/arabmaqamrock/runs/20261022-185953_harith_bin_hiliza_singing-techniques_formatted/03-الرد-على-الواشي-والرسوخ-كالأرعن_3_810750224.wav" \
  $W/inputs/ORIGINAL.wav
sha256sum $W/inputs/ORIGINAL.wav      # 3981465c…
```

### 4.3 Re-derive the tokens

```bash
cd /content/arabmaqamrock
BIN=./bin/audiocpp_cli_prefix
OUT=$W/rederive
"$BIN" --task gen --family yue2 --model models/Yue2-3B-GGUF --backend cuda --threads 8 \
  --session-option yue2.model_gguf=yue2-3b-bf16.gguf \
  --session-option yue2.vae_gguf=yue2-vae-f16.gguf \
  --session-option yue2.ar_lora=/content/arabmaqamrock/loras/arabmaqamrock-v3-ar.safetensors \
  --session-option yue2.ar_lora_scale=1.0 \
  --session-option yue2.nar_lora=/content/arabmaqamrock/loras/arabmaqamrock-v3-nar.safetensors \
  --session-option yue2.nar_lora_scale=1.0 \
  --session-option yue2.attention=flash \
  --lyrics "$(cat $CASE/intake/lyrics.txt)" \
  --request-option style="$(cat $CASE/intake/style.txt)" \
  --request-option cot=off \
  --request-option semantic_max_tokens=6750 \
  --request-option export_semantic=true \
  --request-option stop_after=semantic \
  --seed 810750224 \
  --out "$OUT/semantic_only.wav" --out-dir "$OUT/artifacts" --log

grep -E 'positive_prefix_tokens|negative_prefix_tokens|semantic.tokens|truncated' $OUT/*.log
# expect 1020 / 12 / 5938 / 0

python3 - <<PY
import json, glob
src = sorted(glob.glob('$OUT/**/*semantic*.json', recursive=True))
assert len(src) == 1, src
d = json.load(open(src[0]))
tok = d if isinstance(d, list) else d['tokens']
assert len(tok) == 5938, len(tok)
json.dump(tok, open('$OUT/tokens_baseline.json', 'w'))
print('frames', len(tok))
PY
```

### 4.4 Prove bit-identity

```bash
TOK=$W/rederive/tokens_baseline.json
"$BIN" --task gen --family yue2 --model models/Yue2-3B-GGUF --backend cuda --threads 8 \
  --session-option yue2.model_gguf=yue2-3b-bf16.gguf \
  --session-option yue2.vae_gguf=yue2-vae-f16.gguf \
  --session-option yue2.ar_lora=/content/arabmaqamrock/loras/arabmaqamrock-v3-ar.safetensors \
  --session-option yue2.ar_lora_scale=1.0 \
  --session-option yue2.nar_lora=/content/arabmaqamrock/loras/arabmaqamrock-v3-nar.safetensors \
  --session-option yue2.nar_lora_scale=1.0 \
  --session-option yue2.attention=flash \
  --lyrics "$(cat $CASE/intake/lyrics.txt)" \
  --request-option style="$(cat $CASE/intake/style.txt)" \
  --request-option cot=off \
  --request-option semantic_prefix_file="$TOK" \
  --request-option semantic_min_tokens=5938 \
  --request-option semantic_max_tokens=5938 \
  --seed 810750224 \
  --out "$W/rederive/baseline.wav" --out-dir "$W/rederive/artifacts" --log
sha256sum $W/rederive/baseline.wav     # must equal 3981465c…
```

**Stop here if it does not match.** Write the actual hash in `record.md`.

### 4.5 Build the prefix

```bash
python3 - <<PY
import json
tok = json.load(open('$W/rederive/tokens_baseline.json'))
assert len(tok) == 5938
json.dump(tok[:3161], open('$W/rederive/tokens_prefix_3161.json', 'w'))
print('prefix 3161 =', 3161/25, 's')
PY
```

### 4.6 Render one batch of 8

Prefix **3161** (126.44 s, the note offset — the model starts in the 0.36 s gap
and sings the phrase naturally). `max=3250` (130.00 s) covers L1's end and the
breath, with trailing context.

```bash
python3 - <<PY
import json, os
base = 810750224
lyr = open('$CASE/intake/lyrics.txt').read()
sty = open('$CASE/intake/style.txt').read()
reqs = []
for k in range(8):
    reqs.append({
        "id": f"c001_s{k:02d}",
        "lyrics": lyr,
        "seed": base + k,
        "options": {
            "style": sty,
            "cot": "off",
            "semantic_prefix_file": os.path.abspath('$W/rederive/tokens_prefix_3161.json'),
            "semantic_min_tokens": 3250,
            "semantic_max_tokens": 3250,
            "export_semantic": True,
        },
    })
json.dump(reqs, open('$W/candidates/requests.json', 'w'), ensure_ascii=False, indent=1)
print(len(reqs), 'requests')
PY

"$BIN" --task gen --family yue2 --model models/Yue2-3B-GGUF --backend cuda --threads 8 \
  --session-option yue2.model_gguf=yue2-3b-bf16.gguf \
  --session-option yue2.vae_gguf=yue2-vae-f16.gguf \
  --session-option yue2.ar_lora=/content/arabmaqamrock/loras/arabmaqamrock-v3-ar.safetensors \
  --session-option yue2.ar_lora_scale=1.0 \
  --session-option yue2.nar_lora=/content/arabmaqamrock/loras/arabmaqamrock-v3-nar.safetensors \
  --session-option yue2.nar_lora_scale=1.0 \
  --session-option yue2.attention=flash \
  --request-sequence $W/candidates/requests.json \
  --out-dir $W/candidates --log
```

Gate: every candidate exists and is ≥ 129.18 s long (through L1's comp end).

### 4.7 Demucs and score

Use the same Demucs model for the original and every candidate.

```bash
mkdir -p $W/scripts
cp docs/happy_accidents/Baghdad_Moon/token_surgery/scripts/comp_region.py \
   docs/happy_accidents/Baghdad_Moon/token_surgery/scripts/verify_final.py $W/scripts/

demucs --two-stems=vocals -n htdemucs -d cuda -o $W/stems $W/inputs/ORIGINAL.wav
for f in $W/candidates/c001_s*.wav; do
  demucs --two-stems=vocals -n htdemucs -d cuda -o $W/stems "$f"
done
```

The agent writes a case-local `score_case.py` from the metric table below; the
reference `score_*` scripts have Baghdad's windows hard-coded and must not be
edited.

Score on the **comp window only**:

| metric | L1 | L2 | L3 |
|---|---|---|---|
| f0 contour | 126.79–129.18, 311→355→370→415→465→368 Hz, ±20 cents | 126.79–127.72, 311→355→370 | 127.28–127.60, 370 Hz |
| duration | phrase 2.36 s ±15 % | run-up 0.93 s ±20 % | syllable 0.47 s ±20 % |
| closure | 80–160 ms | 80–160 ms | 80–160 ms |
| onset/end | phrase start/end within ±60 ms | note start Δ ≤ +60 ms | closure aligned within ±20 ms |
| CTC | `فَأَدُّوهَا` present | same | same |
| edge | < 1 dB | < 1 dB | < 1 dB |

Shortlist **3** by a combined rank: f0 first, then closure, then timing.

### 4.8 Comp the ladder from the tails (audition)

`comp_region.py` asserts that the candidate and the original have the same
shape. The tails are 130 s; the take is 237.5 s. Pad each shortlisted tail with
silence to the take's length before comping. The comp region is inside the first
130 s, so the padding never reaches the output. (The final comp in 4.9 uses a
full-length render and needs no padding.)

```bash
python3 - <<PY
import soundfile as sf, numpy as np, glob
orig, sr = sf.read('$W/inputs/ORIGINAL.wav', dtype='int16', always_2d=True)
for p in sorted(glob.glob('$W/candidates/c001_s*.wav')):
    y, sr2 = sf.read(p, dtype='int16', always_2d=True)
    assert sr2 == sr
    if len(y) < len(orig):
        y = np.pad(y, ((0, len(orig) - len(y)), (0, 0)))
    out = p.replace('.wav', '_padded.wav')
    sf.write(out, y, sr, subtype='PCM_16')
    print(out)
PY
```

Build **L1 first** for the three shortlisted seeds. The user hears them on
`01_*_line`. If none passes, build L2 from the same seeds, then L3. Stop at the
first accepted level.

```bash
# example: seed s03, L1
python3 $W/scripts/comp_region.py \
  $W/inputs/ORIGINAL.wav $W/candidates/c001_s03_padded.wav $W/output/audition_L1_s03.wav \
  --mode vocal --orig-stems $W/stems/htdemucs/ORIGINAL \
  --cand-stems $W/stems/htdemucs/c001_s03 \
  --start 126.60 --end 129.18 --fade-in 0.03 --fade-out 0.06 --gain-ramp
```

For L2 use `126.60–127.72` and `0.03/0.04`; for L3 use `127.18–127.65` and
`0.01/0.015`. Use `--shift-ms` if the phrase is late/early (≤ ±60 for L1/L2,
≤ ±20 for L3). Do not time-stretch.

### 4.9 Full-render the picked seed, rebuild the accepted level

The tail comps choose the **seed and the level**. The final comes from a full
render of that seed.

```bash
mkdir -p $W/winner
python3 - <<PY
import json, os
req = {
  "id": "c001_win",
  "lyrics": open('$CASE/intake/lyrics.txt').read(),
  "seed": WINNER_SEED,                      # replace with the picked seed
  "options": {
    "style": open('$CASE/intake/style.txt').read(),
    "cot": "off",
    "semantic_prefix_file": os.path.abspath('$W/rederive/tokens_prefix_3161.json'),
    "semantic_min_tokens": 5938,
    "semantic_max_tokens": 5938,
    "export_semantic": True,
  },
}
json.dump([req], open('$W/winner/request.json', 'w'), ensure_ascii=False, indent=1)
PY

"$BIN" --task gen --family yue2 --model models/Yue2-3B-GGUF --backend cuda --threads 8 \
  --session-option yue2.model_gguf=yue2-3b-bf16.gguf \
  --session-option yue2.vae_gguf=yue2-vae-f16.gguf \
  --session-option yue2.ar_lora=/content/arabmaqamrock/loras/arabmaqamrock-v3-ar.safetensors \
  --session-option yue2.ar_lora_scale=1.0 \
  --session-option yue2.nar_lora=/content/arabmaqamrock/loras/arabmaqamrock-v3-nar.safetensors \
  --session-option yue2.nar_lora_scale=1.0 \
  --session-option yue2.attention=flash \
  --request-sequence $W/winner/request.json --out-dir $W/winner --log

demucs --two-stems=vocals -n htdemucs -d cuda -o $W/stems $W/winner/c001_win.wav
```

Check causality: the winner's tokens `[3161, 3250)` must equal the tail's. If
not, the seed or sampler changed — stop.

Then comp the accepted level from the full render:

```bash
# example: L1
python3 $W/scripts/comp_region.py \
  $W/inputs/ORIGINAL.wav $W/winner/c001_win.wav $W/output/FINAL.wav \
  --mode vocal --orig-stems $W/stems/htdemucs/ORIGINAL \
  --cand-stems $W/stems/htdemucs/c001_win \
  --start 126.60 --end 129.18 --fade-in 0.03 --fade-out 0.06 --gain-ramp
```

### 4.10 Verify the accepted take

```bash
python3 $W/scripts/verify_final.py \
  $W/output/FINAL.wav $W/inputs/ORIGINAL.wav 126.60:129.18   # L1; use 127.72 for L2, 127.65 for L3
# expect: outside max abs diff 0, VERDICT PASS
```

Also check: edge steps < 1 dB; duration unchanged; f0 at the joins; local
re-align 122–130 s (`إِلَيْنَا` did not move). Full-section listen before
calling it done.

### 4.11 Package

`output/`, `qc/`, `MANIFEST.json`, `CHECKSUMS.sha256`, a reproduce script, and
the filled `record.md`. Mirror to GCS:

```
gs://akbar-december-2024-backup/arabmaqamrock/runs/20261023_harith03_faadduha/
```

---

## 5. Time

| step | GPU |
|---|---|
| re-derive tokens | ~5.5 min |
| bit-identity render | ~4 min |
| 8-candidate batch (130 s each) | ~18–22 min |
| full render the winner | ~6 min |
| Demucs + score | ~8 min |
| pad tails + audition comps (3 seeds x 3 levels worst case) | ~3 min CPU |
| comps + verify | ~2 min |
| **total** | **~46 min** |

The user's listening: 3 clips at L1; more only if L1 fails.

---

## 6. If all three levels fail

Do **not** grind 20 more seeds. Change one variable:

1. **Text:** respell the geminate in the render's lyric only (`فَأَدّ دُوهَا` or
   a phonetic hint), keeping the published lyric correct. One new batch of 8.
2. **Donor:** the same take's correct `دّ` in `حُدِّثْتُمُوهُ` (176.0–177.8 s).
   Only if phoneme + pitch + duration + level match; the reference run's donor
   attempts mostly failed.
3. **Regenerate the take.** If the song is not precious, this is cheaper.

Stop after two rounds per level. Record which level failed and why.

---

## 7. What this tests

The guide says "replace less"; the user says "start wide, narrow only if
needed". This case is the test:

- If L1 passes, the phrase-first workflow is the fast path, and the guide's
  rule is a fallback, not a starting point.
- If L1 fails but L2 passes, the note was the problem; the word is the unit.
- If only L3 passes, the defect really is microscopic and the ladder earned its
  keep.
- If all fail, the route is wrong (text/donor/new take), not the seed count.

The result goes into `record.md` and, if it contradicts the guide, into the
guide — with the measurement, not an opinion.
