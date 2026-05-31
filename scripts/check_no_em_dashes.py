"""Enforce CLAUDE.md's "no em dashes" rule.

Run: ``python3 scripts/check_no_em_dashes.py``

Behavior:
  - Walks source / docs / static dirs and looks for U+2014 (em dash).
  - Fails (exit 1) if any em dash is found in a non-allowlisted file.
  - Allowlist covers regex character classes that match user-typed
    dashes, plus the rule-explanation docs that quote the character
    as part of the rule itself.

Why: every time we sweep these out by hand, more sneak in. CI gates
the only durable fix.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Files where em dashes are intentional and must stay.
# Keep this list short and justified. Each entry needs a reason.
ALLOWLIST_FILES = {
    # The rule itself quotes the character as a forbidden example.
    "CLAUDE.md",
    "memory/feedback_no_em_dashes.md",
    "memory/feedback_ai_tells.md",
    "memory/MEMORY.md",
    # This script must contain literal em dashes to detect them.
    "scripts/check_no_em_dashes.py",
}

# Files where em dashes appear inside regex character classes that
# match dashes in LLM output / user input. Removing them would silently
# break parsing. The check ignores em dashes on these specific lines.
REGEX_ALLOWLIST_LINES = {
    # path -> set of line numbers (1-indexed)
    "agents/create/chat_prompt.py": {281, 285, 289, 293},
    "static/js/create-chat.js": {349},
}

# File extensions to scan. Binary / generated stuff is excluded.
SCAN_EXTS = {".py", ".html", ".js", ".css", ".md", ".txt", ".toml", ".yml", ".yaml"}

# Top-level dirs to skip entirely.
SKIP_DIRS = {".venv", "node_modules", ".git", "__pycache__", ".pytest_cache", "output"}


def is_allowlisted_line(rel: str, line_no: int, line: str) -> bool:
    """Check if a specific em-dash hit is allowlisted."""
    allowed_lines = REGEX_ALLOWLIST_LINES.get(rel)
    if allowed_lines and line_no in allowed_lines:
        # Sanity-check the line really does look like a regex char class.
        if re.search(r"\[[^\]]*—[^\]]*\]", line):
            return True
    return False


def scan_file(path: Path) -> list[tuple[int, str]]:
    """Return list of (line_no, line) tuples containing an em dash."""
    try:
        text = path.read_text()
    except (UnicodeDecodeError, OSError):
        return []
    if "—" not in text:
        return []
    hits = []
    for i, line in enumerate(text.splitlines(), start=1):
        if "—" in line:
            hits.append((i, line.rstrip()))
    return hits


def main() -> int:
    violations: list[tuple[str, int, str]] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix not in SCAN_EXTS:
            continue
        # Skip excluded dirs.
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        rel = str(path.relative_to(ROOT))
        if rel in ALLOWLIST_FILES:
            continue
        hits = scan_file(path)
        for line_no, line in hits:
            if is_allowlisted_line(rel, line_no, line):
                continue
            violations.append((rel, line_no, line))

    if violations:
        print("Em dashes found (CLAUDE.md forbids them, see Writing Style):\n")
        for rel, line_no, line in violations:
            # Truncate very long lines so the report stays readable.
            snippet = line if len(line) <= 120 else line[:117] + "..."
            print(f"  {rel}:{line_no}: {snippet}")
        print(f"\n{len(violations)} violation(s). Replace each em dash with a")
        print("hyphen (-), comma, colon, parentheses, or split into two sentences.")
        return 1

    print("No em dashes found. Clean.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
