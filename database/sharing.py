"""Trip sharing and public trip functions."""

from __future__ import annotations

import re
from typing import Any

from database.connection import USE_POSTGRES, get_db
from database.trips import add_trip, get_trip_by_link
from database.users import get_all_users

# --- SQL constants ---

_SQL_PG_SET_TRIP_PUBLIC = """
    UPDATE trips SET is_public = %s
    WHERE user_id = %s AND link = %s
"""
_SQL_SQLITE_SET_TRIP_PUBLIC = """
    UPDATE trips SET is_public = ?
    WHERE user_id = ? AND link = ?
"""

_SQL_PG_GET_PUBLIC_TRIPS = """
    SELECT t.id, t.title, t.link, t.dates, t.days, t.locations, t.activities,
           t.map_status, t.map_error, u.username as owner_username, t.itinerary_data
    FROM trips t
    JOIN users u ON t.user_id = u.id
    WHERE t.is_public = TRUE
    ORDER BY t.created_at DESC
"""
_SQL_PG_GET_PUBLIC_TRIPS_EXCLUDE_USER = """
    SELECT t.id, t.title, t.link, t.dates, t.days, t.locations, t.activities,
           t.map_status, t.map_error, u.username as owner_username, t.itinerary_data
    FROM trips t
    JOIN users u ON t.user_id = u.id
    WHERE t.is_public = TRUE AND t.user_id != %s
    ORDER BY t.created_at DESC
"""
_SQL_SQLITE_GET_PUBLIC_TRIPS = """
    SELECT t.id, t.title, t.link, t.dates, t.days, t.locations, t.activities,
           t.map_status, t.map_error, u.username as owner_username, t.itinerary_data
    FROM trips t
    JOIN users u ON t.user_id = u.id
    WHERE t.is_public = 1
    ORDER BY t.created_at DESC
"""
_SQL_SQLITE_GET_PUBLIC_TRIPS_EXCLUDE_USER = """
    SELECT t.id, t.title, t.link, t.dates, t.days, t.locations, t.activities,
           t.map_status, t.map_error, u.username as owner_username, t.itinerary_data
    FROM trips t
    JOIN users u ON t.user_id = u.id
    WHERE t.is_public = 1 AND t.user_id != ?
    ORDER BY t.created_at DESC
"""

_SQL_PG_GET_TRIP_BY_LINK_ANY_USER = """
    SELECT id, user_id, title, link, dates, days, locations, activities,
           map_status, map_error, itinerary_data
    FROM trips WHERE link = %s
"""
_SQL_SQLITE_GET_TRIP_BY_LINK_ANY_USER = """
    SELECT id, user_id, title, link, dates, days, locations, activities,
           map_status, map_error, itinerary_data
    FROM trips WHERE link = ?
"""

_SQL_PG_COUNT_TRIPS_BY_USER_AND_LINK = "SELECT COUNT(*) FROM trips WHERE user_id = %s AND link = %s"
_SQL_SQLITE_COUNT_TRIPS_BY_USER_AND_LINK = (
    "SELECT COUNT(*) FROM trips WHERE user_id = ? AND link = ?"
)

_SQL_PG_IS_TRIP_PUBLIC = "SELECT is_public FROM trips WHERE link = %s"
_SQL_SQLITE_IS_TRIP_PUBLIC = "SELECT is_public FROM trips WHERE link = ?"


def copy_trip_to_user(source_user_id: int, link: str, target_user_id: int) -> int | None:
    """Copy a trip from one user to another. Returns new trip ID or None if failed."""
    source_trip = get_trip_by_link(source_user_id, link)
    if not source_trip:
        return None

    trip_data = {
        "title": source_trip["title"],
        "link": source_trip["link"],
        "dates": source_trip.get("dates"),
        "days": source_trip.get("days"),
        "locations": source_trip.get("locations"),
        "activities": source_trip.get("activities"),
        "map_status": source_trip.get("map_status", "ready"),
    }

    return add_trip(target_user_id, trip_data, source_trip.get("itinerary_data"))


def share_trip_with_all(source_user_id: int, link: str) -> int:
    """Share a trip with all users. Returns count of users shared with."""
    users = get_all_users()
    shared_count = 0
    for user in users:
        if user["id"] != source_user_id:
            if copy_trip_to_user(source_user_id, link, user["id"]):
                shared_count += 1
    return shared_count


def is_trip_public(link: str) -> bool:
    """True if the trip with this link is marked public (any owner)."""
    with get_db() as conn:
        cursor = conn.cursor()
        if USE_POSTGRES:
            cursor.execute(_SQL_PG_IS_TRIP_PUBLIC, (link,))
        else:
            cursor.execute(_SQL_SQLITE_IS_TRIP_PUBLIC, (link,))
        row = cursor.fetchone()
        return bool(row and row[0])


def set_trip_public(user_id: int, link: str, is_public: bool) -> bool:
    """Set a trip's public visibility."""
    with get_db() as conn:
        cursor = conn.cursor()
        if USE_POSTGRES:
            cursor.execute(_SQL_PG_SET_TRIP_PUBLIC, (is_public, user_id, link))
        else:
            cursor.execute(_SQL_SQLITE_SET_TRIP_PUBLIC, (is_public, user_id, link))
        return cursor.rowcount > 0


def get_public_trips(exclude_user_id: int | None = None) -> list[dict[str, Any]]:
    """Get all public trips, optionally excluding a specific user's trips."""
    with get_db() as conn:
        cursor = conn.cursor()
        if USE_POSTGRES:
            if exclude_user_id:
                cursor.execute(_SQL_PG_GET_PUBLIC_TRIPS_EXCLUDE_USER, (exclude_user_id,))
            else:
                cursor.execute(_SQL_PG_GET_PUBLIC_TRIPS)
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
                "owner_username",
                "itinerary_data",
            ]
            return [dict(zip(columns, row, strict=False)) for row in cursor.fetchall()]
        else:
            if exclude_user_id:
                cursor.execute(_SQL_SQLITE_GET_PUBLIC_TRIPS_EXCLUDE_USER, (exclude_user_id,))
            else:
                cursor.execute(_SQL_SQLITE_GET_PUBLIC_TRIPS)
            return [dict(row) for row in cursor.fetchall()]


def copy_trip_by_link(link: str, target_user_id: int) -> dict[str, Any] | None:
    """Copy any trip by link to a target user with a unique link.

    Returns dict with new_link and trip_id, or None if failed.
    """
    import json

    # Get the source trip (regardless of owner)
    with get_db() as conn:
        cursor = conn.cursor()
        if USE_POSTGRES:
            cursor.execute(_SQL_PG_GET_TRIP_BY_LINK_ANY_USER, (link,))
            row = cursor.fetchone()
            if not row:
                return None
            columns = [
                "id",
                "user_id",
                "title",
                "link",
                "dates",
                "days",
                "locations",
                "activities",
                "map_status",
                "map_error",
                "itinerary_data",
            ]
            source_trip = dict(zip(columns, row, strict=False))
        else:
            cursor.execute(_SQL_SQLITE_GET_TRIP_BY_LINK_ANY_USER, (link,))
            row = cursor.fetchone()
            if not row:
                return None
            source_trip = dict(row)

    # If target user owns this trip, they can edit directly (no copy needed)
    if source_trip.get("user_id") == target_user_id:
        return {"new_link": link, "trip_id": source_trip["id"], "was_copied": False}

    # Generate a unique link for the target user
    title = source_trip.get("title", "trip")
    slug = title.lower()
    slug = re.sub(r"[^a-z0-9]+", "_", slug)
    slug = re.sub(r"_+", "_", slug).strip("_")
    base_link = f"{slug}.html"

    new_link = base_link
    with get_db() as conn:
        cursor = conn.cursor()
        counter = 1
        while True:
            if USE_POSTGRES:
                cursor.execute(_SQL_PG_COUNT_TRIPS_BY_USER_AND_LINK, (target_user_id, new_link))
            else:
                cursor.execute(_SQL_SQLITE_COUNT_TRIPS_BY_USER_AND_LINK, (target_user_id, new_link))
            count = cursor.fetchone()[0]
            if count == 0:
                break
            counter += 1
            new_link = f"{slug}_{counter}.html"

    # Parse itinerary_data if it's a string (SQLite returns strings)
    itinerary_data = source_trip.get("itinerary_data")
    if isinstance(itinerary_data, str):
        try:
            itinerary_data = json.loads(itinerary_data)
        except (json.JSONDecodeError, ValueError):
            itinerary_data = None

    trip_data = {
        "title": source_trip.get("title"),
        "link": new_link,
        "dates": source_trip.get("dates"),
        "days": source_trip.get("days"),
        "locations": source_trip.get("locations"),
        "activities": source_trip.get("activities"),
        "map_status": source_trip.get("map_status", "ready"),
    }

    trip_id = add_trip(target_user_id, trip_data, itinerary_data)
    if trip_id:
        return {"new_link": new_link, "trip_id": trip_id, "was_copied": True}
    return None
