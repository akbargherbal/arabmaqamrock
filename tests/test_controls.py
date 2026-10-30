#!/usr/bin/env python3
"""Unit tests for the per-song control keys in generate.py.

No model, no network, no GPU: validation, resolution and the environment a
track would be rendered with.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import generate  # noqa: E402

ABC = "X:1\nT:test\nM:4/4\nL:1/4\nK:D\nD E F G|\n"


def write_assets(tmp: Path) -> None:
    (tmp / "style.txt").write_text("arabmaqamrock test style", encoding="utf-8")
    (tmp / "lyrics.txt").write_text("يا ليل", encoding="utf-8")
    (tmp / "score.abc").write_text(ABC, encoding="utf-8")


def manifest(songs: list[dict], defaults: dict | None = None) -> dict:
    return {
        "defaults": defaults or {"style_file": "style.txt", "quantile": 0.95,
                                 "cot": "full"},
        "songs": songs,
    }


class ControlKeys(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        write_assets(self.tmp)
        patcher = mock.patch.dict(os.environ, {}, clear=False)
        patcher.start()
        self.addCleanup(patcher.stop)
        for key in ("EXTRA_REQUEST_OPTS", "LORA_AR_SCALE", "LORA_NAR_SCALE"):
            os.environ.pop(key, None)
        self.addCleanup(lambda: [os.environ.pop(k, None) for k in
                                 ("EXTRA_REQUEST_OPTS", "LORA_AR_SCALE", "LORA_NAR_SCALE")])

    def resolve(self, data: dict):
        return generate.resolve_songs(data, self.tmp)

    def test_absent_means_nothing_is_passed(self):
        song = self.resolve(manifest([{"name": "a", "lyrics_file": "lyrics.txt"}]))[0]
        self.assertEqual(song.controls, {})
        self.assertEqual(song.lora_scale, {})

    def test_defaults_then_song_override(self):
        data = manifest(
            [{"name": "inherit", "lyrics_file": "lyrics.txt"},
             {"name": "override", "lyrics_file": "lyrics.txt",
              "guidance_scale": 2.0, "semantic_top_k": 50}],
            defaults={"style_file": "style.txt", "cot": "full",
                      "guidance_scale": 1.5, "semantic_temperature": 0.9},
        )
        inherit, override = self.resolve(data)
        self.assertEqual(inherit.controls,
                         {"guidance_scale": 1.5, "semantic_temperature": 0.9})
        self.assertEqual(override.controls,
                         {"guidance_scale": 2.0, "semantic_temperature": 0.9,
                          "semantic_top_k": 50})

    def test_bounds(self):
        bad = [
            {"guidance_scale": 25},
            {"guidance_scale": -1},
            {"guidance_scale": True},
            {"semantic_temperature": 6},
            {"semantic_top_p": 0},
            {"semantic_top_p": 1.5},
            {"semantic_top_k": 0},
            {"semantic_repetition_penalty": 0},
            {"num_inference_steps": 0},
            {"lora_ar_scale": 2},
        ]
        for extra in bad:
            with self.subTest(extra=extra), self.assertRaises(generate.PlanError):
                self.resolve(manifest([{"name": "a", "lyrics_file": "lyrics.txt",
                                        **extra}]))

    def test_abc_keys_need_a_plan_stage(self):
        data = manifest([{"name": "a", "lyrics_file": "lyrics.txt",
                          "abc_temperature": 0.5}],
                        defaults={"style_file": "style.txt", "cot": "off"})
        with self.assertRaisesRegex(generate.PlanError, "cot=off"):
            self.resolve(data)

    def test_abc_keys_rejected_with_external_score(self):
        data = manifest([{"name": "a", "lyrics_file": "lyrics.txt",
                          "abc_file": "score.abc", "cot": "melody",
                          "abc_top_p": 0.8}])
        with self.assertRaisesRegex(generate.PlanError, "score is supplied"):
            self.resolve(data)

    def test_abc_token_bounds(self):
        data = manifest([{"name": "a", "lyrics_file": "lyrics.txt",
                          "abc_min_tokens": 100, "abc_max_tokens": 50}])
        with self.assertRaisesRegex(generate.PlanError, "abc_max_tokens"):
            self.resolve(data)

    def test_extra_request_opts_are_exclusive(self):
        os.environ["EXTRA_REQUEST_OPTS"] = "guidance_scale=1.2"
        data = manifest([{"name": "a", "lyrics_file": "lyrics.txt",
                          "guidance_scale": 1.5}])
        with self.assertRaisesRegex(generate.PlanError, "EXTRA_REQUEST_OPTS"):
            self.resolve(data)

    def test_env_passthrough_without_control_keys(self):
        os.environ["EXTRA_REQUEST_OPTS"] = "guidance_scale=1.2"
        song = self.resolve(manifest([{"name": "a", "lyrics_file": "lyrics.txt"}]))[0]
        self.assertEqual(song.controls, {})

    def test_lora_scale(self):
        data = manifest([{"name": "a", "lyrics_file": "lyrics.txt",
                          "lora_ar_scale": 0.7, "lora_nar_scale": 0.5}])
        self.assertEqual(self.resolve(data)[0].lora_scale,
                         {"ar": 0.7, "nar": 0.5})

    def test_lora_scale_env_is_exclusive(self):
        os.environ["LORA_AR_SCALE"] = "0.9"
        data = manifest([{"name": "a", "lyrics_file": "lyrics.txt",
                          "lora_ar_scale": 0.7}])
        with self.assertRaisesRegex(generate.PlanError, "LORA_AR_SCALE"):
            self.resolve(data)

    def test_opts_string_is_stable(self):
        controls = {"guidance_scale": 1.5, "semantic_top_k": 50,
                    "semantic_top_p": 0.95}
        self.assertEqual(generate._opts_string(controls),
                         "guidance_scale=1.5 semantic_top_k=50 semantic_top_p=0.95")


class RunBatchEnv(unittest.TestCase):
    def test_controls_and_scales_reach_the_runner_per_track(self):
        tmp = Path(tempfile.mkdtemp())
        (tmp / "prompts").mkdir()
        (tmp / "prompts" / "a_style.txt").write_text("s", encoding="utf-8")
        (tmp / "prompts" / "a_lyrics.txt").write_text("ل", encoding="utf-8")
        prompt_info = {"a": {
            "style_file": "prompts/a_style.txt",
            "lyrics_file": "prompts/a_lyrics.txt",
            "style_sha256": "x", "lyrics_sha256": "y", "cot": "full",
            "abc_file": None, "abc_sha256": None, "abc_source": None,
            "score_alias": None, "score_s": None,
        }}
        fp = {"loras": {}, "lora_ar_sha256": "x", "lora_nar_sha256": "y",
              "model_gguf": "m", "vae_gguf": "v", "model_gguf_sha256": "a",
              "vae_gguf_sha256": "b", "checkpoint_step": 5000,
              "audio_cpp_commit": "c"}
        gpu = {"name": "T4", "compute_cap": "75"}
        tracks = [
            generate.Track(1, "a", 0, 7, 100, 0.95, 1, cot="full",
                           controls={"guidance_scale": 1.5},
                           lora_scale={"ar": 0.7}),
            generate.Track(2, "a", 1, 8, 100, 0.95, 1, cot="full"),
        ]
        seen = []

        def runner(cmd, env, log):
            seen.append((cmd[3], {k: env.get(k) for k in
                                  ("EXTRA_REQUEST_OPTS", "LORA_AR_SCALE",
                                   "LORA_NAR_SCALE")}))
            return 0

        with mock.patch.dict(os.environ, {}, clear=True):
            generate.run_batch(tmp, tracks, prompt_info, fp, gpu,
                               Path("/tmp/ar"), Path("/tmp/nar"), runner=runner)

        self.assertEqual(seen[0], ("7", {"EXTRA_REQUEST_OPTS": "guidance_scale=1.5",
                                         "LORA_AR_SCALE": "0.7",
                                         "LORA_NAR_SCALE": None}))
        self.assertEqual(seen[1], ("8", {"EXTRA_REQUEST_OPTS": None,
                                         "LORA_AR_SCALE": None,
                                         "LORA_NAR_SCALE": None}))
        sidecar = json.loads((tmp / "a_7.json").read_text(encoding="utf-8"))
        self.assertEqual(sidecar["controls"], {"guidance_scale": 1.5})
        self.assertEqual(sidecar["lora_scale"], {"ar": 0.7})


if __name__ == "__main__":
    unittest.main()
