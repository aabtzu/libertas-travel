"""Shared Flask utilities: auth decorator and JSON response helpers."""

from __future__ import annotations

import functools
import os

from flask import g, jsonify, redirect, request, session


def load_current_user() -> None:
    """Populate flask.g with user info from session on every request."""
    g.user_id = session.get("user_id")
    g.username = session.get("username")
    g.auth_disabled = os.environ.get("AUTH_DISABLED", "").lower() == "true"
    # When auth is disabled (dev mode), default to user_id=1 — matches old server.py behaviour
    if g.auth_disabled and not g.user_id:
        g.user_id = 1


def require_auth(f):
    """Decorator: require authentication. Returns 401 for API routes, redirects HTML routes."""

    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if not g.auth_disabled and not g.user_id:
            if request.path.startswith("/api/"):
                return jsonify({"error": "Unauthorized"}), 401
            return redirect(f"/login?redirect={request.path}")
        return f(*args, **kwargs)

    return decorated


def json_ok(data: dict):
    return jsonify(data), 200


def json_err(msg: str, status: int = 400):
    return jsonify({"success": False, "error": msg}), status
