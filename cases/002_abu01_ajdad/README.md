# Case 002 — `وَالْأَجْدَادِ` (Abu al-Ala', take `3285212580`, arm `a01`)

**Status: PREP COMPLETE.** No audio edited, no GPU used. This folder holds the
intake, the alignment index, the defect card, the audition clips and the
preparation/friction log.

> **Goal:** a real, user-perspective test of "fix one pronunciation error" —
> first the preparation (this folder), then one GPU session on Colab.
>
> **Preparation log:** [PREP.md](PREP.md) — what took time, what was friction,
> what would make it faster.

## The take

| | |
|---|---|
| Run | `20261113-044223_abu01_defaults` |
| Take | `abu01_a01_3285212580.wav` |
| Seed | `3285212580` |
| LoRA | `a01` = `mix_v3/a0.1` (AR `d48109b3…`, NAR `88f00bcb…`) |
| Cap / frames | `7250` / **5727** frames @ 25 fps |
| Duration | 229.0787 s |
| Format | 48 kHz, stereo, PCM_16 |
| sha256 | `30860a08d5ca53731e76766e529d6de7039fa3e6eb96548b18c002417923dad0` |
| GPU (original) | Tesla **L4** (sm89) |
| Lyrics / style | exact run files, hashes match the sidecar |
| Stems | Demucs 4.1.0 `htdemucs`, 44.1 kHz; local `work/stems/…`, backed up to the run's `stems/` on GCS |

## The defect

Chorus 1, line 13:

```
هَوَانُ الْآبَاءِ وَالْأَجْدَادِ...
```

| field | value |
|---|---|
| target | `وَالْأَجْدَادِ` |
| occurrence | **1 of 2** — chorus 2 (200.10–201.92) **confirmed correct**; one edit |
| heard | `وَالْأَجْدَاج` — final `د` → **/g/** (confirmed) |
| class | consonant substitution, word-final |
| note after | a sustained ≈247 Hz tail 111.33–112.55 — **keep** (confirmed) |

Word box **109.149–111.329**; quiet point before **108.88**; note ends
**≈112.55**; reverb to ≈113.2. Full map: [intake/alignment.md](intake/alignment.md).

## What is proven locally (CPU, ~2 min)

- the WAV hash matches the sidecar; format/duration match;
- forced alignment: **141/141 words**, coverage 1.0, 30 line cues;
- the target word occurs **twice** (109.149 and 200.096); the **second
  occurrence is correct by ear**, so this is **one edit**;
- the note continues **1.2 s past** the lexical end — cutting at the box end
  would cut inside the note;
- the same take sings the same rhyme earlier in `الْأَجْسَادِ`
  (97.03–98.81) — a free reference; the A/B clip confirms it is the clean /d/.

**Not proven — the gate:** this take has **no exported semantic stream**
(`export_semantic` was off). Before any edit, a T4 must re-derive the 5727-frame
stream and prove the baseline WAV is bit-identical (`30860a08…`). The original
ran on an **L4**; the only prefix-capable binary is for the **T4**. If the gate
fails, stop — do not edit an unproven stream.

## Ear gates — closed; one strategy choice left

**Answered 2026-11-14:** the class is /g/ (confirmed); occurrence 2 is correct
(one edit); the tail is correct (keep it).

**The boundary is measured, not heard.** The old "hole test" on the **mix** was
the wrong instrument: the mix's instruments fill the 70 ms vocal break, so the
hamza and the waw sound merged. On the **vocal stem** the break is clear
(108.85–108.92, −35 dB, flatness low → glottal closure, not a breath).

Interactive chart: **`review/gaps.html`** (generated; regenerate with
`scripts/plot_gaps.py`) and the committed preview `review/gaps.png`. Two rows
(mix / vocal), word boxes from the alignment, numbered low-energy regions.
It shows the central fact: **the mix has 0 gaps; the vocal has 3**, and the only
break before the word is inside `الْآبَاءِ`.

| strategy | span | what the candidate re-sings | join sits in |
|---|---|---|---|
| **B (default)** | **109.10–111.35** | `wā` + the word + 20 ms of the sustain | at the word onset, **voiced** |
| D (fallback) | 106.20–111.35 | the whole line | **400 ms gap** before `هَوَانُ` |
| A (last resort) | 108.88–111.35 | hamza release + kasra + the word | glottal closure, but **inside** the previous word |

C (107.05) is **withdrawn**: the chart shows continuous energy there; the
alignment "gap" between `هَوَانُ` and `الْآبَاءِ` is not acoustic.

> **Rule (reusable):** when comping a vocal stem, approve boundaries on the
> **stem**, never on the mix. The instrumental bed exists to mask the join.

> **Review rule:** a 3 s clip locates the edit; it does not judge the repair.
> The final verdict is on the full track.

## Read next

- [PREP.md](PREP.md) — preparation timeline, friction log, accelerators, Colab gates.
- [intake/defect_card.md](intake/defect_card.md) — the one card to approve.
- [intake/alignment.md](intake/alignment.md) — how the word was found and measured.
- [spec/repair_spec.draft.json](spec/repair_spec.draft.json) — units, prefix/max, checks.
