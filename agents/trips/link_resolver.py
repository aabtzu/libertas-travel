"""Resolve missing website URLs, Google Maps links, and locations for trip items."""

from __future__ import annotations

import json
import re
from typing import Any

from agents.common.llm import SONNET, make_llm


def fill_missing_links(itinerary_data: dict[str, Any], trip_title: str = "") -> dict:
    """Fill in missing location, website, and Google Maps URL fields on all
    items in a trip. Order matters: locations are filled FIRST so the
    other fillers can use the freshly-added city for disambiguation.

    Why locations matter: with no location, the geocoder uses just the
    item title. That works for "Hohenschwangau Castle" but breaks for
    ambiguous names like "Marienplatz" (Munich, Cologne, Stuttgart, ...)
    or "Hofbräuhaus", the geocoder picks the wrong city silently and the
    map ends up with markers in the wrong country.

    Returns: {"locations_added": N, "maps_added": N, "websites_added": N}.
    """
    all_items = list(itinerary_data.get("ideas", []))
    for day in itinerary_data.get("days", []):
        all_items.extend(day.get("items", []))

    locations_added = _fill_missing_locations(all_items, trip_title)
    maps_added = _fill_missing_maps_links(all_items)
    websites_added = _fill_missing_websites(all_items)

    return {
        "locations_added": locations_added,
        "maps_added": maps_added,
        "websites_added": websites_added,
    }


def _fill_missing_locations(items: list[dict], trip_title: str) -> int:
    """For each item with no location, ask the LLM for a 'City, Country'
    string. Trip-level context (title + the locations of items that DO
    have one) is passed in so the model can infer the right city for
    ambiguous titles."""
    need_location = [i for i in items if not (i.get("location") or "").strip()]
    if not need_location:
        return 0

    # Collect known locations to give the model trip-level context
    known_locations = sorted(
        {(i.get("location") or "").strip() for i in items if (i.get("location") or "").strip()}
    )
    context_lines = []
    if trip_title:
        context_lines.append(f"Trip: {trip_title}")
    if known_locations:
        context_lines.append("Other items in this trip are located in:")
        for loc in known_locations[:10]:
            context_lines.append(f"  - {loc}")
    context = "\n".join(context_lines) if context_lines else "(no other context)"

    titles = "\n".join(f"- {i.get('title', '')}" for i in need_location if i.get("title"))

    try:
        llm = make_llm(model=SONNET, max_tokens=1024)
        response = llm.call_api(
            system_prompt=(
                "You assign a 'City, Country' location to travel itinerary items. "
                "Return ONLY a JSON object mapping each item title (verbatim) to "
                'a "City, Country" string. If you cannot determine the city with '
                "high confidence, OMIT that item from the response, never guess. "
                "Use the trip context to disambiguate names that exist in multiple "
                "cities. No markdown fences, no commentary."
            ),
            messages=[
                {
                    "role": "user",
                    "content": (f"{context}\n\nFill in 'City, Country' for these items:\n{titles}"),
                }
            ],
            return_full_response=True,
        )
        text = response.content[0].text.strip()
        text = re.sub(r"^```\w*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
        suggestions = json.loads(text)
    except Exception as e:
        print(f"[LINKS] Location fill failed: {e}")
        return 0

    added = 0
    for item in need_location:
        suggested = suggestions.get(item.get("title", ""))
        if isinstance(suggested, str) and "," in suggested:
            item["location"] = suggested.strip()
            added += 1
    return added


def _fill_missing_maps_links(items: list[dict]) -> int:
    """Stub a Google Maps search URL for any item missing one."""
    added = 0
    for item in items:
        if not item.get("google_maps_link"):
            title = item.get("title", "")
            loc = item.get("location", "")
            if title:
                q = f"{title} {loc}".strip().replace(" ", "%20")
                item["google_maps_link"] = f"https://www.google.com/maps/search/?api=1&query={q}"
                added += 1
    return added


def _fill_missing_websites(items: list[dict]) -> int:
    """Ask the LLM for official websites for items missing one. Items
    whose existing website is a Google search fallback are also re-tried."""
    need_website = [
        i for i in items if not i.get("website") or "google.com/search" in str(i.get("website", ""))
    ]
    if not need_website:
        return 0

    names = "\n".join(f"- {i['title']} in {i.get('location', '')}" for i in need_website)
    try:
        llm = make_llm(model=SONNET, max_tokens=2048)
        response = llm.call_api(
            system_prompt="Return ONLY valid JSON, no markdown fences, no other text.",
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Find official website URLs for these venues. "
                        "Return JSON mapping name to url. Omit if unknown.\n\n"
                        f"{names}"
                    ),
                }
            ],
            return_full_response=True,
        )
        text = response.content[0].text.strip()
        text = re.sub(r"^```\w*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
        websites = json.loads(text)
    except Exception as e:
        print(f"[LINKS] Website lookup failed: {e}")
        return 0

    added = 0
    for item in need_website:
        url = websites.get(item["title"])
        if url and isinstance(url, str) and url.startswith("http"):
            item["website"] = url
            added += 1
        elif isinstance(item.get("website"), str) and "google.com/search" in item["website"]:
            item["website"] = ""  # Clear stale Google search fallback
    return added
