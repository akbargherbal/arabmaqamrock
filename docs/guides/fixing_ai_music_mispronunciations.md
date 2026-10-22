# Fixing Mispronunciations in AI Music

## A preservation-first field guide

> **Core principle:** a mispronunciation is a defect inside a take you want to
> keep. Do not regenerate the song. Replace the smallest musical unit that
> contains the defect, and leave everything else untouched.

This guide is for the recurring case: generative music produces a gem — the
arrangement, melody, voice and mix are right — but one or two words are sung
wrong. The goal is to repair those words without losing the happy accident.

It applies to hosted systems (Suno-style covers and section regeneration) and
to local models (YuE / audio.cpp and similar token-based systems). The controls
differ; the strategy does not.

**Version:** 1.1 — 2026-10-20 (adds the reproducible reference run in §14).

**Operational companion:** [Repair Session Runbook](repair_session_runbook.md)
— the step-by-step session procedure, defect card and repair record.

**Contents**

0. [The ten rules](#0-the-ten-rules)
1. [Decide what kind of defect you have](#1-decide-what-kind-of-defect-you-have)
2. [Find the defect precisely](#2-find-the-defect-precisely)
3. [Choose the repair route](#3-choose-the-repair-route)
4. [The core method: re-sing the smallest unit](#4-the-core-method-re-sing-the-smallest-unit)
5. [Choose the unit](#5-choose-the-unit)
6. [Build the comp](#6-build-the-comp)
7. [Evaluate](#7-evaluate)
8. [Review protocol](#8-review-protocol)
9. [Delivery and documentation](#9-delivery-and-documentation)
10. [Failure modes and fixes](#10-failure-modes-and-fixes)
11. [Model-specific notes](#11-model-specific-notes)
12. [One-page checklist](#12-one-page-checklist)
13. [Templates](#13-templates)
14. [Reference run: Baghdad Moon final fix](#14-reference-run-baghdad-moon-final-fix)
15. [Worked example](#appendix-worked-example-baghdad-moon)
16. [Glossary](#glossary)

---

## 0. The ten rules

1. **Preserve first.** Never overwrite the original. Hash it and keep it.
2. **Repair, don’t re-render.** A new full song is a different performance, not
   a fix.
3. **Replace less, not better.** The winning edit is usually smaller than you
   think.
4. **The unit is musical, not lexical.** A word can end in a multi-second
   melisma; a note can span several words.
5. **Cut the conditioning before the error.** If the model sees the bad
   pronunciation, it will tend to repeat it.
6. **Keep what is already correct.** If the surrounding phrase is right, do not
   replace it.
7. **Joins belong at performance boundaries** — breaths, note offsets, real
   gaps — never at a fixed word ± margin.
8. **The ear is the oracle.** Pitch, duration, envelope and ASR are filters,
   not verdicts.
9. **Bit-identity outside the edit is the guarantee.** Never claim more.
10. **Review complete audio.** Full track with timestamps, or a complete
    section ending at a real boundary. Never ask for a verdict on a partial
    word.

---

## 1. Decide what kind of defect you have

### 1.1 Repair, regenerate, or keep?

Not every mispronunciation should be fixed. Ask three questions:

| question | if yes | if no |
|---|---|---|
| Is the take special — would a new generation lose something you cannot recreate? | preserve it | a new take may be cheaper |
| Does the error break meaning or immersion? | repair | keep it, or lean into it |
| Is the error isolated — one word, one consonant, one note? | local repair | a section or a new take may be needed |

Three legitimate outcomes:

- **Keep it.** A slight accent or slur can be part of the charm. If it does not
  pull you out of the song, leaving it is an aesthetic choice, not a failure.
- **Repair it.** The take is worth preserving and the defect is local.
- **Regenerate it.** The take is not precious, or the defect is systemic
  (wrong language, wrong accent throughout, wrong melody). Local repair would be
  whack-a-mole.

Repair changes the artifact from a “document of spontaneity” into an “edited
master.” That is a real change; make it deliberately and label it honestly.

### 1.2 Classify the defect

“Mispronunciation” covers several different failures. The fix depends on which
one you have:

| defect | example | usual fix |
|---|---|---|
| Wrong consonant | `ف` sung as `ب`; `ه` sung as `م` | re-sing the word with the correct phoneme |
| Wrong vowel | `a` vs `e`, short vs long | re-sing; donor rarely works |
| Missing/extra syllable | swallowed consonant, added vowel | re-sing the syllable/word |
| Wrong word | model substitutes a rhyming word | re-sing from the lyric |
| Wrong pitch/melody | final note a fourth lower | choose a take with the right contour; re-sing |
| Wrong timing | word late/early | re-sing or time-shift; check the unit |
| Mix/timbre artifact | lisp, metallic sibilance, phasey vowel | stem/comp or different take, not a phoneme fix |

**Common model biases**

- **Rhyme gravity:** the preceding line’s rhyme pulls the target word toward
  the same ending (e.g., a final `-m` replacing a soft `-h`).
- **Plosive preference at climax:** a hard `b`/`p`/`t` may replace a softer
  fricative because it gives the singer a stronger attack.
- **Melisma swallows consonants:** the model prioritizes the run/vowel and the
  final consonant becomes a different sound or disappears.
- **Language/accent mismatch:** the model applies the dominant language’s
  phonology to a word from another language.
- **Repeated-word contamination:** a word heard earlier in the song is
  substituted in the same melodic position.
- **LoRA/style bias:** a style adapter may push toward a genre-typical vowel or
  consonant, especially at phrase endings.

These are hypotheses, not excuses. Confirm by listening and by comparing the
target with a known-correct occurrence in the same song or another take.

**Do not start generating until you know which category you are in.** A pitch
error cannot be fixed by a better consonant; a consonant error cannot be fixed
by a longer fade.

### 1.3 Prevention is cheaper than repair

Before you need this guide:

- proofread the lyric and the language/accent tags;
- if the model consistently misses a phoneme, try a phonetic respelling in the
  **generation prompt only** (keep the published lyric correct);
- generate several takes and choose on pronunciation, not only on vibe;
- do not cut the generation short — let melismas and final notes finish;
- keep the seed/settings of any take that is close; a good take is a reference,
  not a disposable draft.

---

## 2. Find the defect precisely

### 2.1 Listen to the whole track first

Listen once without stopping. Mark:

- the exact word and timestamp;
- what was sung vs what should have been sung;
- whether the error is a consonant, vowel, word, pitch or timing;
- what happens *after* the word — does the melody continue, hold, or repeat?

The last point is critical. The damage may not be at the word; it may be in the
note that follows it.

### 2.2 Text timing is not musical timing

Lyric timestamps and ASR word boundaries are useful starting points, but they
are not edit boundaries. A word’s final vowel or consonant can be held for
seconds. In a melismatic style, the last letter may carry the entire emotional
peak of the phrase.

Find the **complete musical unit**:

- start: the onset of the defective word (or a breath just before it);
- end: the end of the note or melisma that belongs to that word — not the end
  of the lexical token;
- include any ornament, run, vibrato tail, or release that the singer treats as
  part of the word.

If you cut at a dictionary word boundary, you may cut inside a note.

### 2.3 Isolate the vocal

Use source separation (Demucs or equivalent) to get the lead vocal. This lets
you:

- see where the voice actually starts and stops;
- measure pitch and level without the instruments;
- comp only the vocal later, keeping the original instrumental.

Caveats:

- separation is not perfect; bleed and artifacts exist;
- check the full mix as well; a stem can lie;
- use the same separation model for the original and the candidate when
  comparing.

### 2.4 Measure, don’t guess

For the target unit, measure:

- **pitch contour** (f0): median, range, vibrato, final note;
- **duration**: how long the note actually lasts;
- **envelope**: RMS over 10–20 ms windows, gaps, breaths, level;
- **spectrogram**: consonant attacks, sibilance, artifacts;
- **alignment**: lag between candidate and original.

A useful sanity check: if the candidate’s final note is a different pitch class
from the original, no cut point will make it match. Fix the take, not the fade.

### 2.5 Write the repair brief

Before generating anything, write down:

```
Track:
Original file + hash:
Model / LoRA / seed / sampler / GPU:
Target word:
Heard as:
Should be:
Musical unit (start–end):
What must not change:
Delivery format:
```

This brief prevents the most expensive error: solving the wrong problem.

---

## 3. Choose the repair route

### 3.1 Decision tree

```
Is the take special?
├─ no  → generate a new take / cover; do not spend time on surgery
└─ yes → does the error break meaning or immersion?
   ├─ no  → keep it (or use an alternate mix)
   └─ yes → can you isolate the vocal?
      ├─ no  → try section regeneration or stem separation first
      └─ yes → is the surrounding performance correct?
         ├─ yes → re-sing the smallest unit (usually one word)
         └─ no  → re-sing the phrase or section that is actually wrong
```

### 3.2 Route comparison

| route | fidelity to the take | control | cost | main risk |
|---|---|---|---|---|
| Keep it | 100% | none | none | defect remains |
| Donor splice from another take | high if same singer | medium | low | donor carries wrong phoneme/prosody |
| Audio inpainting | medium | low | medium | fills plausibly, cannot choose a phoneme |
| Section regeneration (hosted Studio) | medium | medium | low | new section, seam, no bit-identity |
| Cover with audio influence | low–medium | one global dial | low | repeats the error at high influence; drifts at low |
| Local AR re-sing + comp | **high** | **high** | medium | NAR non-locality; needs a comp |
| New full generation | none | high | low | loses the happy accident |

### 3.3 Why donor splices usually fail

Taking the same word from another take of the same song is tempting: same
singer, same language, same style. It often fails because:

- the donor may have the same mispronunciation (the model’s bias is shared);
- the phoneme may be correct but the **prosody** — pitch, timing, vowel color —
  belongs to a different context;
- splicing audio at word boundaries creates a new join, and the join is often
  more audible than the original error;
- donor tokens do not automatically transfer the consonant; token-level
  splicing can preserve the wrong phoneme.

Use a donor only if you can verify **phoneme + pitch + duration + level** in the
new context. If not, re-sing.

### 3.4 Why inpainting is not a phoneme tool

Audio inpainting is good at filling a gap with plausible audio. It is not good
at making a singer produce a specific consonant. It may generate a generic
vowel or a smear that fits the gap but does not say the word. Use it for repair
of a click, drop-out or instrumental gap — not as the primary fix for a
mispronunciation.

---

## 4. The core method: re-sing the smallest unit

This is the highest-control route for token-based local models. It also
describes the mental model you should use when working with any system that
lets you condition on part of a performance.

### 4.1 Freeze and prove determinism

Before changing anything:

- freeze model, LoRA, seed, sampler, guidance, GPU and runtime;
- reproduce the original render exactly — semantic tokens and audio hash;
- verify that a second run with the same inputs gives the same output.

Without a deterministic baseline, every A/B is noise. If you cannot reproduce
the original, you cannot claim that a difference came from your edit.

### 4.2 Cut the conditioning before the error

The model should see the real lyric and the correct prior performance, but it
should **not** see the bad pronunciation in its conditioning.

- In a token model: force the semantic-token prefix up to the start of the
  defective unit, then let the model generate the unit from the lyric.
- In an audio-influence system: the whole source audio is the conditioning, so
  high influence tends to repeat the error. Lowering influence can escape it,
  but the arrangement drifts. The token-prefix method is cleaner because the
  error is simply absent from the condition.

This is the single most important mechanical idea in the guide:

> **Keep 100% of the context before the error; keep 0% of the error itself.**

### 4.3 Generate a tail, not a song

You do not need a new full song. Generate from the prefix through the end of the
unit (and a little beyond), then discard everything after the comp region. This
is cheaper, preserves context, and makes the edit possible.

### 4.4 Sweep seeds

Generate multiple takes. The model’s performance varies enormously between
seeds. Score them on the **musical unit**, not the whole song.

The model load is the fixed cost; extra takes are cheap. A sweep of 8–32 tails
is usually enough to find a usable phoneme and prosody.

### 4.5 Select on the unit

Do not select on “sounds close overall.” Select on:

- the correct phoneme (ear);
- the correct pitch contour and final note (f0);
- the correct duration and timing (envelope/DTW);
- no new artifact at the joins.

Envelope correlation alone is dangerous: it measures dynamics, not melody. A
take can have a beautiful envelope and the wrong final note.

---

## 5. Choose the unit

### 5.1 Word, phrase, note, or section?

| unit | use when | risk |
|---|---|---|
| Single word | the error is isolated and the surrounding phrase is correct | a join in a continuous phrase |
| Phrase | the model re-sings the phrase as a unit and the joins need context | replaces correct material; may drift |
| Sustained note / melisma | the error is in the ornament or final vowel | easy to cut inside the note; hard to match |
| Section | the whole section is wrong, or no clean internal boundary exists | replaces the most; highest chance of drift |

**Default:** the smallest unit that contains the error and has clean
performance boundaries. Do not assume phrase > word. In the worked example
below, the winning edit was *smaller* than the phrase.

### 5.2 The melisma rule

**Never end a comp inside a sustained vowel or melisma.**

If the final letter is held for seconds, that note is part of the word. Either:

- include the entire note in the replacement, or
- keep the original note and end the comp at its **start** (the boundary
  between the corrected word and the already-correct held note).

If the candidate’s note is shorter than the original, keeping the original is
usually better than time-stretching. Stretch only as a last resort, and check
for artifacts.

Both can work. If the final consonant sits at the start of the held note,
include the consonant attack and hand off during the sustain — do not cut before
the consonant. What cannot work is cutting 100–200 ms into the note and handing
the rest back to the original: the ear hears a truncated note followed by a
second attack or a pitch change.

### 5.3 Keep what is already correct

If the original already sings `اللهَ يَنْزِعُهُ` correctly, do not replace it
just because it is inside the same phrase as the bad word. Replace the bad word
and keep the good phrase.

This is the difference between “repair” and “re-render.” The original is not
the enemy; it is the reference.

---

## 6. Build the comp

### 6.1 Vocal stem only

If the goal is to keep the music, comp only the lead vocal:

- separate the original into stems;
- replace the vocal in the chosen region with the candidate’s vocal;
- keep the original instrumental sample-for-sample.

A full-mix comp replaces the arrangement too. In AI takes, the candidate’s
drums, bass and guitars often correlate poorly with the original and may be
louder or differently timed. That is not a vocal fix; it is a remix.

Caveat: stem separation can introduce artifacts. Check the full mix after
comping; if the vocal stem is thin or phasey, try a different separation model
or a full-mix comp as a last resort.

### 6.2 Boundaries

Choose boundaries at:

- a breath or voiceless gap in the lead vocal;
- a real note offset or release;
- the start of the next word, if the previous word is correct.

Avoid:

- fixed word ± 0.3 s;
- dictionary boundaries that fall mid-note;
- the middle of a sustained vowel;
- a boundary chosen only because the waveform is low-energy (the music may be
  sustaining underneath).

### 6.3 Fades and level

- Use a short cosine crossfade: ~30–80 ms for a word join, up to 120–200 ms for
  a phrase or a timbre mismatch.
- Match level at both edges with a short probe (20–50 ms) and a gentle dB ramp.
- Do not boost more than a few dB; boosting a quiet take also boosts noise.
- A fade removes clicks. It does not fix a wrong phoneme, a wrong pitch, or a
  level jump of several dB.

### 6.4 Timing

Measure the lag between candidate and original on the target unit. If the
candidate is late or early, shift it before comping. Do not shift blindly: a
global shift can misalign the start while fixing the end. Check both edges.

### 6.5 Verification

After building the comp, verify:

- the original file hash is unchanged;
- the final differs only inside the intended regions;
- outside those regions, the max absolute difference is **0**;
- edge level steps are small (ideally < 1 dB);
- no sample discontinuity or click;
- pitch continues across the join;
- the final note / melisma is intact;
- the music is unchanged (if vocal-only);
- mono compatibility / phase is acceptable.

Bit-identity is only meaningful at the same sample rate, channel layout and
format. If you resample or re-encode, you can no longer claim sample-for-sample
equality; document the conversion instead.

Keep the verification output. “Sounds fine” is not a QC record.

---

## 7. Evaluate

### 7.1 Ear first

Listen to the **full track** or a **complete section** that runs to a real
boundary or the end of the track. Do not judge a partial word. The defect may
be fixed at the target and regress immediately after it.

Ask focused questions:

- Is the target phoneme correct?
- Is the melody/pitch correct?
- Is the timing natural?
- Is the join audible?
- Does the performance regress after the join?
- Is the music still the same?
- Does it sound like the same singer and the same session?

### 7.2 Metrics as filters

| metric | what it catches | what it misses |
|---|---|---|
| f0 contour | wrong note, wrong octave, pitch jump | timbre, phoneme identity |
| duration / envelope | timing, level, drop-outs | pitch, consonant |
| DTW / correlation | rhythmic alignment | melody, phoneme |
| ASR / CTC | word identity | single consonants, accent |
| spectrogram | clicks, sibilance, artifacts | musical naturalness |
| edge RMS step | level jump at the join | timbre mismatch |

Use metrics to rank and diagnose; use the ear to decide.

### 7.3 Acceptance

Define “good enough” before listening:

- the word is intelligible and correct;
- the melody and timing are right;
- no new artifact at the join;
- the music is intact;
- the performance still feels like the same take.

A **9.5/10** result is often the right stop. The last half-point may require
replacing more of the performance, which is exactly what you were trying to
preserve. Perfection is not the goal; a transparent repair is.

---

## 8. Review protocol

When asking someone else to judge:

**Send either**

1. the **full track** plus the target timestamps; or
2. a **complete section** that ends at a real boundary or the end of the track.

**Never send**

- a clip that ends inside a sustained vowel or melisma;
- a clip that ends in the middle of a word;
- a “word-only” excerpt that hides the note that follows.

A good review request:

```
Original: 00_ORIGINAL_full.wav
Candidate: 10_FINAL_full.wav
Target: 202.21–204.54, then let it run to 215.879
Question: is the consonant correct, is the join audible, and does the
melisma after 204.54 remain natural?
```

Do not ask “is this good?” without a target. Ask about the specific defect and
the specific risk.

---

## 9. Delivery and documentation

A repair is not delivered until it is documented and reproducible.

Minimum manifest:

```
original_sha256:
final_sha256:
duration / sample rate / channels:
changed_spans:
outside_max_abs_diff:
edge_level_steps:
stem_model:
model / LoRA / seed / sampler:
candidate_source:
comp_region:
fades:
what_is_bit_identical:
what_is_not_bit_identical:
```

Rules:

- never overwrite the original;
- keep the candidate renders and token/seed files;
- keep the script or command that built the comp;
- state clearly that the audio is bit-identical **outside** the comp, not
  inside it;
- keep an A/B pack with the original and final, using the same windows;
- version the delivery (`v1`, `v2`, …) and say what changed.

A complete, reproducible example of this manifest and directory layout is the
reference run in §14.

---

## 10. Failure modes and fixes

| symptom | likely cause | fix |
|---|---|---|
| Two consonants / “double word” | comp cut mid-word; original resumes inside the word | move the boundary to the word/note edge; keep the correct original |
| A second vowel or second `ه` | comp cut inside a melisma; candidate note truncated | include the whole note, or keep the original note and cut at its start |
| Pitch jump at the join | candidate has the wrong final note | choose a take with the right f0 contour; do not fix with fades |
| Level jump | candidate is louder/quieter | level probe + dB ramp; check both edges |
| Click / tick | sample discontinuity | short cosine fade; verify sample step |
| Thin, phasey or robotic vocal | stem separation artifact or full-mix comp | try another stem model; comp vocal only |
| Music changed | full-mix comp | vocal-stem comp; keep original instrumental |
| Timing drift | candidate late/early | measure lag; shift; check both ends |
| ASR says correct, ear says wrong | CTC is unreliable at phoneme level | trust the ear; inspect spectrogram |
| Donor sounds wrong in context | correct phoneme, wrong prosody/timbre | re-sing in context instead of splicing |
| Regression after the edit | you reviewed a partial word | listen to the full section/track |
| Harsh sibilance | codec/stem artifact | different take or separation; avoid boosting highs |

---

## 11. Model-specific notes

### Hosted cover / section systems (Suno-style)

*Vendor internals vary; these are workflow-level observations, not claims about
any specific product’s architecture.*

- A cover with audio influence is a **global** control. High influence follows
  the source — including the error; low influence escapes the error but drifts.
- In the workflow this guide was derived from, influence around **60–85%** is
  the useful range; the exact point is track-dependent. Iterate, but expect a
  fidelity/freedom trade-off. There is no guarantee that the corrected phoneme
  survives at the influence that preserves the arrangement.
- Section regeneration (Studio-style) is closer to a local repair, but it still
  replaces a section. Choose section boundaries at real musical boundaries, not
  at a fixed number of bars, and check the end of any held note.
- If the system does not expose stems or tokens, you can still separate the
  output with Demucs and comp the vocal into the original. The result is only as
  good as the separation and the match between takes.

**If you only have a hosted system:**

1. Try section regeneration at a real musical boundary.
2. If that is unavailable, generate several covers at different influence
   values; keep the one with the correct phoneme and the closest prosody.
3. Separate the chosen output and comp its vocal into the original, keeping the
   original instrumental.
4. If the vocal timbre does not match well enough, choose between a new full
   cover and keeping the error. Do not pretend a full cover is a surgical fix.

### Local token models (YuE / audio.cpp and similar)

- The song is represented as semantic tokens; you can force an exact prefix.
- Cut the prefix **before** the error; let the AR stage generate the unit from
  the lyric.
- The NAR stage is globally coupled: the new render differs everywhere at the
  sample level. A local comp is mandatory if you want bit-identity outside the
  edit.
- Batch renders are cheap relative to model load; sweep seeds.
- Verify semantic and audio determinism before trusting any comparison.

### Any system

- The same principles apply: isolate, choose the smallest unit, preserve what
  is correct, join at performance boundaries, verify, review complete audio.

---

## 12. One-page checklist

```
[ ] Save and hash the original. Never overwrite it.
[ ] Listen to the full track. Mark the defect and what follows it.
[ ] Classify: consonant, vowel, word, pitch, timing, or mix.
[ ] Separate the vocal. Find the complete musical unit, including melisma.
[ ] Measure f0, duration, envelope, and the boundary.
[ ] Freeze model/seed/settings; prove determinism.
[ ] Choose the route: keep / donor / section regen / AR re-sing + comp.
[ ] Cut the conditioning before the error.
[ ] Generate multiple takes; render through the end of the unit.
[ ] Select by ear + pitch + duration, not envelope alone.
[ ] Comp the vocal only; keep the original instrumental.
[ ] Put joins at breaths/note boundaries; fade and level-match.
[ ] Verify bit-identity outside the edit; measure the seam.
[ ] Review the full track or a complete section.
[ ] Deliver with hashes, changed spans, and a clear bit-identity claim.
[ ] Stop at good enough if more editing would cost the take.
```

---

## 13. Templates

### Repair brief

```
Track:
Original file / sha256:
Model / LoRA / seed / sampler / GPU:
Target word:
Heard as:
Should be:
Musical unit (start–end):
What must not change:
Delivery format:
```

### Review request

```
Original: <full track or complete section>
Candidate: <same window>
Target: <timestamps; tell them to continue to the end of the note>
Questions:
  1. Is the target phoneme correct?
  2. Is the melody/pitch correct?
  3. Is the join audible?
  4. Does the performance regress after the join?
  5. Is the music unchanged?
```

### QC manifest

```
original_sha256:
final_sha256:
duration / sample rate:
changed_spans:
outside_max_abs_diff:
edge_level_steps:
model / seed / sampler:
candidate:
comp_region / fades:
bit-identical outside:
not bit-identical inside:
```

---

## 14. Reference run: Baghdad Moon final fix

A complete, self-contained run that applies this guide end to end. It is the
canonical example to copy when you need to fix a new song.

```
gs://akbar-december-2024-backup/arabmaqamrock/runs/20261020_baghdad_moon_final_fix_v2/
```

Project docs:
`docs/happy_accidents/Baghdad_Moon/token_surgery/` (the narrative history,
measurements and lessons).

### What the run is

A deterministic **composite**, not a new generation:

```
inputs/ORIGINAL.wav
  + word 1 from inputs/e1_ar_s03.wav
  + word 2 from inputs/s13.wav     (فَإِنَّ only)
  + scripts/comp_region.py         (202.21–204.54 s, vocal stem)
  = output/FINAL_e1_ar_s03_s13_41.wav
```

Final hash: `9b8fdb21…`; original hash: `dbc00722…`; duration 215.879 s.
Changed spans: **156.9964–158.8546 s** and **202.2105–204.5395 s**; outside
max abs diff **0**; hold 207.5 s–end byte-identical to the original.

### Download and reproduce

```bash
gsutil -m cp -r \
  gs://akbar-december-2024-backup/arabmaqamrock/runs/20261020_baghdad_moon_final_fix_v2 .
cd 20261020_baghdad_moon_final_fix_v2
bash scripts/reproduce_final.sh
```

Expected last line:

```
PASS: final is byte-identical to the delivered v2 track.
```

The script checks the original hash, rebuilds the final with
`scripts/comp_region.py`, runs `scripts/verify_final.py`, and checks the final
hash. It writes `qc/comp_output.json` and `qc/verify_output.txt`.

Melisma analysis:

```bash
python3 scripts/analyze_melisma.py
# writes analysis/melisma.json
```

### Run layout

```
README.md                     overview and quick facts
METHOD.md                     lab notebook: decisions, failures, commands
PROVENANCE.md                 model, seeds, prefixes, stems, hashes
REVIEW.md                     full-track audition instructions
MANIFEST.json                 machine-readable manifest
CHECKSUMS.sha256              sha256 of every file (except itself)
inputs/
  ORIGINAL.wav                frozen original
  e1_ar_s03.wav               word-1 render
  s13.wav                     word-2 tail render
  request_e1_s03.json         exact word-1 request
  request_e2_s13.json         exact word-2 request
stems/
  original/vocals.wav         Demucs vocal stem, original
  s13/vocals.wav              Demucs vocal stem, s13
tokens/                       prefixes and the e1 full token export
scripts/                      comp, verify, reproduce, analyze, scoring
output/                       FINAL_e1_ar_s03_s13_41.wav + .sha256
analysis/                     melisma.json + melisma.md
qc/                           comp report, verify transcript, hashes
```

### How the method was applied

1. **Baseline.** Both determinism gates passed; original hash frozen. No edit
   was attempted until the baseline was exact.
2. **Word 1 (`عَلَيْهِ`, Verse 2).** AR re-sing from prefix 3933, max 3964,
   seed `1712905621` (`s03`); whole-word vocal comp at 156.995–158.855 s.
   Accepted by ear.
3. **Word 2 (`فَإِنَّ`, Outro).** Donor splices failed 0/4. The v1 word comp
   ended at 204.775 s, inside `الله`. The phrase comp ended at 207.90 s, inside
   the final `ه`.
4. **The measurement.** The original final `ه` is a **G4 ≈ 391 Hz hold from
   ~207.7 to ~213.2 s (≈5.5 s)**, release to ~215. The phrase candidate `s13`
   ends the phrase on **D4 ≈ 295 Hz** and holds only ~2.7 s. No cut point can
   fix a wrong final note.
5. **The decision.** Replace **only `فَإِنَّ`** at 202.21–204.54 s; keep the
   original `اللهَ يَنْزِعُهُ` and the entire melisma. Vocal stem only, no
   timing shift, 50 ms in / 80 ms out, gain ramp.
6. **QC.** Changed spans as above; outside diff 0; edge step at 204.54
   −0.36 dB; hold 207.5 s–end byte-identical.
7. **Review.** Full tracks only; S1 target 154.5–161.0 s; S2 target 200.0 s to
   the end. Never a partial word.

### Mapping the guide to the run

| guide step | artifact in the run |
|---|---|
| save/hash original | `inputs/ORIGINAL.wav`, `MANIFEST.json` |
| word 1 source | `inputs/e1_ar_s03.wav`, `inputs/request_e1_s03.json`, `tokens/tokens_prefix_e1_3933.json` |
| word 2 source | `inputs/s13.wav`, `inputs/request_e2_s13.json`, `tokens/tokens_prefix_e2_5056.json` |
| isolate vocal | `stems/original/vocals.wav`, `stems/s13/vocals.wav` |
| build comp | `scripts/comp_region.py`, `scripts/reproduce_final.sh` |
| verify | `scripts/verify_final.py`, `qc/verify_output.txt` |
| melisma measurement | `scripts/analyze_melisma.py`, `analysis/melisma.json` |
| manifest / hashes | `MANIFEST.json`, `CHECKSUMS.sha256` |
| review | `REVIEW.md`, `inputs/ORIGINAL.wav`, `output/FINAL_e1_ar_s03_s13_41.wav` |
| provenance | `PROVENANCE.md` |

### What to copy for a new repair

- the **layout**: `inputs/`, `stems/`, `scripts/`, `output/`, `qc/`, `analysis/`,
  `MANIFEST.json`, `CHECKSUMS.sha256`;
- the **manifest fields**: original/final hashes, changed spans, comp region,
  fades, edge steps, model/seed/prefix, what is and is not bit-identical;
- the **reproduce script**: one command that rebuilds the final and checks the
  expected hash;
- the **analysis script**: measure the final note before choosing the unit;
- the **review rule**: full track with timestamps, or a complete section ending
  at a real boundary / end of track.

### What not to infer

- This is **not** a rule that every fix is word-level. Word 1 and word 2 both
  happened to be word-level here; the rule is the **smallest correct unit**.
- This is **not** a rule that every melisma is 5.5 s. Measure your own.
- This is **not** a new generation. The final is a deterministic composite; it
  can be reconstructed exactly, but it cannot be regenerated as one model pass.
- The 9.5–9.7/10 result is a legitimate stop. The remaining glitch at 204.54 is
  a join/timbre question, not a reason to replace the melisma again.

---

## Appendix: worked example (Baghdad Moon)

A concrete case shows why the unit matters. The complete, self-contained run is
in §14.

- The take was a “happy accident”; the arrangement, voice and mix were right.
- Two words were wrong: `عَلَيْهِ` → `عَلِيم`, and `فَإِنَّ` → `بِأَنَّ`.
- The outro phrase `فَإِنَّ اللهَ يَنْزِعُهُ` was treated as one unit at first.
- Measurement showed the final `ه` is a **G4 ≈ 391 Hz hold from ~207.7 to
  ~213.2 s (≈5.5 s)**, not a word ending. The phrase comp ended at 207.90 s —
  160 ms inside the note — so it truncated the candidate and handed the rest
  back to the original: a second `ه`.
- The phrase-level winner `s13` ended on **D4 ≈ 295 Hz**, not G4; envelope
  correlation had hidden the wrong final note.
- The accepted fix replaced **only `فَإِنَّ`** (202.21–204.54 s), kept the
  original `اللهَ يَنْزِعُهُ` and its entire melisma, and used an 80 ms
  crossfade. The final differs from the original only in two spans; the hold is
  byte-identical. The user rated it **9.5–9.7/10**.

The lesson is not “always use a word” or “always use a phrase.” It is:

> **Use the smallest unit that contains the error and has clean performance
> boundaries. Keep everything the original already sings correctly.**

---

## Glossary

- **AR / NAR:** autoregressive and non-autoregressive stages of a token-based
  music model. AR generates semantic tokens; NAR renders audio and is globally
  coupled.
- **Semantic tokens:** discrete representation of the song’s content; a prefix
  can be forced to condition generation.
- **Prefix:** the token sequence before the generated unit. Cutting it before
  the error removes the error from the conditioning.
- **Comp:** a local audio splice; the original waveform with one region
  replaced.
- **Stem:** an isolated instrument or vocal track from source separation.
- **Melisma:** a sequence of notes sung on one syllable; can last seconds.
- **f0:** fundamental frequency; the perceived pitch.
- **DTW:** dynamic time warping; alignment between two time series.
- **Bit-identity:** sample-for-sample equality. Claim it only outside the comp.

---

*Canonical guide. If you remember only one line: replace less, keep the take.*
