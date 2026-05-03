"""Auth blueprint: login, register, logout."""

from __future__ import annotations

from datetime import UTC, datetime

from flask import Blueprint, request, session

from agents.auth import credentials as auth
from agents.common.flask_utils import json_err, json_ok

auth_bp = Blueprint("auth", __name__)


@auth_bp.post("/api/login")
def login():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()

    if not username or not password:
        return json_err("Username and password required")

    user = auth.verify_credentials(username, password)
    if not user:
        return json_err("Invalid username or password", status=401)

    session["user_id"] = user["id"]
    session["username"] = user["username"]
    return json_ok({"success": True, "username": user["username"]})


@auth_bp.post("/api/register")
def register():
    import os

    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    email = data.get("email", "").strip()
    password = data.get("password", "").strip()
    invite_code = data.get("invite_code", "").strip()

    # If INVITE_CODE env var is set, require a matching code to register.
    expected = os.environ.get("INVITE_CODE", "")
    if expected:
        if not invite_code:
            return json_err("An invite code is required to register.")
        if invite_code != expected:
            return json_err("Invalid invite code.")

    success, error = auth.register_user(username, email, password)
    if success:
        # Greppable line in Render logs so the owner can monitor signups
        # via `render logs | grep '\[SIGNUP\]'`. Email/IP intentionally
        # omitted from logs — keep PII out of the log stream.
        ts = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        print(f"[SIGNUP] {username} @ {ts}", flush=True)
        return json_ok({"success": True})
    return json_err(error)


@auth_bp.post("/api/logout")
def logout():
    session.clear()
    return json_ok({"success": True})
