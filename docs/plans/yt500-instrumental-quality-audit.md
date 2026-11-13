# YT500 instrumental — generation and duration-gate audit

**Snapshot:** 2026-11-11, **full corpus** (489/489 songs have a take).
**Machine-readable copy:** `outputs/YT500/generation/quality_audit_duration.json`
(one object per failing take: name, title, artist, nominal, WAV/MP3 length,
delta, bucket, cap, seed, run, score hash, MP3 URI).
**Gate (plan §8.3):** generated duration within **±15%** of the score's
`nominal_seconds`. Nominal and source `duration_s` agree to <1% on every row,
so this is an audio-length problem, not a score-parsing problem.

## Headline

| Question | Answer |
|---|---|
| Songs generated | **489 / 489** (driver `--status`: `done=489 pending=0 mismatches=0`) |
| Rendering failures (`Exit status != 0`, bad sidecar) | **0** |
| Takes with a marker but no uploaded MP3 | **2** (`yt500-0129`, `yt500-0159`), both re-rendered successfully |
| Duration gate (within ±15%) | **460 pass / 29 fail → 94.1% pass, 5.9% fail** |
| Severe short (≤ −30%, likely early EOS) | **7** |
| Short (−15% … −30%) | **15** |
| Long (+15% … +18.4%) | **7** |
| MP3 < 100 KB / zero-byte | **0 / 0** (smallest 0.35 MB, median 6.5 MB) |
| Score-hash mismatches | **0** (1,554 run score copies checked) |
| Recipe drift | **none** — one `style_sha256`, `cot=full`, AR/NAR 0.85/1.0, defaults+loras identical to manifest 18 in every run |

The 6 songs with no take are out of scope by design: **4 `no-abc`** (no parsed
score) and **2 `inline-key`** (deferred, see the plan §1). They are not failures
of yesterday's run.

## Why the file count looks like ~470

GCS holds **491 MP3 objects for 489 unique songs**, because `yt500-0129` and
`yt500-0159` were rendered three times each after their first MP3 did not
upload. Per session run:

| Run | Takes marked | MP3s | Note |
|---|---:|---:|---|
| `20261110-083615_yt500inst` | 12 | 12 | pilot |
| `20261110-085847_yt500inst` | 8 | 8 | killed early (SIGTERM) |
| `20261110-092455_yt500inst` | 2 | 2 | killed early (SIGTERM) |
| `20261110-095521_yt500inst` | 376 | 374 | bulk; 2 markers had no MP3 |
| `20261110-183143_yt500inst` | 57 | 57 | bulk continuation |
| `20261110-200631_yt500inst` | 36 | 36 | bulk + MP3 retries |
| `20261110-205443_yt500inst` | 2 | 2 | final retry, finished 20:58Z |
| **Total** | **493** | **491** | **489 unique songs** |

The three large session dirs alone contain 374 + 57 + 36 = **467 MP3s**, which
matches the "around 470" impression if the four small/pilot dirs are left out.
Browsing all seven gives 491 files. Deduplicating by song name gives the true
**489**. There is no missing audio beyond the two original retries.

## Duration-gate failures (29 of 489)

| Bucket | Count | Meaning |
|---|---:|---|
| Severe short (≤ −30%) | **7** | almost certainly early EOS/truncation; re-render |
| Short (−15% … −30%) | 15 | borderline; decide per track |
| Long (+15% … +18.4%) | 7 | arrangement runs past the score; borderline |
| Within ±15% (pass) | 460 | — |

All 29 failures are **batch-path** takes. Two are new relative to the mid-run
snapshot (`yt500-0165` severe short, `yt500-0302` long); the other 27 were
already catalogued and still fail.

### Failing takes

| # | Bucket | Track | Title / artist | Nominal | WAV | Δ | cap | seed | Run |
|---:|---|---|---|---:|---:|---:|---:|---|---|
| 1 | severe short | `yt500-0165-4ehTSqSPvgk` | Ben Idayya — Majid Al Mohandis | 339s | 14.4s | -95.8% | 9986 | 1690371890 | `20261110-200631_yt500inst` |
| 2 | severe short | `yt500-0034-kyxGsD-eP1I` | Andou Zine — Asma Lmnawar | 332s | 84.9s | -74.4% | 9804 | 1314355762 | `20261110-183143_yt500inst` |
| 3 | severe short | `yt500-0623-pbWDY8LbVVk` | Alawah — Melhim Zain | 310s | 97.6s | -68.5% | 9240 | 558678698 | `20261110-095521_yt500inst` |
| 4 | severe short | `yt500-0642-iMAe5sh1u7k` | Majnouni — Waleed Al Shami | 280s | 92.9s | -66.8% | 8500 | 1932839153 | `20261110-095521_yt500inst` |
| 5 | severe short | `yt500-0103-58APpZMC2Yw` | Law Tearafou — Elissa | 346s | 193.2s | -44.3% | 10163 | 2555150370 | `20261110-095521_yt500inst` |
| 6 | severe short | `yt500-0118-hIPoRdfbsYs` | Ykhalili Albak — Najwa Karam | 400s | 241.6s | -39.6% | 11510 | 2700908498 | `20261110-095521_yt500inst` |
| 7 | severe short | `yt500-0290-tf2PD_IxjmM` | Olay Jaya — Assi El Hallani | 323s | 208.2s | -35.6% | 9576 | 970013721 | `20261110-095521_yt500inst` |
| 8 | short | `yt500-0259-UeL9kJ4uGyY` | Ana Ana — Rashed Al Majed | 405s | 300.0s | -26.0% | 11633 | 3096277166 | `20261110-095521_yt500inst` |
| 9 | short | `yt500-0452-FqltwFT25fM` | Tabaan — Rabeh Saqer | 242s | 180.0s | -25.5% | 7541 | 3098657591 | `20261110-095521_yt500inst` |
| 10 | short | `yt500-0040-j9eZtAjA1oE` | Hattan — Majid Al Mohandis | 395s | 300.0s | -24.1% | 11381 | 1779747039 | `20261110-095521_yt500inst` |
| 11 | short | `yt500-0685-MVLg42W7b18` | Maaad Tesaal — Rabeh Saqer | 294s | 223.7s | -23.9% | 8849 | 1208020853 | `20261110-095521_yt500inst` |
| 12 | short | `yt500-0261-byK0dlhokOA` | Lealy Nahary — Amr Diab | 273s | 213.0s | -21.9% | 8315 | 3722330835 | `20261110-183143_yt500inst` |
| 13 | short | `yt500-0330-zQ9Bq4yU9k8` | Sabiya — Asma Lmnawar | 251s | 196.6s | -21.7% | 7772 | 1493452708 | `20261110-095521_yt500inst` |
| 14 | short | `yt500-0130-r99RZ4ViteM` | Hask Wejudi — Rashed Al Majed | 292s | 231.3s | -20.7% | 8796 | 3951800241 | `20261110-183143_yt500inst` |
| 15 | short | `yt500-0295-AE9BTVpyuuQ` | Taaref Sheno Ahebak — Assi El Hallani | 254s | 201.8s | -20.6% | 7856 | 741512351 | `20261110-095521_yt500inst` |
| 16 | short | `yt500-0433-Atx7biRfhzU` | Baasha Tafasilak — Najwa Karam | 314s | 249.7s | -20.6% | 9358 | 3335575890 | `20261110-095521_yt500inst` |
| 17 | short | `yt500-0279-wYk-JyifeRE` | Entebeh — Majid Al Mohandis | 276s | 224.1s | -18.8% | 8403 | 1565258927 | `20261110-095521_yt500inst` |
| 18 | short | `yt500-0355-3Uei9m0RpJQ` | DeeJay — Balqees | 278s | 227.0s | -18.5% | 8462 | 4230957805 | `20261110-095521_yt500inst` |
| 19 | short | `yt500-0390-faLLKMdiEHs` | Shou Hal Hala — Najwa Karam | 320s | 262.8s | -17.9% | 9508 | 4196336553 | `20261110-095521_yt500inst` |
| 20 | short | `yt500-0640-VnYiVwJhG0Q` | Ya Layem El Mshtag — Nawal El Kuwaitia | 295s | 244.8s | -17.1% | 8885 | 2424802295 | `20261110-095521_yt500inst` |
| 21 | short | `yt500-0657-l5ldxD5llBU` | Law Bass Ta3ref — Najwa Karam | 331s | 274.7s | -16.9% | 9769 | 4045737294 | `20261110-095521_yt500inst` |
| 22 | short | `yt500-0202-pAFV9RT-yrA` | 40 — Assi El Hallani | 211s | 179.3s | -15.2% | 6786 | 3979204925 | `20261110-095521_yt500inst` |
| 23 | long | `yt500-0021-7Rx6wDS286s` | Aa Baly Habibi — Elissa | 395s | 455.4s | +15.2% | 11384 | 2579198127 | `20261110-095521_yt500inst` |
| 24 | long | `yt500-0652-ItMVUZ3RGhM` | Kabad Bad — Melhim Zain | 379s | 438.9s | +15.8% | 10972 | 655827854 | `20261110-095521_yt500inst` |
| 25 | long | `yt500-0302-uTTsZSjIMxI` | Khalow — Majid Al Mohandis | 370s | 429.8s | +16.2% | 10744 | 1791543491 | `20261110-200631_yt500inst` |
| 26 | long | `yt500-0611-2Jr_2H652Vc` | Ma A'd Tesa'l — Rabeh Saqer | 358s | 418.1s | +16.8% | 10453 | 2612196988 | `20261110-095521_yt500inst` |
| 27 | long | `yt500-0018-dWahuREerq0` | Asaad Wahda — Elissa | 335s | 394.8s | +17.9% | 9870 | 2963975505 | `20261110-095521_yt500inst` |
| 28 | long | `yt500-0308-bNuW5JWv-Bg` | Ehsen Eldhan — Rabeh Saqer | 329s | 389.3s | +18.2% | 9733 | 1658642730 | `20261110-183143_yt500inst` |
| 29 | long | `yt500-0111-Rh9M8EBs6bw` | Mabrouk — Balqees | 326s | 386.0s | +18.4% | 9649 | 2947375897 | `20261110-095521_yt500inst` |

Per-take artifacts live at
`gs://akbar-december-2024-backup/arabmaqamrock/runs/<run>/<name>_<seed>.{mp3,json,_time.txt}`.
`<name>_<seed>.json` carries `cap`, `wav_bytes`, `wav_duration_s`,
`wav_sha256`, `abc_sha256`. Every row has a cap; on the short takes the cap is
far above the output length.

## Observations

- **The cap is not binding.** Every short take has `cap` well above the
  missing length (e.g. `0034`: 9,804 semantic frames ≈ 392s vs 84.9s output;
  `0165` rendered only 14.4s). The engine stopped early (likely EOS) rather
  than hitting the request cap.
- **Two exact round lengths.** `0040` and `0259` are exactly 300.0s and
  `0452` exactly 180.0s. MP3 `ffprobe` durations match, so these are real.
  Round 5:00/3:00 outputs suggest a possible internal stop/section boundary,
  worth checking in the engine before re-rendering.
- **The newest severe short is extreme.** `yt500-0165` (14.4s of a 339s score)
  came from the `200631` run with cap 9986 (≈400s); inspect that sidecar and
  request before re-rendering.
- **All failures are batch takes** (`engine: "batch"`); none from the
  per-track `generate.py` pilot runs. The pilot is only n=22, so this may be
  coincidence, but it is consistent with the earlier note that length varies
  with seed and early EOS is silent.
- **`truncated` is never set** by `write_marker()` in
  `plumbing/run_yt500_generation.py`; the field is always `None`. The §11
  "list `truncated: true/maybe`" step cannot currently work. The JSON snapshot
  adds an **inferred** `truncated_inferred: true` for the 22 short rows.
- **Long takes are mild** (+15…+18.4%) and likely need a slightly tighter
  arrangement; the short ones are the real defect.
- **Everything else passes.** 491 MP3s are all > 100 KB (min 0.35 MB, median
  6.5 MB), 0 score-hash mismatches across 1,554 run score copies, and every
  run's `input.json` `defaults`/`loras` is byte-equal to manifest 18, with one
  unique `style_sha256` (`bddaf3f9…`) and `cot=full`.

## Reproduce

```bash
python3 plumbing/run_yt500_generation.py --status --work-dir /tmp/yt500_status
# snapshot JSON (name/title/artist/nominal/wav/delta/cap/seed/run/mp3)
jq -r '.tracks[] | [.name,.bucket,.delta_pct,.cap,.seed,.run] | @tsv' \
  outputs/YT500/generation/quality_audit_duration.json
```

The audit selects, per song, the take that has an uploaded MP3 (newest run on
ties), joins it to `outputs/YT500/generation/index.json` on `name` for
`nominal_seconds`, and checks `abc_sha256` against the corpus. `wav_duration_s`
is from the take sidecar; the 7 severe shorts and 2 long rows were verified with
`ffprobe` on the actual MP3s and match to <0.2%.

## Next steps

1. **Re-render the 7 severe shorts** with a fresh seed (keep the cap; probe
   `yt500-0165` first because 14.4s suggests an immediate EOS or a broken
   request). Add them to `work/yt500_gen/retry_names.txt`; the driver treats
   listed names as pending without touching the old GCS markers.
2. **Decide the 22 borderline takes** (15 short + 7 long): accept as-is or
   re-render. They are 4.5% of the corpus; re-rendering costs ~30–40 min.
3. **Fix the `truncated` flag** in the batch marker writer so the §11 audit is
   meaningful (e.g. flag when `wav_duration_s < 0.85 * nominal`).
4. **Publish the final index** (`generation_index.jsonl`, plan §11) once the
   outlier re-renders are settled; the audio and recipe gates are otherwise
   complete.
5. **Listening gates remain open.** Vocal/arrangement checks are not automated;
   audition a stratified sample before accepting the corpus.

## See also

- `docs/plans/yt500-instrumental-generation.md` §8.3 (gates), §11 (audit)
- `docs/plans/yt500-instrumental-run-log.md` (living run log)
- `outputs/YT500/generation/index.json` (`nominal_seconds`, titles, artists)
- `outputs/YT500/generation/quality_audit_duration.json` (this snapshot)
