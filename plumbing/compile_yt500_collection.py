#!/usr/bin/env python3
"""Compile the YT500 instrumental collection and attach its captions.

The collection is a *metadata tree*: one folder per track under ``tracks/``
plus catalog files at the root.  This compiler has three modes, and only the
captioned dataset (``v0.2``) is produced by ``--attach-captions``::

    build
        Recompile the catalog files (jsonl/csv/md/m3u/parquet) from the
        per-track ``track.json`` files.  The 460-track set is frozen in the
        tree, so a rebuild is deterministic and never adds or drops a track.

    --attach-captions
        Attach the polished captions of a ``music_captioning`` caption album:
        ``caption.txt`` + ``caption.json`` per track, the ``caption`` block in
        ``track.json``, caption columns in every catalog, ``captions.jsonl`` /
        ``captions.sha256``, the manifest (``dataset_version: v0.2``) and the
        README / dataset card.  Two runs over the same inputs are byte
        identical.

    --verify
        Check the caption chain (file hash == track.json hash == catalog hash),
        the take seed, the catalog columns, the line count of
        ``captions.jsonl`` and, with ``--remote``, that the bucket holds one
        ``caption.json`` per track.

Usage::

    python3 plumbing/compile_yt500_collection.py --local /data/yt500 --build
    python3 plumbing/compile_yt500_collection.py --local /data/yt500 \\
        --captions album.json --attach-captions --allow-unpolished
    python3 plumbing/compile_yt500_collection.py --local /data/yt500 --verify
    python3 plumbing/compile_yt500_collection.py --local /data/yt500 --verify \\
        --remote

The catalog writer reproduces the ``v0.1`` text artifacts byte for byte; that
is the regression test for the format (see ``tests/test_compile_yt500_collection.py``).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parent.parent

DATASET_URI = "gs://akbar-december-2024-backup/DATASET/yt500_instrumental"
ALBUM_URI = (
    "gs://akbar-december-2024-backup/GENERATION/YT500_INSTRUMENTAL/work/"
    "caption_album.json"
)

DATASET_TITLE = "YT500 Instrumental \u2014 quality-gated tracks"
DATASET_VERSION = "v0.2"
GATE_EXPR = "abs(wav_s - nominal_s) / nominal_s <= 0.15"

CAPTION_SCHEMA = "yt500-caption/1"
CAPTION_PIPELINE_VERSION = 3
MIN_CAPTION_CHARS = 200
ALLOWED_REWRITE = ("ok", "fallback", "single_chunk")

# ``<name>_<seed>``: the name itself contains ``_`` (video ids do), so the
# name group is greedy and the seed is the trailing run of digits.
STEM_RE = re.compile(r"^(yt500-\d{4}-.+)_(\d+)$")
TIMESTAMP_RE = re.compile(r"\[\d{1,2}:\d{2}")

CATALOG_COLUMNS = [
    "name", "rank", "video_id", "title", "artist", "country", "tier",
    "nominal_s", "wav_s", "delta_pct", "gate", "sections", "run", "seed",
    "cap", "lyrics_sha256", "style_sha256", "abc_sha256", "mp3_source",
]
CAPTION_COLUMNS = ["caption_sha256", "caption_chars", "rewrite_status"]

PARQUET_COLUMNS = [
    "name", "rank", "video_id", "title", "artist", "country", "tier", "gate",
    "nominal_s", "wav_s", "delta_pct", "sections", "run", "seed", "cap",
    "engine", "lyrics_kind", "lyrics_sha256", "lyrics_text", "style_sha256",
    "abc_sha256", "mp3_source", "mp3_bytes", "wav_sha256", "takes",
]

LAYOUT_OLD = """tracks/<name>/
  audio.mp3     the kept take (3.02 GB total)
  lyrics.txt    section tag plan used for this take
  style.txt     exact style prompt used
  score.abc     instrumental ABC score
  track.json    ids, hashes, seed, provenance
catalog.jsonl   one row per track, tag plan inlined
catalog.csv     spreadsheet view
catalog.md      human-readable table
playlist.m3u    rank order
recipe/         canonical style + LoRA/scales/CoT
"""

LAYOUT_NEW = """tracks/<name>/
  audio.mp3     the kept take (3.02 GB total)
  lyrics.txt    section tag plan used for this take
  style.txt     exact style prompt used
  score.abc     instrumental ABC score
  track.json    ids, hashes, seed, provenance, caption pointer
  caption.txt   polished prose caption for this take
  caption.json  full caption record (chunks, tags, audio, rewrite)
catalog.jsonl   one row per track, tag plan + caption fields inlined
catalog.csv     spreadsheet view
catalog.md      human-readable table
playlist.m3u    rank order
captions.jsonl  one line per caption artifact (sha256, bytes)
captions.sha256 sha256 of captions.jsonl
recipe/         canonical style + LoRA/scales/CoT
"""

CAPTIONS_SECTION = """## Captions

Every track carries a prose caption written from its audio by the ACE-Step
Captioner (4-bit `ACE-Step/acestep-captioner`) and polished by a small instruct
model (`Qwen3-4B-Instruct-2507`).  `caption.txt` is the final prose;
`caption.json` keeps the per-chunk text it was built from, the take it
describes and the experimental tag lists.

The tag lists (`instruments`, `vocals`, `production`) come from deterministic
lexicon matching and are **experimental** — they are not ground truth.

`catalog.jsonl`, `catalog.csv` and `tracks.parquet` carry `caption_sha256`,
`caption_chars` and `rewrite_status`; `captions.jsonl` lists every caption
artifact with its sha256 and size, and `captions.sha256` hashes that index.
"""


class CaptionError(RuntimeError):
    """A caption cannot be attached to a track."""


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        raise


def dump_json(obj: Any) -> bytes:
    """Exactly the serialization used by the v0.1 catalog."""
    return (json.dumps(obj, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


# --------------------------------------------------------------------------- #
# reading the album
# --------------------------------------------------------------------------- #
def parse_caption_album(
    album_path: str | Path, data: dict | None = None
) -> tuple[dict[str, dict], str]:
    """Index a caption album by the full take stem ``<name>_<seed>``.

    Returns ``(tracks, album_sha256)``.  The name is greedy so that a video id
    containing ``_`` is not split, and the seed is the trailing digit run.
    """
    path = Path(album_path)
    raw = path.read_bytes()
    album = data if data is not None else json.loads(raw)
    tracks: dict[str, dict] = {}
    for track in album.get("tracks", []):
        stem = Path(str(track.get("file", ""))).stem
        if not STEM_RE.match(stem):
            raise CaptionError(f"album entry has no <name>_<seed> stem: {track.get('file')!r}")
        if stem in tracks:
            raise CaptionError(f"album has two entries for take {stem}")
        tracks[stem] = track
    return tracks, sha256_bytes(raw)


def caption_record(
    row: dict,
    track: dict,
    *,
    album: str = "",
    album_sha256: str = "",
    pipeline_version: int = CAPTION_PIPELINE_VERSION,
    pipeline_stage: str = "polished",
    allow_unpolished: bool = False,
    min_chars: int = MIN_CAPTION_CHARS,
) -> dict:
    """Build the ``caption.json`` record for ``row`` from album ``track``.

    Hard guards (raise :class:`CaptionError`):

    * the album entry is for exactly the take the row pins
      (``<name>_<seed>``), so a newer take can never caption an old seed;
    * the caption is non-empty, free of ``[00:12]``-style timestamps and at
      least ``min_chars`` characters long;
    * ``rewrite_status`` is one of ``ok`` / ``fallback`` / ``single_chunk``.
      ``failed`` is only accepted with ``allow_unpolished`` and is flagged.
    """
    name = row["name"]
    seed = row["generation"]["seed"]
    stem = f"{name}_{seed}"
    actual = Path(str(track.get("file", ""))).stem
    if actual != stem:
        raise CaptionError(
            f"{name}: album take is {actual!r}, expected {stem!r} for seed {seed}"
        )

    caption = str(track.get("caption") or "").strip()
    if not caption:
        raise CaptionError(f"{name}: empty caption for take {stem}")
    if TIMESTAMP_RE.search(caption):
        raise CaptionError(
            f"{name}: caption carries a time reference "
            f"{TIMESTAMP_RE.search(caption).group(0)!r}"
        )
    chars = len(caption)
    if chars < min_chars:
        raise CaptionError(
            f"{name}: caption is {chars} chars, below --min-caption-chars {min_chars}"
        )

    status = track.get("rewrite_status")
    unpolished = False
    if status == "failed":
        if not allow_unpolished:
            raise CaptionError(
                f"{name}: rewrite_status is 'failed' (pass --allow-unpolished to attach "
                "the raw caption and flag it)"
            )
        unpolished = True
    elif status not in ALLOWED_REWRITE:
        raise CaptionError(f"{name}: unexpected rewrite_status {status!r}")

    text = caption + "\n"
    return {
        "schema": CAPTION_SCHEMA,
        "name": name,
        "take": {
            "file": track["file"],
            "seed": seed,
            "run": row["generation"]["run"],
        },
        "caption": caption,
        "caption_sha256": sha256_bytes(text.encode("utf-8")),
        "caption_chars": chars,
        "caption_raw": track.get("caption_raw") or "",
        "chunk_captions": list(track.get("chunk_captions") or []),
        "tags": {
            "instruments": list(track.get("instruments") or []),
            "vocals": list(track.get("vocals") or []),
            "production": list(track.get("production") or []),
        },
        "tags_experimental": bool(track.get("tags_experimental", True)),
        "rewrite": {
            "status": status,
            "model": track.get("rewrite_model"),
            "prompt_version": track.get("rewrite_prompt_version"),
            "seconds": track.get("rewrite_seconds"),
        },
        "pipeline": {
            "version": pipeline_version,
            "stage": pipeline_stage,
            "album": album,
            "album_sha256": album_sha256,
        },
        "audio": {
            "duration_s": track.get("duration_s"),
            "bitrate_kbps": track.get("bitrate_kbps"),
            "chunk_count": track.get("chunk_count"),
            "silence_trimmed_s": track.get("silence_trimmed_s"),
        },
        "unpolished": unpolished,
    }


# --------------------------------------------------------------------------- #
# catalog writers
# --------------------------------------------------------------------------- #
def _csv_row(row: dict) -> list:
    out = [
        row["name"], row["rank"], row["video_id"], row["title"], row["artist"],
        row["country"], row["tier"], row["nominal_s"], row["wav_s"],
        row["delta_pct"], row["gate"], "|".join(row["sections"]),
        row["generation"]["run"], row["generation"]["seed"],
        row["generation"]["cap"], row["lyrics"]["sha256"],
        row["style"]["sha256"], row["score"]["abc_sha256"], row["audio"]["source"],
    ]
    if "caption_sha256" in row:
        out += [row["caption_sha256"], row["caption_chars"], row["rewrite_status"]]
    return out


def _parquet_records(rows: Iterable[dict]) -> list[dict]:
    records = []
    for row in rows:
        rec = {
            "name": row["name"],
            "rank": row["rank"],
            "video_id": row["video_id"],
            "title": row["title"],
            "artist": row["artist"],
            "country": row["country"],
            "tier": row["tier"],
            "gate": row["gate"],
            "nominal_s": row["nominal_s"],
            "wav_s": row["wav_s"],
            "delta_pct": row["delta_pct"],
            "sections": "|".join(row["sections"]),
            "run": row["generation"]["run"],
            "seed": row["generation"]["seed"],
            "cap": row["generation"]["cap"],
            "engine": row["generation"]["engine"],
            "lyrics_kind": row["lyrics"]["kind"],
            "lyrics_sha256": row["lyrics"]["sha256"],
            "lyrics_text": row["lyrics"]["text"],
            "style_sha256": row["style"]["sha256"],
            "abc_sha256": row["score"]["abc_sha256"],
            "mp3_source": row["audio"]["source"],
            "mp3_bytes": row["audio"]["mp3_bytes"],
            "wav_sha256": row["audio"]["wav_sha256"],
            "takes": "|".join(row["provenance"]["takes"]),
        }
        if "caption_sha256" in row:
            rec["caption_sha256"] = row["caption_sha256"]
            rec["caption_chars"] = row["caption_chars"]
            rec["rewrite_status"] = row["rewrite_status"]
        records.append(rec)
    return records


def _write_parquet(path: Path, rows: list[dict]) -> None:
    records = _parquet_records(rows)
    columns = list(PARQUET_COLUMNS)
    if rows and "caption_sha256" in rows[0]:
        columns += CAPTION_COLUMNS
    buf = io.BytesIO()
    try:
        import pandas as pd  # noqa: WPS433  (optional at import time)
    except ImportError as exc:  # pragma: no cover - Colab always has it
        raise SystemExit(f"pandas is required to write tracks.parquet: {exc}") from exc
    frame = pd.DataFrame(records, columns=columns)
    frame.to_parquet(buf, index=False)
    atomic_write(path, buf.getvalue())


def write_catalogs(rows: list[dict], out_dir: str | Path) -> list[dict]:
    """Write every catalog artifact from ``rows``; return the manifest file list.

    The v0.1 layout is reproduced exactly (same column order, same CSV line
    endings, same markdown header); caption columns are appended only when the
    rows carry them.
    """
    out = Path(out_dir)
    rows = sorted(rows, key=lambda r: r["rank"])
    has_captions = bool(rows) and "caption_sha256" in rows[0]

    jsonl = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows).encode("utf-8")
    atomic_write(out / "catalog.jsonl", jsonl)
    atomic_write(out / "tracks.jsonl", jsonl)

    columns = CATALOG_COLUMNS + (CAPTION_COLUMNS if has_captions else [])
    buf = io.StringIO(newline="")
    writer = csv.writer(buf)
    writer.writerow(columns)
    for row in rows:
        writer.writerow(_csv_row(row))
    atomic_write(out / "catalog.csv", buf.getvalue().encode("utf-8"))

    md = ["# YT500 instrumental \u2014 catalogue", "",
          f"{len(rows)} tracks, rank order. `lyrics` are section tag plans.", "",
          "| # | Track | Title \u2014 artist | Dur | \u0394 | Tags | Run |",
          "|---:|---|---|---:|---:|---|---|"]
    for row in rows:
        md.append(
            f"| {row['rank']} | `{row['name']}` | {row['title']} \u2014 {row['artist']} "
            f"| {round(row['wav_s'])}s | {row['delta_pct']:+.1f}% | {len(row['sections'])} "
            f"| `{row['generation']['run']}` |"
        )
    atomic_write(out / "catalog.md", ("\n".join(md) + "\n").encode("utf-8"))

    m3u = ["#EXTM3U"]
    for row in rows:
        m3u.append(
            f"#EXTINF:{round(row['wav_s'])},{row['title']} \u2014 {row['artist']} "
            f"({row['delta_pct']:+.1f}%)"
        )
        m3u.append(f"tracks/{row['name']}/audio.mp3")
    atomic_write(out / "playlist.m3u", ("\n".join(m3u) + "\n").encode("utf-8"))

    _write_parquet(out / "tracks.parquet", rows)

    return [
        {"path": name, "sha256": sha256_file(out / name), "bytes": (out / name).stat().st_size}
        for name in ("catalog.jsonl", "catalog.csv", "catalog.md", "tracks.jsonl",
                     "tracks.parquet", "playlist.m3u")
    ]


# --------------------------------------------------------------------------- #
# tree reading
# --------------------------------------------------------------------------- #
def load_rows(local: str | Path) -> list[dict]:
    root = Path(local)
    tracks = root / "tracks"
    if not tracks.is_dir():
        raise SystemExit(f"no tracks/ directory under {root}")
    rows = []
    for path in sorted(tracks.glob("*/track.json")):
        rows.append(json.loads(path.read_text(encoding="utf-8")))
    if not rows:
        raise SystemExit(f"no track.json under {tracks}")
    rows.sort(key=lambda r: r["rank"])
    names = [r["name"] for r in rows]
    if len(names) != len(set(names)):
        raise SystemExit("duplicate track names in the tree")
    return rows


def load_manifest(local: str | Path) -> dict:
    path = Path(local) / "manifest.json"
    if not path.exists():
        raise SystemExit(f"missing {path}; attach needs the v0.1 manifest")
    return json.loads(path.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# documents
# --------------------------------------------------------------------------- #
def render_docs(text: str) -> str:
    """Add the caption layout lines and the Captions section (idempotent)."""
    if LAYOUT_NEW.splitlines()[0] in text and "caption.txt   polished prose" in text:
        new_text = text
    else:
        if LAYOUT_OLD not in text:
            raise SystemExit("README/card layout block not found; refusing to rewrite it")
        new_text = text.replace(LAYOUT_OLD, LAYOUT_NEW)
    if "## Captions" not in new_text:
        anchor = "## Recipe\n"
        if anchor not in new_text:
            raise SystemExit("README/card has no '## Recipe' anchor for the captions section")
        new_text = new_text.replace(anchor, CAPTIONS_SECTION + "\n" + anchor, 1)
    return new_text


def render_success(manifest: dict, captions: int) -> str:
    lines = [f"{manifest['generated_at']}", f"tracks={manifest['counts']['tracks']}"]
    if captions:
        lines.append(f"captions={captions}")
    lines.append("parquet=tracks.parquet")
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- #
# attach
# --------------------------------------------------------------------------- #
def _resolve_album(args) -> Path:
    if args.captions:
        path = Path(args.captions)
        if not path.exists():
            raise SystemExit(f"--captions not found: {path}")
        return path
    if args.captions_uri:
        tmp = Path(tempfile.mkdtemp(prefix="yt500-album-")) / "caption_album.json"
        cmd = ["gcloud", "storage", "cp", "-q", args.captions_uri, str(tmp)]
        subprocess.run(cmd, check=True)
        return tmp
    raise SystemExit("attach needs --captions PATH or --captions-uri URI")


def attach(args) -> int:
    root = Path(args.local).resolve()
    album_path = _resolve_album(args)
    album = json.loads(album_path.read_bytes())
    album_sha = sha256_file(album_path)
    album_tracks, _ = parse_caption_album(album_path, data=album)

    version = album.get("caption_pipeline_version")
    stage = album.get("caption_stage")
    if version != CAPTION_PIPELINE_VERSION:
        return _fail(f"album pipeline version is {version!r}, expected {CAPTION_PIPELINE_VERSION}")
    if stage != "polished":
        return _fail(f"album stage is {stage!r}, expected 'polished'")

    rows = load_rows(root)
    manifest = load_manifest(root)
    manifest_tracks = manifest.get("counts", {}).get("tracks")
    if manifest_tracks is not None and manifest_tracks != len(rows):
        return _fail(f"manifest counts {manifest_tracks} tracks, tree has {len(rows)}")

    if not args.no_audio:
        missing_audio = [r["name"] for r in rows
                         if not (root / "tracks" / r["name"]
                                 / (r.get("artifacts") or {}).get("audio", "audio.mp3")).exists()]
        if missing_audio:
            return _fail(
                f"{len(missing_audio)} track folders have no audio.mp3 "
                f"(first: {missing_audio[0]}); use --no-audio for a metadata-only tree"
            )

    # validate everything before touching the tree
    prepared: list[tuple[dict, dict, str]] = []
    missing: list[str] = []
    for row in rows:
        stem = f"{row['name']}_{row['generation']['seed']}"
        track = album_tracks.get(stem)
        if track is None:
            if args.allow_missing_captions:
                missing.append(row["name"])
                continue
            return _fail(f"{row['name']}: album has no caption for take {stem}")
        try:
            record = caption_record(
                row,
                track,
                album=f"arabmaqamrock/YT500_INSTRUMENTAL",
                album_sha256=album_sha,
                pipeline_version=version,
                pipeline_stage=stage,
                allow_unpolished=args.allow_unpolished,
                min_chars=args.min_caption_chars,
            )
        except CaptionError as exc:
            return _fail(str(exc))
        prepared.append((row, record, record["caption"] + "\n"))

    # write per-track artifacts + the updated track.json
    for row, record, text in prepared:
        track_dir = root / "tracks" / row["name"]
        text_bytes = text.encode("utf-8")
        caption_bytes = dump_json(record)
        atomic_write(track_dir / "caption.txt", text_bytes)
        atomic_write(track_dir / "caption.json", caption_bytes)

        updated = dict(row)
        artifacts = dict(updated.get("artifacts") or {})
        artifacts["caption"] = "caption.json"
        artifacts["caption_text"] = "caption.txt"
        updated["artifacts"] = artifacts
        updated["caption"] = {
            "schema": CAPTION_SCHEMA,
            "sha256": record["caption_sha256"],
            "chars": record["caption_chars"],
            "rewrite_status": record["rewrite"]["status"],
            "tags_experimental": record["tags_experimental"],
            "unpolished": record["unpolished"],
        }
        atomic_write(track_dir / "track.json", dump_json(updated))

        row["artifacts"] = artifacts
        row["caption"] = updated["caption"]
        row["caption_sha256"] = record["caption_sha256"]
        row["caption_chars"] = record["caption_chars"]
        row["rewrite_status"] = record["rewrite"]["status"]

    files = write_catalogs(rows, root)

    # captions.jsonl + captions.sha256
    lines = []
    for row in rows:
        for rel in ("caption.txt", "caption.json"):
            path = root / "tracks" / row["name"] / rel
            if not path.exists():
                continue
            lines.append({
                "name": row["name"],
                "path": f"tracks/{row['name']}/{rel}",
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
            })
    index = "".join(json.dumps(line, ensure_ascii=False) + "\n" for line in lines).encode("utf-8")
    atomic_write(root / "captions.jsonl", index)
    atomic_write(
        root / "captions.sha256",
        f"{sha256_bytes(index)}  captions.jsonl\n".encode("utf-8"),
    )
    files += [
        {"path": "captions.jsonl", "sha256": sha256_bytes(index), "bytes": len(index)},
        {"path": "captions.sha256",
         "sha256": sha256_file(root / "captions.sha256"),
         "bytes": (root / "captions.sha256").stat().st_size},
    ]

    # README + dataset card (byte identical in v0.1, kept that way)
    doc = render_docs((root / "README.md").read_text(encoding="utf-8"))
    atomic_write(root / "README.md", doc.encode("utf-8"))
    atomic_write(root / "DATASET_CARD.md", doc.encode("utf-8"))
    files += [
        {"path": "README.md", "sha256": sha256_file(root / "README.md"),
         "bytes": (root / "README.md").stat().st_size},
        {"path": "DATASET_CARD.md", "sha256": sha256_file(root / "DATASET_CARD.md"),
         "bytes": (root / "DATASET_CARD.md").stat().st_size},
    ]
    for rel in ("recipe/style.txt", "recipe/recipe.json"):
        path = root / rel
        if path.exists():
            files.append({"path": rel, "sha256": sha256_file(path),
                          "bytes": path.stat().st_size})

    # manifest
    manifest["dataset_version"] = DATASET_VERSION
    manifest.setdefault("counts", {})["captions"] = len(prepared)
    manifest["layout"] = {
        "per_track": ("tracks/<name>/{audio.mp3,lyrics.txt,style.txt,score.abc,"
                      "track.json,caption.txt,caption.json}"),
        "catalog": "catalog.jsonl (same rows as tracks.jsonl)",
        "captions": "captions.jsonl (one line per caption artifact)",
    }
    manifest["captions"] = {
        "source": ALBUM_URI,
        "source_sha256": album_sha,
        "pipeline_version": version,
        "attached_at": (manifest.get("captions") or {}).get("attached_at") or now_utc(),
    }
    if missing:
        manifest["captions"]["missing"] = missing
    manifest["files"] = files
    atomic_write(root / "manifest.json", dump_json(manifest))

    atomic_write(root / "_SUCCESS", render_success(manifest, len(prepared)).encode("utf-8"))

    print(
        f"attach: {len(prepared)} captions, {len(missing)} missing, "
        f"album {album_sha[:12]}, dataset {DATASET_VERSION}"
    )
    if missing:
        print(f"attach: tracks without caption: {missing[:5]}", file=sys.stderr)
    return 0


# --------------------------------------------------------------------------- #
# verify
# --------------------------------------------------------------------------- #
def _remote_objects(prefix_uri: str, suffix: str) -> int | None:
    """Count objects under ``prefix_uri`` whose name ends with ``suffix``.

    One paginated JSON-API listing: ``gcloud storage ls`` stats every object
    (minutes for 460 folders), the API lists 1000 per request.
    """
    if not prefix_uri.startswith("gs://"):
        return None
    bucket, _, prefix = prefix_uri[len("gs://"):].partition("/")
    try:
        token = subprocess.run(
            ["gcloud", "auth", "print-access-token"],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
    except (FileNotFoundError, subprocess.CalledProcessError):
        token = ""
    if token:
        import urllib.parse
        import urllib.request

        count = 0
        page = None
        while True:
            query = {"prefix": prefix, "fields": "items(name),nextPageToken",
                     "maxResults": "1000"}
            if page:
                query["pageToken"] = page
            url = (f"https://storage.googleapis.com/storage/v1/b/{bucket}/o?"
                   + urllib.parse.urlencode(query))
            request = urllib.request.Request(
                url, headers={"Authorization": f"Bearer {token}"})
            try:
                with urllib.request.urlopen(request, timeout=60) as response:
                    payload = json.load(response)
            except Exception:  # noqa: BLE001 - fall back to gcloud below
                break
            count += sum(1 for obj in payload.get("items", [])
                         if str(obj.get("name", "")).endswith(suffix))
            page = payload.get("nextPageToken")
            if not page:
                return count
    # fallback: slow but works without a token
    try:
        out = subprocess.run(
            ["gcloud", "storage", "ls", f"{prefix_uri.rstrip('/')}/*{suffix}"],
            check=True, capture_output=True, text=True,
        ).stdout
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None
    return len([line for line in out.splitlines() if line.strip()])


def verify(args) -> int:
    root = Path(args.local).resolve()
    rows = load_rows(root)
    errors: list[str] = []
    catalog = [json.loads(line) for line in (root / "catalog.jsonl").read_text(
        encoding="utf-8").splitlines() if line.strip()]
    if len(catalog) != len(rows):
        errors.append(f"catalog.jsonl has {len(catalog)} rows, tree has {len(rows)}")

    for row, cat in zip(rows, catalog):
        name = row["name"]
        text_path = root / "tracks" / name / "caption.txt"
        json_path = root / "tracks" / name / "caption.json"
        if not text_path.exists() or not json_path.exists():
            if args.allow_missing_captions:
                continue
            errors.append(f"{name}: caption.txt/caption.json missing")
            continue
        record = json.loads(json_path.read_text(encoding="utf-8"))
        if record.get("schema") != CAPTION_SCHEMA:
            errors.append(f"{name}: schema {record.get('schema')!r}")
        text_sha = sha256_file(text_path)
        if text_sha != record.get("caption_sha256"):
            errors.append(f"{name}: caption.txt sha != caption.json.caption_sha256")
        track = json.loads((root / "tracks" / name / "track.json").read_text(encoding="utf-8"))
        block = track.get("caption") or {}
        if text_sha != block.get("sha256"):
            errors.append(f"{name}: caption.txt sha != track.json.caption.sha256")
        if text_sha != cat.get("caption_sha256"):
            errors.append(f"{name}: caption.txt sha != catalog caption_sha256")
        if block.get("chars") != cat.get("caption_chars"):
            errors.append(f"{name}: caption chars differ between track.json and catalog")
        if record.get("take", {}).get("seed") != row["generation"]["seed"]:
            errors.append(f"{name}: caption seed != track seed")
        if Path(str(record.get("take", {}).get("file", ""))).stem != \
                f"{name}_{row['generation']['seed']}":
            errors.append(f"{name}: caption take file is not <name>_<seed>.mp3")
        if (track.get("artifacts") or {}).get("caption") != "caption.json":
            errors.append(f"{name}: track.json artifacts.caption missing")
        if not (record.get("caption") or "").strip():
            errors.append(f"{name}: empty caption text")
        if record.get("unpolished") and not args.allow_unpolished:
            errors.append(f"{name}: unpolished caption attached without --allow-unpolished")

    index_path = root / "captions.jsonl"
    index_lines = [json.loads(line) for line in index_path.read_text(
        encoding="utf-8").splitlines() if line.strip()] if index_path.exists() else []
    expected = 2 * len([r for r in rows if (root / "tracks" / r["name"] / "caption.json").exists()])
    if len(index_lines) != expected:
        errors.append(f"captions.jsonl has {len(index_lines)} lines, expected {expected}")
    for line in index_lines:
        path = root / line["path"]
        if not path.exists():
            errors.append(f"captions.jsonl: missing {line['path']}")
        elif sha256_file(path) != line["sha256"]:
            errors.append(f"captions.jsonl: hash mismatch for {line['path']}")
    sha_file = root / "captions.sha256"
    if index_path.exists():
        want = f"{sha256_file(index_path)}  captions.jsonl\n"
        if not sha_file.exists() or sha_file.read_text(encoding="utf-8") != want:
            errors.append("captions.sha256 does not match captions.jsonl")

    manifest = load_manifest(root)
    captions = manifest.get("counts", {}).get("captions")
    have = len([r for r in rows if (root / "tracks" / r["name"] / "caption.json").exists()])
    if captions != have:
        errors.append(f"manifest counts.captions {captions} != {have} on disk")
    if manifest.get("dataset_version") != DATASET_VERSION:
        errors.append(f"manifest dataset_version {manifest.get('dataset_version')!r}")
    info = manifest.get("captions") or {}
    for key in ("source", "source_sha256", "pipeline_version", "attached_at"):
        if not info.get(key):
            errors.append(f"manifest captions.{key} missing")

    remote = None
    if args.remote:
        remote = _remote_objects(f"{DATASET_URI}/tracks/", "/caption.json")
        if remote is None:
            print("verify: gcloud not available, skipped --remote", file=sys.stderr)
        elif remote != len(rows):
            errors.append(f"remote has {remote} caption.json, expected {len(rows)}")
        remote_txt = _remote_objects(f"{DATASET_URI}/tracks/", "/caption.txt")
        if remote_txt is not None and remote_txt != len(rows):
            errors.append(f"remote has {remote_txt} caption.txt, expected {len(rows)}")

    if errors:
        print(f"verify: FAILED with {len(errors)} problem(s)", file=sys.stderr)
        for problem in errors[:40]:
            print(f"  - {problem}", file=sys.stderr)
        return 1
    suffix = f", remote={remote}" if remote is not None else ""
    print(f"verify: OK — {len(rows)} tracks, {have} captions{suffix}")
    return 0


# --------------------------------------------------------------------------- #
# build
# --------------------------------------------------------------------------- #
def build(args) -> int:
    """Recompile the catalog files from the per-track metadata."""
    root = Path(args.local).resolve()
    rows = load_rows(root)
    manifest = load_manifest(root)
    files = write_catalogs(rows, root)
    for rel in ("README.md", "DATASET_CARD.md", "recipe/style.txt", "recipe/recipe.json",
                "captions.jsonl", "captions.sha256"):
        path = root / rel
        if path.exists():
            files.append({"path": rel, "sha256": sha256_file(path),
                          "bytes": path.stat().st_size})
    manifest["files"] = files
    atomic_write(root / "manifest.json", dump_json(manifest))
    captions = manifest.get("counts", {}).get("captions", 0)
    atomic_write(root / "_SUCCESS", render_success(manifest, captions).encode("utf-8"))
    print(f"build: {len(rows)} tracks, {captions} captions")
    return 0


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _fail(message: str) -> int:
    print(f"error: {message}", file=sys.stderr)
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compile the YT500 instrumental collection and attach captions.")
    parser.add_argument("--local", required=True, help="dataset tree (contains tracks/)")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--build", action="store_true", help="recompile the catalogs")
    mode.add_argument("--attach-captions", action="store_true",
                      help="attach a caption album to the tree")
    mode.add_argument("--verify", action="store_true", help="check the tree")
    parser.add_argument("--captions", help="caption_album.json (local path)")
    parser.add_argument("--captions-uri", help="caption_album.json (gs:// URI)")
    parser.add_argument("--no-audio", action="store_true",
                        help="the tree has no audio.mp3 (metadata-only checkout)")
    parser.add_argument("--allow-missing-captions", action="store_true",
                        help="leave tracks without a caption instead of failing")
    parser.add_argument("--allow-unpolished", action="store_true",
                        help="attach a 'failed' rewrite status, flagged as unpolished")
    parser.add_argument("--min-caption-chars", type=int, default=MIN_CAPTION_CHARS,
                        help=f"minimum caption length (default {MIN_CAPTION_CHARS})")
    parser.add_argument("--remote", action="store_true",
                        help="verify also counts objects in the bucket")
    args = parser.parse_args(argv)

    if args.attach_captions:
        return attach(args)
    if args.verify:
        return verify(args)
    return build(args)


if __name__ == "__main__":
    raise SystemExit(main())
