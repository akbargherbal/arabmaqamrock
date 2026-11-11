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
    --verify           re-check hashes, counts and folder completeness
    --publish          upload metadata, then copy audio GCS -> GCS
    --download-dir     copy the published audio locally
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


# --- small helpers ----------------------------------------------------------

def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


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


def make_manifest(rows: list[dict], recipe: dict, style_sha: str,
                  built_at: str) -> dict:
    from collections import Counter
    runs = sorted({r["generation"]["run"] for r in rows})
    lyrics = Counter(r["lyrics"]["sha256"] for r in rows)
    styles = Counter(r["style"]["sha256"] for r in rows)
    files = []
    for rel in ("catalog.jsonl", "catalog.csv", "catalog.md", "tracks.jsonl",
                "tracks.parquet", "playlist.m3u", "README.md",
                "DATASET_CARD.md", "recipe/style.txt", "recipe/recipe.json"):
        path = LOCAL / rel
        if path.is_file():
            files.append({"path": rel, "sha256": sha256_file(path),
                          "bytes": path.stat().st_size})
    return {
        "dataset": "YT500 Instrumental — quality-gated tracks",
        "dataset_version": "v0.1",
        "generated_at": built_at,
        "source_runs_uri": GCS_RUNS,
        "source_runs": runs,
        "gate": f"abs(wav_s - nominal_s) / nominal_s <= {GATE_PCT / 100}",
        "counts": {
            "tracks": len(rows),
            "pass": sum(1 for r in rows if r["gate"] == "pass"),
            "accepted": sum(1 for r in rows if r["gate"] == "accepted"),
            "audio_bytes": sum(r["audio"]["mp3_bytes"] or 0 for r in rows),
            "unique_lyrics_plans": len(lyrics),
            "unique_styles": len(styles),
        },
        "recipe": recipe,
        "style_sha256": style_sha,
        "layout": {
            "per_track": "tracks/<name>/{audio.mp3,lyrics.txt,style.txt,score.abc,track.json}",
            "catalog": "catalog.jsonl (same rows as tracks.jsonl)",
        },
        "files": files,
    }


def make_parquet(rows: list[dict]) -> str | None:
    """Write tracks.parquet when pandas/pyarrow are available."""
    try:
        import pandas as pd  # noqa: WPS433
    except ImportError:
        return None
    flat = []
    for r in rows:
        flat.append({
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
        })
    df = pd.DataFrame(flat)
    out = LOCAL / "tracks.parquet"
    df.to_parquet(out, index=False)
    return out.name


def make_readme(rows: list[dict], style_text: str, recipe: dict) -> str:
    n = len(rows)
    total_gb = sum(r["audio"]["mp3_bytes"] or 0 for r in rows) / 1e9
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
tracks/<name>/
  audio.mp3     the kept take ({total_gb:.2f} GB total)
  lyrics.txt    section tag plan used for this take
  style.txt     exact style prompt used
  score.abc     instrumental ABC score
  track.json    ids, hashes, seed, provenance
catalog.jsonl   one row per track, tag plan inlined
catalog.csv     spreadsheet view
catalog.md      human-readable table
playlist.m3u    rank order
recipe/         canonical style + LoRA/scales/CoT
```

## Important: the "lyrics" are section tags

`lyrics.txt` is the tag plan derived from the score's `% section` comments
(`[intro]`, `[verse]`, `[chorus]`, …). It is what the LoRA was conditioned on,
not sung words. `track.json` records `"kind": "section_tags"` so consumers are
not misled.

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

Built {utcnow()}.
"""


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
    with (LOCAL / "catalog.jsonl").open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    cols = ["name", "rank", "video_id", "title", "artist", "country", "tier",
            "nominal_s", "wav_s", "delta_pct", "gate", "sections", "run",
            "seed", "cap", "lyrics_sha256", "style_sha256", "abc_sha256",
            "mp3_source"]
    with (LOCAL / "catalog.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for r in rows:
            w.writerow([r["name"], r["rank"], r["video_id"], r["title"],
                        r["artist"], r["country"], r["tier"], r["nominal_s"],
                        r["wav_s"], r["delta_pct"], r["gate"],
                        "|".join(r["sections"]), r["generation"]["run"],
                        r["generation"]["seed"], r["generation"]["cap"],
                        r["lyrics"]["sha256"], r["style"]["sha256"],
                        r["score"]["abc_sha256"], r["audio"]["source"]])

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

    write_text(LOCAL / "README.md", make_readme(rows, style_text, recipe))
    write_text(LOCAL / "DATASET_CARD.md", make_readme(rows, style_text, recipe))
    shutil.copyfile(LOCAL / "catalog.jsonl", LOCAL / "tracks.jsonl")
    parquet = make_parquet(rows)
    built_at = utcnow()
    manifest = make_manifest(rows, recipe, style_sha, built_at)
    write_json(LOCAL / "manifest.json", manifest)
    write_text(LOCAL / "_SUCCESS",
               f"{built_at}\ntracks={len(rows)}\nparquet={parquet or 'skipped'}\n")
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

    if args.remote:
        folders = count_remote(DATASET_URI + "/tracks", "*/", dirs=True)
        audio = count_remote(DATASET_URI + "/tracks", "*/audio.mp3")
        if folders != len(rows):
            problems.append(f"remote track folders {folders} != {len(rows)}")
        if audio != len(rows):
            problems.append(f"remote audio files {audio} != {len(rows)}")
        print(f"remote: {folders} folders, {audio} audio files")

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
    if args.dry_run:
        print(f"would rsync {LOCAL} -> {DATASET_URI}")
        print(f"would copy {len(rows)} MP3s server-side")
        return 0

    print(f"uploading metadata -> {DATASET_URI}")
    _gsutil("-m", "rsync", "-r", str(LOCAL) + "/", DATASET_URI + "/")

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
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--build", action="store_true", help="write the local dataset tree")
    ap.add_argument("--publish", action="store_true", help="upload and copy audio")
    ap.add_argument("--verify", action="store_true", help="check the build")
    ap.add_argument("--download-dir", type=Path, help="copy published audio locally")
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

    if not any((args.build, args.publish, args.verify, args.download_dir)):
        ap.print_help()
        return 2

    if args.refresh_meta:
        print(f"refreshing run metadata -> {args.meta_dir}")
        drv.fetch_metadata(GCS_RUNS, args.meta_dir, refresh=True)

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
