#!/usr/bin/env python3
"""Inventory the prebuilt `audiocpp_cli` artifacts under this repo's GCS prefix.

The bucket layout only carries one `manifest.json` per arch folder; there is no
top-level register. This script builds one from those manifests (plus remote
object sizes/timestamps) and can publish it to `binaries/index.json`, so the
next person can answer "what exists, for which GPU, and when was it built?"
without reading every folder.

Usage:
    python plumbing/binary_registry.py                  # human table
    python plumbing/binary_registry.py --json           # machine-readable JSON
    python plumbing/binary_registry.py --write-index    # upload binaries/index.json
    python plumbing/binary_registry.py --check          # fail if a published
                                                        # sha256 disagrees
    python plumbing/binary_registry.py --prefix gs://bucket/prefix

The arch list is the same one `plumbing/arch.sh` maps compute capabilities to.
An expected arch with no uploaded artifacts is reported as `missing` rather than
being silently absent.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys

DEFAULT_ROOT = os.environ.get("GCP_ROOT", "gs://akbar-december-2024-backup")
DEFAULT_PREFIX = DEFAULT_ROOT.rstrip("/") + "/arabmaqamrock"

# Keep in sync with plumbing/arch.sh.
EXPECTED = {
    "sm75-t4": {"gpu": "Tesla T4", "cuda_arch": "75"},
    "sm80-a100": {"gpu": "NVIDIA A100", "cuda_arch": "80"},
    "sm89-l4": {"gpu": "NVIDIA L4", "cuda_arch": "89"},
}
META_SUFFIXES = (".sha256", ".json", ".log", ".tar.gz", ".tgz")
LINE_RE = re.compile(r"^\s*(\d+)\s+(\S+)\s+(gs://\S+)$")


def gcs_base() -> tuple[str, list[str]]:
    if shutil.which("gcloud"):
        return "gcloud", ["storage"]
    if shutil.which("gsutil"):
        return "gsutil", []
    sys.exit("binary_registry: need `gcloud` or `gsutil` on PATH")


def run(cmd: list[str], *, input_text: str | None = None) -> str:
    result = subprocess.run(cmd, capture_output=True, text=True,
                            input=input_text)
    if result.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)} failed: "
                           f"{(result.stderr or result.stdout).strip()}")
    return result.stdout


def list_objects(prefix: str) -> dict[str, dict]:
    """remote path -> {size_bytes, updated} for everything under prefix."""
    cli, sub = gcs_base()
    out = run([cli, *sub, "ls", "-l", "-r", prefix.rstrip("/") + "/"])
    objects: dict[str, dict] = {}
    for line in out.splitlines():
        m = LINE_RE.match(line)
        if not m:
            continue
        size, updated, path = m.groups()
        objects[path] = {"size_bytes": int(size), "updated": updated}
    return objects


def read_text(remote: str) -> str | None:
    cli, sub = gcs_base()
    try:
        return run([cli, *sub, "cat", remote])
    except RuntimeError:
        return None


def read_json(remote: str) -> dict | None:
    text = read_text(remote)
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def split_arch(objects: dict[str, dict], prefix: str) -> dict[str, dict[str, dict]]:
    """binaries/<tag>/[...]/file -> {tag: {dir: {name: info}}}."""
    base = prefix.rstrip("/") + "/binaries/"
    arch: dict[str, dict[str, dict]] = {}
    for path, info in objects.items():
        if not path.startswith(base):
            continue
        rel = path[len(base):]
        parts = rel.split("/")
        if len(parts) < 2:
            continue
        tag, dirs, name = parts[0], parts[1:-1], parts[-1]
        subdir = "/".join(dirs)
        arch.setdefault(tag, {}).setdefault(subdir, {})[name] = {
            **info, "path": path,
        }
    return arch


def sha_from_file(text: str | None) -> str | None:
    if not text:
        return None
    token = text.split()[0].strip() if text.split() else ""
    return token or None


def artifact_for(files: dict[str, dict], manifest: dict | None) -> str | None:
    if manifest:
        for key in ("artifact", "name", "file"):
            value = manifest.get(key)
            if isinstance(value, str) and value in files:
                return value
    candidates = [n for n in files if not n.endswith(META_SUFFIXES)]
    if len(candidates) == 1:
        return candidates[0]
    return None


def build_registry(prefix: str) -> dict:
    objects = list_objects(prefix)
    arch = split_arch(objects, prefix)
    architectures: dict[str, dict] = {}

    for tag in sorted(set(EXPECTED) | set(arch)):
        meta = EXPECTED.get(tag, {})
        entry = {
            "gpu": meta.get("gpu", "unknown"),
            "cuda_arch": meta.get("cuda_arch"),
            "status": "missing",
            "artifacts": [],
        }
        for subdir, files in sorted(arch.get(tag, {}).items()):
            manifest_path = f"{prefix.rstrip('/')}/binaries/{tag}/"
            manifest_path += f"{subdir + '/' if subdir else ''}manifest.json"
            manifest = read_json(manifest_path)
            name = artifact_for(files, manifest)
            if not name:
                continue
            info = files[name]
            sha_path = info["path"] + ".sha256"
            sha_text = read_text(sha_path) if sha_path in objects else None
            m = manifest or {}
            recorded = m.get("sha256")
            published = sha_from_file(sha_text)
            entry["artifacts"].append({
                "name": name,
                "subdir": subdir,
                "remote_path": info["path"],
                "size_bytes": info["size_bytes"],
                "remote_updated": info["updated"],
                "built_at": m.get("built_at"),
                "published_at": m.get("published_at"),
                # Older/prefix manifests use different spellings.
                "audio_cpp_commit": (m.get("audio_cpp_commit")
                                     or m.get("local_head")
                                     or m.get("base_commit")),
                "ggml_commit": m.get("ggml_commit") or m.get("ggml_version"),
                "cuda_toolkit": m.get("cuda_toolkit") or m.get("cuda_version"),
                "arch_tag": m.get("arch_tag", tag),
                "purpose": m.get("purpose"),
                "sha256_manifest": recorded,
                "sha256_published": published,
                "sha256_match": (recorded == published) if recorded and published else None,
                "manifest": manifest_path if manifest else None,
            })
            entry["status"] = "available"
        architectures[tag] = entry

    return {
        "generated_at": dt.datetime.now(dt.timezone.utc)
                         .strftime("%Y-%m-%dT%H:%M:%SZ"),
        "prefix": prefix.rstrip("/"),
        "index": prefix.rstrip("/") + "/binaries/index.json",
        "architectures": architectures,
    }


def fmt_size(n: int | None) -> str:
    if not n:
        return "-"
    for unit in ("B", "KiB", "MiB", "GiB"):
        if n < 1024 or unit == "GiB":
            return f"{n:.1f}{unit}" if unit != "B" else f"{n}B"
        n /= 1024
    return f"{n:.1f}GiB"


def print_table(reg: dict) -> None:
    print(f"registry: {reg['index']}")
    print(f"generated: {reg['generated_at']}\n")
    for tag, entry in reg["architectures"].items():
        if not entry["artifacts"]:
            print(f"{tag:<12} {entry['gpu']:<14} {'MISSING':<9}")
            continue
        for a in entry["artifacts"]:
            commit = (a.get("audio_cpp_commit") or "unknown")[:12]
            built = a.get("built_at") or a.get("remote_updated") or "?"
            sha = (a.get("sha256_manifest") or "?")[:12]
            label = tag + ("/" + a["subdir"] if a["subdir"] else "")
            print(f"{label:<20} {entry['gpu']:<14} {a['name']:<34} "
                  f"{built:<20} cuda={a.get('cuda_toolkit') or '?':<10} "
                  f"commit={commit:<12} {fmt_size(a['size_bytes']):>9} "
                  f"sha={sha}")


def main() -> int:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--prefix", default=DEFAULT_PREFIX,
                   help=f"GCS prefix (default: {DEFAULT_PREFIX})")
    p.add_argument("--json", action="store_true", help="print JSON")
    p.add_argument("--write-index", action="store_true",
                   help="upload the registry to <prefix>/binaries/index.json")
    p.add_argument("--check", action="store_true",
                   help="exit non-zero if a manifest sha256 disagrees with its "
                        ".sha256 file")
    args = p.parse_args()

    try:
        reg = build_registry(args.prefix)
    except RuntimeError as exc:
        print(f"binary_registry: {exc}", file=sys.stderr)
        return 2

    mismatches = [
        (tag, a["name"], a["sha256_manifest"], a["sha256_published"])
        for tag, e in reg["architectures"].items()
        for a in e["artifacts"]
        if a["sha256_match"] is False
    ]

    if args.write_index:
        payload = json.dumps(reg, indent=2) + "\n"
        cli, sub = gcs_base()
        try:
            run([cli, *sub, "cp", "-", reg["index"]], input_text=payload)
        except RuntimeError as exc:
            print(f"binary_registry: could not write index: {exc}",
                  file=sys.stderr)
            return 2
        print(f"wrote {reg['index']}")

    if args.json:
        print(json.dumps(reg, indent=2))
    elif not args.write_index:
        print_table(reg)

    if args.check and mismatches:
        for tag, name, want, have in mismatches:
            print(f"sha256 MISMATCH {tag}/{name}: manifest={want} "
                  f"published={have}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
