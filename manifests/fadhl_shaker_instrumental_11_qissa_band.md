# Round 11 — القصة وما فيها: ending tags and a real band

**Written:** 2026-11-08
**Score:** `scores/fadhl_shaker_instrumental/al_qissa_wama_fiha.abc` (319.1 s, Cm, 91 BPM, 2/4)
**Control take:** `runs/20261108-062853_fadhl_inst_10_pilot24/al_qissa_wama_fiha_20261106.wav`
**Seed:** `20261106` for every take. `cot=full`, AR LoRA `ar_lora_inst_v3abc`, NAR off except where stated, `trigger: false`.

## 0. First finding — the control is not a model ending, it is the cap

The take the user heard on this song ends at **329.16 s at full level** (−16.8 dB in
the last second). That is not the model stopping mid-phrase, it is the token cap:

| | |
|---|---|
| score length | 319.12 s |
| cap | 8229 tokens |
| cap in seconds (25 tok/s) | 329.16 s |
| wav duration | 329.158 s |
| sidecar `truncated` | **true** |

`cap = ceil(score_s * 25) + 250` leaves exactly 10 s of headroom, and this song
wanted more, so it was cut mid-bar at full level. Two of the 24 pilot takes are
in this state (`al_qissa_wama_fiha`, `min_kothr_hobbi_feek`); both are exactly
`score + 10.0 s`.

So part of the "sudden ending" on this song is a **cap bug**, not a musical one.
Hence `c1_bare_room`: same bare lyrics, only the cap raised to 9200 (368 s).

The wider pilot picture, which is why this is not a one-song curiosity:

| length outcome | takes |
|---|---|
| within −12 s of the score (healthy) | 18 / 24 |
| truncated at `score + 10.0 s` | 2 / 24 |
| ended 48–135 s early | 4 / 24 (`saharni_alshawq` 120.7 s, `ya_tkoon_habibi` 240.0 s, `ya_hawa_alghaleen` 297.6 s, `lelheen_3ayesh` 240.0 s) |

A quarter of the batch has a structural length failure. Two independent causes:
the cap (2) and the model ending early (4).

## 1. Why tags should fix the early endings

The instrumental LoRA's model card states it was trained on three lyrics forms in
equal thirds — bare `[instrumental]`, untimed tags, and **timed** tags with
`m:ss` — and that training included a **section-cursor loss** plus an **up-weighted
END token**. The allowed tags are exactly:

```
intro, verse, pre-chorus, chorus, bridge, outro
```

One tag per line, real line breaks, nothing else inside the brackets. Production
notes (`[guitar solo]`), lyric text and literal `\n` are out of distribution.

We have only ever fed it the **bare** form, which is the one form with no section
plan and therefore no explicit ending signal. `[intro] / [instrumental] / [outro]`
is the smallest plan that says "there is a beginning, a middle and an end" and
nothing else. Untimed on purpose: the ABC already owns the timing.

## 2. Why the electronics are not a prompt problem

Two facts from the same card:

- The AR LoRA was trained on ~2.7 k instrumentals **regularised 50/50 with YuE2's
  own generations**. Half its prior is synthetic. That is the "DJ box" character,
  and no adjective in the caption removes it.
- The author's own recommendation for realistic output is to pair it with the
  real-audio NAR LoRA (`nar_lora_joint_v9`): *"our renders used that NAR LoRA"*.
  v9 is trained with an **audio-domain loss** (log-mel L1 + multi-resolution STFT
  + a stereo-width term) and selected by ear against real recordings using LTAS,
  the production fingerprint.

Round 06 measured v9 and switched it off for being +2.5 dB louder, narrower and
brighter — a loudness/tone question, not a realism one. It has never been in a
winning configuration, because every manifest since points the `instrumental`
alias at the maqam-rock NAR at scale 0.

The band vocabulary is the cheap lever on top: instrument words are in
distribution for this LoRA (its caption format is *genre, instruments, mood, BPM*),
and the negatives target exactly what the user hears:

```
live band, real instruments, acoustic drums, electric guitar, bass guitar,
hand percussion, warm analog production, organic mix,
no drum machine, no electronic drums, no synth lead, no programmed beats
```

## 3. The takes

The section plan is now a **corpus default**, not a per-song line:

```json
"defaults": { "lyrics": "[intro]\n[instrumental]\n[outro]", ... }
```

`generate.py` gained `defaults.lyrics` / `defaults.lyrics_file` for exactly this
(a per-song `lyrics` still overrides it). Before this, the plan had to be copied
into all 488 song entries, which is how it quietly drifts out of a batch.

| # | take | lyrics | style | AR | NAR |
|---|---|---|---|---|---|
| 1 | `c0_control` | `[instrumental]` | h2 | 1.0 | off |
| 2 | `c1_bare_room` | `[instrumental]` | h2 | 1.0 | off |
| 3 | `c2_tags` | `[intro]/[instrumental]/[outro]` | h2 | 1.0 | off |
| 4 | `c3_band` | same tags | h2 + band | 1.0 | off |
| 5 | `c4_band_v9` | same tags | h2 + band | 1.0 | **v9 @1.0** |
| 6 | `c5_band_v9_ar085` | same tags | h2 + band | **0.85** | **v9 @1.0** |

`c0` keeps the published cap 8229 so it must reproduce the pilot WAV byte for
byte — a pipeline check. Every other take gets cap 9200. The chain then isolates
one variable per step: cap → tags → band words → decoder → adapter strength.

AR 0.85 exists because half the LoRA's training audio is synthetic; giving the
base model (trained on real recordings) more say is the cheapest way to test that.

## 4. Run

```bash
cd /content/arabmaqamrock && git pull
python3 generate.py manifests/fadhl_shaker_instrumental_11_qissa_band.json \
  --label fadhl_inst_11_qissa_band
```

6 takes, ~39 min on a T4, ~25 min on an L4.

## 5. Judging

- **Level-match first.** v9 is ~2.5 dB hotter; louder always sounds better.
- Ending checks: sidecar `truncated` flag, duration vs 319.1 s, and the RMS of the
  last 10 s (a fade should be −30 dB or lower; a cut sits near −15).
- Band checks: does the low end sound like a bass guitar and a kick, or like a
  synth sub? Is the percussion a player or a loop? Is the guitar a performance or
  a preset?

The result decides whether the 488-song batch needs tags + band words + v9, and
whether the cap formula must change to `score_s * 25 + 1000`.
