#!/usr/bin/env python3
"""Tests for the YuE2 Vocal -> Ins instrumental conversion wrapper."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "plumbing" / "yue2_instrumental"))

from abc_tools import parse_abc  # noqa: E402
from instrumentalize import convert_score  # noqa: E402

# Minimal native two-voice score: two instrumental intro bars, then two bars
# where the vocal melody is the only sounding line.
ABC = """X:1
T:
M:4/4
L:1/16
Q:1/4=120
V: Vocal clef=treble name="Vocal Melody" snm="Vocal"
V: Ins clef=treble name="Ins Melody" snm="Inst."
K:C
% intro
V: Vocal
"C"z16|"G"z16|
V: Ins
Z2|
% verse
V: Vocal
"C"c4c4c4c4|"G"G4G4G4G4|
V: Ins
Z2|
"""


class Instrumentalize(unittest.TestCase):
    def test_vocal_is_moved_to_ins_and_left_as_rests(self):
        source = parse_abc(ABC)
        converted, check = convert_score(ABC)
        target = parse_abc(converted)

        self.assertEqual(target.voices["Vocal"].notes, [])
        self.assertEqual(target.voices["Ins"].notes, source.voices["Vocal"].notes)
        self.assertEqual(target.voices["Vocal"].time, source.voices["Vocal"].time)
        self.assertEqual(target.voices["Ins"].bars, source.voices["Ins"].bars)
        self.assertEqual(len(target.voices["Vocal"].chords),
                         len(source.voices["Vocal"].chords))
        self.assertTrue(check["vocal_pitch_onset_duration_preserved"])
        self.assertEqual(check["vocal_notes_after"], 0)
        self.assertEqual(check["vocal_notes_before"],
                         len(source.voices["Vocal"].notes))

    def test_existing_ins_notes_are_kept(self):
        source = parse_abc(ABC)
        converted, check = convert_score(ABC)
        target = parse_abc(converted)
        # The intro Ins rests are empty, so here the check is about the source
        # Ins sounding-note count being carried through unchanged.
        self.assertEqual(check["original_ins_notes"], len(source.voices["Ins"].notes))
        self.assertEqual(check["affected_ins_notes"], [])
        self.assertEqual(len(target.voices["Ins"].notes),
                         len(source.voices["Vocal"].notes)
                         + len(source.voices["Ins"].notes))


if __name__ == "__main__":
    unittest.main()
