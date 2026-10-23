# Case 001 — `فَأَدُّوهَا إِلَيْنَا` (Harith 03, take `810750224`)

**Status: PLANNING.** No audio edited, no GPU used. The case folder holds the
intake, the alignment index, the ladder, the audition loops and the Colab plan.

> **Goal:** fix one pronunciation error quickly. Start with the whole phrase;
> narrow only if it fails. The plan is in [PLAN.md](PLAN.md).

## The take

| | |
|---|---|
| Run | `20261022-185953_harith_bin_hiliza_singing-techniques_formatted` |
| Take | `03-الرد-على-الواشي-والرسوخ-كالأرعن_3_810750224.wav` |
| Seed | `810750224` |
| Cap / frames | `6750` / **5938** frames @ 25 fps |
| Duration | 237.5187 s |
| sha256 | `3981465c20614d00cdc025e8f99525bb85268d5bfb842af1972f51a6d34b7b69` |
| Lyrics sha256 | `5f9548495d57adf401f8ce5b3c2f552cd614ae432f04c2bea01b840a94fb40c8` |
| Style sha256 | `b8ee0cddb918cd17c6000f883948dca45d57458d72db568d7fec6be5e65809e8` |

## The defect

Line 14 (0-based), Verse 2, sung as one prompt line:

```
أَيَّمَا خُطَّةٍ أَرَدْتُمْ فَأَدُّوهَا إِلَيْنَا
```

| field | value |
|---|---|
| target | `فَأَدُّوهَا إِلَيْنَا` (the phrase around the word) |
| occurrence | 1 of 1 |
| heard | the geminate `دّ` is collapsed to a single `د` — `فَأَدُوهَا` |
| target | `fa-ʾad-dū-hā`, with a real geminate |
| class | consonant / gemination (shaddah) |
| note after | **keep** — the `هَا + إِلَيْنَا` note is correct |
| must not change | `أَرَدْتُمْ`, the note, the instrumental, timing |

The closures: **≈55 ms** in this take vs **≈100–120 ms** in the same take's
correct `حُدِّثْتُمُوهُ` (176.0–177.8 s). The ear is the verdict.

## Why the phrase, not the letter

You were right: `هَا` and `إِلَيْنَا` are **not separated**. The 465 Hz note
runs through both words and descends to ≈368 Hz at 129.10, then a breath, then
`تَمْشِي` at 129.99. There is no gap to cut in between the words.

So the ladder starts at the phrase and narrows only if needed:

| level | comp (s) | replaces | joins |
|---|---|---|---|
| **L1 — phrase** | **126.60 – 129.18** | `فَأَدُّوهَا إِلَيْنَا`, including the note | gap before, breath after |
| **L2 — word** | 126.60 – 127.72 | `فَأَدُّو`; keeps the original note | gap before, note start after |
| **L3 — syllable** | 127.18 – 127.65 | `دُّو` (closure + release + vowel) | closure before, release after |

L3 is the floor: a single consonant cannot be comped on its own; the syllable is
the smallest stable unit.

**One render batch, three comps.** The model sings the phrase once; the same
candidate is comped wide (L1), then narrower (L2), then microscopic (L3). No new
generation between levels.

**What you hear:** 3 shortlisted candidates at L1 on the full line. If one
passes, done. If not, L2. If not, L3. At most 6–8 listens, and the session stops
at the first success.

## What is proven, what is not

Proven locally (CPU):

- WAV hash matches the sidecar; lyrics and style hashes match the run;
- forced alignment: **115/115 words**, coverage 0.943, on/off 2.32, intro ok;
- the word runs 126.79–≈128.13, and the note continues through `إِلَيْنَا` to
  ≈129.15 (f0 465→368 Hz); formants confirm `/u/` → `/a/` → front vowel;
- the closure is ≈55 ms vs ≈100–120 ms in the same-take correct geminate.

**Not proven — the gate:** this take has **no exported semantic token stream**.
Before any edit, the T4 must re-derive the 5938-frame stream and prove the
baseline WAV is bit-identical (`3981465c…`). If that fails, stop.

Also unproven until the batch: that the model produces the geminate at all, and
that the phrase candidate keeps the melody. The ladder tests both.

## Listen first

`review/` (`mix` = full mix, `vocal` = Demucs stem):

| file | what it is |
|---|---|
| `01_*_line_123.00_129.20` | **judge the note and the join here** |
| `02_*_unitL1_126.60_129.18` | the whole phrase (L1) |
| `02_*_unitL2_126.60_127.72` | the word, note kept (L2) |
| `02_*_unitL3_127.18_127.65` | the syllable (L3) |
| `03L1_*_loop3` / `03L2_*_loop3` / `03L3_*_loop3` | each unit three times |
| `04_L1_*_marked` / `04_L2_*_marked` | clicks at the unit boundaries |
| `05_*_donor_geminate_175.60_178.50` | same take, correct `دّ` in `حُدِّثْتُمُوهُ` |
| `07_*_geminate_loop4` | target `د` vs donor `دّ`, four times each |
| `10_*_QUICK_word_L1_L2_L3` | locator only: word → L1 → L2 → L3 |

The `.wav` files are git-ignored; regenerate them with `scripts/make_loops.py`.

> **Review rule (guide §8, rule 10):** a 1 s clip is for locating the edit, not
> for judging the repair. Judge on `01_*_line_…` (or the full track).

## Read next

- [PLAN.md](PLAN.md) — the ladder, the one-batch workflow, the Colab runbook.
- [record.md](record.md) — the §4 repair record, filled to the current gate.
- [intake/defect_card.md](intake/defect_card.md) — the one card to approve.
- [intake/alignment.md](intake/alignment.md) — how the index was produced.
- [intake/guide_audit.md](intake/guide_audit.md) — the plan checked against the
  field guide.
