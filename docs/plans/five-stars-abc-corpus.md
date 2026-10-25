# Plan — Five Stars ABC composition corpus

**Status:** phases 0–1 complete; phases 2–5 specified, not started
**Date:** 2026-10-25
**Owner:** this repository (`arabmaqamrock`)
**Upstream data:** `../Five_Stars_ArabMaqamRock` (pickle + 177 MP3s)
**Artifact root:** `datasets/five_stars/`
**GCS corpus:** `gs://akbar-december-2024-backup/arabmaqamrock/datasets/five_stars/v1/`
**Colab compute:** L4 + high-RAM for transcription; T4 is sufficient for alignment

**Next action:** start a Colab L4 session and run §7. Everything upstream of it is
uploaded and verified.

## 1. Goal

Build a **reference corpus for ABC-first composition**: given new lyrics and a
maqam, an LLM should be able to write an ABC score in the manner of these
tracks — adapting, improvising, exploring new patterns — not copying.

The corpus therefore is not a transcription benchmark. Each row is a
*demonstration of the task*:

```
lyrics (diacritized, with section markers)
  + maqam
  + mood
  + style prompt
      -> ABC score (Vocal + Ins voices)
```

Fidelity to the original performance matters less than **whether the ABC is good
enough to imitate**. That distinction drives every decision below.

The payoff loop already exists in this repo: `run_one.sh` accepts `ABC_FILE`
with `COT=melody` and feeds the score to YuE2 as a symbolic guide.

```bash
OUT_DIR=/path/to/run STYLE_FILE=… LYRICS_FILE=… COT=melody \
  ABC_FILE=/path/to/score.abc ./run_one.sh Name 20261024 6750
```

So the full loop is: **LLM writes ABC → validate → render with YuE2 → listen.**

## 2. The data

| | |
|---|---|
| Tracks | **177** (the curated top of a 438-track pool that mixed 4★ and 5★) |
| Audio | 12.727 h, 995 MiB (1.04 GB), MP3 48 kHz stereo ~180 kbps |
| Duration | 3.0 – 6.2 min, median 4.3 |
| Maqams | Hijaz 49 · Ajam 43 · Kurd 43 · Nahawand 42 |
| Unique poems | **112** (69 single-take, 29 pairs, 6 triples, 8 quads) |
| Lyrics | fully diacritized classical Arabic, 12–44 lines, 4–8 sections |
| Selection | **already made** — no quality filter downstream |
| Long tracks | 10 exceed 300 s (two transcription windows); longest 369.7 s |

### Findings that shape the design

- **Style prompts are constant.** 1 unique `genre`, `production`, and
  `instrumentation` string; 110 BPM on all 177. Only `mood` (92 values) and the
  maqam name vary. The corpus cannot teach arrangement variety — do not promise
  that in any prompt or dataset card.
- **The maqam label is a prompt, not a measurement.** `scores/CHANGES.md`
  documents a related "Hijaz" track that transcribed as G natural minor. A
  pitch-profile check is mandatory before a track becomes an exemplar.
- **SheetSage2's artifacts become style.** The same document records octave
  errors (mixed octave marks on a repeated figure) and a missing resolution. If
  40% of exemplars contain octave jumps, the model will imitate them.
- **One lyric group spans two maqams.** The Jassas ibn Murrah poem appears once
  in Ajam and three times in Hijaz. This is *useful* (a controlled
  same-poem/different-maqam comparison) but it means "no cross-maqam
  duplication" is false, and it would leak through a naive split.
- **177 takes are 112 compositions.** Multi-take groups are performance
  variants of one poem; treat them as such when sampling exemplars.
- **`prior_rating` is not the selection criterion.** The listening-rating files
  only cover 89/177 tracks (an earlier partial pass). The 177 themselves are the
  curated best of 438 and are taken as given; the rating field is a bonus signal.

## 3. Locked decisions

| Decision | Value | Why |
|---|---|---|
| Transcription mode | `--melody-only` | Matches `ABC_FILE` consumption; chord symbols cost ~25% more tokens and SheetSage2's harmony labels are Western-tonal and wrong for maqam |
| Voices | Vocal + Ins | Ins carries the guitar/orchestral line, useful for arrangement prompts |
| GPU for transcription | **L4** | SheetSage2 hardcodes `dtype="bf16" if cuda`; T4 (sm_75) has no bf16 support |
| GPU for alignment | **T4 is enough** | Alignment is fp16/fp32 and small; L4 buys ≤2× on a 5–15 min job |
| Primary key | `track_id` = upstream `clip_id` | 157 unique filenames for 177 tracks — filenames collide |
| Selection | all 177 | Curation already happened upstream |
| Token target per few-shot bundle | ~8–10k | 3 exemplars + maqam card + lyrics + instructions |

## 4. Artifact layout

Local (this repo, committed metadata only):

```
datasets/five_stars/
  build_manifest.py      regenerates manifest + lyrics + audit
  stage_audio.sh         builds the staging tree, tars, and checksums
  manifest.jsonl         177 rows, one per track
  lyrics.jsonl           parsed lyrics + style prompt
  audit.json             corpus facts
  README.md              field contract + GCS location
```

This plan lives at `docs/plans/five-stars-abc-corpus.md`; it is uploaded to GCS
as `v1/PLAN.md` so the corpus is self-describing without a repo checkout.

GCS, immutable inputs:

```
gs://akbar-december-2024-backup/arabmaqamrock/datasets/five_stars/v1/
  audio/Ajam.tar  audio/Hijaz.tar  audio/Kurd.tar  audio/Nahawand.tar
  audio/SHA256SUMS
  corpus/manifest.jsonl  corpus/lyrics.jsonl  corpus/audit.json
  README.md  PLAN.md
```

GCS, derived outputs (written by Colab):

```
  transcripts/<track_id>/score.abc, melody_vocal.mid, melody_instrumental.mid,
                          *.lab, events.json, meta.json
  derived/<track_id>.json  lint + pitch profile + maqam verdict
  exemplars/               maqam cards + few-shot bundles
```

Per-maqam tars because each is ~250 MB: a single-maqam rerun pulls 250 MB, and a
failed upload costs one tar rather than the set.

## 5. Phase 0 — provenance (DONE)

Deliverables in `datasets/five_stars/`. Facts established:

- 177 rows, `track_id` unique, no nulls, every hash matches a file on disk.
- `MAQAM` agrees with both the prompt and the folder path on 177/177.
- 24/177 texts were not NFC-normalized upstream; fixed at parse time.
- 6 lyric groups carry 2–3 different diacritizations of the same consonants
  (grammatical reading differences, not corruption).

Re-run with:

```bash
python3 datasets/five_stars/build_manifest.py --src ../Five_Stars_ArabMaqamRock
```

## 6. Phase 1 — stage audio to GCS (DONE 2026-10-25)

Uploaded and verified:

| Object | Bytes |
|---|---|
| `audio/Ajam.tar` | 258,078,720 |
| `audio/Hijaz.tar` | 290,426,880 |
| `audio/Kurd.tar` | 251,269,120 |
| `audio/Nahawand.tar` | 242,421,760 |
| `audio/SHA256SUMS` | 313 |
| `corpus/{manifest.jsonl,lyrics.jsonl,audit.json}` | 1,340,935 |
| `README.md`, `PLAN.md` | 17,559 |

Total **995.21 MiB**, 10 objects. Round-trip verified: the four tars were
downloaded back and passed `sha256sum -c`, and the tar member list matches
`manifest.jsonl` exactly (177 in, 177 out, 0 missing, 0 extra).

Reproduce locally:

```bash
./datasets/five_stars/stage_audio.sh          # builds /tmp/opencode/five_stars_v1
```

Two operational notes:

- Tars were uploaded as **composite objects**, so GCS reports `md5_hash: null`
  for them. Verify with `SHA256SUMS`, not md5/crc32c.
- The tars are deterministic (sorted names, uid/gid 0, mtime 0), so re-staging
  from the same manifest reproduces identical sha256 values.

Layout inside each tar: `audio/<maqam>/<track_id>.mp3`, so extracting inside the
dataset root reproduces the paths `manifest.jsonl` expects.

## 7. Phase 2 — transcribe on Colab L4

### Bootstrap (once per session)

The bucket is private, so authenticate before anything else. Colab ships the
Cloud SDK; if `gcloud` is missing, `!pip install -q google-cloud-storage` is not
enough — use `gsutil` (also preinstalled) or install the SDK.

```python
from google.colab import auth
auth.authenticate_user()
```

```bash
git clone https://github.com/akbargherbal/arabmaqamrock.git /content/amr
cd /content/amr
pip install -q uv
./plumbing/setup_transcribe.sh --cuda --warm        # ~4–6 min, 2.76 GB weights
python3 transcribe.py --doctor                      # system python is fine here

# pull, verify, unpack the corpus
mkdir -p /content/data && cd /content/data
gcloud storage cp 'gs://akbar-december-2024-backup/arabmaqamrock/datasets/five_stars/v1/audio/*.tar' .
gcloud storage cp gs://akbar-december-2024-backup/arabmaqamrock/datasets/five_stars/v1/audio/SHA256SUMS .
sha256sum -c SHA256SUMS
for m in Ajam Hijaz Kurd Nahawand; do tar -xf "$m.tar"; done
find audio -name '*.mp3' | wc -l      # expect 177
```

Note: `python3 transcribe.py` is only valid for `--dry-run`, `--verify`, and
`--doctor`. **The model path must run through `./transcribe.sh`**, which uses the
repo-local `.venv-sheetsage2`; the system Python has no torch.

### Smoke test first (3 tracks, ~2 min)

Two over 5 min (the two-window case) and one under 5 min:

```bash
cd /content/amr
./transcribe.sh \
    /content/data/audio/Ajam/5a30fe55-88d8-4939-86c0-b8ebfaa07f75.mp3 \
    /content/data/audio/Hijaz/57012957-7e5f-4d68-9a74-965b8f811e43.mp3 \
    /content/data/audio/Nahawand/119f56d2-ff83-43bd-ae62-5a01357e8f7e.mp3 \
    --device cuda --threads 4 --melody-only \
    --out-dir /content/out/transcripts
```

Inspect before committing the session:

- `score.abc` parses and `abc2midi` exits 0
- the Vocal voice has a plausible note count (tens per line, not 2, not 500)
- no octave jumps across a repeated figure
- `meta.json` `seconds` per track → the real speedup factor
- `meta.json` `peak_gpu_mib` → headroom on a 24 GB L4

If the speedup is under ~4×, stop and investigate before spending the session on
177 tracks.

### The run

```bash
cd /content/amr
nohup ./transcribe.sh /content/data/audio \
    --recursive \
    --device cuda \
    --threads 4 \
    --melody-only \
    --out-dir /content/out/transcripts \
    --time-budget 5400 \
    > /content/run.log 2>&1 &
```

Notes:

- `--melody-only` is already the default; it is passed explicitly so the intent
  survives in the log.
- The tool discovers 177 MP3s recursively and keys outputs by `clip_id`; stems
  are unique, so no collisions (verified with `--dry-run`).
- Resumable: an existing `score.abc` is skipped only when `meta.json` records a
  successful run, the same source hash, and a matching ABC hash.
- Sync periodically so a disconnect costs minutes, not the session:

```bash
gcloud storage rsync -r /content/out/transcripts \
    gs://akbar-december-2024-backup/arabmaqamrock/datasets/five_stars/v1/transcripts
```

- Verify when the run ends, then archive the driver's own records:

```bash
./transcribe.sh /content/data/audio --recursive --out-dir /content/out/transcripts --verify
gcloud storage cp /content/out/transcripts/{_timings.csv,transcribe_manifest.json} \
    gs://akbar-december-2024-backup/arabmaqamrock/datasets/five_stars/v1/transcripts/
```

### Expectations

| | |
|---|---|
| CPU baseline (measured in this repo) | 417 s for 216 s audio; 433 s for 272 s |
| Whole corpus on CPU, 2 streams | ~10 h |
| L4 at 25 s/track | **~75 min** |
| L4 at 40 s/track | **~2 h** |
| Largest source | 6.2 min → 2 windows (300 s window, 100 s hop) |

`meta.json` already records `seconds` and `peak_gpu_mib`; use them to confirm the
speedup on the first few tracks before walking away.

If `peak_gpu_mib` approaches ~20 GB on a 24 GB L4, or the process OOMs, drop the
long tail (the 10 tracks over 300 s) to `--device cpu` rather than restarting the
batch.

## 8. Phase 3 — QC and tiers

Applied to `transcripts/`, producing `derived/<track_id>.json`:

| Check | Test | Action on failure |
|---|---|---|
| Parse | `abc2midi` exit 0, complete bars | reject from exemplars |
| Vocal presence | >0 pitched notes in `melody_vocal.mid` | reject |
| Octave sanity | no interval > 12 semitones inside a 2-bar window in the Ins voice | flag |
| Range | vocal median pitch within a plausible baritone tessitura | flag |
| Pitch profile | pitch-class histogram vs the maqam template | **gate** |
| Tonic | estimate from the vocal pitch histogram | record |

Tiers:

- **T0** raw transcripts — all 177, never shown to an LLM
- **T1** lint-clean
- **T2** T1 + maqam profile agrees with the label
- **T3** polished exemplars, hand-vetted or model-vetted, with `w:` lines

## 9. Phase 4 — exemplar packaging

The deliverable is **not** 177 files. It is:

1. **4 maqam cards** (~300 tokens each): scale degrees present, characteristic
   intervals, cadence targets, typical range, phrase lengths, melisma density.
   Generated from T2 by aggregation, reviewed by hand.
2. **Retrieval key**: `maqam × mood → ranked track_ids`, so a prompt can pick
   context instead of stuffing the corpus.
3. **~12 polished demonstrations** (3 per maqam): lyrics + ABC + card, with
   `w:` lines once alignment lands.
4. **A composition brief** describing the ABC house style: `V: Vocal` /
   `V: Ins`, `M:2/4`, `L:1/16`, `Q:1/4=…`, `K:…`, `%` section comments.

Token math that drives this: one score ≈ 2.6 KB ≈ **800 tokens**; all 177 ≈
**140k**, unusable. A bundle of 3 exemplars + card + lyrics + instructions ≈
**10k**.

## 10. Phase 5 — forced alignment (after the ABC run)

Purpose: attach lyrics to notes as ABC `w:` lines, turning each exemplar into a
demonstration of text-setting (how many syllables per bar, where melismas land).

**GPU answer: a T4 is sufficient; an L4 buys almost nothing.**

- The bf16 constraint that forced L4 for SheetSage2 does not apply here. T4 has
  native **fp16** tensor cores, which is what alignment stacks use.
- Alignment models are small (wav2vec2/MMS CTC ≈ 300M–1.2 GB) and the corpus is
  only 12.7 h. A CTC forced aligner is a single forward pass plus a Viterbi
  decode — minutes for the whole corpus on a T4.
- MFA (Kaldi) is **CPU-only**, so the GPU choice is irrelevant on that path.
- L4 might be 1.5–2× faster on a job measured in minutes. Not a reason to wait
  for one.

Candidate tools, to be settled by a 3-track bake-off:

| Tool | Arabic | Singing | Device |
|---|---|---|---|
| `ctc-forced-aligner` (`--language ara`, `jonatasgrosman/wav2vec2-large-xlsr-53-arabic`) | yes | untested | CPU/CUDA |
| MFA + Arabic acoustic model | yes | untested | CPU only |
| Note-anchored syllabification | text-only | **yes by construction** | no GPU |

The third option is worth trying first: we will already have vocal note onsets
from SheetSage2, and the lyrics are fully diacritized, so syllable count is
knowable. Align the syllable sequence to note onsets with DTW, no acoustic model
at all. It respects the melody by construction, which is exactly the
correspondence we want to teach.

Accuracy on *sung* Arabic is the real risk here, not compute. Budget a bake-off
on 3 tracks, judged by inspecting whether the `w:` placement matches what a
listener hears.

## 11. Failure modes to watch

| Symptom | Likely cause | Response |
|---|---|---|
| `bf16` dtype error | running on T4 | use L4, or `--device cpu` |
| OOM on 6-min tracks | 2 windows × 300 s attention | transcribe the long tail on CPU |
| Key signature not matching the maqam | SheetSage2 is Western-tonal | expected; do not "fix" the ABC, record it |
| Octave jumps in Ins | documented SheetSage2 failure | flag, do not auto-correct |
| Empty vocal voice | instrumental passage or failed decode | reject from exemplars |
| Colab disconnect | 12 h cap / idle | resume; `gcloud storage rsync` protects output |

## 12. Open questions

1. Alignment approach — CTC aligner vs note-anchored syllabification (§10).
2. Whether the Ins voice belongs in the composed output or is decorative.
3. Whether maqam cards should be hand-written from the corpus or model-drafted
   then edited.
4. Release posture: audio is Suno-rendered and not distributed; SheetSage2 and
   MERT-v2-FullSong are CC-BY-NC-4.0. Internal research only unless re-rendered.

## 13. Provenance

- Upstream pickle + audio: `../Five_Stars_ArabMaqamRock`
- Corpus bundle: `gs://akbar-december-2024-backup/arabmaqamrock/datasets/five_stars/v1/`
  (10 objects, 995.21 MiB, verified by SHA-256 round trip)
- `datasets/five_stars/` is regenerable: `build_manifest.py` → metadata,
  `stage_audio.sh` → tars + checksums
- Transcription model: `m-a-p/SheetSage2` @ `b83c3d79a6d98bcffaf8f9ed112c90aa887887bc`
- Backbone: `m-a-p/MERT-v2-FullSong` (2.53 GB)
- Listening ratings: `../maqam_listen_proof/ratings/*.json` (partial earlier pass,
  89/177 — not the selection criterion)
