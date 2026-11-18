#!/usr/bin/env python3
"""Build the uploadable test corpus for the last-bayt repetition work.

Everything here exists so a future session can re-test alignment / counting
ideas **without a GPU and without re-running Demucs**: stems are 16 kHz mono
FLAC (what every aligner and ASR model resamples to anyway), and the small
metadata files are copied verbatim.

    python3 analysis/hac_clone/build_gcs_corpus.py --staging work/gcs_last_bayt_repeat

Then upload:

    gsutil -m cp -r work/gcs_last_bayt_repeat/* \
        gs://akbar-december-2024-backup/arabmaqamrock/datasets/last_bayt_repeat/
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / "work"

REFERENCE = {"hac_01": Path("/content/hac_01.words.json"),
             "hac_02": Path("/content/hac_02.words.json")}


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def copy_tree(staging: Path) -> list[Path]:
    out: list[Path] = []
    plan = [
        (WORK / "karaoke", staging / "karaoke"),
        (WORK / "ctc", staging / "ctc"),
    ]
    for src, dst in plan:
        for f in sorted(src.rglob("*")):
            if not f.is_file() or f.suffix == ".pyc":
                continue
            rel = f.relative_to(src)
            (dst / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dst / rel)
            out.append(dst / rel)

    (staging / "asr").mkdir(parents=True, exist_ok=True)
    for f in sorted(WORK.glob("asr_*_small.csv")) + sorted(WORK.glob("asr_*_medium.csv")):
        shutil.copy2(f, staging / "asr" / f.name)
        out.append(staging / "asr" / f.name)
    for f in sorted((WORK / "asr_cache").rglob("*.json")) + sorted((WORK / "asr_cache_ctrl").rglob("*.json")):
        group = "controls" if f.parent.name == "asr_cache_ctrl" else f.parent.name
        dst = staging / "asr" / "cache" / group / f.name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, dst)
        out.append(dst)

    (staging / "results").mkdir(parents=True, exist_ok=True)
    for f in [ROOT / "analysis/last_bayt_repeat/results.csv",
              *sorted(WORK.glob("controls_vs_hac.csv")),
              *sorted(WORK.glob("clone_fit_*.csv"))]:
        if f.is_file():
            shutil.copy2(f, staging / "results" / f.name)
            out.append(staging / "results" / f.name)

    (staging / "karaoke/reference").mkdir(parents=True, exist_ok=True)
    for name, p in REFERENCE.items():
        if p.is_file():
            shutil.copy2(p, staging / "karaoke/reference" / p.name)
            out.append(staging / "karaoke/reference" / p.name)
    return out


def track_rows(staging: Path) -> list[dict]:
    rows: dict[tuple[str, str], dict] = {}

    def get(batch: str, track: str) -> dict:
        return rows.setdefault((batch, track), {"batch": batch, "track": track})

    for r in csv.DictReader((ROOT / "analysis/last_bayt_repeat/results.csv").open(encoding="utf-8")):
        t = get(r["batch"], r["track"])
        t.update(seed=int(r["seed"]), cot=r["cot"], abc=r["abc_file"], cap=int(r["cap"]),
                 duration_s=float(r["audio_duration_s"]),
                 asr_count=int(r["asr_count"]), asr_medium=int(r["asr_count_medium"]),
                 ctc_count=int(r["ctc_count"]), ctc_count_asr_ok=int(r["ctc_count_asr_ok"]),
                 review_flag=r["review_flag"])

    for batch in ("OFF", "WOLF", "KURD"):
        f = WORK / f"asr_{batch}_small.csv"
        if not f.is_file():
            continue
        for r in csv.DictReader(f.open(encoding="utf-8")):
            t = get(batch, r["track"])
            t.update(seed=int(r["seed"]), cot=r["cot"] or "off", abc=None,
                     cap=int(r["cap"]) if r["cap"] else None,
                     duration_s=float(r["duration_s"]),
                     asr_count=int(r["occurrences"]), asr_medium=None,
                     ctc_count=None, ctc_count_asr_ok=None, review_flag=None)

    for f in sorted(WORK.glob("clone_fit_*.csv")):
        for r in csv.DictReader(f.open(encoding="utf-8")):
            batch = "B" if f.name.endswith("_B.csv") else "A"
            t = rows.get((batch, r["take"]))
            if t:
                t["pace_vs_reference"] = float(r["pace"])
                t["drift_s_vs_reference"] = float(r["landmark_s"])

    out = []
    for (batch, track), t in sorted(rows.items()):
        # control manifests name the track without its seed, while Demucs wrote
        # ``<name>_<seed>/``; accept whichever exists and record the real folder
        base = staging / "stems16k" / batch
        folder = base / track
        if not folder.is_dir() and base.is_dir():
            cands = sorted(p for p in base.iterdir()
                           if p.is_dir() and p.name.startswith(track + "_"))
            folder = cands[0] if cands else folder
        t["track_dir"] = folder.name
        stems = {}
        for kind in ("vocals", "no_vocals"):
            p = folder / f"{kind}.flac"
            stems[kind] = {"file": str(p.relative_to(staging)), "bytes": p.stat().st_size,
                           "sha256": sha256(p)} if p.is_file() else None
        t["stems"] = stems
        out.append(t)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--staging", type=Path, default=WORK / "gcs_last_bayt_repeat")
    args = ap.parse_args()
    staging = args.staging
    if not (staging / "stems16k").is_dir():
        raise SystemExit(f"{staging}/stems16k missing — run the ffmpeg conversion first")

    extra = copy_tree(staging)
    readme = ROOT / "analysis/hac_clone/gcs_corpus.md"
    if readme.is_file():
        shutil.copy2(readme, staging / "README.md")
        extra.append(staging / "README.md")
    tracks = track_rows(staging)
    stems = [p for p in (staging / "stems16k").rglob("*.flac")]
    total = sum(p.stat().st_size for p in stems)

    manifest = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "purpose": "Offline test corpus for last-bayt repetition / karaoke alignment work. "
                   "Not for listening or mixing.",
        "source_repo": "github.com/akbargherbal/arabmaqamrock",
        "source_runs": [
            "gs://akbar-december-2024-backup/arabmaqamrock/runs/20261117-082924_harith_hac_a/",
            "gs://akbar-december-2024-backup/arabmaqamrock/runs/20261117-093512_harith_hac_b/",
            "gs://akbar-december-2024-backup/arabmaqamrock/runs/20261116-121703_imru_al_qais_sama_laka_shawqun_mix_grid/",
            "gs://akbar-december-2024-backup/arabmaqamrock/runs/20261115-134829_wolf_grid04/",
            "gs://akbar-december-2024-backup/arabmaqamrock/runs/20261115-184206_kurd_mix_grid/",
        ],
        "stems_format": {
            "codec": "FLAC, PCM-16",
            "sample_rate": 16000,
            "channels": 1,
            "ffmpeg": "ffmpeg -ac 1 -ar 16000 -c:a flac -compression_level 8 -map_metadata -1",
            "note": "Demucs originally wrote 44.1 kHz stereo WAV; this is the "
                    "16 kHz mono form every aligner/ASR model resamples to.",
        },
        "counts": {
            "tracks": len(tracks),
            "stem_files": len(stems),
            "stems_bytes": total,
            "reference_alignments": len([p for p in REFERENCE.values() if p.is_file()]),
        },
        "tracks": tracks,
        "other_files": [
            {"file": str(p.relative_to(staging)), "bytes": p.stat().st_size, "sha256": sha256(p)}
            for p in sorted(extra)
        ],
    }
    (staging / "MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + "\n",
                                           encoding="utf-8")
    print(f"{len(tracks)} tracks, {len(stems)} stems, {total/1e6:.0f} MB")
    print(f"extra files: {len(extra)}")
    print(f"wrote {staging/'MANIFEST.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
