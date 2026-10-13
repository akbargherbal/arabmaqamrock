#!/usr/bin/env python3
"""Dynamic YuE2 `semantic_max_tokens` cap derived from a lyrics file.

Canonical implementation of the YuE2 text->duration cap (maqamrock project).
The cap is an **upper** bound -- the length at which a generated song has very
likely finished singing -- so it uses a high-quantile (pinball) fit, not the
conditional mean:

    95th percentile : duration_cap_s = 111.1 + 0.3126 * N_letters  (94.8%)
    97.5th percentile: duration_cap_s = 122.9 + 0.3081 * N_letters (97.8%)

N_letters = count of Arabic letters (Unicode category Lo, block U+0600-U+06FF).
Round the duration to the nearest 10 s, then tokens = duration * 25 (frames/s).

Do NOT use the old centre fit `92.0 + 0.280 * N`: it is the conditional mean
(only 54.7% coverage) and under-provisions the cap, causing truncated songs.

Usage:
    duration_cap.py <lyrics_file> [--quantile {0.90,0.95,0.975}]
        -> integer token cap on stdout (diagnostics go to stderr)

`--quantile` defaults to 0.95. 0.975 is the doc's more forgiving cap.
"""
from __future__ import annotations

import argparse
import sys
import unicodedata

# quantile -> (intercept a, slope b) from the maqamrock duration-cap fit
COEFFS = {
    0.90: (105.1, 0.3059),
    0.95: (111.1, 0.3126),
    0.975: (122.9, 0.3081),
}


def arabic_letters(text: str) -> int:
    return sum(
        1 for c in text
        if 0x0600 <= ord(c) <= 0x06FF and unicodedata.category(c) == "Lo"
    )


def duration_cap(n_letters: int, quantile: float = 0.95) -> tuple[float, float, int, float]:
    """Return (duration_s, duration_rounded_10s, token_cap, quantile)."""
    a, b = COEFFS[quantile]
    dur = a + b * n_letters
    dur_round10 = round(dur / 10.0) * 10
    cap = int(round(dur_round10 * 25))
    return dur, dur_round10, cap, quantile


def main() -> int:
    parser = argparse.ArgumentParser(
        description="YuE2 semantic_max_tokens cap from a lyrics file."
    )
    parser.add_argument("lyrics_file", help="path to the lyrics .txt")
    parser.add_argument(
        "--quantile", type=float, default=0.95, choices=sorted(COEFFS),
        help="cap quantile: 0.90, 0.95 (default), or 0.975",
    )
    args = parser.parse_args()

    with open(args.lyrics_file, encoding="utf-8") as f:
        lyrics = f.read()
    n = arabic_letters(lyrics)
    dur, dur_round10, cap, q = duration_cap(n, args.quantile)
    print(cap)
    print(
        f"[duration_cap] file={args.lyrics_file} N_letters={n} q={q:.3f} "
        f"dur={dur:.1f}s round10={dur_round10:.0f}s cap={cap} tokens",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
