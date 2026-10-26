import pytest
from solution import split_arabic_words


@pytest.mark.parametrize("text,expected", [
    ("يا ليل", ["يا", "ليل"]),
    ("يا، ليل", ["يا", "ليل"]),
    ("يا ليل!", ["يا", "ليل"]),
    ("قلبي", ["قلبي"]),
    ("قَلْبِي", ["قَلْبِي"]),
    ("don't stop", ["don't", "stop"]),
    ("maqam-rock 2", ["maqam-rock", "2"]),
    ("   ", []),
    ("؛؟", []),
    ("أهلاً، وسهلاً!", ["أهلاً", "وسهلاً"]),
    ("habibi يا قلبي", ["habibi", "يا", "قلبي"]),
    ("شيء… آخر", ["شيء", "آخر"]),
    ("a,b;c:d", ["a", "b", "c", "d"]),
    ("٢٠٢٦ سنة", ["٢٠٢٦", "سنة"]),
])
def test_split(text, expected):
    assert split_arabic_words(text) == expected


def test_diacritics_not_stripped():
    out = split_arabic_words("مُحَمَّدٌ")
    assert out == ["مُحَمَّدٌ"]
