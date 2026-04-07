"""
Canonical category → icon and category → color mappings.

Single source of truth for the Python side. The JS equivalent lives in
static/js/main.js (CATEGORY_ICONS / CATEGORY_COLORS). Keep these in sync.

Usage:
    from agents.common.categories import CATEGORY_ICONS, CATEGORY_COLORS
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
CANONICAL_CATEGORIES = frozenset([
    "flight", "train", "bus", "transport",
    "hotel", "meal", "activity", "attraction",
    "home", "other",
])


def normalize_category(raw: str) -> str:
    """Map any raw category string to its canonical name.

    Already-canonical values pass through unchanged.  Unknown values fall
    back to 'activity' (safe default — better than 'other' for most items).
    """
    key = (raw or "").strip().lower()
    if key in CANONICAL_CATEGORIES:
        return key
    return _CATEGORY_ALIASES.get(key, "activity")


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
