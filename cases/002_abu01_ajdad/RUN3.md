# RUN3 — repair of `مِلَّتِي` (occurrence 1) in the CFG 1.5 ABC take

**Session:** Colab T4 (sm75), 2026-11-15, 04:26:01Z → 05:05:23Z
**Base:** `repro_abc_cfg15.wav`, sha `4f9006de…f95b4a`, 224.238667 s / 48 kHz stereo
**Deliverable:** `work/cfg15/comp/B_s2_3285212582.wav`, sha
`ae9217c138a62026605eedc849ccc7a45ee569504e21e76444e14f51d187a654`
**Verdict (user's ear):** **the م is audible, no seam heard.** 02 (B, seed 2)
preferred over 03 (B, seed 3); 04 (D, seed 2) not preferred.

> The original take was never modified. Every comp is byte-identical outside
> 27.46–28.98 s.

---

## 1. Timing — actual vs the 30-minute budget

| phase | start (UTC) | end (UTC) | actual | budget |
|---|---|---:|---:|---:|
| preflight (`git pull`, `setup_colab.sh`, GPU check) | 04:26:01 | 04:26:13 | 0:12 | 5:00 |
| asset fetch (WAV / tokens / log / score / LoRA) | 04:26:13 | 04:26:28 | 0:15 | — |
| **G0 token check** (count + duration + sha) | 04:26:28 | 04:26:35 | **0:07** | 0:30 |
| prefix binary stage + `strings` check | 04:26:35 | 04:27:45 | 1:10 | — |
| asset table / approval gate (human) | 04:27:45 | 04:28:30 | 0:45 | — |
| prefix 672 tokens + request JSON | 04:28:30 | 04:30:11 | 1:41 | — |
| **generation, seed 0 alone** | 04:30:17 | 04:35:39 | **5:22** | — |
| **generation, seeds 1–3 sequential, one session** | 04:36:43 | 04:43:50 | **7:07** | 10:00–20:00 |
| Demucs 4.1.0 install | 04:45:54 | 04:46:10 | 0:16 | — |
| Demucs on original + 4 candidates | 04:46:15 | 04:47:14 | 0:59 | — |
| measure + filter (stem, f0, centroid, seam) | 04:47:17 | 04:49:30 | 2:13 | 5:00 |
| comp B / D + seam verification | 04:49:31 | 04:50:20 | 0:49 | 5:00 |
| listening files + blind A/B + upload | 04:50:31 | 04:52:02 | 1:31 | — |
| **human listening verdict** | 04:52 | 05:00 | **≈8:00** | 5:00–10:00 |
| write-up, sidecar, push | 05:00 | 05:05:23 | 5:00 | — |
| **total wall** | 04:26:01 | 05:05:23 | **39:22** | 30:00 |
| **machine-only total** | 04:26:01 | 04:52:02 | **26:01** | 25:00–30:00 |

**Machine time met the budget (26 min). Wall exceeded it by 9 min:** ~8 min of
that is the human listening verdict, ~5 min is this report. The compute plan
itself fit.

### Where the 9 minutes actually went

1. **One process = one full model load.** `audiocpp_cli_prefix` pays ~5 min of
   fixed cost per process on a T4 (AR init 132 s, NAR LoRA merge 238 s, NAR init
   124 s) regardless of output length. Seed 0 alone cost 322 s to make 31 s of
   audio; seeds 1–3 in **one** `--request-sequence` process cost 427 s total,
   i.e. **45 s per extra seed** after the load (`request.s2.wall_ms 45574`).
   Splitting seeds across two processes cost a second load (~5 min).
2. **A 2.5-minute gap** between the batch ending (04:43:50) and Demucs starting
   (04:45:54) — my status polling overshot; it is dead time, not work.

---

## 2. What was run

```
prefix   = tokens[:672]  (26.88 s)   sha 9b288907…a89fa8
bounds   = semantic_min_tokens = semantic_max_tokens = 775 (31.00 s)
seeds    = 3285212580 (alone), then 3285212581/82/83 in one session
request  = guidance 1.5, cot=full, abc_file=cases/002_abu01_ajdad/abc/score.abc,
           steps 8, context 24576, nar_noise=generated, export_semantic=true,
           sampler T=1 / p=.95 / k=100 / rp=1.2 / window=50,
           LoRA mix_v3/a0.1 (a01) AR d48109b3… NAR 88f00bcb… scale 1.0,
           attention=flash, binary 4117a46a…
```

Log proof the bounds were applied (checked after seed 0, before seeds 1–3):

```
yue2.request … semantic_prefix_frames=672
yue2.sampling.semantic … min_tokens=775 max_tokens=775
yue2.semantic.tokens 775        (not 5606, not 7250)
```

### 2.1 Method, step by step (the part that is easy to lose)

1. **Do not re-derive.** G0 is a count + duration + sha check. `5606/25 = 224.24 s`
   matches the WAV, and the file sha matches the run that produced the WAV, so the
   token stream *is* this take's performance. Everything downstream uses it.
2. **Build the prefix from the take's own stream:** `tokens[:672]` = 26.88 s,
   ~120 ms before the /f/ of `فِي`, so the model enters the phrase on its own.
3. **One request shape, four seeds.** `min = max = 775` (31.00 s). Verify the
   request line in the log *before* the second seed; a wrong bound invalidates
   every later candidate.
4. **Demucs 4.1.0 `htdemucs` on the original and on every candidate** (same
   version that produced the map in `measure_cfg15.json`). All vocal measurements
   are on the 44.1 kHz stem, never on the mix.
5. **Measure the onset per candidate**, not from the card. For each stem, at
   10 ms / 5 ms resolution: `pyin` f0, RMS, spectral centroid, band shares
   (`onset_table.py`, `measure_word.py`). What separates a nasal onset from a
   plain vowel onset here is **centroid**, not pitch or level:

   | candidate | pre-vowel dark segment (centroid) | f0 there | vowel onset (f0→220) | word end | verdict |
   |---|---|---|---|---|---|
   | original (defect) | none — 232–261 Hz throughout | 195–201 | 27.52 | ~28.90 | “لتي” |
   | s0 `…580` | 27.40–27.49 (~203) | 196 | 27.52 | ~28.95 | kept, not chosen |
   | s1 `…581` | none — 264–400 | 201 | 27.56 | ~29.0 | rejected |
   | **s2 `…582`** | **27.455–27.555 (208–228)** | 198–200 | 27.56 | ~28.95 | **chosen** |
   | s3 `…583` | 27.44–27.54 (199–215) | 195–198 | 27.58 | ~29.0 | runner-up |

   Reference for comparison: occurrence 2's onset at 41.06–41.09 is the same
   kind of short, dark, voiced segment (centroid 391–634 while rising).
6. **Filter mechanically, then let the ear decide.** Reject only on things that
   are measurable: word end past 28.98 s, contour off the
   195→220→247→221 Hz shape, a new defect, a seam step. The /m/ itself is not
   provable — see §4.3 — so the survivors go to the ear labelled, not pre-judged.
7. **Comp the vocal only** (`comp_vocal_diff.py`):
   `mix + (cand_voc − orig_voc)` on 27.46–28.98 s, difference computed at
   44.1 kHz, resampled to 48 kHz, 15 ms linear ramps **on the difference**.
8. **Verify** (`verify_seam.py`): byte-identity outside the region, unchanged
   duration, 10 ms mix envelope across the seam (continuous for B: 0.131 →
   0.128 → 0.109 → 0.117 → 0.139 across the join), max sample step at the seam
   vs. inside the region, click ratio.
9. **Two widths from the same candidate**, B (join at the word) and D (join at
   the /f/), plus the runner-up seed as a B variant — three clips, one listening
   round.

Comp:

```
new_mix = mix + (cand_voc − orig_voc)   on 27.46–28.98 s, 44.1 kHz diff,
        resampled to 48 kHz, 15 ms linear ramps on the difference
```

Chosen candidate: **s2 / seed 3285212582**.

---

## 3. What worked

- **G0 in 7 seconds.** Count + duration + sha was enough. No re-derivation, no
  gate render. The take's own tokens are a valid prefix — the whole session hung
  on this and it held.
- **Bounds on the first try.** `min=max=775` appeared in the log; no second
  attempt, no 5606/7250 run.
- **One session for three seeds.** 45 s marginal per seed. This is the only
  reason four candidates fit in the budget at all.
- **Demucs 4.1.0 from `pip`, on GPU, after generation.** 59 s for the full track
  plus four candidates; installed in 16 s.
- **Comp points measured per candidate, not copied.** The card's B start (27.50)
  was right for the original audio but wrong for the candidate: the new nasal
  onset begins at **~27.45**. B was moved to **27.46**, the latest start that
  keeps the murmur while staying after `فِي`'s vowel body. This is the one change
  to the plan, and it is the change that made the م audible.
- **Vocal-only diff + ramps.** Byte-identity outside the region verified; seam
  sample-step 0.29× the max step inside the region on B (0.23× on B_s3); no
  click.

## 4. What failed, and the traps

1. **`truncated 1` is expected here, and the prompt's check said `truncated 0`.**
   With `min = max = 775` the AR is *forced* to stop at the cap without emitting
   an end token, so it always reports `truncated 1` and `emitted_tokens 775`
   (the total, not 103 new). It is not a defect: the line ends ~30.68 s, inside
   the 31.00 s cap, and the comp ends at 28.98. **Do not read `truncated 1` as
   "bounds not applied"** — read `min_tokens` / `max_tokens` / `semantic.tokens`.
2. **The prefix region is not bit-identical to the take.** The candidate is a
   fresh 31 s decode: NAR (`nar_noise=generated`) re-synthesizes the prefix too
   (measured max abs diff 0.65 in 0–26.88 s). Never assume "same tokens ⇒ same
   audio"; the comp must start after the region you actually measured.
3. **The /m/ cannot be proven by measurement.** Reference /m/ and vowel spectra
   in occurrence 2 have cosine similarity 0.92; CTC is useless (known); pyin,
   RMS and spectral flatness do not separate a 40 ms nasal murmur from a dark
   vowel onset. The useful filter was **spectral centroid**: s2 and s3 have a
   distinctly darker (centroid 200–228 Hz) voiced segment before the 220 Hz
   vowel onset; s1 does not. That ranked candidates; the ear decided.
4. **The deletion is not a "seed fluke".** All four seeds re-sang the word
   within 30–40 ms of the original timing and with the same contour
   (195→220→247→221 Hz) — the weak /m/ is a property of this text/route, not of
   one bad sample. Four seeds was the right ceiling; more would not help.
5. **D's join is measurably worse.** Starting at the /f/ onset (27.00) puts the
   splice in a fricative and the local envelope dips (click-ratio 1.19 vs 0.29
   for B). Consistent with the card's ranking of D as fallback.
6. **Two processes, two loads.** The only structural budget failure. If this
   workflow is repeated: run *all* seeds a session can need in **one**
   `--request-sequence` process, and only fall back to a second process if the
   first run fails.

---

## 5. Acceptance

| condition | how judged | result |
|---|---|---|
| the **م** is audible at the start of `مِلَّتِي` | user's ear on 01 → 02, and on the full track | **yes** |
| the user cannot hear where the edit is | user's ear, `Do you hear a seam?` → *"No seam — accept 02"* | **yes** |
| outside the region unchanged | byte comparison vs `repro_abc_cfg15.wav` | **identical** |
| duration unchanged | 224.238667 s | **yes** |
| `فِي` / `وَاعْتِقَادِي` untouched | outside 27.46–28.98 | **byte-identical** |
| candidate word end before the next word | 28.95 < 29.00 | **yes** |

Occurrence 2 (repeated verse) was never touched: no donor splice was made from
41.13–42.55; it stayed a reference only.

---

## 6. Evidence

`gs://akbar-december-2024-backup/arabmaqamrock/runs/20261115-042753_repair002_cfg15/`

```
inputs/      WAV + token + lyrics/style/score copies
tokens/      abc_cfg15_semantic.json (5606) + tokens_prefix_672.json
candidates/  s0…s3 WAV + vocals (all four, no rejects hidden)
comp/        comp.json, B_s2, B_s3, D_s2, verify_*.json, m_original.json
final/       final_B_s2.wav, final_sidecar.json, blind clip1/clip2
session/     timing.tsv, KEY.txt, logs/
```

Blind A/B was staged (`clip1.wav`, `clip2.wav`, key in `session/KEY.txt`) but the
verdict was reached from the labelled comparison; the key was not needed.

Reproduce the comp (scripts are in this repo, `cases/002_abu01_ajdad/scripts/`):

```bash
python3 cases/002_abu01_ajdad/scripts/comp_vocal_diff.py \
  --orig-mix work/cfg15/repro_abc_cfg15.wav \
  --orig-voc work/cfg15/stems/htdemucs/repro_abc_cfg15/vocals.wav \
  --cand-voc work/cfg15/stems/htdemucs/s2_3285212582/vocals.wav \
  --start 27.46 --end 28.98 --cand-offset 0 \
  --out work/cfg15/comp/B_s2_3285212582.wav
```

| script | what it does |
|---|---|
| `scripts/measure_word.py` | f0, RMS, low-band and flatness around the word; word-end search |
| `scripts/onset_table.py` | 10 ms table (t, RMS, f0, low-band %, flatness) for one window |
| `scripts/comp_vocal_diff.py` | the vocal-only diff comp + byte-identity verification |
| `scripts/verify_seam.py` | seam f0/RMS, click ratio, 10 ms envelopes across the join |

Inputs are not in git (WAVs, stems, tokens, binary — `.gitignore`): fetch the
original from `inputs/` in the GCS run folder and re-run Demucs 4.1.0 to get the
stems, or pull `candidates/*_vocals.wav` from the same folder and skip Demucs.
