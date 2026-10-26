import pytest
from solution import cap_report


@pytest.mark.parametrize("n,q,expected", [
    (0, 0.95, "N=0 q=0.950 dur=111.1 cap=2750"),
    (100, 0.95, "N=100 q=0.950 dur=142.4 cap=3500"),
    (0, 0.90, "N=0 q=0.900 dur=105.1 cap=2750"),
    (0, 0.975, "N=0 q=0.975 dur=122.9 cap=3000"),
    (7, 0.90, "N=7 q=0.900 dur=107.2 cap=2750"),
    (12, 0.975, "N=12 q=0.975 dur=126.6 cap=3250"),
])
def test_report(n, q, expected):
    assert cap_report(n, q) == expected


def test_default_quantile():
    assert cap_report(0) == "N=0 q=0.950 dur=111.1 cap=2750"


def test_bad_quantile():
    with pytest.raises(ValueError):
        cap_report(10, 0.5)
