# CHECKPOINT — Baghdad Moon B two-word repair

**Last updated:** 2026-10-20 ~11:20 UTC
**Read this first on a fresh runtime.** It supersedes the "pending" wording in
`RESTORE.md` §5 and `HANDOFF.md` §0/§7.

GCS root:
`gs://akbar-december-2024-backup/arabmaqamrock/runs/20261019_baghdad_moon_token_surgery/`

Original WAV (never modified):
`dbc00722534d5ee763ae54a048cd704eaa4c927e37834cd54542eaf379e0de42`

---

## 1. Where we are

| stage | state |
|---|---|
| restore (repo, model, VAE, LoRAs, binary) | **done**, all hashes verified |
| gate 1 — semantic re-run | **passed exactly** (`1b1aa3e2…`, 5397, 1079/12) |
| gate 2 — full baseline render | **passed exactly** (`dbc00722…`) |
| 13 token-splice candidates rendered | **done** (one batch, all 5397 frames) |
| local-comp hybrids (surgical delivery) | **done** (bit-identical outside edits) |
| listening pack + Arabic scorecard | **done**, handed to the user |
| human listening evaluation, round 1 | **done** — 0/4 accepted (`rating_20261020-1223.md`) |
| delivery bug: comp grafted only changed frames | **found + fixed** (`--word-ranges`) |
| word 1 — **fixed** by AR re-sing (seed s03) | **done**, passes by ear |
| word 2 — donor splice rejected; AR tail sweep | **done** (16 seeds); 5 audition seeds in `listen_v4/` |
| final assembly (`FINAL_*.wav`) | pending the user's e2 pick |
| final report polish / GitHub update | pending after selection |

Nothing is lost if Colab disconnects: every WAV, token file, log, metric and
script is in GCS and/or GitHub (see §4).

---

## 2. Verified facts from this session

- The prefix-capable sm75 binary runs on the T4: `git 58caf774`, sha256
  `4e1534f3e6fde456198ed5404313a832029193bf7ea47c817086a24a5aa3849c`.
- Gate 1: `stop_after=semantic`, original recipe → semantic.json is
  **byte-identical** to `1b1aa3e2…`, 5397 frames,
  `positive_prefix_tokens 1079`, `negative_prefix_tokens 12`, `truncated 0`.
- Gate 2: `semantic_prefix_file=tokens_baseline.json`, `min=max=5397` →
  WAV **bit-identical** `dbc00722…`.
- Batch control: the same baseline tokens through `--request-sequence` are also
  **bit-identical** (`runs/token_surgery/batch_control/`). Batch mode is exact.
- Every one of the 13 candidates exported a `semantic.json` identical to its
  input token file.
- **Token surgery is not waveform-local.** Changing even 8 of 5397 frames
  changes every sample (the NAR flow is globally coupled). Measured:
  median mel Δ **outside** the edited words 0.034–0.071 dB, p95 0.33–0.82 dB;
  the peak 1 s mel Δ lands exactly on the edited second.
- **YuE2 has no repaint/edit mode** (verified in the audio.cpp YuE2 docs: only
  `semantic_prefix` continuation). The generic `--repaint-*` flags belong to
  other model families.
- **Generic audio inpainting is unsuitable** (diffusion inpainting fills
  ≤300 ms gaps unconditionally; it cannot choose the phoneme).
- The viable method is a **local comp**: synthesise the corrected word with the
  model, then graft only that word's time range back into the original
  (`audio_splice.py`, 40 ms crossfades on quiet points). Samples outside the
  graft regions are **bit-identical** to the original.

### Evaluation evidence (honest)

- **e2 `فَإِنَّ` is well supported.** MFCC-DTW to the known-correct B Verse 2
  donor: original **5.24** → `e2_B_word` **3.54**, `e2_A_onset` **3.58**.
  Wrong donors (A/C Outro) score **5.74–5.88**, so the metric discriminates.
- **e1 `عَلَيْهِ` is weaker evidence.** Donor is the Outro (different
  arrangement), so DTW is confounded: original 4.482, `e1_A_note` 4.459,
  `e1_B_word` 4.726.
- **CTC cannot confirm a single consonant.** Phrase-level CTC separates the
  known good/bad instances, but every e2 candidate still transcribes `ب` in the
  phrase window. Do not use CTC alone to accept/reject.
- See `report.md` for the full 13-candidate table.

---

## 3. What was delivered for listening

Five versions, each an **11.1 s montage** containing both error spots at the
same absolute times:

| id | e1 edit | e2 edit | notes |
|---|---|---|---|
| `H0_original` | — | — | reference (e1 ends م, e2 starts ب) |
| `H1_minimal` | final note (8 fr) | onset (13 fr) | least change |
| `H2_e2word` | final note | first 26 fr | stronger `فَإِنَّ` |
| `H3_e1word` | whole word (31 fr) | onset | stronger `عَلَيْهِ` |
| `H4_bothword` | whole word | first 26 fr | strongest, most change |

Montage timing (identical for all versions): **e1 word 2.1–3.4 s**,
gap, **e2 word 7.4–9.6 s**. The Outro's third, muddy `عَلَيْهِ` was **not**
edited.

Arabic scorecard (12 questions, plain-language, validated against the rating app):

```
/content/scorecard_baghdad_moon_two_word.json
```

---

## 4. Artifacts and where they live

### GCS (`$B = gs://akbar-december-2024-backup/arabmaqamrock/runs/20261019_baghdad_moon_token_surgery`)

| path | contents |
|---|---|
| `bin/` | prefix binary + sha256 + manifest + build log |
| `gates/gate_semantic_20261020/` | gate-1 semantic.json + run.log |
| `gates/gate_baseline_audio_20261020/` | gate-2 baseline.wav + run.log |
| `candidates/v2/*.wav` | **13 full candidate renders** |
| `candidates/v2/semantic/<id>.json` | each render's exported tokens (matches input) |
| `candidates/v2/hybrid/*.wav` | **13 local comps** |
| `candidates/v2/requests.json`, `run.log` | batch request + log |
| `deliverables/listen/` | 10 A/B clips (original + H1–H4 × e1/e2) |
| `deliverables/tracks/` | H1–H4 full tracks |
| `deliverables/rating_app/` | 5 montages + `_meta.json` + scorecard + README |
| `reports/` | `report.md`, `APPROACH.md`, `findings.md`, `experiments.md` |
| `scripts/` | `evaluate.py`, `align.py`, `audio_splice.py`, `donor_sim.py`, `ctc_score.py`, `rank.py`, `token_surgery.py` |
| `tokens/` | 13 splice token files + baseline + manifest |
| `workspace/` | text-only workspace tarball |

### GitHub (tracked)

```
docs/happy_accidents/Baghdad_Moon/token_surgery/
  CHECKPOINT.md      ← this file
  RESTORE.md
  HANDOFF.md
  APPROACH.md        ← why token surgery isn't enough; verified options
  report.md          ← full numbers for the 13 candidates + hybrids
  CPU_BUILD.md
  scripts/           ← copies of the working scripts
  scorecard_baghdad_moon_two_word.json
```

`happy_accident/` is **gitignored** (WAVs/stems); its durable copy is the GCS
workspace tarball and the individual GCS paths above.

---

## 5. Reproduce / resume on a fresh runtime

**For final assembly you do NOT need the GPU.** Everything needed is a WAV or
JSON in GCS. Only re-rendering (fallbacks in §6) needs the T4.

```bash
# 1. repo
cd /content && git clone https://github.com/akbargherbal/arabmaqamrock.git
cd arabmaqamrock && git pull --ff-only      # must include this CHECKPOINT.md

# 2. workspace text files (prompts, tokens, baseline semantic, scripts)
B=gs://akbar-december-2024-backup/arabmaqamrock/runs/20261019_baghdad_moon_token_surgery
gsutil cp $B/workspace/happy_accident_workspace_20261020.tar.gz /tmp/
tar -xzf /tmp/happy_accident_workspace_20261020.tar.gz -C /content/arabmaqamrock

# 3. audio needed for assembly
mkdir -p happy_accident/original happy_accident/runs/token_surgery/v2/hybrid
gsutil -m cp "$B/../../20261018-162827_batch_12_variants_backing_vocals/02-*B_1712905618.wav" \
  happy_accident/original/
gsutil -m cp $B/candidates/v2/*.wav             happy_accident/runs/token_surgery/v2/
gsutil -m cp $B/candidates/v2/hybrid/*.wav      happy_accident/runs/token_surgery/v2/hybrid/
sha256sum happy_accident/original/*.wav         # dbc00722…
```

Only if a new render is needed:

```bash
./setup_colab.sh                              # model + VAE + LoRAs
gsutil cp $B/bin/audiocpp_cli_prefix_sm75 bin/
cd bin && sha256sum -c audiocpp_cli_prefix_sm75.sha256 && mv audiocpp_cli_prefix_sm75 audiocpp_cli_prefix
chmod +x audiocpp_cli_prefix && cd .. && . ./cuda_loader_path.sh
./bin/audiocpp_cli_prefix --version           # git: 58caf774
```

---

## 6. Round 2 — what the evaluation changed (2026-10-20 11:20 UTC)

Round 1 was rejected 0/4. Two independent causes, both now understood:

1. **Word 2: comp bug.** `audio_splice.py` grafted only the frames whose tokens
   changed. For a partial-word edit that cuts back to the original *inside* the
   word, so the corrected `ف` was followed by the original `…بِأَنَّ` tail. Fixed
   with `--word-ranges` (graft the whole word). Verified in the audio: the old
   hybrids became bit-identical to the original from 203.52 s, i.e. 1.04 s
   before the word ended.
2. **Word 1: donor tokens do not transfer.** Even whole-word donor comps were
   heard as unchanged, and two direct *audio* grafts of the Outro word (final
   note and whole word) also failed. The donor is not the problem — re-synthesis
   in the Verse-2 context is.

**Fix that works: AR re-sing.** Prefix = the tokens before the word,
`semantic_max_tokens` = the word end, seed sweep. The AR sees the real lyric, so
the correct consonant is available to it.

- Word 1 (`prefix 3933 → max 3964`, 16 seeds): 4 diverse seeds got full
  5397-frame renders; **s01, s03, s04 pass by ear**, s15 fails. Chosen: **s03**.
  Comp region 156.995–158.855 s, `identical_outside_regions: true`.
- Word 2 (`prefix 5056 → max 5397`, 16 seeds): **done**. Five tails chosen by
  rhythmic alignment (s08, s13, s11, s14, s07) are in `deliverables/listen_v4/`;
  comp only the winner (region 201.835–204.775 s).

Artifacts: `deliverables/listen_v3/` (round 2, e1 + e2) and `listen_v4/`
(round 3, e2 only, + `scorecard_baghdad_moon_e2_round3.json`), `runs/e1_resample/`,
`runs/e2_resample/`, `candidates/v3_e1_ar/`, `candidates/v3_e2_ar/` (all 16
renders, so extra takes need no GPU).

### 6.4 What happens next session

1. Read the user's rating (`results.json` / `report.json`), record it in
   `report.md` §6.4.
2. Pick the word-2 take. If none of the five works, audition the other 11 already
   rendered (`candidates/v3_e2_ar/`); `s00/s04/s10` were skipped only for
   rhythmic drift, not for the phoneme.
3. `python3 happy_accident/runs/assemble_final.py <e2.wav> <e2 semantic.json>
   deliverables/tracks/FINAL_e1_ar_s03_<seed>.wav` — no GPU, ~1 minute. It
   asserts `identical_outside_regions` and prints both sha256s.
4. Upload `$B/final/`, update `report.md`/`CHECKPOINT.md` to complete, push.

## 7. What remains — decision tree (historical, round 1)

### Step A — read the user's evaluation (blocking)

The user is rating the 5 montages with the rating app. Results will be in their
`runs/<run_id>/results.json` (and `report.json`). Ask for that file (or the
per-version verdicts) and record them in `report.md`.

Expected output format: one verdict per word per version, e.g.
“e1 fixed in H1/H2, not in H3/H4” / “e2 fixed in H1/H3, needs H2/H4”.

### Step B — choose the final combination

All four combinations of {e1 A_note, e1 B_word} × {e2 A_onset, e2 B_word} are
already rendered as token files and hybrids:

| e1 ↓ / e2 → | A_onset | B_word |
|---|---|---|
| **A_note** | `combo_e1_A_note__e2_A_onset` (H1) | `combo_e1_A_note__e2_B_word` (H2) |
| **B_word** | `combo_e1_B_word__e2_A_onset` (H3) | `combo_e1_B_word__e2_B_word` (H4) |

So any mix the user asks for is available without re-rendering. Just copy the
matching `hybrid/*.wav` as the final track.

If the user instead wants `e1_C_A`, `e1_C_C`, `e2_A_onset_A` or `e2_A_onset_C`,
or a cross combination not in the list above, generate the combo token file
with `token_surgery.py`, render once (`min=max=5397`, original seed), then comp.

### Step C — final QC and delivery

1. `audio_splice.py` output must report `identical_outside_regions: true`.
2. Confirm the original WAV sha256 is still `dbc00722…` (never overwrite).
3. Export the final track as `deliverables/tracks/FINAL_<e1>_<e2>.wav`.
4. Append the human scores to `report.md`; update this checkpoint to
   “complete”.
5. Upload the final track + updated docs to `$B/final/` and `$B/reports/`;
   commit the docs to GitHub.

### Step D — only if both word donors fail by ear

- **e1 AR resample:** `semantic_prefix_file` = first 3933 tokens,
  `semantic_max_tokens=3964`, seed sweep around 1712905618; keep candidates
  whose length is 31 frames; comp.
- **e2 tail resample:** prefix = first **5056** tokens (not 5100),
  `semantic_max_tokens=5397`, seeds `1712905618 + 0..15`; evaluate + comp.
- Both are ~2.5 min per render plus load; batch them.

---

## 7. User's own words (for context)

> “I loved the original track… it was perfect except for 2–3
> mispronunciations… the first time, it's clear it was pronounced عَلِيم — م
> instead of ه.”

The third (Outro `عَلَيْهِ`) is muddy but borderline acceptable; it was left
untouched by design.

---

## 8. Don't redo

- Don't regenerate the baseline semantic or the A/C exports.
- Don't rebuild the binary or run it without the prefix patch.
- Don't re-render the 13 candidates unless a fallback in §6.D is needed.
- Don't overwrite `happy_accident/original/*B_1712905618.wav`.
- Don't claim the output is bit-identical *inside* the edited words — only
  outside them.
