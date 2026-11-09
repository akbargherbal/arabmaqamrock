#!/usr/bin/env python3
"""Export finished WAV takes as MP3 for GCS upload.

Generation stays WAV by design.  This module is the upload layer's audio
formatter: it finds finished takes, keeps a local MP3 cache *outside* the run
directory (so ``transcribe.py`` never discovers duplicate audio), and verifies
each MP3 before it can replace anything.

The cache layout is::

    .cache/gcs_mp3/<run-key>/<take>.mp3
    .cache/gcs_mp3/_index/<run-key>.json

Only the per-run directory is synced to GCS; the index stays local.

Typical use is through ``plumbing/backup_to_gcp.py``.  For inspection::

    python plumbing/audio_export.py out/<run> --dry-run
    python plumbing/audio_export.py out/<run> --bitrate 128k
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import wave
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CACHE = REPO_ROOT / ".cache" / "gcs_mp3"
DEFAULT_BITRATE = "192k"
POLICY_NAME = "UPLOAD_POLICY.json"
POLICY_MP3 = "mp3"
POLICY_WAV = "wav"
_BITRATE_RE = re.compile(r"^\d+[kK]$")

_LOG = logging.getLogger("audio_export")


class AudioExportError(RuntimeError):
    """A WAV could not be exported to MP3."""


class PolicyError(AudioExportError):
    """UPLOAD_POLICY.json is malformed."""


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            block = f.read(chunk)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def _log(logger: logging.Logger | None, level: str, msg: str, *args) -> None:
    (logger or _LOG).__getattribute__(level)(msg, *args)


def _write_json_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    os.replace(tmp, path)


def _read_json(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


# --- policy ----------------------------------------------------------------

@dataclass(frozen=True)
class UploadPolicy:
    """How a run's audio should be stored in GCS.

    ``audio="mp3"`` (the default): upload MP3 for every take.
    ``audio="wav"``: upload WAV for ``takes`` (all takes when empty) and MP3
    for the rest.
    """

    audio: str = POLICY_MP3
    takes: tuple[str, ...] = ()
    reason: str | None = None
    source: str = "default"

    @property
    def is_wav(self) -> bool:
        return self.audio == POLICY_WAV


def read_policy(run_dir: Path) -> UploadPolicy:
    """Read ``UPLOAD_POLICY.json``; a missing file means the MP3 trial policy."""
    path = run_dir / POLICY_NAME
    if not path.is_file():
        return UploadPolicy()
    data = _read_json(path)
    if data is None:
        raise PolicyError(f"{path}: not valid JSON")
    audio = data.get("audio", POLICY_MP3)
    if audio not in (POLICY_MP3, POLICY_WAV):
        raise PolicyError(f"{path}: 'audio' must be {POLICY_MP3!r} or {POLICY_WAV!r}")
    takes = data.get("takes", [])
    if takes is None:
        takes = []
    if not isinstance(takes, list) or any(
            not isinstance(t, str) or not t.strip() for t in takes):
        raise PolicyError(f"{path}: 'takes' must be a list of non-empty strings")
    reason = data.get("reason")
    if reason is not None and not isinstance(reason, str):
        raise PolicyError(f"{path}: 'reason' must be a string")
    return UploadPolicy(
        audio=audio,
        takes=tuple(t.strip() for t in takes),
        reason=reason,
        source=str(path),
    )


def write_policy(run_dir: Path, audio: str, takes=(), reason: str | None = None) -> Path:
    """Write ``UPLOAD_POLICY.json`` (used by ``mark_production.py``)."""
    if audio not in (POLICY_MP3, POLICY_WAV):
        raise PolicyError(f"audio must be {POLICY_MP3!r} or {POLICY_WAV!r}")
    takes_list = [str(t).strip() for t in takes if str(t).strip()]
    path = run_dir / POLICY_NAME
    _write_json_atomic(path, {
        "audio": audio,
        "takes": takes_list,
        "reason": reason,
        "marked_utc": utcnow(),
    })
    return path


def validate_bitrate(value: str) -> str:
    if not _BITRATE_RE.match(value or ""):
        raise AudioExportError(
            f"invalid MP3 bitrate {value!r}; use a value like '128k' or '192k'")
    return value


# --- take discovery --------------------------------------------------------

def _time_file(wav: Path) -> Path:
    return wav.with_name(f"{wav.stem}_time.txt")


def is_finished_take(wav: Path) -> tuple[bool, str]:
    """True only when the runner recorded a successful exit for this WAV."""
    try:
        if wav.stat().st_size <= 0:
            return False, "empty WAV"
    except OSError:
        return False, "missing WAV"
    tf = _time_file(wav)
    try:
        text = tf.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False, f"no {tf.name}"
    if "Exit status: 0" not in text:
        return False, f"{tf.name} does not say 'Exit status: 0'"
    return True, "ok"


def find_wavs(run_dir: Path) -> list[Path]:
    """Top-level WAVs only, matching transcribe.py's non-recursive discovery."""
    if not run_dir.is_dir():
        return []
    return sorted(p for p in run_dir.glob("*")
                  if p.is_file() and p.suffix.lower() == ".wav")


# --- MP3 cache -------------------------------------------------------------

def run_key(run_dir: Path) -> str:
    digest = hashlib.sha256(str(run_dir.resolve()).encode("utf-8")).hexdigest()[:8]
    safe = re.sub(r"[^A-Za-z0-9._-]+", "-", run_dir.name).strip("-") or "run"
    return f"{safe}-{digest}"


def cache_run_dir(cache_root: Path, run_dir: Path) -> Path:
    return cache_root / run_key(run_dir)


def mp3_cache_path(cache_root: Path, run_dir: Path, wav: Path) -> Path:
    rel = wav.relative_to(run_dir)
    return cache_run_dir(cache_root, run_dir) / rel.with_suffix(".mp3")


def cache_index_path(cache_root: Path, run_dir: Path) -> Path:
    return cache_root / "_index" / f"{run_key(run_dir)}.json"


def _new_index(cache_root: Path, run_dir: Path, bitrate: str) -> dict:
    return {
        "version": 1,
        "run_dir": str(run_dir.resolve()),
        "bitrate": bitrate,
        "takes": {},
    }


def _load_index(cache_root: Path, run_dir: Path, bitrate: str) -> dict:
    data = _read_json(cache_index_path(cache_root, run_dir))
    if (not data
            or data.get("run_dir") != str(run_dir.resolve())
            or data.get("bitrate") != bitrate
            or not isinstance(data.get("takes"), dict)):
        return _new_index(cache_root, run_dir, bitrate)
    return data


def probe_duration(path: Path) -> float | None:
    """WAV duration from the header, anything else via ffprobe."""
    if path.suffix.lower() == ".wav":
        try:
            with wave.open(str(path), "rb") as w:
                return w.getnframes() / float(w.getframerate())
        except Exception:  # noqa: BLE001 - fall through to ffprobe
            pass
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return None
    try:
        result = subprocess.run(
            [ffprobe, "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nk=1:nw=1", str(path)],
            capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0 or not result.stdout.strip():
        return None
    try:
        return float(result.stdout.strip())
    except ValueError:
        return None


def _require_tool(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise AudioExportError(f"{name} not found on PATH")
    return path


def _run_command(cmd: list[str], *, timeout: float = 600.0) -> None:
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()[-2000:]
        raise AudioExportError(
            f"{Path(cmd[0]).name} failed (exit {result.returncode}): {detail}")


@dataclass
class Mp3Result:
    wav: Path
    mp3: Path | None
    status: str  # created | cached | planned | skipped | failed
    reason: str = ""
    source_sha256: str | None = None
    mp3_sha256: str | None = None
    duration_s: float | None = None


def ensure_mp3(run_dir: Path, wav: Path, cache_root: Path,
               bitrate: str = DEFAULT_BITRATE, *, force: bool = False,
               dry_run: bool = False,
               logger: logging.Logger | None = None) -> Mp3Result:
    """Return a verified MP3 for ``wav``, encoding it on a cache miss.

    The MP3 is written through ``.tmp`` and only renamed after the duration
    and a full decode check pass.  A cached MP3 is reused when the source hash,
    size, mtime, and bitrate still match.
    """
    bitrate = validate_bitrate(bitrate)
    wav_stat = wav.stat()
    index = _load_index(cache_root, run_dir, bitrate)
    entry = index["takes"].get(wav.name)
    # Avoid hashing a large unchanged WAV on every 5-minute pass.
    if (not force and isinstance(entry, dict)
            and entry.get("source_bytes") == wav_stat.st_size
            and entry.get("source_mtime_ns") == wav_stat.st_mtime_ns
            and entry.get("source_sha256")
            and entry.get("bitrate") == bitrate):
        source_sha = entry["source_sha256"]
    else:
        source_sha = sha256_file(wav)
    mp3 = mp3_cache_path(cache_root, run_dir, wav)

    if not force and isinstance(entry, dict):
        try:
            same = (entry.get("source_sha256") == source_sha
                    and entry.get("bitrate") == bitrate
                    and mp3.is_file()
                    and mp3.stat().st_size == entry.get("mp3_bytes")
                    and mp3.stat().st_mtime_ns == entry.get("mp3_mtime_ns"))
        except OSError:
            same = False
        if same:
            _log(logger, "info", "mp3 cached: %s", mp3)
            return Mp3Result(wav, mp3, "cached", "source unchanged",
                             source_sha, entry.get("mp3_sha256"),
                             entry.get("duration_s"))

    if dry_run:
        _log(logger, "info", "would encode mp3: %s -> %s", wav.name, mp3)
        return Mp3Result(wav, mp3, "planned", "cache miss", source_sha)

    ffmpeg = _require_tool("ffmpeg")
    _require_tool("ffprobe")
    mp3.parent.mkdir(parents=True, exist_ok=True)
    tmp = mp3.with_name(mp3.name + ".tmp")
    try:
        _run_command([
            ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
            "-i", str(wav), "-map_metadata", "0", "-c:a", "libmp3lame",
            "-b:a", bitrate, "-id3v2_version", "3", "-f", "mp3", str(tmp),
        ])
        if not tmp.is_file() or tmp.stat().st_size <= 0:
            raise AudioExportError(f"ffmpeg wrote no MP3 for {wav.name}")
        # Full decode check on the temp file (the .tmp suffix hides the format).
        _run_command([ffmpeg, "-nostdin", "-hide_banner", "-v", "error",
                      "-f", "mp3", "-i", str(tmp), "-f", "null", "-"])
        if wav_stat.st_size > 1_000_000 and tmp.stat().st_size >= wav_stat.st_size:
            raise AudioExportError(
                f"MP3 is not smaller than the WAV for {wav.name} "
                f"({tmp.stat().st_size} >= {wav_stat.st_size})")
        os.replace(tmp, mp3)

    finally:
        if tmp.exists():
            tmp.unlink()

    wav_dur = probe_duration(wav)
    mp3_dur = probe_duration(mp3)
    if wav_dur is not None and mp3_dur is not None:
        tolerance = max(0.25, min(0.5, wav_dur * 0.005))
        if abs(wav_dur - mp3_dur) > tolerance:
            mp3.unlink(missing_ok=True)
            raise AudioExportError(
                f"MP3 duration {mp3_dur:.3f}s differs from WAV "
                f"{wav_dur:.3f}s by more than {tolerance:.2f}s")

    mp3_sha = sha256_file(mp3)
    mp3_stat = mp3.stat()
    index["takes"][wav.name] = {
        "source_sha256": source_sha,
        "source_bytes": wav_stat.st_size,
        "source_mtime_ns": wav_stat.st_mtime_ns,
        "mp3_sha256": mp3_sha,
        "mp3_bytes": mp3_stat.st_size,
        "mp3_mtime_ns": mp3_stat.st_mtime_ns,
        "bitrate": bitrate,
        "duration_s": mp3_dur,
        "created_utc": utcnow(),
    }
    _write_json_atomic(cache_index_path(cache_root, run_dir), index)
    _log(logger, "info", "mp3 created: %s (%.1f MB)", mp3,
         mp3_stat.st_size / 1_000_000)
    return Mp3Result(wav, mp3, "created", "encoded", source_sha, mp3_sha,
                     mp3_dur)


# --- per-run export --------------------------------------------------------

@dataclass
class ExportReport:
    run_dir: Path
    policy: UploadPolicy
    mp3s: list[Path] = field(default_factory=list)
    wavs: list[Path] = field(default_factory=list)
    fallbacks: list[Path] = field(default_factory=list)
    skipped: list[tuple[Path, str]] = field(default_factory=list)
    results: list[Mp3Result] = field(default_factory=list)
    errors: list[tuple[Path, str]] = field(default_factory=list)
    missing_selected: list[str] = field(default_factory=list)

    def summary(self) -> str:
        return (f"policy={self.policy.audio}"
                f"{' takes=' + ','.join(self.policy.takes) if self.policy.takes else ''} "
                f"mp3={len(self.mp3s)} wav={len(self.wavs)} "
                f"fallback={len(self.fallbacks)} skipped={len(self.skipped)} "
                f"errors={len(self.errors)}")


def export_run(run_dir: Path, cache_root: Path, *,
               bitrate: str = DEFAULT_BITRATE,
               require_finished: bool = True,
               force: bool = False,
               dry_run: bool = False,
               logger: logging.Logger | None = None) -> ExportReport:
    """Decide and prepare the audio upload for one run directory."""
    policy = read_policy(run_dir)
    report = ExportReport(run_dir=run_dir, policy=policy)
    wavs = find_wavs(run_dir)
    by_stem = {w.stem: w for w in wavs}

    if policy.is_wav:
        selected = set(policy.takes) if policy.takes else set(by_stem)
        wav_targets = [w for w in wavs if w.stem in selected]
        mp3_targets = [w for w in wavs if w.stem not in selected]
        report.missing_selected = sorted(selected - set(by_stem))
    else:
        wav_targets = []
        mp3_targets = list(wavs)
        if policy.takes:
            _log(logger, "warning",
                 "%s: 'takes' is ignored while audio=%s", POLICY_NAME, policy.audio)

    for wav in mp3_targets:
        finished, reason = (is_finished_take(wav) if require_finished
                            else (wav.is_file() and wav.stat().st_size > 0,
                                  "exists" if wav.is_file() else "missing WAV"))
        if not finished:
            report.skipped.append((wav, reason))
            _log(logger, "info", "skip %s: %s", wav.name, reason)
            continue
        try:
            result = ensure_mp3(run_dir, wav, cache_root, bitrate,
                                force=force, dry_run=dry_run, logger=logger)
        except Exception as exc:  # noqa: BLE001 - fall back to the WAV
            report.errors.append((wav, str(exc)))
            report.fallbacks.append(wav)
            report.results.append(Mp3Result(wav, None, "failed", str(exc)))
            _log(logger, "error", "mp3 failed for %s: %s; WAV will be uploaded",
                 wav.name, exc)
            continue
        report.results.append(result)
        if result.status in ("created", "cached", "planned") and result.mp3:
            report.mp3s.append(result.mp3)

    for wav in wav_targets:
        finished, reason = (is_finished_take(wav) if require_finished
                            else (wav.is_file() and wav.stat().st_size > 0,
                                  "exists" if wav.is_file() else "missing WAV"))
        if not finished:
            report.skipped.append((wav, reason))
            _log(logger, "info", "skip production WAV %s: %s", wav.name, reason)
        else:
            report.wavs.append(wav)

    for stem in report.missing_selected:
        _log(logger, "warning", "%s: selected take has no WAV: %s",
             POLICY_NAME, stem)
    return report


# --- CLI -------------------------------------------------------------------

def _cli(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_dir", help="generation run directory (out/<run>)")
    ap.add_argument("--cache", default=str(DEFAULT_CACHE),
                    help=f"MP3 cache root (default: {DEFAULT_CACHE})")
    ap.add_argument("--bitrate", default=DEFAULT_BITRATE,
                    help=f"MP3 bitrate (default: {DEFAULT_BITRATE})")
    ap.add_argument("--dry-run", action="store_true",
                    help="show what would be encoded; write nothing")
    ap.add_argument("--force", action="store_true",
                    help="re-encode even when the cache is valid")
    ap.add_argument("--unverified", action="store_true",
                    help="accept WAVs without a successful _time.txt")
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    run_dir = Path(args.run_dir).expanduser().resolve()
    if not run_dir.is_dir():
        print(f"not a directory: {run_dir}", file=sys.stderr)
        return 2
    try:
        report = export_run(run_dir, Path(args.cache).expanduser(),
                            bitrate=args.bitrate,
                            require_finished=not args.unverified,
                            force=args.force, dry_run=args.dry_run)
    except AudioExportError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(report.summary())
    for wav, reason in report.skipped:
        print(f"  skip  {wav.name}: {reason}")
    for mp3 in report.mp3s:
        print(f"  mp3   {mp3}")
    for wav in report.wavs:
        print(f"  wav   {wav}")
    for wav in report.fallbacks:
        print(f"  fallback WAV {wav.name}")
    return 1 if report.errors else 0


if __name__ == "__main__":
    raise SystemExit(_cli())
