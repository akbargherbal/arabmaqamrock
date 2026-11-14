# Defect card — case 002

One card per occurrence. Gate A: this card must be right before anything is
rendered.

| field | value |
|---|---|
| **song / take** | Abu al-Ala', `abu01_a01`, take `3285212580` |
| **section / line** | Chorus 1, line 13 |
| **lyric** | `هَوَانُ الْآبَاءِ وَالْأَجْدَادِ...` |
| **target word** | `وَالْأَجْدَادِ` |
| **occurrence** | **1 of 2** — chorus 2 (200.10–201.92) **confirmed correct by ear**; only occurrence 1 is edited |
| **alignment box** | 109.149 – 111.329 s (lexical; the note continues to ≈112.55) |
| **heard** | `وَالْأَجْدَاج` — the final `د` is a **/g/** (Egyptian ج) — **confirmed by ear** |
| **target** | `wal-ʾaj-dā-di` — a clean final /d/ |
| **class** | consonant **substitution** (place/voicing), word-final position — **confirmed** |
| **note after** | **keep** — the sustained ≈247 Hz tail (111.33–112.55) is correct — **confirmed by ear** |
| **must not change** | `هَوَانُ الْآبَاءِ`; the tail; the instrumental; the timing |

## What only the ear can confirm

**Closed 2026-11-14.** The four answers:

1. **`heard`** — confirmed: the final `د` is a **/g/** (Egyptian ج). The
   reference pair `الْأَجْسَادِ` vs `وَالْأَجْدَادِ` made the contrast obvious.
2. **`occurrence 2`** — **correct**. The line at 197.40–202.90 sounds right, so
   this is **one edit, not two**. Bonus: the same take, same singer and same
   section contain a correct version of the word — a verification reference (and
   a theoretical donor; the durations differ, 2.18 s vs 1.82 s, so do not start
   there).
3. **`note_after`** — **keep confirmed**: the tail 111.33–112.55 is correct.
4. **`no second defect`** in the line — confirmed.

The remaining open item is the **boundary approval** (U1/U2), via the hole tests
in `review/09_*`.

## Why the word box is not the cut

- the box starts 109.149, but the quiet dip before it is **108.88** — the only
  clean join in a continuous phrase;
- the box ends 111.329, but the voice continues on the same note to **112.55**;
- the reverb ends ≈113.2 — cutting there includes 0.6 s of silence/reverb.

## The comp variants (draft)

| variant | span (s) | replaces | joins | risk |
|---|---|---|---|---|
| **B — word only (default)** | **109.10 – 111.35** | the `wā` + word + 20 ms of the sustain | word onset, **voiced**; sustain start | join at a consonant onset |
| **D — line (fallback)** | 106.20 – 111.35 | `هَوَانُ الْآبَاءِ وَالْأَجْدَادِ` | **400 ms gap** before `هَوَانُ`; sustain start | replaces two correct words |
| **A — fragment (last resort)** | 108.88 – 111.35 | hamza release + kasra + word | glottal closure, but **inside** the previous word | partial-word start |

- **B is the default**: the smallest whole unit; the previous word stays 100 %.
- **D** is used only if B's start join is audible. It replaces more, but both
  joins are clean (a real gap and the start of the sustain).
- **A** is the last resort: the only silent start, but it starts inside
  `الْآبَاءِ` — the failure mode the ear warned about.
- **C (107.05) is withdrawn**: the chart `review/gaps.html` shows continuous
  energy there; the alignment "gap" between `هَوَانُ` and `الْآبَاءِ` is not
  acoustic.

The tail is kept in all three (the ear confirmed it is correct).

## Card status

- [x] `heard` confirmed — /g/
- [x] occurrence 2 checked — correct, not edited
- [x] `note_after` confirmed — keep the tail
- [x] no second defect in this take
- [x] boundary strategy — B default; see `review/gaps.html`
