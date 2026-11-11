#!/usr/bin/env python3
"""Compile the quality-gated YT500 takes into one dataset.

The dataset lives at ``gs://akbar-december-2024-backup/DATASET/YT500_INSTRUMENTAL``
with one self-contained folder per track::

    tracks/<name>/
      audio.mp3      the kept take
      lyrics.txt     the section tag plan used for that take
      style.txt      the exact style prompt used
      score.abc      the instrumental score rendered
      track.json     ids, hashes, seed, provenance, artifact map

Selecting the set, joining the run metadata and writing the catalogue are
offline. ``--publish`` uploads the metadata tree and copies the MP3s
server-side from the old run prefixes; it never downloads or re-renders audio.

Modes:
    --build            resolve the set and write the local tree
    --attach-captions  attach a music_captioning caption album to a v0.1 tree
    --verify           re-check hashes, counts and folder completeness
    --publish          upload metadata, then copy audio GCS -> GCS
    --download-dir     copy the published audio locally

Captions (``--attach-captions``) are read from the caption album and written
next to each track: ``caption.txt`` (polished prose), ``caption.json`` (the full
record) and a compact ``caption`` block in ``track.json``.  The catalog writers
gain ``caption_sha256``/``caption_chars``/``rewrite_status`` columns plus the
root ``captions.jsonl`` and ``captions.sha256``.  Attach never reselects tracks
and never rewrites audio, scores, styles, lyrics or recipe.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "plumbing"))

import run_yt500_generation as drv  # noqa: E402  (pure Python; no torch)

DATASET_URI = "gs://akbar-december-2024-backup/DATASET/yt500_instrumental"
GCS_RUNS = drv.DEFAULT_RUNS
AUDIT = ROOT / "outputs" / "YT500" / "generation" / "quality_audit_duration.json"
INDEX = ROOT / "outputs" / "YT500" / "generation" / "index.json"
LOCAL = ROOT / "outputs" / "YT500" / "generation" / "collection"
META = ROOT / "work" / "yt500_gen" / "meta"
ACCEPT = ROOT / "work" / "yt500_gen" / "accepted_gray.txt"
GATE_PCT = 15.0
TAG_RE = re.compile(r"\[[^\]]+\]")
ARTIFACTS = ("lyrics.txt", "style.txt", "score.abc", "track.json")

# --- captions ---------------------------------------------------------------
ALBUM_URI = (
    "gs://akbar-december-2024-backup/GENERATION/YT500_INSTRUMENTAL/work/"
    "caption_album.json"
)
CAPTION_SCHEMA = "yt500-caption/1"
# video ids contain ``_`` (e.g. ``…-pEV_jW6S8eM``), so the name is greedy and
# the seed is the trailing digit run.  Never rsplit("_", 1) on the name side.
CAPTION_STEM_RE = re.compile(r"^(yt500-\d{4}-.+)_(\d+)$")
# The rewrite guard in music_captioning ``src/rewrite.py`` rejects timestamps;
# attach uses the timecode shape ("[00:12]" -> "00:12") because chunk-relative
# times become lies once merged into one track description.
CAPTION_TIME_RE = re.compile(r"\b\d{1,2}:\d{2}(?::\d{2})?\b")
CAPTION_STATUSES = ("ok", "fallback", "single_chunk")
CAPTION_COLUMNS = ("caption_sha256", "caption_chars", "rewrite_status")
CAPTION_FILES = ("caption.txt", "caption.json")
MIN_CAPTION_CHARS = 200


# --- small helpers ----------------------------------------------------------

def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    os.replace(tmp, path)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def read_names(path: Path) -> set[str]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return set()
    return {line.split("#", 1)[0].strip() for line in text.splitlines()
            if line.split("#", 1)[0].strip()}


def _gsutil(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    if shutil.which("gsutil") is None:
        raise SystemExit("gsutil not found on PATH")
    proc = subprocess.run(["gsutil", *args], capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise SystemExit(f"gsutil {' '.join(args)} failed:\n"
                         f"{(proc.stderr or proc.stdout).strip()[-2000:]}")
    return proc


# --- selection --------------------------------------------------------------

def select_names(index: dict[str, dict], audit: dict[str, dict],
                 accept_path: Path | None) -> list[str]:
    """Return the dataset names: pass + accepted gray, never short_severe."""
    ready = {n for n, row in index.items()
             if row.get("generation_status") == "ready"}
    failing = set(audit)
    accepted = read_names(accept_path) if accept_path else set()
    unknown = accepted - ready
    if unknown:
        raise SystemExit(f"accept file names not in the ready corpus: "
                         f"{sorted(unknown)[:5]}")
    chosen = (ready - failing) | accepted
    severe = {n for n, row in audit.items() if row.get("bucket") == "short_severe"}
    chosen -= severe
    return sorted(chosen, key=lambda n: (index[n]["source_rank"], n))


# --- remote inventory -------------------------------------------------------

def list_take_mp3s(gcs_runs: str) -> dict[str, tuple[str, int | None]]:
    """Map ``<name>_<seed>`` -> (gs:// uri, bytes) for every session take."""
    pattern = gcs_runs.rstrip("/") + "/*_yt500inst*/*.mp3"
    proc = _gsutil("ls", "-l", pattern, check=False)
    out: dict[str, tuple[str, int | None]] = {}
    for line in proc.stdout.splitlines():
        m = re.match(r"\s*(\d+)\s+\S.*?\s+(gs://\S+\.mp3)\s*$", line)
        if not m:
            continue
        size, uri = int(m.group(1)), m.group(2)
        stem = uri.rsplit("/", 1)[-1][:-4]
        out[stem] = (uri, size)
    if not out:
        raise SystemExit(f"no take MP3s found under {pattern}\n"
                         f"{(proc.stderr or proc.stdout).strip()[-1000:]}")
    return out


def count_remote(uri: str, pattern: str, *, dirs: bool = False) -> int:
    args = ["ls"] + (["-d"] if dirs else []) + [uri.rstrip("/") + "/" + pattern]
    proc = _gsutil(*args, check=False)
    return sum(1 for line in proc.stdout.splitlines() if line.startswith("gs://"))


def remote_suffix_count(prefix_uri: str, suffix: str) -> int | None:
    """Count objects under ``prefix_uri`` whose name ends with ``suffix``.

    ``gsutil ls`` on a wildcard stats every object (minutes for 460 folders);
    one paginated JSON-API listing returns 1000 per request.
    """
    import urllib.parse
    import urllib.request

    bucket, _, prefix = prefix_uri[len("gs://"):].partition("/")
    try:
        token = subprocess.run(["gcloud", "auth", "print-access-token"],
                               capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None
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
        except OSError as exc:
            raise SystemExit(f"cannot list {prefix_uri}: {exc}") from exc
        count += sum(1 for obj in payload.get("items", [])
                     if str(obj.get("name", "")).endswith(suffix))
        page = payload.get("nextPageToken")
        if not page:
            return count


# --- take index -------------------------------------------------------------

def index_takes(meta_root: Path) -> dict[str, list[dict]]:
    """Group every local take by song name."""
    by_name: dict[str, list[dict]] = {}
    for run_dir in sorted(p for p in meta_root.iterdir() if p.is_dir()):
        manifest = read_json(run_dir / "batch_manifest.json") if (
            run_dir / "batch_manifest.json").is_file() else None
        if not manifest:
            continue
        for entry in manifest.get("tracks", []):
            name, seed = entry.get("name"), entry.get("seed")
            if not name or seed is None:
                continue
            side = run_dir / f"{name}_{seed}.json"
            if not side.is_file():
                continue  # never rendered (killed session manifest entry)
            meta = read_json(side)
            by_name.setdefault(name, []).append({
                "run": run_dir.name,
                "name": name,
                "seed": seed,
                "stem": f"{name}_{seed}",
                "entry": entry,
                "sidecar": meta,
                "end_utc": meta.get("end_utc") or "",
            })
    return by_name


def choose_takes(names: list[str], by_name: dict[str, list[dict]],
                 mp3s: dict[str, tuple[str, int | None]],
                 corpus: dict) -> tuple[dict[str, dict], list[dict]]:
    """Pick the newest valid MP3 take per song; return (chosen, rejected)."""
    chosen: dict[str, dict] = {}
    rejected: list[dict] = []
    for name in names:
        usable = []
        for take in by_name.get(name, []):
            side = take["sidecar"]
            if take["stem"] not in mp3s:
                continue
            if side.get("status") != "ok" or side.get("exit") != 0:
                continue
            if side.get("abc_sha256") != corpus["score_hashes"].get(name):
                continue
            usable.append(take)
        if not usable:
            rejected.append({"name": name, "reason": "no valid take with an MP3"})
            continue
        usable.sort(key=lambda t: (t["end_utc"], t["run"]))
        chosen[name] = usable[-1]
    return chosen, rejected


# --- build ------------------------------------------------------------------

def load_prompt_text(meta_root: Path, take: dict, kind: str) -> tuple[Path, str]:
    name = take["name"]
    path = meta_root / take["run"] / "prompts" / f"{name}_{kind}.txt"
    if not path.is_file():
        raise SystemExit(f"missing {kind} prompt: {path}")
    return path, path.read_text(encoding="utf-8")


def load_score(meta_root: Path, take: dict) -> Path:
    path = meta_root / take["run"] / "scores" / f"{take['name']}.abc"
    if not path.is_file():
        raise SystemExit(f"missing score: {path}")
    return path


def build_row(name: str, take: dict, index_row: dict, audit_row: dict | None,
              meta_root: Path, mp3s: dict, corpus: dict,
              style_sha: str, recipe: dict) -> dict:
    entry = take["entry"]
    side = take["sidecar"]
    lyrics_path, lyrics_text = load_prompt_text(meta_root, take, "lyrics")
    style_path, style_text = load_prompt_text(meta_root, take, "style")
    score_path = load_score(meta_root, take)

    lyrics_sha = sha256_file(lyrics_path)
    take_style_sha = sha256_file(style_path)
    score_sha = sha256_file(score_path)
    problems = []
    if entry.get("lyrics_sha256") and entry["lyrics_sha256"] != lyrics_sha:
        problems.append("lyrics hash != run manifest")
    if entry.get("style_sha256") and entry["style_sha256"] != take_style_sha:
        problems.append("style hash != run manifest")
    if score_sha != corpus["score_hashes"].get(name):
        problems.append("score hash != corpus")
    if take_style_sha != style_sha:
        problems.append("style != canonical manifest-18 style")
    if not TAG_RE.search(lyrics_text):
        problems.append("lyrics has no [section] tag")
    if problems:
        raise SystemExit(f"{name}: " + "; ".join(problems))

    nominal = index_row["nominal_seconds"]
    wav_s = side.get("wav_duration_s")
    delta = round((wav_s - nominal) / nominal * 100, 1) if (
        wav_s and nominal) else None
    uri, size = mp3s[take["stem"]]

    return {
        "name": name,
        "rank": index_row["source_rank"],
        "video_id": index_row["video_id"],
        "title": index_row["title"],
        "artist": index_row["source_artist"],
        "country": index_row.get("country"),
        "tier": index_row.get("tier"),
        "gate": "pass" if audit_row is None else "accepted",
        "nominal_s": nominal,
        "wav_s": wav_s,
        "delta_pct": delta,
        "sections": index_row.get("sections") or [],
        "artifacts": {
            "audio": "audio.mp3",
            "lyrics": "lyrics.txt",
            "style": "style.txt",
            "score": "score.abc",
        },
        "generation": {
            "run": take["run"],
            "seed": take["seed"],
            "cap": entry.get("cap"),
            "engine": side.get("engine"),
            "status": side.get("status"),
            "exit": side.get("exit"),
            "end_utc": side.get("end_utc"),
        },
        "lyrics": {"kind": "section_tags", "sha256": lyrics_sha,
                   "text": lyrics_text},
        "style": {"sha256": take_style_sha, "id": "manifest18"},
        "recipe": recipe,
        "score": {"abc_sha256": score_sha,
                  "source": f"{GCS_RUNS}/{take['run']}/scores/{name}.abc"},
        "audio": {"mp3_bytes": size, "mp3_sha256": None,
                  "source": uri, "wav_sha256": side.get("wav_sha256")},
        "provenance": {
            "audit_bucket": "pass" if audit_row is None else audit_row["bucket"],
            "takes": [],
        },
    }


def add_provenance(rows: list[dict], by_name: dict[str, list[dict]]) -> None:
    for row in rows:
        row["provenance"]["takes"] = sorted(
            take["stem"] for take in by_name.get(row["name"], []))


def manifest_files() -> list[dict]:
    """Every root file the manifest pins, in build order."""
    files = []
    for rel in ("catalog.jsonl", "catalog.csv", "catalog.md", "tracks.jsonl",
                "tracks.parquet", "playlist.m3u", "README.md",
                "DATASET_CARD.md", "recipe/style.txt", "recipe/recipe.json",
                "captions.jsonl", "captions.sha256"):
        path = LOCAL / rel
        if path.is_file():
            files.append({"path": rel, "sha256": sha256_file(path),
                          "bytes": path.stat().st_size})
    return files


def make_manifest(rows: list[dict], recipe: dict, style_sha: str,
                  built_at: str, *, dataset_version: str = "v0.1",
                  captions: dict | None = None) -> dict:
    from collections import Counter
    runs = sorted({r["generation"]["run"] for r in rows})
    lyrics = Counter(r["lyrics"]["sha256"] for r in rows)
    styles = Counter(r["style"]["sha256"] for r in rows)
    counts = {
        "tracks": len(rows),
        "pass": sum(1 for r in rows if r["gate"] == "pass"),
        "accepted": sum(1 for r in rows if r["gate"] == "accepted"),
        "audio_bytes": sum(r["audio"]["mp3_bytes"] or 0 for r in rows),
        "unique_lyrics_plans": len(lyrics),
        "unique_styles": len(styles),
    }
    layout = {
        "per_track": "tracks/<name>/{audio.mp3,lyrics.txt,style.txt,score.abc,track.json}",
        "catalog": "catalog.jsonl (same rows as tracks.jsonl)",
    }
    if captions is not None:
        counts["captions"] = captions["count"]
        layout["per_track"] = ("tracks/<name>/{audio.mp3,lyrics.txt,style.txt,"
                               "score.abc,track.json,caption.txt,caption.json}")
        layout["captions"] = "captions.jsonl (one row per track)"
    manifest = {
        "dataset": "YT500 Instrumental — quality-gated tracks",
        "dataset_version": dataset_version,
        "generated_at": built_at,
        "source_runs_uri": GCS_RUNS,
        "source_runs": runs,
        "gate": f"abs(wav_s - nominal_s) / nominal_s <= {GATE_PCT / 100}",
        "counts": counts,
        "recipe": recipe,
        "style_sha256": style_sha,
        "layout": layout,
        "files": manifest_files(),
    }
    if captions is not None:
        manifest["captions"] = {k: v for k, v in captions.items() if k != "count"}
    return manifest


def make_parquet(rows: list[dict]) -> str | None:
    """Write tracks.parquet when pandas/pyarrow are available."""
    try:
        import pandas as pd  # noqa: WPS433
    except ImportError:
        return None
    flat = []
    for r in rows:
        rec = {
            "name": r["name"], "rank": r["rank"], "video_id": r["video_id"],
            "title": r["title"], "artist": r["artist"],
            "country": r["country"], "tier": r["tier"], "gate": r["gate"],
            "nominal_s": r["nominal_s"], "wav_s": r["wav_s"],
            "delta_pct": r["delta_pct"],
            "sections": "|".join(r["sections"]),
            "run": r["generation"]["run"], "seed": r["generation"]["seed"],
            "cap": r["generation"]["cap"], "engine": r["generation"]["engine"],
            "lyrics_kind": r["lyrics"]["kind"],
            "lyrics_sha256": r["lyrics"]["sha256"],
            "lyrics_text": r["lyrics"]["text"],
            "style_sha256": r["style"]["sha256"],
            "abc_sha256": r["score"]["abc_sha256"],
            "mp3_source": r["audio"]["source"],
            "mp3_bytes": r["audio"]["mp3_bytes"],
            "wav_sha256": r["audio"]["wav_sha256"],
            "takes": "|".join(r["provenance"]["takes"]),
        }
        for column in CAPTION_COLUMNS:
            if "caption_sha256" in r:
                rec[column] = r.get(column)
        flat.append(rec)
    df = pd.DataFrame(flat)
    out = LOCAL / "tracks.parquet"
    df.to_parquet(out, index=False)
    return out.name


def make_readme(rows: list[dict], style_text: str, recipe: dict,
                built_at: str | None = None) -> str:
    n = len(rows)
    total_gb = sum(r["audio"]["mp3_bytes"] or 0 for r in rows) / 1e9
    has_captions = bool(rows) and "caption_sha256" in rows[0]
    layout = (
        "tracks/<name>/\n"
        f"  audio.mp3     the kept take ({total_gb:.2f} GB total)\n"
        "  lyrics.txt    section tag plan used for this take\n"
        "  style.txt     exact style prompt used\n"
        "  score.abc     instrumental ABC score\n"
        "  track.json    ids, hashes, seed, provenance"
        + (", caption pointer\n"
           "  caption.txt   polished prose caption for this take\n"
           "  caption.json  full caption record (chunks, tags, audio)\n"
           "catalog.jsonl   one row per track, tag plan + caption fields inlined\n"
           "catalog.csv     spreadsheet view\n"
           "catalog.md      human-readable table\n"
           "playlist.m3u    rank order\n"
           "captions.jsonl  one row per track (caption, tags, hashes)\n"
           "captions.sha256 sha256sum list for every caption artifact\n"
           "recipe/         canonical style + LoRA/scales/CoT\n"
           if has_captions else "\n"
           "catalog.jsonl   one row per track, tag plan inlined\n"
           "catalog.csv     spreadsheet view\n"
           "catalog.md      human-readable table\n"
           "playlist.m3u    rank order\n"
           "recipe/         canonical style + LoRA/scales/CoT\n")
    )
    captions_section = """
## Captions

Every track carries a prose caption written from its audio by the ACE-Step
Captioner (4-bit `ACE-Step/acestep-captioner`) and polished by a small instruct
model. `caption.txt` is the final prose; `caption.json` keeps the per-chunk text,
the take it describes and the tag lists.

The `instruments` / `vocals` / `production` lists come from deterministic lexicon
matching and are **experimental** — they are not ground truth.
""" if has_captions else ""
    return f"""# YT500 instrumental — legitimate-track dataset

{n} instrumental takes from the YT500 corpus, each in its own folder with the
audio, the section tag plan, the style prompt, the score and the take metadata.

## What "legit" means

A take is included when its rendered duration is within ±15% of the score's
nominal length, its sidecar says `status: ok` / `exit: 0`, and its score hash
matches the frozen corpus. The 7 severe-short takes are excluded; 22 borderline
takes can be added later through an accept file. The full audit is
`quality_audit_duration.json` in the generation outputs.

## Layout

```
{layout}```

## Important: the "lyrics" are section tags

`lyrics.txt` is the tag plan derived from the score's `% section` comments
(`[intro]`, `[verse]`, `[chorus]`, …). It is what the LoRA was conditioned on,
not sung words. `track.json` records `"kind": "section_tags"` so consumers are
not misled.
{captions_section}
## Recipe

- Style: `recipe/style.txt`, sha256 `{recipe['style_sha256']}`
- CoT: `{recipe['defaults']['cot']}`
- LoRA: `{recipe['defaults']['lora']}` (AR scale {recipe['defaults']['lora_ar_scale']},
  NAR scale {recipe['defaults']['lora_nar_scale']})
- Trigger: `{recipe['defaults']['trigger']}`

The style prompt:

```
{style_text.strip()}
```

## Fetch

```bash
# one track
gsutil -m cp -r {DATASET_URI}/tracks/<name> .

# the catalogue
gsutil cp {DATASET_URI}/catalog.jsonl .

# all audio (≈{total_gb:.1f} GB)
gsutil -m cp {DATASET_URI}/tracks/*/audio.mp3 .
```

Built {built_at or utcnow()}.
"""


def write_catalogs(rows: list[dict], *, style_text: str, recipe: dict,
                   built_at: str) -> None:
    """The single writer of every root catalogue file.

    ``build`` and ``--attach-captions`` both go through here, so the layout,
    column order, line endings and markdown header can never drift between the
    two modes.  Caption columns and the two caption indexes are written only
    when the rows carry a ``caption_sha256``.
    """
    LOCAL.mkdir(parents=True, exist_ok=True)
    has_captions = bool(rows) and "caption_sha256" in rows[0]

    with (LOCAL / "catalog.jsonl").open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps({k: v for k, v in row.items()
                                 if not k.startswith("_")},
                                ensure_ascii=False) + "\n")
    shutil.copyfile(LOCAL / "catalog.jsonl", LOCAL / "tracks.jsonl")

    cols = ["name", "rank", "video_id", "title", "artist", "country", "tier",
            "nominal_s", "wav_s", "delta_pct", "gate", "sections", "run",
            "seed", "cap", "lyrics_sha256", "style_sha256", "abc_sha256",
            "mp3_source"]
    if has_captions:
        cols += list(CAPTION_COLUMNS)
    with (LOCAL / "catalog.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for r in rows:
            line = [r["name"], r["rank"], r["video_id"], r["title"],
                    r["artist"], r["country"], r["tier"], r["nominal_s"],
                    r["wav_s"], r["delta_pct"], r["gate"],
                    "|".join(r["sections"]), r["generation"]["run"],
                    r["generation"]["seed"], r["generation"]["cap"],
                    r["lyrics"]["sha256"], r["style"]["sha256"],
                    r["score"]["abc_sha256"], r["audio"]["source"]]
            if has_captions:
                line += [r.get("caption_sha256", ""), r.get("caption_chars", ""),
                         r.get("rewrite_status", "")]
            w.writerow(line)

    md = ["# YT500 instrumental — catalogue", "",
          f"{len(rows)} tracks, rank order. "
          "`lyrics` are section tag plans.", "",
          "| # | Track | Title — artist | Dur | Δ | Tags | Run |",
          "|---:|---|---|---:|---:|---|---|"]
    for r in rows:
        md.append(f"| {r['rank']} | `{r['name']}` | {r['title']} — {r['artist']} "
                  f"| {r['wav_s']:.0f}s | {r['delta_pct']:+.1f}% "
                  f"| {len(TAG_RE.findall(r['lyrics']['text']))} "
                  f"| `{r['generation']['run']}` |")
    write_text(LOCAL / "catalog.md", "\n".join(md) + "\n")

    m3u = ["#EXTM3U"]
    for r in rows:
        m3u.append(f"#EXTINF:{int(round(r['wav_s'] or 0))},"
                   f"{r['title']} — {r['artist']} ({r['delta_pct']:+.1f}%)")
        m3u.append(f"tracks/{r['name']}/audio.mp3")
    write_text(LOCAL / "playlist.m3u", "\n".join(m3u) + "\n")

    doc = make_readme(rows, style_text, recipe, built_at)
    write_text(LOCAL / "README.md", doc)
    write_text(LOCAL / "DATASET_CARD.md", doc)
    make_parquet(rows)

    if not has_captions:
        return
    index = []
    checksums = []
    for r in rows:
        sha = r.get("caption_sha256")
        if not sha:
            continue
        entry = r.get("_caption_index") or {}
        index.append({
            "name": r["name"],
            "file": f"{r['name']}_{r['generation']['seed']}.mp3",
            "seed": r["generation"]["seed"],
            "caption": entry.get("caption", ""),
            "instruments": entry.get("instruments", []),
            "vocals": entry.get("vocals", []),
            "production": entry.get("production", []),
            "rewrite_status": r.get("rewrite_status"),
            "caption_sha256": sha,
        })
        for fn in CAPTION_FILES:
            path = LOCAL / "tracks" / r["name"] / fn
            checksums.append(f"{sha256_file(path)}  tracks/{r['name']}/{fn}")
    write_text(LOCAL / "captions.jsonl",
               "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in index))
    write_text(LOCAL / "captions.sha256", "\n".join(checksums) + "\n")

def build(args) -> int:
    index = {r["name"]: r for r in read_json(INDEX)["tracks"]}
    audit = {r["name"]: r for r in read_json(AUDIT)["tracks"]}
    corpus = drv.load_corpus(drv.DEFAULT_CORPUS)
    names = select_names(index, audit, args.accept)
    by_name = index_takes(args.meta_dir)
    mp3s = list_take_mp3s(GCS_RUNS)
    chosen, rejected = choose_takes(names, by_name, mp3s, corpus)
    if args.strict and rejected:
        raise SystemExit(f"{len(rejected)} selected name(s) have no valid take: "
                         f"{[r['name'] for r in rejected[:5]]}")

    data = corpus["data"]
    style_text = data["defaults"]["style"]
    style_sha = hashlib.sha256(style_text.encode("utf-8")).hexdigest()
    recipe = {
        "style_sha256": style_sha,
        "source": "manifests/fadhl_shaker_instrumental_18.json defaults.style",
        "defaults": data["defaults"],
        "loras": data["loras"],
        "model": "Yue2-3B-GGUF",
    }

    rows = []
    for name in names:
        if name not in chosen:
            continue
        take = chosen[name]
        row = build_row(name, take, index[name], audit.get(name),
                        args.meta_dir, mp3s, corpus, style_sha,
                        {k: recipe["defaults"][k] for k in
                         ("cot", "lora", "lora_ar_scale", "lora_nar_scale",
                          "trigger")} | {"model": "Yue2-3B-GGUF"})
        rows.append(row)
    add_provenance(rows, by_name)

    if args.dry_run:
        print(f"dataset set: {len(rows)} tracks "
              f"({sum(1 for r in rows if r['gate'] == 'pass')} pass, "
              f"{sum(1 for r in rows if r['gate'] == 'accepted')} accepted)")
        print(f"audio: {sum(r['audio']['mp3_bytes'] or 0 for r in rows) / 1e9:.2f} GB")
        print(f"would write: {LOCAL}")
        return 0

    tracks_dir = LOCAL / "tracks"
    if tracks_dir.exists():
        shutil.rmtree(tracks_dir)
    recipe_dir = LOCAL / "recipe"
    if recipe_dir.exists():
        shutil.rmtree(recipe_dir)
    recipe_dir.mkdir(parents=True)

    for row in rows:
        tdir = tracks_dir / row["name"]
        tdir.mkdir(parents=True, exist_ok=True)
        take = chosen[row["name"]]
        lyrics_path, lyrics_text = load_prompt_text(args.meta_dir, take, "lyrics")
        style_path, take_style_text = load_prompt_text(args.meta_dir, take, "style")
        score_path = load_score(args.meta_dir, take)
        write_text(tdir / "lyrics.txt", lyrics_text)
        write_text(tdir / "style.txt", take_style_text)
        shutil.copyfile(score_path, tdir / "score.abc")
        write_json(tdir / "track.json", row)

    write_text(recipe_dir / "style.txt", style_text)
    write_json(recipe_dir / "recipe.json", recipe)
    built_at = utcnow()
    write_catalogs(rows, style_text=style_text, recipe=recipe, built_at=built_at)
    manifest = make_manifest(rows, recipe, style_sha, built_at)
    write_json(LOCAL / "manifest.json", manifest)
    parquet = "tracks.parquet" if (LOCAL / "tracks.parquet").is_file() else "skipped"
    write_text(LOCAL / "_SUCCESS",
               f"{built_at}\ntracks={len(rows)}\nparquet={parquet}\n")
    if rejected:
        write_text(LOCAL / "rejected.jsonl",
                   "".join(json.dumps(r, ensure_ascii=False) + "\n"
                           for r in rejected))

    build_info = {
        "built_at": built_at,
        "dataset_uri": DATASET_URI,
        "tracks": len(rows),
        "pass": sum(1 for r in rows if r["gate"] == "pass"),
        "accepted": sum(1 for r in rows if r["gate"] == "accepted"),
        "rejected": len(rejected),
        "style_sha256": style_sha,
        "inputs": {
            "audit": sha256_file(AUDIT),
            "index": sha256_file(INDEX),
            "corpus": sha256_file(drv.DEFAULT_CORPUS),
        },
        "names_sha256": hashlib.sha256(
            "\n".join(r["name"] for r in rows).encode()).hexdigest(),
    }
    write_json(LOCAL / ".build.json", build_info)
    print(f"built {len(rows)} tracks -> {LOCAL}")
    print(f"  pass={build_info['pass']} accepted={build_info['accepted']} "
          f"rejected={len(rejected)} style={style_sha[:16]}…")
    return 0


# --- captions ---------------------------------------------------------------

def load_rows() -> list[dict]:
    """Read the per-track rows of the local tree (``tracks/*/track.json``)."""
    rows = []
    for path in sorted((LOCAL / "tracks").glob("*/track.json")):
        rows.append(read_json(path))
    if not rows:
        raise SystemExit(f"no tracks/*/track.json under {LOCAL}; run --build or pull the tree")
    rows.sort(key=lambda r: (r["rank"], r["name"]))
    names = [r["name"] for r in rows]
    if len(names) != len(set(names)):
        raise SystemExit("duplicate track names in the tree")
    return rows


def parse_caption_album(path: Path) -> tuple[dict[str, dict], str]:
    """Index a caption album by the full take stem ``<name>_<seed>``.

    Returns ``(by_stem, album_sha256)``.  The name group is greedy because
    video ids contain ``_``; the seed is the trailing digit run.  A caption is
    tied to a take, so a name-only match must never be used.
    """
    raw = path.read_bytes()
    album = json.loads(raw)
    by_stem: dict[str, dict] = {}
    for track in album.get("tracks", []):
        stem = Path(str(track.get("file", ""))).stem
        if not CAPTION_STEM_RE.match(stem):
            raise SystemExit(
                f"album entry without <name>_<seed>: {track.get('file')!r}")
        if stem in by_stem:
            raise SystemExit(f"album has two entries for take {stem}")
        by_stem[stem] = track
    return by_stem, sha256_bytes(raw)


def caption_record(row: dict, track: dict, *, album_sha256: str = "",
                   pipeline_version: int = 3, pipeline_stage: str = "polished",
                   allow_unpolished: bool = False,
                   min_chars: int = MIN_CAPTION_CHARS) -> tuple[dict, str]:
    """Build the ``caption.json`` record and the ``caption.txt`` text for a row.

    Hard guards: the album entry must be exactly the dataset's take
    (``<name>_<seed>``); the caption must be non-empty, at least ``min_chars``
    long and free of chunk-relative timecodes; ``rewrite_status`` must be
    terminal, and a ``failed`` one is accepted only with ``--allow-unpolished``
    (and then flagged).
    """
    name = row["name"]
    seed = row["generation"]["seed"]
    stem = f"{name}_{seed}"
    actual = Path(str(track.get("file", ""))).stem
    if actual != stem:
        raise SystemExit(
            f"{name}: album take is {actual!r}, expected {stem!r} for seed {seed}")

    caption = str(track.get("caption") or "").strip()
    if not caption:
        raise SystemExit(f"{name}: empty caption for take {stem}")
    hit = CAPTION_TIME_RE.search(caption)
    if hit:
        raise SystemExit(f"{name}: caption carries a time reference {hit.group(0)!r}")
    if len(caption) < min_chars:
        raise SystemExit(f"{name}: caption is {len(caption)} chars, "
                         f"below the {min_chars}-char floor")

    status = track.get("rewrite_status")
    unpolished = False
    if status == "failed":
        if not allow_unpolished:
            raise SystemExit(
                f"{name}: rewrite_status is 'failed' (pass --allow-unpolished "
                "to attach the raw caption, flagged)")
        unpolished = True
    elif status not in CAPTION_STATUSES:
        raise SystemExit(f"{name}: unexpected rewrite_status {status!r}")

    text = caption + "\n"
    record = {
        "schema": CAPTION_SCHEMA,
        "name": name,
        "take": {"file": track["file"], "seed": seed,
                 "run": row["generation"]["run"]},
        "caption": caption,
        "caption_sha256": sha256_bytes(text.encode("utf-8")),
        "caption_chars": len(caption),
        "caption_raw": track.get("caption_raw") or "",
        "chunk_captions": list(track.get("chunk_captions") or []),
        "instruments": list(track.get("instruments") or []),
        "vocals": list(track.get("vocals") or []),
        "production": list(track.get("production") or []),
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
            "album": ALBUM_URI,
            "album_sha256": album_sha256,
        },
        "audio": {
            "duration_s": track.get("duration_s"),
            "bitrate_kbps": track.get("bitrate_kbps"),
            "chunk_count": track.get("chunk_count"),
            "silence_trimmed_s": track.get("silence_trimmed_s"),
        },
    }
    if unpolished:
        record["unpolished"] = True
    return record, text


def resolve_album(args) -> Path:
    if args.captions:
        path = args.captions.expanduser()
        if not path.is_file():
            raise SystemExit(f"--captions not found: {path}")
        return path
    if args.captions_uri:
        dest = Path(tempfile.mkdtemp(prefix="yt500-album-")) / "caption_album.json"
        proc = subprocess.run(
            ["gcloud", "storage", "cp", "-q", args.captions_uri, str(dest)],
            capture_output=True, text=True)
        if proc.returncode != 0:
            raise SystemExit(f"could not fetch {args.captions_uri}:\n"
                             f"{(proc.stderr or proc.stdout).strip()[-1000:]}")
        return dest
    raise SystemExit("--attach-captions needs --captions PATH or --captions-uri URI")


def attach(args) -> int:
    """Attach a caption album to the v0.1 tree under ``--local``."""
    album_path = resolve_album(args)
    album = read_json(album_path)
    by_stem, album_sha = parse_caption_album(album_path)
    version = album.get("caption_pipeline_version")
    stage = album.get("caption_stage")
    if version != 3:
        raise SystemExit(f"album pipeline version {version!r} != 3")
    if stage != "polished":
        raise SystemExit(f"album stage {stage!r} != 'polished'")

    manifest = read_json(LOCAL / "manifest.json")
    rows = load_rows()

    leaked = list((LOCAL / "tracks").glob("*/audio.mp3"))
    if leaked:
        raise SystemExit(f"{len(leaked)} audio.mp3 in the metadata tree; audio "
                         "stays server-side (pull the tree with "
                         "-x '.*audio\\.mp3$')")

    # validate every row before writing anything
    prepared: list[tuple[dict, dict, str]] = []
    missing: list[str] = []
    for row in rows:
        stem = f"{row['name']}_{row['generation']['seed']}"
        track = by_stem.get(stem)
        if track is None:
            if args.allow_missing_captions:
                missing.append(row["name"])
                continue
            raise SystemExit(f"{row['name']}: album has no caption for its take {stem}")
        record, text = caption_record(
            row, track,
            album_sha256=album_sha,
            pipeline_version=version,
            pipeline_stage=stage,
            allow_unpolished=args.allow_unpolished,
            min_chars=args.min_caption_chars,
        )
        prepared.append((row, record, text))

    for row, record, text in prepared:
        tdir = LOCAL / "tracks" / row["name"]
        write_text(tdir / "caption.txt", text)
        write_json(tdir / "caption.json", record)
        artifacts = dict(row.get("artifacts") or {})
        artifacts["caption"] = "caption.json"
        artifacts["caption_text"] = "caption.txt"
        row["artifacts"] = artifacts
        row["caption"] = {
            "file": "caption.json",
            "text_file": "caption.txt",
            "sha256": record["caption_sha256"],
            "chars": record["caption_chars"],
            "rewrite_status": record["rewrite"]["status"],
            "pipeline_version": record["pipeline"]["version"],
            "take": f"{row['name']}_{row['generation']['seed']}",
        }
        write_json(tdir / "track.json", row)
        row["caption_sha256"] = record["caption_sha256"]
        row["caption_chars"] = record["caption_chars"]
        row["rewrite_status"] = record["rewrite"]["status"]
        row["_caption_index"] = {
            "caption": record["caption"],
            "instruments": record["instruments"],
            "vocals": record["vocals"],
            "production": record["production"],
        }

    recipe = read_json(LOCAL / "recipe" / "recipe.json")
    style_text = (LOCAL / "recipe" / "style.txt").read_text(encoding="utf-8")
    style_sha = hashlib.sha256(style_text.encode("utf-8")).hexdigest()
    generated_at = manifest.get("generated_at") or utcnow()
    write_catalogs(rows, style_text=style_text, recipe=recipe, built_at=generated_at)

    previous = manifest.get("captions") or {}
    captions_block = {
        "count": len(prepared),
        "source": ALBUM_URI,
        "source_sha256": album_sha,
        "pipeline_version": version,
        "attached_at": previous.get("attached_at") or utcnow(),
    }
    if missing:
        captions_block["missing"] = missing
    manifest = make_manifest(rows, recipe, style_sha, generated_at,
                             dataset_version="v0.2", captions=captions_block)
    write_json(LOCAL / "manifest.json", manifest)
    write_text(LOCAL / "_SUCCESS",
               f"{generated_at}\ntracks={len(rows)}\n"
               f"captions={len(prepared)}\nparquet=tracks.parquet\n")

    print(f"attached {len(prepared)}/{len(rows)} captions -> {LOCAL}")
    print(f"  album {album_sha[:16]}…  version {version}  dataset v0.2")
    if missing:
        print(f"  no caption for: {missing[:5]}", file=sys.stderr)
    return 0


# --- verify -----------------------------------------------------------------

def verify(args) -> int:
    if not (LOCAL / "catalog.jsonl").is_file():
        raise SystemExit(f"no build at {LOCAL}; run --build first")
    rows = [json.loads(line) for line in
            (LOCAL / "catalog.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()]
    index = {r["name"]: r for r in read_json(INDEX)["tracks"]}
    audit = {r["name"]: r for r in read_json(AUDIT)["tracks"]}
    expected = set(select_names(index, audit, args.accept))
    problems: list[str] = []

    got = [r["name"] for r in rows]
    if len(got) != len(set(got)):
        problems.append("duplicate names in catalog")
    if set(got) != expected:
        problems.append(f"set mismatch: missing={sorted(expected - set(got))[:5]} "
                        f"extra={sorted(set(got) - expected)[:5]}")
    if any(r["name"] in {n for n, a in audit.items()
                         if a["bucket"] == "short_severe"} for r in rows):
        problems.append("short_severe name present")

    for fn in ("manifest.json", "tracks.jsonl", "_SUCCESS", "DATASET_CARD.md",
               "catalog.csv", "catalog.md", "playlist.m3u"):
        if not (LOCAL / fn).is_file():
            problems.append(f"missing top-level {fn}")
    manifest = read_json(LOCAL / "manifest.json") if (
        LOCAL / "manifest.json").is_file() else {}
    if manifest.get("counts", {}).get("tracks") not in (None, len(rows)):
        problems.append("manifest track count != catalog rows")
    if (LOCAL / "tracks.jsonl").is_file():
        aliases = [json.loads(line)["name"] for line in
                   (LOCAL / "tracks.jsonl").read_text(encoding="utf-8").splitlines()
                   if line.strip()]
        if aliases != got:
            problems.append("tracks.jsonl names/order != catalog.jsonl")

    canon_style = (LOCAL / "recipe" / "style.txt").read_text(encoding="utf-8")
    canon_sha = hashlib.sha256(canon_style.encode()).hexdigest()
    for r in rows:
        tdir = LOCAL / "tracks" / r["name"]
        for fn in ARTIFACTS:
            if not (tdir / fn).is_file():
                problems.append(f"{r['name']}: missing {fn}")
        if (tdir / "style.txt").is_file():
            if sha256_file(tdir / "style.txt") != canon_sha:
                problems.append(f"{r['name']}: style copy mismatch")
        if (tdir / "lyrics.txt").is_file():
            text = (tdir / "lyrics.txt").read_text(encoding="utf-8")
            if sha256_file(tdir / "lyrics.txt") != r["lyrics"]["sha256"]:
                problems.append(f"{r['name']}: lyrics hash mismatch")
            if not TAG_RE.search(text):
                problems.append(f"{r['name']}: lyrics has no tag")
        if (tdir / "score.abc").is_file():
            if sha256_file(tdir / "score.abc") != r["score"]["abc_sha256"]:
                problems.append(f"{r['name']}: score hash mismatch")
        if r["style"]["sha256"] != canon_sha:
            problems.append(f"{r['name']}: track style sha != canonical")

    # --- captions ---------------------------------------------------------
    has_captions = bool(rows) and "caption_sha256" in rows[0]
    captioned = [r for r in rows if r.get("caption_sha256")]
    captions_jsonl = LOCAL / "captions.jsonl"
    caption_rows: list[dict] = []
    if captions_jsonl.is_file():
        caption_rows = [json.loads(line) for line in
                        captions_jsonl.read_text(encoding="utf-8").splitlines()
                        if line.strip()]
    if has_captions:
        if len(caption_rows) != len(captioned):
            problems.append(f"captions.jsonl has {len(caption_rows)} rows, "
                            f"expected {len(captioned)}")
        if [c["name"] for c in caption_rows] != [r["name"] for r in captioned]:
            problems.append("captions.jsonl names/order != catalog.jsonl")
        for r in rows:
            name = r["name"]
            if not r.get("caption_sha256"):
                if not args.allow_missing_captions:
                    problems.append(f"{name}: no caption attached")
                continue
            tdir = LOCAL / "tracks" / name
            text_path, json_path = tdir / "caption.txt", tdir / "caption.json"
            if not text_path.is_file() or not json_path.is_file():
                problems.append(f"{name}: missing caption.txt/caption.json")
                continue
            record = read_json(json_path)
            text_sha = sha256_file(text_path)
            if record.get("caption_sha256") != text_sha:
                problems.append(f"{name}: caption.txt sha != caption.json")
            if r.get("caption_sha256") != text_sha:
                problems.append(f"{name}: caption.txt sha != catalog caption_sha256")
            track = read_json(tdir / "track.json")
            block = track.get("caption") or {}
            if block.get("sha256") != text_sha:
                problems.append(f"{name}: caption.txt sha != track.json.caption")
            if block.get("chars") != r.get("caption_chars"):
                problems.append(f"{name}: caption chars differ (track vs catalog)")
            expected_stem = f"{name}_{r['generation']['seed']}"
            if block.get("take") != expected_stem:
                problems.append(f"{name}: track.json.caption.take != {expected_stem}")
            if (track.get("artifacts") or {}).get("caption") != "caption.json":
                problems.append(f"{name}: track.json artifacts.caption missing")
            take = record.get("take") or {}
            if take.get("seed") != r["generation"]["seed"]:
                problems.append(f"{name}: caption take seed != track seed")
            if Path(str(take.get("file", ""))).stem != expected_stem:
                problems.append(f"{name}: caption take file is not <name>_<seed>.mp3")
            if not (record.get("caption") or "").strip():
                problems.append(f"{name}: empty caption text")
            if record.get("rewrite", {}).get("status") == "failed" \
                    and not args.allow_unpolished:
                problems.append(f"{name}: unpolished caption attached "
                                "(pass --allow-unpolished)")

        sha_path = LOCAL / "captions.sha256"
        lines = sha_path.read_text(encoding="utf-8").splitlines() if sha_path.is_file() else []
        if len(lines) != 2 * len(captioned):
            problems.append(f"captions.sha256 has {len(lines)} lines, "
                            f"expected {2 * len(captioned)}")
        for line in lines:
            m = re.match(r"^([0-9a-f]{64})  (.+)$", line)
            if not m:
                problems.append(f"captions.sha256: bad line {line[:60]!r}")
                continue
            target = LOCAL / m.group(2)
            if not target.is_file():
                problems.append(f"captions.sha256: missing {m.group(2)}")
            elif sha256_file(target) != m.group(1):
                problems.append(f"captions.sha256: hash mismatch {m.group(2)}")

        counts = manifest.get("counts") or {}
        if counts.get("captions") not in (None, len(captioned)):
            problems.append("manifest counts.captions != attached captions")
        info = manifest.get("captions") or {}
        for key in ("source", "source_sha256", "pipeline_version", "attached_at"):
            if not info.get(key):
                problems.append(f"manifest captions.{key} missing")
        if manifest.get("dataset_version") != "v0.2":
            problems.append(f"manifest dataset_version "
                            f"{manifest.get('dataset_version')!r} != 'v0.2'")
        if args.captions:
            album = args.captions.expanduser()
            if album.is_file() and info.get("source_sha256") \
                    and info["source_sha256"] != sha256_file(album):
                problems.append("manifest captions.source_sha256 != --captions")

    if args.remote:
        folders = count_remote(DATASET_URI + "/tracks", "*/", dirs=True)
        audio = count_remote(DATASET_URI + "/tracks", "*/audio.mp3")
        if folders != len(rows):
            problems.append(f"remote track folders {folders} != {len(rows)}")
        if audio != len(rows):
            problems.append(f"remote audio files {audio} != {len(rows)}")
        print(f"remote: {folders} folders, {audio} audio files")
        if has_captions:
            caption_json = remote_suffix_count(DATASET_URI + "/tracks/",
                                               "/caption.json")
            caption_txt = remote_suffix_count(DATASET_URI + "/tracks/",
                                              "/caption.txt")
            for label, count in (("caption.json", caption_json),
                                 ("caption.txt", caption_txt)):
                if count is None:
                    print(f"remote: {label} count skipped (no gcloud token)")
                elif count != len(rows):
                    problems.append(f"remote {label} {count} != {len(rows)}")
                else:
                    print(f"remote: {count} {label}")

    print(f"verified {len(rows)} rows, {len(problems)} problem(s)")
    for p in problems[:40]:
        print("  -", p)
    return 1 if problems else 0


# --- publish ----------------------------------------------------------------

def publish(args) -> int:
    if not (LOCAL / "catalog.jsonl").is_file():
        raise SystemExit(f"no build at {LOCAL}; run --build first")
    rows = [json.loads(line) for line in
            (LOCAL / "catalog.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()]

    # Audio is server-side only.  The local tree must not contain any MP3, and
    # the rsync must never carry -d/--delete: the tree has no audio.mp3, so a
    # deleting rsync would remove all published MP3s.
    leaked = list((LOCAL / "tracks").glob("*/audio.mp3"))
    if leaked:
        raise SystemExit(f"{len(leaked)} audio.mp3 in {LOCAL}/tracks; refusing "
                         "to publish (audio is copied server-side, never uploaded)")
    rsync_args = ["-m", "rsync", "-r", str(LOCAL) + "/", DATASET_URI + "/"]
    if any(flag in ("-d", "--delete", "--delete-unmatched-destination-objects")
           for flag in rsync_args):
        raise SystemExit("refusing to publish with a deleting rsync")

    if args.dry_run:
        print(f"would rsync {LOCAL} -> {DATASET_URI}")
        print(f"  {len(rows)} track folders: track.json"
              + (", caption.txt, caption.json" if "caption_sha256" in rows[0]
                 else "") + ", catalog files")
        if args.no_audio:
            print("would not copy audio (--no-audio: metadata-only publish)")
        else:
            print(f"would copy {len(rows)} MP3s server-side")
        return 0

    print(f"uploading metadata -> {DATASET_URI}")
    _gsutil(*rsync_args)

    if args.no_audio:
        print(f"published {len(rows)} metadata tracks to {DATASET_URI} "
              "(audio untouched)")
        return 0

    def copy_one(row: dict) -> tuple[str, str]:
        name = row["name"]
        dest = f"{DATASET_URI}/tracks/{name}/audio.mp3"
        proc = _gsutil("cp", "-n", row["audio"]["source"], dest, check=False)
        return name, "" if proc.returncode == 0 else (
            proc.stderr or proc.stdout).strip()[-500:]

    print(f"copying {len(rows)} MP3s GCS->GCS (16 workers)")
    failures = []
    with ThreadPoolExecutor(max_workers=16) as pool:
        futures = {pool.submit(copy_one, r): r["name"] for r in rows}
        for i, fut in enumerate(as_completed(futures), 1):
            name, err = fut.result()
            if err:
                failures.append((name, err))
            if i % 50 == 0 or i == len(rows):
                print(f"  {i}/{len(rows)}")
    if failures:
        for name, err in failures[:20]:
            print(f"  FAIL {name}: {err}", file=sys.stderr)
        return 1
    print(f"published {len(rows)} tracks to {DATASET_URI}")
    return 0


# --- download ---------------------------------------------------------------

def download(args) -> int:
    dest: Path = args.download_dir.expanduser().resolve()
    dest.mkdir(parents=True, exist_ok=True)
    rows = [json.loads(line) for line in
            (LOCAL / "catalog.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()]

    def fetch(row: dict) -> tuple[str, str]:
        name = row["name"]
        out = dest / f"{name}.mp3"
        if out.is_file() and out.stat().st_size > 0:
            return name, ""
        src = f"{DATASET_URI}/tracks/{name}/audio.mp3"
        proc = _gsutil("cp", "-n", src, str(out), check=False)
        return name, "" if proc.returncode == 0 else (
            proc.stderr or proc.stdout).strip()[-500:]

    failures = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(fetch, r) for r in rows]
        for i, fut in enumerate(as_completed(futures), 1):
            name, err = fut.result()
            if err:
                failures.append((name, err))
            if i % 50 == 0 or i == len(rows):
                print(f"  {i}/{len(rows)}")
    m3u = ["#EXTM3U"]
    for r in rows:
        f = dest / f"{r['name']}.mp3"
        if f.is_file():
            m3u.append(f"#EXTINF:{int(round(r['wav_s'] or 0))},"
                       f"{r['title']} — {r['artist']} ({r['delta_pct']:+.1f}%)")
            m3u.append(f.name)
    write_text(dest / "playlist.m3u", "\n".join(m3u) + "\n")
    print(f"downloaded {len(rows) - len(failures)}/{len(rows)} -> {dest}")
    for name, err in failures[:20]:
        print(f"  FAIL {name}: {err}", file=sys.stderr)
    return 1 if failures else 0


# --- cli --------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    global LOCAL
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--build", action="store_true", help="write the local dataset tree")
    ap.add_argument("--attach-captions", action="store_true",
                    help="attach a caption album to a v0.1 tree (writes v0.2)")
    ap.add_argument("--publish", action="store_true", help="upload and copy audio")
    ap.add_argument("--verify", action="store_true", help="check the build")
    ap.add_argument("--download-dir", type=Path, help="copy published audio locally")
    ap.add_argument("--local", type=Path, default=LOCAL,
                    help=f"dataset tree to read/write (default: {LOCAL})")
    ap.add_argument("--captions", type=Path, default=None,
                    help="caption_album.json (local path)")
    ap.add_argument("--captions-uri", default=None,
                    help=f"caption_album.json (gs:// URI, default {ALBUM_URI})")
    ap.add_argument("--no-audio", action="store_true",
                    help="with --publish: metadata only, never copy MP3s")
    ap.add_argument("--allow-missing-captions", action="store_true",
                    help="attach what exists instead of failing on a missing take")
    ap.add_argument("--allow-unpolished", action="store_true",
                    help="attach a 'failed' rewrite, flagged unpolished")
    ap.add_argument("--min-caption-chars", type=int, default=MIN_CAPTION_CHARS,
                    help=f"caption length floor (default {MIN_CAPTION_CHARS})")
    ap.add_argument("--accept", type=Path, default=None,
                    help="accept-file with gray names (default: none)")
    ap.add_argument("--meta-dir", type=Path, default=META,
                    help=f"synced run metadata (default: {META})")
    ap.add_argument("--refresh-meta", action="store_true",
                    help="re-sync run metadata from GCS first")
    ap.add_argument("--skip-broken", action="store_false", dest="strict",
                    help="demote a broken selected take to rejected.jsonl")
    ap.add_argument("--remote", action="store_true",
                    help="with --verify: also count objects in the dataset prefix")
    ap.add_argument("--dry-run", action="store_true")
    ap.set_defaults(strict=True)
    args = ap.parse_args(argv)

    LOCAL = args.local.expanduser().resolve()

    if not any((args.build, args.publish, args.verify, args.download_dir,
                args.attach_captions)):
        ap.print_help()
        return 2

    if args.refresh_meta:
        print(f"refreshing run metadata -> {args.meta_dir}")
        drv.fetch_metadata(GCS_RUNS, args.meta_dir, refresh=True)

    if args.attach_captions:
        return attach(args)
    if args.build:
        rc = build(args)
        if rc:
            return rc
    if args.verify:
        return verify(args)
    if args.publish:
        return publish(args)
    if args.download_dir:
        return download(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
