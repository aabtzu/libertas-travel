"""Trip asset functions: save, list, delete source files attached to trips."""

from __future__ import annotations

from typing import Any

from database.connection import USE_POSTGRES, get_db

# --- DDL (called from connection.init_db) ---

DDL_PG_CREATE_ASSETS = """
    CREATE TABLE IF NOT EXISTS trip_assets (
        id SERIAL PRIMARY KEY,
        trip_id INTEGER NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
        original_name VARCHAR(500) NOT NULL,
        stored_filename VARCHAR(500) NOT NULL,
        mime_type VARCHAR(200),
        file_size INTEGER,
        extracted_text TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
"""

DDL_SQLITE_CREATE_ASSETS = """
    CREATE TABLE IF NOT EXISTS trip_assets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        trip_id INTEGER NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
        original_name TEXT NOT NULL,
        stored_filename TEXT NOT NULL,
        mime_type TEXT,
        file_size INTEGER,
        extracted_text TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
"""

DDL_PG_INDEX_ASSETS_TRIP = (
    "CREATE INDEX IF NOT EXISTS idx_trip_assets_trip_id ON trip_assets(trip_id)"
)
DDL_SQLITE_INDEX_ASSETS_TRIP = (
    "CREATE INDEX IF NOT EXISTS idx_trip_assets_trip_id ON trip_assets(trip_id)"
)

# --- SQL constants ---

_SQL_PG_GET_TRIP_ID_BY_LINK = "SELECT id FROM trips WHERE link = %s"
_SQL_SQLITE_GET_TRIP_ID_BY_LINK = "SELECT id FROM trips WHERE link = ?"

_SQL_PG_INSERT_ASSET = """
    INSERT INTO trip_assets (trip_id, original_name, stored_filename, mime_type, file_size, extracted_text)
    VALUES (%s, %s, %s, %s, %s, %s)
    RETURNING id
"""
_SQL_SQLITE_INSERT_ASSET = """
    INSERT INTO trip_assets (trip_id, original_name, stored_filename, mime_type, file_size, extracted_text)
    VALUES (?, ?, ?, ?, ?, ?)
"""

_SQL_PG_GET_ASSETS_FOR_TRIP = """
    SELECT a.id, a.original_name, a.stored_filename, a.mime_type, a.file_size, a.created_at
    FROM trip_assets a
    JOIN trips t ON a.trip_id = t.id
    WHERE t.link = %s
    ORDER BY a.created_at
"""
_SQL_SQLITE_GET_ASSETS_FOR_TRIP = """
    SELECT a.id, a.original_name, a.stored_filename, a.mime_type, a.file_size, a.created_at
    FROM trip_assets a
    JOIN trips t ON a.trip_id = t.id
    WHERE t.link = ?
    ORDER BY a.created_at
"""

_SQL_PG_GET_ASSETS_WITH_TEXT = """
    SELECT a.extracted_text
    FROM trip_assets a
    JOIN trips t ON a.trip_id = t.id
    WHERE t.link = %s AND a.extracted_text IS NOT NULL AND a.extracted_text != ''
    ORDER BY a.created_at
"""
_SQL_SQLITE_GET_ASSETS_WITH_TEXT = """
    SELECT a.extracted_text
    FROM trip_assets a
    JOIN trips t ON a.trip_id = t.id
    WHERE t.link = ? AND a.extracted_text IS NOT NULL AND a.extracted_text != ''
    ORDER BY a.created_at
"""

_SQL_PG_GET_ASSET_BY_ID = """
    SELECT a.id, a.trip_id, a.original_name, a.stored_filename, a.mime_type, a.file_size, t.link
    FROM trip_assets a
    JOIN trips t ON a.trip_id = t.id
    WHERE a.id = %s
"""
_SQL_SQLITE_GET_ASSET_BY_ID = """
    SELECT a.id, a.trip_id, a.original_name, a.stored_filename, a.mime_type, a.file_size, t.link
    FROM trip_assets a
    JOIN trips t ON a.trip_id = t.id
    WHERE a.id = ?
"""

_SQL_PG_DELETE_ASSET = "DELETE FROM trip_assets WHERE id = %s AND trip_id = %s"
_SQL_SQLITE_DELETE_ASSET = "DELETE FROM trip_assets WHERE id = ? AND trip_id = ?"

_ASSET_LIST_COLUMNS = [
    "id",
    "original_name",
    "stored_filename",
    "mime_type",
    "file_size",
    "created_at",
]
_ASSET_FULL_COLUMNS = [
    "id",
    "trip_id",
    "original_name",
    "stored_filename",
    "mime_type",
    "file_size",
    "link",
]


def _trip_id_for_link(cursor, link: str) -> int | None:
    if USE_POSTGRES:
        cursor.execute(_SQL_PG_GET_TRIP_ID_BY_LINK, (link,))
    else:
        cursor.execute(_SQL_SQLITE_GET_TRIP_ID_BY_LINK, (link,))
    row = cursor.fetchone()
    return row[0] if row else None


def save_asset(
    trip_link: str,
    original_name: str,
    stored_filename: str,
    mime_type: str,
    file_size: int,
    extracted_text: str | None = None,
) -> int | None:
    """Record an uploaded asset. Returns the new asset id, or None on failure."""
    with get_db() as conn:
        cursor = conn.cursor()
        trip_id = _trip_id_for_link(cursor, trip_link)
        if not trip_id:
            return None
        if USE_POSTGRES:
            cursor.execute(
                _SQL_PG_INSERT_ASSET,
                (trip_id, original_name, stored_filename, mime_type, file_size, extracted_text),
            )
            row = cursor.fetchone()
            return row[0] if row else None
        else:
            cursor.execute(
                _SQL_SQLITE_INSERT_ASSET,
                (trip_id, original_name, stored_filename, mime_type, file_size, extracted_text),
            )
            return cursor.lastrowid


def get_assets_for_trip(trip_link: str) -> list[dict[str, Any]]:
    """List all assets for a trip (no extracted_text - kept server-side only)."""
    with get_db() as conn:
        cursor = conn.cursor()
        if USE_POSTGRES:
            cursor.execute(_SQL_PG_GET_ASSETS_FOR_TRIP, (trip_link,))
            return [dict(zip(_ASSET_LIST_COLUMNS, row, strict=False)) for row in cursor.fetchall()]
        else:
            cursor.execute(_SQL_SQLITE_GET_ASSETS_FOR_TRIP, (trip_link,))
            return [dict(row) for row in cursor.fetchall()]


def get_asset_by_id(asset_id: int) -> dict[str, Any] | None:
    """Return a single asset row including trip link, for auth checks."""
    with get_db() as conn:
        cursor = conn.cursor()
        if USE_POSTGRES:
            cursor.execute(_SQL_PG_GET_ASSET_BY_ID, (asset_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return dict(zip(_ASSET_FULL_COLUMNS, row, strict=False))
        else:
            cursor.execute(_SQL_SQLITE_GET_ASSET_BY_ID, (asset_id,))
            row = cursor.fetchone()
            return dict(row) if row else None


def get_extracted_texts_for_trip(trip_link: str) -> list[str]:
    """Return list of non-empty extracted_text values for all trip assets."""
    with get_db() as conn:
        cursor = conn.cursor()
        if USE_POSTGRES:
            cursor.execute(_SQL_PG_GET_ASSETS_WITH_TEXT, (trip_link,))
        else:
            cursor.execute(_SQL_SQLITE_GET_ASSETS_WITH_TEXT, (trip_link,))
        return [row[0] for row in cursor.fetchall()]


def delete_asset(asset_id: int, trip_link: str) -> bool:
    """Delete an asset, verifying it belongs to trip_link. Returns True if deleted."""
    with get_db() as conn:
        cursor = conn.cursor()
        trip_id = _trip_id_for_link(cursor, trip_link)
        if not trip_id:
            return False
        if USE_POSTGRES:
            cursor.execute(_SQL_PG_DELETE_ASSET, (asset_id, trip_id))
        else:
            cursor.execute(_SQL_SQLITE_DELETE_ASSET, (asset_id, trip_id))
        return cursor.rowcount > 0
