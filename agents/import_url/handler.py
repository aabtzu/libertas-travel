"""Handler for importing a shared URL into a trip."""

from __future__ import annotations

import database as db
from agents.create.upload_handlers import upload_plan_handler
from agents.create.web_utils import fetch_webpage_for_chat


def fetch_and_extract(url: str) -> dict:
    """Fetch a URL and extract trip items from the page text.

    Returns a dict with keys: success, items, title, error.
    """
    fetch = fetch_webpage_for_chat(url)
    if not fetch.get("success"):
        return {
            "success": False,
            "items": [],
            "title": url,
            "error": fetch.get("error", "Could not fetch page"),
        }

    text = fetch.get("text", "")
    title = fetch.get("title", url)

    if not text.strip():
        return {"success": False, "items": [], "title": title, "error": "Page had no readable text"}

    # Reuse the same parser as email import and file upload
    result, _status = upload_plan_handler(
        user_id=0,  # enrichment only, not saving yet
        filename="import.txt",
        file_data=text.encode("utf-8"),
        ext="txt",
    )

    items = result.get("items", []) if result.get("success") else []
    return {"success": True, "items": items, "title": title, "error": None}


def get_user_trips_for_picker(user_id: int) -> list[dict]:
    """Return non-archived trips (published + drafts) for the trip picker, most recent first."""
    published = db.get_user_trips(user_id)
    drafts = db.get_draft_trips(user_id)
    all_trips = []
    for t in published:
        if not t.get("is_archived"):
            all_trips.append(
                {"link": t["link"], "title": t.get("title") or t["link"], "is_draft": False}
            )
    for t in drafts:
        all_trips.append(
            {
                "link": t["link"],
                "title": (t.get("title") or t["link"]) + " (draft)",
                "is_draft": True,
            }
        )
    return all_trips


def add_items_to_trip(
    user_id: int, link: str, items: list[dict], url: str, page_title: str
) -> bool:
    """Append extracted items to a trip's ideas list."""
    trip = db.get_trip_by_link(user_id, link)
    if not trip:
        return False
    itinerary_data = trip.get("itinerary_data") or {
        "title": trip.get("title", ""),
        "days": [],
        "ideas": [],
        "travelers": [],
    }
    if "ideas" not in itinerary_data:
        itinerary_data["ideas"] = []

    # Tag items with their source URL and page title for reference
    for item in items:
        item.setdefault("source_url", url)
        item.setdefault("source_title", page_title)
        itinerary_data["ideas"].append(item)

    return db.update_trip_itinerary_data(user_id, link, itinerary_data)
