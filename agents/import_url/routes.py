"""Import URL blueprint - handles Web Share Target and direct URL imports."""

from __future__ import annotations

from flask import Blueprint, Response, g, redirect, request

import database as db
from agents.common.flask_utils import require_auth
from agents.import_url.handler import (
    add_items_to_trip,
    fetch_and_extract,
    get_user_trips_for_picker,
)

import_url_bp = Blueprint("import_url", __name__)


def _render_import_page(
    url: str,
    title: str,
    trips: list[dict],
    error: str | None = None,
    success_msg: str | None = None,
    items: list[dict] | None = None,
) -> str:
    trips_options = "\n".join(f'<option value="{t["link"]}">{t["title"]}</option>' for t in trips)
    items_preview = ""
    if items:
        rows = ""
        for item in items[:20]:
            cat = item.get("category") or "other"
            item_title = item.get("title") or "(untitled)"
            rows += (
                f'<li class="import-item"><span class="import-cat">{cat}</span> {item_title}</li>\n'
            )
        if len(items) > 20:
            rows += f'<li class="import-item import-more">...and {len(items) - 20} more</li>'
        items_preview = f'<ul class="import-items-list">{rows}</ul>'

    error_block = f'<div class="import-error">{error}</div>' if error else ""
    success_block = f'<div class="import-success">{success_msg}</div>' if success_msg else ""

    url_display = url[:80] + "..." if len(url) > 80 else url

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Import - Libertas</title>
    <link rel="icon" type="image/svg+xml" href="/static/favicon.svg">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
    <link rel="stylesheet" href="/static/css/main.css?v=14">
    <link rel="stylesheet" href="/static/css/import.css?v=1">
</head>
<body class="import-body">
    <div class="import-container">
        <div class="import-header">
            <a href="/trips.html" class="import-back"><i class="fas fa-arrow-left"></i></a>
            <div class="import-brand">
                <i class="fas fa-feather-alt"></i>
                <span>Import</span>
            </div>
        </div>

        <div class="import-card">
            <div class="import-source">
                <i class="fas fa-link"></i>
                <span class="import-url" title="{url}">{url_display}</span>
            </div>
            {f'<div class="import-page-title">{title}</div>' if title and title != url else ""}
        </div>

        {error_block}
        {success_block}

        {
        f'''<div class="import-preview">
            <div class="import-preview-label"><i class="fas fa-list"></i> {len(items)} item{"s" if len(items) != 1 else ""} found</div>
            {items_preview}
        </div>'''
        if items
        else ""
    }

        <form class="import-form" method="POST" action="/import">
            <input type="hidden" name="url" value="{url}">
            <input type="hidden" name="page_title" value="{title}">

            <div class="import-field">
                <label for="trip_link">Add to trip</label>
                <select name="trip_link" id="trip_link" required>
                    <option value="">-- choose a trip --</option>
                    <option value="__new__">+ New draft trip</option>
                    {trips_options}
                </select>
            </div>

            <button type="submit" class="import-btn">
                <i class="fas fa-plus"></i>
                Add to trip
            </button>
        </form>
    </div>
</body>
</html>"""


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
