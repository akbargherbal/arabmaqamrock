# Audit — case 001 plan vs the field guide

Compared against `docs/guides/fixing_ai_music_mispronunciations.md` (v1.1) and
the runbook (v0.1), after the formant correction. Verdict first, then the
receipts.

## Verdict

The plan follows the guide's method. My "isn't this impractical?" answer is
**not a departure** — it is the guide's own decision tree (§1.1, §3.1): if the
take is not special, generate a new take; repair only a take worth preserving.
What I added is a quantification of that trade-off, not a different rule.

The audit did find **two real violations in my plan**, both now fixed:

1. **Unit B ended at 128.05 s — inside the `هَا` note/vowel.** Guide §5.2 says
   never end a comp inside a sustained vowel or melisma: either include the whole
   note, or keep the original note and end at its start. 128.05 is neither. My
   first fix, B = 128.13 (the word boundary), was **still mid-note**: the 465 Hz
   note continues through `إِلَيْنَا` and descends to ≈129.15. The user's
   continuity point caught this. Final resolution: **B is removed**; the plan is
   a **wide-first ladder**: **L1 = 126.60–129.18** (whole phrase, first),
   **L2 = 126.60–127.72** (word, keeps the note), **L3 = 127.18–127.65**
   (syllable, the floor). This inverts the guide's default order on purpose: the
   user's objective is ease/speed, and the wide route has the cleanest joins.
   The ladder is the test of whether "replace less" is a law or a fallback.
2. **I asked for a verdict on partial-word clips.** Rule 10 and §8 forbid that:
   review the full track or a complete section ending at a real boundary. Fixed:
   the `هَا` is judged on `05_*_line_123.00_129.20` (or the full track); the 1 s
   clips are only for locating the edit.

A third, smaller error: I called the 370 Hz note the "word-final" note. The
370 Hz note is `دُو`; the word-final `هَا` is 415→465 Hz. Fixed in the record
and card.

## Where the plan follows the guide

| guide | what the plan does |
|---|---|
| §0.1 / §4.1 preserve, hash, prove determinism | take hashed `3981465c…`; original frozen; re-derive + bit-identity gate before any edit |
| §0.2 repair, don't re-render | local AR re-sing + vocal-stem comp; no new song |
| §0.3 replace less | unit A keeps the correct `هَا`; the edit is 1.12 s of vocal |
| §0.4 / §2.2 unit is musical, not lexical | both aligners were overridden by f0 + formants; the unit is sub-word |
| §0.5 cut conditioning before the error | prefix 3169 (126.76 s), 0.45 s before the geminate at 127.21 |
| §0.6 keep what is correct | `هَا` and `إِلَيْنَا` kept in A; only `فَأَدُّو` replaced |
| §0.7 / §6.2 joins at performance boundaries | 126.60 = quietest gap point; 127.72 = unvoiced release before `هَا` |
| §0.8 / §7.1 ear is the oracle | four human gates; scores are filters |
| §0.9 / §6.5 bit-identity outside the edit | outside-diff = 0 on the 48 kHz int16 deliverable |
| §0.10 / §8 review complete audio | final gate is full track/section; **intermediate ask corrected** |
| §4.2 cut the conditioning before the error | prefix ends before the word; the bad `دّ` is not in the condition |
| §4.3 generate a tail, not a song | 61 generated frames (2.4 s), not 5938 |
| §4.4 sweep seeds | 16, `810750224 + 0..15` |
| §4.5 / §7.2 select on the unit, metrics as filters | closure duration, f0, duration, hā onset, edges; CTC only as a presence filter |
| §5.1 smallest unit with clean boundaries | A is the smallest unit containing the error and ending at a boundary |
| §5.2 melisma rule | A ends at the **start** of the correct continuous note (`هَا` + `إِلَيْنَا`) — the guide's second option; P ends in the breath after it |
| §5.3 keep what is correct | yes; P is the last resort precisely because it replaces `إِلَيْنَا` |
| §6.1 vocal stem only | comp the Demucs vocal; instrumental sample-for-sample |
| §6.3 fades / level | 30 ms in / 40 ms out; level probe |
| §6.4 timing | measure hā onset Δ, shift before comp; no time-stretch |
| §7.3 stop at good enough | explicit stop rule; keeping the original is a valid verdict |
| §9 manifest / reproduce | MANIFEST, hashes, changed spans, reproduce script |
| §10 failure modes | double consonant / clipped `دُو` / mid-note cut are the named risks |
| §11 local token models | NAR global coupling → local comp mandatory; determinism first |

## Where the plan adds to the guide (not contradictions)

1. **No exported token stream → re-derive + prove bit-identity.**
   The guide §4.1 assumes the tokens exist. The runbook Phase 1 fail branch says
   "no token stream → prefix route unavailable; choose donor or section
   re-render". This case adds a third route: re-derive deterministically with
   the same seed/prompts/runtime, then prove the baseline WAV is bit-identical
   before surgery. The reference run proves this is possible in principle; our
   gate proves it for this take. **This is a protocol change and needs the
   gate's evidence before it is accepted.** If the gate fails, the runbook's
   donor/section branch stands.
2. **Gemination is a defect class the guide lacks.**
   §1.2 has "missing/extra syllable / swallowed consonant", but not consonant
   *length*. A shaddah is a duration defect: the phone identity is right, the
   closure is short. That matters for evaluation — §7.2's CTC row explicitly
   misses single consonants, and a geminate is invisible to CTC. The plan scores
   **closure duration** (80–160 ms vs the original's ≈55 ms), with f0 and timing
   as filters. Add a row to §1.2 and a metric to §7.2.
3. **Formants for word-end detection.**
   §2.4 lists f0, duration, envelope, spectrogram. LPC formants (F1/F2) are what
   caught the aligner error here: the char-level CTC put `هَا` at 127.47–127.61,
   but that region was still /u/ (F1≈420). The real `هَا` is /a/ (F1≈835) at
   127.76. Add formants to §2.4 as the tool for vowel boundaries.
4. **Quantified break-even.**
   §1.1/§3.1 are qualitative ("a new take may be cheaper"). The plan turns it
   into a cost table: regenerate ≈7 min vs repair ≈30 min today / ≈15 min after
   the plumbing. That is a decision aid, not a new rule.
5. **Repair-readiness at generation time.**
   §1.3 lists prevention (proofread, respell, generate several takes, keep the
   seed). It does not say **keep the token stream**. For a token model, exporting
   the semantic tokens at generation time is zero-cost and removes the 9.5 min
   re-derive + bit-check from every future repair. This is the single biggest
   workflow finding of the case.

## Where the guide is incomplete (documentation gaps)

- **Comp wider than generation.** The reference run's comp starts at 156.995 s
  while the prefix/generation starts at 157.32 s. The lead is candidate
  re-synthesis of the prefix tokens, not original audio, and must be auditioned.
  The runbook says this; the guide §4.3/§6.2 does not. Add it.
- **A note can span words, so the lexical word is often not a valid end.** §5.1
  says "a note can span several words", but §5.2's example is a final *letter*
  held for seconds. This case is the other shape: `هَا` and `إِلَيْنَا` are two
  words on one continuous note. The rule applies, but the consequence is that
  there is **no cut between the words** — the unit is either the note's start
  (keep the note) or the end of the note (replace it). Add this shape to §5.2.
- **No-token takes.** The guide assumes the token stream exists; the runbook's
  fail branch is donor/section. Add the re-derive branch (conditional on the
  bit-identity gate) so the first response is not "give up on the prefix route".

## The "impractical" question, in the guide's terms

The guide does **not** say "always repair". §1.1 gives three legitimate outcomes
(keep, repair, regenerate) and §3.1 asks "Is the take special?" first. If no,
"generate a new take; do not spend time on surgery". So:

- For a **disposable practice take**, fixing one letter is not worth 30 minutes.
  Regenerate or keep. This is the guide's answer, not a contradiction of it.
- For a **take you cannot re-roll**, the 1 s patch is the cheapest way to keep
  the performance. The guide's §3.2 rates local AR re-sing + comp as high
  fidelity / high control / medium cost; the reference run is the evidence.
- The error must also **break meaning or immersion** (§1.1). A collapsed shaddah
  changes `فَأَدُّوهَا` into something that is not the word, so it passes that
  test — but that is a judgment for the ear, not the agent.

The honest conclusion: the *repair* is practical only for precious takes; the
*workflow* is practical if it makes the marginal repair cheap (token export,
pinned prefix binary, alignment command, unit helper) and makes the
keep/regenerate decision fast. This case is testing the second claim, not the
first.

## Proposed guide/runbook changes after this case

Only after the session, with evidence:

1. Runbook Phase 1: add "no exported tokens → re-derive + bit-check" as a
   branch, with the pass/fail gate.
2. Runbook Phase 6: replace the generic score table with defect-class scoring
   (gemination → closure; phoneme → CTC; note → f0; timing → onset lag).
3. Guide §1.2: add a gemination/shaddah row.
4. Guide §2.4: add LPC formants for vowel/word boundaries.
5. Guide §5.1/§5.2: state the sub-word "keep the correct final note" case
   explicitly, so §14's whole-word examples are not read as a rule.
6. Guide §4.3/§6.2: document the comp-wider-than-generation lead.
7. Repo: export semantic tokens by default; pin the prefix-capable binary.
