"""User CRUD operations."""

from __future__ import annotations

from typing import Any

import bcrypt

from database.connection import USE_POSTGRES, get_db

# --- SQL constants ---

_SQL_PG_INSERT_USER = (
    "INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s) RETURNING id"
)
_SQL_SQLITE_INSERT_USER = "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)"

_SQL_PG_GET_USER_BY_USERNAME = (
    "SELECT id, username, email, password_hash FROM users WHERE username = %s"
)
_SQL_SQLITE_GET_USER_BY_USERNAME = (
    "SELECT id, username, email, password_hash FROM users WHERE username = ?"
)

_SQL_PG_GET_USER_BY_ID = "SELECT id, username, email FROM users WHERE id = %s"
_SQL_SQLITE_GET_USER_BY_ID = "SELECT id, username, email FROM users WHERE id = ?"

_SQL_PG_USERNAME_EXISTS = "SELECT 1 FROM users WHERE username = %s"
_SQL_SQLITE_USERNAME_EXISTS = "SELECT 1 FROM users WHERE username = ?"

_SQL_PG_EMAIL_EXISTS = "SELECT 1 FROM users WHERE email = %s"
_SQL_SQLITE_EMAIL_EXISTS = "SELECT 1 FROM users WHERE email = ?"

_SQL_PG_GET_USER_BY_EMAIL = "SELECT id, username, email FROM users WHERE LOWER(email) = LOWER(%s)"
_SQL_SQLITE_GET_USER_BY_EMAIL = (
    "SELECT id, username, email FROM users WHERE LOWER(email) = LOWER(?)"
)

_SQL_GET_ALL_USERS = "SELECT id, username FROM users ORDER BY username"

_SQL_PG_SET_USER_EMAIL = "UPDATE users SET email = %s WHERE username = %s"
_SQL_SQLITE_SET_USER_EMAIL = "UPDATE users SET email = ? WHERE username = ?"

_SQL_PG_DELETE_USER = "DELETE FROM users WHERE username = %s"
_SQL_SQLITE_DELETE_USER = "DELETE FROM users WHERE username = ?"

_SQL_PG_GET_USER_BY_FORWARDING_EMAIL = """
    SELECT u.id, u.username, u.email
    FROM users u
    JOIN user_forwarding_emails f ON f.user_id = u.id
    WHERE LOWER(f.email) = LOWER(%s)
"""
_SQL_SQLITE_GET_USER_BY_FORWARDING_EMAIL = """
    SELECT u.id, u.username, u.email
    FROM users u
    JOIN user_forwarding_emails f ON f.user_id = u.id
    WHERE LOWER(f.email) = LOWER(?)
"""

_SQL_PG_ADD_FORWARDING_EMAIL = (
    "INSERT INTO user_forwarding_emails (user_id, email) VALUES (%s, %s) ON CONFLICT DO NOTHING"
)
_SQL_SQLITE_ADD_FORWARDING_EMAIL = (
    "INSERT OR IGNORE INTO user_forwarding_emails (user_id, email) VALUES (?, ?)"
)

_SQL_PG_REMOVE_FORWARDING_EMAIL = (
    "DELETE FROM user_forwarding_emails WHERE user_id = %s AND LOWER(email) = LOWER(%s)"
)
_SQL_SQLITE_REMOVE_FORWARDING_EMAIL = (
    "DELETE FROM user_forwarding_emails WHERE user_id = ? AND LOWER(email) = LOWER(?)"
)

_SQL_PG_GET_FORWARDING_EMAILS = (
    "SELECT email FROM user_forwarding_emails WHERE user_id = %s ORDER BY created_at"
)
_SQL_SQLITE_GET_FORWARDING_EMAILS = (
    "SELECT email FROM user_forwarding_emails WHERE user_id = ? ORDER BY created_at"
)


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against its hash."""
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def create_user(username: str, email: str, password: str) -> int | None:
    """Create a new user. Returns user ID or None if failed."""
    password_hash = hash_password(password)

    with get_db() as conn:
        cursor = conn.cursor()
        try:
            if USE_POSTGRES:
                cursor.execute(_SQL_PG_INSERT_USER, (username, email, password_hash))
                return cursor.fetchone()[0]
            else:
                cursor.execute(_SQL_SQLITE_INSERT_USER, (username, email, password_hash))
                return cursor.lastrowid
        except Exception as e:
            print(f"[DB] Error creating user: {e}")
            return None


def get_user_by_username(username: str) -> dict[str, Any] | None:
    """Get user by username."""
    with get_db() as conn:
        cursor = conn.cursor()
        if USE_POSTGRES:
            cursor.execute(_SQL_PG_GET_USER_BY_USERNAME, (username,))
        else:
            cursor.execute(_SQL_SQLITE_GET_USER_BY_USERNAME, (username,))

        row = cursor.fetchone()
        if row:
            if USE_POSTGRES:
                return {"id": row[0], "username": row[1], "email": row[2], "password_hash": row[3]}
            else:
                return dict(row)
        return None


def get_user_by_id(user_id: int) -> dict[str, Any] | None:
    """Get user by ID."""
    with get_db() as conn:
        cursor = conn.cursor()
        if USE_POSTGRES:
            cursor.execute(_SQL_PG_GET_USER_BY_ID, (user_id,))
        else:
            cursor.execute(_SQL_SQLITE_GET_USER_BY_ID, (user_id,))

        row = cursor.fetchone()
        if row:
            if USE_POSTGRES:
                return {"id": row[0], "username": row[1], "email": row[2]}
            else:
                return dict(row)
        return None


def authenticate_user(username: str, password: str) -> dict[str, Any] | None:
    """Authenticate user and return user dict if successful."""
    user = get_user_by_username(username)
    if user and verify_password(password, user["password_hash"]):
        del user["password_hash"]  # Don't return the hash
        return user
    return None


def username_exists(username: str) -> bool:
    """Check if username already exists."""
    with get_db() as conn:
        cursor = conn.cursor()
        if USE_POSTGRES:
            cursor.execute(_SQL_PG_USERNAME_EXISTS, (username,))
        else:
            cursor.execute(_SQL_SQLITE_USERNAME_EXISTS, (username,))
        return cursor.fetchone() is not None


def email_exists(email: str) -> bool:
    """Check if email already exists."""
    with get_db() as conn:
        cursor = conn.cursor()
        if USE_POSTGRES:
            cursor.execute(_SQL_PG_EMAIL_EXISTS, (email,))
        else:
            cursor.execute(_SQL_SQLITE_EMAIL_EXISTS, (email,))
        return cursor.fetchone() is not None


def get_user_by_email(email: str) -> dict[str, Any] | None:
    """Look up a user by primary or forwarding email address (case-insensitive)."""
    with get_db() as conn:
        cursor = conn.cursor()
        if USE_POSTGRES:
            cursor.execute(_SQL_PG_GET_USER_BY_EMAIL, (email,))
        else:
            cursor.execute(_SQL_SQLITE_GET_USER_BY_EMAIL, (email,))
        row = cursor.fetchone()
        if row:
            return {"id": row[0], "username": row[1], "email": row[2]}
        # Fall back to forwarding addresses
        if USE_POSTGRES:
            cursor.execute(_SQL_PG_GET_USER_BY_FORWARDING_EMAIL, (email,))
        else:
            cursor.execute(_SQL_SQLITE_GET_USER_BY_FORWARDING_EMAIL, (email,))
        row = cursor.fetchone()
        if row:
            return {"id": row[0], "username": row[1], "email": row[2]}
        return None


def get_forwarding_emails(user_id: int) -> list[str]:
    """Return all secondary forwarding email addresses for a user."""
    with get_db() as conn:
        cursor = conn.cursor()
        if USE_POSTGRES:
            cursor.execute(_SQL_PG_GET_FORWARDING_EMAILS, (user_id,))
        else:
            cursor.execute(_SQL_SQLITE_GET_FORWARDING_EMAILS, (user_id,))
        return [row[0] for row in cursor.fetchall()]


def add_forwarding_email(user_id: int, email: str) -> bool:
    """Add a secondary forwarding email for a user. Returns False if it already exists."""
    with get_db() as conn:
        cursor = conn.cursor()
        if USE_POSTGRES:
            cursor.execute(_SQL_PG_ADD_FORWARDING_EMAIL, (user_id, email))
        else:
            cursor.execute(_SQL_SQLITE_ADD_FORWARDING_EMAIL, (user_id, email))
        return cursor.rowcount > 0


def remove_forwarding_email(user_id: int, email: str) -> bool:
    """Remove a secondary forwarding email for a user."""
    with get_db() as conn:
        cursor = conn.cursor()
        if USE_POSTGRES:
            cursor.execute(_SQL_PG_REMOVE_FORWARDING_EMAIL, (user_id, email))
        else:
            cursor.execute(_SQL_SQLITE_REMOVE_FORWARDING_EMAIL, (user_id, email))
        return cursor.rowcount > 0


def set_user_email(username: str, email: str) -> bool:
    """Update the email address for a user by username."""
    with get_db() as conn:
        cursor = conn.cursor()
        if USE_POSTGRES:
            cursor.execute(_SQL_PG_SET_USER_EMAIL, (email, username))
        else:
            cursor.execute(_SQL_SQLITE_SET_USER_EMAIL, (email, username))
        return cursor.rowcount > 0


def ensure_demo_user() -> int:
    """Get or create the system demo user. Returns the user ID.

    The demo user owns public sample trips (e.g. the Paris demo trip).
    It has no real email and a random password that is never used for login.
    """
    import uuid

    username = "demo"
    existing = get_user_by_username(username)
    if existing:
        return existing["id"]

    # Create the demo user with a random password (never used for login)
    password = str(uuid.uuid4())
    user_id = create_user(username, "demo@libertas.app", password)
    if user_id is None:
        raise RuntimeError("Failed to create demo system user")
    print(f"[SEED] Created demo system user with id={user_id}")
    return user_id


_SQL_PG_GET_USER_PROFILE = "SELECT profile FROM users WHERE id = %s"
_SQL_SQLITE_GET_USER_PROFILE = "SELECT profile FROM users WHERE id = ?"

_SQL_PG_SET_USER_PROFILE = "UPDATE users SET profile = %s WHERE id = %s"
_SQL_SQLITE_SET_USER_PROFILE = "UPDATE users SET profile = ? WHERE id = ?"


def get_user_profile(user_id: int) -> dict[str, Any] | None:
    """Get user profile data (style, preferences)."""
    with get_db() as conn:
        cursor = conn.cursor()
        if USE_POSTGRES:
            cursor.execute(_SQL_PG_GET_USER_PROFILE, (user_id,))
        else:
            cursor.execute(_SQL_SQLITE_GET_USER_PROFILE, (user_id,))
        row = cursor.fetchone()
        if row and row[0]:
            if isinstance(row[0], str):
                import json

                return json.loads(row[0])
            return row[0]  # JSONB auto-parses in psycopg2
        return None


def set_user_profile(user_id: int, profile_data: dict[str, Any]) -> bool:
    """Save user profile data."""
    import json

    with get_db() as conn:
        cursor = conn.cursor()
        profile_json = json.dumps(profile_data)
        if USE_POSTGRES:
            cursor.execute(_SQL_PG_SET_USER_PROFILE, (profile_json, user_id))
        else:
            cursor.execute(_SQL_SQLITE_SET_USER_PROFILE, (profile_json, user_id))
        return cursor.rowcount > 0


def get_all_users() -> list[dict[str, Any]]:
    """Get list of all users (id and username only, for sharing)."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(_SQL_GET_ALL_USERS)
        if USE_POSTGRES:
            return [{"id": row[0], "username": row[1]} for row in cursor.fetchall()]
        else:
            return [dict(row) for row in cursor.fetchall()]


def delete_user_by_username(username: str) -> bool:
    """Delete a user (and their trips, via ON DELETE CASCADE on the trips
    FK). Returns True if a row was deleted, False if no such user.

    Used by the admin endpoint to clean up test accounts pre-launch.
    Permanent, there is no undo. Don't use this on the demo system user.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        if USE_POSTGRES:
            cursor.execute(_SQL_PG_DELETE_USER, (username,))
        else:
            cursor.execute(_SQL_SQLITE_DELETE_USER, (username,))
        return cursor.rowcount > 0
