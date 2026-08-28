"""Guards for the design-consistency fixes from the audit in issue #150.

These pin invariants that were violated in the code as shipped, so a
regression is caught rather than rediscovered by eye months later. CI has no
browser, so the CSS and JS checks are text assertions; the category colour
check is a real import and comparison.
"""

from __future__ import annotations

import re
from pathlib import Path

from agents.common.categories import CATEGORY_COLORS

REPO_ROOT = Path(__file__).resolve().parent.parent
MAIN_CSS = REPO_ROOT / "static" / "css" / "main.css"
CALENDAR_JS = REPO_ROOT / "static" / "js" / "calendar-export.js"

CSS_FILES = sorted(
    list((REPO_ROOT / "static" / "css").glob("*.css"))
    + list(REPO_ROOT.glob("agents/*/static/css/*.css"))
)
JS_FILES = sorted(
    list((REPO_ROOT / "static" / "js").glob("*.js"))
    + list(REPO_ROOT.glob("agents/*/static/js/*.js"))
)


def _relative(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT))


class TestCategoryColorsAreShared:
    """Audit finding 1: the map used a different palette from everything else.

    Every category rendered in two unrelated colours: a flight was blue in the
    list and red on the map, a hotel purple in the list and blue on the map.
    Colour is what teaches a user what a category is, so it has to agree.
    """

    def test_marker_colors_come_from_the_shared_palette(self):
        from agents.itinerary.mapper import marker_color

        for category, expected in CATEGORY_COLORS.items():
            assert marker_color(category) == expected, (
                f"map marker for {category!r} is {marker_color(category)} but the "
                f"list and grid use {expected}; markers must read from "
                f"CATEGORY_COLORS so the two views agree"
            )

    def test_no_second_marker_palette_remains(self):
        source = (REPO_ROOT / "agents" / "itinerary" / "mapper.py").read_text()
        assert "MARKER_COLORS" not in source, (
            "MARKER_COLORS was a separate Google Maps palette that made every "
            "category render in two different colours; do not reintroduce it"
        )

    def test_location_types_map_onto_a_category(self):
        """location_type is finer-grained than category and must still resolve."""
        from agents.itinerary.mapper import marker_color

        assert marker_color("flight", "airport") == CATEGORY_COLORS["flight"]
        assert marker_color("transport", "train_station") == CATEGORY_COLORS["train"]

    def test_unknown_category_falls_back_like_the_frontend(self):
        """create-map.js does `CATEGORY_COLORS[cat] || CATEGORY_COLORS.other`.

        Python must match. normalize_category is deliberately not used here:
        it falls back to "activity", which would paint an unknown item green
        on the generated map and grey on the editor's map, recreating exactly
        the mismatch this whole change removes.
        """
        from agents.itinerary.mapper import marker_color

        assert marker_color("no-such-category") == CATEGORY_COLORS["other"]
        assert marker_color(None) == CATEGORY_COLORS["other"]


class TestKeyboardFocusIsVisible:
    """Audit finding 4: home and the public trip view had no focus styling.

    Anyone navigating by keyboard or switch could not see where they were.
    """

    def test_a_global_focus_visible_rule_exists(self):
        css = MAIN_CSS.read_text()
        assert ":focus-visible" in css, (
            "main.css must carry a global :focus-visible rule; it is the only "
            "stylesheet loaded on every page, so it is what makes focus "
            "visible on pages that define no focus styling of their own"
        )
        match = re.search(r"([^{}]*:focus-visible[^{}]*)\{([^}]*)\}", css)
        assert match and "outline" in match.group(2), "the focus rule must actually draw an outline"

    def test_nothing_removes_an_outline_without_replacing_it(self):
        """`outline: none` is fine only when the rule draws its own indicator.

        Most focus styles here legitimately swap the outline for a coloured
        border plus a ring, which is a visible substitute. What is not fine
        is dropping the outline and drawing nothing in its place.
        """
        substitutes = ("border", "box-shadow", "background", "outline-offset")
        offenders = []
        for path in CSS_FILES:
            # Strip comments first: prose about `outline: none` is not code.
            css = re.sub(r"/\*.*?\*/", "", path.read_text(), flags=re.DOTALL)
            for selector, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
                if not re.search(r"outline:\s*(none|0)\b", body):
                    continue
                if any(s in body for s in substitutes):
                    continue
                offenders.append(f"{_relative(path)}: {selector.strip()[:44]}")
        assert not offenders, (
            "these rules remove the focus outline and draw nothing in its "
            "place, so the element has no visible focus state:\n  "
            + "\n  ".join(offenders)
            + "\nSwap in a border, ring or background change instead."
        )


class TestTextContrast:
    """Audit finding 3: hint and empty-state text was unreadable.

    #999 on white is 2.85:1 and #888 is 3.54:1, against a WCAG AA minimum of
    4.5:1 for normal text. That put the lowest contrast on exactly the text a
    new user most needs: empty states and placeholders.
    """

    FAILING_TEXT_GREYS = ("#999999", "#999", "#888888", "#888")

    def test_failing_greys_are_not_used_for_text(self):
        offenders = []
        for path in CSS_FILES:
            for i, line in enumerate(path.read_text().splitlines(), 1):
                match = re.search(r"(?<![-\w])color:\s*(#[0-9a-fA-F]{3,6})\b", line)
                if match and match.group(1).lower() in self.FAILING_TEXT_GREYS:
                    offenders.append(f"{_relative(path)}:{i} {line.strip()[:50]}")
        assert not offenders, (
            "these greys fail WCAG AA as text (#999 is 2.85:1 on white, #888 "
            "is 3.54:1, the minimum is 4.5:1). Use #666, which is 5.74:1 on "
            "white and still passes on the grey backgrounds this app uses:\n  "
            + "\n  ".join(offenders)
        )


class TestNoBrowserDialogs:
    """Audit finding 6, and an existing CLAUDE.md rule.

    alert() and confirm() are unstyleable, block the page, and look nothing
    like the rest of the app. LibertasModal exists to replace them.
    """

    def test_no_bare_alert_confirm_or_prompt(self):
        offenders = []
        pattern = re.compile(r"(?<![.\w])(alert|confirm|prompt)\s*\(")
        for path in JS_FILES:
            for i, line in enumerate(path.read_text().splitlines(), 1):
                stripped = line.strip()
                if stripped.startswith(("*", "//", "/*")):
                    continue
                if pattern.search(line):
                    offenders.append(f"{_relative(path)}:{i} {stripped[:60]}")
        assert not offenders, (
            "use LibertasModal.alert() / LibertasModal.confirm() from main.js "
            "instead of the browser dialogs (CLAUDE.md, CSS / Visual Style):\n  "
            + "\n  ".join(offenders)
        )

    def test_calendar_export_uses_the_shared_modal(self):
        js = CALENDAR_JS.read_text()
        assert "LibertasModal.alert(" in js, (
            "calendar-export.js reports its errors through LibertasModal; it "
            "is loaded only on trips.html, which loads main.js first"
        )


class TestDesignTokens:
    """The token layer from issue #150.

    Colours are defined once and referenced by role. A raw hex in a feature
    stylesheet is how this codebase accumulated 97 colours and six separate
    category palettes.
    """

    def test_root_tokens_are_declared_once(self):
        """Only main.css may declare the shared :root palette."""
        declaring = [
            _relative(p)
            for p in CSS_FILES
            if re.search(r"^:root\s*\{", p.read_text(), re.MULTILINE)
        ]
        assert declaring == ["static/css/tokens.css"], (
            f"the :root palette must live only in tokens.css, found it in "
            f"{declaring}. A second declaration silently wins by cascade "
            f"order, which is exactly how categories.css made a flight cyan "
            f"while the rest of the app drew it blue"
        )

    def test_no_stylesheet_redefines_a_category_token(self):
        """Category colours come from /app-config.css, served from Python."""
        offenders = []
        for path in CSS_FILES:
            for i, line in enumerate(path.read_text().splitlines(), 1):
                if re.match(r"\s*--cat-[a-z-]+\s*:", line):
                    offenders.append(f"{_relative(path)}:{i}")
        assert not offenders, (
            "category colours are owned by agents/common/categories.py and "
            "served as custom properties by /app-config.css; consume them "
            "with var(--cat-<name>), never redeclare them:\n  " + "\n  ".join(offenders)
        )

    def test_every_category_token_used_is_actually_served(self):
        from agents.common.categories import CATEGORY_COLORS

        served = set()
        for cat in CATEGORY_COLORS:
            served |= {f"--cat-{cat}", f"--cat-{cat}-tint", f"--cat-{cat}-ink"}
        used = set()
        for path in CSS_FILES:
            used |= set(re.findall(r"var\((--cat-[a-z-]+)\)", path.read_text()))
        assert not (used - served), (
            f"these category tokens are referenced but never served by "
            f"/app-config.css: {sorted(used - served)}"
        )


class TestDerivedCategoryContrast:
    """The tint and ink variants must stay readable together.

    They are derived from CATEGORY_COLORS, so changing a category colour
    changes both. This is the check that stops a palette tweak from quietly
    making a badge unreadable.
    """

    @staticmethod
    def _ratio(a: str, b: str) -> float:
        def lum(h: str) -> float:
            h = h.lstrip("#")
            channels = [int(h[i : i + 2], 16) / 255 for i in (0, 2, 4)]
            channels = [
                c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels
            ]
            return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]

        high, low = max(lum(a), lum(b)), min(lum(a), lum(b))
        return (high + 0.05) / (low + 0.05)

    def test_ink_is_readable_on_its_own_tint(self):
        """Badges put -ink text on a -tint background."""
        from agents.common.categories import CATEGORY_INKS, CATEGORY_TINTS

        for cat, ink in CATEGORY_INKS.items():
            ratio = self._ratio(ink, CATEGORY_TINTS[cat])
            assert ratio >= 4.5, (
                f"{cat}: ink {ink} on tint {CATEGORY_TINTS[cat]} is "
                f"{ratio:.2f}:1, below the 4.5:1 minimum. If you changed a "
                f"category colour or _INK_STRENGTH in categories.py, the "
                f"derived pair no longer holds"
            )

    def test_white_is_readable_on_ink(self):
        """Calendar chips and category badges put white text on -ink."""
        from agents.common.categories import CATEGORY_INKS

        for cat, ink in CATEGORY_INKS.items():
            ratio = self._ratio("#ffffff", ink)
            assert ratio >= 4.5, (
                f"{cat}: white on ink {ink} is {ratio:.2f}:1, below 4.5:1. "
                f"White on the undarkened category colour is as low as "
                f"2.15:1, which is why these use the ink variant"
            )

    def test_app_config_css_serves_every_category(self, client):
        from agents.common.categories import CATEGORY_COLORS

        resp = client.get("/app-config.css")
        assert resp.status_code == 200
        assert resp.mimetype == "text/css"
        body = resp.get_data(as_text=True)
        for cat, color in CATEGORY_COLORS.items():
            assert f"--cat-{cat}: {color};" in body, f"{cat} missing from /app-config.css"
            assert f"--cat-{cat}-tint:" in body
            assert f"--cat-{cat}-ink:" in body


def test_pages_that_use_category_tokens_load_the_stylesheet():
    """A page referencing var(--cat-*) must link /app-config.css.

    Otherwise the token resolves to nothing and the element renders unstyled.
    """
    pages = [
        p
        for p in list(REPO_ROOT.glob("agents/*/templates/*.html"))
        if "/static/css/main.css" in p.read_text()
    ]
    missing = [_relative(p) for p in pages if "/app-config.css" not in p.read_text()]
    assert not missing, (
        "these pages load the app stylesheets but not the category tokens "
        "they depend on:\n  " + "\n  ".join(missing)
    )
