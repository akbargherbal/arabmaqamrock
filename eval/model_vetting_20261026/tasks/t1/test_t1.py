import pytest
from solution import parse_abc_length


@pytest.mark.parametrize("text,expected", [
    ("", 1.0),
    ("2", 2.0),
    ("/", 0.5),
    ("/2", 0.5),
    ("//", 0.25),
    ("3/2", 1.5),
    ("7/", 3.5),
    ("1/1", 1.0),
    (" 4 ", 4.0),
    ("/4", 0.25),
])
def test_valid(text, expected):
    assert parse_abc_length(text) == pytest.approx(expected)


@pytest.mark.parametrize("text", ["abc", "0", "/0", "2/0", "-1", "1.5", "1 2", "/x", "3//2"])
def test_invalid(text):
    with pytest.raises(ValueError):
        parse_abc_length(text)


def test_returns_float():
    assert isinstance(parse_abc_length("2"), float)
