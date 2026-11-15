#!/usr/bin/env python3
"""Extract mechanically-checkable claims from live markdown docs into claims.json.

No model judgment here: this only records things a script can later test
(``file:line`` citations, repo paths, CLI flags, dates). Scope — live vs frozen
docs — lives in ``claims_common.py``.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import date
from pathlib import Path

from claims_common import DEFAULT_EXCLUDES, KNOWN_DIRS, KNOWN_EXTS, iter_markdown

DIRS_ALT = "|".join(re.escape(d) for d in KNOWN_DIRS)
EXTS_ALT = "|".join(re.escape(e) for e in KNOWN_EXTS)

CITATION_RE = re.compile(
    r"(?<![\w/.-])([A-Za-z0-9._/-]+\.[A-Za-z0-9]+):(\d+)(?:-(\d+))?(?![\w/-])"
)
TOKEN_RE = re.compile(
    rf"(?<![\w/.-])((?:\.\./)*(?:{DIRS_ALT})/[A-Za-z0-9._/-]+"
    rf"|(?:\.\./)*[A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)+\.(?:{EXTS_ALT})"
    rf"|(?:\.\./)*[A-Za-z0-9._-]+\.(?:{EXTS_ALT}))(?![\w/.-])"
)
RUNTIME_RE = re.compile(r"(?<![\w.-])(/(?:content|root|tmp|usr)/[A-Za-z0-9._/-]+)")
GS_RE = re.compile(r"gs://[A-Za-z0-9._/-]+")
FLAG_RE = re.compile(r"(?<![\w-])(--[a-z][a-z0-9-]{1,})(?![\w-])")
STAMP_RE = re.compile(
    r"Last\s+(?:verified|updated|reviewed)\s*:?\s*(\d{4}-\d{2}-\d{2})",
    re.IGNORECASE,
)


def _add(claims, seen, rel: Path, lineno: int, kind: str, raw: str, context: str, **extra):
    key = (rel.as_posix(), lineno, kind, raw)
    if key in seen:
        return
    seen.add(key)
    claim = {"file": rel.as_posix(), "line": lineno, "kind": kind, "raw": raw, "context": context}
    claim.update(extra)
    claims.append(claim)


def extract(
    root: Path,
    excludes: tuple[str, ...] = DEFAULT_EXCLUDES,
    include_all: bool = False,
) -> dict:
    if include_all:
        excludes = ()
    claims: list[dict] = []
    seen: set[tuple] = set()
    files: list[str] = []
    for path, rel in iter_markdown(root, excludes):
        files.append(rel.as_posix())
        fence_lang: str | None = None
        skip_fence = False
        for lineno, line in enumerate(path.read_text(errors="ignore").splitlines(), 1):
            context = line.strip()[:200]
            if line.lstrip().startswith(("```", "~~~")):
                if fence_lang is None:
                    fence_lang = line.lstrip()[3:].strip().lower()
                    skip_fence = fence_lang in ("json", "yaml", "yml")
                else:
                    fence_lang = None
                    skip_fence = False
                continue
            if not context or skip_fence:
                continue
            for match in CITATION_RE.finditer(line):
                # `127.0.0.1:9222` is an address, not a file:line citation.
                if re.fullmatch(r"[\d.]+", match.group(1)):
                    continue
                start = int(match.group(2))
                end = int(match.group(3)) if match.group(3) else start
                _add(
                    claims,
                    seen,
                    rel,
                    lineno,
                    "citation",
                    match.group(1),
                    context,
                    start_line=start,
                    end_line=end,
                )
            masked = CITATION_RE.sub(" ", line)
            for match in RUNTIME_RE.finditer(masked):
                _add(claims, seen, rel, lineno, "runtime_path", match.group(0), context)
            for match in GS_RE.finditer(masked):
                _add(claims, seen, rel, lineno, "gs_uri", match.group(0), context)
            for match in FLAG_RE.finditer(masked):
                _add(claims, seen, rel, lineno, "flag", match.group(0), context)
            for match in STAMP_RE.finditer(masked):
                _add(claims, seen, rel, lineno, "stamp", match.group(1), context)
            for match in TOKEN_RE.finditer(masked):
                raw = match.group(0)
                # `<take>.tar.gz` yields a bare `.tar.gz` suffix, not a path.
                if raw.startswith(".") and "/" not in raw and raw.count(".") > 1:
                    continue
                _add(claims, seen, rel, lineno, "path", raw, context)
    return {
        "generated": date.today().isoformat(),
        "root": str(root.resolve()),
        "excludes": list(excludes),
        "files_scanned": files,
        "claims": claims,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="repo root to scan (default: .)")
    parser.add_argument("-o", "--out", default=".reconcile/claims.json", help="output JSON path")
    parser.add_argument("--include-all", action="store_true", help="also scan frozen/historical docs")
    parser.add_argument("--exclude", action="append", default=[], help="extra path/glob to exclude (repeatable)")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    excludes = DEFAULT_EXCLUDES + tuple(args.exclude)
    payload = extract(root, excludes, include_all=args.include_all)

    out = Path(args.out)
    if not out.is_absolute():
        out = root / out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n")

    counts: dict[str, int] = {}
    for claim in payload["claims"]:
        counts[claim["kind"]] = counts.get(claim["kind"], 0) + 1
    summary = ", ".join(f"{k}={v}" for k, v in sorted(counts.items()))
    print(f"{len(payload['claims'])} claims from {len(payload['files_scanned'])} files -> {out}")
    print(summary or "no claims")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
