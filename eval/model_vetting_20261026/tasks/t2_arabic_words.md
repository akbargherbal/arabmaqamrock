Write a Python module `solution.py` containing exactly one function:

    split_arabic_words(text: str) -> list[str]

It splits a line of Arabic lyrics (possibly mixed with Latin) into word tokens.

Rules:
- Tokens are returned in original order.
- Whitespace is always a separator and never appears inside a token.
- These characters are separators and must NOT appear in any returned token:
  Arabic comma U+060C "،", Arabic semicolon U+061B "؛", Arabic question mark U+061F "؟",
  and ASCII "." "," "!" "?" ";" ":" "…".
- Arabic diacritics (harakat, U+064B-U+0652, U+0670, and U+06D6-U+06ED) must be PRESERVED
  and stay attached to their base letters.
- Apostrophes "'" and hyphens "-" inside a word are part of the word ("don't", "maqam-rock"
  are single tokens).
- Digits are part of a word ("2" is a token).
- Empty tokens are never returned; a string of only separators returns [].

No printing, no side effects, no extra top-level code.
