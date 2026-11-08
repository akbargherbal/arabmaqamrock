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
