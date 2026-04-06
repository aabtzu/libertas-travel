"""User CRUD operations."""

from __future__ import annotations

from typing import Any

import bcrypt

from database.connection import USE_POSTGRES, get_db


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
                cursor.execute(
                    "INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s) RETURNING id",
                    (username, email, password_hash),
                )
                return cursor.fetchone()[0]
            else:
                cursor.execute(
                    "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
                    (username, email, password_hash),
                )
                return cursor.lastrowid
        except Exception as e:
            print(f"[DB] Error creating user: {e}")
            return None


def get_user_by_username(username: str) -> dict[str, Any] | None:
    """Get user by username."""
    with get_db() as conn:
        cursor = conn.cursor()
        if USE_POSTGRES:
            cursor.execute(
                "SELECT id, username, email, password_hash FROM users WHERE username = %s",
                (username,),
            )
        else:
            cursor.execute(
                "SELECT id, username, email, password_hash FROM users WHERE username = ?",
                (username,),
            )

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
            cursor.execute("SELECT id, username, email FROM users WHERE id = %s", (user_id,))
        else:
            cursor.execute("SELECT id, username, email FROM users WHERE id = ?", (user_id,))

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
            cursor.execute("SELECT 1 FROM users WHERE username = %s", (username,))
        else:
            cursor.execute("SELECT 1 FROM users WHERE username = ?", (username,))
        return cursor.fetchone() is not None


def email_exists(email: str) -> bool:
    """Check if email already exists."""
    with get_db() as conn:
        cursor = conn.cursor()
        if USE_POSTGRES:
            cursor.execute("SELECT 1 FROM users WHERE email = %s", (email,))
        else:
            cursor.execute("SELECT 1 FROM users WHERE email = ?", (email,))
        return cursor.fetchone() is not None


def get_all_users() -> list[dict[str, Any]]:
    """Get list of all users (id and username only, for sharing)."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, username FROM users ORDER BY username")
        if USE_POSTGRES:
            return [{"id": row[0], "username": row[1]} for row in cursor.fetchall()]
        else:
            return [dict(row) for row in cursor.fetchall()]
