# Easygoing Eagle — Control Room

**Status:** interactive educational explainer. No audio, no generation, no backend.
**Source:** [`docs/easygoing-eagle-controls-ar.md`](../easygoing-eagle-controls-ar.md) and
[`manifests/easygoing-eagle.json`](../../manifests/easygoing-eagle.json).
**Files:** [`easygoing-eagle-console.html`](easygoing-eagle-console.html) ·
[`preview-1440.png`](preview-1440.png) · [`preview-390.png`](preview-390.png) ·
[`preview-first-screen.png`](preview-first-screen.png)

Open the HTML file directly. It needs no build step.

---

## The idea

A mixing desk is the interface, not a decoration. The signal path of the model —
**Plan → Voice (AR) → Render (NAR)** — becomes three modules on one faceplate.
Every control sits on the stage that consumes it, so the learner reads the routing
by looking at the desk instead of memorising a table.

The desk opens on **e03_cfg20**: guidance moved from 1.0 to 2.0. The score (`v_a`)
is attached, so the Planning module is visibly locked. That single state teaches
three things at once:

1. guidance lives on the voice, not on the plan;
2. `1.0` is a bypass notch, not a quiet setting;
3. an external score puts the ABC knobs to sleep.

The second key state — **e09_plan**, the only take with no score — is the moment
the Planning module wakes up. The interactive release/attach button lets the
learner move between those two states without leaving the desk.

## What the learner can do

| Action | What it teaches |
|---|---|
| Select a take slot | Loads that take's resolved values, lights only the stage(s) it touches, and updates the readout and the three story columns. |
| Drag a knob or fader / use arrow keys | Puts the desk in a **custom** state. The story switches from the take's question to that control's job, so the learner sees what the control does on its own. |
| Release or attach `score v_a` | Demonstrates the plan/score switch. Releasing wakes `abc_*`; attaching locks them. |
| Try `abc_*` while the score is attached | Shows an explicit **Refused** message instead of silently ignoring the move. |
| Deal and reveal the blind pair | Demonstrates the listening protocol: describe the difference first, then reveal which two settings produced it. This is a paper exercise; no audio is played. |

The scope is deliberately limited to teaching. The page does not edit the manifest,
generate a song, play audio, or print a runnable command.

## Why this metaphor

- **One-to-one mapping.** Three model stages → three physical modules; no invented
  categories.
- **Defaults are engraved.** A green notch on every fader/knob marks the default.
  The brass cap is the current value. The difference is read spatially.
- **Limits are physical.** The red hatch above LoRA `1.0` is the guard rail; the
  hatched amber tail above guidance `2.0` is the "stiffer" zone. These are the real
  constraints from the source document, not decoration.
- **A locked module is louder than a warning.** The Planning module is dimmed,
  hatched, tagged `SCORE LOCK`, and carries the actual `v_a` score excerpt. The rule
  is visible before it is read.
- **The sweep stays on the page.** Nine take slots sit under the desk, so the
  comparison method ("one variable at a time") never leaves the screen.

## Page anatomy

| Region | Job |
|---|---|
| Rail | Interactive status, take counter, context. |
| Intro | The claim: a listening test with the sound removed. The constant (lyric, style, seed) vs the variable (one control). |
| Console | Planning / Voice / Render modules, the readout strip, the legend. |
| Story band | *what moved · listen for · do not expect* for the selected take or the touched control. |
| Sweep | Nine takes; each slot shows the stage touched and the one value that moved. |
| Blind A/B | The listening method, made physical. Deal a pair, commit to a description, then reveal. |
| Hard stops | The four pre-flight refusals from the source doc. |

## Interaction details

- **Real range inputs.** The custom knobs and faders use transparent
  `<input type="range">` elements over the hardware, so keyboard, touch and screen
  readers work without duplicating the physics.
- **Custom state.** Any manual move deselects the stock take. The readout then
  compares every control against its default, and reports how many are away from it.
- **Stage lighting.** A thin brass edge and an amber dot mark the module(s) involved
  in the current state; untouched stages stay plain.
- **Readout.** Shows the take name (or `custom_desk`), the control(s) away from
  default, and the cost: CFG on/off, score lock or planner active, render passes.
- **Score refusal.** The message is announced with `role="status"` and the value
  snaps back. `abc_*` is never silently ignored.
- **Blind deck.** The pair is random, hidden on deal, and revealed on click. The
  card shows the two take IDs and the changed control, not a "winner".
- **Reduced motion.** All transitions are disabled under
  `prefers-reduced-motion: reduce`.

## Design tokens

- **Room:** umber-black `#140f0d`, with warm and faint green room light.
- **Faceplate:** aged bone `#d8cbb5` → `#e8ddca`; ink `#241c16`.
- **Metal:** brass `#b07c42` / `#e2b577`; copper `#9c4a32`.
- **Signals:** verdigris `#4e7b6b` = default notch; amber `#dfa23f` = active lamp;
  rust `#a93a2c` = lock / guard.
- **Type:** Bodoni Moda (operatic display and take names), Archivo (UI and labels),
  Noto Naskh Arabic (the lyric), IBM Plex Mono (ABC score and readout values).
- **Physical cues:** screws, engraved hairlines, bevels, tick arcs, cap shadows,
  a dark score plate. No rounded SaaS cards; radius stays at 2–6 px except the
  console shell.

## Files

- `easygoing-eagle-console.html` — the whole deliverable: Tailwind CDN, Google Fonts,
  CSS and JavaScript in one file.
- `preview-1440.png` — initial e03 state at desktop width.
- `preview-390.png` — initial e03 state at mobile width.
- `preview-first-screen.png` — the intro and the top of the console.

The values shown in the desk mirror `manifests/easygoing-eagle.json`. The prose
follows the explanations in `docs/easygoing-eagle-controls-ar.md`.
