"""Enforce CLAUDE.md's "no inline <script> or <style> in HTML" rule.

Run: ``python3 scripts/check_inline_scripts.py``

Rules enforced:
  - No multi-line <script> blocks without a src= attribute in HTML templates.
    Single-line <script>...</script> (config/data injection) is allowed.
  - No <style> blocks in HTML templates. CSS belongs in static/css/.

Why: inline scripts and styles drift out of sync with the versioned JS/CSS
files, bypass cache-busting, and hide logic from the CI checks that cover
separate files. Every violation that slipped through was found during a
manual audit, never by a failing test. This script closes that gap.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

TEMPLATE_DIRS = [
    ROOT / "agents",
]

# <script src="..."> tags are fine - they load external files.
_SCRIPT_SRC_RE = re.compile(r"<script\b[^>]*\bsrc\s*=", re.IGNORECASE)

# A self-contained single-line data-injection: <script>var x = ...;</script>
# These pass server-side values to JS and have no clean alternative.
_SINGLE_LINE_SCRIPT_RE = re.compile(r"<script>.*?</script>", re.IGNORECASE)

# Opening <script> tag without src= on a line (may be start of a block).
_SCRIPT_OPEN_RE = re.compile(r"<script\b(?![^>]*\bsrc\s*=)[^>]*>", re.IGNORECASE)

# Any <style> opening tag (inline CSS is always a violation here).
_STYLE_OPEN_RE = re.compile(r"<style\b[^>]*>", re.IGNORECASE)


def _html_files() -> list[Path]:
    files = []
    for d in TEMPLATE_DIRS:
        files.extend(d.rglob("*.html"))
    return files


def check_file(path: Path) -> list[str]:
    """Return list of violation descriptions for this file."""
    try:
        text = path.read_text()
    except OSError:
        return []

    rel = str(path.relative_to(ROOT))
    violations = []
    lines = text.splitlines()

    i = 0
    while i < len(lines):
        line = lines[i]
        line_no = i + 1

        # --- <style> check ---
        if _STYLE_OPEN_RE.search(line):
            violations.append(f"{rel}:{line_no}: inline <style> block - move CSS to static/css/")

        # --- <script> check ---
        if _SCRIPT_SRC_RE.search(line):
            # External script with src= - fine.
            i += 1
            continue

        if _SCRIPT_OPEN_RE.search(line):
            # Could be a single-line data injection or the start of a block.
            # Check if it closes on the same line.
            if _SINGLE_LINE_SCRIPT_RE.search(line):
                # Single-line: allowed (data injection pattern).
                i += 1
                continue
            # Multi-line block: violation.
            violations.append(f"{rel}:{line_no}: inline <script> block - move JS to static/js/")

        i += 1

    return violations


def main() -> int:
    all_violations: list[str] = []
    for path in sorted(_html_files()):
        all_violations.extend(check_file(path))

    if all_violations:
        print("Inline scripts/styles found (CLAUDE.md forbids them):\n")
        for v in all_violations:
            print(f"  {v}")
        print(
            f"\n{len(all_violations)} violation(s)."
            " Move JS to static/js/, CSS to static/css/."
            " Single-line <script>var x = ...;</script> data injections are allowed."
        )
        return 1

    print("No inline scripts or styles found. Clean.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
