#!/usr/bin/env python3
"""Publish the two YT500 bundles with explicit role labels and SHA256SUMS.

Kinds
-----
dataset   durable SheetSage2 outputs:
          ``DATASET/yt500_instrumental_transcripts/``
          flat ``<name>.output.abc``/``.output.meta.json`` (uploaded by the
          sync loop) plus archives, manifest, README, DATASET_CARD, SHA256SUMS.

analysis  cheap-to-regenerate study products:
          ``ANALYSIS/yt500_instrumental_abc/``
          ``input/<name>.input.abc``, ``similarity/*`` and SHA256SUMS.

The read-only input dataset is never written to.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DATASET_PREFIX = "gs://akbar-december-2024-backup/DATASET/yt500_instrumental_transcripts"
ANALYSIS_PREFIX = "gs://akbar-december-2024-backup/ANALYSIS/yt500_instrumental_abc"
INPUT_DATASET = "gs://akbar-december-2024-backup/DATASET/yt500_instrumental"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def gsutil(args: list[str], check: bool = True):
    return subprocess.run(["gsutil", "-q", *args], check=check,
                          capture_output=True, text=True)


def upload_many(pairs: list[tuple[Path, str]]) -> int:
    """Upload (local, remote) objects.  Kept for small doc bundles."""
    for local, remote in pairs:
        gsutil(["cp", str(local), remote])
    return len(pairs)


def verified_names(transcripts: Path) -> list[str]:
    sys.path.insert(0, str(REPO / "plumbing"))
    import transcript_archive as TA
    out = []
    for d in sorted(p for p in transcripts.iterdir() if p.is_dir()):
        ok, _ = TA.is_complete(d)
        if ok:
            out.append(d.name)
    return out


def cmd_dataset(args) -> int:
    tx = Path(args.transcripts)
    prefix = args.prefix.rstrip("/")
    names = verified_names(tx)
    publish = Path(args.publish_dir)
    manifest, sums = [], []
    for name in names:
        abc = tx / name / "score.abc"
        meta = publish / f"{name}.output.meta.json"
        arch = tx / f"{name}.tar.gz"
        if not (abc.is_file() and meta.is_file() and arch.is_file()):
            continue
        abc_sha, meta_sha, arch_sha = (sha256_file(abc), sha256_file(meta),
                                       sha256_file(arch))
        m = read_json(meta)
        manifest.append({
            "name": name,
            "role": "output_transcript",
            "output_abc": f"{name}.output.abc",
            "abc_sha256": abc_sha,
            "meta_sha256": meta_sha,
            "archive": f"archives/{name}.output-transcript.tar.gz",
            "archive_sha256": arch_sha,
            "input_sha256": m.get("input_sha256"),
            "input_uri": m.get("input_uri"),
            "audio_sha256": m.get("audio_sha256"),
            "audio_uri": m.get("audio_uri"),
            "model": m.get("model"),
            "model_revision": m.get("model_revision"),
            "melody_only": m.get("melody_only"),
            "seconds": m.get("seconds"),
        })
        sums += [(f"{abc_sha}  {name}.output.abc", f"{prefix}/{name}.output.abc"),
                 (f"{meta_sha}  {name}.output.meta.json",
                  f"{prefix}/{name}.output.meta.json"),
                 (f"{arch_sha}  archives/{name}.output-transcript.tar.gz",
                  f"{prefix}/archives/{name}.output-transcript.tar.gz")]

    manifest_text = "\n".join(json.dumps(r, sort_keys=True) for r in manifest) + "\n"
    sums_text = "\n".join(s for s, _ in sums) + "\n"
    card = f"""# YT500 instrumental — OUTPUT transcripts

**This is the OUTPUT side.** Every `*.output.abc` here is a SheetSage2
transcript of the generated instrumental audio. The **INPUT** scores are the
conditioner: `{INPUT_DATASET}/tracks/<name>/score.abc`.
Match them by `<name>`; `output.meta.json` records `input_sha256`.

- tracks: {len(manifest)}
- model: `m-a-p/SheetSage2` revision `b83c3d79a6d98bcffaf8f9ed112c90aa887887bc`
- mode: `--full` (melody + chord symbols)
- flat mirror: `<name>.output.abc`, `<name>.output.meta.json`
- full archive: `archives/<name>.output-transcript.tar.gz` (contains the whole
  transcribe.py directory; internally the ABC keeps the legacy name
  `score.abc`, which the archive name and sidecar mark as the output side)
- `manifest.jsonl`: per-track hashes and provenance
- `SHA256SUMS`: verify with `sha256sum -c SHA256SUMS`
"""
    readme = f"""# YT500 instrumental transcript bundle

Output side only. Inputs live read-only at
`{INPUT_DATASET}/tracks/<name>/score.abc`.
See `DATASET_CARD.md` for the disambiguation and `manifest.jsonl` for hashes.

Layout::

    <name>.output.abc
    <name>.output.meta.json
    archives/<name>.output-transcript.tar.gz
    archives/_archive_index.json
    manifest.jsonl
    SHA256SUMS
    README.md
    DATASET_CARD.md
    _SUCCESS
"""
    out = Path(args.staging)
    write(out / "DATASET_CARD.md", card)
    write(out / "README.md", readme)
    write(out / "manifest.jsonl", manifest_text)
    write(out / "SHA256SUMS", sums_text)

    pairs = [(out / "DATASET_CARD.md", f"{prefix}/DATASET_CARD.md"),
             (out / "README.md", f"{prefix}/README.md"),
             (out / "manifest.jsonl", f"{prefix}/manifest.jsonl"),
             (out / "SHA256SUMS", f"{prefix}/SHA256SUMS")]
    for local, remote in pairs:
        gsutil(["cp", str(local), remote])
    write(out / "_SUCCESS", json.dumps({
        "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "tracks": len(manifest), "role": "output_transcript"}) + "\n")
    gsutil(["cp", str(out / "_SUCCESS"), f"{prefix}/_SUCCESS"])
    print(json.dumps({"dataset": prefix, "tracks": len(manifest),
                      "objects_hashed": len(sums)}))
    return 0


def cmd_analysis(args) -> int:
    input_dir = Path(args.input_dir)
    sim = Path(args.similarity)
    work = Path(args.work)
    prefix = args.prefix.rstrip("/")
    sums: list[str] = []

    input_files = sorted(input_dir.glob("*.input.abc"))
    for p in input_files:
        sums.append(f"{sha256_file(p)}  input/{p.name}")
    sim_files = [p for p in sorted(sim.rglob("*")) if p.is_file()
                 and p.name != "SHA256SUMS"]
    for p in sim_files:
        rel = p.relative_to(sim).as_posix()
        sums.append(f"{sha256_file(p)}  similarity/{rel}")
    for fname in ("pairs.json", "cohort.json", "failures.json"):
        p = work / fname
        if p.is_file():
            sums.append(f"{sha256_file(p)}  {fname}")

    sums_text = "\n".join(sums) + "\n"
    staging = Path(args.staging)
    write(staging / "SHA256SUMS", sums_text)
    write(staging / "README.md", f"""# YT500 input-vs-output ABC similarity — analysis bundle

- `input/<name>.input.abc` — conditioning scores (role: input)
- `similarity/` — matched table, all-pairs parquet, cohort stats, flags,
  escalation, audit, summary.md, distributions.png
- `pairs.json`, `cohort.json`, `failures.json`

Inputs are read-only copies of `{INPUT_DATASET}/tracks/<name>/score.abc`.
Outputs are `{DATASET_PREFIX}/<name>.output.abc`.
Verify with `sha256sum -c SHA256SUMS`.
""")
    sums.append(f"{sha256_file(staging / 'README.md')}  README.md")
    write(staging / "SHA256SUMS", "\n".join(sums) + "\n")

    # Bulk uploads keep basenames unique: <name>.input.abc and similarity/*.
    if input_files:
        r = subprocess.run(["gsutil", "-q", "-m", "cp",
                            *[str(p) for p in input_files],
                            f"{prefix}/input/"], capture_output=True, text=True)
        if r.returncode != 0:
            print(r.stderr[:500], file=sys.stderr)
            return 1
    if sim_files:
        r = subprocess.run(["gsutil", "-q", "-m", "cp",
                            *[str(p) for p in sim_files],
                            f"{prefix}/similarity/"], capture_output=True, text=True)
        if r.returncode != 0:
            print(r.stderr[:500], file=sys.stderr)
            return 1
    docs = [(staging / "README.md", f"{prefix}/README.md"),
            (staging / "SHA256SUMS", f"{prefix}/SHA256SUMS")]
    for fname in ("pairs.json", "cohort.json", "failures.json"):
        p = work / fname
        if p.is_file():
            docs.append((p, f"{prefix}/{fname}"))
    upload_many(docs)
    objects = len(input_files) + len(sim_files) + len(docs)
    print(f"uploaded {len(input_files)} inputs, {len(sim_files)} similarity files, "
          f"{len(docs)} docs", flush=True)
    write(staging / "_SUCCESS", json.dumps({
        "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "commit": args.commit or "unknown", "objects": objects}) + "\n")
    gsutil(["cp", str(staging / "_SUCCESS"), f"{prefix}/_SUCCESS"])
    print(json.dumps({"analysis": prefix, "objects": objects}))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="kind", required=True)
    d = sub.add_parser("dataset")
    d.add_argument("--transcripts", default="/content/yt500/transcripts")
    d.add_argument("--publish-dir", default=str(REPO / "work/yt500_abc/publish"))
    d.add_argument("--staging", default=str(REPO / "work/yt500_abc/publish_bundle/dataset"))
    d.add_argument("--prefix", default=DATASET_PREFIX)
    d.set_defaults(func=cmd_dataset)
    a = sub.add_parser("analysis")
    a.add_argument("--input-dir", default=str(REPO / "work/yt500_abc/input"))
    a.add_argument("--similarity", default=str(REPO / "work/yt500_abc/similarity"))
    a.add_argument("--work", default=str(REPO / "work/yt500_abc"))
    a.add_argument("--prefix", default=ANALYSIS_PREFIX)
    a.add_argument("--staging", default=str(REPO / "work/yt500_abc/publish_bundle/analysis"))
    a.add_argument("--commit", default=None)
    a.set_defaults(func=cmd_analysis)
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
