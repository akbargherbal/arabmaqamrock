# Fixing a mis-sung word in a generated song — verified options

> Status: researched 2026-10-20. Applies to YuE2 via `audio.cpp`, but the
> conclusion generalises to any song you generated and love.

## The problem in one sentence

We can reproduce the original render **bit-for-bit** from its saved semantic
tokens, but asking the model to render a *slightly different* token stream
re-decodes the whole waveform, because the NAR flow is globally coupled.

## What is actually possible (in order of fidelity)

| approach | local? | keeps original? | verdict |
|---|---|---|---|
| Re-render with the original tokens | — | **bit-identical** | reproduction, no fix |
| Token surgery + full re-render | no (global ripple) | perceptually ~99.9 % | good source of a corrected word |
| Model repaint / inpainting | supposedly | — | **not implemented for YuE2** |
| Generic audio inpainting (diffusion) | yes | yes | cannot control *which phoneme* |
| **Token surgery + local comp into the original** | **yes (sample-exact outside)** | **bit-identical outside** | **recommended** |

### 1. Reproduction is solved

With `semantic_prefix_file` + `semantic_min_tokens = semantic_max_tokens = N`
the AR stage is skipped and the NAR/VAE are deterministic for a request. A
render from the saved 5397-token stream is **bit-identical** to the original
(sha256 `dbc00722…`, verified twice, including once through `--request-sequence`).

### 2. Token surgery is not waveform-local

Changing even 8 of 5397 semantic frames changes every sample: the candidate
differs from the original from ~2 s to the end. This is expected, not a bug:

- The upstream YuE2 docs state: *“a prefix does not reproduce the draws of an
  uninterrupted run: the sampler RNG starts at the first sampled frame, and
  prefilled K/V differ numerically from step-decoded K/V.”*
  (`docs/models/yue2.md` in `0xShug0/audio.cpp`)
- The NAR acoustic flow attends over the whole token sequence, so a local token
  change perturbs the global latent field.

Perceptually the change is still concentrated: median mel Δ outside the edit
regions is **0.03–0.07 dB**, and the peak 1 s mel Δ sits exactly on the edited
second. So a full re-render is a *plausible* delivery, just not a surgical one.

### 3. YuE2 has no repaint/inpainting mode

`audio.cpp` exposes generic `--repaint-start/--repaint-end/--repaint-strength`
flags, but YuE2 is not an `Edit` model in the supported-model table (only
`Music`). Its documented continuation surface is `semantic_prefix` /
`semantic_prefix_file` only. Using the repaint flags on `yue2` would be
ignoring-or-improvising; true latent inpainting would require modifying the NAR
(masked flow) — a research task, not an ad-hoc fix.

### 4. Generic audio inpainting is the wrong tool here

Diffusion audio inpainting (Moliner & Välimäki, *Diffusion-Based Audio
Inpainting*, JAES 72(3), 2024, arXiv:2305.15266) reconstructs gaps of roughly
≤300 ms, unconditionally. It can make a hole sound plausible, but it cannot make
the singer say a **specific** word. We need phoneme control, which the semantic
tokens already give us.

### 5. The production method that fits: vocal comping

Comping — assembling a take from the best words of several takes, with short
crossfades on consonants — is standard studio practice (iZotope, Logic/Ableton
comp lanes). Typical guidance: cut on a consonant, use 10–20 ms crossfades,
never splice mid-vowel.

Our case is ideal for it: the same take contains the word sung **correctly** in
another section (the Outro sings `عَلَيْهِ` correctly; Verse 2 sings `فَإِنَّ`
correctly).

## Recommended pipeline (the one used here)

1. **Reproduce** the original from its saved semantic tokens (bit-exact).
2. **Edit tokens** only in the target word's frame range, using the same-take
   correct occurrence as donor (length-preserving).
3. **Render** the edited stream once (AR skipped).
4. **Comp** only the edited word's time range from the candidate back into the
   original WAV, with ~40 ms crossfades snapped to the quietest point
   (consonant gap) within ±120 ms.
5. **Verify**: samples outside the comp regions must be bit-identical; the mel
   change must be concentrated in the edited second.

Result: original everywhere except ~0.8–1.9 s per fixed word.

`happy_accident/audio_splice.py` implements steps 4–5 and is reusable for any
future "one bad word" repair:

```bash
python3 audio_splice.py ORIGINAL.wav CANDIDATE.wav OUT.wav \
  --tokens tokens_fixed.json --baseline tokens_baseline.json
```

## Honest limitations

- The corrected word is synthesised by the model from donor tokens; it is not a
  recording of the singer. It matches timbre because it is the same model, take
  and context, but the final judgement is by ear.
- The objective verifier (Arabic CTC) can separate the *phrase-level* correct vs
  wrong instances, but is not reliable at single-consonant resolution. Donor
  acoustic similarity (MFCC-DTW) is the stronger signal for `فَإِنَّ`; for
  `عَلَيْهِ` the donor comes from a different section, so DTW is confounded by
  arrangement.
- Comping at a word boundary can leave a faint seam if the candidate's
  background differs; using quiet-point crossfades mitigates it.
