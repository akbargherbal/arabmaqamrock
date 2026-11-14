# RUN 2 — case 002 (`abu01_a01`, `وَالْأَجْدَادِ`)

**Date:** 2026-11-14 · **GPU:** Tesla T4 (sm75) · **Outcome:** **STOPPED at the token gate.**
**Original WAV untouched.** No candidates, no comp, no final were produced.

---

## 1. Result in one line

The take was generated **without exported semantic tokens**. Re-deriving them on
T4 does **not** reproduce the L4 take: two independent T4 runs (different
binaries) agree with each other but produce **5937** frames, not **5727**, and a
full render of the first 5727 frames is a **different performance from the first
5-second window**. The gate fails, so the workflow stops by its own rule.

| gate check | measured | required | verdict |
|---|---|---|---|
| token count | 5937 (twice, identical) | 5727 | ✗ |
| `truncated` | 0 | 0 | ✓ |
| render duration | 229.078667 s | 229.079 s | ✓ |
| sha256 | `07be0e33…` ≠ `30860a08…` | bonus only | — |
| envelope correlation | **0.216** | ≥ 0.99 | **✗** |
| median mel Δ | **7.47 dB** | ≤ 1 dB | **✗** |
| first 5 s window r | **0.382** | ~1 | **✗** |

**Ear confirmation (user, 2026-11-14):** after listening to
`listen/gate_render_full.wav` — *“very different”*. The metrics and the ear
agree: this is not the take. No comp was attempted.

Evidence: `gs://akbar-december-2024-backup/arabmaqamrock/runs/20261114-183900_repair002/`

---

## 2. Actual times vs the 30-minute budget

Start `18:16:10Z`; gate decision `18:38Z`. Packaging/report to ~`18:46Z`.

| phase | budget | actual | Δ | note |
|---|---:|---:|---:|---|
| 0 assets + hashes + GPU | 5 min | **2.8 min** | −2.2 | setup already staged; had to fetch the prefix binary separately (17 s) |
| 1 params from original log | — | 1.5 min | — | original log gives all resolved values |
| 2 re-derive tokens | 2 min | **9.8 min** (2 × 4.9) | **+7.8** | first with prefix binary (5937), then with the exact original binary (5937) |
| 3 token gate render | 4 min | **6.4 min** | **+2.4** | 5727 frames, full 229 s NAR+VAE |
| 3b comparison + diagnosis | — | 1.0 min | — | envelope, mel, 5 s divergence map |
| 4 batch (4 seeds) | 6 min | — | — | not reached |
| 5 Demucs + filter | 6 min | — | — | not reached |
| 6 comp + verify | 5 min | — | — | not reached |
| 7 listen | — | — | — | not reached |
| **to the stop decision** | — | **≈22 min** | | **within 30 min, but no repair delivered** |

**Where the budget went:** the gate itself was 16.2 min (2 re-derives + render),
vs the 6 min budgeted for *gate + batch*. This is the known failure mode from
`CHECKPOINT.md` §8(a): no exported tokens turns the gate into a session.

---

## 3. What was verified (and how)

- **Assets** all matched: WAV `30860a08…`, vocals `bf6273ea…`, no_vocals
  `fec0351b…`, LoRA a0.1 AR `d48109b3…` / NAR `88f00bcb…`, model `4cf3fdff…`,
  VAE `d4f4a05d…`. GPU T4 / 7.5.
- **Binary provenance:** the brief's `4117a46a…` is the **prefix** binary
  (`binaries/sm75-t4/prefix/audiocpp_cli_prefix_sm75`), not the standard
  `bin/audiocpp_cli` (`7ad69d1c…`, the hash the source run used). Both were
  staged; the token recovery was repeated with each.
- **Request parameters** were taken from the original run's log, not defaults:
  `seed 3285212580`, `guidance_scale 1`, `num_inference_steps 8`,
  `context 24576`, `cot off`, `nar_noise generated`,
  semantic `T=1 / p=0.95 / k=100 / rp=1.2 / window 50 / min 200`,
  `max_tokens 7250`, LoRA AR+NAR scale 1.0, `attention=flash`.
- **Both T4 runs are deterministic:** the 5937-frame streams from
  `bin/audiocpp_cli` and `bin/audiocpp_cli_prefix` are **element-for-element
  identical**. So this is not RNG noise on T4; it is an **L4 → T4** difference.
- **The divergence is not a tail-only EOS difference.** The gate render equals
  the original in duration (229.078667 s) but diverges in the first 5 s
  (r = 0.382), and no 5 s window reaches r ≥ 0.9. The extra 210 T4 frames
  (8.4 s) are a symptom, not the cause.
- **No surviving export exists.** The source run's bucket prefix contains no
  `semantic.json`/tokens; a bucket-wide search found none for `abu01`, and the
  local disk only has this session's re-derivations.

---

## 4. What was deliberately not done

- No prefix batch (a prefix from a different performance would splice a
  different singer's trajectory into the take).
- No `no_vocals + candidate` mix, no donor splice from chorus 2 or any other
  take, no fixed cut point.
- No "almost" delivery: the brief makes the pair of conditions mandatory, and
  this route failed the *foundation* condition (same performance), not the
  repair condition.
- `STEPS.md` was **not** edited — nothing in it was contradicted; the stop rule
  it defines is exactly what was executed.

---

## 5. Why this is the correct stop, not a failed attempt

The repair method needs the take's own token stream to (a) lock the AR head so
the model re-sings the same performance, and (b) splice only the vocal. With
the stream missing, every downstream step would have been built on a different
performance. The gate exists to catch exactly this before any GPU batch. It did.

The original file remains the deliverable. The cost of this session is
**22 minutes**, not a bad take.

---

## 6. What must become a script (to make 30 min real next time)

Ordered by the time they would have saved in this session:

1. **`token_gate.py` — one command, all three checks.**
   Input: run dir + expected token count. It builds the re-derive request,
   runs it, compares the count, slices `N`, renders `min=max=N`, and emits
   `gate/compare.json` (sha, envelope r, median mel Δ, 5 s divergence map).
   Saves the manual command assembly and the second re-derive (**~8 min here**).
2. **Export tokens at generation, always.** `export_semantic=true` for any take
   that might be repaired, plus a sidecar field `semantic_sha256` and frame
   count. This alone would have removed **16 of the 22 minutes** and made the
   gate a 4-minute render. (`CHECKPOINT.md` §8 already names this.)
3. **`locate_consonant.py` — the consonant locator + cut picker.**
   From a vocal stem: closure, burst (2–8 kHz), the quietest 20 ms ≥ 30 ms
   after the burst, f0/RMS at the seam. This is the candidate-specific cut;
   it replaces eyeballing `110.30`/`110.35`. (`work/scripts/measure.py` in this
   session is a first version.)
4. **`comp_vocal.py` + `verify_comp.py`.** Difference-at-44.1k → upsample →
   add inside the region; verify byte-identity outside, length, edge steps.
   (`work/scripts/comp.py`, `verify_comp.py` are first versions.)
5. **Binary/arch provenance in the sidecar:** binary sha, compute capability,
   and a `reproducible_on` field. The original is L4; the only prefix binary is
   T4. A take that may need repair should be generated on an arch that has a
   prefix binary, or its tokens must be exported.

**One-line lesson:** *a repair workflow cannot start at repair time; it starts
at generation.* Export the tokens, or the 30-minute budget is fiction.

---

## 7. Post-stop experiment: ABC conditioning (user request)

After the stop, the take's **transcribed** score (`abc/score.abc`, SheetSage2,
made from the finished mix) was fed back as `abc_file` with `cot=full`, same
seed/parameters/LoRA, full render. This is a new conditioning route, not a
reproduction of the original request (`cot=off`, `abc=none`).

| render | tokens | duration | envelope r | median mel Δ |
|---|---:|---:|---:|---:|
| original (L4) | 5727 | 229.079 s | — | — |
| T4 re-derive (no score) | 5937 | 229.079 s | 0.216 | 7.47 dB |
| ABC-conditioned (T4) | **5728** | 229.119 s | **0.633** | **4.19 dB** |

The score anchors the **duration** (5728 ≈ 5727, +40 ms), but not the
performance: the stream differs from frame 0, and the target line at
106.1–113.3 has r = 0.58 at zero lag. Gate still fails; not usable for a comp.

Evidence: `gs://…/runs/20261114-185000_abc_repro/` (WAV, tokens, score,
compare JSON, log, line clip). Original still untouched.
