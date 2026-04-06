"""Core trip CRUD handlers for the Create agent.

Upload, chat, and parsing helpers have been extracted to sub-modules:
  - chat_handler.py    — LLM chat for venue recommendations
  - upload_handlers.py — file upload and URL import pipelines
  - file_parsers.py    — ICS, JSON, Excel, Word parsing
  - flight_utils.py    — airline/airport lookups, Google Flights URL parsing
  - itinerary_utils.py — Itinerary <-> DB data conversion, slugify, format_dates
  - web_utils.py       — HTML extraction, URL download, Google Drive conversion
"""

from __future__ import annotations

import os
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any

import database as db

# Re-export public API consumed by routes — keeps route imports unchanged
from agents.create.chat_handler import create_chat_handler  # noqa: F401
from agents.create.itinerary_utils import _convert_to_itinerary
from agents.create.upload_handlers import (  # noqa: F401
    upload_file_handler,
    upload_plan_handler,
    url_import_handler,
)

OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", Path(__file__).parent.parent.parent / "output"))


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _extract_home_location_flags(itinerary_data: dict[str, Any]) -> dict[str, bool]:
    """Return a mapping of item title -> is_home_location for all day items."""
    flags = {}
    for day in itinerary_data.get("days", []):
        for item in day.get("items", []):
            flags[item.get("title", "")] = bool(item.get("is_home_location", False))
    return flags


def _trigger_map_regen(user_id: int, link: str, itinerary_data: dict[str, Any]) -> None:
    """Clear cached map data and queue background geocoding."""
    import geocoding_worker

    db.update_trip_map_status(user_id, link, "processing", None)
    itinerary = _convert_to_itinerary(
        {"itinerary_data": itinerary_data, "title": itinerary_data.get("title", "Trip")}
    )
    if itinerary:
        geocoding_worker.queue_geocoding(link, itinerary)
        print(f"[SAVE] Queued map regen for {link}", flush=True)


def _generate_trip_html(trip: dict[str, Any], link: str) -> bool:
    """Generate HTML file for a trip. Returns True if successful."""
    try:
        itinerary = _convert_to_itinerary(trip)
        if itinerary and itinerary.items:
            from agents.itinerary.web_view import ItineraryWebView

            web_view = ItineraryWebView()
            web_view.generate(
                itinerary, OUTPUT_DIR / link, use_ai_summary=False, skip_geocoding=True
            )
            print(f"Generated HTML for trip: {link}")
            return True
    except Exception as e:
        print(f"Warning: Could not generate trip HTML: {e}")
        traceback.print_exc()

    return False


# ---------------------------------------------------------------------------
# Trip CRUD handlers
# ---------------------------------------------------------------------------


def create_trip_handler(user_id: int, data: dict[str, Any]) -> dict[str, Any]:
    """Create a new draft trip."""
    title = data.get("title", "").strip()
    if not title:
        return {"error": "Trip title is required"}, 400

    start_date = data.get("start_date")
    end_date = data.get("end_date")
    num_days = data.get("num_days")

    if num_days is not None:
        try:
            num_days = int(num_days)
            if num_days < 1 or num_days > 365:
                return {"error": "Number of days must be between 1 and 365"}, 400
        except (ValueError, TypeError):
            return {"error": "Invalid number of days"}, 400

    trip = db.create_draft_trip(
        user_id=user_id, title=title, start_date=start_date, end_date=end_date, num_days=num_days
    )

    if trip:
        return {"success": True, "trip": trip}, 200
    else:
        return {"error": "Failed to create trip"}, 500


def get_trip_data_handler(user_id: int, link: str) -> dict[str, Any]:
    """Get trip data for editing."""
    trip = db.get_trip_by_link(user_id, link)
    if trip:
        return {"success": True, "trip": trip}, 200
    else:
        return {"error": "Trip not found"}, 404


def save_trip_handler(user_id: int, link: str, data: dict[str, Any]) -> dict[str, Any]:
    """Auto-save trip itinerary data and title."""
    itinerary_data = data.get("itinerary_data")
    if itinerary_data is None:
        return {"error": "No itinerary data provided"}, 400

    needs_map_regen = False
    if "map_data" not in itinerary_data:
        existing_trip = db.get_trip_by_link(user_id, link)
        if existing_trip:
            existing_data = existing_trip.get("itinerary_data") or {}
            if existing_data.get("map_data"):
                old_flags = _extract_home_location_flags(existing_data)
                new_flags = _extract_home_location_flags(itinerary_data)
                if old_flags == new_flags:
                    itinerary_data["map_data"] = existing_data["map_data"]
                else:
                    print(f"[SAVE] is_home_location changed for {link}, will regen map")
                    needs_map_regen = True

    title = data.get("title")
    print(f"[SAVE] link={link}, title={title}")
    if title:
        db.update_trip(user_id, link, {"title": title})
        itinerary_data["title"] = title
        print(f"[SAVE] Updated title to: {title}")

    success = db.update_trip_itinerary_data(user_id, link, itinerary_data)

    if success:
        trip = db.get_trip_by_link(user_id, link)
        if trip and not trip.get("is_draft", True):
            _generate_trip_html(trip, link)

        if needs_map_regen:
            _trigger_map_regen(user_id, link, itinerary_data)

        return {
            "success": True,
            "saved_at": datetime.now().isoformat(),
            "map_regen": needs_map_regen,
        }, 200
    else:
        return {"error": "Failed to save trip"}, 500


def publish_trip_handler(user_id: int, link: str) -> dict[str, Any]:
    """Publish a draft trip (set is_draft=False) and generate HTML."""
    trip = db.get_trip_by_link(user_id, link)
    if not trip:
        return {"error": "Trip not found"}, 404

    print(f"[PUBLISH] link={link}, title from DB={trip.get('title')}")
    itinerary_data = trip.get("itinerary_data") or {}
    print(f"[PUBLISH] title from itinerary_data={itinerary_data.get('title')}")

    _generate_trip_html(trip, link)

    success = db.publish_draft(user_id, link)

    if success:
        return {"success": True}, 200
    else:
        return {"error": "Failed to publish trip"}, 500


def export_trip_handler(user_id: int, link: str) -> dict[str, Any]:
    """Export trip data as downloadable JSON."""
    trip = db.get_trip_by_link(user_id, link)

    if not trip:
        return {"error": "Trip not found"}, 404

    export_data = {
        "export_version": "1.0",
        "exported_at": datetime.now().isoformat(),
        "title": trip.get("title", "Untitled Trip"),
        "dates": trip.get("dates"),
        "days": trip.get("days"),
        "locations": trip.get("locations"),
        "activities": trip.get("activities"),
        "itinerary_data": trip.get("itinerary_data"),
        "is_public": trip.get("is_public", False),
    }

    return {"success": True, "export": export_data}, 200


def add_item_to_trip_handler(user_id: int, link: str, data: dict[str, Any]) -> dict[str, Any]:
    """Add an item to trip's ideas pile."""
    item = data.get("item")
    if not item:
        return {"error": "No item provided"}, 400

    if "title" not in item:
        return {"error": "Item must have a title"}, 400

    success = db.add_item_to_trip(user_id, link, item)

    if success:
        return {"success": True}, 200
    else:
        return {"error": "Failed to add item to trip"}, 500
