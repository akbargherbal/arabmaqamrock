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
    (tmp / "plain_style.txt").write_text("plain test style", encoding="utf-8")
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

    def resolve_no_trigger(self, data: dict):
        return generate.resolve_songs(data, self.tmp, cli_trigger=False)

    def test_trigger_defaults_to_on(self):
        song = self.resolve(manifest(
            [{"name": "a", "lyrics_file": "lyrics.txt"}],
            defaults={"style_file": "plain_style.txt", "cot": "full"},
        ))[0]
        self.assertTrue(song.style_text.startswith("arabmaqamrock "))

    def test_trigger_false_in_defaults(self):
        song = self.resolve(manifest(
            [{"name": "a", "lyrics_file": "lyrics.txt"}],
            defaults={"style_file": "plain_style.txt", "cot": "full",
                      "trigger": False},
        ))[0]
        self.assertEqual(song.style_text, "plain test style")

    def test_trigger_per_song_override(self):
        off, on = self.resolve(manifest(
            [{"name": "off", "lyrics_file": "lyrics.txt", "trigger": False},
             {"name": "on", "lyrics_file": "lyrics.txt", "trigger": True}],
            defaults={"style_file": "plain_style.txt", "cot": "full",
                      "trigger": True},
        ))
        self.assertEqual(off.style_text, "plain test style")
        self.assertTrue(on.style_text.startswith("arabmaqamrock "))

    def test_cli_no_trigger_forces_off(self):
        song = self.resolve_no_trigger(manifest(
            [{"name": "a", "lyrics_file": "lyrics.txt", "trigger": True}],
            defaults={"style_file": "plain_style.txt", "cot": "full",
                      "trigger": True},
        ))[0]
        self.assertEqual(song.style_text, "plain test style")

    def test_trigger_must_be_bool(self):
        for bad in ("false", 0, 1, None):
            with self.subTest(bad=bad), self.assertRaises(generate.PlanError):
                self.resolve(manifest(
                    [{"name": "a", "lyrics_file": "lyrics.txt",
                      "trigger": bad}],
                    defaults={"style_file": "plain_style.txt", "cot": "full"},
                ))
        with self.assertRaises(generate.PlanError):
            self.resolve(manifest(
                [{"name": "a", "lyrics_file": "lyrics.txt"}],
                defaults={"style_file": "plain_style.txt", "cot": "full",
                          "trigger": "false"},
            ))

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


class DefaultLyrics(unittest.TestCase):
    """`defaults.lyrics` carries the corpus-wide section plan; per song wins."""

    TAGS = "[intro]\n[instrumental]\n[outro]"

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        write_assets(self.tmp)

    def resolve(self, data: dict):
        return generate.resolve_songs(data, self.tmp, cli_trigger=False)

    def test_defaults_lyrics_apply(self):
        song = self.resolve(manifest(
            [{"name": "a"}],
            defaults={"style_file": "plain_style.txt", "cot": "off",
                      "lyrics": self.TAGS},
        ))[0]
        self.assertEqual(song.lyrics_text, self.TAGS)

    def test_song_lyrics_override_defaults(self):
        song = self.resolve(manifest(
            [{"name": "a", "lyrics": "[instrumental]"}],
            defaults={"style_file": "plain_style.txt", "cot": "off",
                      "lyrics": self.TAGS},
        ))[0]
        self.assertEqual(song.lyrics_text, "[instrumental]")

    def test_defaults_lyrics_file(self):
        (self.tmp / "tags.txt").write_text(self.TAGS, encoding="utf-8")
        song = self.resolve(manifest(
            [{"name": "a"}],
            defaults={"style_file": "plain_style.txt", "cot": "off",
                      "lyrics_file": "tags.txt"},
        ))[0]
        self.assertEqual(song.lyrics_text, self.TAGS)

    def test_missing_lyrics_still_errors(self):
        with self.assertRaises(generate.PlanError):
            self.resolve(manifest(
                [{"name": "a"}],
                defaults={"style_file": "plain_style.txt", "cot": "off"},
            ))


class LyricsFromScore(unittest.TestCase):
    """`lyrics_from_score` turns a score's `% section` comments into a tag plan."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        write_assets(self.tmp)

    def set_score(self, body: str) -> None:
        (self.tmp / "scored.abc").write_text(
            "X:1\nT:test\nM:4/4\nL:1/4\nQ:1/4=120\nV: Ins\nK:D\n" + body,
            encoding="utf-8")

    def resolve(self, data: dict):
        return generate.resolve_songs(data, self.tmp, cli_trigger=False)

    def plan(self, defaults: dict, songs: list[dict] | None = None):
        defaults = {"style_file": "plain_style.txt", "cot": "melody", **defaults}
        return self.resolve(manifest(
            songs or [{"name": "a", "abc_file": "scored.abc"}], defaults))[0]

    def test_tags_come_from_the_score(self):
        self.set_score("% intro\nD E F G|\n% verse 1\nD E F G|\n"
                       "% chorus\nD E F G|\n% outro\nD E F G|\n")
        song = self.plan({"lyrics_from_score": True})
        self.assertEqual(song.lyrics_text,
                         "[intro]\n[verse]\n[chorus]\n[outro]")

    def test_last_section_becomes_outro(self):
        self.set_score("% intro\nD E F G|\n% verse\nD E F G|\n% chorus\nD E F G|\n")
        self.assertEqual(self.plan({"lyrics_from_score": True}).lyrics_text,
                         "[intro]\n[verse]\n[outro]")

    def test_interlude_maps_to_bridge(self):
        self.set_score("% intro\nD E F G|\n% interlude\nD E F G|\n% chorus\nD E F G|\n")
        self.assertEqual(self.plan({"lyrics_from_score": True}).lyrics_text,
                         "[intro]\n[bridge]\n[outro]")

    def test_unknown_comments_are_dropped(self):
        self.set_score("% intro\nD E F G|\n% guitar solo\nD E F G|\n"
                       "% verse\nD E F G|\n% chorus\nD E F G|\n")
        song = self.plan({"lyrics_from_score": True})
        self.assertEqual(song.lyrics_text, "[intro]\n[verse]\n[outro]")

    def test_single_section_gets_an_intro(self):
        self.set_score("% chorus\nD E F G|\n")
        self.assertEqual(self.plan({"lyrics_from_score": True}).lyrics_text,
                         "[intro]\n[outro]")

    def test_repeated_label_in_place_is_one_section(self):
        self.set_score("% intro\nD E F G|\n% verse\nD E F G|\n% verse\nD E F G|\n")
        self.assertEqual(self.plan({"lyrics_from_score": True}).lyrics_text,
                         "[intro]\n[outro]")

    def test_score_without_comments_errors(self):
        self.set_score("D E F G|\n")
        with self.assertRaises(generate.PlanError):
            self.plan({"lyrics_from_score": True})

    def test_requires_a_score(self):
        with self.assertRaises(generate.PlanError):
            self.plan({"lyrics_from_score": True},
                      [{"name": "a", "lyrics_from_score": True}])

    def test_mutually_exclusive_with_lyrics(self):
        self.set_score("% intro\nD E F G|\n")
        with self.assertRaises(generate.PlanError):
            self.plan({"lyrics_from_score": True, "lyrics": "[instrumental]"})

    def test_song_lyrics_beat_a_default_plan(self):
        self.set_score("% intro\nD E F G|\n% chorus\nD E F G|\n")
        song = self.plan({"lyrics_from_score": True},
                         [{"name": "a", "abc_file": "scored.abc",
                           "lyrics": "[instrumental]"}])
        self.assertEqual(song.lyrics_text, "[instrumental]")

    def test_song_plan_beats_default_lyrics(self):
        self.set_score("% intro\nD E F G|\n% chorus\nD E F G|\n")
        song = self.plan({"lyrics": "[instrumental]"},
                         [{"name": "a", "abc_file": "scored.abc",
                           "lyrics_from_score": True}])
        self.assertEqual(song.lyrics_text, "[intro]\n[outro]")


class CapFollowsTheLength(unittest.TestCase):
    """The cap follows the length: explicit > score length > lyrics fit."""

    # one 4/4 bar at 120 BPM = 2.0 s -> 50 frames
    SCORE_S = 2.0
    SCORED = ("X:1\nT:test\nM:4/4\nL:1/4\nQ:1/4=120\nV: Ins\nK:D\n"
              "D E F G|\n")

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        write_assets(self.tmp)
        (self.tmp / "scored.abc").write_text(self.SCORED, encoding="utf-8")

    def resolve(self, songs: list[dict], defaults: dict | None = None):
        return generate.resolve_songs(
            manifest(songs, defaults or {"style_file": "plain_style.txt",
                                         "cot": "melody"}),
            self.tmp, cli_trigger=False)

    def test_score_sets_the_cap(self):
        song = self.resolve([{"name": "a", "abc_file": "scored.abc",
                              "lyrics": "[instrumental]"}])[0]
        self.assertAlmostEqual(song.score_s, self.SCORE_S, places=3)
        self.assertEqual(song.cap, 50 + generate.SCORE_HEADROOM_S * 25)

    def test_score_cap_needs_no_lyrics_signal(self):
        song = self.resolve([{"name": "a", "abc_file": "scored.abc",
                              "lyrics": "[intro]\n[verse]\n[outro]"}])[0]
        self.assertEqual(song.n_letters, 0)
        self.assertGreater(song.cap, 1000)   # not the 110 s lyrics floor

    def test_explicit_cap_wins_over_the_score(self):
        song = self.resolve([{"name": "a", "abc_file": "scored.abc",
                              "lyrics": "[instrumental]", "cap": 123}])[0]
        self.assertEqual(song.cap, 123)

    def test_explicit_quantile_still_wins_on_a_scored_song(self):
        song = self.resolve([{"name": "a", "abc_file": "scored.abc",
                              "lyrics": "يا ليل يا ليل", "quantile": 0.975}])[0]
        expected = generate.duration_cap(song.n_letters, 0.975)[2]
        self.assertEqual(song.cap, expected)
        self.assertEqual(song.cap_source, "quantile")

    def test_defaults_quantile_still_sizes_a_scored_song(self):
        song = self.resolve(
            [{"name": "a", "abc_file": "scored.abc", "lyrics": "يا ليل يا ليل"}],
            {"style_file": "plain_style.txt", "cot": "melody",
             "quantile": 0.975})[0]
        expected = generate.duration_cap(song.n_letters, 0.975)[2]
        self.assertEqual(song.cap, expected)

    def test_quantile_without_letters_warns_about_the_floor(self):
        # the pathological case the score rule exists for: a tag plan has zero
        # Arabic letters, so an explicit quantile collapses to the 110 s floor.
        with mock.patch.object(generate, "warn") as warned:
            song = self.resolve([{"name": "a", "abc_file": "scored.abc",
                                  "lyrics": "[instrumental]",
                                  "quantile": 0.95}])[0]
        self.assertEqual(song.cap, 2750)
        self.assertIn("no Arabic letters", " ".join(
            str(c.args[0]) for c in warned.call_args_list))

    def test_score_sets_the_cap_when_nothing_is_asked(self):
        song = self.resolve([{"name": "a", "abc_file": "scored.abc",
                              "lyrics": "[instrumental]"}])[0]
        self.assertEqual(song.cap_source, "score")

    def test_unparseable_score_does_not_fall_back_to_the_floor(self):
        (self.tmp / "tuplets.abc").write_text(
            "X:1\nT:test\nM:4/4\nL:1/4\nQ:1/4=120\nV: Ins\nK:D\n(3D E F G|\n",
            encoding="utf-8")
        with self.assertRaises(generate.PlanError):
            self.resolve([{"name": "a", "abc_file": "tuplets.abc",
                           "lyrics": "[instrumental]"}])

    def test_unparseable_score_is_fine_with_an_explicit_cap(self):
        (self.tmp / "tuplets.abc").write_text(
            "X:1\nT:test\nM:4/4\nL:1/4\nQ:1/4=120\nV: Ins\nK:D\n(3D E F G|\n",
            encoding="utf-8")
        song = self.resolve([{"name": "a", "abc_file": "tuplets.abc",
                              "lyrics": "[instrumental]", "cap": 6000}])[0]
        self.assertEqual(song.cap, 6000)

    def test_no_score_still_uses_the_lyrics_fit(self):
        song = self.resolve([{"name": "a", "lyrics": "يا ليل يا ليل"}])[0]
        expected = generate.duration_cap(song.n_letters, 0.95)[2]
        self.assertEqual(song.cap, expected)

    def test_song_quantile_still_sizes_a_song_without_a_score(self):
        song = self.resolve([{"name": "a", "lyrics": "يا ليل يا ليل",
                              "quantile": 0.975}])[0]
        expected = generate.duration_cap(song.n_letters, 0.975)[2]
        self.assertEqual(song.cap, expected)

    def test_cap_and_quantile_remain_exclusive(self):
        with self.assertRaises(generate.PlanError):
            self.resolve([{"name": "a", "lyrics": "يا ليل", "cap": 6000,
                           "quantile": 0.95}])


class DefaultSeeds(unittest.TestCase):
    """`defaults.seed` gives the whole batch one seed; a per-song seed wins."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        write_assets(self.tmp)

    def resolve(self, data: dict):
        return generate.resolve_songs(data, self.tmp, cli_trigger=False)

    def test_defaults_seed_applies_to_every_song(self):
        songs = self.resolve(manifest(
            [{"name": "a"}, {"name": "b"}],
            defaults={"style_file": "plain_style.txt", "cot": "off",
                      "lyrics": "[instrumental]", "seed": 20261106},
        ))
        self.assertEqual([s.seed_spec for s in songs],
                         [("single", 20261106), ("single", 20261106)])

    def test_song_seed_beats_defaults_seed(self):
        song = self.resolve(manifest(
            [{"name": "a", "seed": 7}],
            defaults={"style_file": "plain_style.txt", "cot": "off",
                      "lyrics": "[instrumental]", "seed": 20261106},
        ))[0]
        self.assertEqual(song.seed_spec, ("single", 7))

    def test_defaults_seeds_list(self):
        song = self.resolve(manifest(
            [{"name": "a"}],
            defaults={"style_file": "plain_style.txt", "cot": "off",
                      "lyrics": "[instrumental]", "seeds": [1, 2]},
        ))[0]
        self.assertEqual(song.seed_spec, ("list", (1, 2)))

    def test_defaults_seed_with_defaults_repeat_is_ambiguous(self):
        with self.assertRaises(generate.PlanError):
            self.resolve(manifest(
                [{"name": "a"}],
                defaults={"style_file": "plain_style.txt", "cot": "off",
                          "lyrics": "[instrumental]", "seed": 5, "repeat": 2},
            ))

    def test_no_seed_anywhere_still_draws(self):
        song = self.resolve(manifest(
            [{"name": "a"}],
            defaults={"style_file": "plain_style.txt", "cot": "off",
                      "lyrics": "[instrumental]"},
        ))[0]
        self.assertEqual(song.seed_spec, ("random", 1))


if __name__ == "__main__":
    unittest.main()