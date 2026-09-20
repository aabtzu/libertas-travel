#!/usr/bin/env python3
"""CI check: no hardcoded palette hex colors in JS files.

JS should reference design tokens (var(--accent), var(--status-error), etc.)
instead of raw hex values. This prevents the palette from drifting and ensures
all UI components update automatically if the design tokens change.

Allowlisted paths:
  - Leaflet/map code: map APIs require actual color strings, not CSS variables
  - Minified vendor files: not our code

Allowlisted colors:
  - Colors that have no token equivalent yet (e.g. category colors owned by
    Python and served via /app-config.css as CSS custom properties - those are
    fine to reference as var(--cat-*) but the raw hex lookup is in Python).
  - One-off colors that intentionally aren't in the design system.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Palette colors that MUST use tokens in JS files.
# Add a color here when it has a named token in static/css/tokens.css.
PALETTE_TOKENS = {
    "#667eea": "var(--accent)",
    "#5a6fd6": "var(--accent-hover)",
    "#4f5fc4": "var(--accent-strong)",
    "#f0c674": "var(--highlight)",
    "#1a1a2e": "var(--surface-dark)",
    "#f8f9fa": "var(--surface-raised)",
    "#f5f5f5": "var(--surface-sunken)",
    "#ffffff": "var(--surface)",
    "#27ae60": "var(--status-success)",
    "#e74c3c": "var(--status-error)",
    "#c0392b": "var(--status-error-hover)",
}

# Files / directories where raw hex is acceptable (map APIs, vendor code).
ALLOWLIST_PATHS = {
    "agents/explore/static/js/explore-map.js",  # Leaflet marker colors
    "static/js/create-map.js",  # Leaflet marker colors
    "agents/explore/static/js/explore.js",  # Leaflet
}

HEX_RE = re.compile(r"#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b")

ROOT = Path(__file__).parent.parent


def check_file(path: Path) -> list[str]:
    rel = str(path.relative_to(ROOT))
    if rel in ALLOWLIST_PATHS:
        return []

    errors = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        # Lines tagged /* leaflet-stroke */ use raw hex as Leaflet API input (not CSS).
        if "leaflet-stroke" in line:
            continue
        for m in HEX_RE.finditer(line):
            raw = m.group(0).lower()
            # Normalise 3-digit shorthand
            if len(raw) == 4:
                raw = "#" + "".join(c * 2 for c in raw[1:])
            token = PALETTE_TOKENS.get(raw)
            if token:
                errors.append(f"  {rel}:{lineno}: {raw!r} -> use {token!r}\n    {line.strip()}")
    return errors


def main() -> int:
    js_files = list(ROOT.rglob("*.js"))
    js_files = [
        f
        for f in js_files
        if ".min." not in f.name and "node_modules" not in f.parts and ".venv" not in f.parts
    ]

    all_errors: list[str] = []
    for f in sorted(js_files):
        all_errors.extend(check_file(f))

    if all_errors:
        print("Hardcoded palette colors found in JS files.")
        print("Replace them with the design token shown (var(--...)).\n")
        for e in all_errors:
            print(e)
        print(
            f"\n{len(all_errors)} violation(s). Run scripts/check_hardcoded_colors.py to re-check."
        )
        return 1

    print("No hardcoded palette colors in JS files. Clean.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
