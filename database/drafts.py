"""Draft trip operations: create, update itinerary, publish."""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

from database.connection import USE_POSTGRES, get_db
from database.trips import get_trip_by_link

# --- SQL constants ---

_SQL_PG_COUNT_TRIPS_BY_USER_AND_LINK = "SELECT COUNT(*) FROM trips WHERE user_id = %s AND link = %s"
_SQL_SQLITE_COUNT_TRIPS_BY_USER_AND_LINK = (
    "SELECT COUNT(*) FROM trips WHERE user_id = ? AND link = ?"
)

_SQL_PG_CREATE_DRAFT_TRIP = """
    INSERT INTO trips (user_id, title, link, dates, days, locations, activities, map_status, itinerary_data, is_draft)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE)
    RETURNING id
"""
_SQL_SQLITE_CREATE_DRAFT_TRIP = """
    INSERT INTO trips (user_id, title, link, dates, days, locations, activities, map_status, itinerary_data, is_draft)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
"""

_SQL_PG_GET_DRAFT_TRIPS = """
    SELECT id, title, link, dates, days, locations, activities, map_status, map_error, is_public
    FROM trips WHERE user_id = %s AND is_draft = TRUE ORDER BY created_at DESC
"""
_SQL_SQLITE_GET_DRAFT_TRIPS = """
    SELECT id, title, link, dates, days, locations, activities, map_status, map_error, is_public
    FROM trips WHERE user_id = ? AND is_draft = 1 ORDER BY created_at DESC
"""

_SQL_PG_UPDATE_TRIP_ITINERARY_DATA = """
    UPDATE trips SET itinerary_data = %s, locations = %s, activities = %s
    WHERE user_id = %s AND link = %s
"""
_SQL_SQLITE_UPDATE_TRIP_ITINERARY_DATA = """
    UPDATE trips SET itinerary_data = ?, locations = ?, activities = ?
    WHERE user_id = ? AND link = ?
"""

_SQL_PG_PUBLISH_DRAFT = """
    UPDATE trips SET is_draft = FALSE
    WHERE user_id = %s AND link = %s
"""
_SQL_SQLITE_PUBLISH_DRAFT = """
    UPDATE trips SET is_draft = 0
    WHERE user_id = ? AND link = ?
"""


def create_draft_trip(
    user_id: int,
    title: str,
    start_date: str | None = None,
    end_date: str | None = None,
    num_days: int | None = None,
) -> dict[str, Any] | None:
    """Create a new draft trip. Returns the trip data with link or None if failed."""
    # Generate link from title
    slug = title.lower()
    slug = re.sub(r"[^a-z0-9]+", "_", slug)
    slug = re.sub(r"_+", "_", slug).strip("_")
    base_link = f"{slug}.html"

    # Find a unique link for this user
    link = base_link
    with get_db() as conn:
        cursor = conn.cursor()
        counter = 1
        while True:
            if USE_POSTGRES:
                cursor.execute(_SQL_PG_COUNT_TRIPS_BY_USER_AND_LINK, (user_id, link))
            else:
                cursor.execute(_SQL_SQLITE_COUNT_TRIPS_BY_USER_AND_LINK, (user_id, link))
            count = cursor.fetchone()[0]
            if count == 0:
                break
            counter += 1
            link = f"{slug}_{counter}.html"

    # Format dates string
    dates = None
    if start_date and end_date:
        dates = f"{start_date} - {end_date}"
    elif start_date:
        dates = start_date

    # Calculate days if not provided but dates are
    if not num_days and start_date and end_date:
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d")
            end = datetime.strptime(end_date, "%Y-%m-%d")
            num_days = (end - start).days + 1
        except ValueError:
            pass

    itinerary_data = {
        "title": title,
        "items": [],
        "start_date": start_date,
        "end_date": end_date,
        "travelers": [],
    }

    with get_db() as conn:
        cursor = conn.cursor()
        try:
            itinerary_json = json.dumps(itinerary_data)

            if USE_POSTGRES:
                cursor.execute(
                    _SQL_PG_CREATE_DRAFT_TRIP,
                    (user_id, title, link, dates, num_days, 0, 0, "pending", itinerary_json),
                )
                trip_id = cursor.fetchone()[0]
            else:
                cursor.execute(
                    _SQL_SQLITE_CREATE_DRAFT_TRIP,
                    (user_id, title, link, dates, num_days, 0, 0, "pending", itinerary_json),
                )
                trip_id = cursor.lastrowid

            return {
                "id": trip_id,
                "link": link,
                "title": title,
                "dates": dates,
                "days": num_days,
                "start_date": start_date,
                "end_date": end_date,
                "is_draft": True,
                "itinerary_data": itinerary_data,
            }
        except Exception as e:
            print(f"[DB] Error creating draft trip: {e}")
            return None


def get_draft_trips(user_id: int) -> list[dict[str, Any]]:
    """Get all draft trips for a user."""
    with get_db() as conn:
        cursor = conn.cursor()
        if USE_POSTGRES:
            cursor.execute(_SQL_PG_GET_DRAFT_TRIPS, (user_id,))
            columns = [
                "id",
                "title",
                "link",
                "dates",
                "days",
                "locations",
                "activities",
                "map_status",
                "map_error",
                "is_public",
            ]
            return [dict(zip(columns, row, strict=False)) for row in cursor.fetchall()]
        else:
            cursor.execute(_SQL_SQLITE_GET_DRAFT_TRIPS, (user_id,))
            return [dict(row) for row in cursor.fetchall()]


def update_trip_itinerary_data(user_id: int, link: str, itinerary_data: dict) -> bool:
    """Update a trip's itinerary_data (for auto-save)."""
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            itinerary_json = json.dumps(itinerary_data)

            # Also update counts from itinerary_data
            items = itinerary_data.get("items", [])
            locations = len(
                set(
                    item.get("location", {}).get("name")
                    for item in items
                    if item.get("location") and item.get("location", {}).get("name")
                )
            )
            activities = len(items)

            if USE_POSTGRES:
                cursor.execute(
                    _SQL_PG_UPDATE_TRIP_ITINERARY_DATA,
                    (itinerary_json, locations, activities, user_id, link),
                )
            else:
                cursor.execute(
                    _SQL_SQLITE_UPDATE_TRIP_ITINERARY_DATA,
                    (itinerary_json, locations, activities, user_id, link),
                )
            return cursor.rowcount > 0
        except Exception as e:
            print(f"[DB] Error updating trip itinerary: {e}")
            return False


def publish_draft(user_id: int, link: str) -> bool:
    """Publish a draft trip (set is_draft=False)."""
    with get_db() as conn:
        cursor = conn.cursor()
        if USE_POSTGRES:
            cursor.execute(_SQL_PG_PUBLISH_DRAFT, (user_id, link))
        else:
            cursor.execute(_SQL_SQLITE_PUBLISH_DRAFT, (user_id, link))
        return cursor.rowcount > 0


def add_item_to_trip(user_id: int, link: str, item: dict) -> bool:
    """Add an item to a trip's ideas list (unscheduled items)."""
    trip = get_trip_by_link(user_id, link)
    if not trip:
        return False

    itinerary_data = trip.get("itinerary_data") or {
        "title": trip["title"],
        "days": [],
        "ideas": [],
        "travelers": [],
    }
    if "ideas" not in itinerary_data:
        itinerary_data["ideas"] = []

    itinerary_data["ideas"].append(item)
    return update_trip_itinerary_data(user_id, link, itinerary_data)
