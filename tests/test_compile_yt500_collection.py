"""CPU tests for plumbing/compile_yt500_collection.py.

No network, no audio: a three-row metadata tree plus a fake caption album are
written to a temp dir.  The tests cover the attach guards (empty caption, seed
mismatch, missing name, short caption, failed rewrite) and the two properties
the pipeline depends on: a second attach is byte identical, and a tampered
caption.txt fails ``--verify``.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "compile_yt500_collection", ROOT / "plumbing" / "compile_yt500_collection.py"
)
assert SPEC and SPEC.loader
compiler = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(compiler)

NAMES = [
    ("yt500-0001-abc_DEF1234", 111),
    ("yt500-0002-XY_Z-9876", 222),
    ("yt500-0003-qq-_WXyZ9", 333),
]
CAPTION = (
    "A warm acoustic ensemble opens with plucked oud over a steady frame drum, "
    "the violin answering in call and response while a fretted bass holds the "
    "root. The arrangement swells into a cinematic chorus, then settles back "
    "into a close-miked, reverb-washed outro with hand percussion."
)


def _row(name: str, rank: int, seed: int) -> dict:
    video_id = name.split("-", 2)[2]
    return {
        "name": name,
        "rank": rank,
        "video_id": video_id,
        "title": f"Title {rank}",
        "artist": "Artist",
        "country": "Lebanon",
        "tier": "Tier 1",
        "gate": "pass",
        "nominal_s": 200.0,
        "wav_s": 201.0,
        "delta_pct": 0.5,
        "sections": ["intro", "verse", "outro"],
        "artifacts": {
            "audio": "audio.mp3",
            "lyrics": "lyrics.txt",
            "style": "style.txt",
            "score": "score.abc",
        },
        "generation": {
            "run": "20261110-000000_yt500inst",
            "seed": seed,
            "cap": 1000,
            "engine": "batch",
            "status": "ok",
            "exit": 0,
            "end_utc": "2026-11-10T10:00:00Z",
        },
        "lyrics": {"kind": "section_tags", "sha256": "a" * 64,
                   "text": "[intro]\n[verse]\n[outro]"},
        "style": {"sha256": "b" * 64, "id": "manifest18"},
        "recipe": {"cot": "full"},
        "score": {"abc_sha256": "c" * 64, "source": "gs://bucket/x.abc"},
        "audio": {"mp3_bytes": 1, "mp3_sha256": None,
                  "source": "gs://bucket/x.mp3", "wav_sha256": "d" * 64},
        "provenance": {"audit_bucket": "pass", "takes": [f"{name}_{seed}"]},
    }


def _album_track(name: str, seed: int, caption: str = CAPTION,
                 status: str = "ok") -> dict:
    return {
        "file": f"{name}_{seed}.mp3",
        "duration_s": 201.0,
        "bitrate_kbps": 192,
        "chunk_count": 2,
        "silence_trimmed_s": 0.0,
        "caption": caption,
        "caption_raw": caption,
        "chunk_captions": [caption[:150], caption[150:]],
        "instruments": ["oud", "frame drum"],
        "vocals": [],
        "production": ["reverb", "close-miked"],
        "rewrite_status": status,
        "tags_experimental": True,
        "rewrite_seconds": 1.0,
        "rewrite_model": "gguf:test",
        "rewrite_prompt_version": 2,
    }


def _write_tree(tmp: Path, overrides: dict | None = None) -> Path:
    root = tmp / "dataset"
    rows = []
    for rank, (name, seed) in enumerate(NAMES, start=1):
        row = _row(name, rank, seed)
        rows.append(row)
        track_dir = root / "tracks" / name
        track_dir.mkdir(parents=True)
        (track_dir / "track.json").write_text(
            json.dumps(row, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    compiler.write_catalogs(rows, root)
    manifest = {
        "dataset": "test",
        "dataset_version": "v0.1",
        "generated_at": "2026-11-11T00:00:00Z",
        "gate": compiler.GATE_EXPR,
        "counts": {"tracks": len(rows), "pass": len(rows), "accepted": 0,
                   "audio_bytes": 3, "unique_lyrics_plans": 1, "unique_styles": 1},
        "layout": {"per_track": "tracks/<name>/track.json",
                   "catalog": "catalog.jsonl"},
        "files": [],
    }
    (root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    doc = "# Test collection\n\n## Layout\n\n```\n" + compiler.LAYOUT_OLD + "```\n\n## Recipe\n\nfixed\n"
    (root / "README.md").write_text(doc, encoding="utf-8")
    (root / "DATASET_CARD.md").write_text(doc, encoding="utf-8")
    return root


def _write_album(tmp: Path, mutate=None) -> Path:
    tracks = [_album_track(name, seed) for name, seed in NAMES]
    if mutate:
        mutate(tracks)
    album = {
        "artist": "arabmaqamrock",
        "album": "YT500_INSTRUMENTAL",
        "generated_at": "2026-11-11T01:00:00Z",
        "caption_pipeline_version": 3,
        "caption_stage": "polished",
        "tracks": tracks,
    }
    path = tmp / "album.json"
    path.write_text(json.dumps(album, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _attach(root: Path, album: Path, *extra: str) -> int:
    return compiler.main(["--local", str(root), "--captions", str(album),
                          "--attach-captions", "--no-audio", *extra])


def _verify(root: Path, *extra: str) -> int:
    return compiler.main(["--local", str(root), "--verify", *extra])


def _tree_bytes(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*")) if path.is_file()
    }


def test_attach_writes_chain_and_verifies(tmp_path):
    root = _write_tree(tmp_path)
    album = _write_album(tmp_path)
    assert _attach(root, album) == 0
    assert _verify(root) == 0

    first = json.loads((root / "tracks" / NAMES[0][0] / "caption.json").read_text())
    text_sha = hashlib.sha256(
        (root / "tracks" / NAMES[0][0] / "caption.txt").read_bytes()).hexdigest()
    assert first["schema"] == "yt500-caption/1"
    assert first["take"]["file"] == f"{NAMES[0][0]}_{NAMES[0][1]}.mp3"
    assert first["caption_sha256"] == text_sha
    assert first["pipeline"]["version"] == 3
    assert first["tags"]["instruments"] == ["oud", "frame drum"]

    catalog = [json.loads(line) for line in (root / "catalog.jsonl").read_text().splitlines()]
    assert all(row["caption_sha256"] == first["caption_sha256"] or
               len(row["caption_sha256"]) == 64 for row in catalog)
    manifest = json.loads((root / "manifest.json").read_text())
    assert manifest["dataset_version"] == "v0.2"
    assert manifest["counts"]["captions"] == len(NAMES)
    assert manifest["captions"]["pipeline_version"] == 3
    assert (root / "captions.jsonl").read_text().count("\n") == 2 * len(NAMES)
    assert (root / "_SUCCESS").read_text().count("captions=3") == 1


def test_empty_caption_is_rejected(tmp_path, capsys):
    root = _write_tree(tmp_path)
    album = _write_album(tmp_path, lambda ts: ts[0].update(caption=""))
    assert _attach(root, album) == 1
    assert "empty caption" in capsys.readouterr().err
    assert not (root / "tracks" / NAMES[0][0] / "caption.txt").exists()


def test_seed_mismatch_is_rejected(tmp_path, capsys):
    row = _row(NAMES[0][0], 1, NAMES[0][1])
    wrong = _album_track(NAMES[0][0], 999)
    with pytest.raises(compiler.CaptionError) as exc:
        compiler.caption_record(row, wrong)
    assert "expected" in str(exc.value)

    root = _write_tree(tmp_path)
    album = _write_album(
        tmp_path, lambda ts: ts[0].update(file=f"{NAMES[0][0]}_999.mp3"))
    assert _attach(root, album) == 1
    assert "no caption for take" in capsys.readouterr().err


def test_missing_track_is_fatal_unless_allowed(tmp_path, capsys):
    root = _write_tree(tmp_path)
    album = _write_album(tmp_path, lambda ts: ts.pop(0))
    assert _attach(root, album) == 1
    assert "no caption for take" in capsys.readouterr().err
    assert _attach(root, album, "--allow-missing-captions") == 0
    assert not (root / "tracks" / NAMES[0][0] / "caption.txt").exists()
    assert _verify(root, "--allow-missing-captions") == 0


def test_short_caption_floor(tmp_path, capsys):
    root = _write_tree(tmp_path)
    album = _write_album(tmp_path, lambda ts: ts[0].update(caption="too short"))
    assert _attach(root, album) == 1
    assert "below --min-caption-chars" in capsys.readouterr().err
    assert _attach(root, album, "--min-caption-chars", "5") == 0


def test_failed_rewrite_needs_flag_and_is_flagged(tmp_path, capsys):
    root = _write_tree(tmp_path)
    album = _write_album(tmp_path, lambda ts: ts[0].update(rewrite_status="failed"))
    assert _attach(root, album) == 1
    assert "allow-unpolished" in capsys.readouterr().err
    assert _attach(root, album, "--allow-unpolished") == 0
    record = json.loads((root / "tracks" / NAMES[0][0] / "caption.json").read_text())
    assert record["unpolished"] is True
    assert record["rewrite"]["status"] == "failed"
    track = json.loads((root / "tracks" / NAMES[0][0] / "track.json").read_text())
    assert track["caption"]["unpolished"] is True
    assert _verify(root) == 1
    assert _verify(root, "--allow-unpolished") == 0


def test_second_attach_is_byte_identical(tmp_path):
    root = _write_tree(tmp_path)
    album = _write_album(tmp_path, lambda ts: ts[0].update(rewrite_status="failed"))
    assert _attach(root, album, "--allow-unpolished") == 0
    first = _tree_bytes(root)
    assert _attach(root, album, "--allow-unpolished") == 0
    assert _tree_bytes(root) == first


def test_tampered_caption_fails_verify(tmp_path):
    root = _write_tree(tmp_path)
    album = _write_album(tmp_path)
    assert _attach(root, album) == 0
    target = root / "tracks" / NAMES[1][0] / "caption.txt"
    target.write_text(target.read_text() + "tampered\n", encoding="utf-8")
    assert _verify(root) == 1


def test_build_reproduces_catalogs(tmp_path):
    root = _write_tree(tmp_path)
    before = {name: (root / name).read_bytes()
              for name in ("catalog.jsonl", "tracks.jsonl", "catalog.csv",
                           "catalog.md", "playlist.m3u", "README.md")}
    assert compiler.main(["--local", str(root), "--build"]) == 0
    after = {name: (root / name).read_bytes() for name in before}
    assert after == before


def test_timestamp_caption_is_rejected(tmp_path, capsys):
    root = _write_tree(tmp_path)
    album = _write_album(tmp_path, lambda ts: ts[0].update(
        caption=CAPTION + " [00:42] the drums drop out."))
    assert _attach(root, album) == 1
    assert "time reference" in capsys.readouterr().err
