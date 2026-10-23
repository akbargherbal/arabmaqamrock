# Repair record — case 001

Template: repair_session_runbook.md §4. Filled to the current gate. `TODO` means
"not yet known / needs the GPU run".

```yaml
case: 001
song: 03-الرد-على-الواشي-والرسوخ-كالأرعن (Harith bin Hiliza, singing-techniques batch)
take: 03-الرد-على-الواشي-والرسوخ-كالأرعن_3_810750224.wav
take_sha256: 3981465c20614d00cdc025e8f99525bb85268d5bfb842af1972f51a6d34b7b69
model / seed / prompt:
  model: yue2-3b-bf16.gguf (sha256 4cf3fdff…), VAE yue2-vae-f16.gguf (d4f4a05d…)
  lora: arabmaqamrock v3 AR 3531bb91… / NAR a7eabcad…, scale 1.0
  seed: 810750224
  cap: 6750 (quantile 0.95, 503 letters); frames 5938; duration 237.5187 s
  lyrics_sha256: 5f9548495d57adf401f8ce5b3c2f552cd614ae432f04c2bea01b840a94fb40c8
  style_sha256:  b8ee0cddb918cd17c6000f883948dca45d57458d72db568d7fec6be5e65809e8
lyric: أَيَّمَا خُطَّةٍ أَرَدْتُمْ فَأَدُّوهَا إِلَيْنَا
target_word: فَأَدُّوهَا
occurrence: 1 of 1 (word 65 of 115)
section / line: Verse 2, line 14 (0-based), first line of the verse
defect:
  heard: single د — فَأَدُوهَا; the shaddah/geminate is collapsed
  target: fa-ʾad-dū-hā, with closure + release on دّ
  class: consonant (gemination / shaddah)
  note_after: keep          # the هَا (415→465 Hz) and إِلَيْنَا are correct
  must_not_change: أَرَدْتُمْ; هَا; إِلَيْنَا; the 311→355→370→415→465→368 contour; instrumental; timing
alignment:
  tool: yue2-karaoke-align scripts/a1_align_run.py (CPU), Demucs vocal stem
  model: akbargherbal/wav2vec2-large-xlsr-53-arabic @ 4ca1c9c6ac85
  date: 2026-10-23T10:54:10Z
  result: 115/115 words, coverage 0.943, on/off 2.32, intro ok
  target_box: 126.790–129.180 s (A1 end 127.810 is mid-هَا; char CTC end
              127.612 is still /u/; the note continues through إِلَيْنَا and
              ends ≈129.15, not at the aligner's 128.87)
  neighbours: أَرَدْتُمْ 125.470–126.430; إِلَيْنَا 128.130–128.870
  caveat: one word elsewhere spans 24.3 s (aligner collapse); not near this edit.
          Use a local 122–130 s re-align for downstream QC, not the whole song.
unit ladder:
  L1 phrase  126.60–129.18  (first; joins in gap + breath)
  L2 word    126.60–127.72  (keeps the original هَا + إِلَيْنَا note)
  L3 syllable 127.18–127.65  (closure + release + vowel; the floor)
generation: 126.44–130.00; prefix 3161; max 3250 (89-frame tail)
comp: vocal stem only; fades 30/60 (L1), 30/40 (L2), 10/15 (L3); level-matched
candidates: 8 seeds, 810750224 + 0..7 (TODO)
shortlist: TODO                 # take, closure ms, char score, f0, duration, edge
accepted: TODO
final: TODO                     # path, sha256, changed spans, outside diff
checks: TODO                    # outside 0 | edges | duration | melisma | downstream
verdict: TODO                   # ship | keep original | retry
notes: >
  The take has no exported semantic stream; the repair is blocked on the
  re-derive + bit-identity gate (§4 of PLAN.md). Unit proposed from the vocal
  stem, not from the word box: start at the quietest point of the 0.36 s gap
  (126.60), end at the start of the correct continuous note (127.72) — guide
  §5.2's "keep the original note and end the comp at its start". The note runs
  through إِلَيْنَا and ends ≈129.15. L1 re-sings the whole phrase (joins in the
  gap and the breath); if it fails, L2 keeps the note; if that fails, L3 goes to
  the syllable. The defect is a geminate, so the shortlist metric is closure
  duration, not a word CTC score.
```

## Gate log

| gate | status | evidence |
|---|---|---|
| A — defect card | **waiting on the ear** | `intake/defect_card.md` |
| B — unit ladder | **waiting on the ear** | `review/01_*_line` (verdict), `review/03L*` (units) |
| token provenance (bit-identity) | **not run** | needs T4 |
| C — take pick | not run | — |
| D — final listen | not run | — |

## Measured boundaries (vocal stem)

| marker | time | evidence |
|---|---|---|
| `أَرَدْتُمْ` note offset | ≈126.46 | f0 310 → 237 Hz, unvoiced after |
| gap quietest point | **126.60** | −31.6 dB (band 200–3500 Hz) |
| `فَأَ` onset | 126.788 / vowel 126.84 | char CTC; f0 311 Hz |
| `دُو` notes | 127.04 → 127.28 | f0 355 → 370 Hz; F1≈400 / F2≈1100 → /u/ |
| release before `هَا` | 127.60 – 127.74 | unvoiced; clean join at 127.72 |
| `هَا` (word-final) | 127.76 – ≈128.10 | f0 415 → 465 Hz; F1≈835 / F2≈1300 → /a/ |
| `إِلَيْنَا` onset | ≈128.13 | formants move to F1≈505 / F2≈1850 (front vowel) |
| phrase tail / note end | 128.85 – ≈129.15 | f0 descends 427→368 Hz, still −15 dB; **no gap between the words** |
| breath | 129.20 – 129.75 | −27 to −37 dB; P's clean end at 129.18 |
| `تَمْشِي` | 129.99 | next word |
| target closure | ≈55 ms (127.21–127.26) | low-energy run |
| donor `دّ` in `حُدِّثْتُمُوهُ` | ≈176.4 | same take; closure ≈100–120 ms (approx.) |

## Open items

- [ ] Ear: confirm `heard` and `note_after: keep`.
- [ ] Ear: approve the ladder (L1 first; L2/L3 only if it fails).
- [ ] Confirm no second defect in the take.
- [ ] Decide on `export_semantic` default for future runs.
- [ ] T4: re-derive tokens, prove `3981465c…`.
- [ ] T4: sweep 8 seeds, score, shortlist.
- [ ] Ear: pick.
- [ ] T4: full render, comp, verify, package.
- [ ] Fill `final`, `checks`, `verdict`; close the case.
