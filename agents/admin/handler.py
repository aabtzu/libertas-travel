"""Admin handler: trip regeneration utilities."""

from __future__ import annotations

import json
import os
import traceback
from pathlib import Path

import database as db

OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", Path(__file__).parent.parent.parent / "output"))


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

                itinerary = _convert_to_itinerary({"itinerary_data": itinerary_data, "title": title})

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
                needs_date_fix = not current_dates or current_dates in (
                    "Date unknown",
                    "None",
                    "",
                ) or " - " in current_dates
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
