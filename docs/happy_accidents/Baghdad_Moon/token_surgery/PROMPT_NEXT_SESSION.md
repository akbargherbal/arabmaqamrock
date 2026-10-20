# RESUME PROMPT — Baghdad Moon B: two-word repair

Copy everything below this line into the new session.

---

We are resuming work on the Baghdad Moon B track. The previous Colab VM has been
discarded, so nothing from `/content` survives except what is in GitHub and GCS.
First, read the full checkpoint:

```
https://github.com/akbargherbal/arabmaqamrock/blob/main/docs/happy_accidents/Baghdad_Moon/token_surgery/CHECKPOINT.md
```

Also read, as needed:

- `docs/happy_accidents/Baghdad_Moon/token_surgery/HANDOFF.md` — background/case file (read §0.5)
- `docs/happy_accidents/Baghdad_Moon/token_surgery/report.md` — round 1 + round 2 results
- `docs/happy_accidents/Baghdad_Moon/token_surgery/APPROACH.md` — why the pipeline is what it is

GCS root for this task:
`gs://akbar-december-2024-backup/arabmaqamrock/runs/20261019_baghdad_moon_token_surgery/`

## The goal (unchanged)

Fix exactly two mis-sung words by token-level surgery on the original 5397-frame
semantic stream, changing as little else as possible. Do **not** change lyrics,
style prompt, LoRA, seed, sampler settings or GPU type.

- Word 1: `عَلَيْهِ` in Verse 2, sung `عَلِيم`. Frames 3933–3964.
- Word 2: `فَإِنَّ` in the Outro, sung `بِأَنَّ`. Frames 5056–5114.
- The third, muddy `عَلَيْهِ` in the Outro is **not** edited.

Original WAV must never be overwritten:
`dbc00722534d5ee763ae54a048cd704eaa4c927e37834cd54542eaf379e0de42`

## State when we stopped (2026-10-20 ~12:10 UTC)

- **Word 1 is FIXED and accepted by ear**: AR re-sing, seed `s03`. Hybrid is
  `$B/candidates/v3_e1_ar/e1_ar_s03.wav`, tokens
  `$B/tokens/tokens_e1_ar_s03_full.json`. Comp region 156.995–158.855 s,
  `identical_outside_regions: true`.
- **Word 2 is waiting on the user's ear.** 16 AR tails were rendered from
  prefix = first 5056 tokens, `max=5397`, seeds `1712905618+0..15`; five
  (`s08, s13, s11, s14, s07`) were cut into `$B/deliverables/listen_v4/` with the
  scorecard `scorecard_baghdad_moon_e2_round3.json`. **All 16 raw renders are
  backed up** in `$B/candidates/v3_e2_ar/`, so more takes can be auditioned
  without a GPU.
- Round 1 (the 13 donor splices) was **rejected 0/4**; the causes and the fix are
  in `report.md` §5–§6. The donor route is closed for both words.
- Docs are current on GitHub (`main`), all audio/artifacts on GCS.

**The only thing blocking final assembly is the user's pick among the five
word-2 takes.**

## What to do first

1. Ask for the rating-app output: `runs/<run_id>/results.json` (or
   `report.json`), or a plain answer — which take says `فَإِنَّ`, and is the word
   complete with no seam.
2. Record the verdict in `report.md` (§6.4) and `CHECKPOINT.md`.
3. Assemble — **no GPU needed**, everything is a WAV/JSON:

   ```bash
   B=gs://akbar-december-2024-backup/arabmaqamrock/runs/20261019_baghdad_moon_token_surgery
   cd /content && git clone https://github.com/akbargherbal/arabmaqamrock.git
   cd arabmaqamrock && gh auth setup-git
   gsutil cp $B/workspace/happy_accident_workspace_20261020b.tar.gz /tmp/
   tar -xzf /tmp/happy_accident_workspace_20261020b.tar.gz -C .
   mkdir -p happy_accident/original happy_accident/runs
   gsutil -m cp "$B/../20261018-162827_batch_12_variants_backing_vocals/02-*B_1712905618.wav" happy_accident/original/
   sha256sum happy_accident/original/*.wav        # dbc00722…
   gsutil cp $B/candidates/v3_e1_ar/e1_ar_s03.wav  happy_accident/runs/e1_resample/hybrid/e1_ar_s03.wav
   gsutil cp $B/candidates/v3_e2_ar/e2_ar_s08.wav  happy_accident/runs/e2_resample/pick.wav   # winner
   gsutil cp $B/e2_resample/semantic/e2_ar_s08/semantic.json happy_accident/runs/e2_resample/pick.json
   python3 happy_accident/runs/assemble_final.py \
     happy_accident/runs/e2_resample/pick.wav happy_accident/runs/e2_resample/pick.json \
     happy_accident/deliverables/tracks/FINAL_e1_ar_s03_s08.wav
   ```

   `assemble_final.py` comps word 2 onto the word-1 hybrid, asserts
   `identical_outside_regions`, and prints both sha256s.
4. Final QC / delivery:
   - original still `dbc00722…`; final changed only inside 156.996–158.855 and
     201.835–204.775 s;
   - upload to `$B/final/` and docs to `$B/reports/`;
   - append human scores to `report.md`, mark `CHECKPOINT.md` complete;
   - commit and push (`gh auth setup-git` first, the remote hangs without it).

## If all five auditioned word-2 takes fail

- **First, audition the other 11 takes from the same sweep** (already rendered
  and backed up): `s00 s01 s03 s04 s06 s09 s10 s12 s15` — note
  `s00, s04, s10` were skipped only because their word timing drifted (14–20 dB
  level dip in 202–205 s), not because of the phoneme. Cut any of them with the
  same window 199.8–206.8 s and listen. No GPU, no re-render.
- If all 16 fail, render more seeds (`1712905618+16..47`) or try a slightly
  earlier prefix (e.g. 5040) so the word has more lead-in context. Keep
  `semantic_max_tokens=5397`.
- If the AR word is always right but the **join** is audible, widen the comp
  region to 201.6–205.2 s; if it is always rhythmically displaced, comp the whole
  regenerated tail (202.24–215.88 s) and say so in the report.

## Findings to keep in mind

- **A comp must cover the whole word** (`--word-ranges`). Grafting only the
  changed tokens cuts back to the original inside the word — that was the
  round-1 "ف + half a nūn" failure.
- **Donor tokens do not transfer the consonant.** Whole-word donor comps failed
  by ear, and so did direct audio grafts of the Outro word. Do not reopen this.
- **AR re-sing works.** AR sampling is causal, so the word tokens from a short
  render are valid; only the winner needs a `min=max=5397` render for context.
- Token surgery is not sample-local (NAR global coupling); the comp is what
  makes delivery surgical.
- CTC is unreliable at single-consonant resolution; do not accept/reject on CTC.
- YuE2 has no repaint/edit mode. Generic diffusion inpainting cannot choose the
  phoneme.

## Do not redo

- Do not regenerate the baseline semantic, the A/C exports or the binary.
- Do not re-render the 13 donor candidates or re-run the donor route.
- Do not overwrite the original WAV; do not claim bit-identity *inside* edited
  words — only outside the comp regions.

## Session hygiene

`/content` is ephemeral. After any decision or artifact, upload to the GCS root
and commit docs to GitHub. Scorecards: `scorecard_baghdad_moon_two_word.json`
(round 1, H1–H4) and `scorecard_baghdad_moon_e2_round3.json` (round 3, e2 takes),
both in `docs/happy_accidents/Baghdad_Moon/token_surgery/` and GCS `reports/`.
