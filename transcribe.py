#!/usr/bin/env python3
"""Transcribe generated takes to symbolic melody ABC with SheetSage2.

This is the ArabMaqamRock port of the parent project's `music-cover` tool.
It is intentionally independent of the audio.cpp generation stack:

  * auto device: uses the GPU when one is available, CPU otherwise
  * one model load, sequential tracks
  * resumable, with a source-WAV hash guard against stale ABCs
  * repo-relative paths; no `/content` and no mandatory GCS

Typical use:

    ./plumbing/setup_transcribe.sh          # once
    ./transcribe.sh out/latest --dry-run
    ./transcribe.sh out/latest --smoke
    ./transcribe.sh out/latest

Output defaults to `<run>/transcripts/<stem>/score.abc` plus the model's
side artifacts, a per-track `meta.json`, `_timings.csv`, and a run-level
`transcribe_manifest.json`.
"""
from __future__ import annotations

import argparse
import contextlib
import csv
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
import traceback
import wave
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable

ROOT = Path(__file__).resolve().parent
DEFAULT_MODEL = "m-a-p/SheetSage2"
DEFAULT_REVISION = "b83c3d79a6d98bcffaf8f9ed112c90aa887887bc"
DEFAULT_OUT_NAME = "transcripts"
TOOL_VERSION = "arabmaqamrock-transcribe/1"
AUDIO_EXTS = {".wav", ".mp3", ".flac", ".m4a", ".ogg", ".opus", ".aiff", ".aif", ".webm"}
FAILED_STATUSES = {"failed", "timeout", "no-abc", "invalid-abc", "stale", "invalid"}
DONE_STATUSES = {"ok", "skipped", "skipped-unverified"}


class PlanError(RuntimeError):
    """Invalid input, bad CLI use, or a failed preflight."""


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def is_audio(path: Path) -> bool:
    return path.suffix.lower() in AUDIO_EXTS


def sanitize_stem(name: str) -> str:
    """Keep Unicode and spaces; remove path separators and control chars."""
    cleaned = "".join(ch for ch in name if ch not in "/\\\0" and ord(ch) >= 32)
    cleaned = cleaned.strip().strip(".")
    return cleaned or "track"


def audio_duration(path: Path) -> float | None:
    if path.suffix.lower() == ".wav":
        try:
            with wave.open(str(path), "rb") as w:
                return w.getnframes() / float(w.getframerate())
        except Exception:  # noqa: BLE001 - fall through to ffprobe
            pass
    if shutil.which("ffprobe"):
        try:
            r = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=nk=1:nw=1", str(path)],
                capture_output=True, text=True, timeout=30)
            if r.returncode == 0 and r.stdout.strip():
                return float(r.stdout.strip())
        except (OSError, ValueError, subprocess.TimeoutExpired):
            pass
    return None


def read_pointer(path: Path) -> Path:
    """Resolve `out/latest`, which generate.py writes as a text path."""
    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise PlanError(f"cannot read input pointer {path}: {exc}") from exc
    if not text:
        raise PlanError(f"input pointer is empty: {path}")
    p = Path(text).expanduser()
    candidates = [p] if p.is_absolute() else [
        Path.cwd() / p,
        ROOT / p,
        path.parent / p,
    ]
    for cand in candidates:
        if cand.is_dir():
            return cand.resolve()
    raise PlanError(
        f"{path} points to a missing run: {text}\n"
        f"  generate a run first, or pass an explicit input directory")


def resolve_input_roots(words: list[str]) -> list[Path]:
    """Expand CLI inputs into a small list of run directories / audio files."""
    if not words:
        pointer = ROOT / "out" / "latest"
        if not pointer.is_file():
            raise PlanError(
                "no input given and out/latest does not exist\n"
                "  run generate.py first, or pass an input directory/WAV")
        return [read_pointer(pointer)]

    roots: list[Path] = []
    for word in words:
        p = Path(word).expanduser()
        if p.is_dir():
            roots.append(p.resolve())
        elif p.is_file():
            if is_audio(p):
                roots.append(p.resolve())
            else:
                # Allow `transcribe.py out/latest` explicitly.
                roots.append(read_pointer(p))
        else:
            raise PlanError(f"input not found: {p}")
    # Deduplicate roots.
    out: list[Path] = []
    seen: set[Path] = set()
    for p in roots:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def expand_tracks(roots: list[Path], recursive: bool,
                 exclude: re.Pattern[str] | None) -> list[Path]:
    files: list[Path] = []
    for root in roots:
        if root.is_dir():
            it: Iterable[Path] = root.rglob("*") if recursive else root.glob("*")
            files.extend(sorted(p for p in it if p.is_file() and is_audio(p)))
        else:
            files.append(root)
    seen: set[Path] = set()
    out: list[Path] = []
    for f in files:
        r = f.resolve()
        if r in seen:
            continue
        seen.add(r)
        if exclude is not None and exclude.search(f.stem):
            continue
        out.append(f)
    return out


def resolve_out_dir(roots: list[Path], explicit: str | None) -> Path:
    if explicit:
        return Path(explicit).expanduser().resolve()
    if len(roots) != 1:
        raise PlanError(
            "--out-dir is required when multiple inputs are given\n"
            "  (use one run directory, or pass an explicit output root)")
    root = roots[0]
    base = root if root.is_dir() else root.parent
    return (base / DEFAULT_OUT_NAME).resolve()


@dataclass
class Track:
    src: Path
    stem: str
    out_dir: Path
    abc: Path
    meta: Path
    status: str = "pending"
    seconds: float = 0.0
    error: str = ""
    source_sha256: str = ""
    source_bytes: int = 0
    duration_s: float | None = None
    abc_sha256: str = ""
    abc_bytes: int = 0


@dataclass
class Config:
    roots: list[Path]
    out_dir: Path
    model: str
    revision: str | None
    device: str
    dtype: str
    threads: int
    melody_only: bool
    limit: int
    force: bool
    verify: bool
    dry_run: bool
    doctor: bool
    fail_fast: bool
    time_budget: float
    per_track_timeout: float
    verbose: bool
    recursive: bool
    exclude: re.Pattern[str] | None
    on_collision: str
    cache_dir: Path | None = None


def build_tracks(files: list[Path], out_dir: Path, on_collision: str) -> list[Track]:
    tracks: list[Track] = []
    used: set[str] = set()
    for src in files:
        stem = sanitize_stem(src.stem)
        if stem in used:
            if on_collision == "error":
                other = next(t.src for t in tracks if t.stem == stem)
                raise PlanError(
                    f"duplicate output stem {stem!r}:\n"
                    f"  {other}\n  {src}\n"
                    f"  use --out-dir with a separate tree, or --on-collision suffix")
            base, n = stem, 1
            while stem in used:
                n += 1
                stem = f"{base}_{n}"
        used.add(stem)
        tdir = out_dir / stem
        tracks.append(Track(src=src, stem=stem, out_dir=tdir,
                            abc=tdir / "score.abc", meta=tdir / "meta.json"))
    return tracks


def abc_is_valid(path: Path) -> bool:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    if len(text.strip()) < 8:
        return False
    has_x = re.search(r"(?m)^\s*X\s*:", text) is not None
    has_k = re.search(r"(?m)^\s*K\s*:", text) is not None
    return has_x and has_k


def read_meta(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def existing_decision(track: Track) -> tuple[str, str]:
    """Return (action, reason): run | skip | unverified | stale | invalid."""
    if not track.abc.is_file() or track.abc.stat().st_size == 0:
        return "run", "no ABC"
    if not abc_is_valid(track.abc):
        return "invalid", "existing score.abc is not valid ABC"
    meta = read_meta(track.meta)
    if meta is None:
        return "unverified", "existing score.abc has no meta.json"
    if meta.get("status") != "ok":
        return "run", f"previous status was {meta.get('status')!r}"
    old = meta.get("source_wav_sha256")
    if not old:
        return "unverified", "meta.json has no source_wav_sha256"
    current = track.source_sha256 or sha256_file(track.src)
    if old != current:
        return "stale", (f"source WAV changed since transcription "
                         f"({str(old)[:12]}… != {current[:12]}…)")
    old_abc = meta.get("abc_sha256")
    if not old_abc:
        return "unverified", "meta.json has no abc_sha256"
    if old_abc != sha256_file(track.abc):
        return "invalid", "score.abc does not match meta.json abc_sha256"
    return "skip", "source WAV unchanged"


def find_abc(tdir: Path) -> Path | None:
    direct = tdir / "score.abc"
    if direct.is_file() and direct.stat().st_size > 0:
        return direct
    hits = sorted(tdir.rglob("*.abc"))
    return hits[0] if hits else None


def prepare_environment(cfg: Config) -> None:
    """Set isolated HF module cache before transformers is imported."""
    if "HF_MODULES_CACHE" not in os.environ:
        modules = ROOT / ".cache" / "hf_modules"
        modules.mkdir(parents=True, exist_ok=True)
        os.environ["HF_MODULES_CACHE"] = str(modules)
    if cfg.cache_dir is not None:
        cache = cfg.cache_dir.expanduser().resolve()
        cache.mkdir(parents=True, exist_ok=True)
        os.environ["HF_HOME"] = str(cache)


def native_bf16(torch) -> bool:
    """True only when the GPU does bf16 in hardware (T4 does not)."""
    try:
        return torch.cuda.is_bf16_supported(including_emulation=False)
    except TypeError:  # older torch without the keyword
        return torch.cuda.is_bf16_supported()


def load_model(cfg: Config):
    """Import torch/transformers and load SheetSage2. Kept out of dry-run."""
    import torch  # noqa: PLC0415
    import transformers  # noqa: PLC0415
    from transformers import AutoModel  # noqa: PLC0415

    torch.set_num_threads(cfg.threads)
    if cfg.device == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"
    elif cfg.device == "cuda":
        if not torch.cuda.is_available():
            raise PlanError(
                "--device cuda requested, but CUDA is not available in this env\n"
                "  rebuild/install the CUDA wheels (setup_transcribe.sh --cuda), "
                "or use --device cpu")
        device = "cuda"
    else:
        device = "cpu"

    # SheetSage2 defaults to bf16 autocast on CUDA. Turing-class GPUs (T4)
    # only emulate bf16, which is slow and can raise in some kernels, so fall
    # back to fp32 there. dtype is inert on CPU (autocast is disabled).
    if cfg.dtype != "auto":
        dtype = cfg.dtype
    elif device == "cuda":
        dtype = "bf16" if native_bf16(torch) else "fp32"
    else:
        dtype = "fp32"

    t0 = time.monotonic()
    kwargs = {"trust_remote_code": True}
    if cfg.revision:
        kwargs["revision"] = cfg.revision
    model = AutoModel.from_pretrained(cfg.model, **kwargs).eval()
    model = model.to(device)
    if device == "cpu":
        model = model.float()
    runtime = {
        "python": sys.version.split()[0],
        "torch": torch.__version__,
        "transformers": transformers.__version__,
        "device": device,
        "dtype": dtype,
        "gpu": (torch.cuda.get_device_name(0) if device == "cuda" else None),
        "threads": cfg.threads,
        "load_seconds": round(time.monotonic() - t0, 1),
    }
    return model, runtime


@contextlib.contextmanager
def time_limit(seconds: float):
    if not seconds or not hasattr(signal, "SIGALRM"):
        yield
        return

    def _handler(signum, frame):  # noqa: ARG001
        raise TimeoutError(f"per-track timeout after {seconds:g}s")

    old = signal.signal(signal.SIGALRM, _handler)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)


def write_meta(track: Track, cfg: Config, runtime: dict, *,
               status: str, error: str = "") -> None:
    meta = {
        "tool": TOOL_VERSION,
        "created_utc": utcnow(),
        "status": status,
        "source_wav": str(track.src),
        "source_wav_sha256": track.source_sha256,
        "source_wav_bytes": track.source_bytes,
        "duration_s": (round(track.duration_s, 3)
                       if track.duration_s is not None else None),
        "model": cfg.model,
        "model_revision": cfg.revision,
        "melody_only": cfg.melody_only,
        "device": runtime.get("device"),
        "dtype": runtime.get("dtype"),
        "threads": runtime.get("threads"),
        "python": runtime.get("python"),
        "torch": runtime.get("torch"),
        "transformers": runtime.get("transformers"),
        "seconds": round(track.seconds, 1) if track.seconds else None,
        "abc": "score.abc" if status == "ok" and track.abc.is_file() else None,
        "abc_sha256": track.abc_sha256 or None,
        "abc_bytes": track.abc_bytes or 0,
    }
    if error:
        meta["error"] = error
    track.meta.parent.mkdir(parents=True, exist_ok=True)
    track.meta.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def transcribe_track(model, track: Track, cfg: Config, runtime: dict,
                     emit: Callable[[str], None]) -> None:
    track.source_sha256 = sha256_file(track.src)
    track.source_bytes = track.src.stat().st_size
    track.duration_s = audio_duration(track.src)
    track.out_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.monotonic()
    try:
        with time_limit(cfg.per_track_timeout):
            result = model.transcribe(
                str(track.src), output_dir=str(track.out_dir),
                melody_only=cfg.melody_only,
                dtype=runtime.get("dtype", "bf16"))
    except Exception as exc:  # noqa: BLE001 - one bad track must not kill the batch
        track.seconds = time.monotonic() - t0
        track.status = "timeout" if isinstance(exc, TimeoutError) else "failed"
        track.error = f"{type(exc).__name__}: {exc}"
        if cfg.verbose:
            emit(traceback.format_exc().rstrip())
        write_meta(track, cfg, runtime, status=track.status, error=track.error)
        return

    track.seconds = time.monotonic() - t0
    abc = find_abc(track.out_dir)
    if abc is None and isinstance(result, dict) and result.get("abc"):
        track.abc.write_text(result["abc"], encoding="utf-8")
        abc = track.abc
    if abc is None:
        track.status = "no-abc"
        track.error = "SheetSage2 produced no .abc file"
        write_meta(track, cfg, runtime, status=track.status, error=track.error)
        return
    if abc != track.abc:
        shutil.copy2(abc, track.abc)
    if not abc_is_valid(track.abc):
        track.status = "invalid-abc"
        track.error = "produced score.abc does not look like ABC"
        write_meta(track, cfg, runtime, status=track.status, error=track.error)
        return

    # The source is supposed to be immutable while we work. Verify rather than
    # trusting a hash taken minutes ago.
    if sha256_file(track.src) != track.source_sha256:
        track.status = "failed"
        track.error = "source WAV changed during transcription"
        write_meta(track, cfg, runtime, status=track.status, error=track.error)
        return

    track.abc_sha256 = sha256_file(track.abc)
    track.abc_bytes = track.abc.stat().st_size
    track.status = "ok"
    write_meta(track, cfg, runtime, status="ok")


def write_outputs(cfg: Config, tracks: list[Track], runtime: dict,
                  elapsed_s: float, stopped_early: bool) -> None:
    out = cfg.out_dir
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "_timings.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["stem", "source", "seconds", "status", "abc_bytes",
                    "abc_sha256", "error"])
        for t in tracks:
            w.writerow([t.stem, str(t.src), f"{t.seconds:.1f}", t.status,
                        t.abc_bytes, t.abc_sha256, t.error])

    parents = {t.src.parent for t in tracks}
    source_run = next(iter(parents)) if len(parents) == 1 else None
    batch_manifest = source_run / "batch_manifest.json" if source_run else None
    batch_sha = (sha256_file(batch_manifest)
                 if batch_manifest and batch_manifest.is_file() else None)

    manifest = {
        "tool": TOOL_VERSION,
        "created_utc": utcnow(),
        "source_run": str(source_run) if source_run else None,
        "batch_manifest": str(batch_manifest) if batch_manifest and batch_manifest.is_file() else None,
        "batch_manifest_sha256": batch_sha,
        "out_dir": str(out),
        "model": cfg.model,
        "model_revision": cfg.revision,
        "melody_only": cfg.melody_only,
        "python": runtime.get("python"),
        "torch": runtime.get("torch"),
        "transformers": runtime.get("transformers"),
        "device": runtime.get("device"),
        "dtype": runtime.get("dtype"),
        "threads": runtime.get("threads"),
        "elapsed_s": round(elapsed_s, 1),
        "stopped_early": stopped_early,
        "n": len(tracks),
        "n_ok": sum(1 for t in tracks if t.status in DONE_STATUSES),
        "n_failed": sum(1 for t in tracks if t.status in FAILED_STATUSES),
        "tracks": [{
            "stem": t.stem,
            "source": str(t.src),
            "source_wav_sha256": t.source_sha256 or None,
            "status": t.status,
            "seconds": round(t.seconds, 1),
            "abc": (str(t.abc) if t.status in DONE_STATUSES and t.abc.is_file()
                    else None),
            "abc_sha256": t.abc_sha256 or None,
            "abc_bytes": t.abc_bytes,
            "error": t.error or None,
        } for t in tracks],
    }
    (out / "transcribe_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")


class Emitter:
    def __init__(self, log_path: Path | None):
        self.fh = (open(log_path, "a", encoding="utf-8")
                   if log_path is not None else None)

    def __call__(self, line: str) -> None:
        print(line, flush=True)
        if self.fh is not None:
            self.fh.write(line + "\n")
            self.fh.flush()

    def close(self) -> None:
        if self.fh is not None:
            self.fh.close()
            self.fh = None


def print_plan(cfg: Config, tracks: list[Track]) -> None:
    print(f"model   : {cfg.model}  revision={cfg.revision or '(default)'}")
    print(f"input   : {len(tracks)} track(s)")
    print(f"out-dir : {cfg.out_dir}")
    print(f"device  : {cfg.device}  dtype={cfg.dtype}  threads={cfg.threads}  "
          f"melody_only={cfg.melody_only}")
    for i, t in enumerate(tracks, 1):
        print(f"  {i:>3}  {t.src.name}")
        print(f"        -> {t.out_dir}")


def verify(cfg: Config, tracks: list[Track]) -> int:
    bad = 0
    for t in tracks:
        if not t.abc.is_file() or t.abc.stat().st_size == 0:
            print(f"[MISSING] {t.stem}: no score.abc")
            bad += 1
            continue
        if not abc_is_valid(t.abc):
            print(f"[INVALID] {t.stem}: score.abc is not valid ABC")
            bad += 1
            continue
        meta = read_meta(t.meta)
        if meta is None or not meta.get("source_wav_sha256"):
            print(f"[UNVERIFIED] {t.stem}: no meta.json source hash")
            bad += 1
            continue
        if meta.get("status") != "ok":
            print(f"[FAILED] {t.stem}: meta.json status is {meta.get('status')!r}")
            bad += 1
            continue
        current = sha256_file(t.src)
        if meta["source_wav_sha256"] != current:
            print(f"[STALE] {t.stem}: source WAV changed "
                  f"({str(meta['source_wav_sha256'])[:12]}… != {current[:12]}…)")
            bad += 1
            continue
        if not meta.get("abc_sha256"):
            print(f"[UNVERIFIED] {t.stem}: meta.json has no abc_sha256")
            bad += 1
            continue
        if meta["abc_sha256"] != sha256_file(t.abc):
            print(f"[CHANGED] {t.stem}: score.abc does not match meta.json")
            bad += 1
            continue
        print(f"[OK] {t.stem}")
    print(f"verify: {len(tracks) - bad}/{len(tracks)} ok")
    return 0 if bad == 0 else 1


def doctor(cfg: Config) -> int:
    print(f"tool      : {TOOL_VERSION}")
    print(f"python    : {sys.version.split()[0]}  ({sys.executable})")
    print(f"cwd       : {Path.cwd()}")
    print(f"model     : {cfg.model}  revision={cfg.revision or '(default)'}")
    print(f"device    : {cfg.device}  dtype={cfg.dtype}  threads={cfg.threads}")
    print(f"hf modules: {os.environ.get('HF_MODULES_CACHE', '(unset)')}")
    print(f"hf home   : {os.environ.get('HF_HOME', '(default)')}")
    ffmpeg = shutil.which("ffmpeg")
    print(f"ffmpeg    : {ffmpeg or 'MISSING'}")
    if ffmpeg:
        try:
            r = subprocess.run([ffmpeg, "-version"], capture_output=True,
                               text=True, timeout=10)
            if r.returncode == 0 and r.stdout:
                print(f"           {r.stdout.splitlines()[0]}")
        except (OSError, subprocess.TimeoutExpired):
            pass
    ok = True
    versions = {}
    for name in ("torch", "transformers", "huggingface_hub"):
        try:
            mod = __import__(name)
            versions[name] = getattr(mod, "__version__", "?")
            print(f"{name:<10}: {versions[name]}")
        except Exception as exc:  # noqa: BLE001
            print(f"{name:<10}: IMPORT FAIL ({exc})")
            ok = False
    if sys.version_info[:2] not in ((3, 10), (3, 11)):
        print(f"WARNING   : SheetSage2 expects Python 3.10/3.11; "
              f"this is {sys.version.split()[0]}")
        ok = False
    if versions.get("torch", "").split("+")[0] != "2.8.0":
        print("WARNING   : expected torch==2.8.0 "
              f"(got {versions.get('torch', '?')})")
        ok = False
    if versions.get("transformers") != "4.45.2":
        print("WARNING   : expected transformers==4.45.2 "
              f"(got {versions.get('transformers', '?')})")
        ok = False
    try:
        import torch  # noqa: PLC0415
        cuda = torch.cuda.is_available()
        print(f"cuda      : {cuda}")
        if cuda:
            print(f"gpu       : {torch.cuda.get_device_name(0)}")
            if cfg.dtype == "auto":
                dtype = "bf16" if native_bf16(torch) else "fp32"
            else:
                dtype = cfg.dtype
            print(f"dtype     : {dtype}")
    except Exception:  # noqa: BLE001
        pass
    return 0 if ok and ffmpeg else 1


def run(cfg: Config, tracks: list[Track]) -> int:
    cfg.out_dir.mkdir(parents=True, exist_ok=True)
    emit = Emitter(cfg.out_dir / "_driver.log")
    try:
        prepare_environment(cfg)
        emit(f"== {TOOL_VERSION} ==")
        emit(f"start {utcnow()}  n={len(tracks)}  out={cfg.out_dir}")
        emit(f"model {cfg.model}  revision={cfg.revision or '(default)'}  "
             f"device={cfg.device}  threads={cfg.threads}")
        try:
            model, runtime = load_model(cfg)
        except Exception as exc:  # noqa: BLE001
            emit(f"[error] model load failed: {type(exc).__name__}: {exc}")
            if cfg.verbose:
                emit(traceback.format_exc().rstrip())
            return 1
        emit(f"model loaded in {runtime['load_seconds']}s  "
             f"torch={runtime['torch']}  transformers={runtime['transformers']}  "
             f"device={runtime['device']}  dtype={runtime['dtype']}" +
             (f"  gpu={runtime['gpu']}" if runtime.get("gpu") else ""))
        t0 = time.monotonic()
        stopped_early = False
        for i, t in enumerate(tracks, 1):
            if cfg.time_budget and i > 1 and (time.monotonic() - t0) >= cfg.time_budget:
                stopped_early = True
                emit(f"budget {cfg.time_budget:g}s reached after {i - 1} track(s); "
                     f"stopping before {t.stem}")
                break

            if cfg.force:
                action, reason = "run", "--force"
            else:
                t.source_sha256 = t.source_sha256 or sha256_file(t.src)
                t.source_bytes = t.src.stat().st_size
                action, reason = existing_decision(t)
            if action == "skip":
                t.status = "skipped"
                t.abc_bytes = t.abc.stat().st_size
                t.abc_sha256 = sha256_file(t.abc)
                emit(f"[{i}/{len(tracks)}] {t.stem}  skipped ({reason})")
            elif action == "unverified":
                t.status = "skipped-unverified"
                t.abc_bytes = t.abc.stat().st_size
                t.abc_sha256 = sha256_file(t.abc)
                emit(f"[{i}/{len(tracks)}] {t.stem}  skipped-unverified ({reason}; "
                     f"re-run with --force to redo)")
            elif action in ("stale", "invalid"):
                t.status = action
                t.error = reason
                emit(f"[{i}/{len(tracks)}] {t.stem}  {action.upper()}: {reason}")
            else:
                emit(f"[{i}/{len(tracks)}] {t.stem}  transcribing…")
                transcribe_track(model, t, cfg, runtime, emit)
                note = f"  abc={t.abc_bytes}B" if t.abc_bytes else ""
                emit(f"[{i}/{len(tracks)}] {t.stem}  {t.seconds:.1f}s  "
                     f"{t.status}{note}" +
                     (f"  ({t.error})" if t.error else ""))

            if t.status in FAILED_STATUSES and cfg.fail_fast:
                emit(f"stopping on first failure: {t.stem}")
                break

        elapsed = time.monotonic() - t0
        write_outputs(cfg, tracks, runtime, elapsed, stopped_early)
        n_ok = sum(1 for t in tracks if t.status in DONE_STATUSES)
        n_failed = sum(1 for t in tracks if t.status in FAILED_STATUSES)
        emit(f"done {utcnow()}  ok={n_ok}/{len(tracks)}  failed={n_failed}  "
             f"elapsed={elapsed:.1f}s")
        return 1 if n_failed else 0
    finally:
        emit.close()


def parse_args(argv: list[str] | None = None) -> tuple[Config, list[Track]]:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("inputs", nargs="*",
                    help="WAV/audio files or run directories (default: out/latest)")
    ap.add_argument("--out-dir", default=None,
                    help="output root (default: <input>/transcripts)")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--revision",
                    default=os.environ.get("SHEETSAGE2_REVISION", DEFAULT_REVISION))
    ap.add_argument("--device", choices=["cpu", "cuda", "auto"], default="auto",
                    help="inference device (default: auto -- GPU if available)")
    ap.add_argument("--dtype", choices=["auto", "bf16", "fp32"], default="auto",
                    help="CUDA compute dtype (default: auto -- bf16 on native "
                         "bf16 GPUs, fp32 elsewhere, e.g. T4)")
    ap.add_argument("--threads", type=int,
                    default=min(4, os.cpu_count() or 1),
                    help="torch CPU threads (default: min(4, CPU count))")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--melody-only", dest="melody_only", action="store_true",
                   default=True, help="omit chord symbols (default)")
    g.add_argument("--full", dest="melody_only", action="store_false",
                   help="full SheetSage2 transcription (melody + chords)")
    ap.add_argument("--recursive", action="store_true",
                    help="recurse into input directories")
    ap.add_argument("--exclude", default=None, metavar="REGEX",
                    help="skip stems matching REGEX (no default exclusion)")
    ap.add_argument("--limit", type=int, default=0, help="0 = all")
    ap.add_argument("--smoke", action="store_true",
                    help="process at most one track, then stop")
    ap.add_argument("--on-collision", choices=["error", "suffix"], default="error")
    ap.add_argument("--force", action="store_true",
                    help="re-transcribe even if a valid ABC exists")
    ap.add_argument("--verify", action="store_true",
                    help="re-check hashes only; never load the model")
    ap.add_argument("--fail-fast", action="store_true",
                    help="stop at the first failed track")
    ap.add_argument("--time-budget", type=float, default=0.0,
                    help="stop starting new tracks after this many seconds (0 = off)")
    ap.add_argument("--per-track-timeout", type=float, default=0.0,
                    help="best-effort per-track timeout in seconds (0 = off)")
    ap.add_argument("--dry-run", action="store_true",
                    help="plan only; no torch import, no writes")
    ap.add_argument("--doctor", action="store_true",
                    help="print environment diagnostics and exit")
    ap.add_argument("--cache-dir", default=None,
                    help="HF_HOME for the model cache (default: ~/.cache/huggingface)")
    ap.add_argument("--verbose", action="store_true",
                    help="log full tracebacks")
    ap.add_argument("--version", action="version", version=TOOL_VERSION)
    args = ap.parse_args(argv)

    if args.limit < 0:
        raise PlanError("--limit must be >= 0")
    if args.threads <= 0:
        raise PlanError("--threads must be > 0")
    if args.time_budget < 0 or args.per_track_timeout < 0:
        raise PlanError("timeouts must be >= 0")
    try:
        exclude = re.compile(args.exclude) if args.exclude else None
    except re.error as exc:
        raise PlanError(f"invalid --exclude regex: {exc}") from exc

    if args.doctor:
        # Doctor must work before any run exists; do not require out/latest.
        roots: list[Path] = []
        out_dir = (Path(args.out_dir).expanduser().resolve()
                   if args.out_dir else (ROOT / "out" / DEFAULT_OUT_NAME))
        tracks: list[Track] = []
    else:
        roots = resolve_input_roots(args.inputs)
        out_dir = resolve_out_dir(roots, args.out_dir)
        files = expand_tracks(roots, args.recursive, exclude)
        if not files:
            raise PlanError(f"no audio files found under {', '.join(map(str, roots))}")
        if args.smoke:
            files = files[:1]
        if args.limit:
            files = files[:args.limit]
        tracks = build_tracks(files, out_dir, args.on_collision)

    return Config(
        roots=roots, out_dir=out_dir, model=args.model,
        revision=args.revision or None, device=args.device,
        dtype=args.dtype,
        threads=args.threads, melody_only=args.melody_only,
        limit=args.limit, force=args.force, verify=args.verify,
        dry_run=args.dry_run, doctor=args.doctor, fail_fast=args.fail_fast,
        time_budget=args.time_budget, per_track_timeout=args.per_track_timeout,
        verbose=args.verbose, recursive=args.recursive, exclude=exclude,
        on_collision=args.on_collision,
        cache_dir=Path(args.cache_dir) if args.cache_dir else None,
    ), tracks


def main(argv: list[str] | None = None) -> int:
    try:
        cfg, tracks = parse_args(argv)
        if cfg.doctor:
            prepare_environment(cfg)
            return doctor(cfg)
        if cfg.dry_run:
            print_plan(cfg, tracks)
            return 0
        if cfg.verify:
            return verify(cfg, tracks)
        return run(cfg, tracks)
    except PlanError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\n[interrupted]", file=sys.stderr)
        return 130
    except Exception as exc:  # noqa: BLE001
        print(f"[error] {type(exc).__name__}: {exc}", file=sys.stderr)
        if "-v" in (argv or sys.argv) or "--verbose" in (argv or sys.argv):
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
