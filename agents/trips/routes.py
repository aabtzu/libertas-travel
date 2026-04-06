"""Trips blueprint: trip CRUD, export, calendar, sharing, geocoding, map status."""

from __future__ import annotations

import json
import os
import re
import traceback
from pathlib import Path

import database as db
import geocoding_worker
from agents.common.flask_utils import json_err, json_ok, require_auth
from agents.create import handler as create_handler
from agents.trips.ics import generate_ics
from flask import Blueprint, g, jsonify, request, send_file

trips_bp = Blueprint("trips", __name__)

OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", Path(__file__).parent.parent.parent / "output"))


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
@require_auth
def export_ics(link: str):
    result, status = create_handler.export_trip_handler(g.user_id, link)
    if status != 200:
        return json_err(result.get("error", "Unknown error"), status=status)

    export_data = result.get("export", {})
    title = export_data.get("title", "trip")
    safe_title = re.sub(r"[^\w\s-]", "", title).strip().replace(" ", "_")
    filename = f"{safe_title}.ics"

    ics_content = generate_ics(export_data, link)
    from flask import Response

    return Response(
        ics_content,
        mimetype="text/calendar; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
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
                "message": "Trip copied to your trips" if was_copied else "You already own this trip",
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
    data = request.get_json(silent=True) or {}
    link = data.get("link", "").strip()
    if not link:
        return json_err("No trip link provided")

    trip = db.get_trip_by_link(g.user_id, link)
    if not trip:
        return json_err("Trip not found")

    itinerary_data = trip.get("itinerary_data")
    if not itinerary_data:
        return json_err("No itinerary data available for this trip")

    if isinstance(itinerary_data, str):
        try:
            itinerary_data = json.loads(itinerary_data)
        except (json.JSONDecodeError, ValueError):
            return json_err("Invalid itinerary data format")

    if "map_data" in itinerary_data:
        del itinerary_data["map_data"]
        db.update_trip_itinerary_data(g.user_id, link, itinerary_data)

    from agents.create.handler import _convert_to_itinerary
    from agents.itinerary.mapper import ItineraryMapper

    itinerary = _convert_to_itinerary({"itinerary_data": itinerary_data, "title": trip.get("title", "Trip")})
    if not itinerary:
        return json_err("Could not parse itinerary data")

    db.update_trip_map_status(g.user_id, link, "processing", None)
    try:
        mapper = ItineraryMapper()
        map_data = mapper.create_map_data(itinerary)
        itinerary_data["map_data"] = map_data
        db.update_trip_itinerary_data(g.user_id, link, itinerary_data)
        db.update_trip_map_status(g.user_id, link, "ready", None)
        markers_count = len(map_data.get("markers", []))
        return json_ok({"success": True, "message": f"Map regenerated with {markers_count} locations."})
    except Exception as e:
        traceback.print_exc()
        db.update_trip_map_status(g.user_id, link, "error", str(e))
        return json_err(f"Geocoding failed: {str(e)}")


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
            return json_ok({"success": True, "message": f"Trip shared with {shared_count} users", "sharedCount": shared_count})
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
            return json_ok({"success": True, "message": f"Trip {'made public' if is_public else 'made private'}", "isPublic": is_public})
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
