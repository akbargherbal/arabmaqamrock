# RUNBOOK — one error, one session (case 002)

> **Objective:** the minimum human minutes and the minimum irreversible
> decisions. GPU time is cheap and unattended; human attention is not.
>
> Nothing here is specific to this song except the numbers in
> `spec/repair_spec.draft.json`. The steps are the same for any take.

---

## Inputs the user must supply (4 things)

1. the take (or its run + name);
2. the word;
3. what was heard;
4. a rough time — **any** bracket inside the right section is enough
   (here: 01:49.11–01:53.16, which is 4 s for a 2.2 s word).

Everything else is derived. If the user supplies more than these four, it is a
bonus, not a requirement.

---

## Phase 0 — intake (local, no GPU) — **done**

Hash + format + sidecar, Demucs, forced alignment, f0/RMS map, clip pack.
Cost: ~2 min machine. Output: `intake/`, `review/`, `spec/`.

---

## Phase 1 — close the card (local, human) — **done 2026-11-14**

Answered: the final `د` is **/g/**; occurrence 2 is **correct** (one edit); the
tail is **correct** (keep it). Start strategy: **B default** (word onset, previous word 100 % original);
**D** (whole line, starts in the 400 ms gap before `هَوَانُ`) if B's start join is
audible; **A** (the glottal closure, inside the previous word) as a last resort.

The boundary is not an ear decision: the chart `review/gaps.html` shows the mix
has 0 gaps and the vocal has 3; the only break before the word is inside
`الْآبَاءِ`. Measure on the stem; the human chooses the strategy.

---

## Phase 2 — pre-flight (local, ~5 min, no GPU)

1. **Assets** (verify, do not download):
   - base model + VAE;
   - `a01` AR/NAR from
     `gs://…/OSTRIS_Arabic_Suno_Finetuning/arabic_instrumental_lora/mix_v3/a0.1/`
     (sha `d48109b3…` / `88f00bcb…`);
   - prefix binary `binaries/sm75-t4/prefix/audiocpp_cli_prefix_sm75`
     (sha `4117a46a…`).
2. **Requests as data** (no code): one JSON for the re-derive, one for the batch.
3. **Decide the stop rule** (below) *before* renting the GPU.

**Why here:** every minute spent hunting a path on the GPU box is a minute of a
metered session.

---

## Phase 3 — one Colab session (T4, ~25–30 min)

### 3A. Re-derive the stream (AR only, ~4–5 min)

Single request: original seed / lyrics / style / cap, `stop_after=semantic`,
`export_semantic=true`. Expect **5727 tokens**, prefix 1156, truncated 0.

### 3B. One batch = baseline + tails (NAR/VAE, ~15 min)

One invocation, one model load:

- request 0: **baseline** — the full stream, `min=max=5727`;
- requests 1–16: **tails** — prefix `2718`, max `2825`, seeds `base+0..15`.

If occurrence 2 had been wrong, it would add 16 tails with its own prefix/max in
the same session. It is **correct**, so the batch is one region.

### 3C. Inspect the baseline (the gate)

| gate | test | action |
|---|---|---|
| **G1 fingerprints** | 5727 tokens / prefix 1156 / truncated 0 | fail → stop |
| **G2 same performance** | compare baseline to the original: duration, waveform correlation ≥ 0.99, median mel Δ ≲ 1 dB | fail → stop |
| **G3 bit-identity** | sha256 equals `30860a08…` | bonus, not required across an L4→T4 move |

> G2 is the honest gate when the GPU class changes. Demanding G3 on a different
> architecture can block a valid repair for the wrong reason. Record which gate
> passed; never claim bit-identity you did not get.

**If the gate fails: stop.** Do not splice a word from a different performance,
and do not "try the batch anyway".

---

## Phase 4 — pick and comp (local CPU, ~10 min)

Download the 17 WAVs (or just the tails). Everything below is local.

1. **Filter without ears** (rejects are never auditioned):
   - tail pitch: ≈247 Hz, length ≥ 1.2 s (only if comping A1);
   - onset lag ≤ 60 ms, no time-stretch;
   - `/d/` present (CTC presence filter — a filter, not a verdict);
   - edge level step < 1 dB.
2. **Audition** 3–5 candidates on the **full line** (106.1–113.3).
   Never on the word alone.
3. **Comp the winner from the same render:**
   - **B** `109.10–111.35` (word, tail kept), 40/40 ms fades — default;
   - **D** `106.20–111.35` (whole line, real gap before), 40/40 ms fades — fallback;
   - **A** `108.88–111.35` (fragment, silent start), 40/40 ms fades — last resort.
   Vocal stem only, resampled to 48 kHz; instrumental untouched.
4. The ear picks the variant. **The start is decided after the render, not
   before** — this is what makes the hardest decision reversible.
5. Verify: outside the changed spans the file equals the original; duration
   unchanged; the tail (from 111.35) is byte-identical in all three.

---

## Phase 5 — review and close (local, ~10 min)

- full track (or a complete section ending at a real boundary), with targets:
  S1 105–115 s, S2 197–203 s;
- verdict: ship / keep original / retry;
- manifest: original and final sha256, changed spans, edge steps, comp region,
  what is and is not identical;
- one line in the record: what worked, what did not, which rule changed.

---

## Stop rules (write them before the session)

1. **Gate fails → stop.** No donor fallback, no "close enough" edit.
2. **16 tails, same wrong consonant → the text, not luck.** One phonetic
   respelling attempt (in the request only; the published lyric stays correct).
   Still failing → keep the original or change the take.
3. **Two rounds per word.** Then stop, whatever the score.
4. **No full-song regeneration** to fix a word.
5. **No audition of a partial word.**

---

## Cost model

| phase | human | machine |
|---|---:|---:|
| Phase 0 intake | — | 2 min |
| Phase 1 ear gates | 10 min (done) | — |
| Phase 2 pre-flight | 5 min | — |
| Phase 3 GPU (gate + batch) | 5 min | 25 min |
| Phase 4 filter + comp | 10 min | 5 min |
| Phase 5 review | 10 min | — |
| **total** | **~40 min** | **~30 min** |

The session is **one** GPU rental. The only thing that can turn it into two is a
failed gate or a unit that is not really a boundary.
