# Fixing Mispronunciations in AI Music

## A preservation-first field guide

> **Core principle:** a mispronunciation is a defect inside a take you want to
> keep. Do not regenerate the song. Replace the smallest musical unit that
> contains the defect, and leave everything else untouched.

This guide is for the recurring case: generative music produces a gem — the
arrangement, melody, voice and mix are right — but one or two words are sung
wrong. The goal is to repair those words without losing the happy accident.

It applies to hosted systems (Suno-style covers and section regeneration) and to
local models (YuE / audio.cpp and similar token-based systems). The controls
differ; the strategy does not.

**Version:** **2.0 — 2026-11-15.** Rewritten around the first clean run:
[`cases/002_abu01_ajdad/RUN3.md`](../../cases/002_abu01_ajdad/RUN3.md) —
`مِلَّتِي` in the T4 CFG 1.5 take. That run delivered in **26 minutes of machine
time / 39 minutes wall**, with one GPU session, four seeds and no token
re-derivation.

**Operational companion:** [Repair Session Runbook](repair_session_runbook.md).

> **Baghdad Moon is not the reference run anymore.** It was the learning case:
> it took several sessions and hours, and much of that cost came from mistakes
> this guide now prevents. It is kept as a historical appendix (§17), not as the
> workflow to copy.

**Contents**

0. [The ten rules](#0-the-ten-rules)
1. [What changed from v1](#1-what-changed-from-v1)
2. [Decide what kind of defect you have](#2-decide-what-kind-of-defect-you-have)
3. [Foundation: make the take repairable](#3-foundation-make-the-take-repairable)
4. [Find the defect precisely](#4-find-the-defect-precisely)
5. [Choose the repair route](#5-choose-the-repair-route)
6. [Choose the unit](#6-choose-the-unit)
7. [Generate the candidates](#7-generate-the-candidates)
8. [Filter before the ear](#8-filter-before-the-ear)
9. [Build the comp](#9-build-the-comp)
10. [Verify](#10-verify)
11. [Evaluate and review](#11-evaluate-and-review)
12. [Deliver and document](#12-deliver-and-document)
13. [Failure modes and fixes](#13-failure-modes-and-fixes)
14. [Model-specific notes](#14-model-specific-notes)
15. [One-page checklist](#15-one-page-checklist)
16. [Templates](#16-templates)
17. [Reference run: case 002 / RUN3](#17-reference-run-case-002--run3)
18. [Historical case: Baghdad Moon](#18-historical-case-baghdad-moon)
19. [Glossary](#19-glossary)

---

## 0. The ten rules

1. **Preserve first.** Never overwrite the original. Hash it and keep it.
2. **Export semantic tokens at generation.** A WAV alone is not a repairable
   take. The token stream is the portable record of the performance.
3. **Repair, don’t re-render.** A new full song is a different performance, not
   a fix.
4. **Replace less, not better.** The winning edit is usually smaller than you
   think.
5. **The unit is musical, not lexical.** A word can end in a multi-second
   melisma; a note can span several words.
6. **The prefix locks the tokens, not the prefix audio.** NAR re-synthesis
   changes the prefix region at the sample level; comp only after the region you
   measured.
7. **Filter before the ear.** Generate a few candidates, reject the measurable
   failures, and audition 3–5 — not 16.
8. **Joins belong at performance boundaries.** A consonant onset is a valid
   join, but its f0/RMS step is not the steady-vowel test.
9. **Bit-identity outside the edit is the guarantee.** Never claim more.
10. **Review complete audio and stop at good enough.** Full track or a complete
    section ending at a real boundary. 9.5/10 is a valid stop.

---

## 1. What changed from v1

v1 was distilled from Baghdad Moon. It was honest about the failures, but it
made the failure path look like the method. v2 is distilled from the first run
that met the 30-minute goal.

| topic | v1 / Baghdad | v2 / RUN3 |
|---|---|---|
| foundation | re-derive tokens and prove a bit-identical baseline | **export tokens at generation**; G0 is count + duration + sha |
| gate | full re-render, cross-architecture bit-identity | 7-second token check; no re-derive |
| GPU runs | multiple sessions, retries | one session, one process, four seeds |
| seeds | 8–32 tails | 4 first, **16 ceiling** |
| unit | phrase-first experiments | whole word; measured on the stem |
| comp | phrase/word experiments, 50–80 ms fades | vocal-only diff, **15 ms ramps**, 27.46–28.98 s |
| selection | envelope correlation | ear + pitch + spectral centroid + click ratio |
| duration | hours over several sessions | **26 min machine / 39 min wall** |
| reference | Baghdad Moon | **RUN3 / case 002** |

The rest of this guide explains the v2 path. The Baghdad details are in §18,
clearly marked historical.

---

## 2. Decide what kind of defect you have

### 2.1 Repair, regenerate, or keep?

Not every mispronunciation should be fixed. Ask three questions:

| question | if yes | if no |
|---|---|---|
| Is the take special — would a new generation lose something you cannot recreate? | preserve it | a new take may be cheaper |
| Does the error break meaning or immersion? | repair | keep it, or lean into it |
| Is the error isolated — one word, one consonant, one note? | local repair | a section or a new take may be needed |

Three legitimate outcomes:

- **Keep it.** A slight accent or slur can be part of the charm.
- **Repair it.** The take is worth preserving and the defect is local.
- **Regenerate it.** The take is not precious, or the defect is systemic.

### 2.2 Classify the defect

| defect | example | usual fix |
|---|---|---|
| Wrong consonant | `ف` sung as `ب`; `ه` sung as `م`; `م` missing | re-sing the word with the correct phoneme |
| Wrong vowel | `a` vs `e`, short vs long | re-sing; donor rarely works |
| Missing/extra syllable | swallowed consonant, added vowel | re-sing the syllable/word |
| Wrong word | model substitutes a rhyming word | re-sing from the lyric |
| Wrong pitch/melody | final note a fourth lower | choose a take with the right contour |
| Wrong timing | word late/early | re-sing or time-shift; check the unit |
| Mix/timbre artifact | lisp, metallic sibilance, phasey vowel | stem/comp or a different take |

**Common model biases:** rhyme gravity, plosive preference at climax, melisma
swallowing consonants, language/accent mismatch, repeated-word contamination,
LoRA/style bias. These are hypotheses; confirm by ear and against a known-correct
occurrence in the same take.

### 2.3 Prevention is cheaper than repair

- proofread the lyric and the language/accent tags;
- export semantic tokens for any take that might be kept;
- record seed, sampler, LoRA, model, binary and GPU in the sidecar;
- generate several takes and choose on pronunciation, not only vibe;
- do not cut the generation short — let melismas and final notes finish.

---

## 3. Foundation: make the take repairable

This is the layer that decides whether the repair takes 30 minutes or a session.
It must be decided at generation time.

### 3.1 Export the tokens

For a token-based local model, generate with:

```
export_semantic=true
stop_after=audio
```

and store `semantic.json` beside the WAV, with its sha256 and frame count. The
token stream is the actual recording of the performance. The WAV alone cannot be
edited phonetically.

A take with tokens is repairable on any machine that has the same model, LoRA
and a prefix-capable binary. A take without tokens is not repairable in general.

### 3.2 G0: the token check

The gate is not a re-render. It is a consistency check:

```
len(tokens) / 25  ≈  duration_s
sha256(tokens)    = the hash recorded with the run
sha256(wav)       = the hash recorded with the run
```

In RUN3 this took **7 seconds**:

```
5606 / 25 = 224.24 s vs WAV 224.238667 s
WAV sha 4f9006de…  tokens sha c218c41c…
```

If the count, duration and hashes agree, the tokens are this take's performance.
No AR re-derivation, no full render, no cross-architecture gate.

### 3.3 If the tokens are missing

You have one fallback: re-derive them with the original seed, lyrics, style,
sampler, LoRA and binary, then render the full stream and compare with the WAV.

This is a **foundation test**, not a repair step. It can fail for reasons
unrelated to the defect:

- AR sampling is deterministic **within** a GPU architecture and binary, not
  **across** them;
- an L4 take re-derived on a T4 produced **5937** tokens instead of **5727** and
  a different performance from the first 5 seconds (RUN2);
- bit-identity across architectures is a bonus, never a requirement.

If the gate fails, stop. Do not splice a different performance into the take.
The correct fix is upstream: export tokens at generation.

### 3.4 What to store with every keeper

```
WAV + sha256
semantic.json + sha256 + frame count
lyrics + style + seed
model / LoRA / binary / GPU
generation log (the resolved request line)
```

---

## 4. Find the defect precisely

### 4.1 Listen to the whole track first

Listen once without stopping. Mark:

- the exact word and timestamp;
- what was sung vs what should have been sung;
- whether the error is a consonant, vowel, word, pitch or timing;
- what happens **after** the word — does the melody continue, hold, or repeat?

The last point is critical. The damage may be in the note that follows, not only
in the word.

### 4.2 Text timing is not musical timing

Lyric timestamps and ASR word boundaries are useful starting points, not edit
boundaries. A word’s final vowel or consonant can be held for seconds. Find the
**complete musical unit**:

- start: the onset of the defective word, or a real gap just before it;
- end: the end of the note or melisma that belongs to that word, not the end of
  the lexical token;
- include any ornament, run, vibrato tail or release that belongs to the word.

**The aligner box is an index, not a cut.** In RUN3 the box for `مِلَّتِي` was
27.782–28.902, but the word actually started at **~27.52**; the box was ~0.26 s
late. Cutting at the box would have cut into the word and left the missing م
outside the edit.

### 4.3 Isolate the vocal

Use Demucs 4.1.0 `htdemucs` (or the version that produced the original stems) to
get the lead vocal. Measure on the stem, not the mix. Use the same separation
model for original and candidates when comparing.

Caveats: separation is not perfect; bleed and artifacts exist; check the full mix
after comping.

### 4.4 Measure, don’t guess

For the target unit, measure:

- **pitch contour** (f0): median, range, vibrato, final note;
- **duration**: how long the note actually lasts;
- **envelope**: RMS over 10–20 ms windows, gaps, breaths, level;
- **spectrogram / spectral centroid**: consonant attacks, sibilance, nasal
  murmur;
- **alignment / lag**: candidate vs original.

A useful sanity check: if the candidate’s final note is a different pitch class
from the original, no cut point will make it match. Fix the take, not the fade.

### 4.5 Write the repair card

```
Track / WAV sha:
Tokens sha / frame count:
Model / LoRA / seed / sampler / GPU:
Target word:
Occurrence:
Heard as:
Should be:
What follows the word:
Measured unit (start–end):
What must not change:
```

This card prevents the most expensive error: solving the wrong problem. In RUN3
it was `مِلَّتِي`, occurrence 1 of 2, opening verse; the repeated verse was
correct; the word was ~27.52–28.90, `فِي` before it and `وَاعْتِقَادِي` after it.

---

## 5. Choose the repair route

| route | fidelity to the take | control | cost | main risk |
|---|---|---|---|---|
| Keep it | 100% | none | none | defect remains |
| Donor splice from another take | high if same singer | medium | low | donor carries wrong phoneme/prosody |
| Audio inpainting | medium | low | medium | fills plausibly, cannot choose a phoneme |
| Section regeneration (hosted) | medium | medium | low | new section, seam, no bit-identity |
| Cover with audio influence | low–medium | one global dial | low | repeats the error at high influence |
| Local AR re-sing + comp | **high** | **high** | medium | NAR non-locality; needs a comp |
| New full generation | none | high | low | loses the happy accident |

### 5.1 Why donor splices usually fail

Taking the same word from another take of the same song is tempting: same
singer, same language, same style. It often fails because:

- the donor may have the same mispronunciation (shared model bias);
- the phoneme may be correct but the **prosody** — pitch, timing, vowel color —
  belongs to a different context;
- splicing audio at word boundaries creates a new join, often more audible than
  the original error;
- donor tokens do not automatically transfer the consonant.

Use a donor only if you can verify **phoneme + pitch + duration + level** in the
new context. If not, re-sing.

### 5.2 Why inpainting is not a phoneme tool

Audio inpainting fills a gap with plausible audio. It cannot make a singer
produce a specific consonant. Use it for clicks, drop-outs or instrumental gaps,
not as the primary fix for a mispronunciation.

---

## 6. Choose the unit

### 6.1 Word, phrase, note, or section?

| unit | use when | risk |
|---|---|---|
| Single word | the error is isolated and the surrounding phrase is correct | a join in a continuous phrase |
| Phrase | the model re-sings the phrase as a unit and the joins need context | replaces correct material; may drift |
| Sustained note / melisma | the error is in the ornament or final vowel | easy to cut inside the note; hard to match |
| Section | the whole section is wrong, or no clean internal boundary exists | replaces the most; highest chance of drift |

**Default:** the smallest unit that contains the error and has clean performance
boundaries. In RUN3 that was the whole word `مِلَّتِي`, from 27.46 (the
candidate’s nasal onset) to 28.98 (before `وَاعْتِقَادِي`).

### 6.2 The melisma rule

**Never end a comp inside a sustained vowel or melisma.**

If the final letter is held for seconds, that note is part of the word. Either:

- include the entire note in the replacement, or
- keep the original note and end the comp at its **start**.

If the candidate’s note is shorter than the original, keeping the original is
usually better than time-stretching. What cannot work is cutting 100–200 ms into
the note and handing the rest back to the original: the ear hears a truncated
note followed by a second attack or a pitch change.

### 6.3 Keep what is already correct

Do not replace a correct neighbouring word just because it is inside the same
phrase. In RUN3, `فِي` before the target and `وَاعْتِقَادِي` after it were
correct; the comp was kept between them.

### 6.4 Opening defects have no left context

If the defect is in the first vocal phrase and the track has an intro, use the
intro as the prefix. If the defect is the first vocal sound and there is no
prefix, the left edge is the file start (no left join); generate from 0 with the
same seed/params/ABC and judge the whole opening. Do not pretend it is a
word-level comp with a left seam.

---

## 7. Generate the candidates

### 7.1 One process, sequential seeds

For a local token model:

- **one** `audiocpp_cli_prefix` process at a time;
- **all seeds in one `--request-sequence`** — a second process repays the model
  load (RUN3: ~5 minutes);
- **4 seeds first; 16 is a ceiling**, not a target;
- no `&`, no `xargs -P`, no GNU parallel, no two generation notebook cells;
- before every seed, `pgrep -af audiocpp_cli` must show at most one process.

Two concurrent GPU runs can OOM a T4. In RUN3, one process at a time peaked at
~6.7 GiB host RAM and did not crash; the earlier crashes were consistent with
parallel/multiple model loads.

### 7.2 Cut the prefix before the error

The model should see the real lyric and the correct prior performance, but not
the bad pronunciation in its conditioning.

```
prefix = tokens[:round(unit_start_s × 25)]
```

RUN3: `tokens[:672]` = 26.88 s, ~120 ms before the /f/ of `فِي`. The same render
covered both B (word-onset join) and D (/f/-onset join).

**The prefix locks the tokens, not the prefix audio.** NAR re-synthesis changes
the prefix region at the sample level (RUN3: max abs diff 0.65), so never assume
bit-identity in the prefix. Comp only after the region you measured.

### 7.3 Bounds and the log

Set the end-token bounds:

```
semantic_min_tokens = semantic_max_tokens = round(gen_end_s × 25)
```

RUN3: `min=max=775` = 31.00 s, covering the line end at ~30.68 s.

Check the log **before** the next seed:

```
semantic_prefix_frames=672
min_tokens=775 max_tokens=775
semantic.tokens 775
```

**`truncated 1` is expected when `min=max`.** The AR is forced to stop at the cap
without an end token. Do not reject on `truncated`; check the bounds and token
count. `emitted_tokens` is also 775 in this binary (the total, not 103 new).

If the log says `max_tokens=7250` or `semantic.tokens=5606`, stop: the cap or
prefix bounds were not applied, and the run is much longer than intended.

### 7.4 Memory discipline

- Do not install/run Demucs or the optional ABC transcription before or during
  generation. Run them after the process exits; Demucs on CPU if RAM is tight.
- If the VM is a standard 12.7 GB T4, use a **high-RAM** runtime if available.
- If generation crashes with one seed and the correct bounds, diagnose host OOM
  (`Killed`, exit 137, “used all available RAM”) vs CUDA OOM (`CUDA out of
  memory`). Try high-RAM once; then `cot=off` once; then stop.

---

## 8. Filter before the ear

Generate a few candidates, reject the measurable failures, and audition 3–5.

### 8.1 What to measure per candidate

- word onset and word end on the candidate’s own stem;
- f0 contour in the used span;
- spectral centroid / low-band share at the consonant onset;
- lag vs the original (word and neighbours);
- seam step and click ratio after comping.

### 8.2 What the metrics can and cannot prove

- **Pitch contour** catches a wrong note or a different melody.
- **Duration / word end** catches a candidate that collides with the next word.
- **Spectral centroid** can separate a dark nasal onset from a bright vowel
  onset — in RUN3, s2/s3 had a 200–228 Hz centroid segment before the 220 Hz
  vowel; s1 did not.
- **CTC cannot prove a consonant.** It cannot distinguish `/d/` from `/g/`, and
  in RUN3 it could not prove the /m/. The ear decides the phoneme.
- **Envelope correlation** hides wrong pitch. Do not select on it alone.

### 8.3 The successful RUN3 filter

| candidate | pre-vowel dark segment (centroid) | f0 there | vowel onset | word end | verdict |
|---|---|---|---|---|---|
| original (defect) | none — 232–261 Hz | 195–201 | 27.52 | ~28.90 | “لتي” |
| s0 `…580` | 27.40–27.49 (~203) | 196 | 27.52 | ~28.95 | kept, not chosen |
| s1 `…581` | none — 264–400 | 201 | 27.56 | ~29.0 | rejected |
| **s2 `…582`** | **27.455–27.555 (208–228)** | 198–200 | 27.56 | ~28.95 | **chosen** |
| s3 `…583` | 27.44–27.54 (199–215) | 195–198 | 27.58 | ~29.0 | runner-up |

The /m/ is not provable by measurement; the centroid ranked the candidates and
the ear made the call.

### 8.4 At a consonant onset, f0/RMS is not the gate

The card’s steady-vowel rule is |Δf0| ≤ 20 cents and |ΔRMS| ≤ 1 dB. At a
**consonant-onset** join, the new consonant replaces the previous vowel tail, so
the step is expected to be large:

- RUN3 B_s2: **140 cents / −4.4 dB** at 27.46 — and the ear accepted it;
- the meaningful checks were the 10 ms mix-envelope continuity and the click
  ratio **0.29**.

Keep the 20-cent/1-dB rule for joins inside a sustained vowel. For a consonant
onset, use envelope + click + the ear.

---

## 9. Build the comp

### 9.1 Vocal stem only

If the goal is to keep the music, comp only the lead vocal:

```
new_mix = mix + (candidate_vocals − original_vocals)
```

inside the comp region only. Compute the difference at 44.1 kHz and resample to
48 kHz. Never use `no_vocals + candidate` — that replaces the arrangement too and
cannot be byte-identical outside.

### 9.2 Boundaries

Choose boundaries at:

- a breath or voiceless gap in the lead vocal;
- a real note offset or release;
- the start of the next word, if the previous word is correct;
- the candidate’s own consonant onset, when the join is consonant-to-vowel.

Avoid:

- fixed word ± 0.3 s;
- dictionary boundaries that fall mid-note;
- the middle of a sustained vowel;
- a boundary chosen only because the waveform is low-energy (the music may be
  sustaining underneath).

### 9.3 Ramps and level

RUN3 used **15 ms linear ramps on the difference**, not a long crossfade. A fade
removes clicks; it does not fix a wrong phoneme, a wrong pitch, or a level jump
of several dB.

### 9.4 One render, several comp widths

Generate a window wider than the unit, then comp 2–3 widths from the **same**
candidate:

- **B (default):** start at the candidate’s consonant onset; keep the previous
  word intact.
- **D (fallback):** start at the previous word’s onset; replaces one correct
  word but may give a cleaner consonant join.

In RUN3, B was used at **27.46–28.98**; D at 27.00–28.98 was not chosen. B starts
20 ms before the measured end of `فِي`’s vowel (27.48), so it replaces the last
~20 ms of that vowel tail to include the /m/ onset. `فِي` before 27.46 is
byte-identical; the claim is “outside 27.46–28.98”, not “`فِي` entirely
untouched.”

---

## 10. Verify

After building the comp, verify and print:

- the original file hash is unchanged;
- the final differs only inside the intended region;
- outside the region, the max absolute difference is **0**;
- duration is unchanged;
- the 10 ms mix envelope is continuous across the seam;
- the click ratio is low (RUN3: **0.29**; D was 1.19);
- f0/RMS steps are reported, with the consonant-onset caveat;
- the candidate word end is before the next word onset;
- the kept melisma / final note is intact;
- the music is unchanged (vocal-only).

Bit-identity is only meaningful at the same sample rate, channel layout and
format. If you resample or re-encode, document the conversion.

Keep the verification output. “Sounds fine” is not a QC record.

**Independent re-check (RUN3):** re-download the delivered file from GCS, verify
its sha256 and duration, and compare it with the base WAV outside the comp
region. This catches a bad upload or a wrong file.

---

## 11. Evaluate and review

### 11.1 Ear first

Listen to the **full track**, or a complete section that ends at a real boundary
or the end of the track. Do not judge a partial word.

Ask focused questions:

- Is the target phoneme correct?
- Is the melody/pitch correct?
- Is the timing natural?
- Is the join audible?
- Does the performance regress after the join?
- Is the music still the same?
- Does it sound like the same singer and the same session?

### 11.2 Blind A/B

Give the user two unlabelled files — original and repaired — in random order.
Keep the key out of the message. If the user identifies the repaired file
immediately, the edit is not transparent enough.

### 11.3 Record the scope of the verdict

A verdict on a 7 s line or a 30 s passage is not a full-track verdict. Record
exactly what was heard:

```
verdict: “م audible; no seam” on 02 + the 30 s opening passage
full track staged but not separately judged: yes/no
```

If the full track was not heard, that remains the final check.

### 11.4 Acceptance

Define “good enough” before listening:

- the word is intelligible and correct;
- the melody and timing are right;
- no new artifact at the join;
- the music is intact;
- the performance still feels like the same take.

A **9.5/10** result is often the right stop. Perfection is not the goal; a
transparent repair is.

---

## 12. Deliver and document

A repair is not delivered until it is documented and reproducible.

### 12.1 Minimum manifest

```
original_sha256:
final_sha256:
duration / sample rate / channels:
tokens_sha256 / frames:
changed_spans:
outside_max_abs_diff:
edge_envelope / click_ratio:
model / LoRA / seed / sampler / GPU:
candidate:
comp_region / ramps:
what_is_bit_identical:
what_is_not_bit_identical:
verdict / who heard it / scope:
```

### 12.2 Run layout

```
inputs/      original WAV + token + lyrics/style/score
tokens/      full tokens + prefix + sha
candidates/  all candidates (WAV + vocals), including rejects
comp/        comp.json + B/D comps + verify_*.json
final/       chosen WAV + sha + sidecar + blind A/B + key
session/     timing.tsv + notes + logs
```

### 12.3 Rules

- never overwrite the original;
- keep the candidate renders and token/seed files;
- keep the script or command that built the comp;
- state clearly that the audio is bit-identical **outside** the comp, not inside;
- keep an A/B pack with the original and final, using the same windows;
- version the delivery (`v1`, `v2`, …) and say what changed.

Use the reusable scripts from the case:
`comp_vocal_diff.py`, `measure_word.py`, `onset_table.py`, `verify_seam.py`.

---

## 13. Failure modes and fixes

| symptom | likely cause | fix |
|---|---|---|
| Cannot re-derive the take's tokens | no export; different GPU architecture | stop; use the take's own tokens, or regenerate with `export_semantic=true` |
| Parallel generation crashes / OOM | two model loads at once | one process; one `--request-sequence`; `pgrep` before every seed |
| `truncated 1` | `min=max` forced stop | expected; check `min_tokens`/`max_tokens`/`tokens` |
| Candidate is 224 s, not 31 s | cap/prefix bounds not applied | inspect the log; set `semantic_min_tokens`/`max_tokens` |
| Two consonants / “double word” | comp cut mid-word; original resumes inside the word | move the boundary to the word/note edge |
| A second vowel or second `ه` | comp cut inside a melisma | include the whole note, or keep the original note |
| Pitch jump at the join | candidate has the wrong final note | choose a take with the right f0 contour; fades cannot fix it |
| Large f0/RMS step at a consonant onset | expected: consonant replaces vowel tail | judge by envelope + click + ear, not the steady-vowel rule |
| Click / tick | sample discontinuity | short ramps; verify sample step |
| Prefix region not bit-identical | NAR re-synthesis | expected; comp after the measured region |
| Music changed | full-mix comp | vocal-stem diff comp; keep original instrumental |
| ASR says correct, ear says wrong | CTC is unreliable at phoneme level | trust the ear; inspect the spectrogram/centroid |
| Donor sounds wrong in context | correct phoneme, wrong prosody | re-sing in context |
| Regression after the edit | reviewed a partial word | full section/track |
| Seeds split across processes | extra model load | all seeds in one request sequence |

---

## 14. Model-specific notes

### Hosted cover / section systems (Suno-style)

- A cover with audio influence is a **global** control. High influence follows
  the source — including the error; low influence escapes the error but drifts.
- Section regeneration is closer to a local repair but still replaces a section.
- If the system does not expose stems or tokens, separate the output with Demucs
  and comp the vocal into the original. The result is only as good as the
  separation and the match between takes.
- If the vocal timbre does not match well enough, choose between a new full cover
  and keeping the error. Do not pretend a full cover is a surgical fix.

### Local token models (YuE / audio.cpp and similar)

- The song is represented as semantic tokens; you can force an exact prefix.
- Cut the prefix **before** the error; let the AR stage generate the unit.
- The NAR stage is globally coupled: the new render differs everywhere at the
  sample level. A local comp is mandatory for bit-identity outside the edit.
- Batch seeds in one process; model load is the fixed cost.
- Export tokens at generation; do not rely on cross-architecture re-derivation.

### Any system

- Isolate, choose the smallest unit, preserve what is correct, join at
  performance boundaries, verify, review complete audio.

---

## 15. One-page checklist

```
[ ] Save and hash the original. Never overwrite it.
[ ] Tokens exported? Count/duration/sha match (G0)? If not, stop.
[ ] Listen to the full track. Mark the defect and what follows it.
[ ] Classify: consonant, vowel, word, pitch, timing, or mix.
[ ] Separate the vocal. Measure the musical unit on the stem.
[ ] The aligner box is an index, not a cut.
[ ] Choose the route: keep / donor / section regen / AR re-sing + comp.
[ ] Cut the prefix before the error; build tokens[:N].
[ ] Set min=max=end; expect truncated 1; check tokens/bounds.
[ ] One process; all seeds in one request sequence; 4 seeds first.
[ ] Filter: pitch, word end, centroid, lag; keep 3–5; ear decides.
[ ] Comp the vocal only: mix + (cand_voc − orig_voc); 15 ms ramps.
[ ] B and D from the same candidate; B start at the candidate's consonant.
[ ] Verify: outside diff=0; duration; 10 ms envelope; click ratio.
[ ] Review the full track (or a complete section); blind A/B.
[ ] Deliver with hashes, comp points, token hash, and scope of verdict.
[ ] Stop at good enough if more editing would cost the take.
```

---

## 16. Templates

### Repair brief

```
Track / WAV sha:
Tokens sha / frames:
Model / LoRA / seed / sampler / GPU:
Target word:
Occurrence:
Heard as:
Should be:
What follows the word:
Measured unit (start–end):
Prefix tokens / max tokens:
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
duration / sample rate / channels:
tokens_sha256 / frames:
changed_spans:
outside_max_abs_diff:
edge_envelope / click_ratio:
model / seed / sampler / GPU:
candidate:
comp_region / ramps:
bit-identical outside:
not bit-identical inside:
verdict / scope:
```

---

## 17. Reference run: case 002 / RUN3

This is the canonical example to copy.

**Take:** `repro_abc_cfg15.wav`, sha `4f9006de…`, 224.238667 s, 48 kHz stereo.
**Tokens:** 5606 @ 25 fps, sha `c218c41c…`.
**Defect:** `مِلَّتِي`, opening verse, occurrence 1 of 2; the initial **م** was
missing; the repeated verse was correct.

### 17.1 Timing

| phase | actual |
|---|---:|
| preflight + asset fetch | 0:27 |
| **G0 token check** | **0:07** |
| prefix binary stage | 1:10 |
| approval gate | 0:45 |
| prefix + request JSON | 1:41 |
| generation, seed 0 alone | 5:22 |
| generation, seeds 1–3, one session | 7:07 |
| Demucs install + run (original + 4 candidates) | 1:15 |
| measure + filter | 2:13 |
| comp + seam verify | 0:49 |
| listen prep + blind A/B + upload | 1:31 |
| **machine total** | **26:01** |
| **wall total** | **39:22** |

The two-process split (seed 0 alone, then 1–3) cost ~5 min of model load. All four
seeds in one `--request-sequence` would have been ~7–8 min.

### 17.2 What was run

```
prefix = tokens[:672] (26.88 s)
min = max = 775 (31.00 s)
seeds = 3285212580, 581, 582, 583 (sequential, one process for 1–3)
guidance 1.5 · cot=full · abc_file=abc/score.abc · steps 8
context 24576 · nar_noise=generated · export_semantic=true
LoRA mix_v3/a0.1 (a01) AR d48109b3… NAR 88f00bcb… scale 1.0
attention=flash · binary 4117a46a…
```

Log proof:

```
semantic_prefix_frames=672
min_tokens=775 max_tokens=775
semantic.tokens 775
truncated 1   ← expected when min=max
```

### 17.3 What was chosen

- candidate **s2 / seed 3285212582**;
- comp **27.46–28.98 s**, vocal-only diff, 15 ms ramps;
- final sha `ae9217c1…87a654`, duration 224.238667 s;
- outside the region **byte-identical**;
- seam click ratio **0.29**; f0/RMS step **140 cents / −4.4 dB**, expected at a
  consonant onset;
- user verdict: **“م audible; no seam”** on 02 + the 30 s opening passage; the
  full 224 s track was staged but not separately judged in the transcript.

### 17.4 What made it fast

- **G0 in 7 s**, no re-derivation, no gate render.
- **One take's own tokens** as the prefix.
- **Bounds verified before the next seed** (`775`, not 7250/5606).
- **One process at a time**, no OOM.
- **Four seeds**, not sixteen.
- **Comp points measured per candidate**: the card's 27.50 was moved to 27.46
  because the candidate's nasal onset begins at ~27.45.
- **Vocal-only diff**, byte-identity outside, click/envelope verification.

### 17.5 Evidence and reproduction

```
gs://akbar-december-2024-backup/arabmaqamrock/runs/20261115-042753_repair002_cfg15/
  final/final_B_s2.wav
  final/final_sidecar.json
  comp/comp.json, comp/verify_*.json
  candidates/s0…s3 (WAV + vocals)
  tokens/, inputs/, session/timing.tsv
```

Scripts (in `cases/002_abu01_ajdad/scripts/`):
`comp_vocal_diff.py`, `measure_word.py`, `onset_table.py`, `verify_seam.py`.

Full report: [`cases/002_abu01_ajdad/RUN3.md`](../../cases/002_abu01_ajdad/RUN3.md).

---

## 18. Historical case: Baghdad Moon

**Status: historical learning case. Not the reference workflow.**

Baghdad Moon was the first real attempt (2026-10-20). It ended at 9.5–9.7/10
with two small spans replaced, and it produced many of the rules in this guide.
But it took **several sessions and hours**, and much of that cost came from
mistakes this guide now prevents. Do not copy its path.

### What it got right

- the original was preserved and hashed;
- the final was a deterministic composite, not a new song;
- the winning move was to replace **less**: `عَلَيْهِ` whole-word, and only
  `فَإِنَّ` in the outro, keeping the 5.5 s final `ه` byte-identical;
- the ear, not envelope correlation, chose the take;
- bit-identity was claimed only outside the edit.

### What cost the hours

1. **No exported semantic tokens.** The take had to be re-derived and gated
   before any repair; the gate was a session, not a step.
2. **Cross-architecture determinism.** The original was L4; the only prefix
   binary was T4. The re-derived stream was a different performance, and the
   gate failed. This is a foundation failure, not a repair failure.
3. **Donor splices.** Taking the word from another take was tried and rejected
   0/4; same singer is not enough.
4. **Phrase-first unit.** The outro phrase was treated as one unit; the comp
   ended inside a 5.5 s held note, producing a second `ه`.
5. **Envelope correlation.** It ranked a candidate first despite a wrong final
   note (D4 instead of G4). The metric hid the melody.
6. **Seed/round grinding.** Multiple rounds were spent on the wrong unit before
   the measurement changed the decision.

### What to copy from it

- the **unit** rule: smallest musical unit, not a dictionary word;
- the **melisma** rule: never cut inside a sustained note; keep the original
  hold when it is correct;
- the **ear** rule: metrics are filters;
- the **bit-identity** rule: outside the edit only.

### What not to copy

- do not start a repair without the take's tokens;
- do not make a cross-architecture re-derivation the gate;
- do not try donor splices as the primary route;
- do not start with the phrase if a word has clean boundaries;
- do not select on envelope correlation alone;
- do not treat the Baghdad narrative as the 30-minute workflow.

Historical docs: `docs/happy_accidents/Baghdad_Moon/token_surgery/` (now marked
historical). The current reference is §17 / RUN3.

---

## 19. Glossary

- **AR / NAR:** autoregressive and non-autoregressive stages of a token-based
  music model. AR generates semantic tokens; NAR renders audio and is globally
  coupled.
- **Semantic tokens:** discrete representation of the song’s content; a prefix
  can be forced to condition generation.
- **Prefix:** the token sequence before the generated unit. Cutting it before
  the error removes the error from the conditioning.
- **G0:** the token consistency check — count, duration, hashes. Not a render.
- **Comp:** a local audio splice; the original waveform with one region
  replaced.
- **Stem:** an isolated instrument or vocal track from source separation.
- **Melisma:** a sequence of notes sung on one syllable; can last seconds.
- **f0:** fundamental frequency; the perceived pitch.
- **Spectral centroid:** the “brightness” of a short spectrum; useful for
  separating a dark nasal onset from a bright vowel onset.
- **Click ratio:** seam sample-step relative to the max step inside the region;
  a low ratio means no click.
- **Bit-identity:** sample-for-sample equality. Claim it only outside the comp.

---

*Canonical guide, v2.0. If you remember only one line: **export the tokens, replace
less, keep the take, and measure the unit on the stem.***
