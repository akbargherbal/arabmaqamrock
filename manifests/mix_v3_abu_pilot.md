# mix_v3 × Abu al-Ala — pilot

**Purpose:** first controlled listen of three `mix_v3` arms against the v3
baseline, on one vocal poem (`غير مجد في ملتي واعتقادي`). Same style, lyrics,
controls and seeds; only the LoRA alias changes. These are the **merged**
v3 × instrumental LoRAs, not the pure instrumental adapter.

**Source:** `gs://akbar-december-2024-backup/OSTRIS_Arabic_Suno_Finetuning/arabic_instrumental_lora/mix_v3/`
(`MANIFEST.json` built 2026-11-13). The arms are rank-concat merges of

- carrier: v3 arabmaqamrock final (step 5000), AR `3531bb91…`;
- donor: `arabic_instrumental_lora` final (ck5500), fused `cf6d44bb…`.

Alpha is baked into each file. Runtime `lora_ar_scale` / `lora_nar_scale` scales
the whole adapter, **not** the v3↔instrumental ratio; to change the ratio, use a
different arm.

| Alias | File pair under `a<alpha>/` | AR sha256 (first 12) | Effective AR share |
|---|---|---|---:|
| `v3` | published `arabmaqamrock-v3-{ar,nar}` | `3531bb9106d2` | 0% |
| `a01` | `v3instr_a0.1_{ar,nar}` | `d48109b3117b` | 8.9% |
| `a03` | `v3instr_a0.3_{ar,nar}` | `3a342098b6eb` | 22.8% |
| `a05` | `v3instr_a0.5_{ar,nar}` | `5bef39fe80d4` | 33.0% |

`alpha=0` is tensor-identical to v3, so the baseline needs no fifth merge.

## Fetch and verify

```bash
B=gs://akbar-december-2024-backup/OSTRIS_Arabic_Suno_Finetuning/arabic_instrumental_lora/mix_v3
mkdir -p loras/experiments/mix_v3
gsutil cp "$B/MANIFEST.json" loras/experiments/mix_v3/
for a in 0.1 0.3 0.5; do
  mkdir -p "loras/experiments/mix_v3/a$a"
  gsutil -m cp "$B/a$a/"* "loras/experiments/mix_v3/a$a/"
done

python3 - <<'PY'
import hashlib, json, pathlib
root = pathlib.Path("loras/experiments/mix_v3")
manifest = json.loads((root / "MANIFEST.json").read_text())
for arm in ("0.1", "0.3", "0.5"):
    spec = manifest["arms"][arm]
    for side in ("ar", "nar"):
        p = root / f"a{arm}" / f"v3instr_a{arm}_{side}.safetensors"
        got = hashlib.sha256(p.read_bytes()).hexdigest()
        assert got == spec[side], f"{p}: {got} != {spec[side]}"
        print(f"ok  a{arm} {side}")
PY
```

All six files are 139,501,720 B (AR) / 139,503,288 B (NAR).

## Header check — known false failure on NAR

`python3 plumbing/check_lora.py … --kind nar` **fails these files** with
`missing 4 keys: vae2llm/llm2vae`. That expectation describes NAR v9, which
carries four full replacement weights (396 tensors). A normal NAR LoRA — including
the published v3 NAR — has 392 tensors and no I/O weights. The mix NAR is
structurally normal: 392 tensors, 28 layers, rank 64, only the four I/O keys
"missing". AR passes the checker (392 tensors, rank 64).

Do not treat that NAR failure as a broken download; compare the sha256 against
`MANIFEST.json` instead.

## Run

```bash
python3 generate.py manifests/mix_v3_abu_pilot.json --dry-run
python3 generate.py manifests/mix_v3_abu_pilot.json --label mix_v3_abu_pilot
```

Dry-run plan: 4 songs / 8 tracks (~52 min on a T4), `cap=7250`, `cot=off`,
`guidance_scale=1.5`, `lora_nar_scale=0.5` — the same production controls as the
source poem manifest.

## Read the result

Pair `abu_<alias>_101` with `abu_v3_101` (and the same for seed 313). Judge:

1. Is the vocal still v3 (timbre, maqam behaviour) or did the donor bleed in?
2. Does the arrangement gain the instrumental LoRA's band/oud character?
3. At which alpha does the benefit stop and the vocal start to suffer?

If the answer is "no effect until 0.5, then damage", the useful range is narrow
and a new merge at 0.35–0.45 may be worth building. Record the verdict in this
file, not only in chat.
