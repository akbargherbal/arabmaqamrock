# Lessons — Baghdad Moon B token surgery

**Status of the artifact:** v2 delivered, candidate `41` accepted by ear.
User’s own rating: **9.5–9.7/10**, with one remaining glitch to investigate.
Final: `FINAL_e1_ar_s03_s13_41.wav`, sha256 `9b8fdb21…`.

This is the retrospective we should read before doing another “fix two words”
job. It follows the six stages of the project.

---

## 0. The one-sentence lesson

**The winning move was not to regenerate better; it was to replace less.**

The final track is the original performance plus the smallest possible corrected
unit — `فَإِنَّ` only — with the original `اللهَ يَنْزِعُهُ` and its 5.5 s final
`ه` melisma left literally untouched. The model was necessary to sing the
missing phoneme; it was not necessary to re-sing the rest.

---

## 1. The case study: good diagnosis, wrong repair model

The case study did four valuable things:

- it heard the two slips correctly and named them as **performance-level**
  errors, not lyric errors;
- it proposed the two plausible causes — rhyme gravity for `عَلِيم`, plosive
  attack for `بِأَنَّ`;
- it framed the real aesthetic choice: keep the “happy accident” as a document
  of spontaneity, or repair it;
- it located the song’s value in the exact take — arrangement, voice, mix.

Where it misled us:

- **“Audio inpainting” cannot choose a phoneme.** Generic inpainting fills a
  gap plausibly; it does not make the singer say `ف` instead of `ب`. The hard
  part was never finding the hole; it was making the model produce the right
  consonant inside the existing performance.
- **It treated words as the unit.** The final `ه` is not a word ending; it is a
  ~5.5 s G4 melisma. A lexical word boundary is not necessarily a musical
  boundary.
- **It treated the errors as isolated.** The first one is a word inside a
  phrase; the second is the first word of a phrase whose last note is held for
  seconds. The edit unit has to come from the performance, not the text.
- **It proposed a binary: keep or repair.** Repair turns the artifact into a
  conservation job: keep the original wherever it is already right, and replace
  only what is wrong. That reframing is what eventually worked.

**Lesson 1:** a listening-based case study is an excellent hypothesis
generator, but not an edit plan. It must be followed by exact timing, pitch and
stem analysis.

---

## 2. The Claude chat: the right constitution, the wrong environment

Claude’s chat was useful because it imposed discipline:

- freeze seed, style, LoRA, sampler settings, GPU;
- never overwrite the original;
- prove determinism before changing anything;
- sweep seeds, keep best-of-N;
- validate by listening, not just by a metric;
- fall back to a local splice if regeneration changes too much;
- warn that the NAR stage is globally coupled.

The last warning was the central technical fact of the project. Changing a few
semantic tokens changes the audio everywhere at the sample level. That is why
the deliverable is a **comp**, not a new render.

Where the chat was wrong:

- **It assumed a cover/regeneration problem.** The user wanted a repair, not a
  new version. The value was in the exact take.
- **It assumed the Python `yue2` stack, ABC score, `cot=melody/full`.** The
  actual runtime was audio.cpp / `audiocpp_cli`, `cot=off`, no ABC, no repaint.
- **It assumed the binary could take a semantic prefix.** The shipped binary
  silently ignored it; we had to build a prefix-capable binary.
- **It assumed a full-song seed sweep would preserve the song.** Without a
  score, a new seed is a new take. Targeted AR re-sing from a token prefix was
  the only way to keep context.
- **It assumed ASR/CTC would arbitrate.** CTC is unreliable at single-consonant
  resolution; the ear, plus pitch and duration, was decisive.
- **It assumed the error had to remain in the conditioning.** The key move was
  to cut the prefix *before* the bad word, so the error is absent from the
  conditioning and the model must sing it from the lyric.

**Lesson 2:** use the prompt as a set of hypotheses, not a specification.
Verify every environmental assumption before generating. The most reusable part
of Claude’s contribution was the **experimental constitution**, not the proposed
method.

---

## 3. The initial prompt: invariants survive, specifics do not

The prompt’s constraints were right and stayed right:

- same seed/style/LoRA/GPU;
- no overwrite;
- determinism gates;
- minimal perturbation;
- seed sweep and listening;
- local comp as a fallback;
- honest reporting of failure.

Its specifics were wrong in instructive ways:

- error 2 was not “around frame 5100”; it was **5056–5114**, and 5100 cuts
  inside the word;
- “fix error 2 first, only ~300 frames follow” undersold the problem: the tail
  is 341 frames, but the **musical** tail — the held `ه` — runs for seconds;
- “splice the same length” did not transfer the consonant; the donor route
  failed 0/4;
- “stem-level repair as a last resort” became the **delivery mechanism**;
- batch mode had quirks (must omit `--lyrics` / `--request-option`) that no
  environment-blind prompt could know.

**Lesson 3:** the durable part of a task prompt is the **invariants and the
evaluation discipline**. The proposed method is disposable. Exact frame and
unit discovery must happen before generation, not inside it.

---

## 4. The iteration: each step changed the hypothesis, not just a parameter

The path was:

1. **13 donor splices** — same singer, same take, length-preserving. **0/4.**
   Donor tokens/audio did not carry the missing consonant.
2. **Comp bug** — the graft replaced only changed frames, cutting back to the
   original inside the word. Fixed by replacing whole word ranges.
3. **AR re-sing** — force the prefix before the word, let the model sing it
   from the real lyric. Word 1 accepted (`e1_ar_s03`).
4. **Word 2 tail sweep** — 16 seeds; `s08` and `s13` both 5/5; `s08` chosen for
   rhythmic alignment.
5. **v1 delivered** — two bounded edits, bit-identical elsewhere. The ear heard
   a join in S2: the comp ended at 204.775, inside `الله`.
6. **Phrase comp** — replace `فَإِنَّ اللهَ يَنْزِعُهُ` as a unit; `s13` won the
   envelope score; 16 new tails rendered. Still a join.
7. **Melisma diagnosis** — the final `ه` is a **G4 ≈ 391 Hz hold from ~207.7 to
   ~213.2 s (≈5.5 s)**, not a word ending. The phrase comps ended at 207.90,
   **160 ms into the note**. Also, `s13` ends the phrase on **D4 ≈ 295 Hz**, not
   G4, so no cut point could fix an `s13` phrase comp.
8. **Minimal word comp** — replace only `فَإِنَّ` (202.21–204.54), keep the
   original `اللهَ يَنْزِعُهُ` and the entire melisma. Candidate `41` accepted.

Lessons from the iteration:

1. **The ear is the oracle; metrics are filters.** Envelope correlation ranked
   `s13` first even though its final note was the wrong pitch.
2. **Change the hypothesis, not just the parameters.** More seeds, longer
   fades and shifted takes could not fix a wrong unit or a wrong note.
3. **The unit of edit is the key variable.** Word, phrase, sustained note,
   section — each has different failure modes. The winning unit was smaller
   than the phrase.
4. **Keep what is already correct.** The original `اللهَ يَنْزِعُهُ` was right;
   replacing it was the source of the second `ه`, not the cure.
5. **Joins belong at performance boundaries, not lexical timings.** A word
   boundary can be mid-note; a note boundary can be mid-word.
6. **Bit-identity outside the comp is the right guarantee.** Do not claim more.
   The final differs only in 156.9964–158.8546 and 202.2105–204.5395.
7. **Negative results are assets.** The closed donor route and the invalid
   phrase comps prevented repeated waste.
8. **Seed sweeps are cheap; model load is the cost.** Render many tails, but
   choose the evaluation unit carefully.
9. **9.5–9.7/10 is a valid stop.** A 10/10 may require replacing more of the
   performance, which is exactly what the project was trying to preserve.

---

## 5. `WORKFLOW_VS_SUNO.md`: right control model, wrong unit

That note got the big comparison right:

- Suno cover = global audio conditioning with a fidelity/freedom dial;
- token surgery = bounded re-sing + local comp;
- the error is in the conditioning in a cover, but absent from the prefix in
  our method;
- keep the original instrumental by comping the vocal stem only;
- separate “what is regenerated” from “what is delivered.”

But it encoded the same wrong assumption that caused the last bug:

- it called 202.26–207.74 the phrase and 207.90 “after the phrase”; in fact the
  final `ه` runs to ~213.2;
- it called `s13` the phrase winner on envelope correlation without noting that
  `s13` ends on D4 and is invalid for a full-phrase replacement;
- it mapped “regenerate the verse” to “phrase-level re-sing,” but the accepted
  fix was **word-level `فَإِنَّ` only**, because the rest of the phrase was
  already correct.

**Lesson 5:** even a good conceptual document can carry a bad timing
assumption. When the unit changes, revise the document. The Suno Studio analogy
is closest in spirit, but our best edit was **smaller and stricter** than a
section regeneration. “Influence” maps to the prefix boundary; the more
important control is **what you leave untouched**.

---

## 6. The current milestone: surgical conservation, not perfect regeneration

Where we were:

- a happy-accident take with two wrong words;
- a plan to “regenerate as close as possible”;
- a full-song, global mindset inherited from the cover workflow.

Where we are:

- the original waveform, unchanged outside two tiny spans;
- both words corrected by AR re-sing;
- the original final `ه` melisma preserved sample-for-sample;
- a verified, reproducible delivery with hashes, edge steps and bit-identity;
- a 9.5–9.7/10 result by the only judge that matters.

The remaining glitch is worth one focused pass, but it should be treated as a
**join/timbre problem at 204.54 s**, not as a reason to reopen the melisma or
the whole phrase. The melisma is now the one part we know is right.

The larger lesson is aesthetic:

> A happy accident is fragile. The best edit is the one you cannot hear, and
> the best version may be the one where you replace the least.

The method is reusable:

1. Prove determinism and freeze the baseline.
2. Find the exact word **and its complete musical unit**, including melisma,
   with stems and pitch — not text timing alone.
3. Cut the conditioning before the error.
4. Re-sing the smallest unit that contains the error.
5. Comp the vocal stem only; keep the original instrumental.
6. Choose joins at real performance boundaries; never inside a sustained vowel.
7. Evaluate with ear + pitch + duration + envelope; never envelope alone.
8. Verify bit-identity outside the edit and measure the seam.
9. Review with the full track or a complete section — never a partial word.
10. Stop at good enough when the alternative destroys the take.

---

## 7. Quick reference

| question | answer |
|---|---|
| What was the winning method? | AR re-sing of the smallest wrong unit + vocal-stem comp into the original |
| What was the winning unit for S2? | `فَإِنَّ` only, 202.21–204.54 s |
| What did we leave untouched? | original `اللهَ يَنْزِعُهُ`, including the ~5.5 s final `ه` |
| Why did the phrase comp fail? | cut 160 ms into the melisma; `s13` ended on D4, not G4 |
| What is the final? | `FINAL_e1_ar_s03_s13_41.wav`, sha256 `9b8fdb21…` |
| What is the guarantee? | bit-identical outside 156.9964–158.8546 and 202.2105–204.5395 |
| What is the rating? | 9.5–9.7/10 (user), one join glitch open to investigation |
| What would we do differently? | measure the musical unit first; keep the original wherever it is already correct; don’t assume phrase > word |
