#!/usr/bin/env python3
"""Word-level last-bayt occurrence counter.

``count_last_bayt.py`` scores windows of *Whisper segments*.  On music that is
usually fine, but on a clean vocal stem Whisper often merges two renditions of
the bayt into one 20 s segment, which makes the segment-level counter
undercount.  This variant keeps Whisper's word timestamps and scores windows of
consecutive *words* instead, so a merged segment is split back into its
renditions before fuzzy matching.

The Arabic normalisation, reference extraction, caching and CLI deliberately
match ``count_last_bayt.py``.

Examples
--------
    python3 count_last_bayt_words.py --audio vocals.wav --lyrics-file lyrics.txt
    python3 count_last_bayt_words.py --run-dir /path/to/run --out words.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass, asdict
from pathlib import Path

from count_last_bayt import (
    last_sung_block,
    normalize_arabic,
    song_reference_from_input,
    track_info,
    decode_tail,
)


@dataclass
class Word:
    start: float
    end: float
    text: str
    norm: str


def transcribe_words(path: Path, start_s: float, model_name: str, threads: int,
                     language: str = "ar", device: str = "cpu",
                     compute_type: str = "int8") -> list[Word]:
    from faster_whisper import WhisperModel

    audio = decode_tail(path, start_s)
    model = WhisperModel(model_name, device=device, compute_type=compute_type,
                         cpu_threads=threads)
    raw_segments, _ = model.transcribe(
        audio, language=language, beam_size=5, vad_filter=False,
        condition_on_previous_text=False, word_timestamps=True,
    )
    words: list[Word] = []
    for seg in raw_segments:
        for w in seg.words or []:
            text = w.word.strip()
            norm = normalize_arabic(text)
            if not norm:
                continue
            words.append(Word(w.start + start_s, w.end + start_s, text, norm))
    return words


@dataclass
class Match:
    start: float
    end: float
    score: float
    text: str
    n_words: int


def find_occurrences(words: list[Word], reference: str, threshold: float = 75.0,
                     min_words: int = 5, max_words: int = 12,
                     max_gap: float = 2.5, max_window_s: float = 18.0,
                     nms_overlap: float = 0.35) -> list[Match]:
    from rapidfuzz import fuzz

    ref = normalize_arabic(reference)
    n_ref = len(ref.split())
    lo = max(1, n_ref - 2)
    hi = n_ref + 4
    lo = max(lo, min_words)
    hi = min(hi, max_words)

    candidates: list[Match] = []
    for i in range(len(words)):
        text = ""
        for j in range(i, min(i + hi, len(words))):
            if j > i:
                if words[j].start - words[j - 1].end > max_gap:
                    break
                if words[j].end - words[i].start > max_window_s:
                    break
            text = (text + " " + words[j].norm).strip()
            n_win = j - i + 1
            if n_win < lo:
                continue
            score = float(fuzz.ratio(ref, text))
            if score >= threshold:
                candidates.append(Match(words[i].start, words[j].end, score,
                                        text, n_win))
    if not candidates:
        return []

    accepted: list[Match] = []
    for cand in sorted(candidates, key=lambda m: (-m.score, m.start)):
        duplicate = False
        for kept in accepted:
            inter = max(0.0, min(cand.end, kept.end) - max(cand.start, kept.start))
            if inter <= 0:
                continue
            union = max(cand.end, kept.end) - min(cand.start, kept.start)
            if inter / union >= nms_overlap:
                duplicate = True
                break
        if not duplicate:
            accepted.append(cand)
    return sorted(accepted, key=lambda m: m.start)


def process_audio(audio: Path, reference: str, start_frac: float,
                  model_name: str, threads: int, threshold: float,
                  cache_dir: Path | None, device: str = "cpu",
                  compute_type: str = "int8") -> dict:
    import soundfile as sf

    duration = float(sf.info(str(audio)).duration)
    start_s = max(0.0, duration * start_frac)
    cache = None
    if cache_dir is not None:
        cache = cache_dir / f"{audio.stem}.{model_name}.words.{start_frac:.2f}.json"
        if cache.exists():
            data = json.loads(cache.read_text(encoding="utf-8"))
            words = [Word(**w) for w in data["words"]]
        else:
            words = transcribe_words(audio, start_s, model_name, threads,
                                     device=device, compute_type=compute_type)
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(json.dumps({
                "audio": str(audio), "model": model_name,
                "start_s": start_s, "duration_s": duration,
                "words": [asdict(w) for w in words],
            }, ensure_ascii=False, indent=1), encoding="utf-8")
    else:
        words = transcribe_words(audio, start_s, model_name, threads,
                                 device=device, compute_type=compute_type)

    matches = find_occurrences(words, reference, threshold=threshold)
    strict = find_occurrences(words, reference, threshold=max(threshold, 85.0))
    times = [{"start": round(m.start, 2), "end": round(m.end, 2),
              "score": round(m.score, 1), "n_words": m.n_words} for m in matches]
    strict_times = [{"start": round(m.start, 2), "end": round(m.end, 2),
                     "score": round(m.score, 1)} for m in strict]
    mean_len = (sum(m.end - m.start for m in matches) / len(matches)) if matches else 0.0
    return {
        "duration_s": round(duration, 3),
        "asr_start_s": round(start_s, 2),
        "reference_norm": normalize_arabic(reference),
        "occurrences": len(matches),
        "occurrence_times": json.dumps(times, ensure_ascii=False),
        "occurrences_strict85": len(strict),
        "occurrence_times_strict85": json.dumps(strict_times, ensure_ascii=False),
        "mean_occurrence_s": round(mean_len, 2),
        "first_occurrence_s": round(matches[0].start, 2) if matches else None,
        "last_occurrence_end_s": round(matches[-1].end, 2) if matches else None,
        "asr_words": len(words),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--audio", type=Path)
    ap.add_argument("--lyrics-file", type=Path)
    ap.add_argument("--run-dir", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--cache-dir", type=Path)
    ap.add_argument("--model", default="small")
    ap.add_argument("--threads", type=int, default=2)
    ap.add_argument("--device", default="cpu", choices=["cpu", "cuda"])
    ap.add_argument("--compute-type", default="int8")
    ap.add_argument("--start-frac", type=float, default=0.55)
    ap.add_argument("--threshold", type=float, default=75.0)
    args = ap.parse_args()

    if args.audio:
        if not args.lyrics_file:
            ap.error("--audio requires --lyrics-file")
        ref = last_sung_block(args.lyrics_file.read_text(encoding="utf-8"))
        info = process_audio(args.audio, ref, args.start_frac, args.model,
                             args.threads, args.threshold, args.cache_dir,
                             device=args.device, compute_type=args.compute_type)
        print(json.dumps({"audio": str(args.audio), "reference": ref, **info},
                         ensure_ascii=False, indent=1))
        return 0

    if not args.run_dir:
        ap.error("give --audio or --run-dir")

    run = args.run_dir
    input_json = run / "input.json"
    manifest = json.loads((run / "batch_manifest.json").read_text(encoding="utf-8"))
    rows = []
    for audio in sorted(run.glob("*.mp3")):
        stem = audio.stem
        name, song = song_reference_from_input(input_json, stem)
        ref = last_sung_block(song["lyrics"])
        t = track_info(manifest, stem)
        row = {
            "run": run.name,
            "track": name,
            "seed": t.get("seed"),
            "cap": t.get("cap"),
            "score_s": t.get("score_s"),
            "n_letters": t.get("n_letters"),
            "guidance_scale": (t.get("controls") or {}).get("guidance_scale"),
            "cot": t.get("cot"),
            "abc_file": t.get("abc_file"),
            "reference": ref,
            "audio": audio.name,
        }
        row.update(process_audio(audio, ref, args.start_frac, args.model,
                                 args.threads, args.threshold, args.cache_dir,
                                 device=args.device, compute_type=args.compute_type))
        rows.append(row)
        print(f"{run.name} {stem}: {row['occurrences']} occurrences "
              f"({row['duration_s']:.1f}s)", flush=True)

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        print(f"wrote {args.out} ({len(rows)} rows)")
    else:
        print(json.dumps(rows, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
