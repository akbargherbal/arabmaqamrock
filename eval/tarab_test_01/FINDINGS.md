# tarab_test_01 — results

Run `20261026-164848_tarab_test_01`, rated 2026-10-26 17:33–18:02 UTC.
Source report: `rating_20261026-2102.md` (same directory). Five WAVs, all five
rendered and rated.

**Caveat on the record, not on the finding:** the app was launched with the
**default** scorecard (`meta.settings.scorecard == "default"`) and
`blind: false`. So this run has no `bc_edge` / `lead_front` / `band_answers` /
`second_voice` / `tarab` / `distinct` / `memorable` numbers. What it has instead
is the unedited listening notes, which describe the mechanism more precisely
than the scorecard would have. The missing numbers are a record-keeping debt,
not a gap in the evidence — see §5.

## 1. Scores

| take | overall | fidelity | coherence | mix | artifacts | keep | user /10 |
|---|---|---|---|---|---|---|---|
| `tarab_ctrl_repeat` | 4 | 5 | 4 | 5 | none | yes | **8.0** |
| `tarab_t1_template` | 4 | 5 | 5 | 5 | none | yes | **8.5** |
| `tarab_t2_template_backing` | 4 | 5 | 4 | 5 | none | maybe | **7.5** |
| `tarab_t3_tag_band` | 4 | 5 | 5 | 4 | none | maybe | **7.5** |
| `tarab_t4_template_backing_lyrics` | 3 | 4 | 4 | 4 | **major** | **no** | **gate fail** |

App means: overall 3.80, fidelity 4.80, coherence 4.40, mix 4.60.

The 1–5 `overall` column does not discriminate — four takes sit at 4. The
signal is in the `/10` annotations and the notes. That saturation is the reason
`tarab_test_01` exists as a separate scorecard; the default one cannot rank
this batch.

## 2. The finding: t1 produced the B mechanism; every attempt to *ask* for it
## removed it

**`t1_template` (8.5) is the only take in the batch that did the B thing.**
Verbatim from the notes: the band sings *أستودع الله في*, the lead answers
*بغداد لي قمرًا*, then the band continues *بالكرخ من فلك الأزرار مطلعه* — line
split across voices, lead in front, no competition. The user adds that there
are **no pronunciation errors at all**, "and that counts for it".

t1 differs from the control in exactly one way: the style text is the **full
in-distribution training caption** (the `PRODUCTION_STANDARD` text from
`maqam_prompt_generator.py`, BPM clause removed). Nothing was added to the
lyrics. Nothing was over-specified.

Then, the three attempts to improve on t1:

- **`t2` = t1 + one sentence of explicit backing instruction**
  ("Distant backing vocals answer the lead only at line ends, felt more than
  heard, never a choir; the lead is alone in front.") → **7.5, "boring and
  repetitive, ordinary singing", no backing mentioned at all.** The explicit
  demand produced the *least* interplay in the batch.
- **`t3` = tag list + the production sentence as a fragment** → 7.5, backing
  appears **in the chorus only**, plus a word error (*جنايته*). The fragment
  out of its template underperforms the whole template.
- **`t4` = t2 + call-and-response stage directions inside the lyric brackets** →
  unusable. It sang *لا أكذب الله في بغداد لي قمرًا* — a line from the wrong
  verse grafted onto the right line's second half — **then corrected itself**.
  Major artifact, keep=no. The user's reading: "too many tags broke the model's
  thinking". Musically it is the most inventive take in the batch (humming,
  creative backing voices) **at the cost of the text**.

## 3. The hypothesis, revised

The checkpoint's hypothesis was that the `PRODUCTION_STANDARD` sentence about
the band re-entering between lines is the un-pulled knob. **Confirmed for t1,
falsified as an add-on.**

The pattern across the four variants is sharper than "the sentence works":

> **Describe the sound; do not assign the roles.**

The sentence that works is an *acoustic* description of the mix — "forward
vocals pulling instrumentation down on sustained phrases, then band re-enters
between lines, natural breath room between phrases". It says what the recording
sounds like.

The sentence that backfired is a *directive* about casting — who answers whom,
how quiet, "never a choir", "the lead is alone in front". Same idea, opposite
result.

And the lyric brackets are not a control channel at all: pushing stage
directions into the lyrics cost the text contract.

A second, weaker signal in the same direction: **text fidelity and arrangement
invention compete.** t4 bought its best arrangement with a text collapse. t1 is
the only take that got arrangement *and* clean diction. If that budget is real,
it explains why B is rare — it needs both at once — and it makes "accuracy" and
"creativity" one dial rather than two.

## 4. Decision rules, resolved

| rule | verdict |
|---|---|
| 1. variance check | **open** — see §6. ctrl 8.0 with 3 minor makhraj slips; no ear comparison against C1 was recorded. |
| 2. t2/t4 beat control on `band_answers` / `second_voice` | **no.** t2 flat, t4 gate-failed. The additive backing sentence is falsified. |
| 3. t1 beats t3 | **yes**, 8.5 vs 7.5, and qualitatively: line-level call-and-response vs chorus-only backing. The whole template matters, not the fragment. |
| 4. nothing moves `band_answers` | not triggered — it moved, in t1. |
| 5. diction gate | t4 fails. t1 is the only take with zero diction faults. |

## 5. Debt and how to pay it

1. **Re-rate the same five WAVs** with `tarab_test_01`, **blind**. No GPU, ~10
   min. Gives the actual `bc_edge`/`lead_front`/`second_voice` numbers and
   removes the label-visibility problem (the user knew which take was which,
   which is the one protocol element that was violated).
2. Copy the new run folder into `local_workspace/` so the WAVs are on this
   machine — it also makes the variance check a measurement instead of a
   listening call (§6).

## 6. The two things that could still sink this

- **t1 may be another happy accident.** B was one; t1 has n=1 at seed 101 and
  wins by 0.5/10 over a control that is inside the LoRA's normal 8/10 band.
  Until t1's mechanism reproduces on a second seed it is a lottery ticket, not
  a knob. This is the single most important next test, and it is exactly what
  the checkpoint's "do not judge a difference from one take" rule warns about.
- **The pipeline may be variable.** `ctrl_repeat` used the same score, seed,
  cap and (as far as the record shows) the same tag list as C1, which rendered
  at 198.798667 s. If the new control's duration is ~198.8 s the pipeline is
  effectively deterministic and t1's margin is real; if it is materially longer
  or shorter, the batch has to be read as four takes against a fresh baseline
  rather than against C1.

## 7. Next batch (proposal, not yet written)

Only after t1 replicates. Same score, same cap, same lyrics, and only the
prompt changes:

| take | purpose |
|---|---|
| `t1_template` @ 101, 313, 577 | does the mechanism survive the take? |
| `t1_template` @ 101 (second render) | is a second t1 render even the same song? |
| `ctrl_repeat` @ 313 | baseline at a second seed |
| B, C1 | anchors, already on disk |

Optional, only if the mechanism reproduces and we want the mechanism itself:
`t1` minus the `PRODUCTION_STANDARD` sentence — a clean ablation that separates
"the whole template" from "that one acoustic sentence".

Do **not** re-run t2/t4 and do **not** put stage directions in the lyric
brackets again.
