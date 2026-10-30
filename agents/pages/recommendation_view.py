"""Data preparation for recommendation and write-up page templates."""

from __future__ import annotations

import html as html_mod
import re
from typing import Any

from agents.common.categories import CATEGORY_ICONS
from agents.common.templates import get_nav_html

_CATEGORY_LABELS = {
    "meal": "Restaurants",
    "activity": "Activities",
    "attraction": "Attractions",
    "hotel": "Hotels",
    "flight": "Flights",
    "transport": "Transport",
    "other": "Other",
}

# Categories that are logistical, not planning-relevant for a rec page.
_SKIP_CATEGORIES = {"flight", "transport", "home", "train"}

# Sentence-level patterns that indicate booking/logistical details.
# We strip any sentence matching these from rec notes.
_BOOKING_PATTERNS = [
    re.compile(r"phone[\s:]+[\+\d\-\(\)\s]+", re.IGNORECASE),
    re.compile(r"\+\d[\d\-\(\)\s]{6,}"),  # phone numbers
    re.compile(r"check[- ](in|out)\b", re.IGNORECASE),
    re.compile(r"\bconfirm(ation)?\b.*(number|code|#)", re.IGNORECASE),
    re.compile(r"included in (trip |the )?price", re.IGNORECASE),
    re.compile(r"fare class\b", re.IGNORECASE),
    re.compile(r"\boperated by\b", re.IGNORECASE),
    re.compile(r"departs?\s+\w+[- ]\w+", re.IGNORECASE),  # "departs NYC-Kennedy"
    re.compile(r"arrives?\s+\w+[- ]\w+", re.IGNORECASE),
    re.compile(r"luggage (left|stored|drop)", re.IGNORECASE),
    re.compile(r"passport (information|required)", re.IGNORECASE),
    re.compile(r"booked?\s+(at|via|through|using)\b", re.IGNORECASE),
    re.compile(r"(total )?duration:\s*\d", re.IGNORECASE),
    re.compile(r"shuttle duration\b", re.IGNORECASE),
    re.compile(r"ticket(s)? secured\b", re.IGNORECASE),
    re.compile(r"\bDay \d\b"),  # "Day 1", "Day 3"
]


def _clean_rec_notes(notes: str) -> str:
    """Strip booking/logistical sentences from notes for planning-oriented rec pages."""
    if not notes:
        return ""
    sentences = re.split(r"(?<=[.!?])\s+", notes.strip())
    clean = [s for s in sentences if not any(p.search(s) for p in _BOOKING_PATTERNS)]
    return " ".join(clean).strip()


def _md_to_html(text: str) -> str:
    """Minimal markdown to HTML: bold, italic, headers, links, line breaks."""
    text = html_mod.escape(text)
    text = re.sub(r"^### (.+)$", r"<h3>\1</h3>", text, flags=re.MULTILINE)
    text = re.sub(r"^## (.+)$", r"<h2>\1</h2>", text, flags=re.MULTILINE)
    text = re.sub(r"^# (.+)$", r"<h1>\1</h1>", text, flags=re.MULTILINE)
    text = re.sub(
        r"\[(.+?)\]\((https?://[^\)]+)\)",
        r'<a href="\2" target="_blank" rel="noopener">\1</a>',
        text,
    )
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
    text = text.replace("\n\n", "</p><p>")
    text = text.replace("\n", "<br>")
    return f"<p>{text}</p>"


# Administrative suffixes that make a city name too specific for grouping.
_REGION_SUFFIXES = re.compile(
    r"\s+(Region|Province|District|Department|Prefecture|County|State|Area)\b.*$",
    re.IGNORECASE,
)


def _extract_city(location: str) -> str:
    """Extract the city name from a location string, normalizing sub-region variants.

    'Soraypampa, Cusco Region, Peru' -> 'Cusco'
    'Miraflores, Lima, Peru'         -> 'Lima'
    'Cusco, Peru'                    -> 'Cusco'
    'Lima'                           -> 'Lima'
    """
    if not location:
        return "Other"
    parts = [p.strip() for p in location.split(",")]

    if len(parts) >= 3:
        # "Venue, City, Country" - take the middle part
        city = parts[-2]
    elif len(parts) == 2:
        # "City, Country" - take the first part
        city = parts[0]
    else:
        city = parts[0]

    # Strip administrative suffixes so "Cusco Region" -> "Cusco"
    city = _REGION_SUFFIXES.sub("", city).strip()
    return city or "Other"


def _collect_all_items(itinerary_data: dict) -> list:
    items = list(itinerary_data.get("ideas", []))
    for day in itinerary_data.get("days", []):
        for item in day.get("items", []):
            items.append(item)
    return items


def _build_markers(all_items: list) -> list:
    return [
        {
            "lat": i["latitude"],
            "lng": i["longitude"],
            "title": i.get("title", ""),
            "category": i.get("category", "other"),
        }
        for i in all_items
        if i.get("latitude") and i.get("longitude")
    ]


def build_recommendation_context(
    title: str, itinerary_data: dict[str, Any], trip_link: str = ""
) -> dict:
    """Return template context for the recommendation page."""
    all_items = _collect_all_items(itinerary_data)

    # Deduplicate items by title within each location group so items that
    # appear in both ideas and days don't show twice.
    seen: set[tuple[str, str]] = set()
    location_map: dict[str, dict] = {}
    for item in all_items:
        cat = item.get("category", "other")
        if cat in _SKIP_CATEGORIES:
            continue
        title_key = item.get("title", "").strip().lower()
        loc_raw = item.get("location", "")
        loc_key = _extract_city(loc_raw)
        dedup_key = (title_key, loc_key)
        if dedup_key in seen:
            continue
        seen.add(dedup_key)

        if loc_key not in location_map:
            location_map[loc_key] = {}
        if cat not in location_map[loc_key]:
            location_map[loc_key][cat] = []
        location_map[loc_key][cat].append(item)

    location_groups = [
        {
            "name": loc_name,
            "categories": [
                {
                    "label": _CATEGORY_LABELS.get(cat, cat.title()),
                    "icon": CATEGORY_ICONS.get(cat, "fa-map-marker-alt"),
                    "venues": [
                        {
                            "title": i.get("title", ""),
                            "notes": _clean_rec_notes(i.get("notes", "")),
                            "website": i.get("website", ""),
                            "google_maps_link": i.get("google_maps_link", ""),
                        }
                        for i in items
                    ],
                }
                for cat, items in cat_groups.items()
            ],
        }
        for loc_name, cat_groups in location_map.items()
        if cat_groups
    ]

    return {
        "nav": get_nav_html(""),
        "title": title,
        "item_count": len(all_items),
        "trip_link": trip_link,
        "location_groups": location_groups,
        "tips": itinerary_data.get("tips", []),
        "markers": _build_markers(all_items),
    }


def build_writeup_context(
    title: str,
    writeup_text: str,
    itinerary_data: dict[str, Any] | None = None,
    trip_link: str = "",
) -> dict:
    """Return template context for the write-up page."""
    all_items = _collect_all_items(itinerary_data) if itinerary_data else []
    venues_with_links = [i for i in all_items if i.get("website") or i.get("google_maps_link")]

    return {
        "nav": get_nav_html(""),
        "title": title,
        "content": _md_to_html(writeup_text),
        "trip_link": trip_link,
        "markers": _build_markers(all_items),
        "venues_with_links": [
            {
                "title": i.get("title", ""),
                "website": i.get("website", ""),
                "google_maps_link": i.get("google_maps_link", ""),
            }
            for i in venues_with_links
        ],
    }
