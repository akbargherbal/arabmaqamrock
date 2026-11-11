#!/usr/bin/env python3
"""Recover `no-abc`/`invalid-abc` transcripts from SheetSage2's own exports.

Failure analysis on the first 460-track run showed two deterministic exporter
edge cases, not audio/model failures:

* a sub-beat melody note at the very end of a track cannot be quantised
  (``MelodyVoiceError ... pitch=P at t0-t1``);
* one dropped beat row makes a measure non-consecutive
  (``BeatGridError ... non-consecutive beat IDs``).

Both are repaired *in a temporary copy* of the ``notation/`` export and the
ABC is regenerated with the model's own ``generate_abc_from_exports``.  The
original transcript directory and meta are preserved; the recovered meta gets
``recovered: true``, ``recovery_method`` and ``original_status``/``original_error``.

This is a salvage path for exporter bugs, not a re-transcription.  Tracks that
cannot be recovered stay failed and are reported as ``missing-output``.

Run with the SheetSage2 venv (needs pretty_midi):

    .venv-sheetsage2/bin/python plumbing/recover_yt500_abc.py \
        --transcripts /content/yt500/transcripts
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import re
import shutil
import sys
import tempfile
import time
from pathlib import Path

HF_REVISION = "b83c3d79a6d98bcffaf8f9ed112c90aa887887bc"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def load_notation_module():
    """Import the model's own notation module from the HF cache."""
    candidates = sorted(Path.home().glob(
        "**/models--m-a-p--SheetSage2/snapshots/*/notation_sheetsage2.py"),
        key=lambda p: p.parent.name)
    if not candidates:
        from huggingface_hub import snapshot_download
        snap = Path(snapshot_download("m-a-p/SheetSage2", revision=HF_REVISION))
        candidates = [snap / "notation_sheetsage2.py"]
    chosen = None
    for c in candidates:
        if c.parent.name == HF_REVISION:
            chosen = c
            break
    src = chosen or candidates[-1]
    pkg_root = Path(tempfile.mkdtemp(prefix="ss2pkg_"))
    pkg = pkg_root / "ss2pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    for f in src.parent.glob("*.py"):
        dest = pkg / f.name
        if dest.exists() or dest.is_symlink():
            continue  # __init__.py already materialised above
        dest.symlink_to(f)
    sys.path.insert(0, str(pkg_root))
    return importlib.import_module("ss2pkg.notation_sheetsage2"), src.parent.name


def copy_notation(tdir: Path, dest: Path) -> Path | None:
    src = tdir / "notation"
    if not src.is_dir():
        return None
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest)
    return dest / "song_melody.mid"


def drop_note(midi_path: Path, pitch: int, start: float, end: float) -> bool:
    import pretty_midi
    mid = pretty_midi.PrettyMIDI(str(midi_path))
    removed = 0
    for inst in mid.instruments:
        keep = []
        for n in inst.notes:
            if (n.pitch == pitch and abs(n.start - start) < 1e-4
                    and abs(n.end - end) < 1e-4):
                removed += 1
                continue
            keep.append(n)
        inst.notes = keep
    if removed:
        mid.write(str(midi_path))
    return bool(removed)


def repair_beats(beat_path: Path) -> int:
    """Insert missing sequential beat IDs inside a measure.

    A new measure starts at ID 1, so a jump to 1 is never filled.  A jump such
    as 1 -> 3 is one dropped row (ID 2); the inserted row is linearly spaced.
    """
    lines = [l for l in beat_path.read_text().splitlines() if l.strip()]
    out, inserted = [], 0
    for line in lines:
        parts = line.split()
        if len(parts) >= 2 and out:
            prev = out[-1].split()
            try:
                pid, cid = int(prev[1]), int(parts[1])
                t, pt = float(parts[0]), float(prev[0])
            except (ValueError, IndexError):
                pid = cid = 0
            if cid != 1 and cid > pid + 1:
                gap = cid - pid
                for j, exp in enumerate(range(pid + 1, cid), 1):
                    it = pt + (t - pt) * j / gap
                    out.append(f"{it}\t{exp}\t{prev[2]}\t{prev[3]}")
                    inserted += 1
        out.append(line)
    if inserted:
        beat_path.write_text("\n".join(out) + "\n")
    return inserted


NOTE_ERR = re.compile(r"pitch=(\d+) at ([\d.]+)-([\d.]+)")
BEAT_ERR = re.compile(r"non-consecutive beat IDs")
OVERLAP_ERR = re.compile(r"overlapping quantized melody notes")


def recover_one(tdir: Path, notation, work_root: Path) -> tuple[bool, str]:
    meta = read_json(tdir / "meta.json")
    if metadata_ok(tdir, meta):
        return False, "already-ok"
    tmp = work_root / tdir.name
    midi = copy_notation(tdir, tmp)
    if midi is None:
        return False, "no notation exports"

    def attempt() -> tuple[str | None, Exception | None]:
        try:
            text, _score, _paths = notation.generate_abc_from_exports(
                str(midi), output_path=str(tmp / "recovered.abc"),
                melody_only=False, meter_conflict="infer")
            return text, None
        except Exception as exc:  # noqa: BLE001
            return None, exc

    method = []
    text, err = attempt()
    for _ in range(12):
        if text is not None:
            break
        msg = str(err)
        m = NOTE_ERR.search(msg)
        if m:
            pitch, t0, t1 = int(m.group(1)), float(m.group(2)), float(m.group(3))
            if drop_note(midi, pitch, t0, t1):
                method.append(f"drop.tail-note(pitch={pitch})")
                text, err = attempt()
                continue
        if BEAT_ERR.search(msg):
            n = repair_beats(tmp / "song_beats.txt")
            if n:
                method.append(f"fill.beat-rows(+{n})")
                text, err = attempt()
                continue
        if OVERLAP_ERR.search(msg):
            method.append("unrecoverable.overlap")
        break

    if text is None:
        return False, f"{type(err).__name__}: {str(err)[:160]}"
    if not text.strip():
        return False, "exporter returned empty ABC"

    abc = tdir / "score.abc"
    abc.write_text(text, encoding="utf-8")
    if (tdir / "meta.json").is_file() and not (tdir / "meta.pre-recovery.json").is_file():
        shutil.copy2(tdir / "meta.json", tdir / "meta.pre-recovery.json")
    old = meta or {}
    new = dict(old)
    new.update({
        "status": "ok",
        "abc": "score.abc",
        "abc_sha256": sha256_file(abc),
        "abc_bytes": abc.stat().st_size,
        "recovered": True,
        "recovery_method": ";".join(method) or "direct-reexport",
        "original_status": old.get("status"),
        "original_error": old.get("error"),
        "recovered_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    })
    new.pop("error", None)
    (tdir / "meta.json").write_text(
        json.dumps(new, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return True, new["recovery_method"]


def metadata_ok(tdir: Path, meta: dict | None) -> bool:
    if not meta or meta.get("status") != "ok":
        return False
    abc = tdir / "score.abc"
    return abc.is_file() and meta.get("abc_sha256") == sha256_file(abc)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--transcripts", default="/content/yt500/transcripts")
    ap.add_argument("--report", default="/content/arabmaqamrock/logs/yt500_abc/recovery_report.json")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args(argv)
    root = Path(args.transcripts)
    notation, snapshot = load_notation_module()
    work_root = Path(tempfile.mkdtemp(prefix="yt500_recovery_"))
    rows, done = [], 0
    for tdir in sorted(p for p in root.iterdir() if p.is_dir()):
        meta = read_json(tdir / "meta.json")
        if meta is None or metadata_ok(tdir, meta):
            continue
        if meta.get("status") not in ("no-abc", "invalid-abc"):
            # Do not salvage timeouts/failed runs: their exports may be partial.
            continue
        done += 1
        if args.limit and done > args.limit:
            break
        ok, why = recover_one(tdir, notation, work_root)
        rows.append({"name": tdir.name, "recovered": ok, "detail": why})
        if ok:
            print(f"recovered {tdir.name}: {why}", flush=True)
        else:
            print(f"skip {tdir.name}: {why}", flush=True)
    report = {"utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
              "snapshot": snapshot, "attempted": len(rows),
              "recovered": sum(r["recovered"] for r in rows), "rows": rows}
    Path(args.report).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report).write_text(json.dumps(report, indent=2))
    print(json.dumps({k: report[k] for k in ("attempted", "recovered", "snapshot")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
