# tarab_test_01 — listening evaluation

Five takes of the same score (`scores/moon_101_v2.abc`, sha `e5748c62`), same
seed 101, same cap 7000, same lyrics. Only the style prompt and, in one take,
the lyric stage directions change.

| take | condition |
|---|---|
| `ctrl_repeat` | current tag-list prompt, re-rendered — variance check against C1 |
| `t1_template` | full Hijaz training template (BPM clause removed) |
| `t2_template_backing` | t1 + distant backing vocals at line ends |
| `t3_tag_band` | tag list + "band re-enters between lines" |
| `t4_template_backing_lyrics` | t2 + call-and-response stage directions in the lyric brackets |

Hypothesis: B's teamwork is described word-for-word in the training caption
(`PRODUCTION_STANDARD` in `maqam_prompt_generator.py`) but the moon prompts used
a short tag list that omits it.

## Scorecard

`eval/scorecards/tarab_test_01.json`. Copy it next to the rating app:

```bash
cp eval/scorecards/tarab_test_01.json /path/to/ai_music_rating_app/scorecards/
```

Then point the app at the rendered run folder:

```bash
python app.py --audio "out/<timestamp>_tarab_test_01" --scorecard tarab_test_01 --blind
```

## What the numbers mean

- `bc_edge` is the ranking metric: how close the take is to "a lead voice that
  is the star, with a band that answers in the gaps".
- `band_answers` is the mechanism. If it stays at 1 across all five takes, the
  prompt is not the lever and the arrangement has to come from the score.
- `second_voice` tests B's "felt backing" specifically.
- `tarab` and `distinct` test the other half of the 5-star sentence.
- `diction` is a gate: whole-line collapse makes the take unusable regardless of
  the other scores.

## Decision rules

1. If `ctrl_repeat` does not sound like C1, the pipeline is variable. Judge the
   four variants against the repeat, not against C1.
2. If `t2` or `t4` clearly beats `ctrl_repeat` on `band_answers` and
   `second_voice`, the single sentence steers the band. That is the knob.
3. If `t1` beats `t3`, the full template matters, not just the one sentence.
4. If nothing beats the control on `band_answers`, stop tuning prompts and test
   an explicit sparse `Ins` line in the score instead.
