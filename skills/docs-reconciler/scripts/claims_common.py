"""Shared scope rules for the docs-reconciler claim extractor/verifier.

This is the arabmaqamrock adaptation. The ancestor skill assumed one training
run-config YAML; this repo's authority is the strict manifest schema and the
argparse surface in ``generate.py``. Scope rules therefore mirror *this* repo's
live docs and its generated/runtime directories.
"""

from __future__ import annotations

import fnmatch
import os
from pathlib import Path

# Directories whose paths are worth recognising even without an extension.
# Runtime-only dirs (out/, logs/, bin/, models/, loras/) are deliberately absent:
# they are installed or generated, so a token like `out/latest` is not repo drift.
KNOWN_DIRS = (
    "docs",
    "prompts",
    "scores",
    "manifests",
    "plumbing",
    "skills",
    "cases",
    "eval",
    "datasets",
    "analysis",
    "tests",
    "outputs",
    "local_workspace",
)

KNOWN_EXTS = (
    "md",
    "py",
    "sh",
    "yml",
    "yaml",
    "toml",
    "json",
    "jsonl",
    "txt",
    "csv",
    "tsv",
    "abc",
    "mid",
    "midi",
    "lab",
    "log",
    "db",
    "safetensors",
    "gguf",
    "wav",
    "mp3",
    "png",
    "jpg",
    "jpeg",
    "svg",
    "html",
    "ipynb",
    "zip",
    "gz",
    "tar",
    "env",
)

# Frozen by design: dated plans, session/case records, archived accidents,
# generated graphs and append-only logs. Reconciling these would rewrite the
# record, not fix drift. ``!pattern`` re-includes a narrower live file.
DEFAULT_EXCLUDES = (
    ".git",
    ".pytest_cache",
    ".ruff_cache",
    ".reconcile",
    "__pycache__",
    "node_modules",
    ".venv-sheetsage2",
    ".cache",
    # generated / machine-local trees (also gitignored)
    "out",
    "logs",
    "bin",
    "models",
    "loras",
    "datasets",
    "outputs",
    "local_workspace",
    "happy_accident",
    # dated records and archives: history, not current truth
    "cases",
    "eval",
    "docs/sessions",
    "docs/plans",
    "docs/happy_accidents",
    "ROUND06_RESUME.md",
    "ROUND10_RESUME.md",
    "scores/CHANGES.md",
    # manifest files are run records; only the index is a live doc
    "manifests/*.md",
    "!manifests/README.md",
    # append-only reconciliation log quotes past reports verbatim
    "RECONCILIATION_LOG.md",
    # the report shape example quotes old findings by design
    "skills/docs-reconciler/references/example_drift_report.md",
    # bundled template; the root SOURCE_OF_TRUTH.md is the live copy
    "skills/docs-reconciler/references/source_of_truth_template.md",
    # vendored upstream README; do not reconcile a copy
    "plumbing/yue2_instrumental/README.md",
)

# Path resolution and flag discovery need frozen *code* too (live guides cite
# case scripts and their flags), but not generated/runtime trees.
INDEX_EXCLUDES = (
    ".git",
    ".pytest_cache",
    ".ruff_cache",
    ".reconcile",
    "__pycache__",
    "node_modules",
    ".venv-sheetsage2",
    ".cache",
    "out",
    "logs",
    "bin",
    "models",
    "loras",
    "datasets",
    "local_workspace",
    "happy_accident",
)

CODE_SUFFIXES = (".py", ".sh")

SKIP_PARTS = {
    ".git",
    ".pytest_cache",
    ".ruff_cache",
    ".reconcile",
    "__pycache__",
    "node_modules",
    ".claude",
}


def _pattern_matches(rel: Path, pattern: str) -> bool:
    """Match one exclude token against a repo-relative path.

    Glob tokens match the full POSIX path or the basename. Plain path tokens
    keep the ancestor semantics: a token with ``/`` is a prefix, a bare name
    matches any path component.
    """
    posix = rel.as_posix()
    if any(ch in pattern for ch in "*?["):
        return fnmatch.fnmatch(posix, pattern) or fnmatch.fnmatch(rel.name, pattern)
    raw = pattern.rstrip("/")
    if not raw:
        return False
    if "/" in raw:
        return posix == raw or posix.startswith(raw + "/")
    return raw in rel.parts


def is_excluded(rel: Path, excludes: tuple[str, ...] = DEFAULT_EXCLUDES) -> bool:
    # Re-includes are checked first so `!manifests/README.md` survives the
    # broader `manifests/*.md` exclude regardless of tuple order.
    for raw in excludes:
        if raw.startswith("!") and _pattern_matches(rel, raw[1:]):
            return False
    return any(
        not raw.startswith("!") and _pattern_matches(rel, raw)
        for raw in excludes
    )


def _walk_files(root: Path, excludes: tuple[str, ...]):
    """Yield files without descending into excluded directories."""
    for dirpath, dirnames, filenames in os.walk(root):
        current = Path(dirpath)
        rel_dir = current.relative_to(root)
        kept = []
        for name in dirnames:
            if name in SKIP_PARTS:
                continue
            rel = rel_dir / name
            if is_excluded(rel, excludes):
                continue
            kept.append(name)
        dirnames[:] = kept
        for name in filenames:
            path = current / name
            rel = path.relative_to(root)
            if is_excluded(rel, excludes):
                continue
            yield path, rel


def iter_markdown(root: Path, excludes: tuple[str, ...] = DEFAULT_EXCLUDES):
    for path, rel in _walk_files(root, excludes):
        if path.suffix == ".md":
            yield path, rel


def iter_code(root: Path, excludes: tuple[str, ...] = DEFAULT_EXCLUDES):
    for path, _ in _walk_files(root, excludes):
        if path.suffix in CODE_SUFFIXES and not path.is_symlink():
            yield path


def iter_files(root: Path, excludes: tuple[str, ...] = DEFAULT_EXCLUDES):
    """All repo files outside excluded directories (used for path resolution)."""
    yield from _walk_files(root, excludes)


def relpath(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)
