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
    if g.user_id:
        return redirect("/")
    return _html(generate_login_page())


@pages_bp.get("/register")
@pages_bp.get("/register.html")
def register():
    if g.user_id:
        return redirect("/")
    return _html(generate_register_page())


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
        if owner_id:
            with db.get_db() as conn:
                cursor = conn.cursor()
                if db.USE_POSTGRES:
                    cursor.execute("SELECT is_public FROM trips WHERE link = %s", (link,))
                else:
                    cursor.execute("SELECT is_public FROM trips WHERE link = ?", (link,))
                row = cursor.fetchone()
                if row and row[0]:
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

    from agents.itinerary.web_view import ItineraryWebView
    from geocoding_worker import _convert_itinerary_data_to_worker_format, deserialize_itinerary

    worker_format = _convert_itinerary_data_to_worker_format(itinerary_data, trip.get("title"))
    if not worker_format:
        return "Could not convert trip data", 500

    itinerary = deserialize_itinerary(worker_format)
    map_data = itinerary_data.get("map_data")
    web_view = ItineraryWebView()
    html = web_view.render_html(
        itinerary, map_data,
        is_owner=is_owner,
        is_authenticated=is_authenticated,
        trip_link=link,
    )
    return _html(html)
