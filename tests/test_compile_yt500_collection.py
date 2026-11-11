"""CPU tests for the caption attach mode of compile_yt500_collection.py.

No network, no audio.  A three-row metadata tree and a fake caption album are
written to a temp dir; ``INDEX``/``AUDIT`` are pointed at tiny fixtures so
``--verify`` re-derives the same three names.  Covers the attach guards (empty
caption, seed mismatch, missing take, timestamp, failed rewrite), idempotency,
the hash chain, and the publish no-audio guard.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "compile_yt500_collection", ROOT / "plumbing" / "compile_yt500_collection.py")
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
STYLE = "test style prompt, no audience"
COUNTRY = "Lebanon"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _row(name: str, rank: int, seed: int, style_sha: str) -> dict:
    return {
        "name": name,
        "rank": rank,
        "video_id": name.split("-", 2)[2],
        "title": f"Title {rank}",
        "artist": "Artist",
        "country": COUNTRY,
        "tier": "Tier 1",
        "gate": "pass",
        "nominal_s": 200.0,
        "wav_s": 201.0,
        "delta_pct": 0.5,
        "sections": ["intro", "verse", "outro"],
        "artifacts": {"audio": "audio.mp3", "lyrics": "lyrics.txt",
                      "style": "style.txt", "score": "score.abc"},
        "generation": {"run": "20261110-000000_yt500inst", "seed": seed,
                       "cap": 1000, "engine": "batch", "status": "ok",
                       "exit": 0, "end_utc": "2026-11-10T10:00:00Z"},
        "lyrics": {"kind": "section_tags", "sha256": "", "text": ""},
        "style": {"sha256": style_sha, "id": "manifest18"},
        "recipe": {"cot": "full"},
        "score": {"abc_sha256": "", "source": "gs://bucket/x.abc"},
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


def _write_tree(tmp_path: Path) -> Path:
    root = tmp_path / "dataset"
    style_sha = _sha(STYLE.encode())
    rows = []
    for rank, (name, seed) in enumerate(NAMES, start=1):
        row = _row(name, rank, seed, style_sha)
        lyrics = "[intro]\n[verse]\n[outro]\n"
        row["lyrics"]["text"] = lyrics
        row["lyrics"]["sha256"] = _sha(lyrics.encode())
        abc = f"X:1\nT:{name}\nK:C\nCDEF GABc|\n"
        row["score"]["abc_sha256"] = _sha(abc.encode())
        rows.append(row)
        tdir = root / "tracks" / name
        tdir.mkdir(parents=True)
        (tdir / "lyrics.txt").write_text(lyrics, encoding="utf-8")
        (tdir / "style.txt").write_text(STYLE, encoding="utf-8")
        (tdir / "score.abc").write_text(abc, encoding="utf-8")
        (tdir / "track.json").write_text(
            json.dumps(row, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    recipe = {
        "style_sha256": style_sha,
        "source": "manifests/test.json defaults.style",
        "defaults": {"style": STYLE, "cot": "full", "lora": "instrumental_v9",
                     "lora_ar_scale": 0.85, "lora_nar_scale": 1.0,
                     "trigger": False},
        "loras": {},
        "model": "Yue2-3B-GGUF",
    }
    (root / "recipe").mkdir()
    (root / "recipe" / "style.txt").write_text(STYLE, encoding="utf-8")
    (root / "recipe" / "recipe.json").write_text(
        json.dumps(recipe, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (root / "manifest.json").write_text(json.dumps({
        "dataset": "test",
        "dataset_version": "v0.1",
        "generated_at": "2026-11-11T00:00:00Z",
        "counts": {"tracks": len(rows), "pass": len(rows), "accepted": 0},
        "layout": {"per_track": "tracks/<name>/track.json"},
        "files": [],
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return root


def _write_album(tmp_path: Path, mutate=None) -> Path:
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
    path = tmp_path / "album.json"
    path.write_text(json.dumps(album, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


@pytest.fixture()
def tiny_indexes(tmp_path: Path, monkeypatch):
    index = {"tracks": [{"name": name, "generation_status": "ready",
                         "source_rank": rank}
                        for rank, (name, _) in enumerate(NAMES, start=1)]}
    audit = {"tracks": []}
    index_path, audit_path = tmp_path / "index.json", tmp_path / "audit.json"
    index_path.write_text(json.dumps(index), encoding="utf-8")
    audit_path.write_text(json.dumps(audit), encoding="utf-8")
    monkeypatch.setattr(compiler, "INDEX", index_path)
    monkeypatch.setattr(compiler, "AUDIT", audit_path)
    return index_path, audit_path


def _attach(root: Path, album: Path, *extra: str) -> int:
    return compiler.main(["--local", str(root), "--captions", str(album),
                          "--attach-captions", *extra])


def _verify(root: Path, *extra: str) -> int:
    return compiler.main(["--local", str(root), "--verify", *extra])


def _tree(root: Path) -> dict[str, str]:
    return {str(p.relative_to(root)): _sha(p.read_bytes())
            for p in sorted(root.rglob("*")) if p.is_file()}


def test_attach_writes_chain_and_verifies(tmp_path, tiny_indexes):
    root = _write_tree(tmp_path)
    album = _write_album(tmp_path)
    assert _attach(root, album) == 0
    assert _verify(root) == 0

    name = NAMES[0][0]
    record = json.loads((root / "tracks" / name / "caption.json").read_text())
    text_sha = _sha((root / "tracks" / name / "caption.txt").read_bytes())
    assert record["schema"] == "yt500-caption/1"
    assert record["take"] == {"file": f"{name}_{NAMES[0][1]}.mp3",
                              "seed": NAMES[0][1],
                              "run": "20261110-000000_yt500inst"}
    assert record["caption_sha256"] == text_sha
    assert record["pipeline"]["version"] == 3
    assert record["instruments"] == ["oud", "frame drum"]
    assert record["tags_experimental"] is True

    track = json.loads((root / "tracks" / name / "track.json").read_text())
    assert track["caption"]["sha256"] == text_sha
    assert track["caption"]["take"] == f"{name}_{NAMES[0][1]}"
    assert track["artifacts"]["caption"] == "caption.json"
    assert track["artifacts"]["caption_text"] == "caption.txt"

    catalog = [json.loads(line) for line in
               (root / "catalog.jsonl").read_text().splitlines()]
    assert catalog[0]["caption_sha256"] == text_sha
    assert catalog[0]["rewrite_status"] == "ok"
    manifest = json.loads((root / "manifest.json").read_text())
    assert manifest["dataset_version"] == "v0.2"
    assert manifest["counts"]["captions"] == len(NAMES)
    assert manifest["captions"]["pipeline_version"] == 3
    assert "caption.txt" in manifest["layout"]["per_track"]
    assert (root / "captions.jsonl").read_text().count("\n") == len(NAMES)
    assert (root / "captions.sha256").read_text().count("\n") == 2 * len(NAMES)
    assert "caption.txt" in (root / "README.md").read_text()


def test_empty_caption_is_rejected(tmp_path, tiny_indexes):
    root = _write_tree(tmp_path)
    album = _write_album(tmp_path, lambda ts: ts[0].update(caption=""))
    with pytest.raises(SystemExit, match="empty caption"):
        _attach(root, album)
    assert not (root / "tracks" / NAMES[0][0] / "caption.txt").exists()


def test_seed_mismatch_is_rejected(tmp_path, tiny_indexes):
    root = _write_tree(tmp_path)
    album = _write_album(tmp_path, lambda ts: ts[0].update(
        file=f"{NAMES[0][0]}_999.mp3"))
    with pytest.raises(SystemExit, match="no caption for its take"):
        _attach(root, album)


def test_missing_take_is_fatal_unless_allowed(tmp_path, tiny_indexes):
    root = _write_tree(tmp_path)
    album = _write_album(tmp_path, lambda ts: ts.pop(0))
    with pytest.raises(SystemExit, match="no caption for its take"):
        _attach(root, album)
    assert _attach(root, album, "--allow-missing-captions") == 0
    assert not (root / "tracks" / NAMES[0][0] / "caption.txt").exists()
    assert _verify(root, "--allow-missing-captions") == 0


def test_timestamp_caption_is_rejected(tmp_path, tiny_indexes):
    root = _write_tree(tmp_path)
    album = _write_album(tmp_path, lambda ts: ts[0].update(
        caption=CAPTION + " At 01:42 the drums drop out."))
    with pytest.raises(SystemExit, match="time reference"):
        _attach(root, album)


def test_failed_rewrite_needs_flag_and_is_flagged(tmp_path, tiny_indexes):
    root = _write_tree(tmp_path)
    album = _write_album(tmp_path, lambda ts: ts[0].update(rewrite_status="failed"))
    with pytest.raises(SystemExit, match="allow-unpolished"):
        _attach(root, album)
    assert _attach(root, album, "--allow-unpolished") == 0
    record = json.loads((root / "tracks" / NAMES[0][0] / "caption.json").read_text())
    assert record["unpolished"] is True
    assert record["rewrite"]["status"] == "failed"
    manifest = json.loads((root / "manifest.json").read_text())
    assert manifest["captions"]["unpolished"] == [NAMES[0][0]]
    assert manifest["counts"]["captions_unpolished"] == 1
    assert _verify(root) == 1
    assert _verify(root, "--allow-unpolished") == 0


def test_second_attach_is_byte_identical(tmp_path, tiny_indexes):
    root = _write_tree(tmp_path)
    album = _write_album(tmp_path, lambda ts: ts[0].update(rewrite_status="failed"))
    assert _attach(root, album, "--allow-unpolished") == 0
    first = _tree(root)
    assert _attach(root, album, "--allow-unpolished") == 0
    assert _tree(root) == first


def test_tampered_caption_fails_verify(tmp_path, tiny_indexes):
    root = _write_tree(tmp_path)
    album = _write_album(tmp_path)
    assert _attach(root, album) == 0
    target = root / "tracks" / NAMES[1][0] / "caption.txt"
    target.write_text(target.read_text() + "tampered\n", encoding="utf-8")
    assert _verify(root) == 1


def test_publish_refuses_audio_in_tree(tmp_path, tiny_indexes):
    root = _write_tree(tmp_path)
    album = _write_album(tmp_path)
    assert _attach(root, album) == 0
    (root / "tracks" / NAMES[0][0] / "audio.mp3").write_bytes(b"not audio")
    with pytest.raises(SystemExit, match="audio.mp3"):
        compiler.main(["--local", str(root), "--publish", "--no-audio", "--dry-run"])


def test_publish_no_audio_dry_run(tmp_path, tiny_indexes, capsys):
    root = _write_tree(tmp_path)
    album = _write_album(tmp_path)
    assert _attach(root, album) == 0
    assert compiler.main(["--local", str(root), "--publish", "--no-audio",
                          "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "would not copy audio" in out
