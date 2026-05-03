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
from agents.itinerary.templates import generate_trips_page
from agents.pages.profile_view import generate_profile_page
from agents.pages.recommendation_view import generate_recommendation_page

pages_bp = Blueprint("pages", __name__)


def _html(content: str) -> Response:
    return Response(content, mimetype="text/html")


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

    # Reserved page names — let 404 fall through; they have dedicated routes above
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
        return "Trip not found", 404

    # Determine viewer context — used by web_view to render the right header buttons
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

    from agents.itinerary.web_view import ItineraryWebView
    from geocoding_worker import _convert_itinerary_data_to_worker_format, deserialize_itinerary

    worker_format = _convert_itinerary_data_to_worker_format(itinerary_data, trip.get("title"))
    if not worker_format:
        return "Could not convert trip data", 500

    itinerary = deserialize_itinerary(worker_format)
    map_data = itinerary_data.get("map_data")
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
    """Public recommendation view — no login required."""
    link = rec_name
    if not link.endswith(".html"):
        link = link + ".html"

    # Find the trip by link (any owner)
    owner_id = db.get_trip_owner(link)
    if owner_id is None:
        return "Not found", 404

    trip = db.get_trip_by_link(owner_id, link)
    if not trip:
        return "Not found", 404

    # Must be public
    if not trip.get("is_public"):
        return "Not found", 404

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
    """Public write-up view — AI-generated narrative recommendation."""
    link = rec_name
    if not link.endswith(".html"):
        link = link + ".html"

    owner_id = db.get_trip_owner(link)
    if owner_id is None:
        return "Not found", 404

    trip = db.get_trip_by_link(owner_id, link)
    if not trip or not trip.get("is_public"):
        return "Not found", 404

    itinerary_data = trip.get("itinerary_data") or {}
    if isinstance(itinerary_data, str):
        import json

        itinerary_data = json.loads(itinerary_data)

    # Check for cached write-up first
    writeup_text = itinerary_data.get("writeup", "")

    if not writeup_text:
        # Generate on the fly — use owner's style profile if available
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
            # Log the actual cause — silently swallowing made debugging painful
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
