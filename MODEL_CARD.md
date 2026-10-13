# Model card

The published weights this repo uses. Both are LoRAs for **YuE2** (3B), consumed by
**audio.cpp** (GGUF runtime) — *not* `transformers`. Both are **non-commercial**
derivatives of YuE2.

## ArabMaqamRock v3 — [`akbargherbal/arabmaqamrock-yue2-lora`](https://huggingface.co/akbargherbal/arabmaqamrock-yue2-lora)

Arabic maqam rock (four maqams; symphonic/orchestral rock, deep male vocals).

| | |
|---|---|
| **Trigger word** | `arabmaqamrock` (prepended automatically by `generate.py`) |
| AR adapter | `arabmaqamrock-v3-ar.safetensors` — sha256 `3531bb9106d2292eefe58eabe11ec08bb7dddc69554f2b016dc9f13f711fab18` |
| NAR adapter | `arabmaqamrock-v3-nar.safetensors` — sha256 `a7eabcadb22146048bcb5e65d04828ee9454559523ca161bd38c06060deb0cae` |
| Rank | 32 / alpha 32 (EMA weights) |
| Trained to | step 5000 |
| Load | `yue2.ar_lora` + `yue2.nar_lora`, scale 1.0, `cot=off` (defaults in `run_one.sh`) |

Honest quality note: the v3 final scored **4/5** in listening — strong
timbre/arrangement/style match, but "flat / generic" melodic inventiveness. A style
adapter with `cot=off` cannot make the composer more inventive; that is a settings /
prompt / selection problem (see the parent repo's v3 "spice" sweep).

## Quran pronunciation — [`akbargherbal/quran-pronunciation-yue2-lora`](https://huggingface.co/akbargherbal/quran-pronunciation-yue2-lora)

A **diction/pronunciation** adapter trained on Quran recitation (AHH-filtered, 3
reciters). **No trigger word.** Released for research / dialect work.

| | |
|---|---|
| AR adapter | `quran-pronunciation-ar.safetensors` — sha256 `c9305c35798c5453a54419fd54c8a74543e9f40d8c95481e02a7af647269ce28` |
| NAR adapter | `quran-pronunciation-nar.safetensors` — sha256 `2097fd6eb9ec8728f34441e16758c71cec7df2d79ef1a449e1eba95f79408159` |
| Rank | 32 / 32, AR + NAR jointly (EMA weights) |
| Trained to | 28,467 steps (3 epochs) |

Honest quality note: the diction gain is **not demonstrated** — in a blinded compare the
rubric saturated, and throat-letter fidelity (ع/ح/ر) was "present but lightened". It was
**shelved** for the maqam-rock project and is not a validated recitation model.

## Using them

`generate.py` loads the v3 pair by default from `loras/`. To also fetch the Quran
adapter and use it in a batch:

```bash
hf download akbargherbal/quran-pronunciation-yue2-lora \
  quran-pronunciation-ar.safetensors quran-pronunciation-nar.safetensors --local-dir loras/quran
```

```json
"loras": { "quran": { "ar": "loras/quran/quran-pronunciation-ar.safetensors",
                      "nar": "loras/quran/quran-pronunciation-nar.safetensors" } }
```

## License

**CC-BY-NC-4.0 — non-commercial only.** Inherited from `m-a-p/YuE2-3B` via
`audio-cpp/Yue2-3B-GGUF`. The repository's own *code* is MIT (see [LICENSE](LICENSE));
the weights are not.
