# Suno covers vs token surgery — how the workflows differ

This note compares the workflow that produced the original “happy accident” take
(Suno-style cover with audio influence, and Suno Studio section regeneration)
with the token-level repair used in this project.

Suno is described at the level of the observed user workflow, not as a claim
about its internals. The point is the control model: **global audio
conditioning with a fidelity/freedom dial** versus **bounded token-level
re-singing plus a local audio comp**.

> **Revision after round 6 (2026-10-20).** This note was written before the
> final-`ه` melisma was measured. The control-model comparison still holds, but
> two claims below are superseded: the musical unit is **not** 202.26–207.74 s
> (the final `ه` holds to ~213.2 s), and the accepted fix was **smaller than a
> phrase** — only `فَإِنَّ` (202.21–204.54 s), leaving the original
> `اللهَ يَنْزِعُهُ` and its melisma untouched. See §8.

---

## 1. The two problems look similar, but they are not

Both workflows start from the same place:

- the song is a happy accident — arrangement, melody, voice and mix are right;
- two words are mis-sung;
- the goal is to keep the take and fix only the phonemes.

Suno solves this by **regenerating the song under source-audio influence**. The
user searches for an influence value (e.g. 60–85%) where the pronunciation
changes but the arrangement still feels like the original. It is an iterative
global search: raise influence to stay close, lower it to escape the error.

Our workflow solves it by **regenerating only the musical unit and grafting it
back into the original waveform**. There is no full-song re-render in the
deliverable. Outside the comp region, the file is bit-identical to the original.

The difference is not just technical. It changes what “fidelity” means:

| | Suno cover / Studio | Token surgery |
|---|---|---|
| Fidelity to the source | approximate, perceptual | exact outside the edit (bit-identical) |
| What is preserved | the overall performance | the actual samples |
| What is allowed to change | everything, a little | only the chosen span |
| How the error is avoided | tune a global influence value | remove the error from the conditioning |

---

## 2. Why high influence repeats the mispronunciation

In an audio-influence cover, the **source audio is the conditioning**, and that
audio contains the error. At high influence the model follows the source’s
phonetic trajectory closely — including the wrong consonant. Lower the
influence and the text/style prior gets more say, so the error can disappear,
but the arrangement, timbre and timing also drift.

That is the 70% → 65% behaviour: one scalar trades **fidelity to the source**
against **freedom from the source**, and the error sits on the fidelity side.

In token surgery, the conditioning is a **semantic-token prefix that stops
before the bad word**. The model sees the real lyric and the entire prior
performance, but it does **not** see the erroneous word in the conditioning at
all. The error is outside the forced prefix; the AR must generate that word
from the text.

So we do not face the “high influence repeats the error” trade-off:

- we keep **100% of the context before the error**;
- we keep **0% of the error itself**;
- the model re-sings the word/phrase from the lyric.

The price is that the NAR stage is globally coupled: the re-sung audio differs
from the original everywhere at the sample level. That is why the delivery is a
**local comp**, not a replacement. We measured the non-locality explicitly
(median mel Δ outside the edited words 0.034–0.071 dB, p95 0.33–0.82 dB), and
the comp is what turns “a new render” into “a surgical edit”.

---

## 3. Side-by-side

| Dimension | Suno cover (audio influence) | Suno Studio (section regen) | Token surgery (this project) |
|---|---|---|---|
| What is conditioned | whole source audio at X% | section + surrounding context | exact token prefix before the unit |
| What is regenerated | whole song | selected section | word or phrase (AR tail) |
| Main fidelity control | influence % (one scalar) | section boundaries | prefix boundary + comp region (separate controls) |
| Is the error in the conditioning? | yes — the source audio contains it | often yes | **no** — the cut is before it |
| What is delivered | a new full mix | a new section | original waveform + local comp |
| Guarantee outside the edit | none | none | **bit-identical outside the comp** |
| Iteration space | influence up/down, seeds | section retries | seed sweep, unit (word/phrase), join points, fades, stem vs full mix |
| Typical failure | error repeats, or arrangement drifts | section seam | seam/level/timing — fixed by comp design |
| Cost per trial | one full song generation | one section generation | one tail render; many takes share one model load |

---

## 4. Mapping the Suno concepts onto this workflow

**“Cover influence 60–85%” → the prefix boundary.** There is no single
percentage. The nearest analogue is how much real prior performance is forced.
Unlike a percentage, it is discrete and exact: we force everything before the
error, so context is maximal and the error is absent.

**“Regenerate the verse” → bounded AR re-sing of the smallest correct unit.**
We first tried the phrase `فَإِنَّ اللهَ يَنْزِعُهُ` as one unit, but that was
too large: the original `اللهَ يَنْزِعُهُ` was already correct, and its final
`ه` is a ~5.5 s G4 melisma. The accepted fix re-sings **only `فَإِنَّ`**
(202.21–204.54 s) and leaves the rest of the phrase untouched. For the Verse-2
`عَلَيْهِ`, a word-level unit was enough. The principle is not “phrase beats
word”; it is “use the smallest unit that contains the error and has clean
performance boundaries.”

**“Nudge the model and retry” → seed sweep + take selection.** We rendered 16
tails, scored them on the intended unit, and picked the best. The model load is
the fixed cost; extra takes are cheap. The phrase-level shortlist put `s13`
first on vocal-stem envelope correlation (0.91 at +110 ms), but that score was
envelope-only: `s13` ends the phrase on **D4 (~295 Hz)**, not the original G4,
so it was invalid for a full-phrase replacement. It was still the right take
for `فَإِنَّ` alone. Envelope correlation ranks dynamics, not melody.

**“Keep the music as much as possible” → vocal-stem-only comp.** This is the
part the cover workflow does not give you. We can keep the **original
instrumental sample-for-sample** and replace only the lead vocal. That matters:
over the phrase, the take’s drums/bass/other correlate with the original at
≈0 (drums even +4 dB louder), so a full-mix comp would replace the arrangement,
not just the voice.

**“Where to make the cut” → joins in the performance, including melisma.** We
choose the entrance and exit from the vocal envelope and the actual note
boundaries, not from a timeline grid. For the outro, the first phrase comp left
at 207.90 s and called that “after the phrase”; in fact the final `ه` is a
~5.5 s G4 hold that runs to ~213.2 s, so 207.90 s was **160 ms inside the
note**. The accepted fix enters at 202.21 s and leaves at **204.54 s**, the
start of `الله`, keeping the original `اللهَ يَنْزِعُهُ` and its entire
melisma. The old v1 comp cut at 204.775 s, inside `الله`; the phrase comp cut
inside the `ه`.

**“Iterative nudging” → a different search space.** Suno iterates on one global
knob. We iterate on interpretable choices: the unit, which take, where the joins
are, fade length, full mix vs vocal stem. The S2 search moved from word-level
to phrase-level and then **back to a smaller word-level unit**, from 40 ms to
50/120 ms fades, from full mix to vocal stem, and from 202.10 to 202.21 s. The
last move was the important one: the winning edit was smaller, not bigger.

---

## 5. What each workflow is good at

**Suno is better when** the goal is a new version of the song in the same
spirit, with minimal engineering. It is fast, integrated, needs no local GPU or
binary, and lets you audition full takes immediately.

**Token surgery is better when** the goal is to preserve a specific recording.
It is slower to set up, but it gives:

- a deterministic anchor (the original hash never changes);
- bit-identity outside the edit;
- joins chosen at vocal gaps, with measured edge level steps;
- a phoneme fixed by re-singing from the lyric, not by hoping a global
  influence value lands on it;
- reproducibility from tokens, seeds and scripts;
- the ability to keep the original instrumental while replacing only the vocal.

---

## 6. The philosophical difference

Suno searches a **global fidelity/freedom knob** until the error disappears.

This project **removes the error from the conditioning**, regenerates only the
musical unit, and **grafts it back** into the original.

That is the whole difference in one sentence. It is why we can have both a
correct `فَإِنَّ` and a rest of the track that is literally the same recording.

---

## 7. Practical checklist if you come from the Suno workflow

1. **Do not regenerate the song.** Find the exact frame range of the error and
   its **complete musical unit** — word, phrase, or sustained note, including
   any melisma. Use Demucs + pitch/duration, not text timing alone.
2. **Cut the conditioning before the error.** Force the token prefix up to the
   unit; let the model generate the unit from the lyric.
3. **Sweep seeds, score the unit, not the whole song.** Use the ear for the
   phoneme; use pitch, duration, envelope and DTW for rhythm and level. Never
   select on envelope correlation alone.
4. **Choose joins in the performance.** A breath, a voiceless gap, or a real
   note boundary — never a fixed word ± margin and never inside a sustained
   vowel. Check the neighbouring word and note boundaries.
5. **Deliver by comp.** Replace only the chosen span; verify bit-identity
   outside it. If the music must not change, comp the vocal stem only. If the
   original vocal is already correct, leave it alone.
6. **Measure the seam.** Edge level step, sample step, pitch continuity and
   phrase continuity. A 40 ms fade removes clicks but not a mid-word cut, a
   pitch change, or a +3.5 dB level jump.
7. **Review with complete audio.** Full track + target timestamps, or a
   complete section ending at a real boundary / end of track. Never ask for a
   verdict on a partial word.

---

## 8. Revision after the melisma finding

The original version of this note treated `فَإِنَّ اللهَ يَنْزِعُهُ`
(202.26–207.74 s) as a phrase ending at 207.74 s and recommended a phrase-level
comp ending at 207.90 s. That was wrong for this song:

- the final `ه` is a **G4 ≈ 391 Hz hold from ~207.7 to ~213.2 s (≈5.5 s)**,
  with release/reverb to ~215 s; 207.90 s is 160 ms inside it;
- `s13` ends the phrase on **D4 ≈ 295 Hz**, not G4, so an `s13` phrase comp
  could never preserve the original ending;
- the original `اللهَ يَنْزِعُهُ` was already correct, so replacing it was
  unnecessary;
- the accepted fix is **only `فَإِنَّ`**, 202.21–204.54 s.

The general correction is not “use a phrase instead of a word.” It is:

> **Use the smallest unit that contains the error and has clean performance
> boundaries. Keep everything the original already sings correctly.**

That is why the winning edit is smaller than the phrase and why the original
melisma is untouched. The Suno Studio analogy remains the closest in spirit,
but our best edit was smaller and stricter than a section regeneration.

---

Related documents: `LESSONS.md`, the canonical
`../../../guides/fixing_ai_music_mispronunciations.md`, `report.md` §5–§8,
`PROGRESS.md` §4, `CHECKPOINT.md` §6.8, and the case study
`../case_study_Baghdad_moon.md`.
