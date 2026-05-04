"""Block marketing-copy AI tells in user-facing strings.

Run: ``python3 scripts/check_marketing_copy.py``

Flags banned phrases listed in CLAUDE.md "UX Copy Style." The list is
deliberately small and targets the specific phrases that signal
"AI-written marketing copy" rather than every possible synonym.

Wired into CI via .github/workflows/test.yml.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Phrases that count as a CI failure. Match is case-insensitive.
# Keep this list short. Add only patterns that are nearly always tells.
BANNED_PATTERNS = [
    r"\bAI[- ]powered\b",
    r"\bAI[- ]driven\b",
    r"\bagentic\b",
    r"\bintelligent agents?\b",
    r"\bseamlessly\b",
    r"\beffortlessly\b",
    r"\beffortless\b",
    r"\bdiscover amazing\b",
    r"\bcurated thousands\b",
    r"\bpowerful tools\b",
    r"\byour journey starts\b",
    r"\bunlock your\b",
    r"\belevate your\b",
    r"\btransform your\b",
    r"\bwe['']ve got you covered\b",
    r"\btravel adventures\b",
    r"\bAI co-planner\b",
    r"\bAI travel companion\b",
]

# Files to scan: only stuff that ships to a user.
SCAN_DIRS = [
    "agents",  # template files + Python that returns HTML strings
    "static",  # JS/CSS rendered into the browser
]
SCAN_EXTS = {".html", ".js", ".py"}

# Files where one of these phrases is justified context (e.g. the rule
# itself enumerates them). Add with a one-line reason.
ALLOWLIST_FILES = {
    "scripts/check_marketing_copy.py": "this script must contain the literal patterns",
    "CLAUDE.md": "the rule itself enumerates the banned phrases",
    "memory/feedback_ai_tells.md": "documents the smell",
    "memory/feedback_no_em_dashes.md": "rule doc",
    "memory/feedback_brief_copy.md": "rule doc",
}

SKIP_DIRS = {".venv", "node_modules", ".git", "__pycache__", ".pytest_cache"}


def scan_file(path: Path) -> list[tuple[int, str, str]]:
    """Return list of (line_no, banned_pattern, line) for hits in this file."""
    try:
        text = path.read_text()
    except (UnicodeDecodeError, OSError):
        return []
    hits = []
    for i, line in enumerate(text.splitlines(), start=1):
        for pat in BANNED_PATTERNS:
            if re.search(pat, line, re.IGNORECASE):
                hits.append((i, pat, line.rstrip()))
    return hits


def main() -> int:
    violations: list[tuple[str, int, str, str]] = []
    for top in SCAN_DIRS:
        top_path = ROOT / top
        if not top_path.exists():
            continue
        for path in top_path.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix not in SCAN_EXTS:
                continue
            if any(part in SKIP_DIRS for part in path.parts):
                continue
            rel = str(path.relative_to(ROOT))
            if rel in ALLOWLIST_FILES:
                continue
            for line_no, pat, line in scan_file(path):
                violations.append((rel, line_no, pat, line))

    if violations:
        print("Marketing-copy AI tells found (CLAUDE.md UX Copy Style):\n")
        for rel, line_no, pat, line in violations:
            snippet = line if len(line) <= 120 else line[:117] + "..."
            print(f"  {rel}:{line_no} [{pat}]")
            print(f"    {snippet}")
        print(
            f"\n{len(violations)} violation(s). Replace with concrete verbs "
            "describing what the feature does."
        )
        return 1

    print("No marketing-copy tells found. Clean.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
