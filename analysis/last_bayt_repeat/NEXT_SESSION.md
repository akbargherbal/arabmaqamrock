# Next session — GPU analysis only (no generation)

> **Status, 2026-11-18: executed.** Everything below was run on a T4; results are
> in `REPORT.md` §3.1–§3.2 and `results.csv`. Two things came out differently
> from this plan and are worth carrying forward: (1) CTC placement looked like a
> counter but is **not** — calibrated on 15 no-score takes with a known answer of
> 2 it returns 4–8, so ASR is the arbiter and `ctc_count` is an upper bound;
> (2) the "we always used an ABC" confound was resolved by measuring 27
> **existing** `cot=off` takes (mean 1.85 renditions) rather than by a new render.
> The spec is kept as written for provenance.

**Decision (2026-11-17):** no new renders. A T4 is available for *analysis*: stem
separation, ASR/CTC and forced alignment. This file is the handoff for that
session. Generation experiments stay parked (see `REPORT.md` §8) until the
analysis answers the open questions.

---

## 0. Scope

Do:

* separate vocal stems for the 16 HAC takes;
* run ASR over all 16 takes and get a real per-track repeat count;
* run CTC / forced alignment on the final chorus to confirm where the loop
  starts and whether the 7th rendition on `hac_01_1114111` is a real bayt or a
  cadential reprise;
* reconcile those three measurements and rewrite `results.csv`.

Do **not**:

* call `generate.py`, `run_one.sh`, or any audio.cpp render path;
* run token surgery / prefix repair;
* run SheetSage2 transcription (it produces melody ABC, irrelevant here);
* modify production code or commit analysis artifacts into run buckets.

---

## 1. Hardware and environment

Target: **NVIDIA T4, 16 GB, Turing (compute 7.5)**.

T4 constraints that matter:

* **No bf16 and no FlashAttention-2** (both need Ampere+). Use `float16` or
  `int8_float16` everywhere; do not enable `attn_implementation="flash_attention_2"`.
* Keep models sequential; do not co-reside Demucs + Whisper large + XLSR at once.
* Rough VRAM: Demucs `htdemucs` ≈ 4–6 GB, Whisper `medium` fp16 ≈ 2–3 GB,
  `large-v3` int8 ≈ 4–5 GB, XLSR-53 ≈ 1.2 GB fp32.

Suggested setup (fresh VM, CUDA 12.x wheel):

```bash
python3 -m pip install -q --upgrade pip
python3 -m pip install -q torch torchaudio --index-url https://download.pytorch.org/whl/cu121
python3 -m pip install -q "demucs==4.1.0" faster-whisper transformers soundfile librosa rapidfuzz
```

Existing repo tooling to reuse:

| Need | Use |
|---|---|
| vocal stems | `python3 -m demucs -n htdemucs --two-stems=vocals -d cuda` (same 4.1.0 as the earlier case work) |
| ASR counting | `analysis/last_bayt_repeat/count_last_bayt.py` (already validated) |
| CTC alignment | `docs/happy_accidents/Baghdad_Moon/token_surgery/scripts/align.py` (`--vocals`) |
| CTC hypothesis scoring | `docs/happy_accidents/Baghdad_Moon/token_surgery/scripts/ctc_score.py` |

Models already used by the project:

* ASR: faster-whisper `small` (validated), `medium` (cross-check), optionally `large-v3`.
* CTC aligner: `akbargherbal/wav2vec2-large-xlsr-53-arabic` @ `4ca1c9c6ac85`
  (the model that produced the existing karaoke `words.json`) and
  `jonatasgrosman/wav2vec2-large-xlsr-53-arabic` (used by `align.py`).

---

## 2. Inputs

Everything below is already produced; nothing needs re-rendering.

| Input | Path |
|---|---|
| 16 MP3s + per-track JSON/logs | `gs://akbar-december-2024-backup/arabmaqamrock/runs/20261117-082924_harith_hac_a/` and `…093512_harith_hac_b/` |
| Existing karaoke alignments | `…/karaoke/*.words.json` (already downloaded to `/tmp/opencode/karaokeA|B`) |
| Lyrics | `…/hac_01_lyrics.txt`, `…/hac_02_lyrics.txt` (also inline in `manifests/harith_hac_{A,B}.json`) |
| Current proxy results | `analysis/last_bayt_repeat/results.csv` |
| Score/vocal budget | `analysis/last_bayt_repeat/score_gap.csv` |

Total audio: **~89 minutes** across 16 takes (2 × ~44.5 min).

Plan disk: ~2–3 GB for 44.1 kHz vocal stems, ~130 MB for MP3s, ~2 GB for model
weights, a few hundred MB for ASR/alignment JSON.

---

## 3. Tasks, order and acceptance

Run in this order; each step is independently useful if time runs out.

### T1 — Vocal stems (Demucs, ~15–30 min)

```bash
mkdir -p work/stems
for f in /tmp/opencode/hacA/*.mp3 /tmp/opencode/hacB/*.mp3; do
  python3 -m demucs -n htdemucs --two-stems=vocals -d cuda \
    -o work/stems "$f"
done
```

Output: `work/stems/htdemucs/<track>/vocals.wav` (+ `no_vocals.wav`).

Acceptance: 16/16 stems exist, same sample rate as source, duration within
±0.1 s. Keep the full mix too — do not overwrite it.

Why: the HAC mix is guitar/drum heavy; ASR and CTC both improve on the vocal
stem, and the existing `align.py` explicitly requires `--vocals`.

### T2 — ASR ground truth for all 16 (faster-whisper, ~15–45 min)

```bash
# small first (matches the validated run); separate cache dir for the GPU pass
python3 analysis/last_bayt_repeat/count_last_bayt.py \
  --run-dir /tmp/opencode/hacA --cache-dir work/asr_cache \
  --model small --device cuda --compute-type float16 --threads 4 --threshold 75 \
  --out work/asr_A_small.csv

python3 analysis/last_bayt_repeat/count_last_bayt.py \
  --run-dir /tmp/opencode/hacB --cache-dir work/asr_cache \
  --model small --device cuda --compute-type float16 --threads 4 --threshold 75 \
  --out work/asr_B_small.csv
```

Then repeat with `--model medium` for a cross-check (and `large-v3` only if the
two disagree by >1 on any track). Use the **vocal stems** as `--audio` for the
disputed tracks rather than the full mix.

`count_last_bayt.py` gained `--device {cpu,cuda}` and `--compute-type` for this
session; the defaults (`cpu`, `int8`) preserve the local behaviour. Use
`float16`, not `bf16`, on the T4.

Acceptance:

* per-track `occurrences` from `small` and `medium` agree within ±1;
* `hac_01_1114111` resolves to 6 or 7, with the 315.6–328.6 s item classified
  as bayt vs cadential reprise;
* the strict `>=85` count is recorded alongside the 75-threshold count.

Record both `asr_count` (75) and `asr_count_strict85` in the new `results.csv`.

### T3 — CTC / forced alignment of the final chorus (~10–20 min)

For each take, align the last bayt text against the **vocal stem** over the
window `[first_chorus_start − 5 s, end]` from `results.csv`:

```bash
python3 docs/happy_accidents/Baghdad_Moon/token_surgery/scripts/align.py \
  work/stems/htdemucs/<track>/vocals.wav \
  "اتلهي بها الهواجر اذ كل ابن هم بليه عمياء" \
  --start <chorus_start-5> --end <duration> --vocals
```

Pass the **undiacritized** bayt (the XLSR tokenizer drops harakat, and
`align.py` zips characters to tokens one-to-one; diacritics would desynchronise
that zip). Use the same normalised reference that `count_last_bayt.py` prints as
`reference_norm`.

Do two passes:

1. **Per-character Viterbi** of the single bayt text — gives word onset/offset
   and shows whether the text fits the first rendition or is stretched across
   several.
2. **N-best placement**: align the same bayt starting at each candidate onset
   from the ASR segments (or slide in 0.5 s steps) and keep the highest
   likelihood placements. This is the CTC analogue of `count_last_bayt.py` and
   does not rely on Whisper's segmentation.

Acceptance:

* the accepted onset list matches the ASR occurrence list within ±0.5 s on at
  least 12/16 takes;
* `hac_01_1114111` onset list is available for both the 6- and 7-rendition
  readings;
* no alignment is run on the full mix.

Why CTC in addition to ASR: Whisper can merge or hallucinate repeated phrases
under music. CTC alignment against the *known text* is the independent check,
and it also tells us whether the model sings the whole bayt or only its tail.

### T4 — Reconcile and rewrite `results.csv` (~30 min, CPU)

Add these columns to the 16 rows:

| Column | Source |
|---|---|
| `asr_count` | T2, threshold 75 |
| `asr_count_strict85` | T2 |
| `asr_count_medium` | T2 |
| `ctc_count` | T3 accepted placements |
| `ctc_first_onset_s`, `ctc_last_offset_s` | T3 |
| `review_flag` | `agree` / `disagree` / `disputed` |

Rules:

* `review_flag=agree` when `asr_count` and `ctc_count` differ by ≤1;
* `disputed` when they differ by ≥2, or when `hac_01_1114111` is split 6 vs 7;
* keep the alignment proxy (`est_count`) as a column, not as truth.

Acceptance: `results.csv` has 16 rows, no blank ASR count, and every disputed
row has a one-line note with timings.

### T5 — Spot-check the disputed takes (only if needed, ~15 min)

Pick up to 3 `disputed` takes and:

* export 10 s clips around each contested onset from the vocal stem;
* run `ctc_score.py` with correct vs shifted/wrong word hypotheses;
* listen once (headphones) and annotate.

Do not expand this into a full manual audit.

---

## 4. What each result decides

| Measurement | Question it answers |
|---|---|
| ASR count (T2) | How many bayts are actually sung? (ground truth) |
| CTC placements (T3) | Is the count an ASR segmentation artifact? Where does the loop start? |
| Stems (T1) | Are the extra renditions in the lead vocal or bleed/backing? |
| Reconciled table (T4) | Which takes exceed 2 renditions, by how much, and with what confidence? |

This is enough to close the diagnosis in `REPORT.md`. It does **not** test the
cause; that still needs the parked generation matrix (E1/E6 first).

---

## 5. Outputs to bring back

```
work/
├── stems/htdemucs/<track>/vocals.wav
├── asr_A_small.csv, asr_A_medium.csv
├── asr_B_small.csv, asr_B_medium.csv
├── ctc/<track>.json          # accepted onsets + per-word spans
└── results_asr_ctc.csv       # reconciled 16-row table
```

Copy the reconciled CSV over `analysis/last_bayt_repeat/results.csv` (or keep
both: `results.csv` for the proxy, `results_asr_ctc.csv` for measured counts)
and add a short "measured counts" subsection to `REPORT.md`.

---

## 6. Time and failure budget

| Step | T4 time | If it overruns |
|---|---:|---|
| setup + model downloads | 10–15 min | pin wheels; models total ~3–4 GB |
| T1 stems | 15–30 min | process 8 A-takes first, B only if needed |
| T2 ASR small | 10–20 min | already have `small` cached for 1 track |
| T2 ASR medium | 20–40 min | run only the 8 A-takes |
| T3 CTC align | 10–20 min | tail windows only, not whole tracks |
| T4 reconcile | 30 min | CPU; can run locally |

Stop rule: if T2 `small` and `medium` agree on all 16 within ±1, skip `large-v3`
and skip T5. If T3 disagrees with both, prefer the CTC result on the vocal stem
and mark the row `disputed`, do not silently pick one.

---

## 7. Explicit non-goals

* No re-rendering, no seed sweep, no score trimming, no lyric edits.
* No "fix" applied to the MP3s; stems are analysis artifacts only.
* No changes to `scores/harith_hac/*.abc`, `manifests/*.json`, or `generate.py`.
* The generation matrix in `REPORT.md` §8 stays deferred until the measured
  counts are in.
