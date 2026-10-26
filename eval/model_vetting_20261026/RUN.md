# BytePlus ModelArk coding plan — model vetting (2026-10-26)

Which models on the new BytePlus ModelArk subscription are worth using, judged
against the model already in daily use: `deepseek-flash` on DeepSeek's own API
(`DEEPSEEK_API_KEY`, configured before this plan existed).

## Method

Three self-contained Python tasks, each with a hidden pytest file the model never
sees. One request per cell, no retries, `temperature: 0`, `max_tokens: 6000`. The
reply must be a single fenced code block; it is written to `solution.py` and
scored by running the tests.

| Task | What it exercises |
|---|---|
| `t1_abc_length` | spec compliance — ABC note-length grammar (`2`, `/`, `/2`, `//`, `3/2`, `7/`), `ValueError` on malformed input |
| `t2_arabic_words` | Unicode precision — split Arabic lyrics, preserve harakat, treat `، ؛ ؟ ; : …` as separators, keep `don't` / `maqam-rock` whole |
| `t3_cap_report` | exact output format — duration cap report, round-to-nearest-10, `.5` away from zero, `ValueError` on unknown quantile |

All three are drawn from this project's own domain (ABC score handling, Arabic
lyric processing, the `duration_cap.py` report line), not generic interview tasks.

`cost_usd` is the **list-price equivalent** at off-peak standard rates
(USD / 1M tokens), because the plan itself is a subscription: the metric that
matters is how fast a model burns quota per unit of work, not the invoice.

## Results

Single shot, 3 tasks per model. Cost is per successful task, relative to the
control.

| Model | Pass | $/pass | vs control | Latency | Out tok | Resolves to |
|---|---|---|---|---|---|---|
| `deepseek-flash` (control, DeepSeek API) | 3/3 | 0.00103 | 1.0× | 31 s | 4,944 | `deepseek-flash` |
| `deepseek-v4.1-flash` | 3/3 | 0.00105 | 1.0× | 29 s | 5,012 | `deepseek-v4-1-flash` |
| `deepseek-v4-flash` | 3/3 | 0.00396 | 3.8× | 75 s | 8,729 | `deepseek-v4-flash` |
| `deepseek-v4-pro` | 3/3 | 0.00769 | 7.4× | 93 s | 5,548 | `deepseek-v4-pro` |
| `ark-code-latest` | 3/3 | n/a | n/a | 34 s | 7,316 | `auto` (opaque) |
| `bytedance-seed-code` | 2/3 | 0.00872 | 8.4× | 134 s | 8,592 | `dola-seed-2.0-lite` |
| `dola-seed-2.0-pro` | 3/3 | 0.00997 | 9.6× | 170 s | 9,803 | `dola-seed-2.0-pro` |
| `kimi-k2.5` | 3/3 | 0.01047 | 10.1× | 155 s | 10,307 | `dola-seed-2-0-pro` |
| `glm-5.3-flash` | 2/3 | 0.00512 | 5.0× | 464 s | 20,320 | `glm-5-3-flash` |
| `glm-5.2` | 2/3 | 0.02830 | 27.4× | 160 s | 12,593 | `glm-5.2` |
| `dola-seed-2.0-code` | 3/3 | 0.04328 | 41.8× | 560 s | 43,112 | `dola-seed-2.0-code` |

Total sweep cost: **$0.32**.

## Findings

**`deepseek-v4.1-flash` is the same model experience as the control.** Same
score, near-identical prompt token counts (308/323/279 — identical tokenizer),
same output volume, same price, marginally faster. Moving the default onto the
subscription is a no-op for quality and cost.

**Nothing on the plan beats it.** Every alternative that matched the score cost
4–42× more per successful task. `dola-seed-2.0-code` produced 43k output tokens
for three files that need ~40 lines each; at $3/M output that is the single most
expensive way to write Python available on this plan. `glm-5.3-flash` timed out
at 280 s on one task and needed 100 s on the others, which is unusable
interactively regardless of price.

**`ark-code-latest` is unbudgetable.** It passes and is fast, but it reports as
`auto`, has no published price, and its prompt-token signature matches the
DeepSeek family exactly — almost certainly a router onto a DeepSeek Flash
backend. Fine to use, impossible to reason about.

**Aliases are not what they say.** `kimi-k2.5` is served by
`dola-seed-2-0-pro`; `bytedance-seed-code` is served by `dola-seed-2.0-lite`;
`dola-seed-2.0-lite` requested *directly* returns
`404 UnsupportedModel ... does not support the coding plan feature`. Model
names in the picker cannot be taken at face value on this endpoint.

**Failure modes are silent, not loud.** `glm-5.2` implemented the rounding with
`Decimal('10').quantize()`, which rounds to *integers*, not tens, and returned
`cap=2775` instead of `2750` — a confident, plausible, wrong answer (see
`failures/glm-5.2__t3__solution.py`). `bytedance-seed-code` dropped `;` and `:`
from its separator class and split `a,b;c:d` into three tokens instead of four
(`failures/bytedance-seed-code__t2__solution.py`). Neither model signalled doubt.

## Config decision

Pruned to `deepseek-v4.1-flash` alone. Every removed entry either scored worse,
cost 3.8–41.8× more per pass, or could not be priced. If a harder task ever
defeats it, the escalation tier to re-add is:

```json
"deepseek-v4-pro": {
  "name": "deepseek-v4-pro",
  "limit": { "context": 1024000, "output": 65536 }
}
```

It tied on quality at 7.4× the cost, so it was not worth carrying by default,
but these three tasks are too small to prove it is *never* better on long,
multi-file work.

## Caveats

- n=1 per cell on three short tasks. Treat as directional: the 4–42× cost gaps
  are far outside noise, the 3/3-vs-3/3 ties are not.
- Every call was a cache miss. Real sessions reuse a system prompt, so prefix
  caching ($0.003/M vs $0.15/M input) makes the DeepSeek path cheaper than these
  figures suggest.
- The sweep ran off-peak. BytePlus doubles prices Mon–Fri 09:00–12:00 and
  14:00–18:00 UTC+8, so peak-hour ratios shift but the ranking does not.
- Not covered: image input, long context, and multi-turn tool-call loops — the
  three places cheap models usually break.

## Reproduce

```bash
export DEEPSEEK_API_KEY=...          # optional control arm
python3 eval/model_vetting_20261026/harness.py                     # all models
python3 eval/model_vetting_20261026/harness.py deepseek-v4.1-flash # subset
```

The BytePlus key is read from `~/.secrets/byteplus-key` (override with
`BYTEPLUS_KEY_FILE`); it is never stored in the repo.

```
harness.py            runner (pricing table lives here)
tasks/*.md            the three specs given to the model
tasks/tN/test_tN.py   hidden tests, never shown to the model
results.json          raw per-run records (latency, tokens, cost, verdict)
summary.csv           one row per model
failures/             the wrong-but-plausible solutions kept as evidence
```
