#!/usr/bin/env python3
"""JSON-driven batch generation for the fine-tuned YuE2 LoRA (audio.cpp path).

One input JSON -> 1..N songs x 1..M takes each, generated **strictly
sequentially** (never in parallel: two concurrent runs can OOM the NAR graph)
through the canonical runner INFERENCE/run_one.sh, into one self-contained run
folder under out/. Random seeds by default.

Schema (strict: unknown keys are an error)

    {
      "loras": {                            # optional alias registry, per-song adapters
        "v3":     { "dir": "loras" },       # -> loras/arabmaqamrock-v3-{ar,nar}.safetensors
        "quran":  { "dir": "loras/quran" }, # -> loras/quran/arabmaqamrock-v3-{ar,nar}.safetensors
        "custom": { "ar": "my_ar.safetensors", "nar": "my_nar.safetensors" }
      },                                    # "dir" -> <dir>/arabmaqamrock-v3-{ar,nar}.safetensors,
                                            # or explicit "ar"+"nar"; relative paths resolve here
      "defaults": {                        # optional; per-song fields win
        "style":      "arabmaqamrock ...", # or "style_file": "prompts/Hijaz_style.txt"
        "repeat":     2,                   # takes per song, fresh random seeds
        "quantile":   0.95,                # cap quantile: 0.90 / 0.95 / 0.975
        "lora":       "v2"                 # alias for songs with no 'lora'
      },
      "songs": [
        {
          "name":    "my_song",            # required slug (Unicode letters/digits, '-'/'_'); duplicates get _2/_3...
          "style":   "arabmaqamrock ...",  # inline  xor style_file
          "style_file": "prompts/Hijaz_style.txt",
          "lyrics":  "[Verse 1]\n...",     # inline  xor lyrics_file
          "lyrics_file": "my_lyrics.txt",
          "lora":    "qahh_a0p1",         # optional alias; else defaults.lora, else the CLI pair
          "repeat":  3,                    # -> 3 fresh random seeds
          "seeds":   [1, 2, 3],            # or explicit, all < 2^32
          "seed":    42,                   # or exactly one render
          "cap":     6000,                 # explicit semantic_max_tokens
          "quantile": 0.975                # xor cap
        }
      ]
    }

Precedence: song field > CLI flag > "defaults" > built-in default. For `lora`
there is no CLI flag: song > `defaults.lora` > the `--lora-ar`/`--lora-nar` pair.
Every referenced pair is existence-checked in preflight before any GPU work.

Seeds default to `secrets.randbelow(2**32)`; values >= 2^32 alias because
audio.cpp seeds a uint32 (DECISIONS.md). The trigger "arabmaqamrock " is
prepended to the style when absent, matching every training caption and the
staged prompts (disable with --no-trigger).

Everything lands in out/<YYYYMMDD-HHMMSS>_<label>/:

    input.json               exact copy of the input
    batch_manifest.json      resolved seeds/caps/hashes, written BEFORE generation
    batch_summary.txt        per-track exit/wall/duration/truncation + totals
    _driver.log              full console output of the batch
    _runs_status.log         START/END per track (written by run_one.sh)
    _failed_runs.log         failures only
    prompts/<name>_{style,lyrics}.txt   flattened copies (the conditioning text)
    <name>_<seed>.wav / .log / _time.txt / _gpu.csv   (run_one.sh outputs)
    <name>_<seed>.json       per-track sidecar (DECISIONS.md sidecar policy)

Re-running with the same --out-dir resumes: tracks whose WAV exists and whose
_time.txt says "Exit status: 0" are skipped, and the seeds from the existing
batch_manifest.json are reused; --force regenerates anyway.

Dry-run (--dry-run) validates the JSON, resolves caps and prints the plan
without writing anything or needing a GPU.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import time
import wave
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, TextIO

sys.path.insert(0, str(Path(__file__).resolve().parent))
from duration_cap import COEFFS, arabic_letters, duration_cap  # noqa: E402

ROOT = Path(__file__).resolve().parent   # this repo (generate.py sits at the repo root)
REPO_INFERENCE = ROOT
RUN_ONE = REPO_INFERENCE / "run_one.sh"
BIN = ROOT / "bin" / "audiocpp_cli"
MODEL_DIR = ROOT / "models" / "Yue2-3B-GGUF"
MODEL_GGUF = "yue2-3b-bf16.gguf"
VAE_GGUF = "yue2-vae-f16.gguf"
LORA_AR_NAME = "arabmaqamrock-v3-ar.safetensors"
LORA_NAR_NAME = "arabmaqamrock-v3-nar.safetensors"
LORA_DIR = ROOT / "loras"
LORA_AR = LORA_DIR / LORA_AR_NAME
LORA_NAR = LORA_DIR / LORA_NAR_NAME
AUDIO_CPP = ROOT / "audio.cpp"

TRIGGER = "arabmaqamrock "
MAX_SEED = 2 ** 32
QUANTILES = sorted(COEFFS)
DEFAULT_QUANTILE = 0.95
NAME_RE = re.compile(r"^[^\W_][\w-]*$", re.UNICODE)
LORA_ALIAS_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
TRUNC_RE = re.compile(r"truncated\s*[=:]\s*([01])", re.IGNORECASE)
SEC_PER_TRACK = 389.6  # T4 mean wall/track, docs/INFERENCE.md benchmark
CHECKPOINT_STEP = 5000

SONG_KEYS = {"name", "style", "style_file", "lyrics", "lyrics_file",
             "repeat", "seeds", "seed", "cap", "quantile", "lora"}
DEFAULT_KEYS = {"style", "style_file", "repeat", "quantile", "lora"}
LORA_SPEC_KEYS = {"dir", "ar", "nar"}


class PlanError(Exception):
    """Invalid input JSON, bad CLI use, or failed preflight."""


@dataclass
class Song:
    name: str
    style_text: str
    lyrics_text: str
    cap: int
    quantile: float
    n_letters: int
    seed_spec: tuple  # ("list", (int,...)) | ("single", int) | ("random", count)
    lora: str | None = None  # alias into input.loras, or None for the CLI/default pair


@dataclass
class Track:
    idx: int
    name: str
    take: int
    seed: int | None  # None only in dry-run (not drawn)
    cap: int
    quantile: float
    n_letters: int
    lora: str | None = None  # alias, for the sidecar
    lora_ar: Path | None = None  # resolved AR adapter (None -> run_batch's default)
    lora_nar: Path | None = None  # resolved NAR adapter


@dataclass
class Result:
    track: Track
    status: str  # ok | failed | skipped
    exit: int | None = None
    wall_s: float | None = None
    wav_duration_s: float | None = None
    truncated: bool | None = None
    truncated_source: str | None = None


# --- small helpers ---------------------------------------------------------

def fail(msg: str) -> None:
    raise PlanError(msg)


def check(cond: bool, msg: str) -> None:
    if not cond:
        fail(msg)


def info(msg: str) -> None:
    print(f"[info] {msg}", file=sys.stderr)


def warn(msg: str) -> None:
    print(f"[warn] {msg}", file=sys.stderr)


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fmt_hms(seconds: float) -> str:
    s = int(round(seconds))
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m}:{sec:02d}"


def sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _unknown_keys(obj: dict, allowed: set, where: str) -> None:
    extra = sorted(set(obj) - allowed)
    if extra:
        fail(f"{where}: unknown key(s): {', '.join(extra)} "
             f"(allowed: {', '.join(sorted(allowed))})")


def _is_pos_int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool) and v >= 1


def _validate_seed(v, where: str) -> None:
    check(isinstance(v, int) and not isinstance(v, bool) and 0 <= v < MAX_SEED,
          f"{where}.seed(s): integer in [0, {MAX_SEED}) required "
          f"(audio.cpp seeds a uint32, larger values alias)")


def _validate_quantile(q, where: str) -> None:
    check(q in QUANTILES, f"{where}: quantile must be one of {QUANTILES}")


def _read_text(path: Path, where: str) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError as e:
        fail(f"{where}: not valid UTF-8: {path} ({e})")


# --- input parsing / validation -------------------------------------------

def load_input(path: Path) -> tuple[dict, bytes]:
    try:
        raw = path.read_bytes()
    except OSError as e:
        fail(f"cannot read input JSON: {e}")
    try:
        data = json.loads(raw.decode("utf-8"))
    except UnicodeDecodeError as e:
        fail(f"{path}: not valid UTF-8: {e}")
    except json.JSONDecodeError as e:
        fail(f"{path}: invalid JSON: {e}")
    check(isinstance(data, dict),
          f"{path}: top level must be an object with 'songs' (and optional 'defaults')")
    return data, raw


def _abs_path(value, base_dir: Path, where: str) -> Path:
    check(isinstance(value, str) and value.strip(), f"{where}: non-empty string required")
    p = Path(value).expanduser()
    return p if p.is_absolute() else base_dir / p


def resolve_loras(data: dict, base_dir: Path) -> dict[str, tuple[Path, Path]]:
    """Resolve the optional 'loras' alias registry to (AR, NAR) path pairs.

    Existence is NOT checked here (dry-run must work off-VM); preflight checks
    every referenced pair before any GPU work.
    """
    loras_raw = data.get("loras", {})
    check(isinstance(loras_raw, dict), "input.loras: must be an object")
    registry: dict[str, tuple[Path, Path]] = {}
    for alias, spec in loras_raw.items():
        where = f"input.loras[{alias!r}]"
        check(isinstance(alias, str) and LORA_ALIAS_RE.match(alias),
              f"{where}: alias must match {LORA_ALIAS_RE.pattern}")
        check(isinstance(spec, dict), f"{where}: must be an object")
        _unknown_keys(spec, LORA_SPEC_KEYS, where)
        has_dir = "dir" in spec
        has_pair = "ar" in spec or "nar" in spec
        check(has_dir != has_pair,
              f"{where}: use either 'dir' or both 'ar' and 'nar' (not both forms)")
        if has_dir:
            d = _abs_path(spec["dir"], base_dir, f"{where}.dir")
            ar, nar = d / LORA_AR_NAME, d / LORA_NAR_NAME
        else:
            check("ar" in spec and "nar" in spec,
                  f"{where}: 'ar' and 'nar' must both be given")
            ar = _abs_path(spec["ar"], base_dir, f"{where}.ar")
            nar = _abs_path(spec["nar"], base_dir, f"{where}.nar")
        registry[alias] = (ar, nar)
    return registry


def _resolve_string(obj: dict, inline_key: str, file_key: str,
                    base_dir: Path, where: str) -> tuple[str | None, Path | None]:
    has_inline = inline_key in obj
    has_file = file_key in obj
    check(not (has_inline and has_file),
          f"{where}: '{inline_key}' and '{file_key}' are mutually exclusive")
    if has_inline:
        v = obj[inline_key]
        check(isinstance(v, str) and v.strip(), f"{where}.{inline_key}: non-empty string required")
        return v, None
    if has_file:
        v = obj[file_key]
        check(isinstance(v, str) and v.strip(), f"{where}.{file_key}: non-empty string required")
        p = Path(v).expanduser()
        if not p.is_absolute():
            p = base_dir / p
        check(p.is_file(), f"{where}.{file_key}: file not found: {p}")
        return None, p
    return None, None


def _style_text(raw: dict, defaults: dict, base_dir: Path, where: str,
                trigger: bool) -> str:
    text, path = _resolve_string(raw, "style", "style_file", base_dir, where)
    if text is None and path is None:
        text, path = _resolve_string(defaults, "style", "style_file", base_dir,
                                     "input.defaults")
    check(text is not None or path is not None,
          f"{where}: needs 'style' or 'style_file' (or input.defaults)")
    if path is not None:
        text = _read_text(path, f"{where}.style_file")
    check(text.strip(), f"{where}: style is empty")
    if trigger and TRIGGER.strip() not in text:
        text = TRIGGER + text
        info(f"{where}: trigger '{TRIGGER.strip()}' prepended to style")
    return text


def _lyrics_text(raw: dict, base_dir: Path, where: str) -> str:
    text, path = _resolve_string(raw, "lyrics", "lyrics_file", base_dir, where)
    check(text is not None or path is not None, f"{where}: needs 'lyrics' or 'lyrics_file'")
    if path is not None:
        text = _read_text(path, f"{where}.lyrics_file")
    check(text.strip(), f"{where}: lyrics are empty")
    return text


def _cap_settings(raw: dict, base_q: float, n_letters: int, where: str) -> tuple[float, int]:
    has_cap = "cap" in raw
    has_q = "quantile" in raw
    check(not (has_cap and has_q), f"{where}: 'cap' and 'quantile' are mutually exclusive")
    if has_cap:
        cap = raw["cap"]
        check(_is_pos_int(cap), f"{where}.cap: positive integer required")
        return base_q, cap
    q = raw["quantile"] if has_q else base_q
    _validate_quantile(q, f"{where}.quantile")
    _, _, cap, _ = duration_cap(n_letters, q)
    return q, cap


def _seed_spec(raw: dict, defaults: dict, where: str) -> tuple:
    has_list = "seeds" in raw
    has_one = "seed" in raw
    has_rep = "repeat" in raw
    rep = raw.get("repeat", defaults.get("repeat", 1))
    if has_rep:
        check(_is_pos_int(rep), f"{where}.repeat: integer >= 1 required")
    if has_list:
        check(not has_one and not has_rep,
              f"{where}: 'seeds' is mutually exclusive with 'seed' and 'repeat'")
        seeds = raw["seeds"]
        check(isinstance(seeds, list) and seeds, f"{where}.seeds: non-empty array required")
        for s in seeds:
            _validate_seed(s, where)
        check(len(set(seeds)) == len(seeds),
              f"{where}.seeds: duplicate seeds would collide on the same output filename")
        return ("list", tuple(seeds))
    if has_one:
        check(not has_rep or rep <= 1, f"{where}: 'seed' with repeat > 1 is ambiguous; use 'seeds'")
        _validate_seed(raw["seed"], where)
        return ("single", raw["seed"])
    return ("random", rep)


def _lora_alias(raw: dict, defaults: dict, loras: dict, where: str) -> str | None:
    for obj, label in ((raw, where), (defaults, "input.defaults")):
        if "lora" in obj:
            v = obj["lora"]
            check(isinstance(v, str) and v.strip(), f"{label}.lora: non-empty string required")
            known = ', '.join(sorted(loras)) if loras else None
            check(v in loras,
                  f"{label}.lora: unknown alias '{v}'"
                  + (f" (known: {known})" if known else " (no input.loras registry defined)"))
            return v
    return None


def resolve_songs(data: dict, base_dir: Path, cli_quantile: float | None = None,
                  trigger: bool = True, loras: dict | None = None) -> list[Song]:
    """Validate the input JSON and resolve every song (no writes, no GPU)."""
    check(isinstance(data, dict), "input: top level must be a JSON object")
    _unknown_keys(data, {"defaults", "songs", "loras"}, "input")
    defaults = data.get("defaults", {})
    check(isinstance(defaults, dict), "input.defaults: must be an object")
    _unknown_keys(defaults, DEFAULT_KEYS, "input.defaults")
    if "repeat" in defaults:
        check(_is_pos_int(defaults["repeat"]), "input.defaults.repeat: integer >= 1 required")
    if "quantile" in defaults:
        _validate_quantile(defaults["quantile"], "input.defaults.quantile")

    songs_raw = data.get("songs")
    check(isinstance(songs_raw, list) and songs_raw, "input.songs: non-empty array required")

    base_q = cli_quantile if cli_quantile is not None else defaults.get("quantile", DEFAULT_QUANTILE)
    _validate_quantile(base_q, "--quantile")

    songs: list[Song] = []
    seen: set[str] = set()
    for i, raw in enumerate(songs_raw):
        where = f"input.songs[{i}]"
        check(isinstance(raw, dict), f"{where}: must be an object")
        _unknown_keys(raw, SONG_KEYS, where)

        name = raw.get("name")
        check(isinstance(name, str) and NAME_RE.match(name),
              f"{where}.name: required name slug (Unicode letters/digits, "
              f"'-' or '_'; no spaces/dots/slashes), matching {NAME_RE.pattern}")
        base = name
        n = 2
        while name in seen:
            name = f"{base}_{n}"
            n += 1
        if name != base:
            warn(f"{where}.name: '{base}' already used; renamed to '{name}'")
        seen.add(name)

        style_text = _style_text(raw, defaults, base_dir, where, trigger)
        lyrics_text = _lyrics_text(raw, base_dir, where)
        n_letters = arabic_letters(lyrics_text)
        if n_letters == 0:
            warn(f"{where} ('{name}'): lyrics contain no Arabic letters; "
                 f"the auto cap falls back to the quantile floor")
        quantile, cap = _cap_settings(raw, base_q, n_letters, where)
        songs.append(Song(name, style_text, lyrics_text, cap, quantile, n_letters,
                          _seed_spec(raw, defaults, where),
                          _lora_alias(raw, defaults, loras or {}, where)))
    return songs


# --- planning --------------------------------------------------------------

def draw_seeds(count: int) -> list[int]:
    seen: set[int] = set()
    out: list[int] = []
    while len(out) < count:
        s = secrets.randbelow(MAX_SEED)
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out


def build_tracks(songs: list[Song], limit: int | None = None,
                 seed_lookup: dict | None = None, draw: bool = True,
                 loras: dict | None = None) -> list[Track]:
    tracks: list[Track] = []
    idx = 0
    for song in songs:
        kind, val = song.seed_spec
        if kind == "list":
            seeds: list[int | None] = list(val)
        elif kind == "single":
            seeds = [val]
        else:
            seeds = draw_seeds(val) if draw else [None] * val
        ar, nar = loras[song.lora] if (song.lora and loras) else (None, None)
        for take, seed in enumerate(seeds):
            if seed_lookup:
                seed = seed_lookup.get((song.name, take), seed)
            idx += 1
            if limit is not None and idx > limit:
                return tracks
            tracks.append(Track(idx, song.name, take, seed, song.cap,
                                song.quantile, song.n_letters, song.lora, ar, nar))
    return tracks


def slugify(text: str) -> str:
    s = re.sub(r"[^A-Za-z0-9_-]+", "-", text).strip("-").lower()
    return s or "songs"


def pick_run_dir(label: str) -> Path:
    out_root = ROOT / "out"
    stem = f"{datetime.now().strftime('%Y%m%d-%H%M%S')}_{label}"
    run_dir = out_root / stem
    n = 2
    while run_dir.exists():
        run_dir = out_root / f"{stem}-{n}"
        n += 1
    return run_dir


def load_manifest_seeds(run_dir: Path) -> dict:
    manifest = run_dir / "batch_manifest.json"
    if not manifest.is_file():
        return {}
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        warn(f"could not read {manifest}; drawing fresh seeds")
        return {}
    return {(t.get("name"), t.get("take")): t.get("seed")
            for t in data.get("tracks", []) if t.get("seed") is not None}


# --- preflight / assets ----------------------------------------------------

def gpu_info() -> dict | None:
    if not shutil.which("nvidia-smi"):
        return None
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.used,memory.total,compute_cap",
             "--format=csv,noheader"], capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if r.returncode != 0 or not r.stdout.strip():
        return None
    parts = [p.strip() for p in r.stdout.strip().splitlines()[0].split(",")]
    if len(parts) < 4:
        return None
    return {"name": parts[0], "memory_used": parts[1],
            "memory_total": parts[2], "compute_cap": parts[3]}


def git_commit(path: Path) -> str | None:
    try:
        r = subprocess.run(["git", "-C", str(path), "rev-parse", "--short", "HEAD"],
                           capture_output=True, text=True, timeout=15)
        return r.stdout.strip() if r.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def asset_fingerprint(lora_ar: Path, lora_nar: Path, hash_big: bool = True,
                      loras: dict | None = None) -> dict:
    if hash_big:
        info("hashing model assets (main GGUF + VAE, ~3.9 GB once per batch)...")
    fp = {
        "lora_ar_sha256": sha256_file(lora_ar),
        "lora_nar_sha256": sha256_file(lora_nar),
        "model_gguf": MODEL_GGUF,
        "vae_gguf": VAE_GGUF,
        "model_gguf_sha256": sha256_file(MODEL_DIR / MODEL_GGUF) if hash_big else None,
        "vae_gguf_sha256": sha256_file(MODEL_DIR / VAE_GGUF) if hash_big else None,
        "audio_cpp_commit": git_commit(AUDIO_CPP),
        "checkpoint_step": CHECKPOINT_STEP,
    }
    if loras:
        fp["loras"] = {
            alias: {"ar": str(ar), "nar": str(nar),
                    "ar_sha256": sha256_file(ar), "nar_sha256": sha256_file(nar)}
            for alias, (ar, nar) in loras.items()
        }
    return fp


def preflight(lora_ar: Path, lora_nar: Path,
              loras: dict | None = None) -> dict:
    problems = []
    checks = [
        (RUN_ONE, "runner"),
        (BIN, "audiocpp_cli binary"),
        (Path("/usr/bin/time"), "GNU time (apt-get install time)"),
        (MODEL_DIR / MODEL_GGUF, "main GGUF"),
        (MODEL_DIR / VAE_GGUF, "VAE GGUF"),
        (lora_ar, "AR LoRA adapter"),
        (lora_nar, "NAR LoRA adapter"),
    ]
    for alias, (ar, nar) in (loras or {}).items():
        checks.append((ar, f"AR LoRA adapter [{alias}]"))
        checks.append((nar, f"NAR LoRA adapter [{alias}]"))
    for path, what in checks:
        if not path.is_file():
            problems.append(f"missing {what}: {path}")
    if BIN.is_file() and not os.access(BIN, os.X_OK):
        problems.append(f"not executable: {BIN}")
    if not (MODEL_DIR / "sidecars").is_dir():
        problems.append(f"missing sidecars dir: {MODEL_DIR / 'sidecars'}")
    if problems:
        fail("preflight failed:\n  - " + "\n  - ".join(problems)
             + "\n  run ./install.sh first (builds audiocpp_cli, downloads the GGUF"
             + " model, and fetches the LoRA), and check --lora-ar/--lora-nar.")

    gpu = gpu_info()
    check(gpu is not None, "nvidia-smi did not report a GPU; inference needs the Colab GPU runtime")

    disk_target = ROOT if ROOT.exists() else Path("/")
    try:
        free_gb = shutil.disk_usage(str(disk_target)).free / 1e9
    except OSError:
        free_gb = float("nan")
    info(f"GPU: {gpu['name']} (CC {gpu['compute_cap']}) | free disk: {free_gb:.1f} GB "
         f"| VA allocated: {gpu['memory_used']}/{gpu['memory_total']} MiB")
    return gpu


# --- materialize the run folder -------------------------------------------

def materialize(run_dir: Path, songs: list[Song], raw_input: bytes,
                input_path: Path, tracks: list[Track], fp: dict, gpu: dict) -> dict:
    prompts_dir = run_dir / "prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    prompt_info: dict[str, dict] = {}
    for song in songs:
        style_path = prompts_dir / f"{song.name}_style.txt"
        lyrics_path = prompts_dir / f"{song.name}_lyrics.txt"
        style_path.write_text(song.style_text, encoding="utf-8")
        lyrics_path.write_text(song.lyrics_text, encoding="utf-8")
        prompt_info[song.name] = {
            "style_file": f"prompts/{song.name}_style.txt",
            "lyrics_file": f"prompts/{song.name}_lyrics.txt",
            "style_sha256": sha256_file(style_path),
            "lyrics_sha256": sha256_file(lyrics_path),
        }

    (run_dir / "input.json").write_bytes(raw_input)

    manifest = {
        "generated_at": utcnow(),
        "run_dir": str(run_dir),
        "input_file": str(input_path),
        "input_sha256": hashlib.sha256(raw_input).hexdigest(),
        "assets": fp,
        "gpu": {"name": gpu["name"], "compute_cap": gpu["compute_cap"]},
        "tracks": [],
    }
    for t in tracks:
        p = prompt_info[t.name]
        manifest["tracks"].append({
            "idx": t.idx, "name": t.name, "take": t.take, "seed": t.seed,
            "cap": t.cap, "quantile": t.quantile, "n_letters": t.n_letters,
            "style_file": p["style_file"], "style_sha256": p["style_sha256"],
            "lyrics_file": p["lyrics_file"], "lyrics_sha256": p["lyrics_sha256"],
        })
    (run_dir / "batch_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return prompt_info


# --- execution -------------------------------------------------------------

def subprocess_runner(cmd: list[str], env: dict, log_fh: TextIO) -> int:
    proc = subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, bufsize=1)
    assert proc.stdout is not None
    for line in proc.stdout:
        sys.stdout.write(line)
        sys.stdout.flush()
        log_fh.write(line)
        log_fh.flush()
    return proc.wait()


def _succeeded(wav: Path, time_file: Path) -> bool:
    try:
        if wav.stat().st_size <= 0:
            return False
    except OSError:
        return False
    try:
        return "Exit status: 0" in time_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False


def wav_duration(path: Path) -> float | None:
    if not path.is_file():
        return None
    try:
        with wave.open(str(path), "rb") as w:
            return w.getnframes() / float(w.getframerate())
    except Exception:
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


def truncation_info(log_path: Path, dur: float | None, cap: int) -> tuple[bool | None, str | None]:
    if log_path.is_file():
        try:
            m = TRUNC_RE.search(log_path.read_text(encoding="utf-8", errors="replace"))
            if m:
                return bool(int(m.group(1))), "log"
        except OSError:
            pass
    if dur is not None:
        return dur >= (cap / 25.0) - 1.0, "duration_heuristic"
    return None, None


def wait_vram_free(max_seconds: float = 60.0) -> None:
    if not shutil.which("nvidia-smi"):
        return
    deadline = time.monotonic() + max_seconds
    while time.monotonic() < deadline:
        try:
            r = subprocess.run(
                ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=15)
        except (OSError, subprocess.TimeoutExpired):
            return
        if r.returncode != 0 or not r.stdout.strip():
            return
        try:
            used = int(r.stdout.strip().splitlines()[0])
        except ValueError:
            return
        if used < 1000:
            return
        time.sleep(2)


def sidecar_fields(t: Track, prompt_info: dict, fp: dict, gpu: dict) -> dict:
    p = prompt_info[t.name]
    entry = (fp.get("loras") or {}).get(t.lora) if t.lora else None
    return {
        "idx": t.idx,
        "name": t.name,
        "take": t.take,
        "seed": t.seed,
        "cap": t.cap,
        "quantile": t.quantile,
        "n_letters": t.n_letters,
        "start_utc": utcnow(),
        "run_one": f"INFERENCE/run_one.sh {t.name} {t.seed} {t.cap}",
        "lyrics_file": p["lyrics_file"],
        "lyrics_sha256": p["lyrics_sha256"],
        "style_file": p["style_file"],
        "style_sha256": p["style_sha256"],
        "lora_alias": t.lora,
        "lora_ar_sha256": entry["ar_sha256"] if entry else fp["lora_ar_sha256"],
        "lora_nar_sha256": entry["nar_sha256"] if entry else fp["lora_nar_sha256"],
        "model_gguf": fp["model_gguf"],
        "vae_gguf": fp["vae_gguf"],
        "model_gguf_sha256": fp["model_gguf_sha256"],
        "vae_gguf_sha256": fp["vae_gguf_sha256"],
        "attention": "flash",
        "cot": "off",
        "checkpoint_step": fp["checkpoint_step"],
        "audio_cpp_commit": fp["audio_cpp_commit"],
        "gpu": gpu["name"],
        "compute_cap": gpu["compute_cap"],
        "status": "started",
    }


def _write_sidecar(path: Path, fields: dict) -> None:
    path.write_text(json.dumps(fields, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_batch(run_dir: Path, tracks: list[Track], prompt_info: dict, fp: dict,
              gpu: dict, lora_ar: Path, lora_nar: Path, *, force: bool = False,
              runner: Callable[[list[str], dict, TextIO], int] = subprocess_runner) -> list[Result]:
    results: list[Result] = []
    failed_log = run_dir / "_failed_runs.log"
    driver_log = open(run_dir / "_driver.log", "a", encoding="utf-8")
    total = len(tracks)
    try:
        for t in tracks:
            ar = t.lora_ar or lora_ar
            nar = t.lora_nar or lora_nar
            wav = run_dir / f"{t.name}_{t.seed}.wav"
            time_file = run_dir / f"{t.name}_{t.seed}_time.txt"
            log_file = run_dir / f"{t.name}_{t.seed}.log"
            sidecar = run_dir / f"{t.name}_{t.seed}.json"

            if not force and _succeeded(wav, time_file):
                print(f"[{t.idx}/{total}] skip {t.name} take={t.take} seed={t.seed} "
                      f"(already succeeded; --force to redo)")
                results.append(Result(t, "skipped"))
                continue

            lora_tag = f" lora={t.lora}" if t.lora else ""
            print(f"[{t.idx}/{total}] {t.name} take={t.take} seed={t.seed} cap={t.cap} "
                  f"(q={t.quantile}, N={t.n_letters}){lora_tag} start={utcnow()}")
            fields = sidecar_fields(t, prompt_info, fp, gpu)
            _write_sidecar(sidecar, fields)

            env = dict(os.environ)
            env.update({
                "OUT_DIR": str(run_dir),
                "STYLE_FILE": str(run_dir / prompt_info[t.name]["style_file"]),
                "LYRICS_FILE": str(run_dir / prompt_info[t.name]["lyrics_file"]),
                "LORA_AR": str(ar),
                "LORA_NAR": str(nar),
                # This batch path is the trained cot=off regime. ABC-guided
                # renders use run_one.sh directly (COT=melody ABC_FILE=...).
                "COT": "off",
                "ABC_FILE": "",
            })
            cmd = ["bash", str(RUN_ONE), t.name, str(t.seed), str(t.cap)]

            t0 = time.monotonic()
            rc = runner(cmd, env, driver_log)
            wall = time.monotonic() - t0

            dur = wav_duration(wav) if wav.is_file() else None
            trunc, trunc_src = truncation_info(log_file, dur, t.cap)
            fields.update({
                "exit": rc,
                "end_utc": utcnow(),
                "wall_s": round(wall, 1),
                "wav_sha256": sha256_file(wav) if wav.is_file() and wav.stat().st_size else None,
                "wav_duration_s": dur,
                "truncated": trunc,
                "truncated_source": trunc_src,
                "status": "ok" if rc == 0 else "failed",
            })
            _write_sidecar(sidecar, fields)

            if rc != 0:
                line = (f"FAILED idx={t.idx} {t.name} seed={t.seed} "
                        f"exit={rc} {utcnow()}")
                print(line)
                with open(failed_log, "a", encoding="utf-8") as f:
                    f.write(line + "\n")
                wait_vram_free()
                print(f"[{t.idx}/{total}] {t.name} seed={t.seed} wall={fmt_hms(wall)} "
                      f"FAILED exit={rc} (continuing)")
            else:
                dur_s = "-" if dur is None else f"{dur:.1f}"
                print(f"[{t.idx}/{total}] {t.name} seed={t.seed} wall={fmt_hms(wall)} ok "
                      f"dur={dur_s}s")

            results.append(Result(t, "ok" if rc == 0 else "failed", rc, wall,
                                  dur, trunc, trunc_src))
    finally:
        driver_log.close()
    return results


# --- reporting -------------------------------------------------------------

def _trunc_label(r: Result) -> str:
    if r.truncated is None:
        return "-"
    if not r.truncated:
        return "no"
    return "yes" if r.truncated_source == "log" else "maybe"


def render_summary(run_dir: Path, results: list[Result]) -> str:
    lines = [f"=== batch summary — {utcnow()} ===", f"run dir: {run_dir}", ""]
    header = (f"{'idx':>4}  {'name':<28}  {'take':>4}  {'seed':>10}  {'cap':>5}  "
              f"{'exit':>4}  {'wall':>8}  {'dur_s':>7}  {'trunc':>6}")
    lines.append(header)
    lines.append("-" * len(header))
    for r in results:
        t = r.track
        seed = "-" if t.seed is None else str(t.seed)
        exit_s = "-" if r.exit is None else str(r.exit)
        wall = "-" if r.wall_s is None else fmt_hms(r.wall_s)
        dur = "-" if r.wav_duration_s is None else f"{r.wav_duration_s:.1f}"
        lines.append(f"{t.idx:>4}  {t.name:<28}  {t.take:>4}  {seed:>10}  {t.cap:>5}  "
                     f"{exit_s:>4}  {wall:>8}  {dur:>7}  {_trunc_label(r):>6}")

    ok = sum(1 for r in results if r.status == "ok")
    failed = sum(1 for r in results if r.status == "failed")
    skipped = sum(1 for r in results if r.status == "skipped")
    total_wall = sum(r.wall_s or 0.0 for r in results)
    lines += ["", f"ok: {ok}   failed: {failed}   skipped: {skipped}   "
                  f"total wall: {fmt_hms(total_wall)}"]
    truncs = [r for r in results if r.truncated]
    if truncs:
        lines.append("possibly truncated: " + ", ".join(
            f"{r.track.name} seed {r.track.seed} ({r.truncated_source})" for r in truncs))
    if failed:
        lines.append(f"failures: {run_dir / '_failed_runs.log'}")
    return "\n".join(lines) + "\n"


def print_plan(songs: list[Song], tracks: list[Track], run_dir: Path, dry_run: bool) -> None:
    est_min = len(tracks) * SEC_PER_TRACK / 60.0
    print(f"plan: {len(songs)} song(s), {len(tracks)} track(s); "
          f"projected ~{est_min:.0f} min on a T4 (~{SEC_PER_TRACK:.0f} s/track)")
    print(f"run dir: {run_dir}" + ("   [dry-run: nothing will be written]" if dry_run else ""))
    print(f"{'idx':>4}  {'name':<28}  {'take':>4}  {'seed':>10}  {'cap':>5}  {'q':>5}  lora")
    for t in tracks:
        seed = str(t.seed) if t.seed is not None else "<random>"
        print(f"{t.idx:>4}  {t.name:<28}  {t.take:>4}  {seed:>10}  {t.cap:>5}  {t.quantile:>5}  "
              f"{t.lora or '-'}")


# --- CLI -------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="generate.py",
        description="Generate tracks from a JSON of songs (style + lyrics) through "
                    "INFERENCE/run_one.sh, sequentially, random seeds by default.",
        epilog="See docs/INFERENCE.md ('Generate from your own JSON') for the schema.",
    )
    p.add_argument("json", help="input JSON with 'songs' (and optional 'defaults')")
    p.add_argument("--label", default=None,
                   help="run-folder label (default: slug of the JSON filename)")
    p.add_argument("--out-dir", default=None,
                   help="explicit run dir (enables resume; default: out/<timestamp>_<label>)")
    p.add_argument("--quantile", type=float, default=None, choices=QUANTILES,
                   help="cap quantile when a song has no explicit cap/quantile")
    p.add_argument("--dry-run", action="store_true",
                   help="validate and print the plan; writes nothing, needs no GPU")
    p.add_argument("--force", action="store_true",
                   help="regenerate tracks that already succeeded")
    p.add_argument("--limit", type=int, default=None,
                   help="only the first N tracks (smoke tests)")
    p.add_argument("--no-trigger", action="store_true",
                   help="do not auto-prepend 'arabmaqamrock ' to styles")
    p.add_argument("--lora-ar", default=None,
                   help="default AR adapter for songs with no 'lora' alias "
                        "(built-in default: the live converted v2 pair)")
    p.add_argument("--lora-nar", default=None,
                   help="default NAR adapter for songs with no 'lora' alias "
                        "(built-in default: the live converted v2 pair)")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        check(args.limit is None or _is_pos_int(args.limit), "--limit must be an integer >= 1")
        input_path = Path(args.json)
        lora_ar = Path(args.lora_ar).expanduser() if args.lora_ar else LORA_AR
        lora_nar = Path(args.lora_nar).expanduser() if args.lora_nar else LORA_NAR
        base_dir = input_path.resolve().parent
        data, raw = load_input(input_path)
        loras = resolve_loras(data, base_dir)
        songs = resolve_songs(data, base_dir, args.quantile,
                              trigger=not args.no_trigger, loras=loras)

        if args.out_dir:
            run_dir = Path(args.out_dir)
        else:
            run_dir = pick_run_dir(args.label or slugify(input_path.stem))

        seed_lookup = load_manifest_seeds(run_dir)
        tracks = build_tracks(songs, limit=args.limit,
                              seed_lookup=seed_lookup, draw=not args.dry_run,
                              loras=loras)
        check(tracks, "no tracks to run (check --limit)")

        if args.dry_run:
            print_plan(songs, tracks, run_dir, dry_run=True)
            return 0

        gpu = preflight(lora_ar, lora_nar, loras)
        run_dir.mkdir(parents=True, exist_ok=True)
        fp = asset_fingerprint(lora_ar, lora_nar, loras=loras)
        prompt_info = materialize(run_dir, songs, raw, input_path, tracks, fp, gpu)

        print_plan(songs, tracks, run_dir, dry_run=False)
        print()
        results = run_batch(run_dir, tracks, prompt_info, fp, gpu, lora_ar, lora_nar,
                            force=args.force)

        try:
            (ROOT / "out").mkdir(parents=True, exist_ok=True)
            (ROOT / "out" / "latest").write_text(str(run_dir) + "\n", encoding="utf-8")
        except OSError as e:
            warn(f"could not update out/latest: {e}")

        summary = render_summary(run_dir, results)
        (run_dir / "batch_summary.txt").write_text(summary, encoding="utf-8")
        print()
        print(summary, end="")
        return 1 if any(r.status == "failed" for r in results) else 0
    except PlanError as e:
        print(f"[error] {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\n[interrupted] batch stopped; partial outputs are in place", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
