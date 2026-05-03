"""Enforce CLAUDE.md's file-length rule (target 500, hard 800).

Run: ``python3 scripts/check_file_size.py``

Behavior:
  • Walks the repo's source dirs (agents/, database/, static/, scripts/,
    tests/, root *.py) and counts lines per .py / .js / .css / .html file.
  • A file is treated as a violation if it exceeds 800 lines.
  • Files listed in ``.file_size_baseline.toml`` are grandfathered IN at
    their listed ceiling, they can keep their current size but can't grow.
    Goal: shrink each one over time and delete its baseline entry.
  • Files between 501 and 800 lines print a warning (non-fatal).
  • Exit 0 = clean. Exit 1 = at least one hard violation or a baseline
    file that grew.

Wired into CI via .github/workflows/test.yml.
"""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path

HARD_LIMIT = 800
SOFT_LIMIT = 500

# Source roots we care about. Anything outside these is skipped.
INCLUDE_DIRS = ("agents", "database", "static", "scripts", "tests")
INCLUDE_ROOT_FILES = ("app.py",)
INCLUDE_EXTS = {".py", ".js", ".css", ".html"}

# Path components that mark a vendored / generated tree we should ignore.
EXCLUDE_PARTS = {
    ".venv",
    "venv",
    "__pycache__",
    "output",
    "data",
    "node_modules",
    ".git",
    "test-results",
    ".claude",
}

REPO_ROOT = Path(__file__).resolve().parent.parent
BASELINE_PATH = REPO_ROOT / ".file_size_baseline.toml"


def _load_baseline() -> dict[str, int]:
    if not BASELINE_PATH.exists():
        return {}
    with BASELINE_PATH.open("rb") as f:
        data = tomllib.load(f)
    return {k: int(v) for k, v in (data.get("files") or {}).items()}


def _candidate_files() -> list[Path]:
    out: list[Path] = []
    for d in INCLUDE_DIRS:
        root = REPO_ROOT / d
        if not root.exists():
            continue
        for p in root.rglob("*"):
            if not p.is_file() or p.suffix not in INCLUDE_EXTS:
                continue
            if any(part in EXCLUDE_PARTS for part in p.parts):
                continue
            out.append(p)
    for name in INCLUDE_ROOT_FILES:
        p = REPO_ROOT / name
        if p.exists():
            out.append(p)
    return out


def _count_lines(path: Path) -> int:
    with path.open("r", encoding="utf-8", errors="ignore") as f:
        return sum(1 for _ in f)


def main() -> int:
    baseline = _load_baseline()
    hard_violations: list[tuple[str, int]] = []
    grew: list[tuple[str, int, int]] = []
    warnings: list[tuple[str, int]] = []

    for path in _candidate_files():
        count = _count_lines(path)
        rel = str(path.relative_to(REPO_ROOT))

        if rel in baseline:
            ceiling = baseline[rel]
            if count > ceiling:
                grew.append((rel, count, ceiling))
            elif count <= HARD_LIMIT:
                # File is in baseline but has been shrunk under the hard
                # limit, nudge the contributor to delete the entry.
                print(
                    f"  💡  {rel}: {count} lines (baseline allows {ceiling}). "
                    "Now under the hard limit, remove from .file_size_baseline.toml."
                )
            continue

        if count > HARD_LIMIT:
            hard_violations.append((rel, count))
        elif count > SOFT_LIMIT:
            warnings.append((rel, count))

    if warnings:
        print(f"⚠️   Over target ({SOFT_LIMIT}+ lines, not yet over hard limit):")
        for rel, n in sorted(warnings, key=lambda x: -x[1]):
            print(f"     {n:>5}  {rel}")
        print()

    failed = bool(hard_violations or grew)

    if hard_violations:
        print(f"❌  Over hard limit ({HARD_LIMIT}) and not in .file_size_baseline.toml:")
        for rel, n in sorted(hard_violations, key=lambda x: -x[1]):
            print(f"     {n:>5}  {rel}")
        print(
            "    → Split the file by responsibility, OR add to "
            ".file_size_baseline.toml with a written justification."
        )
        print()

    if grew:
        print("❌  Baseline files grew (they're allowed to shrink, never grow):")
        for rel, n, ceiling in grew:
            print(f"     {rel}: {n} > {ceiling} (baseline ceiling)")
        print(
            "    → Trim until it's at or below the baseline, OR justify "
            "raising the ceiling in your PR description."
        )
        print()

    if failed:
        return 1

    print("✅  File-length check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
