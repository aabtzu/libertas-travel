"""Import URL blueprint - handles Web Share Target and direct URL imports."""

from __future__ import annotations

from flask import Blueprint, Response, g, redirect, render_template, request

import database as db
from agents.common.flask_utils import require_auth
from agents.import_url.handler import (
    add_items_to_trip,
    fetch_and_extract,
    get_user_trips_for_picker,
)

import_url_bp = Blueprint("import_url", __name__, template_folder="templates")


def _render_import_page(
    url: str,
    title: str,
    trips: list[dict],
    error: str | None = None,
    success_msg: str | None = None,
    items: list[dict] | None = None,
) -> str:
    url_display = url[:80] + "..." if len(url) > 80 else url
    return render_template(
        "import.html",
        url=url,
        url_display=url_display,
        title=title,
        trips=trips,
        error=error,
        success_msg=success_msg,
        items=items or [],
    )


@import_url_bp.get("/import")
@require_auth
def import_get():
    """Show the import page. Receives ?url= from Web Share Target or direct link."""
    url = request.args.get("url") or request.args.get("text") or ""
    title = request.args.get("title") or ""

    # text param may contain the URL when sharing from some apps
    if not url.startswith("http") and request.args.get("text", "").startswith("http"):
        url = request.args.get("text", "")

    if not url:
        return Response(
            _render_import_page(
                "", "", [], error="No URL provided. Share a page from your browser."
            ),
            mimetype="text/html",
        )

    trips = get_user_trips_for_picker(g.user_id)
    return Response(_render_import_page(url, title, trips), mimetype="text/html")


@import_url_bp.post("/import")
@require_auth
def import_post():
    """Fetch the URL, extract items, and add them to the chosen trip."""
    url = request.form.get("url", "").strip()
    page_title = request.form.get("page_title", "").strip()
    trip_link = request.form.get("trip_link", "").strip()
    user_id = g.user_id

    trips = get_user_trips_for_picker(user_id)

    if not url:
        return Response(
            _render_import_page("", "", trips, error="Missing URL."),
            mimetype="text/html",
        )
    if not trip_link:
        return Response(
            _render_import_page(url, page_title, trips, error="Please choose a trip."),
            mimetype="text/html",
        )

    # Fetch and extract items from the URL
    result = fetch_and_extract(url)
    if not result["success"]:
        return Response(
            _render_import_page(url, page_title, trips, error=result["error"]),
            mimetype="text/html",
        )

    items = result["items"]
    actual_title = result["title"] or page_title

    if not items:
        return Response(
            _render_import_page(
                url,
                actual_title,
                trips,
                error="No trip items could be extracted from this page. Try a different URL.",
            ),
            mimetype="text/html",
        )

    # Create new draft trip if requested
    if trip_link == "__new__":
        trip_title = actual_title or "Imported from web"
        new_trip = db.create_draft_trip(user_id=user_id, title=trip_title)
        if not new_trip:
            return Response(
                _render_import_page(url, actual_title, trips, error="Could not create draft trip."),
                mimetype="text/html",
            )
        trip_link = new_trip["link"]

    ok = add_items_to_trip(user_id, trip_link, items, url, actual_title)
    if not ok:
        return Response(
            _render_import_page(
                url, actual_title, trips, error="Could not save items. Trip not found."
            ),
            mimetype="text/html",
        )

    n = len(items)
    return redirect(f"/{trip_link}?imported={n}")
