#!/usr/bin/env python3
"""Single-shot model vetting for the BytePlus ModelArk coding plan.

Three small, hidden-test tasks (ABC length parsing, Arabic word splitting,
exact-format duration report). No retries: one request per cell, code extracted
from the first ```python block, scored by pytest.

Each run records latency and token usage. `cost_usd` is the *list-price
equivalent* (off-peak standard API prices, USD per 1M tokens) so models can be
compared on quota burn even though the plan itself is a subscription.

Usage:
    python3 harness.py                # all models, all tasks
    python3 harness.py deepseek-v4.1-flash glm-5.3-flash   # subset

Env:
    DEEPSEEK_API_KEY   optional; enables the direct-DeepSeek control arm.
    BYTEPLUS_KEY_FILE  default ~/.secrets/byteplus-key
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.abspath(__file__))
TASKS = ["t1", "t2", "t3"]
TASK_FILES = {"t1": "t1_abc_length", "t2": "t2_arabic_words", "t3": "t3_cap_report"}
BYTEPLUS = "https://ark.ap-southeast.bytepluses.com/api/coding/v3/chat/completions"
DEEPSEEK = "https://api.deepseek.com/v1/chat/completions"

KEY_FILE = os.path.expanduser(os.environ.get("BYTEPLUS_KEY_FILE", "~/.secrets/byteplus-key"))

# label, url, api key, request model, $in/M, $out/M  (None price = unknown)
TARGETS = [
    ("deepseek-v4.1-flash", BYTEPLUS, "bp", "deepseek-v4.1-flash", 0.15, 0.60),
    ("deepseek-v4-flash", BYTEPLUS, "bp", "deepseek-v4-flash", 0.44, 1.32),
    ("deepseek-v4-pro", BYTEPLUS, "bp", "deepseek-v4-pro", 1.32, 3.96),
    ("ark-code-latest", BYTEPLUS, "bp", "ark-code-latest", None, None),
    ("glm-5.3-flash", BYTEPLUS, "bp", "glm-5.3-flash", 0.15, 0.50),
    ("glm-5.2", BYTEPLUS, "bp", "glm-5.2", 1.40, 4.40),
    ("dola-seed-2.0-code", BYTEPLUS, "bp", "dola-seed-2.0-code", 0.50, 3.00),
    ("dola-seed-2.0-pro", BYTEPLUS, "bp", "dola-seed-2.0-pro", 0.50, 3.00),
    ("bytedance-seed-code", BYTEPLUS, "bp", "bytedance-seed-code", 0.25, 2.00),
    ("kimi-k2.5", BYTEPLUS, "bp", "kimi-k2.5", 0.50, 3.00),
]

# Control arm: the same model on DeepSeek's own API, for provider comparison.
if os.environ.get("DEEPSEEK_API_KEY"):
    TARGETS.insert(0, ("deepseek-flash (direct)", DEEPSEEK, "ds", "deepseek-flash", 0.15, 0.60))

SYS = ("You are a senior Python engineer. Follow the spec exactly. "
       "Reply with exactly one ```python fenced code block containing the complete file "
       "and nothing else - no prose, no tests.")


def api_key(which: str) -> str:
    if which == "bp":
        with open(KEY_FILE) as f:
            return f.read().strip()
    return os.environ["DEEPSEEK_API_KEY"]


def extract(text: str) -> str:
    m = re.search(r"```(?:python|py)?[ \t]*\n(.*?)```", text, re.S)
    return (m.group(1) if m else text).strip() + "\n"


def call(url, key, model, prompt):
    body = json.dumps({
        "model": model,
        "messages": [{"role": "system", "content": SYS},
                     {"role": "user", "content": prompt}],
        "max_tokens": 6000,
        "temperature": 0,
    }).encode()
    req = urllib.request.Request(url, data=body, headers={
        "Authorization": "Bearer " + key, "Content-Type": "application/json"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            d = json.load(r)
        if "error" in d:
            return None, time.time() - t0, {"error": d["error"]}
        ch = d["choices"][0]
        return ch["message"], time.time() - t0, {
            "usage": d.get("usage", {}),
            "finish": ch.get("finish_reason"),
            "resolved": d.get("model"),
        }
    except urllib.error.HTTPError as e:
        try:
            err = json.load(e)
        except Exception:
            err = {"raw": e.read()[:300].decode("utf-8", "replace")}
        return None, time.time() - t0, {"error": err}
    except Exception as e:
        return None, time.time() - t0, {"error": repr(e)}


def score(label, task, msg, meta, dt, pin, pout):
    rec = {"model": label, "task": task, "secs": round(dt, 1),
           "resolved": meta.get("resolved"), "finish": meta.get("finish")}
    if msg is None:
        rec.update(ok=False, fail_reason="api_error", error=str(meta.get("error"))[:300])
        return rec
    usage = meta.get("usage") or {}
    it, ot = usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)
    rec.update(in_tok=it, out_tok=ot,
               reasoning_tok=(usage.get("completion_tokens_details") or {}).get("reasoning_tokens", 0))
    if pin is not None:
        rec["cost_usd"] = round(it / 1e6 * pin + ot / 1e6 * pout, 6)

    text = msg.get("content") or ""
    wd = os.path.join(ROOT, "runs", label.replace(" ", "_"), task)
    shutil.rmtree(wd, ignore_errors=True)
    os.makedirs(wd)
    with open(os.path.join(wd, "solution.py"), "w") as f:
        f.write(extract(text))
    with open(os.path.join(wd, "raw.txt"), "w") as f:
        f.write(text)
    shutil.copy(os.path.join(ROOT, "tasks", task, f"test_{task}.py"), wd)

    p = subprocess.run([sys.executable, "-m", "pytest", "-q", "--no-header", "-x"],
                       cwd=wd, capture_output=True, text=True, timeout=120)
    rec["ok"] = p.returncode == 0
    if not rec["ok"]:
        lines = [ln for ln in p.stdout.splitlines() if ln.strip()]
        rec["fail_reason"] = " | ".join(lines[-3:])[:300]
    return rec


def run_one(target, task):
    label, url, key, model, pin, pout = target
    with open(os.path.join(ROOT, "tasks", TASK_FILES[task] + ".md")) as f:
        prompt = f.read()
    msg, dt, meta = call(url, api_key(key), model, prompt)
    return score(label, task, msg, meta, dt, pin, pout)


if __name__ == "__main__":
    wanted = set(sys.argv[1:])
    targets = [t for t in TARGETS if not wanted or t[0] in wanted]
    jobs = [(t, task) for t in targets for task in TASKS]

    out = []
    with ThreadPoolExecutor(6) as ex:
        futures = [ex.submit(run_one, t, task) for t, task in jobs]
        for f in futures:
            r = f.result()
            out.append(r)
            print(f"{r['model']:<24} {r['task']}  {'PASS' if r['ok'] else 'FAIL'}  "
                  f"{r['secs']:>6}s  tok={r.get('in_tok', '?')}/{r.get('out_tok', '?')}  "
                  f"{r.get('fail_reason', '')[:70]}", flush=True)
    with open(os.path.join(ROOT, "results.json"), "w") as f:
        json.dump(out, f, indent=1)
