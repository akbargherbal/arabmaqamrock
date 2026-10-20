> **v1 DELIVERED — 2026-10-20 14:50 UTC; one open polish item.**
> Both words are fixed and `$B/final/FINAL_e1_ar_s03_s08.wav` (`51c6e238…`) is
> delivered. The user hears a join in the **outro** edit (S2); S1 is transparent.
> Do not rerun the steps below. Read `CHECKPOINT.md` §6.5 and `PROGRESS.md` §4
> for the seam work; the word-level route is done.

We are resuming the Baghdad Moon B two-word repair. The previous Colab VM is gone,
so nothing from `/content` survives except GitHub and GCS.

Read this first, then the live checkpoint:

```
https://github.com/akbargherbal/arabmaqamrock/blob/main/docs/happy_accidents/Baghdad_Moon/token_surgery/CHECKPOINT.md
```

Also, as needed:
- `docs/happy_accidents/Baghdad_Moon/token_surgery/HANDOFF.md` (read §0.5)
- `docs/happy_accidents/Baghdad_Moon/token_surgery/report.md` (§5–§6)
- `docs/happy_accidents/Baghdad_Moon/token_surgery/PROMPT_NEXT_SESSION.md`

GCS root:
`gs://akbar-december-2024-backup/arabmaqamrock/runs/20261019_baghdad_moon_token_surgery/`

## Goal (unchanged)

The original take is musically right but two words are mis-sung. Fix exactly those
two by token-level surgery on the original 5397-frame semantic stream, changing as
little else as possible. Do not change lyrics, style, LoRA, seed, sampler settings
or GPU type.

- Word 1 `عَلَيْهِ` (Verse 2): sung `عَلِيم`. Frames 3933–3964, ~157.3–158.55 s.
- Word 2 `فَإِنَّ` (Outro): sung `بِأَنَّ`. Frames 5056–5114, ~202.26–204.54 s.
- The third, muddy `عَلَيْهِ` in the Outro is NOT edited.

Original WAV must never be overwritten:
`dbc00722534d5ee763ae54a048cd704eaa4c927e37834cd54542eaf379e0de42`

## State when we stopped (2026-10-20 ~12:25 UTC)

- **Word 1 is FIXED and accepted by ear.** AR re-sing, seed `s03`.
  Hybrid: `$B/candidates/v3_e1_ar/e1_ar_s03.wav`
  Tokens: `$B/tokens/tokens_e1_ar_s03_full.json`
  Comp region 156.995–158.855 s, `identical_outside_regions: true`.
- **Word 2 is waiting on the user's ear.** 16 AR tails were rendered from
  prefix = first 5056 tokens, `max_tokens=5397`, seeds `1712905618+0..15`.
  Five takes (`s08, s13, s11, s14, s07`) are in
  `$B/deliverables/listen_v4/` with the rating-app scorecard
  `scorecard_baghdad_moon_e2_round3.json`. **All 16 raw renders are backed up**
  in `$B/candidates/v3_e2_ar/`, so more takes can be auditioned without a GPU.
- Round 1 (the 13 donor splices) was rejected 0/4; the donor route is closed.
  Causes and fixes are in `report.md` §5–§6.
- The assembly script is tested end-to-end (no GPU needed).

## What to do first in this session

1. Ask for the rating result — ideally the app's `runs/<run_id>/results.json` (or
   `report.json`); otherwise a plain answer: which take says `فَإِنَّ`, is the word
   complete, is any seam audible.
2. Record the verdict in `report.md` §6.4 and update `CHECKPOINT.md`.
3. Assemble the final track (no GPU):

```bash
B=gs://akbar-december-2024-backup/arabmaqamrock/runs/20261019_baghdad_moon_token_surgery
cd /content && git clone https://github.com/akbargherbal/arabmaqamrock.git
cd arabmaqamrock && gh auth setup-git
gsutil cp $B/workspace/happy_accident_workspace_20261020c.tar.gz /tmp/
tar -xzf /tmp/happy_accident_workspace_20261020c.tar.gz -C .
mkdir -p happy_accident/original happy_accident/runs
gsutil -m cp "gs://akbar-december-2024-backup/arabmaqamrock/runs/20261018-162827_batch_12_variants_backing_vocals/02-*B_1712905618.wav" happy_accident/original/
sha256sum happy_accident/original/*.wav            # must be dbc00722…

# word-1 hybrid (accepted) and the chosen word-2 take, e.g. s08
gsutil cp $B/candidates/v3_e1_ar/e1_ar_s03.wav happy_accident/runs/e1_resample/hybrid/e1_ar_s03.wav
gsutil cp $B/candidates/v3_e2_ar/e2_ar_s08.wav happy_accident/runs/e2_resample/pick.wav
gsutil cp $B/e2_resample/semantic/e2_ar_s08.json happy_accident/runs/e2_resample/pick.json

python3 happy_accident/runs/assemble_final.py \
  happy_accident/runs/e2_resample/pick.wav happy_accident/runs/e2_resample/pick.json \
  happy_accident/deliverables/tracks/FINAL_e1_ar_s03_s08.wav
```

`assemble_final.py` comps word 2 onto the word-1 hybrid, asserts
`identical_outside_regions`, and prints both sha256s.

4. Final QC and delivery:
   - original still `dbc00722…`; final differs only in 156.996–158.855 s and
     201.835–204.775 s;
   - upload to `$B/final/`, docs to `$B/reports/`;
   - append human scores to `report.md`, mark `CHECKPOINT.md` complete;
   - commit and push (`gh auth setup-git` first — the remote hangs without it).

## If none of the five word-2 takes works

- First audition the other 11 from the same sweep (already rendered, no GPU):
  `s00 s01 s03 s04 s06 s09 s10 s12 s15`. `s00/s04/s10` were only skipped for
  rhythmic drift, not for the phoneme.
- If all 16 fail: render more seeds (`1712905618+16..47`) or use an earlier
  prefix (e.g. 5040) so the word has more lead-in; keep `max_tokens=5397`.
- If the word is right but the join is audible: widen the comp region to
  201.6–205.2 s. If it is always rhythmically displaced: comp the whole
  regenerated tail (202.24–215.88 s) and say so in the report.

## Findings to keep in mind

- **A comp must cover the whole word** (`--word-ranges`), and it must **clip** a
  run that extends past the word — an AR tail render changes 341 frames, and
  without clipping the comp would replace the whole 13.6 s outro.
- **Donor tokens do not transfer the consonant.** Whole-word donor comps failed
  by ear, and so did direct audio grafts of the Outro word. Don't reopen this.
- **AR re-sing works.** AR sampling is causal, so word tokens from a short render
  are valid; only the winner needs `min=max=5397` for context.
- Token surgery is not sample-local (NAR global coupling); the local comp is what
  makes delivery surgical.
- CTC is unreliable at single-consonant resolution; never accept/reject on it.
- YuE2 has no repaint/edit mode; generic diffusion inpainting cannot choose the
  phoneme.

## Do not redo

- Do not regenerate the baseline semantic, the A/C exports, or the binary.
- Do not re-render the 13 donor candidates or re-run the donor route.
- Do not overwrite the original WAV.
- Do not claim bit-identity *inside* the edited words — only outside the comp
  regions.

## Session hygiene

`/content` is ephemeral. After any decision or new artifact, upload to the GCS
root above and commit docs to GitHub.
