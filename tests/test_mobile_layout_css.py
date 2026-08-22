"""Guards for the mobile layout rules that keep the chat button reachable.

Background: the trip editor's chat button (``.mobile-chat-fab``) is
``position: fixed``, so it anchors to the layout viewport. When any element
overflows horizontally, mobile browsers widen the layout viewport to fit it
(measured: a 390px phone viewport became 736px), and the button is dragged
off-screen with it. Users could only reach it by scrolling sideways.

Three separate causes were found and fixed:
  1. ``.title-input`` had a hard ``min-width: 250px`` inside a nowrap flex
     row, so the header alone needed ~736px.
  2. The view-tab strip (Itinerary / Grid / Map / Calendar) plus the add-day
     button needed ~509px in a row that could not scroll.
  3. The chat sidebar was parked off-canvas with ``right: -100%``, which
     counts as scrollable overflow. A transform does not.

CI has no browser, so these are text assertions on the stylesheet. They are
deliberately narrow: each one pins an invariant that actually broke, and the
failure message says why it matters.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
CHAT_CSS = REPO_ROOT / "static" / "css" / "create-chat.css"
CREATE_HTML = REPO_ROOT / "agents" / "create" / "templates" / "create.html"

# The breakpoint the editor uses for its mobile layout.
MOBILE_BREAKPOINT = "@media (max-width: 900px)"


def _media_block(css: str, header: str) -> str:
    """Return the body of a media query, matched by braces.

    A plain regex is not enough here: the block contains nested rules, so we
    count braces from the opening one to find the matching close.
    """
    start = css.index(header)
    brace = css.index("{", start)
    depth = 0
    for i in range(brace, len(css)):
        if css[i] == "{":
            depth += 1
        elif css[i] == "}":
            depth -= 1
            if depth == 0:
                return css[brace + 1 : i]
    raise AssertionError(f"unbalanced braces after {header!r}")


def _rule(block: str, selector: str) -> str:
    """Return the declarations of the first rule matching ``selector``."""
    pattern = re.compile(
        r"(?:^|[},])\s*" + re.escape(selector) + r"\s*(?:,[^{]*)?\{([^}]*)\}",
        re.MULTILINE,
    )
    match = pattern.search(block)
    assert match, f"no rule for {selector!r} inside {MOBILE_BREAKPOINT}"
    return match.group(1)


@pytest.fixture(scope="module")
def mobile_css() -> str:
    return _media_block(CHAT_CSS.read_text(), MOBILE_BREAKPOINT)


def test_sidebar_is_parked_with_transform_not_a_negative_offset(mobile_css: str):
    """Off-canvas via transform, because transforms do not affect layout.

    ``right: -100%`` puts the panel outside the right edge, which counts as
    scrollable overflow and widens the mobile layout viewport.
    """
    rule = _rule(mobile_css, ".editor-sidebar")
    assert "translateX(100%)" in rule, (
        "the mobile chat sidebar must be parked off-canvas with a transform; "
        "a negative offset creates scrollable overflow that widens the "
        "layout viewport and pushes the fixed chat button off-screen"
    )
    assert not re.search(r"right:\s*-", rule), (
        "negative `right` on the off-canvas sidebar reintroduces the "
        "horizontal overflow this rule exists to avoid"
    )


def test_title_input_can_shrink_on_mobile(mobile_css: str):
    """The 250px floor on the title is what forced the header wide."""
    rule = _rule(mobile_css, ".title-input")
    assert re.search(r"min-width:\s*0", rule), (
        "`.title-input` must clear its desktop `min-width: 250px` on mobile; "
        "a flex item will not shrink below the intrinsic width of an <input> "
        "without it, which pushes the whole header past the screen width"
    )


def test_header_action_row_wraps_instead_of_squashing(mobile_css: str):
    rule = _rule(mobile_css, ".header-right")
    assert "flex-wrap: wrap" in rule, (
        "`.header-right` must wrap on mobile; without it the save button is "
        "compressed below its own label and the remainder spills as overflow"
    )


def test_tab_strip_scrolls_instead_of_widening_the_page(mobile_css: str):
    rule = _rule(mobile_css, ".timeline-tabs")
    assert "overflow-x: auto" in rule, (
        "the view-tab strip must scroll inside its own box; the four tabs "
        "plus the add-day button need more room than a phone screen"
    )
    assert re.search(r"min-width:\s*0", rule), (
        "overflow-x alone does nothing here: a flex item will not shrink "
        "below its content's intrinsic width unless min-width is cleared, so "
        "the strip has nothing to scroll inside"
    )


def test_editor_contains_residual_horizontal_overflow(mobile_css: str):
    """Backstop so a future stray element cannot widen the viewport."""
    rule = _rule(mobile_css, ".create-container")
    assert "overflow-x: hidden" in rule, (
        "`.create-container` must contain horizontal overflow on mobile so "
        "the layout viewport stays at the phone width and the fixed chat "
        "button stays on screen"
    )


def test_mobile_rules_target_selectors_that_exist_in_the_template(mobile_css: str):
    """A previous rule targeted `.header-title input`, which matches nothing.

    That is why the title kept its desktop size on phones for so long. Any
    header selector styled for mobile must actually appear in create.html.
    """
    html = CREATE_HTML.read_text()
    for selector in (".header-left", ".header-right", ".title-input"):
        if selector in mobile_css:
            css_class = selector.lstrip(".")
            assert css_class in html, (
                f"{selector} is styled for mobile but no element in "
                f"create.html carries that class, so the rule is dead"
            )
    assert "header-title" not in html, (
        "create.html does not use `.header-title`; if it is reintroduced, "
        "update the mobile header rules to match"
    )


def test_chat_button_is_a_direct_child_of_body(mobile_css: str):
    """position: fixed anchors to the viewport only if no ancestor creates a
    containing block, so the button is deliberately kept outside the editor.
    """
    html = CREATE_HTML.read_text()
    match = re.search(r'<button class="mobile-chat-fab".*?</button>', html, re.DOTALL)
    assert match, "the mobile chat button is missing from create.html"
    after = html[match.end() :]
    # Only the closing body/html tags and scripts may follow it.
    assert "</body>" in after, "chat button must sit at the end of the document body"
    assert "<div" not in after.split("</body>")[0], (
        "the chat button must remain a direct child of <body>; nesting it "
        "inside a transformed or filtered ancestor would make position:fixed "
        "resolve against that ancestor instead of the viewport"
    )
