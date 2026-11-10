#!/usr/bin/env python3
"""Offline tests for the YT500 generation corpus builder. No GPU, no network."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "plumbing"))

import yt500_generation_corpus as corpus  # noqa: E402


def track(rank: int, video_id: str, abc: str | None,
          status: str = "ok", duration: float = 200.0) -> dict:
    return {
        "track_id": f"YT500/shard-01/{rank:04d}_{video_id}",
        "source_rank": rank,
        "video_id": video_id,
        "source_artist": "Artist",
        "title": f"Title {rank}",
        "duration_s": duration,
        "transcribe_status": status,
        "abc": abc,
        "_shard": "shard-01",
    }


class NormalizeInlineKeysTest(unittest.TestCase):
    def test_rest_prefix_is_moved_to_bar_start(self):
        text = 'X:1\nK:C\nV: Vocal\n"C"z8|z[K:F]z6z|\n'
        out, changes, failures = corpus.normalize_inline_keys(text)
        self.assertEqual(failures, [])
        self.assertEqual(len(changes), 1)
        self.assertIn('[K:F]zz6z', out)
        self.assertNotIn('z[K:F]', out)

    def test_pitched_prefix_is_refused(self):
        text = 'X:1\nK:C\nV: Vocal\n"C"G2[K:F]z6|\n'
        _, _, failures = corpus.normalize_inline_keys(text)
        self.assertEqual(len(failures), 1)
        self.assertEqual(failures[0]["key"], "[K:F]")

    def test_key_at_bar_start_is_untouched(self):
        text = 'X:1\nK:C\nV: Vocal\n"C"z8|[K:F]z8|\n'
        out, changes, failures = corpus.normalize_inline_keys(text)
        self.assertEqual(changes, [])
        self.assertEqual(failures, [])
        self.assertEqual(out, text)


class SelectionTest(unittest.TestCase):
    def test_no_abc_and_unfixable_are_excluded(self):
        tracks = [
            track(1, "good", 'X:1\nK:C\nV: Vocal\n"C"z8|\n'),
            track(2, "missing", None, status="no-abc"),
            track(3, "pitched", 'X:1\nK:C\nV: Vocal\n"C"G2[K:F]z6|\n'),
        ]
        ready, excluded = corpus.select_tracks(tracks)
        self.assertEqual([corpus.track_name(t) for t in ready],
                         ["yt500-0001-good"])
        self.assertEqual({e["reason"] for e in excluded},
                         {"no-abc", "inline_key_change"})

    def test_rest_prefix_track_is_ready(self):
        tracks = [track(1, "rest", 'X:1\nK:C\nV: Vocal\n"C"z8|z[K:F]z6z|\n')]
        ready, excluded = corpus.select_tracks(tracks)
        self.assertEqual(len(ready), 1)
        self.assertEqual(excluded, [])
        self.assertIn('[K:F]', ready[0]["_abc_normalized"])


class ManifestTest(unittest.TestCase):
    def test_manifest_copies_reference_recipe(self):
        reference = corpus.load_reference()
        good = [
            {**track(1, "a", "x"), "_instrumental_sha256": "a" * 64,
             "_report": {"nominal_seconds": 100.0}, "_sections": ["intro"]},
            {**track(2, "b", "x"), "_instrumental_sha256": "b" * 64,
             "_report": {"nominal_seconds": 120.0}, "_sections": ["verse"]},
        ]
        manifest = corpus.build_manifest(good, reference)
        self.assertEqual(manifest["defaults"], reference["defaults"])
        self.assertEqual(manifest["loras"], reference["loras"])
        self.assertEqual(manifest["base_dir"], "..")
        self.assertEqual(len(manifest["songs"]), 2)
        self.assertEqual(
            manifest["scores"]["yt500-0001-a"],
            "scores/yt500_instrumental/yt500-0001-a.abc")

    def test_index_counts_statuses(self):
        tracks = [
            track(1, "good", "x"),
            track(2, "missing", None, status="no-abc"),
            track(3, "pitched", "x"),
        ]
        good = [{**tracks[0], "_instrumental_sha256": "a" * 64,
                 "_report": {"nominal_seconds": 1.0}, "_sections": ["intro"]}]
        excluded = [{"name": "yt500-0003-pitched",
                     "reason": "inline_key_change", "detail": []},
                    {"name": "yt500-0002-missing",
                     "reason": "no-abc", "detail": ""}]
        index = corpus.build_index(tracks, good, excluded)
        self.assertEqual(index["counts"]["source"], 3)
        self.assertEqual(index["counts"]["ready"], 1)
        self.assertEqual(index["counts"]["excluded_no_abc"], 1)
        self.assertEqual(index["counts"]["excluded_inline_key"], 1)
        row = {r["name"]: r for r in index["tracks"]}
        self.assertEqual(row["yt500-0001-good"]["generation_status"], "ready")
        self.assertEqual(row["yt500-0002-missing"]["reason"], "no-abc")


if __name__ == "__main__":
    unittest.main()
