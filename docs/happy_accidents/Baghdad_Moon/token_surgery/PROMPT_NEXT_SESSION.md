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

- `docs/happy_accidents/Baghdad_Moon/token_surgery/report.md` — per-candidate metrics
- `docs/happy_accidents/Baghdad_Moon/token_surgery/APPROACH.md` — why the pipeline is what it is
- `docs/happy_accidents/Baghdad_Moon/token_surgery/HANDOFF.md` — background/case file

GCS root for this task:
`gs://akbar-december-2024-backup/arabmaqamrock/runs/20261019_baghdad_moon_token_surgery/`

## The goal (unchanged)

The original Baghdad Moon B take is musically right but has two mis-sung words.
Fix exactly those two words by token-level surgery on the original 5397-frame
semantic stream, changing as little else as possible. Do **not** change lyrics,
style prompt, LoRA, seed, sampler settings or GPU type.

- Word 1: `عَلَيْهِ` in Verse 2, sung as `عَلِيم` (ends in م instead of ه).
  Frames 3933–3964, about 157.3–158.55 s.
- Word 2: `فَإِنَّ` in the Outro, sung as `بِأَنَّ` (starts with ب instead of ف).
  Frames 5056–5114, about 202.26–204.54 s.
- The third, muddy `عَلَيْهِ` in the Outro is **not** edited. It is borderline
  acceptable by the user's own judgement.

Original WAV must never be overwritten. Its sha256 is:
`dbc00722534d5ee763ae54a048cd704eaa4c927e37834cd54542eaf379e0de42`

## State when we stopped

- Restore done; model, VAE and LoRAs verified.
- Prefix-capable binary verified on T4: git `58caf774`,
  sha256 `4e1534f3e6fde456198ed5404313a832029193bf7ea47c817086a24a5aa3849c`.
- Gate 1 (semantic) passed exactly: `1b1aa3e2…`, 5397 frames,
  `positive_prefix_tokens 1079`, `negative_prefix_tokens 12`.
- Gate 2 (full render) passed exactly: WAV `dbc00722…`. Batch mode also exact.
- 13 token-splice candidates rendered, one batch, all 5397 frames. Every exported
  semantic matches its input token file.
- 13 local-comp hybrids built with `audio_splice.py`; all report
  `identical_outside_regions: true`.
- Listening pack delivered: 5 montages (original + H1–H4), 10 A/B clips,
  4 full hybrid tracks, plus an Arabic 12-question scorecard.

**The user was in the middle of the listening evaluation with the rating app.
That is the only thing blocking final assembly.**

## What to do first in this session

1. Ask the user for their evaluation result. Ideally the app's
   `runs/<run_id>/results.json` (or `report.json`). If they don't have the file,
   accept a plain answer: for each word, which version sounded correct, and
   whether any seam was audible.

   The five rated versions and what they contain:

   | ID | Word 1 edit | Word 2 edit |
   |---|---|---|
   | `01_original` | none | none |
   | `02_H1_minimal` | final note (8 frames) | onset (13 frames) |
   | `03_H2_e2word` | final note | first 26 frames |
   | `04_H3_e1word` | whole word (31 frames) | onset |
   | `05_H4_bothword` | whole word | first 26 frames |

   Montage timing is identical in all five: word 1 at 2.1–3.4 s, word 2 at
   7.4–9.6 s, total 11.1 s.

2. Record their verdicts in `report.md` (human evaluation section) and update
   `CHECKPOINT.md` status.

3. Pick the winning word-1 edit and word-2 edit. Any mix of
   {final note, whole word} × {onset, first 26 frames} already exists:

   | word 1 ↓ / word 2 → | onset | first 26 |
   |---|---|---|
   | final note | H1 | H2 |
   | whole word | H3 | H4 |

   Just use the matching `hybrid/*.wav` as the final track — **no GPU and no
   re-render needed**.

4. If the user instead asks for a combination involving the C donors
   (`e1_C_A`, `e1_C_C`, `e2_A_onset_A`, `e2_A_onset_C`), generate the combo
   token file with `token_surgery.py`, render once at `min=max=5397` with the
   original seed, then comp. On a fresh GPU runtime:

   ```bash
   ./setup_colab.sh
   B=gs://akbar-december-2024-backup/arabmaqamrock/runs/20261019_baghdad_moon_token_surgery
   gsutil cp $B/bin/audiocpp_cli_prefix_sm75 bin/
   cd bin && sha256sum -c audiocpp_cli_prefix_sm75.sha256 \
     && mv audiocpp_cli_prefix_sm75 audiocpp_cli_prefix \
     && chmod +x audiocpp_cli_prefix && cd ..
   . ./cuda_loader_path.sh
   ./bin/audiocpp_cli_prefix --version   # must print git: 58caf774
   ```

5. Final QC and delivery:
   - Re-run `audio_splice.py` and confirm `identical_outside_regions: true`.
   - Confirm the original WAV is still `dbc00722…`.
   - Export `deliverables/tracks/FINAL_<word1>_<word2>.wav`.
   - Append the human scores to `report.md`; mark `CHECKPOINT.md` complete.
   - Upload the final track and docs to `$B/final/` and `$B/reports/`.
   - Commit and push the docs to GitHub (`gh auth setup-git` first; the repo
     remote hangs without it).

## Fallback, only if both word donors fail by ear

- Word 1 AR resample: `semantic_prefix_file` = first 3933 tokens,
  `semantic_max_tokens=3964`, seed sweep around 1712905618; keep candidates of
  31 frames; comp.
- Word 2 tail resample: prefix = first **5056** tokens (not 5100),
  `semantic_max_tokens=5397`, seeds `1712905618 + 0..15`; evaluate and comp.

## Important findings to keep in mind

- Token surgery is **not** sample-local. Changing 8 of 5397 frames changes the
  whole waveform (NAR global coupling). A one-request baseline control proved
  this is not batch RNG.
- Perceptual collateral is small: median mel Δ outside the edits 0.034–0.071 dB,
  p95 0.33–0.82 dB; the peak 1 s mel Δ lands exactly on the edited second.
- YuE2 has no repaint/edit mode (only `semantic_prefix` continuation). Generic
  diffusion inpainting cannot choose the phoneme, so it is unsuitable.
- The delivery method is a **local comp**: synthesise the corrected word, then
  graft only that word's time range back into the original with 40 ms
  crossfades on quiet points.
- Evidence: word 2 is strong (donor MFCC-DTW 5.24 → 3.54; wrong donors
  5.74–5.88). Word 1 is weaker (original 4.482, best candidate 4.459) because
  its only donor is the differently-arranged Outro.
- CTC is not reliable at single-consonant resolution. Do not use it alone to
  accept or reject a candidate.

## Do not redo

- Do not regenerate the baseline semantic or the A/C exports.
- Do not rebuild the binary.
- Do not re-render the 13 candidates unless a fallback above is needed.
- Do not overwrite the original WAV.
- Do not claim bit-identity *inside* the edited words — only outside them.

## Session hygiene

`/content` is ephemeral. After any decision or new artifact, upload to the GCS
root above and commit docs to GitHub. The scorecard is at
`docs/happy_accidents/Baghdad_Moon/token_surgery/scorecard_baghdad_moon_two_word.json`
and a copy is in GCS `reports/`.
