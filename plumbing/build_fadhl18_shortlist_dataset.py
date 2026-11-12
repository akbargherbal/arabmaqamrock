#!/usr/bin/env python3
"""Build the Fadl Shaker Instrumental 18 *shortlist* dataset.

Shape mirrors ``DATASET/yt500_instrumental`` (one self-contained folder per
track, audio + input score + metadata + catalog + recipe), with two deliberate
differences:

* only the tracks in ``docs/plans/fadhl18-abc-shortlist-keep-review.json``
  are included;
* captions are deferred, so no caption files / captions.jsonl are written. The
  output-side SheetSage2 transcript is kept as ``transcript.abc`` because the
  shortlist was selected on input-vs-output similarity.

Audio is copied server-side (GCS -> GCS); the small ABC files and metadata are
built locally and uploaded. Use ``--mode verify`` to download and check hashes.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SOURCE = "gs://akbar-december-2024-backup/DATASET/fadhl_shaker_instrumental_18"
SOURCE_RUN = "20261110-050958_fadhl_shaker_instrumental_18"
DEST = "gs://akbar-december-2024-backup/DATASET/fadhl_shaker_instrumental_18_shortlist"
SHORTLIST = ROOT / "docs/plans/fadhl18-abc-shortlist-keep-review.json"
SOURCE_MANIFEST = ROOT / "manifests/fadhl_shaker_instrumental_18.json"
LOCAL = ROOT / "work/fadhl18/dataset"
SOURCE_TRACKS = ROOT / "work/fadhl18/tracks.jsonl"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")


def gsutil(*args: str, check: bool = True, quiet: bool = True):
    cmd = ["gsutil"] + (["-q"] if quiet else []) + list(args)
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise SystemExit(f"gsutil {' '.join(args)} failed:\n"
                         f"{(proc.stderr or proc.stdout).strip()[-2000:]}")
    return proc


def download(uri: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    gsutil("cp", uri, str(path))


def cat_json(uri: str) -> dict:
    proc = gsutil("cat", uri)
    return json.loads(proc.stdout)


def sections_from_abc(text: str) -> list[str]:
    out = []
    for line in text.splitlines():
        m = re.match(r"^\s*%\s*(\S.*?)\s*$", line)
        if m:
            out.append(m.group(1))
    return out


def build() -> None:
    short = read_json(SHORTLIST)
    tracks = short["tracks"]
    if not tracks:
        raise SystemExit("shortlist has no qualifying tracks")
    if not SOURCE_TRACKS.is_file():
        SOURCE_TRACKS.parent.mkdir(parents=True, exist_ok=True)
        gsutil("cp", f"{SOURCE}/tracks.jsonl", str(SOURCE_TRACKS))
    source_rows = {}
    for line in SOURCE_TRACKS.read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            source_rows[Path(r["abc_reference_path"]).name[:-4]] = r

    repo_manifest = read_json(SOURCE_MANIFEST)
    style = repo_manifest["defaults"]["style"].strip()
    recipe = {
        "source_dataset": SOURCE,
        "source_run": SOURCE_RUN,
        "style_sha256": hashlib.sha256((style + "\n").encode()).hexdigest(),
        "defaults": repo_manifest["defaults"],
        "loras": repo_manifest.get("loras", {}),
        "abc_transcriber": "m-a-p/SheetSage2 (full: melody + chords)",
        "captioning": "deferred; source captions exist in the source dataset",
    }

    if LOCAL.exists():
        shutil.rmtree(LOCAL)
    (LOCAL / "recipe").mkdir(parents=True)
    (LOCAL / "tracks").mkdir(parents=True)
    (LOCAL / "recipe/style.txt").write_text(style + "\n", encoding="utf-8")
    write_json(LOCAL / "recipe/recipe.json", recipe)
    (LOCAL / "shortlist.json").write_text(
        json.dumps(short, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    audio_entries = []
    rows = []
    caption_rows = []
    for t in sorted(tracks, key=lambda x: -x["composite"]):
        name = t["name"]
        stem = t["source_name"]
        src = source_rows[stem]
        tdir = LOCAL / "tracks" / name
        tdir.mkdir(parents=True)
        score = tdir / "score.abc"
        transcript = tdir / "transcript.abc"
        download(t["input_uri"], score)
        download(t["output_uri"], transcript)
        if sha256_file(score) != t["input_sha256"]:
            raise SystemExit(f"input hash mismatch: {name}")
        if sha256_file(transcript) != t["output_sha256"]:
            raise SystemExit(f"output hash mismatch: {name}")

        cap_src_uri = f"{SOURCE}/captions/{stem}.json"
        cap_src = cat_json(cap_src_uri)
        cap = cap_src.get("caption") or {}
        if (cap_src.get("audio") or {}).get("sha256") != t["audio_sha256"]:
            raise SystemExit(f"caption audio hash mismatch: {name}")
        cap_text = (cap.get("text") or "").strip()
        if not cap_text:
            raise SystemExit(f"empty caption text: {name}")
        (tdir / "caption.txt").write_text(cap_text + "\n", encoding="utf-8")
        cap_sha = sha256_file(tdir / "caption.txt")
        cap_obj = {
            "schema": "yt500-caption/1",
            "name": name,
            "source_name": stem,
            "take": {
                "file": (cap_src.get("audio") or {}).get("file"),
                "seed": cap_src.get("seed"),
                "run": cap_src.get("run_id"),
            },
            "caption": cap_text,
            "caption_sha256": cap_sha,
            "caption_chars": len(cap_text),
            "caption_raw": cap.get("caption_raw"),
            "chunk_captions": cap.get("chunk_captions") or [],
            "instruments": cap.get("instruments") or [],
            "vocals": cap.get("vocals") or [],
            "production": cap.get("production") or [],
            "tags_experimental": bool(cap.get("tags_experimental")),
            "rewrite": {
                "status": cap.get("rewrite_status"),
                "model": cap.get("rewrite_model"),
                "prompt_version": 1,
            },
            "pipeline": {
                "version": 3,
                "stage": "polished",
                "source_dataset": SOURCE,
                "source_caption": cap_src_uri,
            },
            "audio": {
                "duration_s": (cap_src.get("audio") or {}).get("duration_s"),
                "bitrate_kbps": (cap_src.get("audio") or {}).get("bitrate_kbps"),
                "chunk_count": cap.get("chunk_count"),
                "silence_trimmed_s": cap.get("silence_trimmed_s"),
            },
            "abc_transcription": {
                "model": (cap_src.get("abc_transcription") or {}).get("model"),
                "model_revision": (cap_src.get("abc_transcription") or {}).get("model_revision"),
                "seconds": (cap_src.get("abc_transcription") or {}).get("seconds"),
                "status": (cap_src.get("abc_transcription") or {}).get("status"),
            },
        }
        write_json(tdir / "caption.json", cap_obj)

        sections = sections_from_abc(score.read_text(encoding="utf-8",
                                                      errors="replace"))
        lyrics = "\n".join(f"[{s}]" for s in sections) + "\n"
        (tdir / "lyrics.txt").write_text(lyrics, encoding="utf-8")
        (tdir / "style.txt").write_text(style + "\n", encoding="utf-8")

        track = {
            "name": name,
            "source_name": stem,
            "song": src.get("name"),
            "artist": "Fadl Shaker",
            "duration_s": src.get("duration_s"),
            "seed": src.get("seed"),
            "source_dataset": SOURCE,
            "source_run_id": src.get("run_id"),
            "source_track_id": src.get("track_id"),
            "source_uris": {
                "audio": src.get("gs_uri"),
                "score": t["input_uri"],
                "transcript": t["output_uri"],
            },
            "hashes": {
                "audio_sha256": t["audio_sha256"],
                "score_sha256": t["input_sha256"],
                "transcript_sha256": t["output_sha256"],
            },
            "similarity": {
                "composite": t["composite"],
                "deep_composite": t["deep_composite"],
                "decision": t["decision"],
                "qualify": t["qualify"],
                "codes": t["codes"],
                "retrieval_rank": t["retrieval_rank"],
                "lift_vs_mismatched": t["lift_vs_mismatched"],
                "groups": {
                    "global": t["grp_global"],
                    "harmony": t["grp_harmony"],
                    "melody": t["grp_melody"],
                    "rhythm": t["grp_rhythm"],
                },
                "duration_sim": t["duration_sim"],
                "note_count_ratio": t["note_count_ratio"],
                "key_sim": t["key_sim"],
                "tempo_sim": t["tempo_sim"],
            },
            "artifacts": {
                "audio": "audio.mp3",
                "score": "score.abc",
                "transcript": "transcript.abc",
                "lyrics": "lyrics.txt",
                "style": "style.txt",
                "caption": "caption.json",
                "caption_text": "caption.txt",
            },
            "roles": {
                "score": "input (generation conditioner)",
                "transcript": "output (SheetSage2 full)",
            },
            "caption": {
                "file": "caption.json",
                "text_file": "caption.txt",
                "sha256": cap_sha,
                "chars": len(cap_text),
                "rewrite_status": cap.get("rewrite_status"),
                "pipeline_version": 3,
                "take": (cap_src.get("audio") or {}).get("file"),
            },
            "caption_status": "ok",
        }
        write_json(tdir / "track.json", track)
        audio_entries.append({
            "path": f"tracks/{name}/audio.mp3",
            "sha256": t["audio_sha256"],
            "bytes": src.get("audio_bytes"),
            "source": src.get("gs_uri"),
        })
        rows.append({
            "name": name,
            "song": src.get("name"),
            "artist": "Fadl Shaker",
            "duration_s": src.get("duration_s"),
            "composite": t["composite"],
            "deep_composite": t["deep_composite"],
            "decision": t["decision"],
            "qualify": t["qualify"],
            "codes": t["codes"],
            "retrieval_rank": t["retrieval_rank"],
            "lift_vs_mismatched": t["lift_vs_mismatched"],
            "audio_sha256": t["audio_sha256"],
            "score_sha256": t["input_sha256"],
            "transcript_sha256": t["output_sha256"],
            "source_name": stem,
            "source_track_id": src.get("track_id"),
            "source_run_id": src.get("run_id"),
            "caption": cap_text,
            "caption_sha256": cap_sha,
            "caption_chars": len(cap_text),
            "caption_rewrite_status": cap.get("rewrite_status"),
            "instruments": cap.get("instruments") or [],
            "vocals": cap.get("vocals") or [],
            "production": cap.get("production") or [],
            "artifacts": track["artifacts"],
        })
        caption_rows.append({
            "name": name,
            "source_name": stem,
            "file": (cap_src.get("audio") or {}).get("file"),
            "seed": cap_src.get("seed"),
            "caption": cap_text,
            "caption_sha256": cap_sha,
            "caption_chars": len(cap_text),
            "instruments": cap.get("instruments") or [],
            "vocals": cap.get("vocals") or [],
            "production": cap.get("production") or [],
            "rewrite_status": cap.get("rewrite_status"),
            "tags_experimental": bool(cap.get("tags_experimental")),
        })

    with (LOCAL / "tracks.jsonl").open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    shutil.copyfile(LOCAL / "tracks.jsonl", LOCAL / "catalog.jsonl")
    with (LOCAL / "captions.jsonl").open("w", encoding="utf-8") as fh:
        for r in caption_rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    cap_sums = []
    for r in rows:
        for fn in ("caption.txt", "caption.json"):
            p = LOCAL / "tracks" / r["name"] / fn
            cap_sums.append(f"{sha256_file(p)}  tracks/{r['name']}/{fn}")
    cap_sums.sort(key=lambda line: line.split("  ", 1)[1])
    (LOCAL / "captions.sha256").write_text("\n".join(cap_sums) + "\n",
                                           encoding="utf-8")
    pd.DataFrame(rows).to_parquet(LOCAL / "tracks.parquet", index=False)
    fields = ["name", "song", "artist", "duration_s", "composite",
              "deep_composite", "decision", "qualify", "codes",
              "retrieval_rank", "lift_vs_mismatched", "audio_sha256",
              "score_sha256", "transcript_sha256", "caption_chars",
              "caption_sha256", "caption_rewrite_status", "source_name",
              "source_track_id", "source_run_id"]
    with (LOCAL / "catalog.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k) for k in fields})
    md = ["# Fadl Shaker Instrumental 18 — shortlist catalogue", "",
          f"{len(rows)} tracks, sorted by composite similarity.", "",
          "| name | song | duration_s | composite | deep | decision |",
          "|---|---|---:|---:|---:|---|"]
    for r in rows:
        md.append(f"| {r['name']} | {r['song']} | {r['duration_s']:.1f} | "
                  f"{r['composite']:.3f} | {r['deep_composite']:.3f} | "
                  f"{r['decision']} |")
    (LOCAL / "catalog.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    m3u = ["#EXTM3U"]
    for r in rows:
        m3u.append(f"#EXTINF:{int(round(r['duration_s']))},Fadl Shaker - {r['song']}")
        m3u.append(f"tracks/{r['name']}/audio.mp3")
    (LOCAL / "playlist.m3u").write_text("\n".join(m3u) + "\n", encoding="utf-8")

    counts = {
        "tracks": len(rows),
        "with_audio": len(audio_entries),
        "with_score": len(rows),
        "with_transcript": len(rows),
        "captions": len(rows),
        "audio_bytes": sum((a.get("bytes") or 0) for a in audio_entries),
    }
    generated = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    card = f"""# Fadl Shaker Instrumental 18 — ABC-similarity shortlist

{len(rows)} generated instrumental takes whose SheetSage2 output ABC is
acceptably similar to the reference ABC used as the generation conditioner.

## Selection

- Source: `{SOURCE}` (24 tracks).
- Shortlist rule: `decision != REGENERATE`, cheap composite **≥ 0.85**, deep
  composite **≥ 0.65**.
- Selected: **{len(rows)} / 24**. The 2 borderline tracks (composite 0.825 and
  0.832) are excluded and listed in `shortlist.json`.
- Decision codes: KEEP **{sum(1 for r in rows if r['decision'] == 'KEEP')}**,
  REVIEW **{sum(1 for r in rows if r['decision'] == 'REVIEW')}**.

Track IDs are `fs18-<source_name>`; `track.json.source_name` maps each one back
to the source dataset.

## Layout

```
tracks/<name>/
  audio.mp3       generated MP3 (server-side copy from the source run)
  score.abc       input: reference ABC used as the generation conditioner
  transcript.abc  output: SheetSage2 --full transcript of audio.mp3
  lyrics.txt      section-tag plan derived from score.abc (% comments)
  style.txt       generation style prompt
  caption.txt     polished prose caption for this take
  caption.json    full caption record (chunks, tags, audio, rewrite)
  track.json      ids, hashes, similarity scores, provenance
catalog.jsonl     one row per track
catalog.csv       spreadsheet view
catalog.md        human-readable table
playlist.m3u      composite-descending order
tracks.parquet    same rows as tracks.jsonl
captions.jsonl    one caption row per track
captions.sha256   sha256sum list for every caption artifact
manifest.json     counts, selection, layout, file hashes
shortlist.json    full shortlist decision record (incl. excluded tracks)
recipe/           style + LoRA/defaults
SHA256SUMS        sha256sum -c compatible
```

## Captions

Every track has the polished prose caption from the source dataset, copied
into `caption.txt` and normalised into `caption.json` (`schema:
yt500-caption/1`). `captions.jsonl` inlines the caption, tags and SHA-256;
`captions.sha256` covers every caption file. The source is
`{SOURCE}/captions/<source_name>.json`. Captions are machine-generated and the
tag lists are experimental — see `track.json.caption` for the pointer.

## Sides

`score.abc` is the **input** side. `transcript.abc` is the **output** side.
They are not interchangeable; `track.json` records the SHA-256 of each.

## Provenance

The transcriptions were independently reproduced from the source MP3s with
SheetSage2 revision `b83c3d79a6d98bcffaf8f9ed112c90aa887887bc`; all 24 source
tracks were byte-identical to the published transcriptions. See
`ANALYSIS/fadhl_shaker_instrumental_18_abc/similarity/reproducibility.json`.
"""
    (LOCAL / "DATASET_CARD.md").write_text(card, encoding="utf-8")
    readme = f"""# Fadl Shaker Instrumental 18 — shortlist dataset

{len(rows)} tracks, input score + generated audio + SheetSage2 transcript +
polished caption. Layout and disjoint sides are documented in
`DATASET_CARD.md`; hashes are in `manifest.json`, `SHA256SUMS` and
`captions.sha256`.

Source: `{SOURCE}`
Analysis: `gs://akbar-december-2024-backup/ANALYSIS/fadhl_shaker_instrumental_18_abc`
"""
    (LOCAL / "README.md").write_text(readme, encoding="utf-8")
    (LOCAL / "_SUCCESS").write_text(
        f"{generated}\ntracks={len(rows)}\ncaptions={len(rows)}\n"
        "parquet=tracks.parquet\n",
        encoding="utf-8")

    # manifest: every file except manifest.json and SHA256SUMS, plus audio.
    files = []
    for p in sorted(LOCAL.rglob("*")):
        if not p.is_file() or p.name in ("manifest.json", "SHA256SUMS"):
            continue
        files.append({"path": p.relative_to(LOCAL).as_posix(),
                      "sha256": sha256_file(p), "bytes": p.stat().st_size})
    files.extend(audio_entries)
    files.sort(key=lambda x: x["path"])
    manifest = {
        "dataset": "Fadl Shaker Instrumental 18 — ABC-similarity shortlist",
        "dataset_version": "v0.1",
        "generated_at": generated,
        "source_dataset": SOURCE,
        "source_run_id": SOURCE_RUN,
        "selection": {
            "shortlist": "docs/plans/fadhl18-abc-shortlist-keep-review.json",
            "criteria": "decision != REGENERATE AND composite >= 0.85 AND deep_composite >= 0.65",
            "source_tracks": 24,
            "selected": len(rows),
            "excluded_borderline": [
                {"name": t["source_name"], "composite": t["composite"],
                 "deep_composite": t["deep_composite"]}
                for t in short.get("excluded", {}).get("borderline", [])
            ],
            "excluded_reject": [t["source_name"] for t in
                                short.get("excluded", {}).get("reject", [])],
        },
        "counts": counts,
        "layout": {
            "per_track": "tracks/<name>/{audio.mp3,score.abc,transcript.abc,lyrics.txt,style.txt,caption.txt,caption.json,track.json}",
            "captions": "captions.jsonl inlines caption rows; captions.sha256 covers per-track caption files",
        },
        "roles": {
            "score.abc": "input / generation conditioner",
            "transcript.abc": "output / SheetSage2 full transcription",
        },
        "recipe": "recipe/recipe.json",
        "files": files,
    }
    write_json(LOCAL / "manifest.json", manifest)
    sums = []
    for p in sorted(LOCAL.rglob("*")):
        if not p.is_file() or p.name == "SHA256SUMS":
            continue
        sums.append(f"{sha256_file(p)}  {p.relative_to(LOCAL).as_posix()}")
    for a in audio_entries:
        sums.append(f"{a['sha256']}  {a['path']}")
    sums.sort(key=lambda line: line.split("  ", 1)[1])
    (LOCAL / "SHA256SUMS").write_text("\n".join(sums) + "\n", encoding="utf-8")
    write_json(LOCAL / ".build.json", {
        "built_at": generated,
        "dataset_uri": DEST,
        "tracks": len(rows),
        "source_dataset": SOURCE,
        "source_run_id": SOURCE_RUN,
        "shortlist": "docs/plans/fadhl18-abc-shortlist-keep-review.json",
        "captions": len(rows),
    })
    print(json.dumps({"local": str(LOCAL), "counts": counts,
                      "files_hashed": len(sums)}, indent=2))


def publish() -> None:
    if not (LOCAL / "manifest.json").is_file():
        raise SystemExit(f"build first: {LOCAL} is missing")
    gsutil("-m", "cp", "-r", str(LOCAL / "tracks"), DEST + "/")
    gsutil("-m", "cp", "-r", str(LOCAL / "recipe"), DEST + "/")
    gsutil("-m", "cp", str(LOCAL / "catalog.jsonl"),
           str(LOCAL / "catalog.csv"), str(LOCAL / "catalog.md"),
           str(LOCAL / "tracks.jsonl"), str(LOCAL / "tracks.parquet"),
           str(LOCAL / "playlist.m3u"), str(LOCAL / "manifest.json"),
           str(LOCAL / "README.md"), str(LOCAL / "DATASET_CARD.md"),
           str(LOCAL / "shortlist.json"), str(LOCAL / "captions.jsonl"),
           str(LOCAL / "captions.sha256"), str(LOCAL / "SHA256SUMS"),
           str(LOCAL / ".build.json"), DEST + "/")
    gsutil("rm", "-f", DEST + "/_SUCCESS", check=False)

    rows = [json.loads(line) for line in
            (LOCAL / "tracks.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()]
    source_by_name = {}
    for t in read_json(SHORTLIST)["tracks"]:
        source_by_name[t["name"]] = t["audio_uri"]

    def upload_audio(row):
        uri = source_by_name[row["name"]]
        dest = f"{DEST}/tracks/{row['name']}/audio.mp3"
        gsutil("cp", uri, dest)
        return row["name"]

    with ThreadPoolExecutor(max_workers=6) as ex:
        done = list(ex.map(upload_audio, rows))
    gsutil("cp", str(LOCAL / "_SUCCESS"), DEST + "/_SUCCESS")
    print(json.dumps({"published": DEST, "tracks": len(done)}))


def verify() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="fadhl18_shortlist_verify_"))
    try:
        gsutil("-m", "cp", "-r", DEST + "/*", str(tmp) + "/")
        proc = subprocess.run(["sha256sum", "-c", "SHA256SUMS"], cwd=tmp,
                              capture_output=True, text=True)
        ok = sum(1 for line in proc.stdout.splitlines() if line.endswith(": OK"))
        bad = [line for line in proc.stdout.splitlines()
               if not line.endswith(": OK")]
        files = list((tmp / "tracks").glob("*/audio.mp3"))
        result = {
            "sha256_exit": proc.returncode,
            "sha256_ok": ok,
            "sha256_bad": len(bad),
            "audio_files": len(files),
            "track_dirs": len(list((tmp / "tracks").iterdir())),
            "success": (tmp / "_SUCCESS").is_file(),
            "partial": (tmp / "_PARTIAL.json").is_file(),
        }
        print(json.dumps(result, indent=2))
        if bad:
            print("\n".join(bad[:10]))
        if proc.returncode != 0 or not result["success"]:
            raise SystemExit("verification failed")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mode", choices=["build", "publish", "verify", "all"],
                    default="all")
    args = ap.parse_args()
    if args.mode in ("build", "all"):
        build()
    if args.mode in ("publish", "all"):
        publish()
    if args.mode in ("verify", "all"):
        verify()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
