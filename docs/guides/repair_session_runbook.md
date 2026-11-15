# Repair Session Runbook

## Fixing one or two mispronounced words in a generated take

> The take is the asset. The repair is a composite, not a new performance.
> The aligner finds the word; the ear decides the defect; the tools narrow the
> search and execute the edit.

**Version:** 1.0 — 2026-11-15

**Status:** proven on the first clean run
([`cases/002_abu01_ajdad/RUN3.md`](../../cases/002_abu01_ajdad/RUN3.md):
`مِلَّتِي`, 26 min machine / 39 min wall).

**Companion:** [Fixing Mispronunciations in AI Music](fixing_ai_music_mispronunciations.md)
(the field guide: principles, evidence, failure modes).

> **Baghdad Moon is historical.** It was the learning case, not the reference.
> Its old handoff documents remain for evidence, but do not follow them as the
> current procedure. The current reference is RUN3 / case 002.

---

## How to use this document

- **Before the session:** read §1–§3 and fill the intake sheet.
- **During the session:** follow §5 one phase at a time. Fill the record in §4.
- **After the session:** §6 closes the case. The filled record is the template
  for the next song.
- **If a rule conflicts with what you hear:** the ear wins. Change the rule only
  after the session, with a note and a measurement.

The motion in one block:

```
listen → collect defects → G0 token check → defect card → approve unit
→ one batch (4 seeds, one process) → filter → audition → comp
→ verify → full listen → package → close
```

### One-screen checklist

```
[ ] Exact take hashed; original frozen
[ ] Tokens exist for this take; count + duration + sha match (G0)
[ ] Defect card filled for each occurrence
[ ] Vocal stem isolated on the same timebase as the comp
[ ] Unit proposed; 2–4 s loop approved by ear
[ ] Prefix built from the take's own tokens
[ ] One process; seeds sequential; 4 seeds first
[ ] Log checked: prefix 672, min=max=775, tokens 775 (truncated 1 expected)
[ ] Demucs after generation; candidates filtered
[ ] Take picked by ear
[ ] Vocal-only diff comp; B and D from the same candidate
[ ] Outside-diff = 0; duration unchanged; click ratio low
[ ] Full section / full track listened; blind A/B
[ ] Record, manifest, checksums, sidecar written
```

---

## 1. The deal

This runbook is:

- **one case = one take**; do not mix takes in a case;
- one existing take, preserved;
- one or more named words, fixed in one pass;
- a deterministic composite: outside the changed spans, the final is
  byte-identical to the original;
- one GPU session if the take has exported tokens.

It is **not**:

- a new full generation;
- a donor splice from another take;
- a reason to replace a correct held note;
- a licence to fix by ear without verification.

The four human gates:

1. the defect card (what was heard, which occurrence);
2. the unit/strategy (where the comp starts and ends);
3. the take pick (which candidate);
4. the final listen (full section/track, blind A/B).

Everything else is mechanical.

---

## 2. What the reference run proved

| claim | evidence |
|---|---|
| G0 can be 7 s | 5606/25 = 224.24 s, WAV/tokens hashes match; no re-derive |
| one process is memory-safe | one `audiocpp_cli_prefix` at a time; ~6.7 GiB host RAM on a 12 GiB T4; no crash |
| four seeds are enough | four re-sang within 30–40 ms; s2/s3 had the dark nasal onset; s2 chosen |
| one render covers B and D | prefix 672 → max 775; same candidate, two comp widths |
| the unit follows the candidate | card said 27.50; s2's /m/ starts ~27.45; comp used 27.46 |
| a consonant onset is not a steady-vowel join | s2: 140 cents / −4.4 dB, click ratio 0.29; ear accepted |
| outside-diff can be zero | final byte-identical outside 27.46–28.98; duration unchanged |

The full numbers are in `RUN3.md` §1–§5.

---

## 3. Roles

| role | owns | does not own |
|---|---|---|
| human | defect card, unit approval, take pick, final verdict | technical commands |
| agent/tool | hashes, alignment, measurement, generation, comp, verification | whether the seam is audible |
| both | stop rules and acceptance | “it sounds fine” without a measurement |

The agent must ask only: **“Do you hear a seam?”** or **“Which version is
better?”** Do not ask the user to choose sample rates, prefixes or fades.

---

## 4. The repair record

Fill this once per case; it is the handoff and the audit trail.

```
Case / take:
Original WAV + sha256:
Duration / sample rate / channels:
Tokens + sha256 + frame count:
Model / LoRA / binary / GPU:
Seed / sampler / guidance / steps / context:
Defect word / occurrence / heard / target:
Aligner box:
Measured word start / end:
Previous word / next word:
Prefix tokens / prefix seconds:
min_tokens / max_tokens:
Candidates / chosen candidate:
Comp region / ramps:
Outside max abs diff:
Duration unchanged:
Click ratio / envelope:
Verdict / who heard it / scope:
```

---

## 5. The protocol

### Phase 0 — Intake and G0 (tool, ~1 min)

1. Hash the WAV; freeze the original.
2. Confirm the tokens exist and are this take's:
   ```
   len(tokens) / 25 ≈ duration_s
   sha256(tokens) == recorded
   sha256(wav) == recorded
   ```
3. If tokens are missing, stop. Re-derive is a separate foundation test and can
   fail across GPU architectures; see the guide §3.3.
4. Record the run dir and the G0 numbers.

### Phase 1 — Localize (tool + human, ~5–10 min)

1. Listen to the whole track once; collect all defects before editing.
2. For the target, align the CFG/new take with the same lyrics. The aligner is
   an **index**, not a cut.
3. Demucs 4.1.0 `htdemucs` (or the version that produced the original stems).
4. Measure on the vocal stem:
   - f0 / RMS / spectral centroid / low-band share;
   - consonant closure/burst (for a final consonant) or nasal onset (for /m/);
   - word end, next-word onset, held note.
5. Write the card; approve the unit with a 2–4 s loop.

**Opening defect?** Use the intro as prefix if it exists. If the defect is the
first vocal sound and there is no prefix, the left edge is the file start; judge
the whole opening.

### Phase 2 — Generate (tool, ~5–10 min GPU)

1. Build the prefix from the take's own tokens:
   ```
   prefix = tokens[:round(unit_start_s × 25)]
   ```
   RUN3: 672 tokens = 26.88 s (120 ms before the /f/ of `فِي`).
2. Set `semantic_min_tokens = semantic_max_tokens = round(gen_end_s × 25)`.
   RUN3: 775 = 31.00 s (line ends ~30.68).
3. Same request as the take: `guidance_scale`, `cot`, `abc_file`,
   `num_inference_steps`, `context`, `nar_noise`, sampler, LoRA, attention.
4. **One process, all seeds in one `--request-sequence`.** 4 seeds first; 16 is
   a ceiling. No `&`, `xargs -P`, GNU parallel, or two notebook cells.
5. Before every seed: `pgrep -af audiocpp_cli` must show at most one process.
6. Read the log before the next seed:
   ```
   semantic_prefix_frames=672
   min_tokens=775 max_tokens=775
   semantic.tokens 775
   truncated 1   ← expected when min=max
   ```
7. Do not run Demucs or the optional ABC before/during generation.

### Phase 3 — Filter (tool + human, ~5 min)

1. Demucs each candidate.
2. Measure per candidate:
   - word onset/end on its own stem;
   - f0 contour;
   - spectral centroid / low-band share at the consonant onset;
   - lag vs the original.
3. Reject if:
   - the word end passes the next word onset;
   - the contour differs from the original in the used span;
   - a new defect appears;
   - the consonant onset is not darker/nasal where it should be.
4. Keep at most 3–5 for listening. Do not select on envelope correlation alone;
   it hides wrong pitch.

### Phase 4 — Comp (tool, ~5 min)

1. Vocal-only diff:
   ```
   new_mix = mix + (candidate_vocals − original_vocals)
   ```
   inside the region; difference at 44.1 kHz, resample to 48 kHz.
2. Never `no_vocals + candidate`.
3. Boundaries:
   - **B (default):** candidate consonant onset → candidate word end; keep the
     previous word.
   - **D (fallback):** previous word onset → candidate word end; replaces one
     correct word but may give a cleaner consonant join.
4. 15 ms ramps on the difference; no long crossfade.
5. Remember: the prefix region is not bit-identical; comp only after the region
   you measured.

### Phase 5 — Verify and listen (tool + human, ~5–10 min)

1. Print:
   - final sha256; duration; sample rate; channels;
   - outside max abs diff = 0;
   - 10 ms envelope across the seam; click ratio;
   - candidate word end < next word onset;
   - kept melisma/final note intact.
2. Prepare:
   - `01_line_original.wav`;
   - `02_line_B.wav`;
   - `03_line_D.wav`;
   - the full track for the chosen version;
   - blind A/B (original vs repaired, random order, key hidden).
3. Ask only: **“Do you hear a seam?”** / **“Which is better?”**
4. If the user hears a seam → stop; the original stays.
5. Record the scope: opening/02 vs full track.

### Phase 6 — Package and close (tool + human, ~5 min)

Store under the run's GCS folder:

```
inputs/      WAV + token + lyrics/style/score
tokens/      full tokens + prefix + sha
candidates/  all candidates (WAV + vocals), including rejects
comp/        comp.json + B/D + verify_*.json
final/       chosen WAV + sha + sidecar + blind A/B + key
session/     timing.tsv + notes + logs
```

Write/update the case report (`RUN<n>.md`) with:

- actual timing vs the 30-minute budget;
- what worked/failed/traps;
- the acceptance table;
- the exact comp points and token bounds;
- what to script next.

---

## 6. Failure branches

| branch | action |
|---|---|
| G0 fails (count/duration/sha) | stop; wrong token file; do not re-derive blindly |
| tokens missing | re-derive gate is a separate session; if it fails, stop |
| one seed crashes / OOM | check host vs CUDA OOM; high-RAM once; `cot=off` once; stop |
| log says 7250/5606 | bounds not applied; stop before more seeds |
| all seeds miss the phoneme | one phonetic respelling / one wider unit; then stop |
| candidate word end collides with next word | reject; widen or choose another seed |
| audible seam | stop; original stays |
| f0/RMS step is large at a consonant onset | expected; judge by envelope/click/ear |
| user identifies the repaired file in blind A/B | not transparent; stop/iterate |

---

## 7. Timing and token math

```
frames      = seconds × 25
prefix      = round(unit_start_s × 25)
max         = round(gen_end_s × 25)
min         = max
tokens      = max (this binary reports total, not new)
truncated   = 1 when min=max (expected)
```

RUN3:

```
prefix 672  = 26.88 s
max    775  = 31.00 s
line end   ~30.68 s
comp B     27.46–28.98 s
```

Budget:

| phase | human | machine |
|---|---:|---:|
| intake/card | 5–8 min | 2–3 min |
| G0 | — | 30 s |
| generation (4 seeds) | 2–5 min | 7–12 min |
| filter | 3–5 min | 2–3 min |
| comp + verify | 5–8 min | 1 min |
| listen | 5–10 min | — |
| **total** | **20–25 min** | **~26 min** |

The first process pays the model load (~5 min). All seeds in one process cost
~45 s per extra seed after the first. Splitting seeds across two processes costs
another load.

---

## 8. Case folder layout

```
cases/<case>/
  README.md
  RUNBOOK.md
  CHECKPOINT.md
  RUN2.md, RUN3.md, ...
  intake/
    defect_card.md
    words.json
    measure.json
    hashes.txt
  spec/
    repair_spec.json
  scripts/
    comp_vocal_diff.py
    measure_word.py
    onset_table.py
    verify_seam.py
  review/
    gaps.png
    clips...
```

The audio, stems, tokens and candidates live in the run folder on GCS, not in
git. Keep the scripts and the manifest in git.

---

## 9. Command cheat sheet (local token model)

```bash
# 0. G0
python3 - <<'PY'
import json, wave, hashlib
w = wave.open('work/cfg15/repro_abc_cfg15.wav')
print('duration', w.getnframes()/w.getframerate())
t = json.load(open('work/cfg15/abc_cfg15_semantic.json'))
print('tokens', len(t), '->', len(t)/25)
PY

# 1. prefix
python3 - <<'PY'
import json
t = json.load(open('work/cfg15/abc_cfg15_semantic.json'))
assert len(t) == 5606
json.dump(t[:672], open('work/cfg15/tokens_prefix_672.json', 'w'))
PY

# 2. generation (one process; all seeds in the request sequence)
. ./cuda_loader_path.sh
./bin/audiocpp_cli_prefix --task gen --family yue2 \
  --model models/Yue2-3B-GGUF --backend cuda --threads 8 \
  --request-sequence work/cfg15/req_seeds.json \
  --out-dir work/cfg15/cand --log

# 3. Demucs (after generation)
pip install -q "demucs==4.1.0"
python3 -m demucs -n htdemucs --two-stems=vocals -d cuda \
  -o work/cfg15/stems work/cfg15/cand/s2_3285212582.wav

# 4. comp (vocal-only diff)
python3 cases/002_abu01_ajdad/scripts/comp_vocal_diff.py \
  --orig-mix work/cfg15/repro_abc_cfg15.wav \
  --orig-voc work/cfg15/stems/htdemucs/repro_abc_cfg15/vocals.wav \
  --cand-voc work/cfg15/stems/htdemucs/s2_3285212582/vocals.wav \
  --start 27.46 --end 28.98 --cand-offset 0 \
  --out work/cfg15/comp/B_s2.wav

# 5. verify
python3 cases/002_abu01_ajdad/scripts/verify_seam.py \
  work/cfg15/comp/B_s2.wav \
  work/cfg15/stems/htdemucs/repro_abc_cfg15/vocals.wav \
  work/cfg15/stems/htdemucs/s2_3285212582/vocals.wav \
  27.46 28.98 B_s2
```

---

## 10. Glossary

- **G0:** token consistency check (count + duration + sha), not a render.
- **Prefix:** the token sequence before the generated unit.
- **B / D:** comp widths — word-onset join vs previous-word onset join.
- **Comp:** local audio splice; vocal-only diff.
- **Click ratio:** seam sample step relative to the max step inside the region.
- **Spectrum centroid:** brightness of a short spectrum; useful for nasal onset.
- **`truncated 1`:** expected when `min=max`; not a failure.

---

*Runbook v1.0. If you remember one line: **G0, one process, four seeds, measure
the unit, comp the vocal only, and let the ear decide.***
