"""Simple authentication module for Libertas."""

import hashlib
import os
import secrets
import time
from typing import Optional, Dict, Tuple

# Default credentials (override with environment variables)
DEFAULT_USERNAME = "aab"
DEFAULT_PASSWORD = "abcxyz#$%"

# Session settings
SESSION_DURATION = 24 * 60 * 60  # 24 hours in seconds
SESSION_COOKIE_NAME = "libertas_session"

# In-memory session store (sessions persist while server is running)
_sessions = {}  # type: Dict[str, dict]


def get_credentials():
    # type: () -> Tuple[str, str]
    """Get authentication credentials from environment or defaults."""
    username = os.environ.get("AUTH_USERNAME", DEFAULT_USERNAME)
    password = os.environ.get("AUTH_PASSWORD", DEFAULT_PASSWORD)
    return username, password


def hash_password(password: str) -> str:
    """Create a simple hash of the password."""
    return hashlib.sha256(password.encode()).hexdigest()


def verify_credentials(username: str, password: str) -> bool:
    """Verify username and password against stored credentials."""
    expected_username, expected_password = get_credentials()
    return (
        username == expected_username and
        password == expected_password
    )


def create_session(username: str) -> str:
    """Create a new session and return the session token."""
    token = secrets.token_urlsafe(32)
    _sessions[token] = {
        "username": username,
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
    """Check if authentication is enabled (always enabled if credentials are set)."""
    # Auth is enabled by default; set AUTH_DISABLED=true to disable
    return os.environ.get("AUTH_DISABLED", "").lower() != "true"
