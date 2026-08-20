"""Explore blueprint: venue search and explore chat."""

from __future__ import annotations

from flask import Blueprint, request, session

from agents.common.flask_utils import json_err, json_ok
from agents.common.venue_capture import save_venue_to_curated
from agents.explore.handler import explore_chat_handler, load_venues

explore_bp = Blueprint("explore", __name__)


@explore_bp.get("/api/explore/venues")
def venues():
    return json_ok(load_venues())


@explore_bp.post("/api/explore/chat")
def explore_chat():
    user_id = session.get("user_id")
    data = request.get_json(silent=True) or {}
    message = data.get("message", "").strip()
    history = data.get("history", [])
    current_venues = data.get("current_venues", [])

    if not message:
        return json_err("No message provided")

    try:
        result, status = explore_chat_handler(
            message, history, user_id=user_id, current_venues=current_venues
        )
    except Exception as e:
        import traceback

        traceback.print_exc()
        return json_err(f"Chat handler error: {e}", status=500)
    if status == 200:
        return json_ok(result)
    return json_err(result.get("error", "Unknown error"), status=status)


@explore_bp.post("/api/explore/save-venue")
def save_venue():
    """Save a single venue to the curated database."""
    user_id = session.get("user_id")
    data = request.get_json(silent=True) or {}
    name = data.get("name", "").strip()
    city = data.get("city", "").strip()
    notes = data.get("notes", "")
    venue_type = data.get("venue_type", "")

    if not name:
        return json_err("Venue name is required")

    result = save_venue_to_curated(name, city, notes, venue_type, user_id=user_id)
    return json_ok(result)
