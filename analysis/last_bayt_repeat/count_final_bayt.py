#!/usr/bin/env python3
"""Count repeats of the *final sung bayt* in any run directory (no ASR).

Cross-batch instrument used to break the ABC confound: it measures the same
quantity with the same CTC placement rule on the HAC batch (ABC + ``cot=full``
+ cap 9000) and on control batches that differ in having no ABC and
``cot=off``.

Reuses the placement machinery from ``ctc_placements.py`` and only adds the
boilerplate for walking a run directory:

* reference text = ``last_sung_block(lyrics)`` (same rule as the ASR counters)
* ``written``    = how many times that normalised block occurs in the sheet
* ``ctc_count``  = placements after span-NMS, over the whole vocal stem

Default parameters are deliberately identical to ``ctc_placements.py``
(window 11 s, step 0.25 s, span 7-13 s, NMS overlap 0.10, min separation
7.5 s, margin +0.25 over the median window score), so numbers are comparable
across batches.  ``--stability`` adds the 10/11/12/13 s window sweep.

Usage
-----
    python3 count_final_bayt.py \
        --audio-dir /tmp/opencode/vocal_off \
        --input-json /tmp/opencode/vocal_off/input.json \
        --manifest /tmp/opencode/vocal_off/batch_manifest.json \
        --stems-root work/stems/OFF --out work/off_bayt.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import statistics
from pathlib import Path

import numpy as np

from count_last_bayt import last_sung_block, normalize_arabic, song_reference_from_input
from ctc_placements import CTC_MODEL, load_logits, nms_placements, place_bayt


def written_count(sheet: str, reference: str) -> int:
    ref = normalize_arabic(reference)
    hay = normalize_arabic(sheet)
    if not ref:
        return 0
    return max(1, hay.count(ref))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--audio-dir", type=Path,
                    help="run directory holding the rendered audio")
    ap.add_argument("--input-json", type=Path,
                    help="the run's input.json (for lyrics)")
    ap.add_argument("--manifest", type=Path,
                    help="the run's batch_manifest.json (for seed/cot/abc/cap)")
    ap.add_argument("--from-results", type=Path,
                    help="instead of a run dir: read batch/track/expected_count "
                         "from an existing results.csv and use --text")
    ap.add_argument("--text", default=None,
                    help="reference bayt for --from-results (undiacritized)")
    ap.add_argument("--stems-root", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--region-frac", type=float, default=0.0,
                    help="scan from this fraction of the track (0 = whole stem)")
    ap.add_argument("--window-s", type=float, default=11.0)
    ap.add_argument("--step-s", type=float, default=0.25)
    ap.add_argument("--min-span", type=float, default=7.0)
    ap.add_argument("--max-span", type=float, default=13.0)
    ap.add_argument("--min-separation", type=float, default=7.5)
    ap.add_argument("--nms-overlap", type=float, default=0.10)
    ap.add_argument("--margin", type=float, default=0.25)
    ap.add_argument("--stability", action="store_true",
                    help="also count with 10/11/12/13 s windows")
    args = ap.parse_args()

    import soundfile as sf
    import torch
    from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor

    manifest = {}
    if args.manifest:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    # Demucs names its output folder after the audio file stem, which is
    # ``<name>_<seed>``, while the manifest keys tracks by ``name`` alone.
    tracks: dict[str, dict] = {}
    for t in manifest.get("tracks", []):
        tracks[t["name"]] = t
        tracks[f"{t['name']}_{t['seed']}"] = t

    device = args.device if (args.device != "cuda" or torch.cuda.is_available()) else "cpu"
    processor = Wav2Vec2Processor.from_pretrained(CTC_MODEL)
    model = Wav2Vec2ForCTC.from_pretrained(CTC_MODEL).to(device).eval()
    tokenizer = processor.tokenizer
    blank = tokenizer.pad_token_id if tokenizer.pad_token_id is not None else 0

    # ---- build the work list ------------------------------------------------
    items = []
    if args.from_results:
        ref = args.text or ""
        if not ref:
            raise SystemExit("--from-results needs --text (the reference bayt)")
        for row in csv.DictReader(args.from_results.open(encoding="utf-8")):
            batch, track = row["batch"], row["track"]
            items.append({
                "batch": batch,
                "track": track,
                "vocal": args.stems_root / batch / "htdemucs" / track / "vocals.wav",
                "reference": ref,
                "written": int(float(row.get("expected_count") or 2)),
                "meta": {k: row.get(k) for k in ("seed", "cap", "cot")} | {"abc": row.get("abc_file")},
            })
    else:
        for name in ("audio_dir", "input_json", "manifest"):
            if not getattr(args, name):
                raise SystemExit(f"--{name.replace('_', '-')} is required without --from-results")
        for audio in sorted(args.audio_dir.iterdir()):
            if audio.suffix.lower() not in (".mp3", ".wav", ".flac"):
                continue
            stem_name = audio.stem
            _, song = song_reference_from_input(args.input_json, stem_name)
            reference = last_sung_block(song["lyrics"])
            t = tracks.get(stem_name, {})
            items.append({
                "batch": None,
                "track": stem_name,
                "vocal": args.stems_root / "htdemucs" / stem_name / "vocals.wav",
                "reference": reference,
                "written": written_count(song["lyrics"], reference),
                "meta": {
                    "seed": t.get("seed", song.get("seed")),
                    "cap": t.get("cap"),
                    "cot": t.get("cot"),
                    "abc": bool(t.get("abc_file")),
                    "n_letters": t.get("n_letters"),
                    "ref_words": len(normalize_arabic(reference).split()),
                },
            })

    rows = []
    for it in items:
        stem_name = it["track"]
        vocal = it["vocal"]
        if not vocal.exists():
            print(f"warning: missing stem {vocal}", flush=True)
            continue
        reference = it["reference"]
        written = it["written"]
        # CTC target must be undiacritized, exactly as in ``ctc_placements.py``:
        # 95 diacritized tokens vs ~45 bare ones is the difference between a
        # selective alignment and a permissive one that matches junk.
        target = normalize_arabic(reference)
        token_ids = tokenizer(target, add_special_tokens=False).input_ids

        dur = float(sf.info(str(vocal)).duration)
        start = round(dur * args.region_frac, 2)
        log_probs = load_logits(vocal, start, dur, processor, model, device)

        def count_with(window_s: float):
            cands = place_bayt(log_probs, token_ids, blank, start, 50.0,
                               window_s, args.step_s, args.min_span, args.max_span)
            med = statistics.median(c["score"] for c in cands) if cands else 0.0
            keep = nms_placements(
                [c for c in cands if c["score"] >= med + args.margin],
                args.nms_overlap, args.min_separation)
            return med, keep

        median, kept = count_with(args.window_s)
        stability = {}
        if args.stability:
            for w in (10.0, 11.0, 12.0, 13.0):
                stability[w] = len(kept) if abs(w - args.window_s) < 1e-6 else len(count_with(w)[1])

        t = it["meta"]
        row = {
            "track": stem_name,
            "duration_s": round(dur, 2),
            "region_s": start,
            "reference": reference,
            "ref_tokens": len(token_ids),
            "written": written,
            "ctc_count": len(kept),
            "extra": len(kept) - written,
            "median_score": round(float(median), 4),
            "n_candidates": len(kept),
            "onsets_s": json.dumps([p["onset_s"] for p in kept]),
            "spans_s": json.dumps([p["span_s"] for p in kept]),
            "stability": json.dumps(stability or None),
        }
        row = ({"batch": it["batch"]} if it["batch"] else {}) | {k: t.get(k) for k in
              ("seed", "cap", "cot", "abc", "n_letters", "ref_words")} | row
        rows.append(row)
        tail = f" stability={stability}" if stability else ""
        print(f"{stem_name}: count={len(kept)} written={written}{tail}", flush=True)

    if rows:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
        print(f"wrote {args.out} ({len(rows)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
