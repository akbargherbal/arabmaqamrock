# Suno's generation controls, and what ArabMaqamRock can and cannot borrow

**Date:** 2026-10-30
**Author:** agent session (DeepSeek V4.1 Flash) at Akbar's request
**Subject:** a hands-on read of Suno's v6 *Create* surface — every knob, what it
actually sends, and a mapping against this repo's controls.
**Status:** findings. §7.1–7.2 (per-song control keys + resolved-control
recording) were implemented on 2026-10-30; the rest of §7 is parked as written.
Two sample clips were generated and left in the account for listening.

---

## 0. TL;DR

1. The Advanced panel exposes **seven** controls (vocal gender, duration, max
   mode, weirdness, style influence, variety, personalize) on top of styles,
   lyrics, title and the model picker. Only three are continuous sliders, and
   the only "hard" musical control is **duration** — and even that is a target,
   not a guarantee. Exclude-styles exists in the payload but never appeared on
   screen.
2. Under the hood everything reduces to one POST to `/api/generate/v2-web/`:
   `tags` + `prompt` + `negative_tags` + a `metadata.control_sliders` object of
   three 0–1 fractions plus an integer `aug_creativity`. **There is no seed**,
   no key, no tempo, no meter, no melody input, no negative prompt in the UI we
   saw.
3. The style string you type is **not** the string the model sees. Both test
   takes came back with a paraphrased `metadata.tags` (added "hushed close-mic
   verses", "doubled hooks", "roomy unprocessed vocals", …), and the two
   paraphrases differed from each other. This is the single most important
   finding for our project.
4. The four controls that transfer cleanly to `arabmaqamrock` are: **style text**,
   **lyrics**, **take count / variability**, and **duration**. The two that map
   onto knobs we already have under different names are **style influence → CFG
   (`guidance_scale`)** and **weirdness → `semantic_temperature`**. The rest
   (max mode, audio influence, personalize, exclude-styles) have **no honest
   analogue** in YuE2 and should not be faked.
5. Suno's output is fast (~35 s for a 3.7-minute song) but lossy (~130 kbps
   m4a/opus on the free tier) and its Terms forbid both scraping and *training
   other models* on the output. That constraint, not the UI, is the hard ceiling
   on using Suno as a data source.

---

## 1. Method

- Read the app through Chrome's DevTools endpoint on `127.0.0.1:9222`, in a
  **second tab** (`/create`), so the tab that was already open was left alone.
- Inspected the DOM, the client bundle (149 chunks, fetched read-only), and the
  i18n bundle `https://suno.com/locales/en/create.json` for verbatim UI strings.
- Generated **one batch (two clips)** with a real UI flow: click → type → Create.
  This matters: the settings path was the product's, not a hand-built API call.
- **The trigger word `arabmaqamrock` was deliberately not used anywhere.**
  It appears zero times in the submitted style, the lyrics, the title, and the
  stored clip metadata.
- Account: `complexvideos3915`, free tier. Model: `v6-mini` (`chirp-goose`).
- No proxy, no headless mode, no reload loop. One navigation per page, short
  pauses between actions.

### Test inputs

| | |
|---|---|
| Style | `prompts/Hijaz_style.txt` with the trigger word stripped — 780 chars |
| Lyrics | `prompts/example_lyrics.txt`, as-is — 1,318 chars, 585 Arabic letters |
| Title | `Hijaz Test 01` |
| Mode | Advanced, v6-mini, duration Auto, max mode Off, weirdness 50, style influence 50, variety Normal, personalize Off |
| Trigger word | **not used** |

### Result

| clip | id | duration | size | bitrate | model | status |
|---|---|---|---|---|---|---|
| A | `26f94477-…-f6b0f5197e1d` | 3:42.6 (222.64 s) | 3,648,290 B | ~131 kbps | chirp-goose | complete |
| B | `56cfd7ff-…-5547de524ace` | 3:32.8 (212.76 s) | 3,424,345 B | ~129 kbps | chirp-goose | complete |

Both were created at `17:40:50.920Z` and finished at `17:41:27.364Z` and
`17:41:23.590Z` — **32–36 s** for two full-length songs. They are private
(`is_public: false`) and sit in *My Workspace* for auditioning.

I did **not** listen to them (text-only model). Everything below about audio
content is structural, not a quality judgement.

---

## 2. The control surface as shipped

### 2.1 Inputs

| Control | Limit | Notes |
|---|---|---|
| Lyrics | 5,000 chars (counter "0 of 5000") | rich-text box; `[Verse]`-style section tags accepted; empty ⇒ instrumental |
| Styles | 1,000 chars (counter "0/1000") | free text, comma/period separated, a suggestion chip row sits under it |
| Song title | optional | used as the filename/display name |
| Audio / Voice / Image | uploads | "Browse, upload, or record audio", "Add Voice", "Add an image to your creation" |
| Save to… | workspace | output library target |

### 2.2 Advanced options (the "More Options" card)

| Knob | Type / range | Default | What it does (product wording) |
|---|---|---|---|
| **Vocal Gender** | Male / Female / unset | unset | "Change the gender of the generated vocals" |
| **Duration** | Auto, or Custom **10 s – 6 min** | Auto | "Desired song length, 10 seconds to 6 minutes." |
| **Max Mode** | Off / On | Off | "Uses more compute to maximize consistency throughout the song. **Costs 2× credits per song.**" |
| **Weirdness** | slider 0–100 | 50 ("Expected results") | "Turn it up for wild, unexpected results" |
| **Style Influence** | slider 0–100 | 50 ("Moderate") | "Turn it up to match your style description" |
| **Variety** | stepped slider 0–4 | 1 ("Normal") | changes how much the takes are allowed to drift from the style |
| **Personalize** | Off / On | Off | "Make Variety match your taste"; disabled until Variety is up ("Turn up Variety to use Personalize") |

Slider zone labels (verbatim, from the client constants):

- Weirdness: `0 Safe zone` · `0.33 Expected results` · `0.66 Experimental results` · `0.8 Chaos mode`
- Style Influence: `0 Loose` · `0.33 Moderate` · `0.67 Strong`
- Audio Influence (only with a reference): `0 Loose` · `0.33 Moderate` · `0.67 Strong`
- Variety: `0 Exact style` · `1 Balanced variety` · `2 Distinct styles` · `3 Bold exploration` · `4 Unreasonably varied`
  (value text: Off / Normal / High / Extra / Max)

Variety tooltips, verbatim:

> Off — "Clips use the same style."
> Normal — "Clips have slight style variation."
> High — "Clips have high style variation."
> Extra — "Clips have very high style variation."
> Max — "Clips may differ significantly from your style input."

### 2.3 Present in the payload but not in our UI

These exist in the client and are sent when their conditions are met; they were
not visible for this account/model:

- **Exclude styles** → `negative_tags`. The string and the input exist in the
  bundle; it did not render in the v6-mini Advanced card we saw.
- **Audio Influence** → enabled only when a reference exists (uploaded audio or
  a Persona). Default 25 (not 50).
- **Mumble mode** → placeholder vocals without lyrics (feature-flag gated).
- **Persona** → a saved voice/style profile; also the only way to get
  `audio_influence` without uploading audio.
- **Stems / stem tasks** → separate generation tasks (`stem_task`,
  `stem_type_group_name`); `has_stem: false` on our clips.

### 2.4 Models

| Model | Tier | Product copy |
|---|---|---|
| `v6` (`chirp-hawk` in the client's model map) | Pro | "Powerful. Versatile. Refined. Our best model yet." |
| `v6-wild` (hawk family, exact id not verified) | Pro | "Best for experimental ideas." |
| `v6-mini` (`chirp-goose`, confirmed in clip metadata) | free | "A free, more efficient version of premium v6 models." |

The bundle still knows the older families (`chirp-v3-5-tau`, `chirp-auk`,
`chirp-bluejay`, `chirp-crow`, `chirp-fenix`, `chirp-carp`), but the picker only
offers the v6 family.

---

## 3. Under the hood: what one Create actually sends

The body is assembled in `1x45npig0ngk1.js`. Skeleton, with our run's values:

```jsonc
{
  "project_id": null,
  "token": null,
  "generation_type": "TEXT",
  "title": "Hijaz Test 01",
  "tags": "<the 780-char Hijaz style>",
  "negative_tags": "",
  "prompt": "<the 1,318-char lyrics>",
  "make_instrumental": false,
  "mv": "chirp-goose",
  "duration": null,              // seconds when Custom
  "metadata": {
    "create_mode": "custom",
    "is_max_mode": false,
    "is_mumble": false,
    "disable_volume_normalization": false,
    "control_sliders": { "aug_creativity": 1 }
  }
}
```

Rules visible in the client code:

- `weirdness_constraint = weirdness / 100`, `style_weight = styleInfluence / 100`,
  `audio_weight = audioInfluence / 100` — all 0..1.
- **Defaults are omitted, not sent**: at 50/50/25 the three fractions are dropped
  from `control_sliders`. That is why our stored clips only contain
  `aug_creativity: 1`. (Verified live: the clip metadata has exactly that.)
- `aug_creativity` is the Variety slider, an integer 0–4, and it is sent even at
  its default.
- `vocal_gender` is `"m"`/`"f"` inside `metadata`, absent when unset.
- `duration` is seconds at top level; `gen_duration` is the same value echoed in
  clip metadata for re-hydration.
- **No `seed` field exists anywhere in the payload or the UI.** A clip can be
  re-generated only as a "cover"/"extend", never as an exact repeat.

---

## 4. The style rewriter is the headline finding

What we submitted (first 180 chars):

> Symphonic cinematic orchestral ballad, hymn-like grand concert hall acoustics,
> heavy rock instrumentation, stately groove, 110 BPM. Maqam Hijaz. deep male
> vocals, mixed-voice chest-head resonance blend on sustained notes, …

What clip A stores and displays as its styles:

> Symphonic cinematic orchestral ballad, hymn-like grand concert hall acoustics,
> Audiophile recording, punchy centered mix, bright presence, clean transients,
> large dynamic range, natural breath room between phrases; **forward vocals pull
> instrumentation down on sustained phrases, then the band re-enters; deep male
> vocals, hushed close-mic verses, doubled hooks**, full-voiced commanding
> presence, mixed-voice chest-head resonance blend on sustained notes, …
> Distorted electric guitars, orchestral strings, weighted acoustic rock drums,
> tight rhythm section; **stately 110 BPM groove**, Poignant, Chivalric, Emotional.

Word-level diff against the input:

| clip | added | dropped |
|---|---|---|
| A | close-mic, doubled, hooks, hushed, pull, verses | heavy, pulling, lines, mood, in |
| B | at, back, choruses, clipped, endings, melismas, phrase, pull, rhythmic, roomy, staccato, unprocessed, verses | blend, down, heavy, instrumentation, phrase-ending, phrasing, pulling, sustains, then, with, mood, in |

Three consequences:

1. The style text is an **input to a rewriter**, not a spec. "Heavy rock
   instrumentation" survived as a concept in A and was dropped outright in B,
   while B gained "roomy unprocessed vocals" — a production instruction nobody
   asked for.
2. The rewrite is **stochastic per take**. The same submit produced two
   different styles. That is a hidden variable the user cannot control and
   cannot see unless they open "Show full styles" on each clip.
3. The **original string is not stored** on the clip. The only place it survives
   is the browser form. Provenance is lost server-side.

For a maqam project this is exactly backwards: the maqam name is the one token
that must survive verbatim, and the rewriter is free to paraphrase everything
around it. In our pipeline the style file is already the ground truth and is
archived under `prompts/`; Suno cannot offer that.

---

## 5. Mapping to ArabMaqamRock

Our controls, for reference: `style`/`style_file`, `lyrics`/`lyrics_file`,
`seed`/`seeds`/`repeat`, `cap`/`quantile` (from `duration_cap.py`), `lora`
(alias into a `loras` map), `abc_file`/`score` + `cot` (`off|melody|full`),
the trigger word, and `EXTRA_REQUEST_OPTS` (`guidance_scale`,
`semantic_temperature`, `semantic_repetition_penalty`), plus `run_one.sh`'s
`LORA_AR_SCALE` / `LORA_NAR_SCALE`.

| Suno control | What it really is | Our equivalent | Verdict |
|---|---|---|---|
| **Styles** (1,000 ch) | text → rewritten per take | `style` / `style_file`, archived verbatim | **Transfers, with our version strictly better** (no rewrite, no cap, provenance) |
| **Lyrics** (5,000 ch) | text with section tags | `lyrics` / `lyrics_file` | Transfers 1:1 |
| **Exclude styles** | `negative_tags` | none (YuE2 has no negative prompt) | **No honest analogue** — do not add a fake field |
| **Vocal gender** | `vocal_gender: m/f` | style text ("deep male vocals") | Partial; a caption token, not a hard control |
| **Duration** | target 10–360 s | `cap` / `quantile` → `semantic_max_tokens` | **Transfers as a cap**, not as a length |
| **Max mode** | 2× compute, "consistency" | `cot=full` + score, longer cap, best-of-N | **Analogue only via a quality pass** (parked, §7.6) |
| **Weirdness** 0–100 | sampling entropy | `semantic_temperature` (and `guidance_scale`) | **Transfers as a preset**, not as one knob |
| **Style influence** 0–100 | adherence to styles | `guidance_scale` most directly; `LORA_*_SCALE` secondarily | **Transfers**, but must be labelled honestly |
| **Audio influence** | reference audio / Persona | `lora_ar_scale` / `lora_nar_scale` is the nearest lever; no audio prompt (§7.7) | **Does not transfer as a knob**; the adapter is the mechanism |
| **Variety** 0–4 | how far takes may drift | `repeat` + `seeds` (exact) — Suno instead *rewrites the style* | **Transfers as seed sweeps**, with a different mechanism |
| **Personalize** | "Variety matches your taste" | listening rubric in `eval/` | **Transfers as a reranker**, not a generation knob |
| **Model picker** | v6 / v6-wild / v6-mini | LoRA alias (`v3`, `quran`) + base model | Partial; ours is per-adapter, not per-quality-tier |
| **Seed** | *does not exist* | `seed` / `seeds`, recorded in `batch_manifest.json` | **We are strictly ahead.** This is our main reproducibility claim |
| **Take count** | always 2 per submit | `repeat: N` | **We are ahead** |
| **Reuse prompt** | copies style/lyrics into the form | `--out-dir`, manifests, `input.json` copy | We are ahead (exact, versioned) |
| **Cover / Extend / Reverse / Adjust speed** | re-render or DSP on a clip | ABC edit + `cot` re-render | Different: ours is symbolic, theirs is blind re-roll |
| **Stems** | paid separation | `has_stem` false on free; SheetSage2 transcription instead | Different tool for a different job |
| **Melody / MIDI input** | none | `abc_file` + `cot=melody|full` | **Our unique capability** |
| **Output** | ~130 kbps m4a/opus, WAV gated | 16-bit WAV | We are ahead |
| **Latency / cost** | ~35 s/song, credits | ~6–7 min/song on a T4, GPU time | Suno wins on speed; we win on ownership |

### The one-line summary of the mapping

Suno gives you **fast, pretty, non-reproducible** takes with a rewriter in the
middle. ArabMaqamRock gives you **slow, reproducible, symbolically editable**
takes with no rewriter. Almost every Suno knob is either a soft prior over a
black box or a credit meter. We already own the axes that matter for research:
seed, score, adapter scale, and exact prompt capture.

---

## 6. Challenges

### 6.1 Hard challenges (cannot be engineered around)

1. **No seed ⇒ no A/B.** Any "Suno vs ours" comparison confounds model,
   rewriter, and luck. Two takes per submit is the entire sample.
2. **Silent style rewriting.** The variable under test (the style prompt) is
   mutated before inference, differently per take. You cannot attribute a
   difference to your edit.
3. **No musical controls.** No key, tempo, meter, maqam, mode, or melody. "Maqam
   Hijaz" is a suggestion that survives or not, depending on the rewriter.
4. **Model churn.** v6 arrived with no version pin in the API. Whatever you
   measure today is gone at the next silent update.
5. **Terms of Service.** Two clauses matter (quoted in §8): no scraping/robots,
   and no using output to "train other artificial intelligence and machine
   learning models". A pipeline that harvests Suno clips for a LoRA is exactly
   the prohibited case.
6. **Free-tier output is non-commercial and lossy.** 130 kbps opus is a poor
   source for timbre training compared with WAV; WAV/`audio_url` is gated
   (`/api/forbidden` without entitlement).

### 6.2 Soft challenges (annoying but workable)

1. **Opacity of gating.** Which knob appears depends on plan, model, feature
   flags, and whether references exist. Two accounts can see different UIs.
2. **Credits as a control dimension.** Max Mode doubles cost; batch size is
   fixed at 2; "Earn Credits" and "Listen and Rank" in Labs turn evaluation into
   a currency grind.
3. **Bot defences.** Cloudflare Turnstile is loaded on the page. Automating the
   UI is both detectable and, per §8, prohibited.
4. **No batch API for these controls.** The web client is the only surface.
5. **Durations are short.** 3.5 min for 1,318 chars / 6 sections. Our own cap
   model would have allowed 290 s at q=0.95 for the same lyrics; Suno delivered
   213–223 s, i.e. it compresses rather than stretches.
6. **Metadata is lossy.** `display_tags` collapses everything to three words
   (`symphonic, cinematic, ballad`), and `control_sliders` omits defaults, so a
   clip record cannot reconstruct the form that made it.

---

## 7. Opportunities, filtered to **control depth**

Filter: additive manifest fields only; absent key ⇒ byte-identical behaviour;
each item ≤ ~75 lines; no GPU sweep needed to land. Knob-by-knob semantics,
with the code paths they come from, are in **Appendix D**. `duration` is **not** on this
list — the cap is a fitted upper bound from the training corpus (§7.6), and a
seconds field would trade a measured quantity for a guess.

| # | Change | Effort | Impact | Lives in |
|---|---|---|---|---|
| 7.1 | Flat per-song control keys (`guidance_scale`, `semantic_*`, `abc_*`, `lora_*_scale`) | ~75 lines | **High** — the real control surface, per track instead of per batch | `generate.py`, `run_one.sh`, README |
| 7.2 | Record resolved controls in sidecar/manifest, print in `--dry-run` | ~15 lines | **High** — without it, 7.1 makes runs less reproducible | `generate.py` |
| 7.3 | `--from-run <dir>` to clone a run's exact settings | ~25 lines | Medium — A/B becomes one flag | `generate.py` |
| 7.4 | One-line provenance note in `MODEL_CARD.md` | ~5 lines | Medium (legal, not technical) | `MODEL_CARD.md` |

### 7.1 Per-song control keys

**Implemented 2026-10-30** in `generate.py` (allowlist below, except
`semantic_min_tokens`, which stayed out); covered by
`tests/test_controls.py` and exercised by `manifests/controls.example.json`.

Everything interesting already reaches `audio.cpp` through
`--request-option`; the only problem is that it arrives via one environment
variable, so **every track in a batch shares it**. Make the same options
first-class manifest fields, using the existing flat schema and the existing
precedence (song > CLI > `defaults` > built-in), so there is no new merge rule to
learn:

```json
"defaults": { "guidance_scale": 1.5, "semantic_temperature": 0.9 },
"songs": [
  { "name": "tight",  "guidance_scale": 2.0 },
  { "name": "wilder", "guidance_scale": 1.0, "semantic_temperature": 1.15 },
  { "name": "half_style", "lora_ar_scale": 0.7, "lora_nar_scale": 0.5 }
]
```

Allowlist for v1 — deliberately small, every key already used somewhere in this
repo:

| Key | Default (cot=off / melody·full) | Binary limit | What it actually controls |
|---|---|---|---|
| `guidance_scale` | 1.01 / **1.0 (= off)** | 0–20 | text adherence (CFG) over **tags + lyrics together**. Not ABC, not timbre (§D) |
| `semantic_temperature` | 1.0 | 0–5 (0 = greedy) | randomness of the vocal/melody token stream |
| `semantic_top_p` | 0.95 | (0, 1] | nucleus width |
| `semantic_top_k` | 100 | ≥ 1 | top-k width |
| `semantic_repetition_penalty` | 1.2 | > 0 | penalty on tokens seen in the last `penalty_window` (50) |
| `num_inference_steps` | 8 | ≥ 1 | NAR flow-matching steps; audio detail, not adherence |
| `abc_temperature` | 0.7 | 0–5 | the **plan** stage only (see §D.2) |
| `abc_top_p` / `abc_top_k` | 0.9 / 30 | (0,1] / ≥1 | same |
| `abc_repetition_penalty` | 1.005 | > 0 | same |
| `abc_min_tokens` / `abc_max_tokens` | 32 / 4096 | ≥0 / ≥min | same |
| `lora_ar_scale`, `lora_nar_scale` | 1.0 | finite (we clamp 0–1.5) | weight blend per expert; the "how much adapter" dial (§D.10) |

Before writing the parser, run `strings "$BIN" | grep -E
'guidance_scale|semantic_top_p|abc_temperature|num_inference_steps'`: this repo
has already been burned once by an option the binary silently ignored
(`semantic_prefix`, see `docs/happy_accidents/.../HANDOFF.md`). Anything missing
from `strings` does not go in the allowlist.

Excluded on purpose from v1:

- `style`, `cot`, `semantic_max_tokens`, `abc_file` — already first-class fields;
  duplicating them would create two sources of truth.
- `semantic_prefix` / `semantic_prefix_file` — the strongest lock (exact
  semantic frames), but the shipped binary is not guaranteed to support it and
  **silently ignores it** when it does not (`docs/transcription.md`). Add it only
  behind a preflight `strings "$BIN" | grep semantic_prefix` check.
- `semantic_min_tokens` — token surgery, not a knob.

Rules:

- Same precedence as every other field: song value, else `defaults`, else the
  binary's own default. No implicit values, no preset layer.
- **The control keys and `EXTRA_REQUEST_OPTS` are mutually exclusive** (hard
  error naming the offending key). Same reasoning as `cap` xor `quantile`: no
  silent precedence between two sources of the same setting. A manifest without
  control keys keeps using the env var exactly as today. `lora_*_scale` follows
  the same rule against `LORA_AR_SCALE` / `LORA_NAR_SCALE`.
- Unknown key, wrong type, or out-of-range value fails in `--dry-run` before any
  GPU work.
- `abc_*` keys on a song with an external `abc_file` are a **hard error**, not a
  silent no-op: the docs already say they are ignored there.
- Emitted as `env["EXTRA_REQUEST_OPTS"] = "k=v k=v"` per track in `run_batch`
  (values are numeric, so the existing whitespace split in `run_one.sh` is
  safe); `lora_*_scale` go to `LORA_AR_SCALE` / `LORA_NAR_SCALE`.

Acceptance (met): a three-song manifest with three different control sets
produces three different `EXTRA_REQUEST_OPTS` strings in the sidecars;
`--dry-run` prints the resolved values per track; a song with both a control key
and a non-empty `EXTRA_REQUEST_OPTS` fails before any GPU work.

### 7.2 Make the resolved controls visible

**Implemented 2026-10-30:** `controls` and `lora_scale` are written to the
sidecar and to each `tracks[]` entry of `batch_manifest.json`, and `--dry-run`
prints a compact `controls` column (plus the inherited `EXTRA_REQUEST_OPTS` when
no control keys are set).

The sidecar records style/lyrics/ABC/LoRA/model/GPU hashes but **not** the
sampler options that were actually passed. That is the gap that would make 7.1
net-negative for reproducibility.

- `sidecar_fields()`: add `controls` (resolved dict), `lora_scale`, and
  `request_opts_env` (the inherited `EXTRA_REQUEST_OPTS`, or null when the
  manifest set control keys).
- `batch_manifest.json`: `controls` and `lora_scale` in each `tracks[]` entry
  (the file has a `tracks` list and no `defaults` block).
- `--dry-run`: one compact column per track, e.g. `g=1.5 t=0.9` or
  `ar=0.7 nar=0.5`.
- Preflight: when no control keys are set, print the inherited
  `EXTRA_REQUEST_OPTS` once, so an env-driven batch is not invisible either.

~15 lines.

### 7.3 `--from-run <dir>`

`input.json` is copied into every run, so the data exists. The obstacle is path
resolution: `base_dir` is relative to the manifest that contains it, and after
copying it points at the wrong place.

- The resolved `base_dir` is not recorded today; add it to
  `batch_manifest.json` (one line in `materialize()`), and for older runs fall
  back to the directory of the recorded `input_file`.
- Read `out/<run>/input.json`, rewrite `base_dir` to that absolute directory,
  and feed it through the normal resolver.
- Optional `--set name=value` (repeatable) for the one field under test.
- Refuse if the run's `batch_manifest.json` hashes no longer match disk.

~25 lines. The zero-code alternative is to keep each experiment manifest under
`manifests/` — but seeds and caps then get copied by hand, which is the mistake
this prevents.

### 7.4 Zero-code items

- `MODEL_CARD.md`: one paragraph on where the training audio came from and that
  Suno's Terms forbid using its output to train other models (§8).
- `README.md`: one sentence that `EXTRA_REQUEST_OPTS` is **batch-global** — it
  currently reads like a per-run knob.

### 7.5 Regression check against `manifests/`

Baseline (all ten manifests, `--dry-run`, today):

| manifest | tracks |
|---|---:|
| `04.json` | 3 |
| `1332683623_baghdad_moon_formatted.json` | 3 |
| `baghdad_moon_formatted.json` | 2 |
| `baghdad_moon_spec.json` | 6 |
| `moon_edit.json` | 9 |
| `moon_edit2.json` | 6 |
| `pragmatic-grasshopper_ibn_zuraiq_formatted.json` | 12 |
| `songs.example.json` | 2 |
| `spiritual-potato.json` | 6 |
| `tarab_test_01.json` | 5 |

What the files actually use: song keys `name/lyrics/style/score/cot/seed/cap`;
defaults keys `quantile/repeat/style/style_file/cot`. **No manifest uses any of
the proposed control keys, `duration`, `preset`, `seeds`, or song-level
`repeat`.** Validation is strict but additive (`_unknown_keys`), so new accepted
keys cannot make an existing file fail.

| item | risk | why |
|---|---|---|
| 7.1 control keys | **None** | opt-in; absent ⇒ `EXTRA_REQUEST_OPTS` and `LORA_*_SCALE` pass through untouched |
| 7.2 sidecar/manifest fields | **None** | `batch_manifest.json` is only *hashed* by `transcribe.py` and `tests/test_transcribe.py`, never parsed by key |
| 7.3 `--from-run` | **None** | new flag, nothing calls it |
| 7.4 docs | **None** | text |

Two traps worth writing down:

1. **`songs.example.json` has no `defaults.repeat`** (built-in default = 1),
   while every other manifest sets it explicitly. Verified: adding
   `defaults.repeat: 2` takes that file from 2 tracks to 3 — the `seed: 7` song
   stays one take because the seed/repeat conflict check only fires when
   `repeat` is written at song level, while the random-seed song quietly gains a
   take. This is why nothing in §7.1–7.2 may touch take counts.
2. **`songs.example.json` already mixes `defaults.quantile` with a song-level
   `cap`.** Legal today (song wins). Any new conflict check must be evaluated on
   the song's own keys, as `_cap_settings` does, not on a merged dict.

A third, quieter point: control keys must not default to any value. "Absent" has
to mean "pass nothing", exactly as today. The moment `normal`-style defaults get
filled in, every existing take would change on re-render while claiming to be
neutral.

Acceptance for the PR: re-run the ten dry-runs and diff the track counts (must be
identical); render one track from `songs.example.json` with and without the new
code and compare WAV hashes (must be identical when no control keys are set).

### 7.6 Parked on purpose

| Idea | Why not now |
|---|---|
| `duration` in seconds | The cap is a quantile fit on the LoRA's training corpus (`duration_cap.py`), i.e. a measured upper bound, not a preference. A seconds field would replace a studied quantity with a guess. Not a priority. |
| `preset` (tight/normal/wild) | Pure sugar over the control keys; adds a vocabulary layer and a second place to hide defaults. Add only if the raw keys prove too verbose in practice. |
| LLM style rewriter | Explicitly not wanted; also recreates Suno's provenance problem. |
| Best-of-N verifier | Medium-high effort: needs a scoring harness and listener time before it means anything. |
| Exclude-styles / negative prompt | No YuE2 mechanism. A field that changes nothing is worse than no field. |
| Max Mode as a flag | A compute/consistency trade-off we cannot honour as a switch; the honest version is best-of-N. |
| Personalize / taste model | Needs labels and a model; valuable later, not a ≤75-line change. |
| Edit-without-re-roll | Already possible via ABC + `cot`; the gap is packaging, a bigger design task. |

### 7.7 Can we do "Audio Influence"? (direct answer)

No — not in the way Suno means it. Suno's Audio Influence pulls the render toward
an uploaded reference audio or Persona; YuE2 has no audio-prompt, no
embedding-reference, and no in-context audio channel. The ABC score is often
mistaken for it, but it is **symbolic**: it fixes melody/chords/structure, and
its influence is structural, not timbral (see *Controlling ABC influence* in
`docs/transcription.md`).

Three things that *do* move the render toward a target, in order of strength:

| Lever | Moves | Cost |
|---|---|---|
| A LoRA trained on the target audio | timbre + style + phrasing | a training run; this is the real mechanism |
| `lora_ar_scale` / `lora_nar_scale` | how much of that adapter, split vocal vs rendered | free; §7.1 |
| `guidance_scale` | how hard the text style is pushed | free; §7.1 |

And one that moves it structurally: the ABC score plus `cot` — but that is a
different question from "make it sound like this reference".

## 8. Compliance and licensing (read before building anything on Suno)

Quoted from `https://suno.com/terms` (retrieved 2026-10-30):

> "…engage in or use any data mining, robots, scraping, or similar data
> gathering or extraction methods…"

> "…use the Services (and any Output or Voice Model) to create, develop or
> improve any competing products or services or to power, enable or train other
> artificial intelligence and machine learning models, tools or technologies…"

> "Free or Basic Tier Accounts: … you will only use such Outputs for your
> lawful, personal and non-commercial purposes."

> "… if you are a user of the Pro or Premier paid tier … Suno hereby assigns to
> you all of its right, title and interest in and to any Output …"

Implications for this repo:

- The README states the training data is "Suno-rendered audio". If that audio was
  collected at scale, it runs into both the scraping clause and the
  train-other-models clause. **This report is not legal advice**, but the risk is
  concrete and should be resolved before any further data collection.
- Free-tier output cannot be used commercially, regardless of what the LoRA
  licence says.
- Automating the UI (even gently, as done here) is fine for a one-off
  investigation; it is not a lawful basis for a harvesting pipeline.
- The weights remain CC-BY-NC-4.0 and the code MIT. Those two facts are
  independent of the Suno question and should stay separate in the docs.

**Recommendation:** stop treating Suno as a data source going forward; document
the provenance of the existing v3 data explicitly in `MODEL_CARD.md`; prefer
commissioned recordings, public-domain/CC material, or licensed library music
for the next adapter. If Suno is used again, use it only as a *reference
listening* tool with a paid account, and never as training input.

---

## 9. What I would do next (in order)

1. **Control keys + `lora_*_scale` + sidecar fields** (§7.1–7.2), in one PR.
   They share the resolver, the sidecar and `--dry-run`, so splitting them costs
   more than doing them together. Test: the ten dry-runs must be unchanged, then
   one smoke batch of three songs that differ only in control keys.
2. **`--from-run`** (§7.3), so that smoke batch can be repeated with one field
   changed.
3. **Two zero-code lines** (§7.4): provenance in `MODEL_CARD.md`, batch-scope
   note in `README.md`.
4. **Calibrate the ranges, not the feature.** One song, fixed seed:
   `guidance_scale` 1.0 / 1.5 / 2.0, then `semantic_temperature` 0.8 / 1.0 /
   1.2. Six renders tell us which values deserve to become documented defaults.
5. **Listen to the two Suno clips** and write the paragraph — not to copy the
   rewriter, but to decide whether "roomy unprocessed vocals"-style additions
   are something our style files should ever say.

Acceptance for 1–2: every control appears in `--dry-run` with its resolved
value; a run without control keys hashes identically to today; every run can be
replayed from `input.json` + `batch_manifest.json`; no knob changes behaviour
silently.

---

## Appendix A — verbatim strings used above

- Max mode: "Uses more compute to maximize consistency throughout the song.
  Costs 2x credits per song."
- Duration: "Desired song length, 10 seconds to 6 minutes."
- Weirdness: "Turn it up for wild, unexpected results."
- Style Influence: "Turn it up to match your style description."
- Audio Influence: "Turn it up to resemble your original audio or Persona."
- Personalize: "Make Variety match your taste" / "Turn up Variety to use
  Personalize."
- Vocal gender: "Change the gender of the generated vocals."

## Appendix B — stored clip record (clip A, trimmed)

```jsonc
{
  "id": "26f94477-d9de-41da-a328-f6b0f5197e1d",
  "title": "Hijaz Test 01",
  "model_name": "chirp-goose",
  "major_model_version": "v6-mini",
  "status": "complete",
  "is_public": false,
  "display_tags": "symphonic, cinematic, ballad",
  "metadata": {
    "duration": 222.64,
    "type": "gen",
    "make_instrumental": false,
    "is_mumble": false,
    "control_sliders": { "aug_creativity": 1 },
    "tags": "<746-char rewritten style>",
    "prompt": "<lyrics, unchanged>",
    "has_stem": false,
    "uses_latest_model": true
  },
  "media_urls": [
    { "content_type": "m4a-opus", "delivery": "progressive",
      "url": "https://d2lwuy8qc234o3.cloudfront.net/1/clip/26f9….m4a" }
  ],
  "audio_url": "https://studio-api.prod.suno.com/api/forbidden"
}
```

## Appendix C — limits of this investigation

- One account, free tier, one model (`v6-mini`), one batch of two clips.
- Slider → payload fractions for **non-default** values were read from the
  client bundle, not observed live (I generated at defaults to stay inside the
  "one or two clips" budget).
- The "Exclude styles", "Mumble", "Audio Influence" and "Stems" rows describe
  the bundle's capabilities, not what this account could see.
- No listening evaluation; no loudness, key, or maqam analysis of the clips.

## Appendix D — what each knob actually does (from the implementation)

Sources: the YuE2 reference package (`multimodal-art-projection/YuE`, `main` @
`55668d6b`, `src/yue2/protocol.py`, `sampling.py`, `pipeline.py`) and the runtime
we actually ship (`0xShug0/audio.cpp`, `main` @ `350670db`,
`src/models/yue2/{request.cpp,pipeline.cpp,ar_runtime.cpp,nar_runtime.cpp}`,
`src/models/yue2/types.cpp`, `include/engine/models/yue2/types.h`). Both
implementations agree; the C++ is a port of the Python.

### D.1 The four stages

| stage | what runs | user knobs that act here |
|---|---|---|
| 1. plan (optional) | same AR model writes an ABC score; only when `cot != off` **and** no external score | `abc_*` sampling only — **no CFG** (`ar->generate`, not `generate_cfg`) |
| 2. semantic (AR) | AR model writes the music-token stream | `guidance_scale`, `semantic_*`, `seed`, `semantic_prefix_file` |
| 3. NAR | flow-matching decoder renders latents, `num_inference_steps` ODE steps per chunk | `num_inference_steps`, `seed`, `nar_noise_file` |
| 4. VAE | latents → WAV | none |

The single most useful consequence: **`guidance_scale` acts in stage 2 only.** It
does not shape the ABC plan (stage 1 has no CFG) and it does not touch audio
texture (stage 3).

### D.2 `guidance_scale` (alias `cfg_scale`) — what exactly it steers

The positive prefix is the whole text block, not the style alone:

```
[EOD] INSTRUCTIONS[cot] "\n[Tags]\n" <style> "\n[Lyrics]\n" <lyrics> "\n" [+ ABC tokens]
```

The negative prefix is the generic instruction for that CoT mode, with **no**
tags and **no** lyrics:

```
[EOD] INSTRUCTIONS[cot] [+ the exact same ABC tokens, if cot != off]
```

CFG then blends the two logit streams:

```
logits = negative + guidance_scale * (positive - negative)
```

(Reference: `protocol.py::SongRequest.text`, `token_prefixes`,
`negative_prefix`; C++: `pipeline.cpp::request_text`, `negative_prefix`, and
`ar_runtime.cpp::generate_cfg`.)

So, precisely:

- It controls adherence to **tags *and* lyrics together**, relative to a generic
  "generate music from the given conditions" instruction. There is no knob that
  pushes the style without also pushing the lyrics.
- It does **not** steer the ABC when `cot != off`: the ABC ids are identical in
  both branches, so the contrast is text-only. The ABC's grip comes from being in
  the prefix, not from CFG.
- With an external score, raising it can move *away* from the score's implied
  harmony when the style text conflicts with it (already documented in
  `docs/transcription.md`).
- Default is **1.0 for `cot=melody|full` — i.e. CFG is off**. At exactly 1.0 the
  runtime calls `generate()` with one branch, not `generate_cfg()`. The 1.01
  default for `cot=off` is a hair above 1, effectively "almost off".
  **Therefore every scored manifest in `manifests/` runs with CFG disabled
  today.** Adding `guidance_scale` to one is not a nudge; it turns CFG on for
  the first time, doubles the AR branch cost, and changes the take.
- Range is 0–20 (`request.cpp`). 0 means "negative branch only", i.e. the
  generic instruction; it is a valid but destructive experiment.

### D.3 `semantic_temperature`

Applied **after** the CFG blend, as `logits / T`; `T = 0` means greedy
(`sampling.py::distribution`). Default 1.0, valid 0–5. It changes the randomness
of token selection. It does not change what the model is conditioned on — that
is `guidance_scale`'s job. Lower = fewer surprises and more literal repetition;
higher = more invention and more risk of drifting off the maqam.

### D.4 `semantic_top_p` / `semantic_top_k`

Applied after temperature, in that order (`top_k` first, then nucleus). Defaults
0.95 / 100. These only truncate the candidate distribution; they cannot add
adherence the model did not already have.

### D.5 `semantic_repetition_penalty` / `semantic_penalty_window`

A multiplicative penalty on logits of tokens that appeared in the last
`penalty_window` (default 50) tokens: positive logits are divided, negative ones
multiplied (`sampling.py::window_penalty`; same arithmetic in the C++ sampler).
It suppresses literal loops. Push it too hard and sustained notes, melisma and
repeated syllables get distorted, because the penalty cannot tell a musical
repeat from a verbal one.

### D.6 `semantic_min_tokens` / `semantic_max_tokens`

`min_tokens` blocks the end token until that many tokens exist (default 200);
`max_tokens` is the hard budget (default 9000, and our `cap` overrides it). These
are bounds, not targets: the model still stops when it wants to, above the floor.

### D.7 `abc_*` sampling

The plan stage uses the **same AR sampler** with its own defaults: temperature
0.7, top_p 0.9, top_k 30, repetition penalty 1.005, window 100, min 32, max
4096. These change *which notes and chords the model plans*. Everything
downstream inherits that plan, so abc_* are the strongest "composition" knobs —
and they are **ignored when you supply an external `abc_file`** (the plan stage
is skipped entirely). That is why §7.1 makes mixing them a hard error.

### D.8 `num_inference_steps`

`ode_steps` in the NAR solver, one midpoint step per interval of `1/steps`
(`nar_runtime.cpp::solve_chunk`). audio.cpp defaults to **8**; the reference
package defaults to 32. It buys audio detail and costs time linearly. It does
not make the model follow the style, lyrics or score any better.

### D.9 `seed`

Seeds both the AR sampler and the NAR noise (`sampling.py` resets the
request-local generator per stage; C++ uses `std::mt19937` from the same seed).
Same seed + same settings + same weights = same bytes. Change any knob above and
the trajectory changes too, so a seed is only meaningful together with the full
resolved settings — which is exactly why §7.2 records them.

### D.10 `lora_ar_scale` / `lora_nar_scale`

Inference-time blend between base weights and adapter weights, applied per
expert (`lora.cpp`): 1.0 = full adapter, 0.0 = base model. AR shapes the
semantic plan/vocal behaviour; NAR shapes the rendered audio. The C++ only
checks that the value is finite; the 0–1.5 clamp in §7.1 is our own guard, not a
runtime limit. This is weight-space interpolation, not a prompt weight: it
cannot be expressed as text, and it does not "pull toward" an arbitrary reference
recording — only toward what the adapter learned.

### D.11 `cot`, `abc_file`, `semantic_prefix_file`, `nar_noise_file`

- `cot` picks the instruction sentence *and* whether the plan stage runs
  (`off` = no plan; `melody` = melody-only ABC; `full` = chord-annotated ABC).
- `abc_file` injects an external score into the prefix; requires `cot != off`.
  There is no strength value — influence is structural (scope, density, partial
  coverage), as `docs/transcription.md` lays out.
- `semantic_prefix_file` forces exact AR frames at the head of the stream. It
  is the only hard lock, and it is the one option that a shipped binary may
  silently ignore; check `strings` first.
- `nar_noise_file` supplies the initial latent noise for the NAR stage instead of
  drawing it from the seed — a way to reproduce or transplant texture. Not
  worth exposing until someone needs it.
