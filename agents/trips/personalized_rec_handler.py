"""Handler for creating personalized recommendation trips from an existing trip.

The user provides a free-form directive ('just Lima restaurants', 'only outdoor
activities') and an LLM filters the trip items to match. The filtered items are
stored as a new recommendation trip with a shareable /r/<link> URL.
"""

from __future__ import annotations

import json
import re
from typing import Any

import database as db
from agents.common.llm import HAIKU, make_llm
from agents.pages.recommendation_view import _collect_all_items, _extract_city

_SKIP_CATEGORIES = {"flight", "transport", "home", "train"}

_FILTER_SYSTEM = """You are a trip assistant. The user wants to create a
personalized recommendation list from a trip's items.

Given a list of trip items and a directive, select which items best match the
directive. Return ONLY a JSON array of item titles to include (exact match to
the title field). No commentary, no markdown, just the JSON array."""


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower().strip())[:30].strip("_")


def _make_rec_link(source_link: str, directive: str) -> str:
    base = source_link.replace(".html", "")
    suffix = _slug(directive)
    candidate = f"{base}_{suffix}.html"
    # Trim if too long (DB slug length limit is practical around 120 chars)
    if len(candidate) > 120:
        candidate = f"{base[:80]}_{suffix}.html"
    return candidate


def _filter_items_with_llm(items: list[dict], directive: str) -> list[dict]:
    """Ask the LLM which items match the directive. Fall back to all items on error."""
    if not items:
        return []

    item_list = [
        {
            "title": i.get("title", ""),
            "category": i.get("category", "other"),
            "location": _extract_city(i.get("location", "")),
        }
        for i in items
    ]
    prompt = (
        f"Directive: {directive}\n\n"
        f"Items:\n{json.dumps(item_list, indent=2)}\n\n"
        "Return a JSON array of titles to include."
    )
    try:
        llm = make_llm(model=HAIKU, max_tokens=1024)
        raw = llm.call_api(
            system_prompt=_FILTER_SYSTEM, messages=[{"role": "user", "content": prompt}]
        )
        # raw may be str or object with .content
        text = raw if isinstance(raw, str) else (raw.content[0].text if raw.content else "")
        # Extract JSON array from response
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if not match:
            return items
        selected_titles = {t.lower().strip() for t in json.loads(match.group())}
        return [i for i in items if i.get("title", "").lower().strip() in selected_titles]
    except Exception as e:
        print(f"[personalized_rec] LLM filter error: {e}")
        return items  # fail open - return everything


def create_personalized_rec_handler(
    user_id: int, source_link: str, directive: str
) -> tuple[dict[str, Any], int]:
    """Create a new recommendation trip filtered by the given directive."""
    directive = directive.strip()
    if not directive:
        return {"error": "Directive is required"}, 400

    # Verify the user can read the source trip (owner or collaborator)
    owner_id = db.get_trip_owner(source_link)
    if owner_id is None:
        return {"error": "Trip not found"}, 404
    if not db.can_user_edit_trip(source_link, user_id):
        return {"error": "You do not have access to this trip"}, 403

    source_trip = db.get_trip_by_link(owner_id, source_link)
    if not source_trip:
        return {"error": "Trip not found"}, 404

    itinerary_data = source_trip.get("itinerary_data") or {}
    all_items = [
        i for i in _collect_all_items(itinerary_data) if i.get("category") not in _SKIP_CATEGORIES
    ]

    filtered = _filter_items_with_llm(all_items, directive)
    if not filtered:
        return {"error": "No items matched the directive"}, 400

    rec_link = _make_rec_link(source_link, directive)

    # Check for existing trip at this link (same user, same directive)
    existing_owner = db.get_trip_owner(rec_link)
    if existing_owner is not None:
        # Already exists - just return the link
        return {
            "success": True,
            "link": rec_link,
            "url": f"/r/{rec_link.replace('.html', '')}",
            "count": len(filtered),
        }, 200

    rec_itinerary = {
        "title": f"{source_trip.get('title', 'Trip')} - {directive.title()}",
        "ideas": filtered,
        "days": [],
    }
    trip_data = {
        "title": rec_itinerary["title"],
        "link": rec_link,
        "trip_type": "recommendation",
        "map_status": "pending",
    }
    db.add_trip(user_id, trip_data, rec_itinerary)
    db.update_trip(user_id, rec_link, {"title": rec_itinerary["title"]})

    return {
        "success": True,
        "link": rec_link,
        "url": f"/r/{rec_link.replace('.html', '')}",
        "count": len(filtered),
    }, 200
