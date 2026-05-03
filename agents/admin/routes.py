"""Admin blueprint: debug info, trip regeneration, venue management."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from flask import Blueprint, g, request

import database as db
from agents.common.flask_utils import json_err, json_ok, require_auth

admin_bp = Blueprint("admin", __name__)

OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", Path(__file__).parent.parent.parent / "output"))

_SQL_COUNT_USERS = "SELECT COUNT(*) FROM users"
_SQL_COUNT_TRIPS = "SELECT COUNT(*) FROM trips"
_SQL_LIST_RECENT_TRIPS = (
    "SELECT id, user_id, title, link FROM trips ORDER BY created_at DESC LIMIT 10"
)


@admin_bp.get("/api/debug")
def debug():
    from agents.explore.handler import load_venues

    debug_info: dict = {
        "output_dir": str(OUTPUT_DIR),
        "output_dir_exists": OUTPUT_DIR.exists(),
        "output_dir_is_dir": OUTPUT_DIR.is_dir() if OUTPUT_DIR.exists() else False,
        "env_output_dir": os.environ.get("OUTPUT_DIR", "NOT SET"),
        "env_port": os.environ.get("PORT", "NOT SET"),
        "cwd": os.getcwd(),
    }

    if OUTPUT_DIR.exists():
        try:
            files = list(OUTPUT_DIR.iterdir())
            debug_info["output_files"] = [f.name for f in files if f.is_file()]
            debug_info["output_file_count"] = len([f for f in files if f.is_file()])
        except Exception as e:
            debug_info["output_files_error"] = str(e)

    uploads_dir = OUTPUT_DIR / "uploads"
    if uploads_dir.exists():
        try:
            uploads = list(uploads_dir.iterdir())
            debug_info["uploaded_files"] = [f.name for f in uploads]
            debug_info["uploaded_file_count"] = len(uploads)
        except Exception as e:
            debug_info["uploaded_files_error"] = str(e)

    try:
        result = subprocess.run(
            ["df", "-h", str(OUTPUT_DIR)], capture_output=True, text=True, timeout=5
        )
        debug_info["disk_space"] = result.stdout
    except Exception as e:
        debug_info["disk_space_error"] = str(e)

    try:
        with db.get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(_SQL_COUNT_USERS)
            debug_info["users_count"] = cursor.fetchone()[0]
            cursor.execute(_SQL_COUNT_TRIPS)
            debug_info["trips_count"] = cursor.fetchone()[0]
            cursor.execute(_SQL_LIST_RECENT_TRIPS)
            debug_info["trips"] = [
                {"id": row[0], "user_id": row[1], "title": row[2], "link": row[3]}
                for row in cursor.fetchall()
            ]
    except Exception as e:
        debug_info["trips_error"] = str(e)

    try:
        venues_seed_csv = Path(__file__).parent.parent.parent / "data" / "venues_seed.csv"

        if request.args.get("reimport_venues"):
            import agents.explore.handler as explore_handler
            from agents.explore.handler import _venues_cache as _vc  # noqa: F401

            explore_handler._venues_cache = None
            if venues_seed_csv.exists():
                imported = db.import_venues_from_csv(str(venues_seed_csv), source="curated")
                debug_info["reimport_result"] = f"Imported {imported} venues"
            else:
                debug_info["reimport_result"] = "CSV not found"

        if request.args.get("geocode_missing"):
            from geocode_venues import geocode_address

            venues = load_venues()
            missing = [v for v in venues if not v.get("latitude") or not v.get("longitude")]
            debug_info["geocode_total_missing"] = len(missing)
            geocoded = 0
            failed = 0
            results = []
            import time

            for v in missing[:50]:
                name = v.get("name", "")
                city = v.get("city", "")
                country = v.get("country", "")
                lat, lng = geocode_address(name, city, country)
                if lat and lng:
                    db.update_venue_coordinates(v["id"], lat, lng)
                    geocoded += 1
                    results.append(f"✓ {name}: {lat:.4f}, {lng:.4f}")
                else:
                    lat, lng = geocode_address("", city, country)
                    if lat and lng:
                        db.update_venue_coordinates(v["id"], lat, lng)
                        geocoded += 1
                        results.append(f"✓ {name} (city-level): {lat:.4f}, {lng:.4f}")
                    else:
                        failed += 1
                        results.append(f"✗ {name}: NOT FOUND")
                time.sleep(1.1)

            import agents.explore.handler as explore_handler

            explore_handler._venues_cache = None
            debug_info["geocode_result"] = f"Geocoded {geocoded}, failed {failed}"
            debug_info["geocode_details"] = results

        venue_count = db.get_venue_count()
        debug_info["venue_count"] = venue_count
        debug_info["venues_seed_csv"] = str(venues_seed_csv)
        debug_info["venues_seed_exists"] = venues_seed_csv.exists()

        if venue_count > 0:
            stats = db.get_venue_stats()
            debug_info["venues_by_state"] = dict(list(stats.get("by_state", {}).items())[:15])
            debug_info["venues_by_country"] = stats.get("by_country", {})

    except Exception as e:
        debug_info["venue_error"] = str(e)

    return json_ok(debug_info)


@admin_bp.post("/api/admin/seed")
def seed_demo():
    """Seed (or re-seed) demo trips owned by the system demo user.

    Protected by SECRET_KEY: caller must send ``X-Admin-Key: <SECRET_KEY>``
    header so this endpoint is safe to expose without login.
    """
    import os

    secret_key = os.environ.get("SECRET_KEY", "")
    provided = request.headers.get("X-Admin-Key", "")
    if not secret_key or provided != secret_key:
        return json_err("Unauthorized", status=401)

    force = request.args.get("force", "").lower() in ("1", "true", "yes")
    from agents.admin.handler import seed_demo_trips

    results = seed_demo_trips(force=force)
    return json_ok({"success": True, **results})


@admin_bp.post("/api/admin/retry-geocoding")
def admin_retry_geocoding():
    """Re-geocode a trip by link. Protected by SECRET_KEY (X-Admin-Key header).

    Body JSON: {"link": "paris_provence_adventure.html"}
    """
    import os

    secret_key = os.environ.get("SECRET_KEY", "")
    provided = request.headers.get("X-Admin-Key", "")
    if not secret_key or provided != secret_key:
        return json_err("Unauthorized", status=401)

    from agents.admin.handler import admin_retry_geocoding as _retry

    data = request.get_json(silent=True) or {}
    link = data.get("link", "").strip()
    if not link:
        return json_err("No trip link provided")

    result = _retry(link)
    return json_ok(result)


@admin_bp.post("/api/admin/add-trip")
def admin_add_trip():
    """Create or update a trip for any user. Protected by SECRET_KEY.

    Body JSON: {"username": "...", "title": "...", "link": "...", "itinerary_data": {...}, "trip_type": "...", "is_public": true}
    """
    import os

    secret_key = os.environ.get("SECRET_KEY", "")
    provided = request.headers.get("X-Admin-Key", "")
    if not secret_key or provided != secret_key:
        return json_err("Unauthorized", status=401)

    data = request.get_json(silent=True) or {}
    username = data.get("username", "")
    title = data.get("title", "")
    if not title:
        return json_err("title required")

    # Find user by username
    user = db.get_user_by_username(username) if username else None
    user_id = user["id"] if user else db.ensure_demo_user()

    link = data.get("link", "")
    if not link:
        import re

        link = re.sub(r"[^\w\s-]", "", title).strip().replace(" ", "_").lower() + ".html"

    trip_data = {
        "title": title,
        "link": link,
        "trip_type": data.get("trip_type", "itinerary"),
        "map_status": "pending",
    }

    itinerary_data = data.get("itinerary_data")
    db.add_trip(user_id, trip_data, itinerary_data)

    if data.get("is_public"):
        db.set_trip_public(user_id, link, True)

    return json_ok({"success": True, "link": link, "user_id": user_id})


@admin_bp.post("/api/admin/add-venues")
def admin_add_venues():
    """Bulk-add curated venues. Protected by SECRET_KEY (X-Admin-Key header).

    Body JSON: {"venues": [{"name": "...", "city": "...", ...}, ...]}
    """
    import os

    secret_key = os.environ.get("SECRET_KEY", "")
    provided = request.headers.get("X-Admin-Key", "")
    if not secret_key or provided != secret_key:
        return json_err("Unauthorized", status=401)

    data = request.get_json(silent=True) or {}
    venues = data.get("venues", [])
    if not venues:
        return json_err("No venues provided")

    added = 0
    skipped = 0
    for v in venues:
        existing = db.find_venue_by_name_and_city(v.get("name", ""), v.get("city", ""))
        if existing:
            skipped += 1
            continue
        db.add_venue(v)
        added += 1

    return json_ok({"success": True, "added": added, "skipped": skipped})


@admin_bp.post("/api/regenerate-all-trips")
@require_auth
def regenerate_all_trips():
    from agents.admin.handler import regenerate_all_trip_html

    results = regenerate_all_trip_html(g.user_id)
    return json_ok(
        {
            "success": True,
            "regenerated": results["regenerated"],
            "skipped": results["skipped"],
            "errors": results["errors"],
        }
    )
