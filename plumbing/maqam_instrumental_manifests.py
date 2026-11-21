#!/usr/bin/env python3
"""Generate maqam instrumental manifests for ``generate.py``.

The batch is built from the three documents in
``docs/misc/instrumental_music/``:

* ``instrumental_base_prompt.md``       -- the style caption template
* ``maqam_emotions.json``               -- the mood palette for each maqam
* ``most_common_lyrics_arrangements.py`` -- the section plans

Every song gets a unique combination of three mood tags, a section plan whose
length matches the requested profile (short 6-7, standard 8, long 9-10), and
the standard ``a0.15`` instrumental recipe used by
``manifests/maqam_instrumental_songs_03.json``.

Interactive (the few knobs have defaults in brackets)::

    python3 plumbing/maqam_instrumental_manifests.py

Non-interactive::

    python3 plumbing/maqam_instrumental_manifests.py --yes \
        --tracks 12 --repeat 1 --length mixed --cap 8500 \
        --out manifests/maqam_instrumental_songs_04.json

Then validate or render it::

    python3 generate.py manifests/maqam_instrumental_songs_04.json --dry-run
"""

from __future__ import annotations

import argparse
import importlib.util
import itertools
import json
import math
import os
import random
import re
import sys
from pathlib import Path
from typing import NoReturn

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs" / "misc" / "instrumental_music"
EMOTIONS_PATH = DOCS / "maqam_emotions.json"
ARRANGEMENTS_PATH = DOCS / "most_common_lyrics_arrangements.py"
BASE_PROMPT_PATH = DOCS / "instrumental_base_prompt.md"

MANIFESTS_DIR = ROOT / "manifests"
DEFAULT_STEM = "maqam_instrumental_songs"
DEFAULT_TRACKS = 10
DEFAULT_REPEAT = 1
DEFAULT_CAP = 8500
DEFAULT_MOODS = 3
DEFAULT_LENGTH = "mixed"

# Section counts exclude the trailing [End] marker: a plan with seven musical
# sections (intro, verse, chorus, bridge, verse, chorus, outro) has eight lines.
LENGTH_PROFILES = {
    "short": (6, 7),
    "standard": (8, 8),
    "long": (9, 10),
}
LENGTH_CHOICES = ("short", "standard", "long", "mixed")
MIXED_CYCLE = ("short", "standard", "long")

# Western scale written beside the maqam, per README.md / docs/base-prompt.md.
SCALES = {
    "Hijaz": "Phrygian Dominant",
    "Nahawand": "Natural Minor Scale (Aeolian)",
    "Ajam": "Major Scale (Ionian)",
    "Kurd": "Phrygian Mode",
}

# The winning instrumental arm (docs/generation-defaults.md).
LORAS = {
    "a015": {
        "ar": "loras/blend/a0.15/v3instr_a0.15_ar.safetensors",
        "nar": "loras/blend/a0.15/v3instr_a0.15_nar.safetensors",
    }
}
DEFAULT_LORA = "a015"


# --------------------------------------------------------------------------
# Loading the source documents
# --------------------------------------------------------------------------

def load_emotions(path: Path = EMOTIONS_PATH) -> dict[str, list[str]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    maqams = data.get("maqams")
    if not isinstance(maqams, dict) or not maqams:
        raise SystemExit(f"{path}: expected a non-empty 'maqams' object")
    out: dict[str, list[str]] = {}
    for name, entry in maqams.items():
        emotions = entry.get("emotions") if isinstance(entry, dict) else None
        if not isinstance(emotions, list) or not emotions:
            raise SystemExit(f"{path}: maqam {name!r} has no 'emotions' list")
        out[name] = [str(e) for e in emotions]
    return out


def load_arrangements(path: Path = ARRANGEMENTS_PATH) -> list[str]:
    spec = importlib.util.spec_from_file_location("_maqam_arrangements", path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"{path}: cannot load arrangements module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    plans = getattr(module, "lyrics_arrangement", None)
    if not isinstance(plans, list) or not plans:
        raise SystemExit(f"{path}: expected a non-empty 'lyrics_arrangement' list")
    for plan in plans:
        if not isinstance(plan, str) or not plan.strip():
            raise SystemExit(f"{path}: every arrangement must be a non-empty string")
    return plans


def load_base_prompt(path: Path = BASE_PROMPT_PATH) -> str:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise SystemExit(f"{path}: empty base prompt")
    return text


# --------------------------------------------------------------------------
# Building blocks
# --------------------------------------------------------------------------

def section_count(plan: str) -> int:
    """Musical sections in a plan, ignoring the closing ``[End]`` marker."""
    tags = [line.strip() for line in plan.splitlines() if line.strip()]
    return sum(1 for tag in tags if tag.lower() != "[end]")


def arrangements_for(profile: str, plans: list[str]) -> list[str]:
    """Plans whose section count falls inside a length profile."""
    if profile == "mixed":
        return list(plans)
    try:
        low, high = LENGTH_PROFILES[profile]
    except KeyError:
        raise ValueError(f"unknown length profile: {profile!r}") from None
    pool = [p for p in plans if low <= section_count(p) <= high]
    if not pool:
        raise ValueError(f"no arrangements with {low}-{high} sections")
    return pool


def slug(text: str) -> str:
    """Lowercase name-safe slug (generate.py allows letters, digits, ``-``/``_``)."""
    text = text.strip().lower()
    text = re.sub(r"[^\w-]+", "-", text, flags=re.UNICODE)
    text = re.sub(r"-{2,}", "-", text)
    return text.strip("-_")


def build_style(
    base_prompt: str,
    maqam: str,
    moods: tuple[str, ...],
    *,
    keep_vocalization: bool = False,
) -> str:
    """Fill the base-prompt template and make the caption safely instrumental.

    ``instrumental_base_prompt.md`` contains the literal word ``vocalization``;
    for an instrumental cover it is replaced by ``no vocals, no singing`` (the
    guard used by ``maqam_instrumental_songs_03.json``). Pass
    ``keep_vocalization=True`` to leave the document untouched.
    """
    text = " ".join(base_prompt.replace("**", "").split())
    text = text.replace("[MAQAM]", maqam)
    text = text.replace("[SCALE / MODE]", SCALES.get(maqam, ""))
    text = text.replace("[MOOD]", ", ".join(moods))
    if not keep_vocalization:
        text = re.sub(r"\bvocalization\b", "no vocals, no singing", text,
                      flags=re.IGNORECASE)
    # A maqam without a known Western scale leaves an empty slot: tidy up.
    text = re.sub(r"\s*,\s*,+", ", ", text)
    text = re.sub(r",\s*,", ", ", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip().strip(",").strip()


def mood_combinations(
    emotions: list[str],
    count: int,
    moods_per_track: int,
    rng: random.Random,
) -> list[tuple[str, ...]]:
    """Pick unique mood combinations, spreading the first tag across the palette.

    Pass one anchors each track on a different emotion, so a small batch still
    covers the whole palette. Later passes fill with random unique combinations.
    """
    palette = list(dict.fromkeys(emotions))  # dedupe, keep the document order
    if moods_per_track < 1:
        raise ValueError("moods_per_track must be at least 1")
    if len(palette) < moods_per_track:
        raise ValueError(
            f"need {moods_per_track} moods but the palette has {len(palette)}")
    count = min(count, math.comb(len(palette), moods_per_track))
    rng.shuffle(palette)

    chosen: list[tuple[str, ...]] = []
    seen: set[tuple[str, ...]] = set()

    for anchor in palette:
        if len(chosen) >= count:
            break
        others = [e for e in palette if e != anchor]
        if len(others) < moods_per_track - 1:
            continue
        pair = tuple(sorted(rng.sample(others, moods_per_track - 1)))
        combo = tuple(sorted((anchor, *pair)))
        if combo not in seen:
            seen.add(combo)
            chosen.append((anchor, *pair))

    if len(chosen) < count:
        remaining = [c for c in itertools.combinations(palette, moods_per_track)
                     if c not in seen]
        rng.shuffle(remaining)
        chosen.extend(remaining[:count - len(chosen)])

    return chosen


def _profile_for(index: int, length: str) -> str:
    if length != "mixed":
        return length
    return MIXED_CYCLE[index % len(MIXED_CYCLE)]


def build_songs(
    maqams: list[str],
    emotions_by_maqam: dict[str, list[str]],
    arrangements: list[str],
    base_prompt: str,
    *,
    tracks_per_maqam: int,
    length: str,
    moods_per_track: int = DEFAULT_MOODS,
    cap: int | None = DEFAULT_CAP,
    seed: int | None = None,
    keep_vocalization: bool = False,
) -> list[dict]:
    """Build the ``songs`` list for the manifest."""
    if tracks_per_maqam < 1:
        raise ValueError("tracks_per_maqam must be at least 1")
    rng = random.Random(seed)

    # One shuffled plan cycle per profile so repeated runs with the same seed
    # produce the same order, while different seeds vary the arrangement.
    profiles = (("short", "standard", "long") if length == "mixed" else (length,))
    cycles = {
        profile: arrangements_for(profile, arrangements)
        for profile in profiles
    }
    for pool in cycles.values():
        rng.shuffle(pool)
    counters = {profile: 0 for profile in cycles}

    width = max(2, len(str(tracks_per_maqam * len(maqams))))
    songs: list[dict] = []
    used_names: set[str] = set()
    index = 0

    for maqam in maqams:
        combos = mood_combinations(
            emotions_by_maqam[maqam], tracks_per_maqam, moods_per_track, rng)
        for moods in combos:
            profile = _profile_for(index, length)
            pool = cycles[profile]
            plan = pool[counters[profile] % len(pool)]
            counters[profile] += 1

            index += 1
            name = (
                f"{index:0{width}d}_{slug(maqam)}_"
                + "_".join(slug(mood) for mood in moods)
            )
            base, suffix = name, 2
            while name in used_names:
                name = f"{base}_{suffix}"
                suffix += 1
            used_names.add(name)

            song: dict = {"name": name}
            if cap is not None:
                song["cap"] = cap
            song["style"] = build_style(
                base_prompt, maqam, moods,
                keep_vocalization=keep_vocalization)
            song["lyrics"] = plan
            songs.append(song)

    return songs


def base_dir_for(out_path: Path) -> str:
    """Manifest ``base_dir`` that points at the repository root."""
    rel = os.path.relpath(ROOT, out_path.parent.resolve())
    return Path(rel).as_posix()


def build_manifest(
    songs: list[dict],
    *,
    repeat: int,
    out_path: Path,
    base_dir: str | None = None,
) -> dict:
    if repeat < 1:
        raise ValueError("repeat must be at least 1")
    return {
        "base_dir": base_dir if base_dir is not None else base_dir_for(out_path),
        "defaults": {
            "repeat": repeat,
            "lora": DEFAULT_LORA,
            "cot": "off",
            "quantile": 0.95,
            "guidance_scale": 1.5,
            "lora_ar_scale": 0.75,
            "lora_nar_scale": 1.0,
            "trigger": False,
        },
        "loras": LORAS,
        "songs": songs,
    }


def next_output_path(directory: Path = MANIFESTS_DIR,
                     stem: str = DEFAULT_STEM) -> Path:
    number = 1
    while (directory / f"{stem}_{number:02d}.json").exists():
        number += 1
    return directory / f"{stem}_{number:02d}.json"


# --------------------------------------------------------------------------
# Interactive prompts
# --------------------------------------------------------------------------

def _ask(prompt: str, default, parser=str, choices=None):
    shown = default
    suffix = f" [{shown}]" if shown not in (None, "") else ""
    while True:
        try:
            raw = input(f"{prompt}{suffix}: ").strip()
        except EOFError:
            print()
            return default
        if not raw:
            return default
        try:
            value = parser(raw)
        except (TypeError, ValueError):
            print(f"  invalid value: {raw!r}")
            continue
        if choices is not None and value not in choices:
            print(f"  choose one of: {', '.join(choices)}")
            continue
        return value


def _ask_cap(default: int | None = DEFAULT_CAP) -> int | None:
    shown = str(default) if default is not None else "none"
    while True:
        try:
            raw = input(f"Token cap [{shown}, or 'none']: ").strip()
        except EOFError:
            print()
            return default
        if not raw:
            return default
        if raw.lower() in {"none", "no", "off", "0"}:
            return None
        try:
            value = int(raw)
        except ValueError:
            value = 0
        if value > 0:
            return value
        print("  enter a positive integer, or 'none'")


def _ask_output(default: Path) -> Path:
    shown = os.path.relpath(default)
    while True:
        try:
            raw = input(f"Output file [{shown}]: ").strip()
        except EOFError:
            print()
            return default
        if not raw:
            return default
        path = Path(raw).expanduser()
        if path.suffix.lower() != ".json":
            path = path.with_suffix(".json")
        return path


def _ask_seed() -> int | None:
    while True:
        try:
            raw = input("Random seed [random]: ").strip()
        except EOFError:
            print()
            return None
        if not raw:
            return None
        try:
            return int(raw)
        except ValueError:
            print("  enter an integer, or leave blank for random")


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a maqam instrumental batch manifest.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Run without flags for the interactive prompts. Values supplied on\n"
            "the command line are not asked again. --yes uses defaults for\n"
            "anything still missing.\n\n"
            "Length profiles count musical sections, not the closing [End]:\n"
            "  short    6-7 sections\n"
            "  standard 8 sections\n"
            "  long     9-10 sections\n"
            "  mixed    cycles short/standard/long"
        ),
    )
    parser.add_argument("--tracks", type=int, metavar="N",
                        help=f"tracks per maqam (default {DEFAULT_TRACKS})")
    parser.add_argument("--repeat", type=int, metavar="N",
                        help=f"takes per song (default {DEFAULT_REPEAT})")
    parser.add_argument("--length", choices=LENGTH_CHOICES,
                        help=f"section-length profile (default {DEFAULT_LENGTH})")
    cap_group = parser.add_mutually_exclusive_group()
    cap_group.add_argument("--cap", type=int, metavar="TOKENS",
                           help=f"token cap (default {DEFAULT_CAP})")
    cap_group.add_argument("--no-cap", action="store_true",
                           help="omit the cap and let quantile 0.95 size the track")
    parser.add_argument("--moods", type=int, default=DEFAULT_MOODS,
                        metavar="N", help="mood tags per song (default 3)")
    parser.add_argument("--seed", type=int,
                        help="seed for mood/arrangement selection (default random)")
    parser.add_argument("--maqams", nargs="+", metavar="NAME",
                        help="subset of maqams, in the order given")
    parser.add_argument("--out", type=Path,
                        help="output manifest (default: next free numbered file)")
    parser.add_argument("--force", action="store_true",
                        help="overwrite --out if it already exists")
    parser.add_argument("--keep-vocalization", action="store_true",
                        help="keep the base prompt's 'vocalization' word")
    parser.add_argument("--yes", "-y", action="store_true",
                        help="do not prompt; use flags and defaults")
    return parser.parse_args(argv)


def _fail(message: str) -> NoReturn:
    raise SystemExit(f"error: {message}")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    interactive = not args.yes

    emotions_by_maqam = load_emotions()
    arrangements = load_arrangements()
    base_prompt = load_base_prompt()

    if args.maqams:
        unknown = [m for m in args.maqams if m not in emotions_by_maqam]
        if unknown:
            _fail(f"unknown maqam(s): {', '.join(unknown)}; "
                  f"known: {', '.join(emotions_by_maqam)}")
        maqams = list(dict.fromkeys(args.maqams))
    else:
        maqams = list(emotions_by_maqam)

    missing_scale = [m for m in maqams if m not in SCALES]
    if missing_scale:
        print(f"note: no Western scale mapping for {', '.join(missing_scale)}; "
              f"the style will carry the maqam name only.", file=sys.stderr)

    if args.tracks is None:
        tracks = (_ask("Tracks per maqam", DEFAULT_TRACKS, int)
                  if interactive else DEFAULT_TRACKS)
    else:
        tracks = args.tracks
    if tracks < 1:
        _fail("--tracks must be at least 1")

    if args.repeat is None:
        repeat = (_ask("Takes per song (repeat)", DEFAULT_REPEAT, int)
                  if interactive else DEFAULT_REPEAT)
    else:
        repeat = args.repeat
    if repeat < 1:
        _fail("--repeat must be at least 1")

    if args.length is None:
        length = (_ask("Length profile", DEFAULT_LENGTH, str.lower, LENGTH_CHOICES)
                  if interactive else DEFAULT_LENGTH)
    else:
        length = args.length

    if args.no_cap:
        cap = None
    elif args.cap is not None:
        cap = args.cap
        if cap < 1:
            _fail("--cap must be at least 1 (or use --no-cap)")
    else:
        cap = _ask_cap(DEFAULT_CAP) if interactive else DEFAULT_CAP

    if args.moods < 1:
        _fail("--moods must be at least 1")
    for maqam in maqams:
        palette_size = len(set(emotions_by_maqam[maqam]))
        if args.moods > palette_size:
            _fail(f"--moods {args.moods} exceeds the {maqam} palette "
                  f"({palette_size} unique emotions)")

    max_unique = min(
        math.comb(len(set(emotions_by_maqam[maqam])), args.moods)
        for maqam in maqams)
    if tracks > max_unique:
        print(f"note: {tracks} tracks/maqam requested, but only {max_unique} "
              f"unique {args.moods}-mood combinations exist; capping.",
              file=sys.stderr)
        tracks = max_unique

    seed = args.seed
    if seed is None and interactive:
        seed = _ask_seed()
    if seed is None:
        # Pick and report one so a batch can be reproduced with --seed.
        seed = random.SystemRandom().randrange(2**32)

    if args.out is not None:
        out_path = args.out.expanduser()
        if out_path.suffix.lower() != ".json":
            out_path = out_path.with_suffix(".json")
        if out_path.exists() and not args.force:
            _fail(f"{out_path} already exists (use --force to overwrite)")
    elif interactive:
        out_path = _ask_output(next_output_path())
    else:
        out_path = next_output_path()

    try:
        songs = build_songs(
            maqams, emotions_by_maqam, arrangements, base_prompt,
            tracks_per_maqam=tracks,
            length=length,
            moods_per_track=args.moods,
            cap=cap,
            seed=seed,
            keep_vocalization=args.keep_vocalization,
        )
    except ValueError as exc:
        _fail(str(exc))

    manifest = build_manifest(songs, repeat=repeat, out_path=out_path)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(f"wrote {out_path} ({len(songs)} songs)")
    print(f"  maqams: {', '.join(maqams)}")
    print(f"  tracks/maqam: {tracks}; repeat: {repeat}; "
          f"length: {length}; cap: {cap if cap is not None else 'none'}; "
          f"seed: {seed}")
    print(f"  validate: python3 generate.py {out_path} --dry-run")
    return 0


if __name__ == "__main__":
    sys.exit(main())
