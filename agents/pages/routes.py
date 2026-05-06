"""Pages blueprint: HTML page routes for the Libertas UI."""

from __future__ import annotations

import os

from flask import Blueprint, Response, g, redirect

import database as db
from agents.common.flask_utils import require_auth
from agents.common.templates import (
    generate_about_page,
    generate_home_page,
    generate_how_it_works_page,
    generate_login_page,
    generate_register_page,
    get_nav_html,
)
from agents.explore.templates import generate_explore_page
from agents.itinerary import geocoding_worker
from agents.itinerary.templates import generate_trips_page
from agents.pages.profile_view import generate_profile_page
from agents.pages.recommendation_view import generate_recommendation_page

pages_bp = Blueprint("pages", __name__)


def _html(content: str) -> Response:
    return Response(content, mimetype="text/html")


# Status used for "trip exists but is no longer publicly shared." 410 Gone is
# the right semantic: the resource was here, the owner pulled it. 404 would
# have implied it never existed.
_PRIVATE_TRIP_STATUS = 410


def _trip_not_available_response(link: str, reason: str) -> Response:
    """Render a friendly "this trip isn't available" page.

    Two reasons handled:
      - "missing": the link doesn't match any trip in the DB.
      - "private": a trip with that link exists but isn't public, and the
        viewer isn't logged in as the owner.

    The previous behavior was a bare 404 string, which made shared links
    look broken when in fact the owner had just toggled the trip private.
    """
    is_private = reason == "private"
    title = "This trip isn't public" if is_private else "Trip not found"
    headline = (
        "This trip isn't shared publicly anymore."
        if is_private
        else "We couldn't find a trip at this link."
    )
    detail = (
        "If you're the trip owner, log in and toggle the lock icon on the trip "
        "card to share it again."
        if is_private
        else "The link may be mistyped, or the trip may have been deleted."
    )
    nav = get_nav_html(active_page="")
    body = f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="UTF-8"><title>{title} - Libertas</title>
<link rel="icon" type="image/svg+xml" href="/static/favicon.svg">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
<link rel="stylesheet" href="/static/css/main.css?v=14">
<style>
.unavailable {{ max-width: 560px; margin: 80px auto; padding: 40px 32px; background: #fff;
  border-radius: 12px; box-shadow: 0 2px 20px rgba(0,0,0,0.08); text-align: center; }}
.unavailable i {{ font-size: 3rem; color: #667eea; margin-bottom: 16px; }}
.unavailable h1 {{ font-size: 1.4rem; color: #1a1a2e; margin: 0 0 12px; }}
.unavailable p {{ color: #555; line-height: 1.5; margin: 0 0 14px; }}
.unavailable .actions {{ margin-top: 24px; display: flex; gap: 12px; justify-content: center; }}
.unavailable .btn {{ display: inline-flex; align-items: center; gap: 6px; padding: 10px 18px;
  background: #667eea; color: #fff; border-radius: 8px; text-decoration: none; font-size: 0.95rem; }}
.unavailable .btn.secondary {{ background: #f0f1ff; color: #4a5fd6; }}
.unavailable .btn:hover {{ filter: brightness(0.95); }}
.unavailable .link-tag {{ font-family: monospace; font-size: 0.85rem; color: #888;
  background: #f5f5f5; padding: 4px 8px; border-radius: 4px; word-break: break-all; }}
</style></head><body>
{nav}
<div class="unavailable">
<i class="fas fa-{"lock" if is_private else "compass"}"></i>
<h1>{headline}</h1>
<p>{detail}</p>
<p><span class="link-tag">{link}</span></p>
<div class="actions">
<a href="/" class="btn">Home</a>
<a href="/trips.html" class="btn secondary">My trips</a>
</div>
</div>
</body></html>"""
    return Response(body, mimetype="text/html", status=_PRIVATE_TRIP_STATUS if is_private else 404)


@pages_bp.get("/")
@pages_bp.get("/index.html")
def home():
    return _html(generate_home_page())


@pages_bp.get("/how-it-works")
def how_it_works():
    return _html(generate_how_it_works_page())


@pages_bp.get("/about")
@pages_bp.get("/about.html")
def about():
    return _html(generate_about_page())


@pages_bp.get("/explore")
@pages_bp.get("/explore.html")
def explore():
    google_maps_api_key = os.environ.get("GOOGLE_MAPS_API_KEY", "")
    return _html(generate_explore_page(google_maps_api_key))


@pages_bp.get("/login")
@pages_bp.get("/login.html")
def login():
    # In dev (AUTH_DISABLED=true) every request gets a fake user_id, which
    # would otherwise redirect away from the auth pages and make them
    # unreachable for previewing.
    if g.user_id and not g.auth_disabled:
        return redirect("/")
    return _html(generate_login_page())


@pages_bp.get("/register")
@pages_bp.get("/register.html")
def register():
    if g.user_id and not g.auth_disabled:
        return redirect("/")
    return _html(generate_register_page())


@pages_bp.get("/profile")
@require_auth
def profile():
    profile_data = db.get_user_profile(g.user_id) or {}

    return _html(generate_profile_page(profile_data))


@pages_bp.get("/trips")
@pages_bp.get("/trips.html")
@require_auth
def trips():
    user_trips = db.get_user_trips(g.user_id)
    public_trips = db.get_public_trips(exclude_user_id=g.user_id)
    return _html(generate_trips_page(user_trips, public_trips))


@pages_bp.get("/create")
@pages_bp.get("/create.html")
@require_auth
def create():
    from pathlib import Path

    template_path = Path(__file__).parent.parent / "create" / "templates" / "create.html"
    if not template_path.exists():
        return "Create page template not found", 404
    html = template_path.read_text().format(nav_html=get_nav_html(""))
    return _html(html)


@pages_bp.get("/<path:trip_name>.html")
def trip_html(trip_name: str):
    """Serve trip HTML dynamically from database."""
    if ".." in trip_name:
        return "Forbidden", 403

    link = trip_name
    if link.startswith("trip/"):
        link = link[5:]

    # Reserved page names, let 404 fall through; they have dedicated routes above
    reserved = {"index", "about", "how-it-works", "trips", "login", "register", "create", "explore"}
    if link in reserved:
        return "Not found", 404

    # DB stores links with .html suffix (e.g. "cycling_worlds_sep_2026.html")
    # but the URL route strips it via the /<path:trip_name>.html pattern
    if not link.endswith(".html"):
        link = link + ".html"

    user_id = g.user_id
    trip = None
    owner_id = None  # always defined so we can use it for is_owner check below

    if user_id:
        trip = db.get_trip_by_link(user_id, link)

    if not trip:
        owner_id = db.get_trip_owner(link)
        if owner_id and db.is_trip_public(link):
            trip = db.get_trip_by_link(owner_id, link)

    if not trip:
        # Distinguish "trip never existed" from "trip exists but is private now"
        # so a stale shared link gets a friendly explanation, not a hard 404.
        existing_owner = owner_id or db.get_trip_owner(link)
        reason = "private" if existing_owner else "missing"
        return _trip_not_available_response(link, reason)

    # Determine viewer context, used by web_view to render the right header buttons
    is_authenticated = user_id is not None
    trip_owner_id = owner_id or db.get_trip_owner(link)
    is_owner = is_authenticated and (user_id == trip_owner_id)

    itinerary_data = trip.get("itinerary_data")
    if not itinerary_data:
        return "Trip has no itinerary data", 404

    # Recommendation trips (ideas-only, no days) render via the recommendation view.
    # The day-by-day view can't show them and its map-status polling would infinite-loop.
    if trip.get("trip_type") == "recommendation":
        return _html(
            generate_recommendation_page(
                trip.get("title", "Recommendations"), itinerary_data, trip_link=link
            )
        )

    from agents.itinerary.geocoding_worker import (
        _convert_itinerary_data_to_worker_format,
        deserialize_itinerary,
    )
    from agents.itinerary.web_view import ItineraryWebView

    worker_format = _convert_itinerary_data_to_worker_format(itinerary_data, trip.get("title"))
    if not worker_format:
        return "Could not convert trip data", 500

    itinerary = deserialize_itinerary(worker_format)
    map_data = itinerary_data.get("map_data")

    # Self-heal stuck trips: if status was advanced to "ready" but map_data
    # is missing, the trip is in the bad state that previously caused the
    # client-side reload loop. Reset to "pending" and queue a regen so the
    # background worker computes map_data; the page renders with the
    # spinner and JS polling drives a single reload when it flips to
    # ready. No manual /api/admin/retry-geocoding needed.
    if not map_data and trip.get("map_status") == "ready":
        # Use the trip owner's user_id, not the visitor's, the visitor
        # may be anonymous viewing a public trip.
        owner = trip_owner_id or db.get_trip_owner(link)
        if owner:
            db.update_trip_map_status(owner, link, "pending", None)
            geocoding_worker.queue_geocoding(link, itinerary)
            print(f"[SELF-HEAL] Queued regen for stuck trip {link!r}", flush=True)

    # Use the per-trip icon picked by the LLM (cached on the trips page);
    # fall back to "plane" if it hasn't been computed yet.
    card_icon = itinerary_data.get("card_icon") or "plane"
    web_view = ItineraryWebView()
    html = web_view.render_html(
        itinerary,
        map_data,
        is_owner=is_owner,
        is_authenticated=is_authenticated,
        trip_link=link,
        card_icon=card_icon,
    )
    return _html(html)


@pages_bp.get("/r/<path:rec_name>.html")
@pages_bp.get("/r/<path:rec_name>")
def recommendation_view(rec_name: str):
    """Public recommendation view, no login required."""
    link = rec_name
    if not link.endswith(".html"):
        link = link + ".html"

    # Find the trip by link (any owner)
    owner_id = db.get_trip_owner(link)
    if owner_id is None:
        return _trip_not_available_response(link, "missing")

    trip = db.get_trip_by_link(owner_id, link)
    if not trip:
        return _trip_not_available_response(link, "missing")

    if not trip.get("is_public"):
        return _trip_not_available_response(link, "private")

    itinerary_data = trip.get("itinerary_data") or {}
    if isinstance(itinerary_data, str):
        import json

        itinerary_data = json.loads(itinerary_data)

    html = generate_recommendation_page(
        trip.get("title", "Recommendations"), itinerary_data, trip_link=link
    )
    return _html(html)


@pages_bp.get("/w/<path:rec_name>.html")
@pages_bp.get("/w/<path:rec_name>")
def writeup_view(rec_name: str):
    """Public write-up view, AI-generated narrative recommendation."""
    link = rec_name
    if not link.endswith(".html"):
        link = link + ".html"

    owner_id = db.get_trip_owner(link)
    if owner_id is None:
        return _trip_not_available_response(link, "missing")

    trip = db.get_trip_by_link(owner_id, link)
    if not trip:
        return _trip_not_available_response(link, "missing")
    if not trip.get("is_public"):
        return _trip_not_available_response(link, "private")

    itinerary_data = trip.get("itinerary_data") or {}
    if isinstance(itinerary_data, str):
        import json

        itinerary_data = json.loads(itinerary_data)

    # Check for cached write-up first
    writeup_text = itinerary_data.get("writeup", "")

    if not writeup_text:
        # Generate on the fly, use owner's style profile if available
        try:
            from agents.trips.writeup import generate_writeup

            style_profile = None
            writing_samples = ""
            owner_profile = db.get_user_profile(owner_id)
            if owner_profile:
                style_profile = owner_profile.get("style_profile")
                writing_samples = owner_profile.get("writing_samples", "")

            writeup_text = generate_writeup(
                trip.get("title", "Recommendations"),
                itinerary_data,
                style_profile=style_profile,
                writing_samples=writing_samples,
            )
        except Exception as e:
            # Log the actual cause, silently swallowing made debugging painful
            import traceback

            traceback.print_exc()
            writeup_text = f"Write-up generation failed: {e}"

    from agents.pages.recommendation_view import render_writeup_page

    html = render_writeup_page(
        trip.get("title", "Recommendations"),
        writeup_text,
        itinerary_data=itinerary_data,
        trip_link=link,
    )
    return _html(html)
