#!/usr/bin/env python3
"""Build the canonical manifest for the Five Stars ABC corpus.

Reads the upstream pickle + audio tree and emits a stable, joinable record per
track. Everything downstream (transcription, ABC linting, exemplar packaging)
keys off `track_id`, which is the upstream `clip_id`.

    python3 datasets/five_stars/build_manifest.py \
        --src ../../Five_Stars_ArabMaqamRock \
        --out .

Outputs, next to this script by default:

    manifest.jsonl   one row per track (177)
    lyrics.jsonl     one row per track: raw + plain text + parsed sections
    audit.json       corpus-level QC facts, regenerated each run

The script is idempotent: re-running rewrites the three files in place.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import unicodedata
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

# --------------------------------------------------------------------------
# lyrics parsing
# --------------------------------------------------------------------------

# "///***///" and the JSON-escaped variant "///\*\*\*///"
HEADER_RE = re.compile(r"^[^\w\[]*///")
SECTION_RE = re.compile(r"^\[([^\]]*)\]\s*$")
ARABIC_RE = re.compile(r"[\u0600-\u06FF]")
HARAKAT_RE = re.compile(r"[\u064B-\u0652]")
TRAILING_RE = re.compile(r"\s*(\.\.\.|…)\s*$")


def parse_lyrics(raw: str) -> dict:
    """Split the generation-prompt lyrics into sections and plain text.

    Text is NFC-normalised: the upstream JSON mixes canonical orderings of the
    Arabic combining marks across files.
    """
    raw = unicodedata.normalize("NFC", raw)
    sections: list[dict] = []
    current = {"type": "unsectioned", "direction": "", "lines": []}

    for line in raw.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        if HEADER_RE.match(stripped) or stripped.startswith("///"):
            continue

        m = SECTION_RE.match(stripped)
        if m:
            label = m.group(1).strip()
            parts = [p.strip() for p in label.split("|")]
            head = parts[0]
            # Section type is the leading word(s) before a performance note,
            # e.g. "Verse 1", "Chorus", "Intro", "Outro buffer".
            current = {
                "type": head,
                "direction": " | ".join(parts[1:]).strip(),
                "lines": [],
            }
            sections.append(current)
            continue

        # Drop lines with no Arabic (stray English notes inside the body).
        if not ARABIC_RE.search(stripped):
            continue
        current["lines"].append(stripped)

    # Drop empty sections produced by trailing markers.
    sections = [s for s in sections if s["lines"]]

    plain_lines = [TRAILING_RE.sub("", ln) for s in sections for ln in s["lines"]]
    plain = "\n".join(plain_lines)

    # Normalised form used only for grouping identical poems across takes.
    norm = "\n".join(
        re.sub(r"\s+", " ", re.sub(r"[\u064B-\u0652]", "", ln)).strip()
        for ln in plain_lines
    )
    group_id = hashlib.sha1(norm.encode("utf-8")).hexdigest()[:16]

    return {
        "sections": sections,
        "plain": plain,
        "norm": norm,
        "lyric_group_id": group_id,
        "n_sections": len(sections),
        "n_lines": len(plain_lines),
        "n_chars": len(plain),
        "has_harakat": bool(HARAKAT_RE.search(plain)),
    }


# --------------------------------------------------------------------------
# title parsing
# --------------------------------------------------------------------------

TITLE_RE = re.compile(r"^(?:([A-Z][A-Z_]+)_)?(\d\d)-(.+?)(_RETAKE)?$")
TAKE_RE = re.compile(r"_(SONG_[A-Z])$")


def parse_title(title: str, filename: str) -> dict:
    prefix = None
    tm = TITLE_RE.match(title)
    if tm:
        prefix, section_no, slug, retake = tm.groups()
    else:
        section_no, slug, retake = None, title, None

    take = None
    fm = TAKE_RE.search(Path(filename).stem)
    if fm:
        take = fm.group(1)

    return {
        "poem_slug": slug,
        "section_no": int(section_no) if section_no else None,
        "take": take,
        "variant_prefix": prefix,
        "is_retake": bool(retake) or bool(prefix and "RETAKE" in prefix),
    }


# --------------------------------------------------------------------------
# audio probing
# --------------------------------------------------------------------------


def probe(path: Path) -> dict:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "format=duration,bit_rate,size:stream=sample_rate,channels",
         "-of", "json", str(path)],
        capture_output=True, text=True,
    )
    fmt = json.loads(out.stdout)["format"]
    stream = json.loads(out.stdout)["streams"][0]
    return {
        "duration_s": round(float(fmt["duration"]), 3),
        "bytes": int(fmt["size"]),
        "bit_rate": int(fmt["bit_rate"]),
        "sample_rate": int(stream["sample_rate"]),
        "channels": int(stream["channels"]),
    }


def loudness(path: Path) -> dict:
    out = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", str(path),
         "-af", "volumedetect", "-f", "null", "-"],
        capture_output=True, text=True,
    ).stderr
    mean = re.search(r"mean_volume: ([-\d.]+) dB", out)
    peak = re.search(r"max_volume: ([-\d.]+) dB", out)
    return {
        "mean_volume_db": float(mean.group(1)) if mean else None,
        "max_volume_db": float(peak.group(1)) if peak else None,
    }


def sha256(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def analyse(path: Path) -> dict:
    return {**probe(path), **loudness(path), "sha256": sha256(path)}


# --------------------------------------------------------------------------
# optional rating join (non-authoritative)
# --------------------------------------------------------------------------

RATINGS_DIR = Path("/home/akbar/Jupyter_Notebooks/OpenCode/maqam_listen_proof/ratings")


def load_ratings() -> dict[str, list[dict]]:
    if not RATINGS_DIR.is_dir():
        return {}
    found: dict[str, list[dict]] = {}
    for path in sorted(RATINGS_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        for filename, entry in data.get("ratings", {}).items():
            found.setdefault(filename, []).append(
                {"maqam": data.get("maqam"), "stars": entry.get("stars"),
                 "rated_at": entry.get("rated_at")}
            )
    return found


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", required=True, type=Path,
                    help="upstream Five_Stars_ArabMaqamRock directory")
    ap.add_argument("--out", default=Path(__file__).parent, type=Path)
    ap.add_argument("--workers", type=int, default=10)
    args = ap.parse_args()

    src = args.src.resolve()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)

    pkl = src / "FIVE_STARS_MAQAM_DATASET.pkl"
    if not pkl.is_file():
        raise SystemExit(f"missing {pkl}")
    df = pd.read_pickle(pkl)
    print(f"[load] {len(df)} rows from {pkl.name}")

    ratings = load_ratings()

    # --- analyse audio in parallel -------------------------------------
    audio_paths = [src / p.lstrip("./") for p in df["NEW_MP3_PATH"]]
    missing = [p for p in audio_paths if not p.is_file()]
    if missing:
        raise SystemExit(f"{len(missing)} audio files missing, first: {missing[0]}")
    print(f"[audio] probing {len(audio_paths)} files")
    with ThreadPoolExecutor(args.workers) as pool:
        audio = list(pool.map(analyse, audio_paths))

    # --- build rows -----------------------------------------------------
    rows, lyric_rows = [], []
    for i, (_, r) in enumerate(df.iterrows()):
        tr = r["TRACKS"]
        ly = parse_lyrics(r["LYRICS"])
        ti = parse_title(tr["original_title"], tr["assigned_filename"])
        a = audio[i]

        prior = ratings.get(tr["assigned_filename"], [])
        stars = [p["stars"] for p in prior if p.get("stars") is not None]

        track_id = r["CLIP_ID"]
        rows.append({
            "track_id": track_id,
            "maqam": r["MAQAM"],
            "audio_path": f"audio/{r['MAQAM']}/{track_id}.mp3",
            "audio_sha256": a["sha256"],
            "duration_s": a["duration_s"],
            "bytes": a["bytes"],
            "bit_rate": a["bit_rate"],
            "sample_rate": a["sample_rate"],
            "channels": a["channels"],
            "mean_volume_db": a["mean_volume_db"],
            "max_volume_db": a["max_volume_db"],
            "original_title": tr["original_title"],
            "assigned_filename": tr["assigned_filename"],
            **ti,
            "lyric_group_id": ly["lyric_group_id"],
            "n_lines": ly["n_lines"],
            "n_sections": ly["n_sections"],
            "n_chars": ly["n_chars"],
            "has_harakat": ly["has_harakat"],
            "prior_rating": stars[0] if stars else None,
            "created_at": tr.get("created_at"),
            "upstream_status": tr.get("status"),
        })
        lyric_rows.append({
            "track_id": track_id,
            "maqam": r["MAQAM"],
            "lyric_group_id": ly["lyric_group_id"],
            "sections": ly["sections"],
            "plain": ly["plain"],
            "style_prompt": r["STYLE"],
            "exclude_styles": tr.get("exclude_styles"),
        })

    # duplicate accounting
    counts = Counter(row["lyric_group_id"] for row in rows)
    variants: dict[str, set[str]] = {}
    for rec in lyric_rows:
        variants.setdefault(rec["lyric_group_id"], set()).add(rec["plain"])
    for row in rows:
        row["lyric_group_copies"] = counts[row["lyric_group_id"]]
        row["group_diacritizations"] = len(variants[row["lyric_group_id"]])

    def dump(name: str, records: list[dict]) -> None:
        path = out / name
        with open(path, "w", encoding="utf-8") as f:
            for rec in records:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(f"[write] {path.name}: {len(records)} records")

    dump("manifest.jsonl", rows)
    dump("lyrics.jsonl", lyric_rows)

    # --- audit ----------------------------------------------------------
    durs = [r["duration_s"] for r in rows]
    audit = {
        "generated_from": str(pkl),
        "tracks": len(rows),
        "total_hours": round(sum(durs) / 3600, 3),
        "total_gb": round(sum(r["bytes"] for r in rows) / 1e9, 3),
        "duration_s": {"min": min(durs), "max": max(durs),
                       "median": round(sorted(durs)[len(durs) // 2], 1)},
        "per_maqam": dict(Counter(r["maqam"] for r in rows)),
        "unique_lyric_groups": len(counts),
        "lyric_group_copies": dict(sorted(Counter(counts.values()).items())),
        "groups_with_multiple_diacritizations": sum(
            1 for s in variants.values() if len(s) > 1),
        "diacritization_variants_per_group": dict(sorted(
            Counter(len(s) for s in variants.values()).items())),
        "unique_poem_slug": len({r["poem_slug"] for r in rows}),
        "unique_section_title": len({r["original_title"] for r in rows}),
        "takes": dict(Counter(r["take"] or "none" for r in rows)),
        "retakes": sum(1 for r in rows if r["is_retake"]),
        "sections_per_track": {
            "min": min(r["n_sections"] for r in rows),
            "max": max(r["n_sections"] for r in rows),
        },
        "lines_per_track": {
            "min": min(r["n_lines"] for r in rows),
            "max": max(r["n_lines"] for r in rows),
            "mean": round(sum(r["n_lines"] for r in rows) / len(rows), 1),
        },
        "all_diacritized": all(r["has_harakat"] for r in rows),
        "audio": {
            "sample_rates": sorted({r["sample_rate"] for r in rows}),
            "channels": sorted({r["channels"] for r in rows}),
            "peak_db_worst": max(r["max_volume_db"] for r in rows),
            "mean_db_range": [min(r["mean_volume_db"] for r in rows),
                              max(r["mean_volume_db"] for r in rows)],
        },
        "prior_ratings": {
            "note": "earlier partial listening pass; NOT a filter, all 177 are curated",
            "matched": sum(1 for r in rows if r["prior_rating"] is not None),
            "stars": dict(sorted(Counter(r["prior_rating"] for r in rows
                                         if r["prior_rating"] is not None).items())),
        },
    }

    # style prompt variance
    styles = list(df["STYLE"])

    def field(text: str, name: str) -> str | None:
        m = re.search(rf'^{name}:\s*"([^"]*)"', text, re.M)
        return m.group(1) if m else None

    audit["style_prompt"] = {
        "unique_genre": len({field(s, "genre") for s in styles}),
        "unique_vocals": len({field(s, "vocals") for s in styles}),
        "unique_production": len({field(s, "production") for s in styles}),
        "unique_instrumentation": len({field(s, "instrumentation") for s in styles}),
        "unique_mood": len({field(s, "mood") for s in styles}),
        "bpm": dict(Counter(re.search(r"(\d+)\s*BPM", s).group(1)
                            for s in styles if re.search(r"(\d+)\s*BPM", s))),
    }

    audit_path = out / "audit.json"
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n",
                          encoding="utf-8")
    print(f"[write] {audit_path.name}")
    print(f"[done] {len(rows)} tracks, {audit['total_hours']} h, "
          f"{audit['unique_lyric_groups']} unique lyric groups")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
