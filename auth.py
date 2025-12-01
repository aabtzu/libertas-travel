"""Authentication module for Libertas with database support."""

import os
import secrets
import time
from typing import Optional, Dict

import database as db

# Session settings
SESSION_DURATION = 24 * 60 * 60  # 24 hours in seconds
SESSION_COOKIE_NAME = "libertas_session"

# In-memory session store (sessions persist while server is running)
_sessions = {}  # type: Dict[str, dict]


def verify_credentials(username: str, password: str) -> Optional[Dict]:
    """Verify username and password against database.
    Returns user dict if successful, None otherwise.
    """
    return db.authenticate_user(username, password)


def register_user(username: str, email: str, password: str) -> tuple:
    """Register a new user.
    Returns (success: bool, error_message: str or None)
    """
    # Validate input
    if not username or len(username) < 3:
        return False, "Username must be at least 3 characters"
    if not email or "@" not in email:
        return False, "Invalid email address"
    if not password or len(password) < 6:
        return False, "Password must be at least 6 characters"

    # Check if username/email exists
    if db.username_exists(username):
        return False, "Username already taken"
    if db.email_exists(email):
        return False, "Email already registered"

    # Create user
    user_id = db.create_user(username, email, password)
    if user_id:
        return True, None
    else:
        return False, "Failed to create user"


def create_session(user: Dict) -> str:
    """Create a new session and return the session token."""
    token = secrets.token_urlsafe(32)
    _sessions[token] = {
        "user_id": user["id"],
        "username": user["username"],
        "created": time.time(),
        "expires": time.time() + SESSION_DURATION,
    }
    return token


def validate_session(token: Optional[str]) -> Optional[dict]:
    """Validate a session token and return session data if valid."""
    if not token:
        return None

    session = _sessions.get(token)
    if not session:
        return None

    # Check if session has expired
    if time.time() > session["expires"]:
        del _sessions[token]
        return None

    return session


def get_session_user_id(token: Optional[str]) -> Optional[int]:
    """Get the user_id from a session token."""
    session = validate_session(token)
    if session:
        return session.get("user_id")
    return None


def destroy_session(token: str) -> bool:
    """Destroy a session by its token."""
    if token in _sessions:
        del _sessions[token]
        return True
    return False


def get_session_cookie_header(token, secure=False):
    # type: (str, bool) -> str
    """Generate Set-Cookie header value for session."""
    cookie = "{name}={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age={duration}".format(
        name=SESSION_COOKIE_NAME, token=token, duration=SESSION_DURATION
    )
    if secure:
        cookie += "; Secure"
    return cookie


def get_logout_cookie_header():
    # type: () -> str
    """Generate Set-Cookie header to clear the session cookie."""
    return "{name}=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0".format(name=SESSION_COOKIE_NAME)


def parse_cookies(cookie_header):
    # type: (str) -> Dict[str, str]
    """Parse Cookie header into dictionary."""
    cookies = {}
    if cookie_header:
        for item in cookie_header.split(";"):
            item = item.strip()
            if "=" in item:
                key, value = item.split("=", 1)
                cookies[key.strip()] = value.strip()
    return cookies


def is_auth_enabled():
    # type: () -> bool
    """Check if authentication is enabled."""
    return os.environ.get("AUTH_DISABLED", "").lower() != "true"


def ensure_default_user():
    """Ensure a default admin user exists (for initial setup)."""
    default_username = os.environ.get("AUTH_USERNAME", "admin")
    default_password = os.environ.get("AUTH_PASSWORD", "libertas")
    default_email = os.environ.get("AUTH_EMAIL", "admin@example.com")

    if not db.username_exists(default_username):
        user_id = db.create_user(default_username, default_email, default_password)
        if user_id:
            print(f"[AUTH] Created default user: {default_username}")
        else:
            print(f"[AUTH] Failed to create default user")
