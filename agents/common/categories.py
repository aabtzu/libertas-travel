"""
Canonical category → icon and category → color mappings, plus shared date helpers.

Single source of truth. JS reads CATEGORY_ICONS/COLORS via /app-config.js (served by
pages/routes.py), so there is no separate JS copy to keep in sync.

Usage:
    from agents.common.categories import CATEGORY_ICONS, CATEGORY_COLORS
    from agents.common.categories import get_trip_date_range, get_trip_start_date
"""

# Aliases: raw strings the LLM or parsers might produce → canonical category name.
# Add new aliases here; nowhere else.
_CATEGORY_ALIASES: dict[str, str] = {
    # flight
    "air": "flight",
    "plane": "flight",
    "travel": "flight",
    # train
    "rail": "train",
    # bus
    "coach": "bus",
    # transport
    "car": "transport",
    "transportation": "transport",
    "transfer": "transport",
    # hotel
    "accommodation": "hotel",
    "lodging": "hotel",
    "stay": "hotel",
    "hostel": "hotel",
    # meal
    "restaurant": "meal",
    "food": "meal",
    "dining": "meal",
    "breakfast": "meal",
    "lunch": "meal",
    "dinner": "meal",
    # activity
    "event": "activity",
    # attraction
    "sightseeing": "attraction",
    "museum": "attraction",
    "tour": "attraction",
}

# The set of canonical category names (values in CATEGORY_ICONS).
CANONICAL_CATEGORIES = frozenset(
    [
        "flight",
        "train",
        "bus",
        "transport",
        "hotel",
        "meal",
        "activity",
        "attraction",
        "home",
        "other",
    ]
)


def normalize_category(raw: str) -> str:
    """Map any raw category string to its canonical name.

    Already-canonical values pass through unchanged.  Unknown values fall
    back to 'activity' (safe default, better than 'other' for most items).
    """
    key = (raw or "").strip().lower()
    if key in CANONICAL_CATEGORIES:
        return key
    return _CATEGORY_ALIASES.get(key, "activity")


# Categories that represent transport/travel (go in the Travel column, use arrow separator).
# Add any new transport type here, web_view.py and other renderers import this.
TRAVEL_CATEGORIES: frozenset[str] = frozenset(["flight", "transport", "train", "bus"])

CATEGORY_ICONS: dict[str, str] = {
    "flight": "fa-plane",
    "travel": "fa-plane",
    "train": "fa-train",
    "bus": "fa-bus",
    "transport": "fa-car",
    "hotel": "fa-bed",
    "lodging": "fa-bed",
    "meal": "fa-utensils",
    "restaurant": "fa-utensils",
    "activity": "fa-star",
    "attraction": "fa-landmark",
    "home": "fa-home",
    "other": "fa-calendar-day",
}

CATEGORY_COLORS: dict[str, str] = {
    "flight": "#3b82f6",
    "travel": "#3b82f6",
    "train": "#f59e0b",
    "bus": "#f59e0b",
    "transport": "#f59e0b",
    "hotel": "#8b5cf6",
    "lodging": "#8b5cf6",
    "meal": "#ef4444",
    "restaurant": "#ef4444",
    "activity": "#22c55e",
    "attraction": "#06b6d4",
    "other": "#6b7280",
}


# Derived category colours.
#
# CATEGORY_COLORS above is the single source. These two are computed from it
# so a palette change flows everywhere and cannot drift, which is exactly how
# the app previously ended up with four different colour schemes for the same
# categories (issue #150).
#
#   *_TINT  a pale wash for a badge or row background
#   *_INK   a darkened version of the colour, readable as text on that tint
#
# The 60% figure is the most saturated darkening where every category clears
# WCAG AA (4.5:1) against its own tint; the worst case, amber, lands at
# 4.95:1. Keeping more of the colour looks better but fails: at 65% amber
# drops to 4.35:1. test_design_consistency.py enforces this, so changing
# these constants without rechecking contrast will fail the build.
_TINT_STRENGTH = 0.12
_INK_STRENGTH = 0.60


def _blend(color: str, other: str, keep: float) -> str:
    """Mix ``color`` with ``other``, keeping ``keep`` of the original."""
    a = [int(color.lstrip("#")[i : i + 2], 16) for i in (0, 2, 4)]
    b = [int(other.lstrip("#")[i : i + 2], 16) for i in (0, 2, 4)]
    mixed = (round(a[i] * keep + b[i] * (1 - keep)) for i in range(3))
    return "#{:02x}{:02x}{:02x}".format(*mixed)


CATEGORY_TINTS: dict[str, str] = {
    cat: _blend(color, "#ffffff", _TINT_STRENGTH) for cat, color in CATEGORY_COLORS.items()
}

CATEGORY_INKS: dict[str, str] = {
    cat: _blend(color, "#000000", _INK_STRENGTH) for cat, color in CATEGORY_COLORS.items()
}


def get_trip_start_date(itinerary_data: dict) -> str | None:
    """Return the trip start date, falling back to the first day in the days array."""
    if not itinerary_data:
        return None
    if itinerary_data.get("start_date"):
        return itinerary_data["start_date"]
    days = itinerary_data.get("days", [])
    if days:
        first = days[0]
        if isinstance(first, dict) and first.get("date"):
            return first["date"]
    return None


def get_trip_date_range(itinerary_data: dict) -> tuple[str, str]:
    """Return (start_date, end_date), falling back to the days array when top-level fields absent."""
    start = itinerary_data.get("start_date") or ""
    end = itinerary_data.get("end_date") or ""
    if start and end:
        return start, end
    day_dates = [d["date"] for d in itinerary_data.get("days", []) if d.get("date")]
    if day_dates:
        return min(day_dates), max(day_dates)
    return "", ""
