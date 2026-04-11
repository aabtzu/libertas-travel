"""Explore blueprint: venue search and explore chat."""

from __future__ import annotations

from flask import Blueprint, request

from agents.common.flask_utils import json_err, json_ok
from agents.explore.handler import explore_chat_handler, load_venues

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

    try:
        result, status = explore_chat_handler(message, history)
    except Exception as e:
        import traceback

        traceback.print_exc()
        return json_err(f"Chat handler error: {e}", status=500)
    if status == 200:
        return json_ok(result)
    return json_err(result.get("error", "Unknown error"), status=status)
