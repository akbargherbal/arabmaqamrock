# Session — tarab / arrangement test, listening pending (2026-10-26, evening)

Read this first when resuming. State of play, not narrative.

**Status:** the project pivoted this session from "edit the melody for maqam" to
"what made Baghdad Moon stick, and can we aim at it". The new target is the
**BC edge** (§2). The test batch was rendered and **rated** on 2026-10-26
17:33–18:02 UTC.

**Result, in one line:** `t1_template` — the plain full training caption, nothing
added — produced B's line-splitting call-and-response with zero diction faults
(8.5/10). Every attempt to *ask* for that behaviour removed it: t2 (explicit
backing sentence) went flat at 7.5, t3 (the sentence as a fragment) gave
chorus-only backing at 7.5, t4 (stage directions in the lyric brackets) bought
the batch's best arrangement with a text collapse and is gated out.

Full analysis, scores, resolved decision rules and the next batch:
**`eval/tarab_test_01/FINDINGS.md`**. Raw report:
`eval/tarab_test_01/rating_20261026-2102.md`.

Two things are in flight: t1 has **n=1 at seed 101**, so it may be another happy
accident rather than a knob; and the app was run with the **default** scorecard
and `blind: false`, so the `bc_edge` numbers do not exist yet. Both are addressed
in FINDINGS §5–§6. Do not extend to seeds 313/577 until t1 replicates.

## 1. Why the pivot

The user's brief at the start of the session: *"I want to rethink the whole
enterprise from scratch."* The maqam-edit thread had produced rounds of sheets
that passed their own checks and tracks the user did not want. The reason is now
clear and should not be re-litigated:

- "Maqam" is used loosely in this project. Nobody is checking theory. The user
  does not know or care whether Suno/the LoRA adhered to Hijaz.
- The 438-track corpus was generated from `maqam_prompt_generator.py`; the music
  felt good, so the trigger word became `arabmaqamrock`. The LoRA averages
  **8/10, occasionally 9/10**.
- **Baghdad Moon** is the rare 9/10 happy accident. It was repaired (two
  mispronunciations) and accepted at 9.5–9.7/10. It is the target archetype.
- The target is therefore **more takes like B**, not theoretical maqam fidelity.

The old edit work is paused, not deleted. The six round-2 WAVs and the G1
listening are superseded by this thread.

## 2. The triangle, in the user's words

| vertex | what it is | user's description |
|---|---|---|
| **A** | any take generated **without** an ABC score — the out-of-the-box LoRA family, e.g. seeds 101/313/577 | 7/10, generic, chill, bland. "A style in itself", but not the target. |
| **B** | Baghdad Moon (the happy accident) | 9/10. Vocals perfect; music feels different; **choir / teamwork**. Backing comes and goes, felt more than heard. Backing sings half a line (*أعطيت ملكًا*), lead answers (*فلم أحسن سياسته*); guitar fills 1–2 s gaps and leaves. |
| **C** | the v2 edit of seed 101, run `20261025-195356_moon_edit` | promising; **a lead singer shining**. The band is sparse and works around him; the chorus sounds traditionally Arabic (*أستودع الله في بغداد لي قمرًا*); "not a busy song". |

**The sweet spot is the BC edge:** a star lead voice with a tarab character, plus
a band/second voice that answers only in the gaps and never competes.

Named B moments, verified against a word-level alignment of the final WAV:

| time | event |
|---|---|
| 0:38.5–0:43.7 | line 2 (أستودع الله في بغداد لي قمرا) |
| **0:43.7–0:46.1** | **the voice stops; the band answers — the 2-second fill** |
| 1:33–1:46 | chorus; lead + backing together |
| **1:51.6–1:57.5** | the line the user hums: لا أكذب الله ثوب الصبر منخرق عني |
| 1:57.5–1:59.7 | band answer after that line |
| 2:16.8–2:29.0 | أعطيت ملكا فلم أحسن سياسته / وكل من لا يسوس الملك يخلعه |

User's five-star sentence for B: **"the vocals are perfect"** and **"the music
feels different"** — different from the LoRA average, reminding of **tarab
without oud/qanun/darbuka**. The user is not sure "tarab" is the right word;
it is a working name, to be tested, not defined.

## 3. What the score analysis found (do not re-derive)

We read five scores: A1/A2/A3 (vanilla seeds 101/313/577), B, and C1 (the v2
seed-101 sheet). Findings:

- **A and B are nearly identical on gross vocal metrics.** Singing covers 57–63%
  of the track in all of them; A1, B and C1 all span 21 semitones; phrase count,
  phrase seconds and gap distributions overlap. So "more melody", "more range",
  "more silence" or "more fills" do **not** explain why B sticks.
- **The ABC does not contain the 0:43.7–0:46.1 fill.** B's `Vocal` line is
  silent there and the `Ins` line shows nothing until 0:50.9. The transcript is
  a melody sketch, not the arrangement. Use the scores to rule things out, not
  to explain the magic.
- **C vs A1 is the only controlled pair:** same take, same rhythm, same phrase
  boundaries. C's differences: one voice instead of two (the `Ins` line was
  deleted), the chorus sits ~3.9 semitones higher (61.1 → 65.0), and the melody
  is rewritten with 151 accidentals. The user hears that as "soloist" vs
  "choir/teamwork", and hears the Arabic character in C's chorus.
- **The strongest lead is in the training caption, not in the audio analysis.**
  `PRODUCTION_STANDARD` in `maqam_prompt_generator.py` says, verbatim:
  *"forward vocals pulling instrumentation down on sustained phrases then band
  re-enters between lines … natural breath room between phrases."* That is the
  B behaviour, written in the data the adapter was trained on. The moon runs used
  a short tag list that **omits this sentence**. Hypothesis: the prompt is a knob
  we have not pulled.

Useful hashes and lengths:

| item | value |
|---|---|
| B final WAV | 215.878667 s, sha `9b8fdb21…6311c` |
| B transcript | sha `9f57b30c…4010e`, 2/4, 89 BPM, Gm, `Vocal` + `Ins` |
| C score | `scores/moon_101_v2.abc`, sha `e5748c62…8bee` (tracked) |
| C1 render | `moon_101_v2_101.wav`, 198.798667 s, cap 7000, seed 101, `cot=melody` |
| A1 / A2 / A3 | 217.318667 / 242.878667 / 237.838667 s |

The five audio files are in `local_workspace/listen/` with `LISTEN.md`:
`A1_vanilla_seed101.wav`, `A2_vanilla_seed313.wav`, `A3_vanilla_seed577.wav`,
`B_baghdad_moon.wav`, `C1_v2_seed101.wav`.

## 4. The test batch: `tarab_test_01.json`

Same score (`moon_101_v2`, sha `e5748c62`), same seed 101, same cap 7000, same
lyrics. **Only the conditioning text changes.**

| take | prompt | question |
|---|---|---|
| `tarab_ctrl_repeat` | current tag-list prompt, re-rendered | is the pipeline repeatable vs C1? |
| `tarab_t1_template` | full Hijaz training template, BPM clause removed | does the in-distribution caption beat the tag list? |
| `tarab_t2_template_backing` | t1 + distant backing at line ends | can we *ask* for B's felt second voice? |
| `tarab_t3_tag_band` | tag list + "band re-enters between lines" | is that one sentence enough? |
| `tarab_t4_template_backing_lyrics` | t2 + call-and-response in the lyric brackets | does scripting it in the lyrics help? |

`tarab` is not in any prompt. The test uses words from the training vocabulary.

Dry-run: 5 tracks, ~32 min on a T4, cap 7000, score 218.6 s → 5466 frames,
headroom 1534. Output names: `<name>_101.wav`.

## 5. How to evaluate

App: `https://github.com/akbargherbal/ai_music_rating_app.git`.
Scorecard: **`eval/scorecards/tarab_test_01.json`** — validated against the app's
own validator, 14 criteria, summary metric `bc_edge`.

```bash
cp eval/scorecards/tarab_test_01.json /path/to/ai_music_rating_app/scorecards/
python app.py --audio "out/<timestamp>_tarab_test_01" --scorecard tarab_test_01 --blind
```

Blind mode is required: it hides file names and shuffles order, so the prompt
labels cannot drive the rating.

Scorecard keys, in order:

| key | measures |
|---|---|
| `bc_edge` | closeness to the BC edge (the ranking metric) |
| `overall` | gut call |
| `lead_front` | is the lead the star, or shared/buried? |
| `band_answers` | does the band answer in the pause before he returns? |
| `sparse` | is there room around the voice? |
| `second_voice` | none / faint and felt / clear answers / full choir / overwhelms |
| `tarab` | Arabic character as *feeling*, not theory |
| `distinct` | different from the LoRA average |
| `memorable` | a moment to replay or hum |
| `diction` | **gate** — whole-line collapse makes the take unusable |
| `mix`, `artifacts`, `keep`, `notes` | controls |

## 6. Decision rules for the next session

1. **First, the variance check.** Compare `tarab_ctrl_repeat_101.wav` with C1
   (`C1_v2_seed101.wav`). If they are materially different, the pipeline is
   variable: judge the four variants against the repeat, not against C1.
2. **If `t2` or `t4` beats the control on `band_answers` and `second_voice`,
   the single backing sentence steers the band.** That is the knob; extend to
   seeds 313/577.
3. **If `t1` beats `t3`, the whole template matters**, not just one sentence.
4. **If nothing moves `band_answers`,** stop tuning prompts. The next lever is a
   sparse answering `Ins` line written into the C score. Do not go back to
   melody editing.
5. **Diction is a gate.** Any take with whole-line collapse loses regardless of
   its musical scores.
6. Record the actual numbers; do not summarise from memory. Export the app
   report (Markdown/JSON) into `eval/tarab_test_01/`.

## 7. Open items

- Render `tarab_test_01.json` in Colab; confirm **all five WAVs** landed. The
  run is resumable with `--out-dir`.
- Copy the scorecard into the app repo before launching.
- The scorecard snapshot and report go in `eval/tarab_test_01/` after the
  session.
- If the prompt knob works, the next batch is the same conditions on seeds 313
  and 577, plus B and C1 as anchors, to see whether the effect survives the take.
- If the prompt knob fails, the `Ins`-line test is the next single experiment.
- The `tarab` label is provisional. If the ratings show the shared factor is
  something else, rename the objective; do not defend the word.
- The round-2 G1 listening is superseded but the six WAVs remain on disk. Do not
  delete them.

## 8. Rules of engagement

- **Name the file with any timestamp.** "A at 1:37" is ambiguous; write
  "`A1_vanilla_seed101.wav` at 1:37". A is a family, not a track.
- **A = any no-ABC take.** B = Baghdad Moon. C = the v2 edit (C1 = seed 101).
- **Do not re-open the maqam-theory thread.** The user's ear is the ground truth;
  the analyst cannot hear, so it must not explain the magic from the notation.
- **Do not judge a difference from one take.** Use the repeat and, when the
  effect looks real, a second seed.
- **Do not let the word "tarab" become a definition.** It is the current name of
  a hypothesis.
