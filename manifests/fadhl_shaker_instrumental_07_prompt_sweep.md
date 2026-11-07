# حبيتك — generic prompt sweep (round 07)

**Constraint:** this prompt must work for ~500 songs, so it must not name
instruments, tempo, or key. The ABC score already carries melody, chords, tempo,
key and sections. The style string only says **what kind of production** we
want; the score constrains everything else.

The prompt therefore uses only generic production tags:

```
instrumental cover, full band arrangement, clear lead melody,
continuous accompaniment, rich full production, no vocals, no singing
```

No `oud`, no `darbuka`, no `101 BPM`, no `G minor`. If a song needs a specific
texture, that belongs in the score, not the prompt.

## Where it lives

One string in `defaults.style` applies to every song in a manifest:

```json
"defaults": {
  "style": "instrumental cover, full band arrangement, ...",
  "cot": "full",
  "lora": "instrumental",
  "lora_ar_scale": 1.0,
  "lora_nar_scale": 0.0,
  "trigger": false
}
```

A per-song `style` still overrides it for exceptions. That is the whole
"hardcoding" surface: one editable line.

## Variants

Same score, seed `20261106`, `cot=full`, `cap=6993`, AR scale 1.0, NAR off.
Only the style (and `g5`'s lyrics) changes.

| # | Name | Chars | Idea |
|---|---|---|---|
| 1 | `g0_bare` | 23 | absolute minimum: `instrumental, no vocals` |
| 2 | `g1_cover` | 131 | generic cover, no density words |
| 3 | `g2_dense` | 203 | + layered / busy / no empty space |
| 4 | `g3_prose` | 1343 | the round-04/05 prose control |
| 5 | `g4_arabic` | 210 | `g2` + the corpus-level word `Arabic` |
| 6 | `g5_sections` | 203 | `g2` + score-derived section tags |

`g5` lyrics (generated from the score's sections, `interlude` → `instrumental`):

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

Six takes, ~39 min on a T4.

## Decision

| Result | Decision |
|---|---|
| `g1`/`g2` as good as `g3` (prose) | drop the prose forever; use the generic string in `defaults` |
| `g1` ≈ `g2` | use `g1`; density words add nothing |
| `g2` > `g1` | keep `layered / busy / no empty space` |
| `g4` > `g2` | add the single word `Arabic` (still generic) |
| `g0` already good | the score does the work; the style can stay nearly empty |
| `g5` > `g2` | auto-generate section tags for all 500 scores |

Whatever wins is one line in `defaults.style`, and the 500-song manifest only
needs `name` + `score` + `lyrics: "[instrumental]"` per song.
