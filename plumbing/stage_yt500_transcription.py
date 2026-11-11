#!/usr/bin/env python3
"""Inventory + byte-exact staging for the YT500 transcription run.

The dataset is read-only.  Every audio file is copied byte-for-byte from GCS to
``<audio-dir>/<name>.mp3`` (flattened: all source files are named ``audio.mp3``)
and every input score to ``<inputs-dir>/<name>.abc``.  Nothing is transcoded,
re-tagged or tarred.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

DATASET = "gs://akbar-december-2024-backup/DATASET/yt500_instrumental"
REPO = Path(__file__).resolve().parent.parent
CORPUS_INDEX = REPO / "outputs/YT500/generation/index.json"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def load_corpus_index(path: Path) -> dict[str, dict]:
    if not path.is_file():
        return {}
    obj = json.loads(path.read_text(encoding="utf-8"))
    tracks = obj.get("tracks", obj if isinstance(obj, list) else [])
    return {t["name"]: t for t in tracks if isinstance(t, dict) and t.get("name")}


def build_inventory(tracks_path: Path, input_dir: Path,
                    corpus_index: Path, allow_mismatch: bool = False) -> dict:
    rows = read_jsonl(tracks_path)
    index = load_corpus_index(corpus_index)
    names = [r["name"] for r in rows]
    if len(names) != len(set(names)):
        raise SystemExit(f"inventory: duplicate names in {tracks_path}")

    nominal = sorted(r.get("nominal_s") or 0.0 for r in rows)
    q1, q2, q3 = (nominal[len(nominal) // 4], nominal[len(nominal) // 2],
                  nominal[3 * len(nominal) // 4])

    def quartile(x: float) -> str:
        if x <= q1:
            return "Q1"
        if x <= q2:
            return "Q2"
        if x <= q3:
            return "Q3"
        return "Q4"

    tracks, mismatches = [], []
    for r in rows:
        name = r["name"]
        abc = input_dir / f"{name}.input.abc"
        legacy = input_dir / f"{name}.abc"
        if not abc.is_file() and legacy.is_file():
            abc = legacy
        sha = sha256_file(abc) if abc.is_file() else None
        idx = index.get(name, {})
        expected = idx.get("instrumental_abc_sha256")
        match = bool(sha and expected and sha == expected)
        if not match:
            mismatches.append({
                "name": name, "sha256": sha, "expected": expected,
                "reason": "missing file" if sha is None else
                          ("no expected hash" if not expected else "sha256 mismatch"),
            })
        arts = r.get("artifacts") or {}
        tracks.append({
            "name": name,
            "role": "input",
            "sha256": sha,
            "input_sha256": sha,
            "expected_sha256": expected,
            "hash_match": match,
            "nominal_s": r.get("nominal_s"),
            "wav_s": r.get("wav_s"),
            "delta_pct": r.get("delta_pct"),
            "sections_count": len(r.get("sections") or []),
            "tier": r.get("tier"),
            "country": r.get("country"),
            "duration_quartile": quartile(r.get("nominal_s") or 0.0),
            "has_score": bool(arts.get("score")),
            "has_audio": bool(arts.get("audio")),
            "input_abc": str(abc) if abc.is_file() else None,
            "input_uri": f"{DATASET}/tracks/{name}/score.abc",
        })

    inv = {
        "version": 1,
        "dataset": DATASET,
        "track_count": len(tracks),
        "hash_verified": sum(t["hash_match"] for t in tracks),
        "mismatches": mismatches,
        "duration_quantiles": {"q1": q1, "median": q2, "q3": q3},
        "tracks": tracks,
    }
    if mismatches and not allow_mismatch:
        print(f"inventory: {len(mismatches)} hash mismatches (see JSON); "
              f"pass --allow-mismatch to continue", file=sys.stderr)
    return inv


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, sort_keys=True))
    tmp.replace(path)


def remote_audio_sizes() -> dict[str, int]:
    """One `gsutil ls -l` for every audio.mp3 (byte sizes for resume checks)."""
    try:
        r = subprocess.run(
            ["gsutil", "ls", "-l", f"{DATASET}/tracks/*/audio.mp3"],
            capture_output=True, text=True, timeout=600)
    except (OSError, subprocess.TimeoutExpired):
        return {}
    out = {}
    for line in r.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[0].isdigit() and parts[-1].endswith("audio.mp3"):
            name = parts[-1].split("/")[-2]
            out[name] = int(parts[0])
    return out


def gsutil_cp(uri: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    subprocess.run(["gsutil", "-q", "cp", uri, str(tmp)], check=True)
    os.replace(tmp, dest)


def copy_file(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    shutil.copyfile(src, tmp)
    os.replace(tmp, dest)


def stage(inv: dict, audio_dir: Path, input_dir: Path, workers: int,
          verify_sizes: bool = True) -> dict:
    tracks = inv["tracks"]
    sizes = remote_audio_sizes() if verify_sizes else {}
    audio_dir.mkdir(parents=True, exist_ok=True)
    input_dir.mkdir(parents=True, exist_ok=True)
    errors = []

    def one(t: dict) -> tuple[str, str]:
        name = t["name"]
        mp3 = audio_dir / f"{name}.mp3"
        abc = input_dir / f"{name}.input.abc"
        if not abc.is_file():
            src = t.get("input_abc")
            if src and Path(src).is_file():
                copy_file(Path(src), abc)
            else:
                gsutil_cp(f"{DATASET}/tracks/{name}/score.abc", abc)
        if mp3.is_file() and mp3.stat().st_size > 0:
            if not sizes or sizes.get(name) in (None, mp3.stat().st_size):
                return name, "exists"
        gsutil_cp(f"{DATASET}/tracks/{name}/audio.mp3", mp3)
        want = sizes.get(name)
        if want is not None and mp3.stat().st_size != want:
            raise RuntimeError(f"size mismatch: {mp3.stat().st_size} != {want}")
        return name, "copied"

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(one, t): t["name"] for t in tracks}
        done = copied = 0
        for f in as_completed(futs):
            done += 1
            try:
                _, status = f.result()
                copied += status == "copied"
            except Exception as exc:  # noqa: BLE001
                errors.append({"name": futs[f], "error": str(exc)})
            if done % 25 == 0:
                print(f"staged {done}/{len(tracks)} (copied={copied}, errors={len(errors)})",
                      flush=True)
    report = {"staged": len(tracks) - len(errors), "copied": copied,
              "errors": errors, "audio_dir": str(audio_dir),
              "input_dir": str(input_dir)}
    print(json.dumps(report, indent=2))
    return report


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tracks", default=str(REPO / "work/yt500_abc/tracks.jsonl"))
    ap.add_argument("--inputs", "--input-dir-local", dest="inputs",
                    default=str(REPO / "work/yt500_abc/input"),
                    help="local input-score directory (<name>.input.abc)")
    ap.add_argument("--corpus-index", default=str(CORPUS_INDEX))
    ap.add_argument("--inventory", default=str(REPO / "work/yt500_abc/inventory.json"))
    ap.add_argument("--inventory-only", action="store_true")
    ap.add_argument("--force", action="store_true",
                    help="rebuild inventory even if the JSON already exists")
    ap.add_argument("--allow-mismatch", action="store_true")
    ap.add_argument("--audio-dir", default="/content/yt500/audio")
    ap.add_argument("--input-dir", "--inputs-dir", dest="input_dir",
                    default="/content/yt500/input",
                    help="staged input dir (<name>.input.abc)")
    ap.add_argument("--workers", type=int, default=24)
    ap.add_argument("--skip-size-check", action="store_true")
    args = ap.parse_args(argv)

    inv_path = Path(args.inventory)
    if inv_path.is_file() and args.inventory_only and not args.force:
        inv = json.loads(inv_path.read_text(encoding="utf-8"))
    else:
        inv = build_inventory(Path(args.tracks), Path(args.inputs),
                              Path(args.corpus_index), args.allow_mismatch)
        write_json(inv_path, inv)
        print(f"inventory: {inv['track_count']} tracks, "
              f"{inv['hash_verified']} sha256 verified, "
              f"{len(inv['mismatches'])} mismatches -> {inv_path}")
    if args.inventory_only:
        return 0 if not inv["mismatches"] else 1
    if inv.get("mismatches") and not args.allow_mismatch:
        print("stage: refusing to continue with hash mismatches", file=sys.stderr)
        return 2
    report = stage(inv, Path(args.audio_dir), Path(args.input_dir),
                   args.workers, verify_sizes=not args.skip_size_check)
    return 0 if not report["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
