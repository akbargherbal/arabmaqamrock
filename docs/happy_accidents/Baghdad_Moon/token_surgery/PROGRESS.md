# Progress summary — Baghdad Moon B two-word repair

**Status:** v1 delivered (both words fixed), **one open polish item**: an audible
join in the outro edit.
**Span:** 2026-10-19 → 2026-10-20 (4 sessions across two ephemeral Colab VMs).
**Read with:** `CHECKPOINT.md` (live state), `report.md` (measurements).

---

## 1. Goal and constraints (unchanged)

Fix exactly two mis-sung words in the original take, changing as little else as
possible:

| id | word | section | heard as | correct | frames | time |
|---|---|---|---|---|---|---|
| e1 | `عَلَيْهِ` | Verse 2 | `عَلِيمْ` (ends م) | `عَلَيْهِ` (ends ه) | 3933–3964 | 157.32–158.56 s |
| e2 | `فَإِنَّ` | Outro | `بِأَنَّ` (starts ب) | `فَإِنَّ` (starts ف) | 5056–5114 | 202.24–204.56 s |

The third, muddy `عَلَيْهِ` in the Outro is **not** edited.

Frozen: lyrics, style prompt, LoRA, seed `1712905618`, sampler settings, GPU type
(T4). The original WAV is never overwritten:
`dbc00722534d5ee763ae54a048cd704eaa4c927e37834cd54542eaf379e0de42`.

Original: `02-استيداع-قمر-بغداد-ولوعة-الوداع-B_1712905618`
(5397 semantic frames, 48 kHz stereo, 215.879 s, 10,362,176 samples).

---

## 2. What was proven (keep these)

1. **Reproduction is exact.** Semantic-only re-run is byte-identical
   (`1b1aa3e2…`, 5397 frames, 1079 positive / 12 negative prefix tokens, 0
   truncated). A full render from `tokens_baseline.json` with
   `min=max=5397` is bit-identical (`dbc00722…`). Batch mode is exact too.
2. **The prefix-capable sm75 binary works on the T4** (`4e1534f3…`,
   `git 58caf774`), built from CPU-only on a separate machine.
3. **Token surgery is not waveform-local.** Changing 8 of 5397 frames changes
   every sample (NAR flow is globally coupled). Measured median mel Δ outside
   the edited word 0.034–0.071 dB, p95 0.33–0.82 dB; the peak Δ lands on the
   edited second. Therefore token edits must be delivered by a **local audio
   comp**.
4. **A comp must cover the whole word, and must clip longer runs.**
   `audio_splice.py --word-ranges` grafts the word, not just changed tokens.
   An AR tail render changes 341 frames; without clipping, the comp would
   replace the whole 13.6 s outro. All deliveries verify
   `identical_outside_regions: true`.
5. **Donor tokens/audio do not transfer the consonant.** 13 length-preserving
   same-take splices, whole-word donor comps, and direct audio grafts all failed
   by ear (round 1: 0/4). The donor is not a timbre problem — it does not deliver
   the phoneme in the target context.
6. **AR re-sing works.** Give the AR the real lyric with a prefix, let it
   generate the word/phrase, sweep seeds, then comp. AR sampling is causal, so
   word tokens from a short render are valid; only the winner needs a full
   5397-frame render.
7. **YuE2 has no repaint/edit mode**; generic diffusion inpainting fills short
   gaps unconditionally and cannot choose a phoneme. CTC is unreliable at
   single-consonant resolution — never accept/reject on CTC alone.
8. **A local comp can be surgical.** The delivered track differs from the
   original only inside the two comp regions; every other sample is
   bit-identical.

---

## 3. Session / round history

| round | date | what was tried | outcome |
|---|---|---|---|
| build + gates | 2026-10-19 | restore, CPU build, semantic gate, baseline gate, batch control | **both gates exact** |
| 1 | 2026-10-19/20 | 13 donor-token splices + H1–H4 local comps | **rejected 0/4** (`rating_20261020-1223.md`) |
| 2 | 2026-10-20 AM | diagnosis: comp cut mid-word; donors don't carry `ه`/`ف`. AR re-sing word 1, 16 seeds | **word 1 fixed** (`e1_ar_s03`, accepted) |
| 2b | 2026-10-20 AM | word 2: AR tail (prefix 5056 → 5397), 16 seeds, 5 auditioned for rhythm | **five takes** in `listen_v4/` |
| 3 | 2026-10-20 12:57 | user rating of the five tails | **`s08` and `s13` both 5/5**; `s08` chosen |
| 3b | 2026-10-20 14:50 | final assembly, QC, delivery | **v1 delivered** (`51c6e238…`) |
| 4 | 2026-10-20 PM | post-delivery listen | **S2 join audible**; documentation + next options |

### Round 1 — donor route (closed)

Thirteen length-preserving splices from the same take / A / C variants, rendered
in one batch. All rendered correctly; all were heard as unchanged or worse. The
word-2 comp bug (grafting only changed frames) cut back to the original inside
the word — the "ف + half a nūn" artifact. Fixed with `--word-ranges`, but the
donor still failed as a phoneme. **Do not reopen the donor route.**

### Round 2 — word 1 by AR re-sing (accepted)

Prefix = first 3933 tokens, `semantic_max_tokens = 3964`, seeds
`1712905618+0..15`. Four diverse seeds got full 5397-frame renders; `s01`,
`s03`, `s04` passed by ear, `s15` failed. Chosen: **`s03`**. Comp region
156.995–158.855 s. Transparent by ear (S1).

### Round 3 — word 2 by AR tail re-sing (phoneme fixed)

Prefix = first 5056 tokens, `semantic_max_tokens = 5397`, same seed sweep.
All 16 tails are valid (5397 frames, first 5056 tokens identical, 338–341
regenerated). Takes are mutually unrelated (55–58 of the word's 58 tokens
differ), so the shortlist was chosen for **rhythmic alignment** of the 202–205 s
energy envelope: `s08` 5.5 dB, `s13` 5.8, `s11`/`s14` 6.2, `s07` 6.4.

Listening verdict (`rating_20261020-1557.md`, not blind):

| take | `ف` | diction | melody | seam | overall | keep |
|---|---|---:|---:|---|---:|---|
| `00_ORIGINAL` | still `ب` | 1 | 1 | bad | 1 | no |
| **`s08`** | **fixed** | **5** | **5** | **none** | **5** | **yes** |
| **`s13`** | **fixed** | **5** | **5** | **none** | **5** | **yes** |
| `s14` | unclear (`v`) | 4 | 4 | none | 4 | maybe |
| `s11` | fixed | 5 | 1 | bad | 1 | no |
| `s07` | still `ب` | 1 | 1 | bad | 1 | no |

`s08` chosen over the tied `s13` for better rhythmic alignment. `s11` is
informative: the word was right, but the re-sung tail collapsed afterwards
(`الله` mangled into `ينزعه`) — a warning about tail continuity.

### v1 delivery (2026-10-20 14:50 UTC)

`FINAL_e1_ar_s03_s08.wav` = word-1 hybrid `e1_ar_s03` + word-2 `s08` comp.

| check | value |
|---|---|
| sha256 | `51c6e238dfaad123779e32b113786df651b4c7053771f6f7dfc4970e2fb2a8e1` |
| format | 48 kHz stereo PCM_16, 215.879 s |
| original | `dbc00722…`, unchanged |
| changed span | 156.9964–158.8546 s and 201.8353–204.7747 s (230,261 samples) |
| max diff outside regions | **0** |
| boundary sample step | equals original at all four cuts (no click) |
| GCS | `$B/final/FINAL_e1_ar_s03_s08.wav` |

---

## 4. Open issue (round 4) — audible join in the outro

**User's report:** v1 is close, but the outro edit has a sudden jump / "two
clips joined" feel. S1 (Verse 2, word-level) is transparent; S2 (Outro) is not.
This is a **join/perception** problem, not a wrong phoneme — `فَإِنَّ` is
correct.

**Measured cause (10 ms envelopes, original vs `s08`; word timing from
`evidence.md`):**

- The comp edges are fixed word ± 0.3 s, **not** chosen at word/phrase
  boundaries. With the ASR/CTC word timing:
  - start **201.835 s** is inside the preceding `عَلَيْهِ` (201.04–202.26 s);
  - end **204.775 s** is inside `الله` (204.54–204.98 s), not after it.
  So the comp cuts both neighbouring words mid-vowel and crossfades there.
- Both edges are also not low-energy: 201.835 s sits in a sustained ~74–75 dB
  region; 204.775 s sits at ~71 dB.
- At the end cut the take is **~+3.5 dB** relative to the original; right after
  the cut the curves diverge sharply (at 205.10 s: original 76.2 dB, take
  69.3 dB). A 40 ms fade removes the click but cannot hide a level/timbre step.
- More fundamentally, the comp reverts to the **original mid-phrase**: the model
  re-sings `فَإِنَّ اللهَ يَنْزِعُهُ` as one unit (202.26–207.74 s), but we keep
  only `فَإِنَّ` (to 204.775 s) and cut back to the original inside `الله`. The
  model's phrase continuation is discarded, so the join is phrase-internal even
  though the region was intended to end at a word boundary.

**User's proposals:**

1. Comp a **sub-phrase** (`فَإِنَّ اللهَ يَنْزِعُهُ`) as one unit, so joins land
   at phrase edges and the interior stays internally consistent.
2. Use **4-stem separation** to choose cut points at the lowest trough across
   stems (drums/bass near-silent), making the cut inaudible.
3. Go **case by case**: word-level worked for S1, so keep it; use phrase-level
   for S2 if it helps.

**Assessment (including pushback):**

- Sub-phrase is the stronger idea *for this artifact*. The problem is not only
  the cut point; it is reverting from the model's phrase into the original
  mid-phrase. Phrase-level comp moves both joins to phrase edges.
- Caveat: a longer comp replaces more original audio (including music). We
  measured that `s08`'s post-word envelope diverges from the original after
  ~205 s, so a whole-phrase comp may introduce rhythmic drift. Test `s08` and
  `s13` by ear before committing. If the phrase drifts, a GPU re-render with an
  earlier prefix (so the phrase is re-sung with lead-in) or a vocal-stem-only
  comp is the fallback.
- Stem separation is useful but not a magic trough finder: stems sum to the mix,
  so the global trough is essentially the mix trough. What stems add is
  *attribution* — avoid cutting a sustained bass note, a drum transient, or a
  held vowel. For a vocal comp the primary criterion should be a **voiceless gap
  or breath in the lead vocal**, with the instrumental stems as constraints.
  Separation artifacts can also mislead; validate against the full mix.
- Case-by-case is right: S1's word is short (31 frames) and its word-level comp
  was accepted as transparent; S2's word is 2.3 s, stretched, inside a
  continuous phrase, and its comp is audible.

**Next experiments (cheap → expensive):**

1. **No GPU:** phrase-level comps from the existing `s08`/`s13` tails. Target
   the musical unit `فَإِنَّ اللهَ يَنْزِعُهُ` (202.26–207.74 s per
   `evidence.md`), with the end **after 207.74 s** — or, if that drifts, at
   least **after `الله` (204.98 s)**, never inside it. The start is still
   inside the preceding word; use a longer fade over 201.8–202.2 rather than a
   hard word edge. Audition 2–4 variants; the full tails are already in
   `$B/candidates/v3_e2_ar/`.
2. **No GPU:** word-level comp with level matching and a longer fade
   (120–200 ms) at envelope crossings — quick sanity check, may not fix phrase
   continuity.
3. **CPU/GPU:** Demucs vocal/instrumental split; comp the **vocal stem only**
   and keep the original instrumental. (`demucs` is not installed in the
   current runtime; needs `pip install demucs`.)
4. **GPU:** re-render the phrase with an earlier prefix (e.g. frame 4980–5000)
   and `max_tokens=5397`, a few seeds, then phrase-comp. Only if 1–3 fail.

Do **not** claim bit-identity inside the comp regions — only outside them.

---

## 5. Artifact map

GCS root:
`gs://akbar-december-2024-backup/arabmaqamrock/runs/20261019_baghdad_moon_token_surgery/`
(`$B` below).

| path | contents |
|---|---|
| `$B/final/FINAL_e1_ar_s03_s08.wav` | delivered v1 + `.sha256` |
| `$B/deliverables/listen_final/` | original vs FINAL A/B clips (e1, e2) |
| `$B/candidates/v3_e1_ar/` | word-1 AR renders (incl. `e1_ar_s03.wav`) |
| `$B/candidates/v3_e2_ar/` | all 16 word-2 tails |
| `$B/e2_resample/semantic/` | token export per tail |
| `$B/tokens/` | baseline + 13 splice token files + word-1 full tokens |
| `$B/candidates/v2/` | 13 donor renders + hybrids (closed route) |
| `$B/deliverables/listen_v4/` | round-3 word-2 pack |
| `$B/reports/` | all docs, scorecards, ratings |
| `$B/workspace/happy_accident_workspace_20261020c.tar.gz` | text workspace |

GitHub (tracked): `docs/happy_accidents/Baghdad_Moon/token_surgery/` —
`CHECKPOINT.md`, `report.md`, `PROGRESS.md`, `HANDOFF.md`, `APPROACH.md`,
`RESTORE.md`, `CPU_BUILD.md`, scripts, scorecards and ratings.

`happy_accident/` is gitignored (audio); its durable copy is GCS.

---

## 6. Do not redo

- Do not regenerate the baseline semantic, A/C exports, or the prefix binary.
- Do not re-render the 13 donor candidates or reopen the donor route.
- Do not overwrite the original WAV.
- Do not re-render the 16 word-2 tails — they are all backed up.
- Do not accept/reject on CTC alone.
- Do not claim bit-identity *inside* the edited words; only outside the comp
  regions.

---

## 7. Lessons worth carrying forward

1. **Fix the model's behavior, not just the tokens.** AR re-sing succeeds where
   donor token/audio grafts fail because the model sees the real lyric and
   context.
2. **Token surgery needs an audio comp.** The NAR flow is globally coupled;
   sample-local claims are false except outside the graft.
3. **A comp is a musical edit, not just a signal edit.** Cutting mid-phrase,
   at a fixed margin, can be inaudible in one song and obvious in another.
   Choose join points in the performance (breath/gap), and consider comping the
   musical unit, not the lexical token range.
4. **Measure the seam after delivery.** Waveform boundary continuity (no click)
   is necessary but not sufficient; level, timbre, timing and phrase continuity
   matter more.
5. **Sweep seeds for performance, not just similarity.** The winning word-2 take
   was picked for rhythmic alignment; token diversity between seeds is huge.
