# PREP — case 002: what preparation costs, and where the time goes

This is the **user-perspective** log of preparing one pronunciation repair on a
normal laptop (no GPU): what was needed before touching the model, what took
time, what was friction, and what would make the next case faster.

Scope: **preparation only.** No render, no edit, no GPU. The repair session is
the next step.

---

## 1. The deal

The user supplies: a song, a word that is sung wrong, and a rough idea of where
it is. Everything else is preparation:

1. freeze the exact take (hash, format, provenance);
2. find the word, and **all** its occurrences;
3. measure where the word ends **musically** (not lexically);
4. propose the unit(s) and the generation window;
5. package the clips the ear needs;
6. list the gates the GPU session must pass **before** it renders anything.

The output of preparation is a **card, a map, a clip pack, and a gate list** —
not audio.

---

## 2. What the user gave, and what was actually needed

The first message gave `01:42.11 – 01:53.16` (a range of ~11 s: the whole
chorus). A correction followed: `01:49.11 – 01:53.16` (4 s). The actual word is
**2.18 s** (109.149–111.329), with a **1.2 s tail** (to 112.55) and reverb to
113.2.

That is not a complaint: the corrected range bracketed the word exactly at the
start (109.11 vs 109.149, a 40 ms difference). But it shows the real problem:

> **A listener reports a region, not a word.** The region can be 10× the word,
> and it contains three different "ends". Turning it into an edit boundary is
> measurement work, not listening work.

The fix is not "listen more carefully". It is: **give the user a locator clip
and let the aligner produce the index**, then ask only for approval.

---

## 3. What the machine did (measured on this laptop)

| step | wall | notes |
|---|---:|---|
| download the 42 MB WAV from GCS | 7.4 s | mp3 is 5.5 MB but unusable for the edit |
| `ffprobe` + sha256 + sidecar check | <1 s | hash matches `30860a08…` |
| Demucs `htdemucs` (229 s, CPU) | **59 s** | the only slow step |
| forced CTC alignment (141 words) | **~55 s** | includes model load |
| f0/RMS map + clip cutting | ~6 s | `scripts/make_loops.py` |
| **total** | **~2 min 10 s** | one-time, per take |

That is the *whole* preparation. The expensive part is not the machine; it is
the **decisions and the missing artefacts** below.

---

## 4. The map (what preparation produced)

```
line 13   هَوَانُ الْآبَاءِ وَالْأَجْدَادِ...
          106.289        108.989  109.149        111.329   112.55   113.2
             |              |        |              |         |       |
          هَوَانُ        الْآبَاءِ  وَالْأَجْدَادِ   lexical   note    reverb
                                        ↑        end       end     end
                                   quiet dip 108.88
```

| fact | value | why it matters |
|---|---|---|
| word box | 109.149–111.329 | the index, not the cut |
| quiet point before | **108.88–108.92** (−31 dB) | the only clean join |
| lexical end | 111.33 | the aligner stops here |
| note body ends | **112.55** | the tail is 1.2 s of correct vowel |
| reverb ends | ≈113.2 | your second timestamp |
| second occurrence | **200.096–201.916** | the chorus repeats |
| free reference | `الْأَجْسَادِ` 97.03–98.81 | same take, correct final `د` |
| frames | 5727 total @ 25 fps | prefix 2718, max 2825 |

---

## 5. Friction log

Cost is measured where possible; otherwise marked *est.*

| # | friction | what it cost | fix |
|---|---|---|---|
| **F1** | The timestamp was a **section**, not a word (11 s → 4 s → 2.2 s). | 2 round-trips (~10 min) + a risk of aligning the wrong line. | Ask for the **lyric line**, not a time. Ship a locator clip. Let the aligner produce the index. |
| **F2** | The word occurs **twice** (chorus 1 and 2). "One word" was ambiguous. | If missed: a second GPU session (~15 min) or a rejected delivery. | The aligner lists occurrences for free. The card has an `occurrence` field; the review pack includes occurrence 2. |
| **F3** | Three different "ends": 111.33 / 112.55 / 113.2. | Picking the wrong one = cutting inside a sustained note. In Baghdad Moon this cost 3 rejected rounds. | Measure f0/RMS first (2 min). End at 112.70, never inside 111.33–112.55. |
| **F4** | **No `export_semantic`** on the take → no token stream. | The repair is blocked until a re-derive + bit-identity gate (~6 min GPU), and may be a dead end. | Make `export_semantic=true` the default for any take worth keeping. One flag. |
| **F5** | Provenance gap: original on **L4 (sm89)**, `audio_cpp_commit: null`; the only prefix binary is **T4 (sm75)**, from a *different* commit (`7d701047`). | The determinism gate can fail for reasons unrelated to the repair, and you cannot tell which. *est.* 1 session. | Record binary sha + commit + GPU in the sidecar. Build/keep a prefix binary per arch. Standardize generation of "repairable" takes on one GPU class. |
| **F6** | The `a01` LoRA is **not** in the run folder and **not** on HF. It lives in another bucket prefix (`OSTRIS…/mix_v3/a0.1`), referenced only in a log script. | *est.* 10–20 min of hunting + a 266 MB download. | Store the LoRA **URI + hash** in the sidecar (the hash is there; the URI is not). |
| **F7** | The link pointed at the **mp3**; the edit needs the **WAV**. | Starting from mp3 = decode/re-encode, no bit-identity, lossy consonants. | Always start from the run's 48 kHz WAV. |
| **F8** | Sibling takes have **different durations** (229 / 248 / 251 / 180 s), so timestamps do not transfer. | A naive "check the other takes" is wrong; each needs its own alignment (~2 min each). *est.* 6 min for 3. | Align siblings once, store `words.json` next to each take. Or skip the sibling check explicitly. |
| **F9** | Demucs stem is **44.1 kHz**, the mix is **48 kHz**. | A naive stem comp clicks or shifts. | Resample the stem to 48 kHz before comping (done in this prep). |
| **F10** | The aligner's box is early at holds and collapses long melismas (one 14.7 s word in the outro). | Wrong cut if you trust the box. | Never use the box as the cut; use f0 + RMS + the audition loop. |
| **F11** | Run names lie: `abu01_orig` is **not** the original take — it is the same song with `guidance=1.5, nar=0.5`. | A whole case can be built on the wrong file. *est.* 30+ min. | Name runs by their controls; the sidecar should say "delivered / experimental". |
| **F12** | Asking the ear to approve a 70 ms boundary **on the mix**. The instrumental bed fills the vocal break, so the ear hears the hamza and waw as merged and cannot answer. | One round-trip and a wrong mental model (“the words are fused”). | Approve boundaries on the **stem** (measure), not on the mix (listen). The human chooses the *strategy*, not the sample. |

### The one that did **not** cost anything

The poem's rhyme is `-dī`, so the same rhyme (with a final `د`) recurs several
times (`الْأَجْسَادِ`, `الْأَضْدَادِ`, `الْآبَادِ`, `سَوَادِ`) — presumably clean,
since the user reports one defect. Within 12 s of the defect there is a
same-singer reference. That is a free ear-calibration and a free candidate
filter — use it.

---

## 6. What worked, and should be standard

1. **Freeze first, listen second.** Hash + format + sidecar before any analysis.
2. **Forced alignment as an index** (2 min CPU): gives the word, its neighbours,
   **all occurrences**, and line cues. It does not give the cut.
3. **f0 + RMS map** on the vocal stem: gives the musical end, the quiet point,
   and the tail length. 6 s of code; catches the expensive mistake.
   Corollary: approve boundaries on the **stem**, never on the mix — the
   instrumental bed hides a 70 ms vocal break.
4. **A reference pair** from the same take (correct vs wrong consonant): the user
   confirms the defect class in 12 seconds.
5. **A clip pack with questions**, not a folder of files: 4 files, 4 questions.
6. **A card with 3 open fields** — everything else is pre-filled from the
   analysis. The user's time is judgment, not data entry.

---

## 7. What the Colab session needs (the gates)

> Do these **before** rendering anything. The order matters.

### Gate 0 — the right take
- the WAV `abu01_a01_3285212580.wav`, sha256 `30860a08…`;
- the **defaults** run (`20261113-044223`), not `abu01_orig`;
- the exact `lyrics.txt` / `style.txt` (hashes in `intake/hashes.txt`).

### Gate 1 — the assets
| asset | where | check |
|---|---|---|
| base model + VAE | `setup_colab.sh` | `4cf3fdff…` / `d4f4a05d…` |
| LoRA `a01` AR/NAR | `gs://…/OSTRIS_Arabic_Suno_Finetuning/arabic_instrumental_lora/mix_v3/a0.1/` | `d48109b3…` / `88f00bcb…` |
| prefix binary | `gs://…/arabmaqamrock/binaries/sm75-t4/prefix/audiocpp_cli_prefix_sm75` | sha `4117a46a…`, `strings` shows `semantic_prefix` |
| GPU | **T4** (sm75) | the only arch with a prefix binary |

`setup_colab.sh` does **not** install `a01`; stage it explicitly and verify the
hashes. If Colab gives an L4 or A100, there is **no prefix binary** for it —
either force T4 or build one (CPU build, not on the GPU box).

### Gate 2 — the token stream (decisive)
```
stop_after=semantic, seed 3285212580, cap 7250, export_semantic=true
expect: 5727 tokens, prefix 1156, truncated 0
```
then render the stream with `min=max=5727` and compare the WAV sha256.

- **Pass** (`30860a08…`): the stream is the take's; the repair can start.
- **Fail**: stop. Do not edit an unproven stream. Decide between: build an
  sm89 prefix binary and repeat on L4; use a new take; or keep the original.

**Expected risk: this is the most likely place for the session to die**, because
the original was L4 and the repair is T4. Budget one session for the gate alone.

### Gate 3 — the unit (the ear)
- U1 `108.88–112.70` (word + tail) — default;
- U2 `108.88–111.40` (word, tail kept) — fallback;
- occurrence 2: edit only if the ear says it is wrong.

### Gate 4 — the render
```
prefix 2718 (108.72 s), max 2825 (113.00 s), 8–16 seeds, export_semantic=true
```
One batch; comp U1 and U2 from the same candidates; no second render between
levels.

---

## 8. Time budget

| phase | human | machine |
|---|---:|---:|
| this preparation | 5 min (3 questions) | 2 min |
| Colab boot + assets | 10 min | 10–15 min |
| token gate (re-derive + render) | 2 min | ~6 min |
| batch (8–16 seeds) | — | 10–20 min |
| score + shortlist | 2 min | 2 min |
| audition + pick | 5–10 min | — |
| comp + QC | 2 min | 2 min |
| full listen + record | 10 min | — |
| **total** | **~30 min** | **~40 min** |

The preparation is **not** where the time goes. The time goes to (a) the token
gate, (b) the wrong unit, (c) seed grinding. All three are addressed above.

---

## 9. The ear answers (2026-11-14)

1. The final `د` is **/g/** (Egyptian ج) — confirmed against `الْأَجْسَادِ`.
2. Occurrence 2 (chorus 2) is **correct** — one edit, not two.
3. The tail 111.33–112.55 is **correct** — keep it.
4. Boundary: the machine measured a 70 ms glottal closure at 108.85–108.92
   (the mix masks it). The chart `review/gaps.html` shows the mix has 0 gaps and
   the vocal has 3. The word boundary itself is **voiced**; the only silent start
   is inside the previous word. Strategy: **B** (word, 109.10–111.35) default;
   **D** (whole line, real gap) fallback; **A** (fragment) last resort.

Closed: the card, the batch size (one region) and the strategy default (B).
Open: the token gate.
