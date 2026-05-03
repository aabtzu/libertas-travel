"""Admin handler: trip regeneration utilities."""

from __future__ import annotations

import json
import os
import traceback
from pathlib import Path

import database as db

OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", Path(__file__).parent.parent.parent / "output"))

# Fixture paths for seeded demo trips
_FIXTURES_DIR = Path(__file__).parent.parent.parent / "tests" / "fixtures"

# Fixed link for the Paris demo trip referenced in how-it-works.html.
# Must include .html suffix — that's how all trips are stored in the DB,
# and the route strips .html from the URL then appends it for the DB lookup.
_PARIS_DEMO_LINK = "paris_provence_adventure.html"


def regenerate_all_trip_html(user_id: int | None = None) -> dict:
    """Regenerate HTML for all trips from their itinerary_data.

    Also fixes dates and days columns in the database.
    Returns dict with regenerated count, skipped count, and errors.
    """
    from agents.create.handler import _convert_to_itinerary
    from agents.itinerary.templates import format_trip_date, get_trip_start_date
    from agents.itinerary.web_view import ItineraryWebView

    results: dict = {"regenerated": 0, "errors": [], "skipped": 0, "db_updated": 0}

    try:
        trips = db.get_user_trips(user_id if user_id is not None else 1)

        for trip in trips:
            link = trip.get("link", "")
            title = trip.get("title", "Unknown")
            itinerary_data_raw = trip.get("itinerary_data")
            current_dates = trip.get("dates", "")
            current_days = trip.get("days", 0)

            if not itinerary_data_raw or not link:
                results["skipped"] += 1
                print(f"[REGEN] Skipped {title}: no itinerary_data or link")
                continue

            try:
                itinerary_data = (
                    json.loads(itinerary_data_raw)
                    if isinstance(itinerary_data_raw, str)
                    else itinerary_data_raw
                )

                itinerary = _convert_to_itinerary(
                    {"itinerary_data": itinerary_data, "title": title}
                )

                if not itinerary or not itinerary.items:
                    results["skipped"] += 1
                    print(f"[REGEN] Skipped {title}: could not convert to itinerary")
                    continue

                web_view = ItineraryWebView()
                web_view.generate(
                    itinerary, OUTPUT_DIR / link, use_ai_summary=False, skip_geocoding=True
                )
                results["regenerated"] += 1
                print(f"[REGEN] Regenerated {link}")

                # Fix dates and days in DB if needed
                needs_date_fix = (
                    not current_dates
                    or current_dates
                    in (
                        "Date unknown",
                        "None",
                        "",
                    )
                    or " - " in current_dates
                )
                update_data: dict = {}

                if needs_date_fix:
                    start_date = get_trip_start_date(itinerary_data)
                    if start_date:
                        formatted_date = format_trip_date(start_date)
                        if formatted_date != "Date unknown":
                            update_data["dates"] = formatted_date

                if not current_days or current_days == 0:
                    days_count = (
                        itinerary.duration_days
                        or len(set(item.day_number for item in itinerary.items if item.day_number))
                        or len(itinerary_data.get("days", []))
                    )
                    if days_count > 0:
                        update_data["days"] = days_count

                if update_data and user_id is not None:
                    db.update_trip(user_id, link, update_data)
                    results["db_updated"] += 1
                    print(f"[REGEN] Updated DB for {title}: {update_data}")

            except Exception as e:
                results["errors"].append(f"{title}: {str(e)}")
                print(f"[REGEN] Error regenerating {title}: {e}")

    except Exception as e:
        results["errors"].append(f"Fatal error: {str(e)}")
        print(f"[REGEN] Fatal error: {e}")
        traceback.print_exc()

    return results


def admin_retry_geocoding(link: str) -> dict:
    """Re-geocode a trip by link (any user). Finds trip owner automatically."""
    trip_owner = db.get_trip_owner(link)
    if trip_owner is None:
        return {"success": False, "error": "Trip not found"}

    trip = db.get_trip_by_link(trip_owner, link)
    if not trip:
        return {"success": False, "error": "Trip not found"}

    itinerary_data = trip.get("itinerary_data")
    if not itinerary_data:
        return {"success": False, "error": "No itinerary data"}

    if isinstance(itinerary_data, str):
        itinerary_data = json.loads(itinerary_data)

    # Clear existing map data to force full re-geocode
    if "map_data" in itinerary_data:
        del itinerary_data["map_data"]
        db.update_trip_itinerary_data(trip_owner, link, itinerary_data)

    from agents.create.handler import _convert_to_itinerary
    from agents.itinerary.mapper import ItineraryMapper

    itinerary = _convert_to_itinerary(
        {"itinerary_data": itinerary_data, "title": trip.get("title", "Trip")}
    )
    if not itinerary:
        return {"success": False, "error": "Could not parse itinerary data"}

    db.update_trip_map_status(trip_owner, link, "processing", None)
    try:
        mapper = ItineraryMapper()
        map_data = mapper.create_map_data(itinerary)
        itinerary_data["map_data"] = map_data
        db.update_trip_itinerary_data(trip_owner, link, itinerary_data)
        db.update_trip_map_status(trip_owner, link, "ready", None)
        markers_count = len(map_data.get("markers", []))
        return {"success": True, "message": f"Re-geocoded with {markers_count} markers"}
    except Exception as e:
        traceback.print_exc()
        db.update_trip_map_status(trip_owner, link, "error", str(e))
        return {"success": False, "error": str(e)}


def regen_all_stuck_trips() -> dict:
    """Find and re-geocode every trip stuck with map_status='ready' but
    no map_data. One-shot bulk fix invoked by /api/admin/regen-stuck-trips.

    Returns: {"success": True, "regenerated": N, "links": [...], "errors": [...]}
    """
    regenerated: list[str] = []
    errors: list[dict] = []

    for user in db.get_all_users():
        for trip in db.get_user_trips(user["id"]):
            itinerary_data = trip.get("itinerary_data") or {}
            if isinstance(itinerary_data, str):
                try:
                    itinerary_data = json.loads(itinerary_data)
                except (json.JSONDecodeError, ValueError):
                    continue
            map_data = itinerary_data.get("map_data")
            status = trip.get("map_status")
            # Stuck = ready but no markers (or no map_data at all)
            is_stuck = status == "ready" and (
                not map_data or not map_data.get("markers")
            )
            if not is_stuck:
                continue

            result = admin_retry_geocoding(trip["link"])
            if result.get("success"):
                regenerated.append(trip["link"])
            else:
                errors.append({"link": trip["link"], "error": result.get("error")})

    return {
        "success": True,
        "regenerated": len(regenerated),
        "links": regenerated,
        "errors": errors,
    }


def seed_demo_trips(force: bool = False) -> dict:
    """Create (or re-seed) the demo trips owned by the system demo user.

    The demo user is created automatically if it doesn't exist.  The Paris &
    Provence demo trip is parsed from ``tests/fixtures/paris_trip.txt`` using
    Claude and then published + made public so anyone can view it at
    ``/paris_provence_adventure.html``.

    Args:
        force: Re-seed even if the trip already exists.

    Returns:
        Dict with keys ``seeded``, ``skipped``, ``errors``.
    """
    from agents.create.itinerary_utils import itinerary_to_data
    from agents.itinerary.parser import ItineraryParser
    from agents.itinerary.web_view import ItineraryWebView

    results: dict = {"seeded": [], "skipped": [], "errors": []}

    demo_user_id = db.ensure_demo_user()

    # --- Paris & Provence demo trip ---
    paris_fixture = _FIXTURES_DIR / "paris_trip.txt"
    if not paris_fixture.exists():
        results["errors"].append(f"Fixture not found: {paris_fixture}")
        return results

    existing = db.get_trip_by_link(demo_user_id, _PARIS_DEMO_LINK)
    if existing and not force:
        print("[SEED] Paris demo trip already exists, skipping (pass force=True to re-seed)")
        results["skipped"].append(_PARIS_DEMO_LINK)
        return results
    if existing and force:
        db.delete_trip(demo_user_id, _PARIS_DEMO_LINK)
        print("[SEED] Deleted existing Paris demo trip for re-seed")

    try:
        text = paris_fixture.read_text(encoding="utf-8")
        parser = ItineraryParser()
        itinerary = parser.parse_text(text, source_url="demo_fixture")

        if not itinerary or not itinerary.items:
            results["errors"].append("Paris fixture parsed to empty itinerary")
            return results

        itinerary_data = itinerary_to_data(itinerary)
        itinerary_data["title"] = "Paris & Provence Adventure"

        # locations and activities are INTEGER counts in the DB schema
        location_count = len(
            {
                item.get("location")
                for day in itinerary_data.get("days", [])
                for item in day.get("items", [])
                if item.get("location")
            }
        )
        activity_count = sum(len(day.get("items", [])) for day in itinerary_data.get("days", []))

        trip_data = {
            "title": "Paris & Provence Adventure",
            "link": _PARIS_DEMO_LINK,
            "dates": itinerary.start_date.strftime("%b %d, %Y") if itinerary.start_date else "",
            "days": itinerary.duration_days or len(itinerary_data.get("days", [])),
            "locations": location_count,
            "activities": activity_count,
            "map_status": "pending",
        }

        db.add_trip(demo_user_id, trip_data, itinerary_data)
        print(f"[SEED] Saved Paris demo trip for demo user {demo_user_id}")

        # Generate HTML
        trip_row = db.get_trip_by_link(demo_user_id, _PARIS_DEMO_LINK)
        if trip_row:
            web_view = ItineraryWebView()
            web_view.generate(
                itinerary,
                OUTPUT_DIR / _PARIS_DEMO_LINK,
                use_ai_summary=False,
                skip_geocoding=True,
            )
            db.publish_draft(demo_user_id, _PARIS_DEMO_LINK)
            db.set_trip_public(demo_user_id, _PARIS_DEMO_LINK, True)
            print(f"[SEED] Published and made public: {_PARIS_DEMO_LINK}")

        results["seeded"].append(_PARIS_DEMO_LINK)

    except Exception as e:
        results["errors"].append(f"Paris trip: {str(e)}")
        traceback.print_exc()

    return results
