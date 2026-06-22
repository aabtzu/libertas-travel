"""Trips blueprint: trip CRUD, export, calendar, sharing, geocoding, map status."""

from __future__ import annotations

import os
import re
import traceback
from pathlib import Path

from flask import Blueprint, g, request

import database as db
from agents.common.flask_utils import json_err, json_ok, require_auth
from agents.create import handler as create_handler
from agents.itinerary import geocoding_worker
from agents.trips.ics import (
    calendar_subscribe_token,
    generate_ics,
    generate_ics_multi,
    user_calendar_token,
    verify_subscribe_token,
    verify_user_calendar_token,
)

trips_bp = Blueprint("trips", __name__)

OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", Path(__file__).parent.parent.parent / "output"))


@trips_bp.get("/api/trips/list")
@require_auth
def list_trips():
    """Return lightweight list of user's trips (for dropdowns)."""
    trips = db.get_user_trips(g.user_id)
    return json_ok(
        {
            "trips": [
                {
                    "link": t["link"],
                    "title": t["title"],
                    "trip_type": t.get("trip_type", "itinerary"),
                }
                for t in trips
            ]
        }
    )


@trips_bp.get("/api/trips/<link>/data")
@require_auth
def get_trip_data(link: str):
    result, status = create_handler.get_trip_data_handler(g.user_id, link)
    if status == 200:
        return json_ok(result)
    return json_err(result.get("error", "Unknown error"), status=status)


@trips_bp.get("/api/trips/<link>/export")
@require_auth
def export_trip(link: str):
    result, status = create_handler.export_trip_handler(g.user_id, link)
    if status != 200:
        return json_err(result.get("error", "Unknown error"), status=status)

    export_data = result.get("export", {})
    title = export_data.get("title", "trip")
    safe_title = re.sub(r"[^\w\s-]", "", title).strip().replace(" ", "_")
    filename = f"{safe_title}_export.json"

    response = json_ok(export_data)
    response[0].headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@trips_bp.get("/api/trips/<link>/calendar.ics")
def export_ics(link: str):
    """Serve a trip as a downloadable .ics file (no token) or as a calendar
    subscription target (with ``?token=...``).

    No ``@require_auth`` here because subscribe mode is by design unauthenticated:
    Outlook / Apple Calendar / Google Calendar polls a fixed URL and can't
    send our session cookie. The token replaces the cookie. For download
    mode we still require an authenticated session.
    """
    from flask import Response

    token = request.args.get("token", "").strip()
    owner_id = db.get_trip_owner(link)
    if owner_id is None:
        return json_err("Trip not found", status=404)

    # Pick auth path: token overrides session.
    if token:
        if not verify_subscribe_token(owner_id, link, token):
            return json_err("Invalid token", status=403)
        viewer_id = owner_id
    else:
        if not g.user_id:
            return json_err("Authentication required", status=401)
        # Allow viewing public trips without owning them. Matches /<trip>.html.
        if g.user_id != owner_id and not db.is_trip_public(link):
            return json_err("Not found", status=404)
        viewer_id = owner_id  # always render against the owner's data

    result, status = create_handler.export_trip_handler(viewer_id, link)
    if status != 200:
        return json_err(result.get("error", "Unknown error"), status=status)

    export_data = result.get("export", {})
    title = export_data.get("title", "trip")
    safe_title = re.sub(r"[^\w\s-]", "", title).strip().replace(" ", "_")
    filename = f"{safe_title}.ics"

    ics_content = generate_ics(export_data, link)
    return Response(
        ics_content,
        mimetype="text/calendar; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@trips_bp.get("/api/trips/<link>/calendar-subscribe-url")
@require_auth
def calendar_subscribe_url(link: str):
    """Return a webcal:// subscribe URL for this trip.

    Owner-only: only the owner gets to hand out a subscription token
    (for now). The URL contains a token that the unauthenticated
    /calendar.ics endpoint validates. Calendar apps interpret webcal://
    as "subscribe and poll for updates."
    """
    owner_id = db.get_trip_owner(link)
    if owner_id is None or owner_id != g.user_id:
        return json_err("Not found", status=404)

    token = calendar_subscribe_token(g.user_id, link)
    # webcal:// is the same as http(s):// but tells the OS to hand the URL
    # to the default calendar app instead of opening it in a browser.
    base = (
        request.host_url.rstrip("/")
        .replace("http://", "webcal://")
        .replace("https://", "webcal://")
    )
    url = f"{base}/api/trips/{link}/calendar.ics?token={token}"
    return json_ok({"url": url})


@trips_bp.get("/api/calendar/subscribe-url")
@require_auth
def user_calendar_subscribe_url():
    """Return a webcal:// URL for the user's all-trips calendar feed.

    The feed covers all published (non-draft) trips that have dates.
    Uses a user-scoped HMAC token so calendar apps can poll without a session.
    """
    token = user_calendar_token(g.user_id)
    base = (
        request.host_url.rstrip("/")
        .replace("http://", "webcal://")
        .replace("https://", "webcal://")
    )
    url = f"{base}/api/calendar/all.ics?user_id={g.user_id}&token={token}"
    return json_ok({"url": url})


@trips_bp.get("/api/calendar/all.ics")
def user_calendar_feed():
    """Serve all published trips with dates as a single .ics feed.

    Unauthenticated: validated by a user-scoped HMAC token (same pattern as
    the per-trip subscribe URL). Calendar apps poll this URL periodically.
    """
    from flask import Response

    try:
        user_id = int(request.args.get("user_id", ""))
    except (ValueError, TypeError):
        return json_err("Missing user_id", status=400)

    token = request.args.get("token", "").strip()
    if not token or not verify_user_calendar_token(user_id, token):
        return json_err("Invalid token", status=403)

    trips = db.get_published_trips_with_dates(user_id)
    ics_content = generate_ics_multi(trips)
    return Response(
        ics_content,
        mimetype="text/calendar; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="libertas-trips.ics"'},
    )


@trips_bp.get("/api/trip/<link>/can-edit")
@require_auth
def can_edit_trip(link: str):
    owner_id = db.get_trip_owner(link)
    if owner_id is None:
        return json_err("Trip not found", status=404)
    return json_ok({"canEdit": owner_id == g.user_id})


@trips_bp.get("/api/map-status")
@require_auth
def map_status():
    link = request.args.get("link", "").strip()
    if not link:
        return json_err("Missing 'link' parameter")

    trip = db.get_trip_by_link(g.user_id, link)
    if not trip:
        return json_err("Trip not found", status=404)

    return json_ok(
        {
            "link": link,
            "map_status": trip.get("map_status", "ready"),
            "map_error": trip.get("map_error"),
            "queue_size": geocoding_worker.get_queue_size(),
        }
    )


@trips_bp.post("/api/trips/create")
@require_auth
def create_trip():
    data = request.get_json(silent=True) or {}
    result, status = create_handler.create_trip_handler(g.user_id, data)
    if status == 200:
        return json_ok(result)
    return json_err(result.get("error", "Unknown error"), status=status)


@trips_bp.post("/api/trips/<link>/save")
@require_auth
def save_trip(link: str):
    data = request.get_json(silent=True) or {}
    result, status = create_handler.save_trip_handler(g.user_id, link, data)
    if status == 200:
        return json_ok(result)
    return json_err(result.get("error", "Unknown error"), status=status)


@trips_bp.post("/api/trips/<link>/publish")
@require_auth
def publish_trip(link: str):
    result, status = create_handler.publish_trip_handler(g.user_id, link)
    if status == 200:
        return json_ok(result)
    return json_err(result.get("error", "Unknown error"), status=status)


@trips_bp.post("/api/trips/clone-ideas")
@require_auth
def clone_ideas():
    """Copy all ideas from a public source trip into a target trip."""
    from agents.trips.handler import clone_ideas_between_trips

    data = request.get_json(silent=True) or {}
    result, status = clone_ideas_between_trips(
        g.user_id,
        data.get("source_link", "").strip(),
        data.get("target_link", "").strip(),
    )
    if status == 200:
        return json_ok({"success": True, **result})
    return json_err(result.get("error", "Unknown error"), status=status)


@trips_bp.post("/api/trips/<link>/items")
@require_auth
def add_trip_item(link: str):
    data = request.get_json(silent=True) or {}
    result, status = create_handler.add_item_to_trip_handler(g.user_id, link, data)
    if status == 200:
        return json_ok(result)
    return json_err(result.get("error", "Unknown error"), status=status)


@trips_bp.post("/api/delete-trip")
@require_auth
def delete_trip():
    data = request.get_json(silent=True) or {}
    link = data.get("link", "").strip()
    if not link:
        return json_err("No trip link provided")

    deleted = db.delete_trip(g.user_id, link)
    if not deleted:
        return json_err("Trip not found")

    html_file = OUTPUT_DIR / link
    if html_file.exists():
        os.unlink(html_file)

    return json_ok({"success": True, "message": "Trip deleted successfully"})


@trips_bp.post("/api/copy-trip")
@require_auth
def copy_trip():
    data = request.get_json(silent=True) or {}
    link = data.get("link", "").strip()
    if not link:
        return json_err("No trip link provided")

    try:
        result = db.copy_trip_by_link(link, g.user_id)
        if not result:
            return json_err("Trip not found")

        new_link = result.get("new_link")
        was_copied = result.get("was_copied", True)

        if was_copied and new_link:
            new_trip = db.get_trip_by_link(g.user_id, new_link)
            if new_trip and new_trip.get("itinerary_data"):
                from agents.create.handler import _convert_to_itinerary
                from agents.itinerary.web_view import ItineraryWebView

                itinerary = _convert_to_itinerary(
                    {"itinerary_data": new_trip["itinerary_data"], "title": new_trip["title"]}
                )
                if itinerary and itinerary.items:
                    web_view = ItineraryWebView()
                    web_view.generate(
                        itinerary, OUTPUT_DIR / new_link, use_ai_summary=False, skip_geocoding=True
                    )

        return json_ok(
            {
                "success": True,
                "new_link": new_link,
                "was_copied": was_copied,
                "message": "Trip copied to your trips"
                if was_copied
                else "You already own this trip",
            }
        )
    except Exception as e:
        traceback.print_exc()
        return json_err(str(e))


@trips_bp.post("/api/rename-trip")
@require_auth
def rename_trip():
    data = request.get_json(silent=True) or {}
    link = data.get("link", "").strip()
    new_title = data.get("newTitle", "").strip()
    if not link:
        return json_err("No trip link provided")
    if not new_title:
        return json_err("No new title provided")

    updated = db.update_trip(g.user_id, link, {"title": new_title})
    if not updated:
        return json_err("Trip not found")
    return json_ok({"success": True, "message": f"Trip renamed to '{new_title}'"})


@trips_bp.post("/api/update-trip")
@require_auth
def update_trip():
    data = request.get_json(silent=True) or {}
    link = data.get("link", "").strip()
    if not link:
        return json_err("No trip link provided")

    updates = {}
    if data.get("title"):
        updates["title"] = data["title"]
    if data.get("dates"):
        updates["dates"] = data["dates"]
    if "days" in data:
        updates["days"] = int(data["days"])
    if "locations" in data:
        updates["locations"] = int(data["locations"])
    if "activities" in data:
        updates["activities"] = int(data["activities"])

    if not updates:
        return json_err("No fields to update")

    updated = db.update_trip(g.user_id, link, updates)
    if not updated:
        return json_err("Trip not found")
    return json_ok({"success": True, "message": "Trip updated successfully"})


@trips_bp.post("/api/retry-geocoding")
@require_auth
def retry_geocoding():
    """Recompute the map for a trip, used by the "Regen Map" button."""
    from agents.trips.handler import regenerate_trip_map

    data = request.get_json(silent=True) or {}
    link = data.get("link", "").strip()
    if not link:
        return json_err("No trip link provided")

    result, status = regenerate_trip_map(g.user_id, link)
    if status == 200:
        return json_ok({"success": True, **result})
    return json_err(result.get("error", "Unknown error"), status=status)


@trips_bp.post("/api/share-trip")
@require_auth
def share_trip():
    data = request.get_json(silent=True) or {}
    link = data.get("link", "").strip()
    target_user_id = data.get("targetUserId")
    share_with_all = data.get("shareWithAll", False)

    if not link:
        return json_err("No trip link provided")

    try:
        if share_with_all:
            shared_count = db.share_trip_with_all(g.user_id, link)
            return json_ok(
                {
                    "success": True,
                    "message": f"Trip shared with {shared_count} users",
                    "sharedCount": shared_count,
                }
            )
        elif target_user_id:
            result = db.copy_trip_to_user(g.user_id, link, target_user_id)
            if result:
                return json_ok({"success": True, "message": "Trip shared successfully"})
            return json_err("Failed to share trip")
        else:
            return json_err("No target user specified")
    except Exception as e:
        traceback.print_exc()
        return json_err(str(e))


@trips_bp.post("/api/toggle-public")
@require_auth
def toggle_public():
    data = request.get_json(silent=True) or {}
    link = data.get("link", "").strip()
    is_public = data.get("isPublic", False)

    if not link:
        return json_err("No trip link provided")

    try:
        updated = db.set_trip_public(g.user_id, link, is_public)
        if updated:
            return json_ok(
                {
                    "success": True,
                    "message": f"Trip {'made public' if is_public else 'made private'}",
                    "isPublic": is_public,
                }
            )
        return json_err("Trip not found")
    except Exception as e:
        traceback.print_exc()
        return json_err(str(e))


@trips_bp.get("/api/trips/<path:link>/card-icon")
@require_auth
def card_icon(link: str):
    """Return the trip's card icon (LLM-picked, cached in itinerary_data)."""
    from agents.trips.handler import get_card_icon

    result, status = get_card_icon(g.user_id, link)
    if status == 200:
        return json_ok(result)
    return json_err(result.get("error", "Unknown error"), status=status)


@trips_bp.post("/api/toggle-archived")
@require_auth
def toggle_archived():
    """Archive or un-archive a trip. Independent of is_public."""
    data = request.get_json(silent=True) or {}
    link = data.get("link", "").strip()
    is_archived = data.get("isArchived", False)

    if not link:
        return json_err("No trip link provided")

    try:
        updated = db.set_trip_archived(g.user_id, link, is_archived)
        if updated:
            return json_ok(
                {
                    "success": True,
                    "message": f"Trip {'archived' if is_archived else 'unarchived'}",
                    "isArchived": is_archived,
                }
            )
        return json_err("Trip not found")
    except Exception as e:
        traceback.print_exc()
        return json_err(str(e))


@trips_bp.post("/api/users")
@require_auth
def get_users():
    try:
        users = db.get_all_users()
        users = [u for u in users if u["id"] != g.user_id]
        return json_ok({"success": True, "users": users})
    except Exception as e:
        traceback.print_exc()
        return json_err(str(e))


@trips_bp.post("/api/trips/<link>/writeup")
@require_auth
def generate_trip_writeup(link: str):
    """Generate an AI narrative write-up from trip ideas and tips."""
    from agents.trips.handler import generate_writeup_for_trip

    result, status = generate_writeup_for_trip(g.user_id, link)
    if status == 200:
        return json_ok({"success": True, **result})
    return json_err(result.get("error", "Unknown error"), status=status)


@trips_bp.post("/api/trips/<link>/fill-links")
@require_auth
def fill_trip_links(link: str):
    """Use LLM to find and fill missing website/maps links for trip items."""
    from agents.trips.handler import fill_links_for_trip

    result, status = fill_links_for_trip(g.user_id, link)
    if status == 200:
        return json_ok({"success": True, **result})
    return json_err(result.get("error", "Unknown error"), status=status)


@trips_bp.get("/api/user/me")
def get_current_user():
    """Return minimal current user info for client-side analytics identification."""
    if not g.user_id:
        return json_ok({"user_id": None})
    return json_ok({"user_id": g.user_id})


@trips_bp.get("/api/user/profile")
@require_auth
def get_user_profile_api():
    """Get user profile data."""
    profile = db.get_user_profile(g.user_id)
    return json_ok({"profile": profile or {}})


@trips_bp.post("/api/user/extract-style")
@require_auth
def extract_writing_style():
    """Extract writing style from user-provided samples and store it."""
    from agents.trips.handler import extract_user_writing_style

    data = request.get_json(silent=True) or {}
    result, status = extract_user_writing_style(g.user_id, data.get("samples", "").strip())
    if status == 200:
        return json_ok({"success": True, **result})
    return json_err(result.get("error", "Unknown error"), status=status)


@trips_bp.post("/api/user/save-profile")
@require_auth
def save_user_profile():
    """Save user profile data (style profile, preferences)."""
    data = request.get_json(silent=True) or {}
    style_profile = data.get("style_profile")
    writing_samples = data.get("writing_samples", "")
    samples_preview = data.get("samples_preview", "")
    user_notes = data.get("user_notes", "")

    if not style_profile:
        return json_err("No profile data provided")

    existing_profile = db.get_user_profile(g.user_id) or {}
    existing_profile["style_profile"] = style_profile
    if writing_samples:
        existing_profile["writing_samples"] = writing_samples
    existing_profile["samples_preview"] = samples_preview
    existing_profile["user_notes"] = user_notes
    db.set_user_profile(g.user_id, existing_profile)

    return json_ok({"success": True})
