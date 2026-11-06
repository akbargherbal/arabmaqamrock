# YuE2 instrumental helpers (vendored)

Copied from the official YuE2 `yue2-music` skill, instrumental workflow:

- Source: <https://github.com/multimodal-art-projection/YuE/tree/main/skills/yue2-music/instrumental>
- Files: `abc_tools.py`, `common.py`, `compile_score.py`, `instrumentalize.py`
- License: MIT (see `LICENSE` in this directory)

They implement the official YuE2 instrumental conversion: move every **Vocal**
note into **Ins**, leave only rests and chord symbols on **Vocal**, and keep the
original Ins notes that do not overlap the vocal melody (Vocal has priority on
overlap).

Do not edit these files unless you are tracking a newer upstream version. The
project wrapper is `plumbing/instrumentalize_scores.py`.
