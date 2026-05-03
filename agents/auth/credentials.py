"""Authentication module for Libertas — credentials and user management.

Session management is handled by Flask's signed cookie session (see app.py).
"""

from __future__ import annotations

import os

import database as db


def verify_credentials(username: str, password: str) -> dict | None:
    """Verify username and password. Returns user dict if valid, None otherwise."""
    return db.authenticate_user(username, password)


def register_user(username: str, email: str, password: str) -> tuple[bool, str | None]:
    """Register a new user. Returns (success, error_message)."""
    if not username or len(username) < 3:
        return False, "Username must be at least 3 characters"
    if not email or "@" not in email:
        return False, "Invalid email address"
    if not password or len(password) < 6:
        return False, "Password must be at least 6 characters"

    if db.username_exists(username):
        return False, "Username already taken"
    if db.email_exists(email):
        return False, "Email already registered"

    user_id = db.create_user(username, email, password)
    if user_id:
        return True, None
    return False, "Failed to create user"


def is_auth_enabled() -> bool:
    """Return True if authentication is active (AUTH_DISABLED env var not set)."""
    return os.environ.get("AUTH_DISABLED", "").lower() != "true"
