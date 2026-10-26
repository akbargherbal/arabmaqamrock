Write a Python module `solution.py` with one function:

    cap_report(n_letters: int, quantile: float = 0.95) -> str

Use this coefficient table (quantile -> (a, b)):

    COEFFS = {0.90: (105.1, 0.3059), 0.95: (111.1, 0.3126), 0.975: (122.9, 0.3081)}

Compute:
- dur = a + b * n_letters
- dur10 = dur rounded to the nearest 10, rounding .5 away from zero
- cap = int(round(dur10 * 25))

Return exactly this string, with no trailing newline:

    f"N={n_letters} q={quantile:.3f} dur={dur:.1f} cap={cap}"

If quantile is not one of the three keys, raise ValueError.

No printing, no side effects, no extra top-level code.
