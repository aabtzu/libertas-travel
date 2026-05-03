"""Trip CRUD operations."""

from __future__ import annotations

import json
from typing import Any

from database.connection import USE_POSTGRES, get_db

# --- SQL constants ---

# Column lists are referenced both inside SELECT statements AND in the Python
# zip() that converts row tuples to dicts. Defining them once here is the
# only way to keep the two from drifting silently when a column is added.
_USER_TRIPS_COLUMNS = [
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
    "is_draft",
    "itinerary_data",
    "trip_type",
    "is_archived",
]
_TRIP_BY_LINK_COLUMNS = [
    "id",
    "title",
    "link",
    "dates",
    "days",
    "locations",
    "activities",
    "map_status",
    "map_error",
    "itinerary_data",
    "is_draft",
    "trip_type",
    "is_public",
    "is_archived",
]

_SQL_PG_GET_USER_TRIPS = (
    f"SELECT {', '.join(_USER_TRIPS_COLUMNS)} "
    f"FROM trips WHERE user_id = %s ORDER BY created_at DESC"
)
_SQL_SQLITE_GET_USER_TRIPS = (
    f"SELECT {', '.join(_USER_TRIPS_COLUMNS)} FROM trips WHERE user_id = ? ORDER BY created_at DESC"
)

_SQL_PG_ADD_TRIP = """
    INSERT INTO trips (user_id, title, link, dates, days, locations, activities, map_status, itinerary_data, trip_type)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (user_id, link) DO UPDATE SET
        title = EXCLUDED.title,
        dates = EXCLUDED.dates,
        days = EXCLUDED.days,
        locations = EXCLUDED.locations,
        activities = EXCLUDED.activities,
        map_status = EXCLUDED.map_status,
        itinerary_data = EXCLUDED.itinerary_data,
        trip_type = EXCLUDED.trip_type
    RETURNING id
"""
_SQL_SQLITE_ADD_TRIP = """
    INSERT OR REPLACE INTO trips (user_id, title, link, dates, days, locations, activities, map_status, itinerary_data, trip_type)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

_SQL_PG_GET_TRIP_BY_LINK = (
    f"SELECT {', '.join(_TRIP_BY_LINK_COLUMNS)} FROM trips WHERE user_id = %s AND link = %s"
)
_SQL_SQLITE_GET_TRIP_BY_LINK = (
    f"SELECT {', '.join(_TRIP_BY_LINK_COLUMNS)} FROM trips WHERE user_id = ? AND link = ?"
)

_SQL_PG_UPDATE_MAP_STATUS = """
    UPDATE trips SET map_status = %s, map_error = %s
    WHERE user_id = %s AND link = %s
"""
_SQL_SQLITE_UPDATE_MAP_STATUS = """
    UPDATE trips SET map_status = ?, map_error = ?
    WHERE user_id = ? AND link = ?
"""

_SQL_GET_PENDING_GEOCODING_TRIPS = """
    SELECT link, itinerary_data, title
    FROM trips
    WHERE map_status IN ('pending', 'processing')
    AND itinerary_data IS NOT NULL
"""

_SQL_PG_DELETE_TRIP = "DELETE FROM trips WHERE user_id = %s AND link = %s"
_SQL_SQLITE_DELETE_TRIP = "DELETE FROM trips WHERE user_id = ? AND link = ?"

_SQL_PG_GET_TRIP_OWNER = "SELECT user_id FROM trips WHERE link = %s"
_SQL_SQLITE_GET_TRIP_OWNER = "SELECT user_id FROM trips WHERE link = ?"

_SQL_PG_SET_TRIP_ARCHIVED = """
    UPDATE trips SET is_archived = %s
    WHERE user_id = %s AND link = %s
"""
_SQL_SQLITE_SET_TRIP_ARCHIVED = """
    UPDATE trips SET is_archived = ?
    WHERE user_id = ? AND link = ?
"""


def get_user_trips(user_id: int) -> list[dict[str, Any]]:
    """Get all trips for a user."""
    with get_db() as conn:
        cursor = conn.cursor()
        if USE_POSTGRES:
            cursor.execute(_SQL_PG_GET_USER_TRIPS, (user_id,))
            return [dict(zip(_USER_TRIPS_COLUMNS, row, strict=False)) for row in cursor.fetchall()]
        else:
            cursor.execute(_SQL_SQLITE_GET_USER_TRIPS, (user_id,))
            return [dict(row) for row in cursor.fetchall()]


def add_trip(
    user_id: int, trip_data: dict[str, Any], itinerary_data: dict | None = None
) -> int | None:
    """Add a trip for a user. Returns trip ID or None if failed."""
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            itinerary_json = json.dumps(itinerary_data) if itinerary_data else None

            trip_type = trip_data.get("trip_type", "itinerary")

            if USE_POSTGRES:
                cursor.execute(
                    _SQL_PG_ADD_TRIP,
                    (
                        user_id,
                        trip_data.get("title"),
                        trip_data.get("link"),
                        trip_data.get("dates"),
                        trip_data.get("days"),
                        trip_data.get("locations"),
                        trip_data.get("activities"),
                        trip_data.get("map_status", "pending"),
                        itinerary_json,
                        trip_type,
                    ),
                )
                return cursor.fetchone()[0]
            else:
                cursor.execute(
                    _SQL_SQLITE_ADD_TRIP,
                    (
                        user_id,
                        trip_data.get("title"),
                        trip_data.get("link"),
                        trip_data.get("dates"),
                        trip_data.get("days"),
                        trip_data.get("locations"),
                        trip_data.get("activities"),
                        trip_data.get("map_status", "pending"),
                        itinerary_json,
                        trip_type,
                    ),
                )
                return cursor.lastrowid
        except Exception as e:
            print(f"[DB] Error adding trip: {e}")
            return None


def get_trip_by_link(user_id: int, link: str) -> dict[str, Any] | None:
    """Get a specific trip by link for a user."""
    with get_db() as conn:
        cursor = conn.cursor()
        if USE_POSTGRES:
            cursor.execute(_SQL_PG_GET_TRIP_BY_LINK, (user_id, link))
            row = cursor.fetchone()
            if row:
                trip = dict(zip(_TRIP_BY_LINK_COLUMNS, row, strict=False))
                if trip["itinerary_data"]:
                    # Already parsed by psycopg2 for JSONB
                    trip["start_date"] = trip["itinerary_data"].get("start_date")
                    trip["end_date"] = trip["itinerary_data"].get("end_date")
                else:
                    trip["start_date"] = None
                    trip["end_date"] = None
                return trip
        else:
            cursor.execute(_SQL_SQLITE_GET_TRIP_BY_LINK, (user_id, link))
            row = cursor.fetchone()
            if row:
                trip = dict(row)
                if trip["itinerary_data"]:
                    trip["itinerary_data"] = json.loads(trip["itinerary_data"])
                    trip["start_date"] = trip["itinerary_data"].get("start_date")
                    trip["end_date"] = trip["itinerary_data"].get("end_date")
                else:
                    trip["start_date"] = None
                    trip["end_date"] = None
                return trip
        return None


def update_trip_map_status(user_id: int, link: str, status: str, error: str | None = None):
    """Update the map status for a trip."""
    with get_db() as conn:
        cursor = conn.cursor()
        if USE_POSTGRES:
            cursor.execute(_SQL_PG_UPDATE_MAP_STATUS, (status, error, user_id, link))
        else:
            cursor.execute(_SQL_SQLITE_UPDATE_MAP_STATUS, (status, error, user_id, link))


def get_pending_geocoding_trips() -> list[dict[str, Any]]:
    """Get all trips with pending or processing map status that need geocoding.

    Used on startup to recover stale geocoding tasks after server restart.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        if USE_POSTGRES:
            cursor.execute(_SQL_GET_PENDING_GEOCODING_TRIPS)
            rows = cursor.fetchall()
            return [{"link": row[0], "itinerary_data": row[1], "title": row[2]} for row in rows]
        else:
            cursor.execute(_SQL_GET_PENDING_GEOCODING_TRIPS)
            rows = cursor.fetchall()
            result = []
            for row in rows:
                itinerary_data = (
                    json.loads(row["itinerary_data"]) if row["itinerary_data"] else None
                )
                if itinerary_data:
                    result.append(
                        {
                            "link": row["link"],
                            "itinerary_data": itinerary_data,
                            "title": row["title"],
                        }
                    )
            return result


def update_trip(user_id: int, link: str, updates: dict[str, Any]) -> bool:
    """Update a trip's fields (title, dates, days, locations, activities)."""
    if not updates:
        return False

    allowed_fields = ["title", "dates", "days", "locations", "activities"]
    set_parts = []
    values = []

    for field in allowed_fields:
        if field in updates:
            set_parts.append(f"{field} = %s" if USE_POSTGRES else f"{field} = ?")
            values.append(updates[field])

    if not set_parts:
        return False

    with get_db() as conn:
        cursor = conn.cursor()
        if USE_POSTGRES:
            query = f"UPDATE trips SET {', '.join(set_parts)} WHERE user_id = %s AND link = %s"
            values.extend([user_id, link])
        else:
            query = f"UPDATE trips SET {', '.join(set_parts)} WHERE user_id = ? AND link = ?"
            values.extend([user_id, link])

        cursor.execute(query, values)
        return cursor.rowcount > 0


def delete_trip(user_id: int, link: str) -> bool:
    """Delete a trip."""
    with get_db() as conn:
        cursor = conn.cursor()
        if USE_POSTGRES:
            cursor.execute(_SQL_PG_DELETE_TRIP, (user_id, link))
        else:
            cursor.execute(_SQL_SQLITE_DELETE_TRIP, (user_id, link))
        return cursor.rowcount > 0


def get_trip_owner(link: str) -> int | None:
    """Get the user_id of a trip owner by link (for any user)."""
    with get_db() as conn:
        cursor = conn.cursor()
        if USE_POSTGRES:
            cursor.execute(_SQL_PG_GET_TRIP_OWNER, (link,))
        else:
            cursor.execute(_SQL_SQLITE_GET_TRIP_OWNER, (link,))
        row = cursor.fetchone()
        return row[0] if row else None


def set_trip_archived(user_id: int, link: str, is_archived: bool) -> bool:
    """Set a trip's archived flag. Archive is independent of is_public
    an archived trip can still be public/recommendable."""
    with get_db() as conn:
        cursor = conn.cursor()
        if USE_POSTGRES:
            cursor.execute(_SQL_PG_SET_TRIP_ARCHIVED, (is_archived, user_id, link))
        else:
            cursor.execute(_SQL_SQLITE_SET_TRIP_ARCHIVED, (is_archived, user_id, link))
        return cursor.rowcount > 0
