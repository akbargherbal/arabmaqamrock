# Round 09 — density words out, idiom words in

**Written:** 2026-11-08
**Score:** `scores/fadhl_shaker_instrumental/habeetak.abc` (269.7 s, Gm, 101 BPM)
**Seed:** `20261106` for every take, `cot=full`, AR LoRA 1.0, NAR off, `trigger: false`

Round 07 proved one word: `Arabic`. This round asks two questions about the rest
of the string, and one about the genre vocabulary.

## 1. Hypothesis — the density words cost more than they buy

`g4` contains `busy instrumentation, no empty space`. The user's read: these may
produce an over-correction. The measurements support it.

`g2_dense` (which differs from `g4` only by the word `Arabic`) shows the failure
mode of asking for density:

| metric | `g2_dense` | `g3_prose` | `g4_arabic` |
|---|---|---|---|
| crest factor | 13.0 | 15.3 | 14.5 |
| 200–500 Hz (rel. LUFS) | **−7.8** | −12.2 | −11.1 |
| 1.2–3 kHz | **−23.9** | −16.9 | −16.3 |
| 6–10 kHz | **−27.5** | −23.3 | −27.5 |
| frame occupancy | 99.5 % | 95.0 % | 94.8 % |

Occupancy is already 95 % without the density words, and 99.5 % with them. The
"no empty space" instruction buys ~5 % more frames and pays for it with a
compressed, low-mid-heavy, dull mix — the thing the user heard as "no feel".

Mechanism: `busy instrumentation, no empty space` describes **mix density**, and
the only way the model can satisfy it is to stack layers and squash them. It
cannot add *arrangement ideas* on command. `layered arrangement` survives the cut
because it describes structure, not loudness.

So `h1_lean` = `g4` minus those two phrases, one variable changed.

## 2. The scale cue

The LoRA's training captions carried `Maqam <name>, <Western scale>` on every
line (see `docs/base-prompt.md`), and the winning variable in the `space-stallion`
batch was the **Western scale name beside the Arabic maqam name**. Generic modal
words were never tested for the instrumental path, so `h2_maqam` tests the cheap
generic form first:

```
maqam, Middle Eastern scales
```

If it wins, the per-song version is score-derived (the ABC already carries the
key and the accidentals), so it stays batch-safe — no per-song handwriting.

## 3. The genre tag — which umbrella?

The user's question: is there a single tag that is **comprehensive** (covers any
Arabic instrumental) and **exclusive** (admits nothing else)? `Arabic` already
does the exclusion — round 07 is the proof: one word, and the take went from
"no feel" to the winner. What is missing is coverage of the *idiom* — the frame
that licenses strings + a rhythm section + modally ornamented lead without
naming a single instrument.

Candidates, and what each actually encodes in caption space:

| tag | covers | excludes | risk |
|---|---|---|---|
| `Arabic orchestra` | the firqa: strings, qanun/oud, percussion, 1970s–2000s Arabic pop | yes, via `Arabic` | English "orchestra" leans Western-symphonic; may drop the drum kit |
| `Arabic pop orchestra` | the same plus the era's drum machine + bass, i.e. exactly `g4`'s "full band" | yes | `pop` may pull Western pop production |
| `tarab` | the aesthetic itself (طرب) — the most Arabic-exclusive word available, and it is already in the training captions | strongly | tarab implies voice and slow melisma; may flatten the groove |
| `Middle Eastern` | geography | no — admits Turkish/Persian | too weak alone |
| `orchestral` (bare) | Western film/symphonic | no | **rejected**: not Arabic-exclusive, loses the rhythm section |
| `world fusion` | nothing specific | no | **rejected**: dilutes everything |

Working recommendation, to be settled by ear: **`Arabic pop orchestra`** as the
umbrella (the closest name for what the user called "full band" Arabic pop), with
the maqam pair as the modal hook — score-derived, one line, no instrument names.

## 4. The sweep

| # | take | what it isolates |
|---|---|---|
| 1 | `h0_control` | exact `g4` string — must be byte-identical to round 07 `g4` |
| 2 | `h1_lean` | **− `busy instrumentation, no empty space`** |
| 3 | `h2_maqam` | `h1` + `maqam, Middle Eastern scales` |
| 4 | `h3_orchestra` | `h1` + `Arabic orchestra` |
| 5 | `h4_tarab` | `h1` + `tarab` |
| 6 | `h5_poporch` | `h1` + `Arabic pop orchestra, maqam` |

Strings:

```
h1: Arabic instrumental cover, full band ensemble, layered arrangement,
    clear lead melody, continuous accompaniment, rich full production,
    no vocals, no singing, no vocal chops

h2: h1 + "maqam, Middle Eastern scales"   (after rich full production)

h3: Arabic instrumental cover, Arabic orchestra, full band ensemble, ...

h4: Arabic instrumental cover, tarab, full band ensemble, ...

h5: Arabic instrumental cover, Arabic pop orchestra, maqam, full band ensemble, ...
```

## 5. Run

```bash
cd /content/arabmaqrock && git pull
python3 generate.py manifests/fadhl_shaker_instrumental_09_genre_tags.json \
  --label fadhl_inst_09_genre
```

6 takes, ≈39 min on a T4, ≈25 min on an L4.

`h0_control` with the same seed and score as round 07 must hash equal to
`g4_arabic_20261106.wav`; if it does not, the pipeline drifted and the whole
sweep is unreadable.

## 6. Reading the result

One seed per variant, so a clear win is real but a tie is not. If two variants
tie on feel, rerun those two with a second seed before choosing.

The end state is still one line in `defaults.style`, then the ten-song batch from
round 08 rebuilt with that line.

## 7. Verdict — `h2_maqam` wins

Run: `gs://akbar-december-2024-backup/arabmaqamrock/runs/20261108-054320_fadhl_inst_09_genre/`
(6/6 takes, `Exit status: 0`). Chosen by ear: **`h2_maqam`**.

Control integrity: `h0_control_20261106.wav` md5
`XpfDHmV39iJg8dRnajiUMg==` = round 07 `g4_arabic_20261106.wav`, byte for byte.
The sweep is readable.

| take | dur | LUFS | crest | occ% | 20–80 | 200–500 | 1.2–3k | 3–6k | 6–10k |
|---|---|---|---|---|---|---|---|---|---|
| `h0_control` | 259.0 | −11.90 | 14.54 | 94.8 | −8.2 | −11.1 | −16.3 | −21.4 | −27.5 |
| `h1_lean` | 260.3 | −12.48 | 13.77 | **85.2** | −3.2 | −11.2 | −24.8 | −27.9 | −29.5 |
| **`h2_maqam`** | **266.2** | −13.83 | **15.52** | 97.4 | −4.5 | −11.2 | **−13.9** | −24.5 | −28.8 |
| `h3_orchestra` | 269.9 | −19.47 | 19.72 | 98.3 | −7.1 | −10.8 | −18.9 | −28.1 | **−34.2** |
| `h4_tarab` | 262.2 | −16.07 | 18.97 | 99.3 | **−11.1** | −10.8 | −17.3 | −26.1 | −32.3 |
| `h5_poporch` | 259.6 | −13.02 | 14.82 | 89.3 | −4.8 | **−13.0** | −18.4 | −24.8 | −28.6 |

Readings:

- **The density words did matter, but not the way we assumed.** Removing them
  alone (`h1`) dropped frame occupancy 94.8 → 85.2 % *and* pulled 1.2–3 kHz down
  8.5 dB: without a density instruction the model leaves holes and loses presence.
  The words were not the boxiness; the boxiness came from `g2`'s dark mid.
- **`h2` buys density back with `maqam, Middle Eastern scales` instead.** It is
  the only take that is simultaneously bassier than the control (−4.5 vs −8.2 dB
  at 20–80 Hz), brighter than it at 1.2–3 kHz (−13.9 vs −16.3), has the best
  crest (15.52), and runs 266.2 s — closest to the score's 269.7 s. Density
  without the squashed, dull signature.
- `h3_orchestra` is 7.6 dB quieter, very dynamic, and loses the top octave
  (6–10 k = −34.2): a bigger, softer orchestra, not a better one.
- `h4_tarab` has the weakest bass of the batch (−11.1) and a boosted low-mid —
  the tarab reading is real but it thins the low end.
- `h5_poporch` is thin in 200–500 Hz (−13.0) and leaves the most holes (89.3 %),
  which is the opposite of what "pop orchestra" was supposed to add.

## 8. The adopted line

```json
"defaults": {
  "style": "Arabic instrumental cover, full band ensemble, layered arrangement, clear lead melody, continuous accompaniment, rich full production, maqam, Middle Eastern scales, no vocals, no singing, no vocal chops",
  "cot": "full",
  "lora": "instrumental",
  "lora_ar_scale": 1.0,
  "lora_nar_scale": 0.0,
  "trigger": false
}
```

Two changes from `g4`: the density pair is gone, and the modal pair is in. Both
were predicted by the user's ear before the numbers agreed.

**Open question left by this result:** `maqam` is generic. If the score-derived
version (Arabic maqam name + its Western scale name, per `docs/base-prompt.md`)
beats the generic pair, it belongs in the same slot — and it is batch-safe
because the ABC carries the key.

**Not in this sweep, and not ever:** the LoRA trigger `arabmaqamrock`. Every
training caption carried it, and all instrumental rounds so far ran with
`trigger: false` — that is now a product decision, not an untested lever.

The trigger's meaning in the training corpus is project-specific and vocal:

```
arabmaqamrock: The music feels like a grand, solemn symphonic-rock ballad driven
by a commanding, deeply resonant Arabic male vocal ...
```

The end product is ~500 instrumental tracks of ~500 Arabic songs that have
nothing to do with `arabmaqamrock`, so the word must never reach the caption.
It stays `trigger: false` in every manifest of this corpus.

Consequence: the idiom cannot be borrowed from the trigger. It has to live in
the style string (`Arabic` + the genre tag) and in the ABC score — which is
exactly what this round is measuring.
