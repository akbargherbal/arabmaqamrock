#!/usr/bin/env python3
"""Build / fetch / verify the frozen 489-score YT500 instrumental corpus.

Source (frozen):   gs://.../TRANSCRIPTS/YT500/YT500/abc/shard-*.json
Bundle (derived):  gs://.../GENERATION/YT500_INSTRUMENTAL/

The builder selects every track with a parsed ABC, normalizes the 5 scores
whose inline key changes the official instrumentalizer rejects (3 recover, 2
are excluded), runs the same Vocal -> Ins conversion used for the Fadl set,
validates every report, and writes the 489-song manifest with the exact
manifest-18 defaults and LoRA registry.

Usage:
    python3 plumbing/yt500_generation_corpus.py --build --upload
    python3 plumbing/yt500_generation_corpus.py --build --dry-run
    python3 plumbing/yt500_generation_corpus.py --fetch
    python3 plumbing/yt500_generation_corpus.py --verify
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import generate as gen  # noqa: E402  (pure Python; no torch)

SOURCE_INDEX = "gs://akbar-december-2024-backup/TRANSCRIPTS/YT500/_index.json"
SOURCE_ABC = "gs://akbar-december-2024-backup/TRANSCRIPTS/YT500/YT500/abc"
BUNDLE = "gs://akbar-december-2024-backup/GENERATION/YT500_INSTRUMENTAL"

REFERENCE = ROOT / "manifests" / "fadhl_shaker_instrumental_18.json"
MANIFEST = ROOT / "manifests" / "yt500_instrumental_489.json"
SCORES = ROOT / "scores" / "yt500_instrumental"
SRC = ROOT / "scores" / "yt500_src"
OUT = ROOT / "outputs" / "YT500" / "generation"
WORK = ROOT / "work" / "yt500_gen" / "corpus"

INSTRUMENTALIZER = ROOT / "plumbing" / "instrumentalize_scores.py"
KEY_RE = re.compile(r"\[K:[^\]]+\]")
QUOTED_RE = re.compile(r'"[^"]*"')
PITCH_RE = re.compile(r"[A-Ga-g]")

# Fields the corpus must inherit verbatim from manifest 18.
EXPECTED_DEFAULTS = {
    "lyrics_from_score": True,
    "cot": "full",
    "lora": "instrumental_v9",
    "lora_ar_scale": 0.85,
    "lora_nar_scale": 1.0,
    "trigger": False,
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def run(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise SystemExit(
            f"command failed ({proc.returncode}): {' '.join(cmd)}\n"
            f"{(proc.stderr or proc.stdout).strip()[-4000:]}")
    return proc


def gcs_cp(src: str, dst: str) -> None:
    if shutil.which("gcloud"):
        run(["gcloud", "storage", "cp", src, dst])
    elif shutil.which("gsutil"):
        run(["gsutil", "-m", "cp", src, dst])
    else:
        raise SystemExit("need gcloud or gsutil on PATH")


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    tmp.replace(path)


# --- score selection and key normalization ----------------------------------

def _has_pitched_note(text: str) -> bool:
    text = QUOTED_RE.sub("", text)
    text = re.sub(r"[zZx0-9,'/\-<>~.\s]", "", text)
    return bool(PITCH_RE.search(text))


def normalize_inline_keys(text: str) -> tuple[str, list[dict], list[dict]]:
    """Move an inline [K:...] to the bar start when only rests precede it.

    The official instrumentalizer refuses a key change that is not at a bar
    start. Three of the five YT500 cases have only rests before the token, so
    moving it to the start of the same bar is pitch-preserving. The remaining
    two have pitched notes before the token; those are reported and excluded.
    """
    changes: list[dict] = []
    failures: list[dict] = []
    out_lines: list[str] = []
    for lineno, line in enumerate(text.splitlines(), 1):
        if "[K:" not in line:
            out_lines.append(line)
            continue
        segments = line.split("|")
        for i, segment in enumerate(segments):
            match = KEY_RE.search(segment)
            if not match or match.start() == 0:
                continue
            prefix = segment[:match.start()]
            if not _has_pitched_note(prefix):
                segments[i] = match.group(0) + prefix + segment[match.end():]
                changes.append({"line": lineno, "key": match.group(0),
                                "action": "moved-to-bar-start"})
            else:
                failures.append({"line": lineno, "key": match.group(0),
                                 "action": "pitched-prefix-before-key",
                                 "segment": segment.strip()[:200]})
        out_lines.append("|".join(segments))
    joined = "\n".join(out_lines)
    if text.endswith("\n"):
        joined += "\n"
    return joined, changes, failures


def track_name(track: dict) -> str:
    return f"yt500-{int(track['source_rank']):04d}-{track['video_id']}"


def load_source(work: Path) -> list[dict]:
    work.mkdir(parents=True, exist_ok=True)
    gcs_cp(SOURCE_INDEX, str(work / "index.json"))
    abc_dir = work / "abc"
    abc_dir.mkdir(parents=True, exist_ok=True)
    gcs_cp(f"{SOURCE_ABC}/shard-*.json", str(abc_dir) + "/")
    files = sorted(abc_dir.glob("shard-*.json"))
    if len(files) != 25:
        raise SystemExit(f"expected 25 shard JSONs, found {len(files)}")
    tracks: list[dict] = []
    for path in files:
        payload = json.loads(path.read_text(encoding="utf-8"))
        for track in payload.get("tracks", []):
            track["_shard"] = payload.get("album", path.stem)
            track["_album_status"] = payload.get("status")
            tracks.append(track)
    index = json.loads((work / "index.json").read_text(encoding="utf-8"))
    total = sum(int(a.get("track_count", 0))
                for a in index.get("albums", {}).values())
    if total != 495:
        raise SystemExit(f"source index reports {total} tracks, expected 495")
    if len(tracks) != 495:
        raise SystemExit(f"shard JSONs hold {len(tracks)} tracks, expected 495")
    return tracks


def select_tracks(tracks: list[dict]) -> tuple[list[dict], list[dict]]:
    ready: list[dict] = []
    excluded: list[dict] = []
    for track in tracks:
        name = track_name(track)
        abc = track.get("abc")
        if track.get("transcribe_status") != "ok" or not abc:
            excluded.append({"name": name, "reason": "no-abc",
                             "detail": "transcribe_status=%r"
                                       % track.get("transcribe_status")})
            continue
        normalized, changes, failures = normalize_inline_keys(abc)
        if failures:
            excluded.append({"name": name, "reason": "inline_key_change",
                             "detail": failures})
            continue
        track["_abc_normalized"] = normalized
        track["_abc_changes"] = changes
        ready.append(track)
    return ready, excluded


# --- conversion / validation ------------------------------------------------

def instrumentalize(ready: list[dict], dry_run: bool = False) -> None:
    if SRC.exists():
        shutil.rmtree(SRC)
    SRC.mkdir(parents=True)
    for track in ready:
        (SRC / f"{track_name(track)}.abc").write_text(
            track["_abc_normalized"], encoding="utf-8", newline="\n")
    if dry_run:
        return
    if SCORES.exists():
        shutil.rmtree(SCORES)
    proc = subprocess.run(
        [sys.executable, str(INSTRUMENTALIZER), str(SRC),
         "--out-dir", str(SCORES)],
        capture_output=True, text=True)
    if proc.returncode != 0:
        raise SystemExit(
            "instrumentalization failed:\n"
            f"{(proc.stderr or proc.stdout).strip()[-6000:]}")


def validate_outputs(ready: list[dict]) -> tuple[list[dict], list[dict]]:
    good: list[dict] = []
    failed: list[dict] = []
    for track in ready:
        name = track_name(track)
        score = SCORES / f"{name}.abc"
        report_path = SCORES / "reports" / f"{name}.json"
        problems: list[str] = []
        if not score.is_file():
            problems.append("missing instrumental score")
        if not report_path.is_file():
            problems.append("missing conversion report")
        report = {}
        if report_path.is_file():
            report = json.loads(report_path.read_text(encoding="utf-8"))
            if report.get("vocal_notes_after") != 0:
                problems.append("vocal notes remain")
            if report.get("chords") != "preserved":
                problems.append("chords not preserved")
            if report.get("vocal_pitch_onset_duration_preserved") is not True:
                problems.append("pitch/onset/duration changed")
            if report.get("meter_and_tempo_preserved") is not True:
                problems.append("meter/tempo changed")
            source_s = track.get("duration_s")
            nominal = report.get("nominal_seconds")
            if (source_s and nominal
                    and abs(nominal - source_s) / source_s > 0.05):
                problems.append(
                    f"nominal {nominal:.1f}s vs source {source_s:.1f}s "
                    f"(>5%)")
        tags: list[str] = []
        if score.is_file():
            text = score.read_text(encoding="utf-8")
            try:
                tags = gen.score_section_tags(text, name)
            except gen.PlanError as exc:
                problems.append(f"no section tags: {exc}")
            if gen.abc_duration_s(text) is None:
                problems.append("score duration does not parse")
        if problems:
            failed.append({"name": name, "reason": "conversion_invalid",
                           "detail": problems})
            continue
        track["_instrumental_text"] = score.read_text(encoding="utf-8")
        track["_instrumental_sha256"] = sha256_file(score)
        track["_report"] = report
        track["_sections"] = tags
        good.append(track)
    return good, failed


# --- manifest / index -------------------------------------------------------

def load_reference() -> dict:
    ref = json.loads(REFERENCE.read_text(encoding="utf-8"))
    defaults = ref.get("defaults", {})
    for key, want in EXPECTED_DEFAULTS.items():
        if defaults.get(key) != want:
            raise SystemExit(
                f"reference manifest changed: defaults[{key!r}] is "
                f"{defaults.get(key)!r}, expected {want!r}")
    if not defaults.get("style"):
        raise SystemExit("reference manifest has no defaults.style")
    if set(ref.get("loras", {})) != {"instrumental", "instrumental_v9"}:
        raise SystemExit("reference manifest lora registry changed")
    return ref


def build_manifest(good: list[dict], reference: dict) -> dict:
    scores = {}
    songs = []
    for track in good:
        name = track_name(track)
        scores[name] = f"scores/yt500_instrumental/{name}.abc"
        songs.append({"name": name, "score": name})
    return {
        "base_dir": "..",
        "loras": reference["loras"],
        "scores": scores,
        "defaults": reference["defaults"],
        "songs": songs,
    }


def build_index(all_tracks: list[dict], good: list[dict],
                excluded: list[dict]) -> dict:
    good_by_name = {track_name(t): t for t in good}
    excluded_by_name = {e["name"]: e for e in excluded}
    rows = []
    for track in all_tracks:
        name = track_name(track)
        row = {
            "name": name,
            "track_id": track.get("track_id"),
            "source_rank": track.get("source_rank"),
            "video_id": track.get("video_id"),
            "title": track.get("title"),
            "source_artist": track.get("source_artist"),
            "country": track.get("country"),
            "tier": track.get("tier"),
            "shard": track.get("_shard"),
            "duration_s": track.get("duration_s"),
            "qc_flags": (track.get("qc") or {}).get("flags") or [],
            "source_abc_sha256": (sha256_text(track["abc"])
                                  if track.get("abc") else None),
            "instrumental_abc_sha256": None,
            "nominal_seconds": None,
            "sections": [],
            "generation_status": "excluded",
            "reason": None,
        }
        if name in good_by_name:
            item = good_by_name[name]
            row["generation_status"] = "ready"
            row["instrumental_abc_sha256"] = item["_instrumental_sha256"]
            row["nominal_seconds"] = round(
                item["_report"].get("nominal_seconds") or 0.0, 3)
            row["sections"] = item["_sections"]
        elif name in excluded_by_name:
            row["reason"] = excluded_by_name[name]["reason"]
        rows.append(row)
    counts = {
        "source": len(rows),
        "ready": sum(r["generation_status"] == "ready" for r in rows),
        "excluded_no_abc": sum(r["reason"] == "no-abc" for r in rows),
        "excluded_inline_key": sum(r["reason"] == "inline_key_change"
                                   for r in rows),
        "excluded_other": sum(r["generation_status"] == "excluded"
                              and r["reason"] not in
                              ("no-abc", "inline_key_change") for r in rows),
    }
    return {"version": 1, "generated_at": gen.utcnow(),
            "counts": counts, "tracks": rows}


def write_outputs(manifest: dict, index: dict, excluded: list[dict],
                  dry_run: bool = False) -> None:
    if dry_run:
        return
    write_json(MANIFEST, manifest)
    write_json(OUT / "index.json", index)
    write_json(OUT / "exclusions.json",
               {"version": 1, "generated_at": gen.utcnow(),
                "counts": len(excluded), "exclusions": excluded})
    score_lines = []
    for path in sorted(SCORES.glob("*.abc")):
        score_lines.append(f"{sha256_file(path)}  {path.name}")
    (OUT / "scores.sha256").write_text("\n".join(score_lines) + "\n",
                                       encoding="utf-8")
    lines = [f"{sha256_file(OUT / 'index.json')}  index.json",
             f"{sha256_file(OUT / 'exclusions.json')}  exclusions.json",
             f"{sha256_file(MANIFEST)}  corpus.json",
             f"{sha256_file(OUT / 'scores.sha256')}  scores.sha256"]
    (OUT / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8")


def upload_bundle() -> None:
    tar_path = OUT / "scores.tar.gz"
    with tarfile.open(tar_path, "w:gz") as tar:
        for path in sorted(SCORES.glob("*.abc")):
            tar.add(path, arcname=path.name)
    gcs_cp(str(MANIFEST), f"{BUNDLE}/corpus.json")
    for name in ("index.json", "exclusions.json", "scores.sha256",
                 "SHA256SUMS", "scores.tar.gz"):
        gcs_cp(str(OUT / name), f"{BUNDLE}/{name}")


def fetch_bundle() -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    for name in ("corpus.json", "index.json", "exclusions.json",
                 "scores.sha256", "SHA256SUMS", "scores.tar.gz"):
        gcs_cp(f"{BUNDLE}/{name}", str(WORK / name))
    sums_path = WORK / "SHA256SUMS"
    for line in sums_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, filename = line.split(None, 1)
        path = WORK / filename.strip()
        if not path.is_file() or sha256_file(path) != digest:
            raise SystemExit(f"bundle checksum mismatch: {path}")
    if SCORES.exists():
        shutil.rmtree(SCORES)
    SCORES.mkdir(parents=True)
    with tarfile.open(WORK / "scores.tar.gz", "r:gz") as tar:
        try:
            tar.extractall(SCORES, filter="data")
        except TypeError:  # Python < 3.12
            tar.extractall(SCORES)
    shutil.copy2(WORK / "corpus.json", MANIFEST)
    OUT.mkdir(parents=True, exist_ok=True)
    for name in ("index.json", "exclusions.json", "scores.sha256",
                 "SHA256SUMS"):
        shutil.copy2(WORK / name, OUT / name)
    verify_local()


def verify_local() -> dict:
    if not MANIFEST.is_file():
        raise SystemExit(f"manifest missing: {MANIFEST}")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    songs = manifest.get("songs", [])
    scores = manifest.get("scores", {})
    if len(songs) != 489:
        raise SystemExit(f"manifest has {len(songs)} songs, expected 489")
    if len(scores) != 489:
        raise SystemExit(f"manifest has {len(scores)} scores, expected 489")
    names = [s["name"] for s in songs]
    if len(set(names)) != len(names):
        raise SystemExit("duplicate song names in manifest")
    missing = []
    bad_tags = []
    bad_duration = []
    for song in songs:
        name = song["name"]
        path = ROOT / scores[name]
        if not path.is_file():
            missing.append(str(path))
            continue
        text = path.read_text(encoding="utf-8")
        try:
            gen.score_section_tags(text, name)
        except gen.PlanError:
            bad_tags.append(name)
        if gen.abc_duration_s(text) is None:
            bad_duration.append(name)
    if missing:
        raise SystemExit(f"missing {len(missing)} score(s), e.g. {missing[:3]}")
    if bad_tags:
        raise SystemExit(f"{len(bad_tags)} score(s) have no section tags: "
                         f"{bad_tags[:5]}")
    if bad_duration:
        raise SystemExit(f"{len(bad_duration)} score(s) have no parsed "
                         f"duration: {bad_duration[:5]}")
    count = len(list(SCORES.glob("*.abc"))) if SCORES.is_dir() else 0
    if count != 489:
        raise SystemExit(f"score directory holds {count} files, expected 489")

    checksum_path = OUT / "scores.sha256"
    if checksum_path.is_file():
        for line in checksum_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            digest, filename = line.split(None, 1)
            path = SCORES / filename.strip()
            if not path.is_file():
                raise SystemExit(f"checksum references a missing score: {path}")
            if sha256_file(path) != digest:
                raise SystemExit(f"score checksum mismatch: {path}")

    index_path = OUT / "index.json"
    if index_path.is_file():
        index = json.loads(index_path.read_text(encoding="utf-8"))
        for row in index.get("tracks", []):
            if row.get("generation_status") != "ready":
                continue
            path = SCORES / f"{row['name']}.abc"
            if sha256_file(path) != row.get("instrumental_abc_sha256"):
                raise SystemExit(f"index hash mismatch: {path}")

    print("verified: 489 songs, 489 scores, hashes, tags and durations OK")
    print(f"manifest: {MANIFEST}")
    print(f"scores  : {SCORES}")
    return manifest


# --- main -------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--build", action="store_true",
                    help="read the frozen GCS source and build the corpus")
    ap.add_argument("--upload", action="store_true",
                    help="with --build, upload the bundle to GCS")
    ap.add_argument("--fetch", action="store_true",
                    help="download the bundle and materialize it locally")
    ap.add_argument("--verify", action="store_true",
                    help="check the local manifest and scores")
    ap.add_argument("--dry-run", action="store_true",
                    help="with --build, validate and print but write nothing")
    args = ap.parse_args(argv)

    if not (args.build or args.fetch or args.verify):
        ap.error("choose --build, --fetch or --verify")

    if args.fetch:
        fetch_bundle()
        return 0
    if args.verify:
        verify_local()
        return 0

    tracks = load_source(WORK)
    ready, excluded = select_tracks(tracks)
    print(f"source: {len(tracks)} tracks; selected for conversion: {len(ready)}")
    instrumentalize(ready, dry_run=args.dry_run)
    if args.dry_run:
        print(f"dry-run: would convert {len(ready)} scores")
        for item in excluded:
            print(f"  excluded {item['name']}: {item['reason']}")
        return 0

    good, conversion_failed = validate_outputs(ready)
    excluded.extend(conversion_failed)
    print(f"converted: {len(good)}; conversion failures: "
          f"{len(conversion_failed)}")
    reference = load_reference()
    manifest = build_manifest(good, reference)
    index = build_index(tracks, good, excluded)
    write_outputs(manifest, index, excluded)
    verify_local()
    print(f"excluded: {len(excluded)}")
    for item in excluded:
        print(f"  {item['name']}: {item['reason']}")
    if args.upload:
        upload_bundle()
        print(f"uploaded bundle: {BUNDLE}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
