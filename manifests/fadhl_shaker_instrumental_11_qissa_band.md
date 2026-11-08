# Round 11 — القصة وما فيها: section plan and a real band

**Written:** 2026-11-08
**Score:** `scores/fadhl_shaker_instrumental/al_qissa_wama_fiha.abc` (319.1 s, Cm, 91 BPM, 2/4)
**Reference take:** `runs/20261108-062853_fadhl_inst_10_pilot24/al_qissa_wama_fiha_20261106.wav`
**Seed:** `20261106` for every take. `cot=full`, AR LoRA `ar_lora_inst_v3abc`, `trigger: false`.

## 0. Two known failures — not re-tested here

**(a) The bare form is settled as a failure.** Every take in rounds 07, 09 and the
24-song pilot used `lyrics: "[instrumental]"`. Across 36 takes that form produced
4 catastrophic early endings (120–297 s against scores of 202–367 s), 2 cap cuts
at exactly `score + 10.0 s`, and the rest ending mid-phrase with no cadence. The
adopted plan is now

```
[intro]
[instrumental]
[outro]
```

stored once in `defaults.lyrics` (it applies to every song; a per-song `lyrics`
still overrides). No take in this round repeats the bare form.

**(b) The cap was the cap.** The take the user heard on this song ends at
**329.16 s at full level** (−16.8 dB in the last second). That is not the model:

| | |
|---|---|
| score length | 319.12 s |
| cap | 8229 tokens |
| cap in seconds (25 tok/s) | 329.16 s |
| wav duration | 329.158 s |
| sidecar `truncated` | **true** |

`cap = ceil(score_s * 25) + 250` leaves 10 s of headroom; this song wanted more
and was cut mid-bar. Every take here uses **cap 9200** (368 s).

For the record, the pilot's length outcomes: 18/24 within −12 s of the score,
2/24 truncated at `score + 10.0`, 4/24 ended 48–135 s early. Two independent
causes — the cap and the ending — and this round fixes both.

## 1. Why tags should fix the early endings

The instrumental LoRA's model card states it was trained on three lyrics forms in
equal thirds — bare `[instrumental]`, untimed tags, and **timed** tags with
`m:ss` — and that training included a **section-cursor loss** plus an **up-weighted
END token**. Allowed tags: `intro, verse, pre-chorus, chorus, bridge, outro`.
One tag per line, real line breaks, nothing else inside the brackets; production
notes, lyric text and literal `\n` are out of distribution.

Untimed on purpose: the ABC already owns the timing, and the plan only has to say
"there is a beginning, a middle and an end".

## 2. Why the electronics are not a prompt problem

From the same card:

- The AR LoRA was trained on ~2.7 k instrumentals **regularised 50/50 with YuE2's
  own generations**. Half its prior is synthetic. That is the "DJ box" character,
  and no adjective in the caption removes it.
- The author's own recommendation for realistic output is to pair it with the
  real-audio NAR LoRA (`nar_lora_joint_v9`): *"our renders used that NAR LoRA"*.
  v9 is trained with an **audio-domain loss** (log-mel L1 + multi-resolution STFT
  + a stereo-width term) and selected by ear against real recordings using LTAS,
  the production fingerprint.

Round 06 measured v9 and switched it off for being louder, narrower and brighter —
a loudness/tone question, not a realism one. It has never been in a winning
configuration, because every manifest since points the `instrumental` alias at the
maqam-rock NAR at scale 0.

The band vocabulary is the cheap lever on top. Instrument words are in
distribution for this LoRA (its caption format is *genre, instruments, mood, BPM*),
and the negatives target exactly what the user hears:

```
live band, real instruments, acoustic drums, electric guitar, bass guitar,
hand percussion, warm analog production, organic mix,
no drum machine, no electronic drums, no synth lead, no programmed beats
```

## 3. The takes — 4

| # | take | style | AR | NAR |
|---|---|---|---|---|
| 1 | `c0_tags` | h2 | 1.0 | off |
| 2 | `c1_band` | h2 + band | 1.0 | off |
| 3 | `c2_band_v9` | h2 + band | 1.0 | **v9 @1.0** |
| 4 | `c3_band_v9_ar085` | h2 + band | **0.85** | **v9 @1.0** |

All four use `[intro]/[instrumental]/[outro]` and cap 9200. One variable per step:
band words → decoder → adapter strength.

AR 0.85 exists because half the LoRA's training audio is synthetic; giving the
base model (trained on real recordings) more say is the cheapest way to test that.

## 4. Run

```bash
cd /content/arabmaqamrock && git pull
python3 generate.py manifests/fadhl_shaker_instrumental_11_qissa_band.json \
  --label fadhl_inst_11_qissa_band
```

4 takes, ~26 min on a T4, ~17 min on an L4.

## 5. Judging

- **Level-match first.** v9 is ~2.5 dB hotter; louder always sounds better.
- Ending checks: sidecar `truncated` flag, duration vs 319.1 s, and the RMS of the
  last 10 s (a fade should be −30 dB or lower; a cut sits near −15).
- Band checks: does the low end sound like a bass guitar and a kick, or a synth
  sub? Is the percussion a player or a loop? Is the guitar a performance or a
  preset?

The result decides whether the 488-song batch needs band words + v9, and whether
the cap formula becomes `score_s * 25 + 1000`.
