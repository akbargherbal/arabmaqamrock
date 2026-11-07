# حبيتك — prompt sweep (round 07)

**Question:** can the style prompt alone make the arrangement denser?

Round 06 proved the NAR decoder is not the lever (it only adds ~2.5 dB of level,
about 2 dB of presence, and narrows the stereo image). The score fixes the notes;
the **style prompt + section tags** are the only text controls that can change
which instruments play and how busy they are.

## The formula

YuE2 conditions on a short tag string, not prose. Order matters: strongest tags
first. Six slots:

```
1 genre + mood        Arabic pop instrumental, romantic, cinematic
2 tempo/key/meter     101 BPM, G minor, 4/4
3 instrument + verb   oud carries the lead melody, qanun answers with tremolo,
                      violin and cello sustain the chords, electric bass locks
                      with the kick
4 rhythm section      darbuka and riq drive a busy groove, hand claps on the
                      backbeat
5 density words       layered full-band arrangement, continuous comping,
                      call-and-response fills, no empty space
6 production + ban    punchy drums, warm low end, wide stereo, plate reverb,
                      no vocals
```

Rules:

- **Never write prose.** One long paragraph dilutes the tags; the round-04/05
  captions (1343 chars) are the counter-example.
- **Name the instrument and its job.** `oud lead` is weak; `oud carries the lead
  melody with vibrato` is strong.
- **Say who plays continuously.** `continuous comping`, `no empty space`,
  `busy fills` are the density levers.
- **Ban the voice at the end.** The instrumental LoRA expects `no vocals`.
- Section tags control *when* layers enter; use `[instrumental]` for the score's
  `interlude` (not in the LoRA's tag list).

## Variants

All takes use the same score, seed `20261106`, `cot=full`, `cap=6993`, AR scale
1.0, NAR off. **Only the style string changes** (except `s5`, which also swaps
`[instrumental]` for section tags).

| # | Name | Chars | Idea |
|---|---|---|---|
| 1 | `s0_control_long` | 1343 | the round-04/05 prose baseline |
| 2 | `s1_compact` | 182 | short tag list |
| 3 | `s2_roles` | 418 | every instrument with a verb/role |
| 4 | `s3_rhythm` | 262 | rhythm section forward, melody light |
| 5 | `s4_dense` | 405 | "wall of sound" maximum density |
| 6 | `s5_roles_sections` | 418 | `s2` + section plan |

Section plan for `s5` (score order is intro → verse → chorus → interlude →
verse → chorus → interlude):

```
[intro]
[verse]
[chorus]
[instrumental]
[verse]
[chorus]
[instrumental]
```

## Run

```bash
python3 generate.py manifests/fadhl_shaker_instrumental_07_prompt_sweep.json --dry-run
python3 generate.py manifests/fadhl_shaker_instrumental_07_prompt_sweep.json \
  --label fadhl_inst_07_prompt
```

Six takes, ~39 min on a T4. If the session is short, `--limit 5` drops `s5`.

## How to judge

Listen in this order, at matched loudness:

1. `s0` vs `s1` — does dropping the prose change anything?
2. `s2` — are the named instruments actually audible (qanun counter-line, bass,
   hand claps)?
3. `s3` — is the groove busier?
4. `s4` — is it denser or just muddier?
5. `s5` — do the section tags make layers enter/leave?

Pick the best, then that style becomes the default for the 23-song batch.
