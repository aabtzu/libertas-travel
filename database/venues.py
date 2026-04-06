"""Venue CRUD, search, and import operations."""

from __future__ import annotations

from typing import Any

from database.connection import USE_POSTGRES, get_db

# --- SQL constants ---

_SQL_PG_ADD_VENUE = """
    INSERT INTO venues (name, venue_type, city, state, country, address,
                        latitude, longitude, website, google_maps_link,
                        notes, description, cuisine_type, michelin_stars,
                        chef, collection, source, created_by)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    RETURNING id
"""
_SQL_SQLITE_ADD_VENUE = """
    INSERT INTO venues (name, venue_type, city, state, country, address,
                        latitude, longitude, website, google_maps_link,
                        notes, description, cuisine_type, michelin_stars,
                        chef, collection, source, created_by)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

_SQL_PG_UPDATE_VENUE_COORDINATES = "UPDATE venues SET latitude = %s, longitude = %s WHERE id = %s"
_SQL_SQLITE_UPDATE_VENUE_COORDINATES = "UPDATE venues SET latitude = ?, longitude = ? WHERE id = ?"

_SQL_PG_SEARCH_VENUES = """
    SELECT id, name, venue_type, city, state, country, address,
           latitude, longitude, website, google_maps_link, notes,
           description, cuisine_type, michelin_stars, chef, collection,
           source, created_by, created_at
    FROM venues
    WHERE LOWER(name) LIKE LOWER(%s)
       OR LOWER(city) LIKE LOWER(%s)
       OR LOWER(description) LIKE LOWER(%s)
       OR LOWER(notes) LIKE LOWER(%s)
    ORDER BY name
    LIMIT %s
"""
_SQL_SQLITE_SEARCH_VENUES = """
    SELECT id, name, venue_type, city, state, country, address,
           latitude, longitude, website, google_maps_link, notes,
           description, cuisine_type, michelin_stars, chef, collection,
           source, created_by, created_at
    FROM venues
    WHERE LOWER(name) LIKE LOWER(?)
       OR LOWER(city) LIKE LOWER(?)
       OR LOWER(description) LIKE LOWER(?)
       OR LOWER(notes) LIKE LOWER(?)
    ORDER BY name
    LIMIT ?
"""

_SQL_PG_GET_VENUE_BY_ID = """
    SELECT id, name, venue_type, city, state, country, address,
           latitude, longitude, website, google_maps_link, notes,
           description, cuisine_type, michelin_stars, chef, collection,
           source, created_by, created_at
    FROM venues WHERE id = %s
"""
_SQL_SQLITE_GET_VENUE_BY_ID = """
    SELECT id, name, venue_type, city, state, country, address,
           latitude, longitude, website, google_maps_link, notes,
           description, cuisine_type, michelin_stars, chef, collection,
           source, created_by, created_at
    FROM venues WHERE id = ?
"""

_SQL_PG_FIND_VENUE_BY_NAME = """
    SELECT id, name, venue_type, city, state, country, address,
           latitude, longitude, website, google_maps_link, notes,
           description, cuisine_type, michelin_stars, chef, collection,
           source, created_by, created_at
    FROM venues
    WHERE LOWER(name) = LOWER(%s)
    LIMIT 1
"""
_SQL_SQLITE_FIND_VENUE_BY_NAME = """
    SELECT id, name, venue_type, city, state, country, address,
           latitude, longitude, website, google_maps_link, notes,
           description, cuisine_type, michelin_stars, chef, collection,
           source, created_by, created_at
    FROM venues
    WHERE LOWER(name) = LOWER(?)
    LIMIT 1
"""

_SQL_PG_FIND_VENUE_BY_NAME_AND_CITY = """
    SELECT id, name, venue_type, city, state, country, address,
           latitude, longitude, website, google_maps_link, notes,
           description, cuisine_type, michelin_stars, chef, collection,
           source, created_by, created_at
    FROM venues
    WHERE LOWER(name) = LOWER(%s) AND LOWER(city) = LOWER(%s)
    LIMIT 1
"""
_SQL_SQLITE_FIND_VENUE_BY_NAME_AND_CITY = """
    SELECT id, name, venue_type, city, state, country, address,
           latitude, longitude, website, google_maps_link, notes,
           description, cuisine_type, michelin_stars, chef, collection,
           source, created_by, created_at
    FROM venues
    WHERE LOWER(name) = LOWER(?) AND LOWER(city) = LOWER(?)
    LIMIT 1
"""

_SQL_GET_VENUE_COUNT = "SELECT COUNT(*) FROM venues"

_SQL_GET_VENUE_STATS_BY_COUNTRY = """
    SELECT country, COUNT(*) as count
    FROM venues
    WHERE country IS NOT NULL AND country != ''
    GROUP BY country
    ORDER BY count DESC
"""
_SQL_GET_VENUE_STATS_BY_CITY = """
    SELECT city, COUNT(*) as count
    FROM venues
    WHERE city IS NOT NULL AND city != ''
    GROUP BY city
    ORDER BY count DESC
    LIMIT 50
"""
_SQL_GET_VENUE_STATS_BY_TYPE = """
    SELECT venue_type, COUNT(*) as count
    FROM venues
    WHERE venue_type IS NOT NULL AND venue_type != ''
    GROUP BY venue_type
    ORDER BY count DESC
"""
_SQL_GET_VENUE_STATS_BY_STATE = """
    SELECT state, COUNT(*) as count
    FROM venues
    WHERE state IS NOT NULL AND state != ''
    GROUP BY state
    ORDER BY count DESC
"""

_SQL_PG_IMPORT_VENUES = """
    INSERT INTO venues (name, venue_type, city, state, country, address,
                        latitude, longitude, website, google_maps_link,
                        notes, description, cuisine_type, michelin_stars,
                        chef, collection, source)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""
_SQL_SQLITE_IMPORT_VENUES = """
    INSERT INTO venues (name, venue_type, city, state, country, address,
                        latitude, longitude, website, google_maps_link,
                        notes, description, cuisine_type, michelin_stars,
                        chef, collection, source)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

# Column list shared across venue SELECT queries
_VENUE_COLUMNS = [
    "id",
    "name",
    "venue_type",
    "city",
    "state",
    "country",
    "address",
    "latitude",
    "longitude",
    "website",
    "google_maps_link",
    "notes",
    "description",
    "cuisine_type",
    "michelin_stars",
    "chef",
    "collection",
    "source",
    "created_by",
    "created_at",
]


def add_venue(venue_data: dict[str, Any], created_by: int | None = None) -> int | None:
    """Add a venue to the database. Returns venue ID or None if failed."""
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            params = (
                venue_data.get("name"),
                venue_data.get("venue_type"),
                venue_data.get("city"),
                venue_data.get("state"),
                venue_data.get("country"),
                venue_data.get("address"),
                venue_data.get("latitude"),
                venue_data.get("longitude"),
                venue_data.get("website"),
                venue_data.get("google_maps_link"),
                venue_data.get("notes"),
                venue_data.get("description"),
                venue_data.get("cuisine_type"),
                venue_data.get("michelin_stars", 0),
                venue_data.get("chef"),
                venue_data.get("collection"),
                venue_data.get("source", "curated"),
                created_by,
            )
            if USE_POSTGRES:
                cursor.execute(_SQL_PG_ADD_VENUE, params)
                return cursor.fetchone()[0]
            else:
                cursor.execute(_SQL_SQLITE_ADD_VENUE, params)
                return cursor.lastrowid
        except Exception as e:
            print(f"[DB] Error adding venue: {e}")
            return None


def update_venue_coordinates(venue_id: int, latitude: float, longitude: float) -> bool:
    """Update latitude and longitude for a venue."""
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            if USE_POSTGRES:
                cursor.execute(_SQL_PG_UPDATE_VENUE_COORDINATES, (latitude, longitude, venue_id))
            else:
                cursor.execute(
                    _SQL_SQLITE_UPDATE_VENUE_COORDINATES, (latitude, longitude, venue_id)
                )
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            print(f"Error updating venue coordinates: {e}")
            return False


def get_all_venues(filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Get all venues, optionally filtered by city, country, venue_type, etc."""
    with get_db() as conn:
        cursor = conn.cursor()

        where_clauses = []
        params = []

        if filters:
            if filters.get("city"):
                where_clauses.append(
                    "LOWER(city) = LOWER(%s)" if USE_POSTGRES else "LOWER(city) = LOWER(?)"
                )
                params.append(filters["city"])
            if filters.get("country"):
                where_clauses.append(
                    "LOWER(country) = LOWER(%s)" if USE_POSTGRES else "LOWER(country) = LOWER(?)"
                )
                params.append(filters["country"])
            if filters.get("state"):
                where_clauses.append(
                    "LOWER(state) = LOWER(%s)" if USE_POSTGRES else "LOWER(state) = LOWER(?)"
                )
                params.append(filters["state"])
            if filters.get("venue_type"):
                where_clauses.append(
                    "LOWER(venue_type) = LOWER(%s)"
                    if USE_POSTGRES
                    else "LOWER(venue_type) = LOWER(?)"
                )
                params.append(filters["venue_type"])
            if filters.get("source"):
                where_clauses.append("source = %s" if USE_POSTGRES else "source = ?")
                params.append(filters["source"])

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        query = f"""
            SELECT id, name, venue_type, city, state, country, address,
                   latitude, longitude, website, google_maps_link, notes,
                   description, cuisine_type, michelin_stars, chef, collection,
                   source, created_by, created_at
            FROM venues
            WHERE {where_sql}
            ORDER BY name
        """

        cursor.execute(query, params)

        if USE_POSTGRES:
            return [dict(zip(_VENUE_COLUMNS, row, strict=False)) for row in cursor.fetchall()]
        else:
            return [dict(row) for row in cursor.fetchall()]


def search_venues(query: str, limit: int = 50) -> list[dict[str, Any]]:
    """Search venues by name, city, or description."""
    with get_db() as conn:
        cursor = conn.cursor()
        search_pattern = f"%{query}%"

        if USE_POSTGRES:
            cursor.execute(
                _SQL_PG_SEARCH_VENUES,
                (search_pattern, search_pattern, search_pattern, search_pattern, limit),
            )
            return [dict(zip(_VENUE_COLUMNS, row, strict=False)) for row in cursor.fetchall()]
        else:
            cursor.execute(
                _SQL_SQLITE_SEARCH_VENUES,
                (search_pattern, search_pattern, search_pattern, search_pattern, limit),
            )
            return [dict(row) for row in cursor.fetchall()]


def flexible_venue_search(
    cities: list[str] | None = None,
    states: list[str] | None = None,
    countries: list[str] | None = None,
    venue_types: list[str] | None = None,
    cuisine_types: list[str] | None = None,
    keywords: list[str] | None = None,
    michelin_only: bool = False,
    limit: int = 30,
) -> list[dict[str, Any]]:
    """
    Flexible venue search with multiple optional filters.
    All filters are combined with AND logic.
    Within each filter list, items are combined with OR logic.
    """
    with get_db() as conn:
        cursor = conn.cursor()

        conditions = []
        params = []
        placeholder = "%s" if USE_POSTGRES else "?"

        if cities:
            city_conditions = []
            for city in cities:
                city_conditions.append(f"LOWER(city) LIKE LOWER({placeholder})")
                params.append(f"%{city}%")
            conditions.append(f"({' OR '.join(city_conditions)})")

        if states:
            state_conditions = []
            for state in states:
                state_conditions.append(f"LOWER(state) LIKE LOWER({placeholder})")
                params.append(f"%{state}%")
            conditions.append(f"({' OR '.join(state_conditions)})")

        if countries:
            country_conditions = []
            for country in countries:
                country_conditions.append(f"LOWER(country) LIKE LOWER({placeholder})")
                params.append(f"%{country}%")
            conditions.append(f"({' OR '.join(country_conditions)})")

        if venue_types:
            type_conditions = []
            for vt in venue_types:
                type_conditions.append(f"LOWER(venue_type) LIKE LOWER({placeholder})")
                params.append(f"%{vt}%")
            conditions.append(f"({' OR '.join(type_conditions)})")

        if cuisine_types:
            cuisine_conditions = []
            for ct in cuisine_types:
                cuisine_conditions.append(f"LOWER(cuisine_type) LIKE LOWER({placeholder})")
                params.append(f"%{ct}%")
            conditions.append(f"({' OR '.join(cuisine_conditions)})")

        if keywords:
            keyword_conditions = []
            for kw in keywords:
                keyword_conditions.append(
                    f"(LOWER(name) LIKE LOWER({placeholder}) OR LOWER(notes) LIKE LOWER({placeholder}) OR LOWER(description) LIKE LOWER({placeholder}))"
                )
                params.extend([f"%{kw}%", f"%{kw}%", f"%{kw}%"])
            conditions.append(f"({' OR '.join(keyword_conditions)})")

        if michelin_only:
            conditions.append("michelin_stars IS NOT NULL AND michelin_stars > 0")

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        query = f"""
            SELECT id, name, venue_type, city, state, country, address,
                   latitude, longitude, website, google_maps_link, notes,
                   description, cuisine_type, michelin_stars, chef, collection,
                   source, created_by, created_at
            FROM venues
            WHERE {where_clause}
            ORDER BY
                CASE WHEN michelin_stars IS NOT NULL AND michelin_stars > 0 THEN 0 ELSE 1 END,
                name
            LIMIT {placeholder}
        """
        params.append(limit)

        cursor.execute(query, params)

        if USE_POSTGRES:
            return [dict(zip(_VENUE_COLUMNS, row, strict=False)) for row in cursor.fetchall()]
        else:
            return [dict(row) for row in cursor.fetchall()]


def get_venue_by_id(venue_id: int) -> dict[str, Any] | None:
    """Get a specific venue by ID."""
    with get_db() as conn:
        cursor = conn.cursor()
        if USE_POSTGRES:
            cursor.execute(_SQL_PG_GET_VENUE_BY_ID, (venue_id,))
            row = cursor.fetchone()
            if row:
                return dict(zip(_VENUE_COLUMNS, row, strict=False))
        else:
            cursor.execute(_SQL_SQLITE_GET_VENUE_BY_ID, (venue_id,))
            row = cursor.fetchone()
            if row:
                return dict(row)
        return None


def find_venue_by_name_and_city(name: str, city: str | None = None) -> dict[str, Any] | None:
    """Find a venue by exact name match (case-insensitive), optionally in a specific city."""
    with get_db() as conn:
        cursor = conn.cursor()
        if city:
            if USE_POSTGRES:
                cursor.execute(_SQL_PG_FIND_VENUE_BY_NAME_AND_CITY, (name, city))
            else:
                cursor.execute(_SQL_SQLITE_FIND_VENUE_BY_NAME_AND_CITY, (name, city))
        else:
            if USE_POSTGRES:
                cursor.execute(_SQL_PG_FIND_VENUE_BY_NAME, (name,))
            else:
                cursor.execute(_SQL_SQLITE_FIND_VENUE_BY_NAME, (name,))

        row = cursor.fetchone()
        if row:
            if USE_POSTGRES:
                return dict(zip(_VENUE_COLUMNS, row, strict=False))
            else:
                return dict(row)
        return None


def get_venue_count() -> int:
    """Get total count of venues."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(_SQL_GET_VENUE_COUNT)
        return cursor.fetchone()[0]


def get_venue_stats() -> dict[str, Any]:
    """Get statistics about venues (counts by city, country, type, etc.)."""
    with get_db() as conn:
        cursor = conn.cursor()

        cursor.execute(_SQL_GET_VENUE_STATS_BY_COUNTRY)
        countries = {row[0]: row[1] for row in cursor.fetchall()}

        cursor.execute(_SQL_GET_VENUE_STATS_BY_CITY)
        cities = {row[0]: row[1] for row in cursor.fetchall()}

        cursor.execute(_SQL_GET_VENUE_STATS_BY_TYPE)
        venue_types = {row[0]: row[1] for row in cursor.fetchall()}

        cursor.execute(_SQL_GET_VENUE_STATS_BY_STATE)
        states = {row[0]: row[1] for row in cursor.fetchall()}

        cursor.execute(_SQL_GET_VENUE_COUNT)
        total = cursor.fetchone()[0]

        return {
            "total": total,
            "by_country": countries,
            "by_city": cities,
            "by_type": venue_types,
            "by_state": states,
        }


def import_venues_from_csv(csv_path: str, source: str = "curated") -> int:
    """Import venues from a CSV file using batch insert. Returns count of imported venues."""
    import csv

    rows = []
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row.get("name", "").strip()
            if not name:
                continue
            rows.append(
                (
                    name,
                    row.get("venue_type", "").strip() or None,
                    row.get("city", "").strip() or None,
                    row.get("state", "").strip() or None,
                    row.get("country", "").strip() or None,
                    row.get("address", "").strip() or None,
                    float(row["latitude"]) if row.get("latitude") else None,
                    float(row["longitude"]) if row.get("longitude") else None,
                    row.get("website", "").strip() or None,
                    row.get("google_maps_link", "").strip() or None,
                    row.get("notes", "").strip() or None,
                    row.get("description", "").strip() or None,
                    row.get("cuisine_type", "").strip() or None,
                    int(row["michelin_stars"]) if row.get("michelin_stars") else 0,
                    row.get("chef", "").strip() or None,
                    row.get("collection", "").strip() or None,
                    source,
                )
            )

    if not rows:
        return 0

    with get_db() as conn:
        cursor = conn.cursor()
        try:
            if USE_POSTGRES:
                cursor.executemany(_SQL_PG_IMPORT_VENUES, rows)
            else:
                cursor.executemany(_SQL_SQLITE_IMPORT_VENUES, rows)
            conn.commit()
            count = len(rows)
            print(f"[DB] Batch imported {count} venues from {csv_path}")
            return count
        except Exception as e:
            print(f"[DB] Error batch importing venues: {e}")
            return 0
