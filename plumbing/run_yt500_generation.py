#!/usr/bin/env python3
"""GCS-resumable driver for the 489-song YT500 instrumental generation.

The GCS run tree is the source of truth. A take is done when its run has a
``batch_manifest.json`` track with the same score hash and a
``<name>_<seed>_time.txt`` containing ``Exit status: 0``. Nothing is restored
except that metadata; old audio and old Colab environments are irrelevant.

Modes:
    --status                 print corpus/done/pending, no writes
    --plan-only              same, plus the next pending names
    --run                    new session: write pending manifest, generate
    --run --batch            A100 fast path via audiocpp_cli --request-sequence
    --fetch-corpus           download/materialize the frozen corpus first

The default per-track path delegates to generate.py (one process per song).
The batch path asks generate.py for the resolved request list, then renders it
in one loaded session and writes the same per-take markers run_one.sh would.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import generate as gen  # noqa: E402  (pure Python; no torch)

DEFAULT_CORPUS = ROOT / "manifests" / "yt500_instrumental_489.json"
DEFAULT_RUNS = "gs://akbar-december-2024-backup/arabmaqamrock/runs"
DEFAULT_WORK = ROOT / "work" / "yt500_gen"
DEFAULT_LABEL = "yt500inst"
META_EXCLUDE = r".*\.(wav|mp3|log|csv)$"


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json_atomic(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    tmp.replace(path)


def read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


# --- corpus -----------------------------------------------------------------

def load_corpus(path: Path) -> dict:
    data = read_json(path)
    if data is None:
        raise SystemExit(
            f"corpus manifest not found or invalid: {path}\n"
            f"run: python3 plumbing/yt500_generation_corpus.py --fetch")
    songs = data.get("songs") or []
    scores = data.get("scores") or {}
    if not songs:
        raise SystemExit(f"corpus has no songs: {path}")
    base = (path.parent / data.get("base_dir", ".")).resolve()
    names = [s["name"] for s in songs]
    if len(set(names)) != len(names):
        raise SystemExit("corpus has duplicate song names")
    score_paths: dict[str, Path] = {}
    score_hashes: dict[str, str] = {}
    missing = []
    for name in names:
        rel = scores.get(name)
        if not rel:
            missing.append(name)
            continue
        p = (base / rel).resolve()
        if not p.is_file():
            missing.append(str(p))
            continue
        score_paths[name] = p
        score_hashes[name] = sha256_file(p)
    if missing:
        raise SystemExit(
            f"corpus is missing {len(missing)} score(s), e.g. {missing[:3]}\n"
            f"run: python3 plumbing/yt500_generation_corpus.py --fetch")
    return {"data": data, "base": base, "names": names,
            "score_paths": score_paths, "score_hashes": score_hashes,
            "songs": {s["name"]: s for s in songs}}


# --- remote metadata --------------------------------------------------------

def _which(*names: str) -> str | None:
    for name in names:
        if shutil.which(name):
            return name
    return None


def sync_meta(remote: str, local: Path) -> None:
    """Download a run's metadata only (no audio/logs/csv)."""
    local.mkdir(parents=True, exist_ok=True)
    remote = remote.rstrip("/") + "/"
    if shutil.which("gsutil"):
        cmd = ["gsutil", "-m", "rsync", "-r", "-x", META_EXCLUDE,
               remote, str(local) + "/"]
    elif shutil.which("gcloud"):
        cmd = ["gcloud", "storage", "rsync", "-r",
               f"--exclude={META_EXCLUDE}", remote, str(local) + "/"]
    else:
        raise SystemExit("need gsutil or gcloud to read the GCS run tree")
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise SystemExit(
            f"metadata sync failed: {' '.join(cmd)}\n"
            f"{(proc.stderr or proc.stdout).strip()[-3000:]}")


def list_remote_runs(gcs_runs: str) -> list[str]:
    pattern = gcs_runs.rstrip("/") + "/*_yt500inst/"
    if shutil.which("gcloud"):
        cmd = ["gcloud", "storage", "ls", pattern]
    elif shutil.which("gsutil"):
        cmd = ["gsutil", "ls", "-d", pattern]
    else:
        raise SystemExit("need gsutil or gcloud to list the GCS run tree")
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        return []
    out = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if line.startswith("gs://"):
            out.append(line.rstrip("/"))
    return sorted(set(out))


def fetch_metadata(gcs_runs: str, meta_root: Path,
                   *, refresh: bool = True) -> list[Path]:
    if refresh and meta_root.exists():
        shutil.rmtree(meta_root)
    meta_root.mkdir(parents=True, exist_ok=True)
    runs = []
    for uri in list_remote_runs(gcs_runs):
        dest = meta_root / uri.rsplit("/", 1)[-1]
        sync_meta(uri, dest)
        runs.append(dest)
    return runs


# --- done set ---------------------------------------------------------------

def scan_done(meta_root: Path, corpus: dict) -> tuple[set[str], list[dict], dict]:
    """Return (done names, per-run counts, mismatches)."""
    done: set[str] = set()
    per_run: dict[str, int] = {}
    mismatches: list[dict] = []
    for run_dir in sorted(p for p in meta_root.iterdir() if p.is_dir()):
        manifest = read_json(run_dir / "batch_manifest.json")
        if not manifest:
            continue
        count = 0
        for track in manifest.get("tracks", []):
            name = track.get("name")
            seed = track.get("seed")
            if name not in corpus["songs"] or seed is None:
                continue
            if track.get("abc_sha256") != corpus["score_hashes"][name]:
                mismatches.append({
                    "run": run_dir.name, "name": name,
                    "got": track.get("abc_sha256"),
                    "want": corpus["score_hashes"][name]})
                continue
            time_file = run_dir / f"{name}_{seed}_time.txt"
            try:
                text = time_file.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if "Exit status: 0" not in text:
                continue
            done.add(name)
            count += 1
        per_run[run_dir.name] = count
    return done, [{"run": k, "done": v} for k, v in sorted(per_run.items())], mismatches


def pending_names(corpus: dict, done: set[str], limit: int | None = None) -> list[str]:
    names = [name for name in corpus["names"] if name not in done]
    if limit is not None:
        names = names[:limit]
    return names


# --- session manifest / requests -------------------------------------------

def write_session_manifest(corpus: dict, names: list[str], path: Path) -> dict:
    data = corpus["data"]
    songs = []
    for name in names:
        source = corpus["songs"][name]
        entry = {"name": name, "score": name}
        for key in ("seed", "seeds", "cap", "quantile", "cot", "lora",
                    "trigger"):
            if key in source:
                entry[key] = source[key]
        songs.append(entry)
    payload = {
        "base_dir": str(corpus["base"]),
        "loras": data["loras"],
        "scores": {name: data["scores"][name] for name in names},
        "defaults": data["defaults"],
        "songs": songs,
    }
    write_json_atomic(path, payload)
    return payload


def pick_run_dir(out_root: Path, label: str) -> Path:
    out_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    candidate = out_root / f"{stamp}_{label}"
    n = 2
    while candidate.exists():
        candidate = out_root / f"{stamp}_{label}-{n}"
        n += 1
    return candidate


# --- batch markers ----------------------------------------------------------

def write_marker(run_dir: Path, track: dict, wav: Path,
                 *, lora_alias: str | None, lora_scale: dict,
                 allow_unstable: bool = False) -> bool:
    """Write the per-take _time.txt + sidecar the backup pipeline expects."""
    name = track["name"]
    seed = track["seed"]
    stem = f"{name}_{seed}"
    try:
        size = wav.stat().st_size
    except OSError:
        return False
    if size <= 0:
        return False
    duration = gen.wav_duration(wav)
    if duration is None or duration < 5.0:
        return False
    marker = run_dir / f"{stem}_time.txt"
    sidecar = run_dir / f"{stem}.json"
    if marker.is_file() and sidecar.is_file() and not allow_unstable:
        return False
    digest = sha256_file(wav)
    marker.write_text(
        'Command being timed: "audiocpp_cli --request-sequence"\n'
        "Exit status: 0\n", encoding="utf-8")
    write_json_atomic(sidecar, {
        "name": name,
        "take": track.get("take", 0),
        "seed": seed,
        "cap": track.get("cap"),
        "score_alias": track.get("score_alias"),
        "abc_sha256": track.get("abc_sha256"),
        "cot": track.get("cot"),
        "lora_alias": lora_alias,
        "lora_scale": lora_scale,
        "status": "ok",
        "exit": 0,
        "engine": "batch",
        "wav_sha256": digest,
        "wav_bytes": size,
        "wav_duration_s": round(duration, 3),
        "end_utc": utcnow(),
    })
    return True


def scan_wavs(run_dir: Path, tracks_by_id: dict, *, lora_alias: str | None,
              lora_scale: dict, sizes: dict, final: bool = False) -> list[str]:
    marked = []
    for wav in sorted(run_dir.glob("*.wav")):
        stem = wav.stem
        track = tracks_by_id.get(stem)
        if track is None:
            continue
        marker = run_dir / f"{stem}_time.txt"
        if marker.is_file():
            continue
        try:
            size = wav.stat().st_size
        except OSError:
            continue
        if not final and sizes.get(stem) != size:
            sizes[stem] = size
            continue
        if write_marker(run_dir, track, wav, lora_alias=lora_alias,
                        lora_scale=lora_scale, allow_unstable=final):
            marked.append(stem)
            print(f"  marked {stem} ({size} bytes)")
    return marked


def marker_loop(stop: threading.Event, run_dir: Path, tracks_by_id: dict,
                lora_alias: str | None, lora_scale: dict) -> None:
    sizes: dict = {}
    while not stop.wait(5.0):
        scan_wavs(run_dir, tracks_by_id, lora_alias=lora_alias,
                  lora_scale=lora_scale, sizes=sizes)


# --- batch execution --------------------------------------------------------

def resolve_session_loras(session: dict, base_dir: Path) -> tuple[Path, Path, str | None, dict]:
    defaults = session.get("defaults", {})
    alias = defaults.get("lora")
    loras = session.get("loras", {})
    if not alias or alias not in loras:
        raise SystemExit(f"session defaults.lora is not in the lora registry: {alias!r}")
    spec = loras[alias]
    ar = (base_dir / spec["ar"]).resolve()
    nar = (base_dir / spec["nar"]).resolve()
    scale = {"ar": defaults.get("lora_ar_scale", 1.0),
             "nar": defaults.get("lora_nar_scale", 1.0)}
    return ar, nar, alias, scale


def run_with_cuda(cmd: list[str], *, cwd: Path | None = None) -> int:
    """Run a CLI that links CUDA 12, with the repo's loader path applied."""
    script = f'. "{ROOT / "cuda_loader_path.sh"}" && exec "$@"'
    return subprocess.run(["bash", "-c", script, "bash", *cmd],
                          cwd=str(cwd or ROOT)).returncode


def build_bin_cmd(*, binary: Path, model_dir: Path, ar: Path, nar: Path,
                  scale: dict, threads: int,
                  requests: Path, run_dir: Path) -> list[str]:
    return [
        str(binary), "--task", "gen", "--family", "yue2",
        "--model", str(model_dir), "--backend", "cuda",
        "--threads", str(threads),
        "--session-option", "yue2.model_gguf=yue2-3b-bf16.gguf",
        "--session-option", "yue2.vae_gguf=yue2-vae-f16.gguf",
        "--session-option", f"yue2.ar_lora={ar}",
        "--session-option", f"yue2.ar_lora_scale={scale['ar']}",
        "--session-option", f"yue2.nar_lora={nar}",
        "--session-option", f"yue2.nar_lora_scale={scale['nar']}",
        "--session-option", "yue2.attention=flash",
        "--request-sequence", str(requests),
        "--out-dir", str(run_dir),
        "--log",
    ]


def run_batch(*, session_path: Path, session: dict, run_dir: Path,
              chunk_size: int, binary: Path, model_dir: Path,
              threads: int) -> int:
    requests_path = run_dir / "requests.json"
    proc = subprocess.run(
        [sys.executable, str(ROOT / "generate.py"), str(session_path),
         "--out-dir", str(run_dir), "--requests-out", str(requests_path)])
    if proc.returncode != 0:
        print(f"request resolution failed (exit {proc.returncode})")
        return proc.returncode
    requests = read_json(requests_path)
    if not isinstance(requests, list) or not requests:
        print(f"no requests written: {requests_path}")
        return 2
    manifest = read_json(run_dir / "batch_manifest.json") or {}
    tracks_by_id = {
        f"{t['name']}_{t['seed']}": t
        for t in manifest.get("tracks", [])
        if t.get("seed") is not None
    }
    ar, nar, alias, scale = resolve_session_loras(session, Path(session["base_dir"]))
    if not binary.is_file():
        print(f"binary missing: {binary}")
        return 2
    help_proc = subprocess.run(["bash", "-c",
                                f'. "{ROOT / "cuda_loader_path.sh"}" && '
                                f'"{binary}" --help'],
                               capture_output=True, text=True)
    help_text = (help_proc.stdout or "") + (help_proc.stderr or "")
    if "request-sequence" not in help_text:
        print("binary does not advertise --request-sequence; "
              "run again without --batch (per-track fallback)")
        return 2
    chunks = [requests] if chunk_size <= 0 else [
        requests[i:i + chunk_size] for i in range(0, len(requests), chunk_size)]
    print(f"batch: {len(requests)} request(s) in {len(chunks)} chunk(s)")
    stop = threading.Event()
    watcher = threading.Thread(
        target=marker_loop,
        args=(stop, run_dir, tracks_by_id, alias, scale),
        daemon=True)
    watcher.start()
    sizes: dict = {}
    results = []
    try:
        for i, chunk in enumerate(chunks, 1):
            chunk_path = run_dir / f"requests_chunk_{i:02d}.json"
            write_json_atomic(chunk_path, chunk)
            cmd = build_bin_cmd(binary=binary, model_dir=model_dir,
                                ar=ar, nar=nar, scale=scale,
                                threads=threads, requests=chunk_path,
                                run_dir=run_dir)
            print(f"chunk {i}/{len(chunks)}: {len(chunk)} request(s)")
            started = time.monotonic()
            rc = run_with_cuda(cmd)
            elapsed = time.monotonic() - started
            scan_wavs(run_dir, tracks_by_id, lora_alias=alias,
                      lora_scale=scale, sizes=sizes, final=True)
            print(f"chunk {i} exit={rc} wall={elapsed/60:.1f} min")
            results.append({"chunk": i, "requests": len(chunk),
                            "exit": rc, "wall_s": round(elapsed, 1)})
    finally:
        stop.set()
        watcher.join(timeout=10)
        scan_wavs(run_dir, tracks_by_id, lora_alias=alias,
                  lora_scale=scale, sizes=sizes, final=True)
    missing = [r["id"] for r in requests
               if not (run_dir / f"{r['id']}_time.txt").is_file()]
    summary = {
        "utc": utcnow(), "requests": len(requests),
        "marked": len(requests) - len(missing),
        "missing": missing, "chunks": results,
    }
    write_json_atomic(run_dir / "batch_run_summary.json", summary)
    if missing:
        print(f"incomplete: {len(missing)} request(s) have no marker")
        for name in missing[:10]:
            print(f"  {name}")
        return 1
    print(f"batch complete: {len(requests)}/{len(requests)} marked")
    return 0


def run_per_track(*, session_path: Path, run_dir: Path) -> int:
    cmd = [sys.executable, str(ROOT / "generate.py"), str(session_path),
           "--out-dir", str(run_dir)]
    print("per-track: generate.py (one process per song)")
    return subprocess.run(cmd).returncode


# --- main -------------------------------------------------------------------

def acquire_lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    fh = path.open("w")
    try:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        fh.close()
        return None
    fh.write(f"pid={os.getpid()} utc={utcnow()}\n")
    fh.flush()
    return fh


def print_status(corpus: dict, done: set[str], per_run: list[dict],
                 mismatches: list[dict], *, plan_only: bool = False) -> None:
    pending = [n for n in corpus["names"] if n not in done]
    print(f"corpus       {len(corpus['names'])}")
    print(f"gcs done     {len(done)}   ({len(per_run)} session runs)")
    print(f"pending      {len(pending)}")
    print(f"mismatches   {len(mismatches)}")
    if mismatches:
        for item in mismatches[:10]:
            print(f"  {item['run']}/{item['name']}: score hash mismatch")
    if plan_only:
        print("next pending:")
        for name in pending[:20]:
            print(f"  {name}")
        if len(pending) > 20:
            print(f"  ... and {len(pending) - 20} more")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    ap.add_argument("--runs", default=DEFAULT_RUNS,
                    help="GCS runs root (default: %(default)s)")
    ap.add_argument("--meta-dir", type=Path, default=None,
                    help="use an existing metadata tree instead of GCS")
    ap.add_argument("--work-dir", type=Path, default=DEFAULT_WORK)
    ap.add_argument("--out-root", type=Path, default=ROOT / "out")
    ap.add_argument("--label", default=DEFAULT_LABEL)
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--plan-only", action="store_true")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--prepare-only", action="store_true",
                    help="with --run, write the session manifest and exit "
                         "before any generation")
    ap.add_argument("--batch", action="store_true",
                    help="use audiocpp_cli --request-sequence instead of "
                         "one generate.py process per song")
    ap.add_argument("--batch-chunk", type=int, default=50,
                    help="requests per batch process; 0 = one process")
    ap.add_argument("--max-songs", type=int, default=None,
                    help="pilot only: cap the pending set")
    ap.add_argument("--threads", type=int, default=8)
    ap.add_argument("--binary", type=Path, default=ROOT / "bin" / "audiocpp_cli")
    ap.add_argument("--model-dir", type=Path,
                    default=ROOT / "models" / "Yue2-3B-GGUF")
    ap.add_argument("--fetch-corpus", action="store_true")
    ap.add_argument("--marker", type=Path, default=None,
                    help="completion marker (default: logs/yt500_gen_<utc>_done.txt)")
    args = ap.parse_args(argv)

    if args.fetch_corpus:
        rc = subprocess.run([sys.executable,
                             str(ROOT / "plumbing" / "yt500_generation_corpus.py"),
                             "--fetch"]).returncode
        if rc != 0:
            return rc

    corpus = load_corpus(args.corpus)
    meta_root = args.meta_dir or (args.work_dir / "meta")
    if args.meta_dir is None:
        print(f"reading metadata: {args.runs}")
        fetch_metadata(args.runs, meta_root)
    done, per_run, mismatches = scan_done(meta_root, corpus)

    if args.status or args.plan_only:
        print_status(corpus, done, per_run, mismatches,
                     plan_only=args.plan_only)
        return 0
    if not args.run:
        ap.error("choose --status, --plan-only or --run")

    lock = acquire_lock(args.work_dir / "run.lock")
    if lock is None:
        print("another generation driver holds the lock; nothing to do")
        return 2
    try:
        names = pending_names(corpus, done, args.max_songs)
        if not names:
            print("nothing pending: 489/489 done")
            return 0
        run_dir = pick_run_dir(args.out_root, args.label)
        run_dir.mkdir(parents=True)
        session_path = args.work_dir / f"session_{run_dir.name}.json"
        session = write_session_manifest(corpus, names, session_path)
        print(f"run dir      {run_dir}")
        print(f"session      {session_path}")
        print(f"pending      {len(names)}")
        if args.prepare_only:
            print("prepared only; no generation started")
            return 0
        if args.batch:
            rc = run_batch(session_path=session_path, session=session,
                           run_dir=run_dir, chunk_size=args.batch_chunk,
                           binary=args.binary, model_dir=args.model_dir,
                           threads=args.threads)
        else:
            rc = run_per_track(session_path=session_path, run_dir=run_dir)
        marker = args.marker or (ROOT / "logs" /
                                 f"yt500_gen_{run_dir.name}_done.txt")
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(f"exit={rc} {utcnow()} run_dir={run_dir}\n",
                          encoding="utf-8")
        print(f"done marker  {marker}")
        return rc
    finally:
        try:
            lock.close()
        except OSError:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
