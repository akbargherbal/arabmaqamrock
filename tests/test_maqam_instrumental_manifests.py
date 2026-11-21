#!/usr/bin/env python3
"""CPU tests for plumbing/maqam_instrumental_manifests.py.

No GPU, no network, no audio: the source documents are the real ones in
docs/misc/instrumental_music/, and every generated manifest is written to a
temporary directory.
"""

from __future__ import annotations

import importlib.util
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "maqam_instrumental_manifests",
    ROOT / "plumbing" / "maqam_instrumental_manifests.py",
)
assert SPEC and SPEC.loader
gen = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gen)

REFERENCE = ROOT / "manifests" / "maqam_instrumental_songs_03.json"


def _load_manifest(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_section_count_ignores_end_marker():
    assert gen.section_count("[intro]\n[verse]\n[outro]\n[End]") == 3
    assert gen.section_count("[intro]\n[verse]\n[outro]") == 3
    assert gen.section_count("[End]") == 0


def test_length_profiles_select_expected_plans():
    plans = gen.load_arrangements()
    short = gen.arrangements_for("short", plans)
    standard = gen.arrangements_for("standard", plans)
    long = gen.arrangements_for("long", plans)

    assert short and all(6 <= gen.section_count(p) <= 7 for p in short)
    assert standard and all(gen.section_count(p) == 8 for p in standard)
    assert long and all(9 <= gen.section_count(p) <= 10 for p in long)
    assert len(gen.arrangements_for("mixed", plans)) == len(plans)


def test_mood_combinations_are_unique_and_cover_palette():
    emotions = gen.load_emotions()["Hijaz"]
    rng = random.Random(11)
    combos = gen.mood_combinations(emotions, 12, 3, rng)

    assert len(combos) == 12
    assert len(set(combos)) == 12
    assert all(len(c) == 3 for c in combos)
    assert all(len(set(c)) == 3 for c in combos)
    assert all(set(c) <= set(emotions) for c in combos)
    # One anchor per emotion until the palette runs out.
    assert len({c[0] for c in combos}) == 12


def test_mood_combinations_cap_at_palette_size():
    emotions = ["a", "b", "c", "d"]
    combos = gen.mood_combinations(emotions, 100, 3, random.Random(0))
    assert len(combos) == 4  # C(4, 3)


def test_build_style_matches_reference_caption():
    base = gen.load_base_prompt()
    style = gen.build_style(
        base, "Hijaz", ("yearning", "nostalgic", "deeply sorrowful"))
    reference = _load_manifest(REFERENCE)["songs"][0]["style"]
    expected = reference.replace("no vocals, no singing", "vocalization")
    assert style == expected


def test_build_style_preserves_vocalization():
    base = gen.load_base_prompt()
    style = gen.build_style(base, "Hijaz", ("yearning", "nostalgic", "aching"))
    assert "vocalization" in style
    assert "no vocals, no singing" not in style


def test_build_style_unknown_maqam_has_no_double_comma():
    base = gen.load_base_prompt()
    style = gen.build_style(base, "Rast", ("calm", "warm", "open"))
    assert "Maqam Rast, mood:" in style
    assert ", ," not in style


def test_manifest_shape_matches_reference(tmp_path):
    out = tmp_path / "maqam.json"
    songs = gen.build_songs(
        ["Hijaz", "Kurd"],
        gen.load_emotions(),
        gen.load_arrangements(),
        gen.load_base_prompt(),
        tracks_per_maqam=3,
        length="mixed",
        cap=8500,
        seed=5,
    )
    manifest = gen.build_manifest(songs, repeat=1, out_path=out)
    reference = _load_manifest(REFERENCE)

    assert set(manifest) == set(reference)
    assert manifest["defaults"] == reference["defaults"]
    assert manifest["loras"] == reference["loras"]
    assert len(manifest["songs"]) == 6
    assert all(set(song) == {"name", "cap", "style", "lyrics"}
               for song in manifest["songs"])
    assert all(song["cap"] == 8500 for song in manifest["songs"])
    assert len({song["name"] for song in manifest["songs"]}) == 6


def test_cli_writes_valid_manifest_and_length_profiles(tmp_path):
    out = tmp_path / "short.json"
    assert gen.main(["--yes", "--tracks", "4", "--length", "short",
                     "--seed", "3", "--out", str(out)]) == 0
    manifest = _load_manifest(out)
    assert len(manifest["songs"]) == 16
    assert all(6 <= gen.section_count(s["lyrics"]) <= 7
               for s in manifest["songs"])
    assert manifest["base_dir"] == gen.base_dir_for(out)

    for profile, check in (
        ("standard", lambda n: n == 8),
        ("long", lambda n: 9 <= n <= 10),
    ):
        path = tmp_path / f"{profile}.json"
        assert gen.main(["--yes", "--tracks", "2", "--length", profile,
                         "--seed", "3", "--out", str(path)]) == 0
        songs = _load_manifest(path)["songs"]
        assert all(check(gen.section_count(s["lyrics"])) for s in songs)


def test_cli_mixed_cycles_short_standard_long(tmp_path):
    out = tmp_path / "mixed.json"
    assert gen.main(["--yes", "--tracks", "3", "--length", "mixed",
                     "--seed", "1", "--out", str(out)]) == 0
    songs = _load_manifest(out)["songs"]
    # 3 tracks/maqam and a 3-profile cycle means each maqam gets one of each.
    counts = [gen.section_count(s["lyrics"]) for s in songs]
    assert all(6 <= counts[i] <= 7 for i in range(0, 12, 3))
    assert all(counts[i] == 8 for i in range(1, 12, 3))
    assert all(9 <= counts[i] <= 10 for i in range(2, 12, 3))


def test_cli_no_cap_omits_cap(tmp_path):
    out = tmp_path / "nocap.json"
    assert gen.main(["--yes", "--tracks", "2", "--no-cap",
                     "--out", str(out)]) == 0
    assert all("cap" not in song for song in _load_manifest(out)["songs"])


def test_cli_maqam_subset_and_order(tmp_path):
    out = tmp_path / "subset.json"
    assert gen.main(["--yes", "--tracks", "1", "--maqams", "Kurd", "Hijaz",
                     "--out", str(out)]) == 0
    songs = _load_manifest(out)["songs"]
    assert [s["name"].split("_", 1)[1].split("_")[0] for s in songs] == [
        "kurd", "hijaz"]


def test_cli_refuses_to_overwrite_without_force(tmp_path):
    out = tmp_path / "exists.json"
    out.write_text("{}", encoding="utf-8")
    try:
        gen.main(["--yes", "--tracks", "1", "--out", str(out)])
    except SystemExit as exc:
        assert "--force" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected SystemExit")
    assert gen.main(["--yes", "--tracks", "1", "--out", str(out),
                     "--force"]) == 0
    assert _load_manifest(out)["songs"]


def test_same_seed_is_deterministic(tmp_path):
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    args = ["--yes", "--tracks", "5", "--length", "mixed", "--seed", "99"]
    assert gen.main([*args, "--out", str(first)]) == 0
    assert gen.main([*args, "--out", str(second)]) == 0
    assert first.read_text(encoding="utf-8") == second.read_text(encoding="utf-8")
