"""Auth blueprint: login, register, logout."""

from __future__ import annotations

import auth
from agents.common.flask_utils import json_err, json_ok
from flask import Blueprint, jsonify, request, session

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
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    email = data.get("email", "").strip()
    password = data.get("password", "").strip()

    success, error = auth.register_user(username, email, password)
    if success:
        return json_ok({"success": True})
    return json_err(error)


@auth_bp.post("/api/logout")
def logout():
    session.clear()
    return json_ok({"success": True})
