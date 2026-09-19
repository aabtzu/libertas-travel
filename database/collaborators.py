"""Trip collaborator functions: invite, accept, list, remove."""

from __future__ import annotations

import secrets
from typing import Any

from database.connection import USE_POSTGRES, get_db

# --- DDL (called from connection.init_db) ---

DDL_PG_CREATE_COLLABORATORS = """
    CREATE TABLE IF NOT EXISTS trip_collaborators (
        id SERIAL PRIMARY KEY,
        trip_id INTEGER NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
        user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
        invited_email VARCHAR(255) NOT NULL,
        role VARCHAR(20) NOT NULL DEFAULT 'editor',
        invited_by INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        token VARCHAR(64) NOT NULL UNIQUE,
        accepted_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
"""

DDL_SQLITE_CREATE_COLLABORATORS = """
    CREATE TABLE IF NOT EXISTS trip_collaborators (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        trip_id INTEGER NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
        user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
        invited_email TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'editor',
        invited_by INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        token TEXT NOT NULL UNIQUE,
        accepted_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
"""

DDL_PG_INDEX_COLLABORATORS_TRIP = (
    "CREATE INDEX IF NOT EXISTS idx_collaborators_trip_id ON trip_collaborators(trip_id)"
)
DDL_SQLITE_INDEX_COLLABORATORS_TRIP = (
    "CREATE INDEX IF NOT EXISTS idx_collaborators_trip_id ON trip_collaborators(trip_id)"
)
DDL_PG_INDEX_COLLABORATORS_USER = (
    "CREATE INDEX IF NOT EXISTS idx_collaborators_user_id ON trip_collaborators(user_id)"
)
DDL_SQLITE_INDEX_COLLABORATORS_USER = (
    "CREATE INDEX IF NOT EXISTS idx_collaborators_user_id ON trip_collaborators(user_id)"
)

# --- SQL constants ---

_SQL_PG_INSERT_INVITE = """
    INSERT INTO trip_collaborators (trip_id, invited_email, role, invited_by, token)
    VALUES (%s, %s, %s, %s, %s)
    ON CONFLICT DO NOTHING
    RETURNING id
"""
_SQL_SQLITE_INSERT_INVITE = """
    INSERT OR IGNORE INTO trip_collaborators (trip_id, invited_email, role, invited_by, token)
    VALUES (?, ?, ?, ?, ?)
"""

_SQL_PG_GET_COLLABORATOR_BY_TOKEN = """
    SELECT c.id, c.trip_id, c.user_id, c.invited_email, c.role, c.invited_by,
           c.accepted_at, t.link, t.title, t.user_id AS owner_id
    FROM trip_collaborators c
    JOIN trips t ON c.trip_id = t.id
    WHERE c.token = %s
"""
_SQL_SQLITE_GET_COLLABORATOR_BY_TOKEN = """
    SELECT c.id, c.trip_id, c.user_id, c.invited_email, c.role, c.invited_by,
           c.accepted_at, t.link, t.title, t.user_id AS owner_id
    FROM trip_collaborators c
    JOIN trips t ON c.trip_id = t.id
    WHERE c.token = ?
"""

_SQL_PG_ACCEPT_INVITE = """
    UPDATE trip_collaborators
    SET user_id = %s, accepted_at = NOW()
    WHERE token = %s AND accepted_at IS NULL
"""
_SQL_SQLITE_ACCEPT_INVITE = """
    UPDATE trip_collaborators
    SET user_id = ?, accepted_at = CURRENT_TIMESTAMP
    WHERE token = ? AND accepted_at IS NULL
"""

_SQL_PG_GET_COLLABORATORS_FOR_TRIP = """
    SELECT c.id, c.user_id, c.invited_email, c.role, c.accepted_at,
           u.username
    FROM trip_collaborators c
    LEFT JOIN users u ON c.user_id = u.id
    WHERE c.trip_id = %s
    ORDER BY c.created_at
"""
_SQL_SQLITE_GET_COLLABORATORS_FOR_TRIP = """
    SELECT c.id, c.user_id, c.invited_email, c.role, c.accepted_at,
           u.username
    FROM trip_collaborators c
    LEFT JOIN users u ON c.user_id = u.id
    WHERE c.trip_id = ?
    ORDER BY c.created_at
"""

_SQL_PG_IS_COLLABORATOR = """
    SELECT id FROM trip_collaborators
    WHERE trip_id = %s AND user_id = %s AND accepted_at IS NOT NULL
"""
_SQL_SQLITE_IS_COLLABORATOR = """
    SELECT id FROM trip_collaborators
    WHERE trip_id = ? AND user_id = ? AND accepted_at IS NOT NULL
"""

_SQL_PG_GET_SHARED_TRIPS = """
    SELECT t.id, t.user_id, t.title, t.link, t.dates, t.days, t.locations,
           t.activities, t.map_status, t.map_error, t.itinerary_data,
           t.is_public, t.is_draft, t.is_archived, t.trip_type,
           u.username AS owner_username
    FROM trip_collaborators c
    JOIN trips t ON c.trip_id = t.id
    JOIN users u ON t.user_id = u.id
    WHERE c.user_id = %s AND c.accepted_at IS NOT NULL
    ORDER BY t.created_at DESC
"""
_SQL_SQLITE_GET_SHARED_TRIPS = """
    SELECT t.id, t.user_id, t.title, t.link, t.dates, t.days, t.locations,
           t.activities, t.map_status, t.map_error, t.itinerary_data,
           t.is_public, t.is_draft, t.is_archived, t.trip_type,
           u.username AS owner_username
    FROM trip_collaborators c
    JOIN trips t ON c.trip_id = t.id
    JOIN users u ON t.user_id = u.id
    WHERE c.user_id = ? AND c.accepted_at IS NOT NULL
    ORDER BY t.created_at DESC
"""

_SQL_PG_REMOVE_COLLABORATOR = """
    DELETE FROM trip_collaborators WHERE id = %s AND trip_id = %s
"""
_SQL_SQLITE_REMOVE_COLLABORATOR = """
    DELETE FROM trip_collaborators WHERE id = ? AND trip_id = ?
"""

_SQL_PG_BIND_PENDING_INVITES = """
    UPDATE trip_collaborators
    SET user_id = %s, accepted_at = NOW()
    WHERE invited_email = %s AND user_id IS NULL AND accepted_at IS NULL
"""
_SQL_SQLITE_BIND_PENDING_INVITES = """
    UPDATE trip_collaborators
    SET user_id = ?, accepted_at = CURRENT_TIMESTAMP
    WHERE invited_email = ? AND user_id IS NULL AND accepted_at IS NULL
"""

_SQL_PG_GET_TRIP_ID_BY_LINK = "SELECT id FROM trips WHERE link = %s"
_SQL_SQLITE_GET_TRIP_ID_BY_LINK = "SELECT id FROM trips WHERE link = ?"

_SQL_PG_GET_EXISTING_INVITE = """
    SELECT id FROM trip_collaborators WHERE trip_id = %s AND invited_email = %s
"""
_SQL_SQLITE_GET_EXISTING_INVITE = """
    SELECT id FROM trip_collaborators WHERE trip_id = ? AND invited_email = ?
"""

_COLLAB_COLUMNS = [
    "id",
    "trip_id",
    "user_id",
    "invited_email",
    "role",
    "invited_by",
    "accepted_at",
    "link",
    "title",
    "owner_id",
]

_SHARED_TRIP_COLUMNS = [
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
    "is_public",
    "is_draft",
    "is_archived",
    "trip_type",
    "owner_username",
]

_LIST_COLUMNS = [
    "id",
    "user_id",
    "invited_email",
    "role",
    "accepted_at",
    "username",
]


def _trip_id_for_link(cursor, link: str) -> int | None:
    if USE_POSTGRES:
        cursor.execute(_SQL_PG_GET_TRIP_ID_BY_LINK, (link,))
    else:
        cursor.execute(_SQL_SQLITE_GET_TRIP_ID_BY_LINK, (link,))
    row = cursor.fetchone()
    return row[0] if row else None


def invite_collaborator(
    trip_link: str, invited_email: str, invited_by_user_id: int, role: str = "editor"
) -> str | None:
    """Add a pending collaborator invite. Returns the invite token, or None if already invited."""
    with get_db() as conn:
        cursor = conn.cursor()
        trip_id = _trip_id_for_link(cursor, trip_link)
        if not trip_id:
            return None

        # Check for existing invite (accepted or pending)
        if USE_POSTGRES:
            cursor.execute(_SQL_PG_GET_EXISTING_INVITE, (trip_id, invited_email.lower()))
        else:
            cursor.execute(_SQL_SQLITE_GET_EXISTING_INVITE, (trip_id, invited_email.lower()))
        if cursor.fetchone():
            return None  # already invited

        token = secrets.token_urlsafe(32)
        if USE_POSTGRES:
            cursor.execute(
                _SQL_PG_INSERT_INVITE,
                (trip_id, invited_email.lower(), role, invited_by_user_id, token),
            )
        else:
            cursor.execute(
                _SQL_SQLITE_INSERT_INVITE,
                (trip_id, invited_email.lower(), role, invited_by_user_id, token),
            )
        return token


def get_invite_by_token(token: str) -> dict[str, Any] | None:
    """Return invite details + trip link/title for a given token."""
    with get_db() as conn:
        cursor = conn.cursor()
        if USE_POSTGRES:
            cursor.execute(_SQL_PG_GET_COLLABORATOR_BY_TOKEN, (token,))
            row = cursor.fetchone()
            if not row:
                return None
            return dict(zip(_COLLAB_COLUMNS, row, strict=False))
        else:
            cursor.execute(_SQL_SQLITE_GET_COLLABORATOR_BY_TOKEN, (token,))
            row = cursor.fetchone()
            return dict(row) if row else None


def accept_invite(token: str, user_id: int) -> bool:
    """Bind a user_id to an invite and mark it accepted. Returns True on success."""
    with get_db() as conn:
        cursor = conn.cursor()
        if USE_POSTGRES:
            cursor.execute(_SQL_PG_ACCEPT_INVITE, (user_id, token))
        else:
            cursor.execute(_SQL_SQLITE_ACCEPT_INVITE, (user_id, token))
        return cursor.rowcount > 0


def bind_pending_invites_for_email(user_id: int, email: str) -> int:
    """Auto-accept all pending invites for an email address when user logs in/registers.

    Returns count of invites bound.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        if USE_POSTGRES:
            cursor.execute(_SQL_PG_BIND_PENDING_INVITES, (user_id, email.lower()))
        else:
            cursor.execute(_SQL_SQLITE_BIND_PENDING_INVITES, (user_id, email.lower()))
        return cursor.rowcount


def is_collaborator(trip_id: int, user_id: int) -> bool:
    """True if user_id is an accepted collaborator on trip_id."""
    with get_db() as conn:
        cursor = conn.cursor()
        if USE_POSTGRES:
            cursor.execute(_SQL_PG_IS_COLLABORATOR, (trip_id, user_id))
        else:
            cursor.execute(_SQL_SQLITE_IS_COLLABORATOR, (trip_id, user_id))
        return cursor.fetchone() is not None


def get_collaborators_for_trip(trip_link: str) -> list[dict[str, Any]]:
    """List all collaborators (pending and accepted) for a trip."""
    with get_db() as conn:
        cursor = conn.cursor()
        trip_id = _trip_id_for_link(cursor, trip_link)
        if not trip_id:
            return []
        if USE_POSTGRES:
            cursor.execute(_SQL_PG_GET_COLLABORATORS_FOR_TRIP, (trip_id,))
            return [dict(zip(_LIST_COLUMNS, row, strict=False)) for row in cursor.fetchall()]
        else:
            cursor.execute(_SQL_SQLITE_GET_COLLABORATORS_FOR_TRIP, (trip_id,))
            return [dict(row) for row in cursor.fetchall()]


def remove_collaborator(trip_link: str, collaborator_id: int) -> bool:
    """Remove a collaborator row by its id. Returns True if deleted."""
    with get_db() as conn:
        cursor = conn.cursor()
        trip_id = _trip_id_for_link(cursor, trip_link)
        if not trip_id:
            return False
        if USE_POSTGRES:
            cursor.execute(_SQL_PG_REMOVE_COLLABORATOR, (collaborator_id, trip_id))
        else:
            cursor.execute(_SQL_SQLITE_REMOVE_COLLABORATOR, (collaborator_id, trip_id))
        return cursor.rowcount > 0


def can_user_edit_trip(trip_link: str, user_id: int) -> bool:
    """True if user_id is the trip owner OR an accepted editor collaborator."""
    from database.trips import get_trip_owner

    owner_id = get_trip_owner(trip_link)
    if owner_id is None:
        return False
    if owner_id == user_id:
        return True
    with get_db() as conn:
        cursor = conn.cursor()
        trip_id = _trip_id_for_link(cursor, trip_link)
        if not trip_id:
            return False
        if USE_POSTGRES:
            cursor.execute(_SQL_PG_IS_COLLABORATOR, (trip_id, user_id))
        else:
            cursor.execute(_SQL_SQLITE_IS_COLLABORATOR, (trip_id, user_id))
        return cursor.fetchone() is not None


def get_shared_trips_for_user(user_id: int) -> list[dict[str, Any]]:
    """Return trips where user_id is an accepted collaborator (not the owner)."""
    with get_db() as conn:
        cursor = conn.cursor()
        if USE_POSTGRES:
            cursor.execute(_SQL_PG_GET_SHARED_TRIPS, (user_id,))
            return [dict(zip(_SHARED_TRIP_COLUMNS, row, strict=False)) for row in cursor.fetchall()]
        else:
            cursor.execute(_SQL_SQLITE_GET_SHARED_TRIPS, (user_id,))
            return [dict(row) for row in cursor.fetchall()]
