#!/usr/bin/env python3
"""Offline tests for the YT500 resume/batch driver. No GPU, no network."""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
import wave
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "plumbing"))

import run_yt500_generation as driver  # noqa: E402


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def make_wav(path: Path, seconds: float = 6.0) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(8000)
        w.writeframes(b"\x00\x00" * int(8000 * seconds))
    return path


def make_corpus(names: list[str]) -> dict:
    return {
        "data": {
            "base_dir": "..",
            "loras": {"instrumental_v9": {"ar": "ar", "nar": "nar"}},
            "scores": {n: f"scores/{n}.abc" for n in names},
            "defaults": {"lora": "instrumental_v9", "cot": "full"},
            "songs": [{"name": n, "score": n} for n in names],
        },
        "base": Path("/repo"),
        "names": names,
        "score_paths": {n: Path(f"/repo/scores/{n}.abc") for n in names},
        "score_hashes": {n: sha(n) for n in names},
        "songs": {n: {"name": n} for n in names},
    }


class ScanDoneTest(unittest.TestCase):
    def test_success_marker_counts_and_failure_does_not(self):
        with tempfile.TemporaryDirectory() as td:
            meta = Path(td)
            run = meta / "20260101_yt500inst"
            run.mkdir()
            names = ["a", "b"]
            corpus = make_corpus(names)
            (run / "batch_manifest.json").write_text(json.dumps({
                "tracks": [
                    {"name": "a", "seed": 7, "abc_sha256": corpus["score_hashes"]["a"]},
                    {"name": "b", "seed": 8, "abc_sha256": corpus["score_hashes"]["b"]},
                ]}))
            (run / "a_7_time.txt").write_text("Exit status: 0\n")
            (run / "b_8_time.txt").write_text("Exit status: 1\n")
            done, per_run, mismatches = driver.scan_done(meta, corpus)
            self.assertEqual(done, {"a"})
            self.assertEqual(per_run, [{"run": run.name, "done": 1}])
            self.assertEqual(mismatches, [])

    def test_score_hash_mismatch_is_not_done(self):
        with tempfile.TemporaryDirectory() as td:
            meta = Path(td)
            run = meta / "20260101_yt500inst"
            run.mkdir()
            corpus = make_corpus(["a"])
            (run / "batch_manifest.json").write_text(json.dumps({
                "tracks": [{"name": "a", "seed": 7, "abc_sha256": "0" * 64}]}))
            (run / "a_7_time.txt").write_text("Exit status: 0\n")
            done, _, mismatches = driver.scan_done(meta, corpus)
            self.assertEqual(done, set())
            self.assertEqual(len(mismatches), 1)

    def test_missing_run_manifest_is_ignored(self):
        with tempfile.TemporaryDirectory() as td:
            meta = Path(td)
            (meta / "20260101_yt500inst").mkdir()
            done, per_run, mismatches = driver.scan_done(meta, make_corpus(["a"]))
            self.assertEqual(done, set())
            self.assertEqual(per_run, [])
            self.assertEqual(mismatches, [])


class SessionManifestTest(unittest.TestCase):
    def test_session_prunes_scores_and_uses_absolute_base(self):
        with tempfile.TemporaryDirectory() as td:
            corpus = make_corpus(["a", "b", "c"])
            corpus["songs"]["a"] = {"name": "a", "seed": 1234}
            path = Path(td) / "session.json"
            payload = driver.write_session_manifest(corpus, ["a", "c"], path)
            self.assertEqual(payload["base_dir"], str(corpus["base"]))
            self.assertEqual(set(payload["scores"]), {"a", "c"})
            self.assertEqual([s["name"] for s in payload["songs"]], ["a", "c"])
            self.assertEqual(payload["songs"][0]["seed"], 1234)
            self.assertEqual(payload["defaults"], corpus["data"]["defaults"])


class MarkerTest(unittest.TestCase):
    def test_write_marker_creates_time_and_sidecar(self):
        with tempfile.TemporaryDirectory() as td:
            run = Path(td)
            wav = make_wav(run / "song_7.wav", seconds=6.0)
            track = {"name": "song", "seed": 7, "cap": 100,
                     "score_alias": "song", "abc_sha256": "a" * 64,
                     "cot": "full", "take": 0}
            ok = driver.write_marker(run, track, wav,
                                     lora_alias="instrumental_v9",
                                     lora_scale={"ar": 0.85, "nar": 1.0})
            self.assertTrue(ok)
            self.assertIn("Exit status: 0",
                          (run / "song_7_time.txt").read_text())
            sidecar = json.loads((run / "song_7.json").read_text())
            self.assertEqual(sidecar["status"], "ok")
            self.assertEqual(sidecar["seed"], 7)
            self.assertEqual(sidecar["lora_alias"], "instrumental_v9")
            self.assertGreater(sidecar["wav_duration_s"], 5)

    def test_short_wav_is_not_marked(self):
        with tempfile.TemporaryDirectory() as td:
            run = Path(td)
            wav = make_wav(run / "song_7.wav", seconds=1.0)
            track = {"name": "song", "seed": 7}
            self.assertFalse(driver.write_marker(
                run, track, wav, lora_alias=None, lora_scale={}))


class BatchCommandTest(unittest.TestCase):
    def test_command_carries_session_assets_once(self):
        cmd = driver.build_bin_cmd(
            binary=Path("/bin/audiocpp_cli"),
            model_dir=Path("/models"),
            ar=Path("/loras/ar.safetensors"),
            nar=Path("/loras/nar.safetensors"),
            scale={"ar": 0.85, "nar": 1.0},
            threads=8,
            requests=Path("/run/requests.json"),
            run_dir=Path("/run"),
        )
        joined = " ".join(cmd)
        self.assertIn("--request-sequence", joined)
        self.assertIn("yue2.ar_lora_scale=0.85", joined)
        self.assertIn("yue2.nar_lora_scale=1.0", joined)
        self.assertEqual(joined.count("--request-sequence"), 1)


if __name__ == "__main__":
    unittest.main()


class RequestPayloadTest(unittest.TestCase):
    def test_request_has_id_tags_style_cap_and_absolute_score(self):
        import generate as gen
        with tempfile.TemporaryDirectory() as td:
            run = Path(td)
            (run / "scores").mkdir()
            (run / "scores" / "song.abc").write_text("X:1\nK:C\n")
            song = gen.Song(
                name="song", style_text="STYLE", lyrics_text="[intro]\n[verse]",
                cap=1234, quantile=0.95, n_letters=0,
                seed_spec=("single", 7), lora="instrumental_v9",
                abc_text="X:1\nK:C\n", abc_source=Path("song.abc"),
                score_alias="song", cot="full", score_s=100.0,
                controls={"guidance_scale": 1.5},
                lora_scale={"ar": 0.85, "nar": 1.0}, cap_source="score")
            track = gen.Track(
                idx=1, name="song", take=0, seed=7, cap=1234,
                quantile=0.95, n_letters=0, lora="instrumental_v9",
                cot="full", score_alias="song", score_s=100.0,
                score_label="song", controls={"guidance_scale": 1.5},
                lora_scale={"ar": 0.85, "nar": 1.0})
            info = {"song": {"abc_file": "scores/song.abc"}}
            requests = gen.build_requests([song], [track], info, run)
            self.assertEqual(requests[0]["id"], "song_7")
            self.assertEqual(requests[0]["seed"], 7)
            self.assertEqual(requests[0]["lyrics"], "[intro]\n[verse]")
            opts = requests[0]["options"]
            self.assertEqual(opts["style"], "STYLE")
            self.assertEqual(opts["cot"], "full")
            self.assertEqual(opts["semantic_max_tokens"], 1234)
            self.assertEqual(opts["guidance_scale"], 1.5)
            self.assertEqual(opts["abc_file"],
                             str((run / "scores" / "song.abc").resolve()))


class PrepareOnlyTest(unittest.TestCase):
    def test_prepare_only_writes_session_without_generation(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            scores = root / "scores"
            scores.mkdir()
            for name in ("a", "b"):
                (scores / f"{name}.abc").write_text("X:1\nK:C\n")
            corpus = {
                "base_dir": str(root),
                "loras": {"instrumental_v9": {"ar": "ar", "nar": "nar"}},
                "scores": {n: f"scores/{n}.abc" for n in ("a", "b")},
                "defaults": {"lora": "instrumental_v9", "cot": "full"},
                "songs": [{"name": n, "score": n, "seed": 100 + i}
                          for i, n in enumerate(("a", "b"))],
            }
            manifest = root / "pilot.json"
            manifest.write_text(json.dumps(corpus))
            (root / "meta").mkdir()
            rc = driver.main([
                "--run", "--prepare-only",
                "--corpus", str(manifest),
                "--meta-dir", str(root / "meta"),
                "--work-dir", str(root / "work"),
                "--out-root", str(root / "out"),
            ])
            self.assertEqual(rc, 0)
            sessions = list((root / "work").glob("session_*.json"))
            self.assertEqual(len(sessions), 1)
            payload = json.loads(sessions[0].read_text())
            self.assertEqual([s["seed"] for s in payload["songs"]], [100, 101])


class ListRemoteRunsTest(unittest.TestCase):
    """`gcloud storage ls <glob>` returns objects; they must collapse to runs.

    Regression: feeding an object URI to sync_meta rsynced each file into its
    own folder, so scan_done found no per-run batch_manifest.json and a fresh
    VM reported done=0 for a fully uploaded run.
    """

    def test_objects_collapse_to_run_prefixes(self):
        stdout = "\n".join([
            "gs://b/runs/20261110-083615_yt500inst/batch_manifest.json",
            "gs://b/runs/20261110-083615_yt500inst/yt500-x_1_time.txt",
            "gs://b/runs/20261110-090000_yt500inst-2/batch_manifest.json",
            "gs://b/runs/other_label/batch_manifest.json",
        ]) + "\n"

        class Proc:
            returncode = 0

        old_run = driver.subprocess.run
        old_which = driver.shutil.which
        driver.shutil.which = lambda name: "/usr/bin/" + name
        driver.subprocess.run = lambda *a, **k: Proc()
        try:
            driver.subprocess.run = lambda *a, **k: Proc()
            Proc.stdout = stdout
            runs = driver.list_remote_runs("gs://b/runs")
        finally:
            driver.subprocess.run = old_run
            driver.shutil.which = old_which

        self.assertEqual(runs, [
            "gs://b/runs/20261110-083615_yt500inst",
            "gs://b/runs/20261110-090000_yt500inst-2",
        ])
