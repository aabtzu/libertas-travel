"""Explore blueprint: venue search and explore chat."""

from __future__ import annotations

from agents.common.flask_utils import json_err, json_ok
from agents.explore.handler import explore_chat_handler, load_venues
from flask import Blueprint, request

explore_bp = Blueprint("explore", __name__)


@explore_bp.get("/api/explore/venues")
def venues():
    return json_ok(load_venues())


@explore_bp.post("/api/explore/chat")
def explore_chat():
    data = request.get_json(silent=True) or {}
    message = data.get("message", "").strip()
    history = data.get("history", [])

    if not message:
        return json_err("No message provided")

    result, status = explore_chat_handler(message, history)
    if status == 200:
        return json_ok(result)
    return json_err(result.get("error", "Unknown error"), status=status)
