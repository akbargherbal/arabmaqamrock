Write a Python module `solution.py` containing exactly one function:

    parse_abc_length(text: str) -> float

It parses the ABC notation note-length suffix into a multiplier of the default note value (1.0 = one whole note unit).

Rules:
- Surrounding whitespace is ignored.
- "" (empty after strip) means 1.0
- a plain integer n means float(n), e.g. "2" -> 2.0
- "/" means 0.5
- "/n" means 1/n, e.g. "/2" -> 0.5
- "n/m" means n/m, e.g. "3/2" -> 1.5
- "n/" means n/2, e.g. "7/" -> 3.5
- "//" means 0.25
- Any malformed or non-positive value must raise ValueError: e.g. "abc", "0", "/0", "2/0", "-1", "1.5", "1 2".

Return the value as a float. No printing, no side effects, no extra top-level code.
