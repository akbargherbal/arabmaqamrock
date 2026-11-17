#!/usr/bin/env python3
"""Count how many times the last lyric section is actually sung.

Pipeline
--------
1. take the last Arabic-bearing lyric block (the "last bayt");
2. transcribe the tail of the audio with faster-whisper (Arabic);
3. normalise Arabic (diacritics, hamza forms, ta marbuta, punctuation);
4. score every 1-4 segment window against the reference with fuzzy matching;
5. merge overlapping/nested windows (NMS) and count the survivors.

The script is diagnostic: it writes JSON/CSV, it does not touch production code.

Examples
--------
    python3 count_last_bayt.py --audio a.mp3 --lyrics-file lyrics.txt
    python3 count_last_bayt.py --run-dir /path/to/run --out results.csv
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable

import numpy as np

# ---------------------------------------------------------------------------
# Arabic normalisation
# ---------------------------------------------------------------------------

_DIACRITICS = (
    "\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06ed"
    "\u0640"                       # tatweel
    "\u200c-\u200f\u202a-\u202e"   # zero-width / bidi controls
)
_DIAC_RE = re.compile(f"[{_DIACRITICS}]")
_TRANS = str.maketrans({
    "أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ٲ": "ا", "ٳ": "ا",
    "ى": "ي", "ئ": "ي", "ؤ": "و", "ة": "ه",
    "ﻻ": "لا", "ﻷ": "لا", "ﻹ": "لا", "ﻵ": "لا",
})
_NON_ARABIC = re.compile(r"[^\u0621-\u064a\s]")
_SPACE = re.compile(r"\s+")
_ARABIC_LETTER = re.compile(r"[\u0621-\u064a]")


def normalize_arabic(text: str) -> str:
    """Light, ASR-tolerant Arabic normalisation.

    Deliberately *not* stemmed: the repeated phrase must stay distinguishable
    from the rest of the poem.
    """
    text = _DIAC_RE.sub("", text)
    text = text.translate(_TRANS)
    text = _NON_ARABIC.sub(" ", text)
    text = _SPACE.sub(" ", text)
    return text.strip()


def has_arabic(text: str) -> bool:
    return bool(_ARABIC_LETTER.search(text))


# ---------------------------------------------------------------------------
# Lyrics: last sung block
# ---------------------------------------------------------------------------

_TAG = re.compile(r"\[[^\]]*\]")


def last_sung_block(lyrics: str) -> str:
    """Return the last blank-line-separated block that carries Arabic lyrics.

    Tags such as ``[Outro | ... fade out]`` are stripped.  A block that only
    contains a tag is skipped, so an all-instrumental outro does not become the
    reference.
    """
    blocks = re.split(r"\n\s*\n", lyrics.strip())
    for block in reversed(blocks):
        body = _TAG.sub("", block)
        lines = [ln.strip() for ln in body.splitlines() if ln.strip()]
        text = " ".join(ln for ln in lines if has_arabic(ln))
        if has_arabic(text):
            return _SPACE.sub(" ", text).strip()
    raise ValueError("no Arabic lyric block found")


def song_reference_from_input(input_json: Path, audio_stem: str) -> tuple[str, dict]:
    """Find the song whose name is a prefix of the audio stem."""
    data = json.loads(input_json.read_text(encoding="utf-8"))
    best = None
    for song in data.get("songs", []):
        name = song.get("name", "")
        if not name:
            continue
        if audio_stem == name or audio_stem.startswith(name + "_"):
            if best is None or len(name) > len(best[0]):
                best = (name, song)
    if best is None:
        raise SystemExit(f"no song in {input_json} matches {audio_stem!r}")
    lyrics = best[1].get("lyrics")
    if lyrics is None:
        raise SystemExit(f"{best[0]}: inline lyrics absent (lyrics_file not staged)")
    return best[0], best[1]


# ---------------------------------------------------------------------------
# ASR
# ---------------------------------------------------------------------------

@dataclass
class Segment:
    start: float
    end: float
    text: str
    norm: str


def decode_tail(path: Path, start_s: float) -> np.ndarray:
    cmd = ["ffmpeg", "-v", "error"]
    if start_s > 0:
        cmd += ["-ss", f"{start_s:.3f}"]
    cmd += ["-i", str(path), "-f", "f32le", "-ac", "1", "-ar", "16000", "-"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32)


def transcribe(path: Path, start_s: float, model_name: str, threads: int,
               language: str = "ar", device: str = "cpu",
               compute_type: str = "int8") -> tuple[list[Segment], float]:
    from faster_whisper import WhisperModel

    audio = decode_tail(path, start_s)
    model = WhisperModel(model_name, device=device, compute_type=compute_type,
                         cpu_threads=threads)
    raw_segments, info = model.transcribe(
        audio, language=language, beam_size=5, vad_filter=False,
        condition_on_previous_text=False,
    )
    segments = []
    for s in raw_segments:
        text = s.text.strip()
        if not text:
            continue
        segments.append(Segment(s.start + start_s, s.end + start_s, text,
                                normalize_arabic(text)))
    return segments, float(info.duration)


# ---------------------------------------------------------------------------
# Fuzzy occurrence finding
# ---------------------------------------------------------------------------

@dataclass
class Match:
    start: float
    end: float
    score: float
    text: str
    n_segments: int


def find_occurrences(segments: list[Segment], reference: str,
                     threshold: float = 75.0, max_gap: float = 2.5,
                     max_window_s: float = 20.0,
                     max_segments: int = 4,
                     nms_overlap: float = 0.35) -> list[Match]:
    """Score consecutive segment windows and return non-overlapping matches.

    A window is a run of 1-4 consecutive segments separated by <= max_gap.
    Nested windows are expected (a full bayt is often split in two segments),
    so the result is deduplicated by time overlap, keeping the best score.
    """
    from rapidfuzz import fuzz

    ref = normalize_arabic(reference)
    candidates: list[Match] = []
    for i in range(len(segments)):
        text = ""
        for j in range(i, min(i + max_segments, len(segments))):
            if j > i:
                gap = segments[j].start - segments[j - 1].end
                if gap > max_gap:
                    break
            if j > i and segments[j].end - segments[i].start > max_window_s:
                break
            text = (text + " " + segments[j].norm).strip()
            score = float(fuzz.ratio(ref, text))
            if score >= threshold:
                candidates.append(Match(segments[i].start, segments[j].end,
                                        score, text, j - i + 1))
    if not candidates:
        return []

    # NMS: best score first, reject windows that mostly duplicate an accepted one.
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


# ---------------------------------------------------------------------------
# Per-track work
# ---------------------------------------------------------------------------

def track_info(manifest: dict, stem: str) -> dict:
    for t in manifest.get("tracks", []):
        expected = f"{t.get('name')}_{t.get('seed')}"
        if stem == expected:
            return t
    # fall back to name prefix; sorted takes still carry the seed
    for t in manifest.get("tracks", []):
        if stem.startswith(str(t.get("name")) + "_"):
            return t
    return {}


def process_audio(audio: Path, reference: str, start_frac: float,
                  model_name: str, threads: int, threshold: float,
                  cache_dir: Path | None, device: str = "cpu",
                  compute_type: str = "int8") -> dict:
    import soundfile as sf  # only for the duration; cheap and already installed

    duration = float(sf.info(str(audio)).duration)
    start_s = max(0.0, duration * start_frac)
    cache = None
    if cache_dir is not None:
        cache = cache_dir / f"{audio.stem}.{model_name}.{start_frac:.2f}.json"
        if cache.exists():
            data = json.loads(cache.read_text(encoding="utf-8"))
            segments = [Segment(**s) for s in data["segments"]]
        else:
            segments, _ = transcribe(audio, start_s, model_name, threads,
                                     device=device, compute_type=compute_type)
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(json.dumps({
                "audio": str(audio), "model": model_name,
                "start_s": start_s, "duration_s": duration,
                "segments": [asdict(s) for s in segments],
            }, ensure_ascii=False, indent=1), encoding="utf-8")
    else:
        segments, _ = transcribe(audio, start_s, model_name, threads,
                                 device=device, compute_type=compute_type)

    matches = find_occurrences(segments, reference, threshold=threshold)
    strict = find_occurrences(segments, reference, threshold=max(threshold, 85.0))
    times = [{"start": round(m.start, 2), "end": round(m.end, 2),
              "score": round(m.score, 1)} for m in matches]
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
        "asr_segments": len(segments),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--audio", type=Path)
    ap.add_argument("--lyrics-file", type=Path)
    ap.add_argument("--run-dir", type=Path,
                    help="batch output dir containing input.json + batch_manifest.json")
    ap.add_argument("--out", type=Path, help="CSV output for --run-dir")
    ap.add_argument("--cache-dir", type=Path)
    ap.add_argument("--model", default="small")
    ap.add_argument("--threads", type=int, default=2)
    ap.add_argument("--device", default="cpu", choices=["cpu", "cuda"],
                    help="faster-whisper device (default cpu; use cuda on the T4)")
    ap.add_argument("--compute-type", default="int8",
                    help="faster-whisper compute type: int8 (CPU) or float16 (T4)")
    ap.add_argument("--start-frac", type=float, default=0.55,
                    help="transcribe from this fraction of the track (default 0.55)")
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
        import csv
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
