"""Generate the shareable recommendation view HTML."""

from __future__ import annotations

import html as html_mod
import re
from typing import Any

from agents.common.categories import CATEGORY_ICONS
from agents.common.templates import get_nav_html


def _esc(text: str) -> str:
    return html_mod.escape(str(text)) if text else ""


def _md_to_html(text: str) -> str:
    """Minimal markdown to HTML: bold, italic, headers, links, line breaks."""
    text = html_mod.escape(text)
    # Headers (order matters — match ### before ## before #)
    text = re.sub(r"^### (.+)$", r"<h3>\1</h3>", text, flags=re.MULTILINE)
    text = re.sub(r"^## (.+)$", r"<h2>\1</h2>", text, flags=re.MULTILINE)
    text = re.sub(r"^# (.+)$", r"<h1>\1</h1>", text, flags=re.MULTILINE)
    # Links: [text](url) → <a>
    text = re.sub(
        r"\[(.+?)\]\((https?://[^\)]+)\)",
        r'<a href="\2" target="_blank" rel="noopener">\1</a>',
        text,
    )
    # Bold: **text** → <strong>
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    # Italic: *text* → <em>
    text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
    # Line breaks
    text = text.replace("\n\n", "</p><p>")
    text = text.replace("\n", "<br>")
    return f"<p>{text}</p>"


def _extract_city(location: str) -> str:
    """Extract the city name from a location string.

    Handles patterns like:
      "Madrid, Spain" → "Madrid"
      "Plaza Mayor, Madrid, Spain" → "Madrid"
      "Seville" → "Seville"
      "" → "Other"
    """
    if not location:
        return "Other"
    parts = [p.strip() for p in location.split(",")]
    if len(parts) >= 3:
        # "Venue, City, Country" → City
        return parts[-2]
    if len(parts) == 2:
        # "City, Country" → City
        return parts[0]
    return parts[0]


def generate_recommendation_page(
    title: str, itinerary_data: dict[str, Any], trip_link: str = ""
) -> str:
    """Build a public recommendation page from trip ideas and day items."""
    # Collect all items — ideas pile + items from scheduled days
    all_items = list(itinerary_data.get("ideas", []))
    for day in itinerary_data.get("days", []):
        for item in day.get("items", []):
            all_items.append(item)

    tips = itinerary_data.get("tips", [])

    # Group by city — extract from location strings like "Venue, City, Country"
    location_groups: dict[str, list] = {}
    for item in all_items:
        loc_key = _extract_city(item.get("location", ""))
        if loc_key not in location_groups:
            location_groups[loc_key] = []
        location_groups[loc_key].append(item)

    category_labels = {
        "meal": "Restaurants",
        "activity": "Activities",
        "attraction": "Attractions",
        "hotel": "Hotels",
        "flight": "Flights",
        "transport": "Transport",
        "other": "Other",
    }

    # Skip these categories from grouped display (shown separately or not useful)
    skip_categories = {"flight", "transport", "home"}

    # Build items HTML — group by location, then category
    items_html = ""
    for loc_name, loc_items in location_groups.items():
        # Sub-group by category within this location
        cat_groups: dict[str, list] = {}
        for item in loc_items:
            cat = item.get("category", "other")
            if cat in skip_categories:
                continue
            if cat not in cat_groups:
                cat_groups[cat] = []
            cat_groups[cat].append(item)

        if not cat_groups:
            continue

        items_html += '<div class="rec-location">'
        items_html += f'<h2 class="rec-location-header"><i class="fas fa-map-marker-alt"></i> {_esc(loc_name)}</h2>'

        for cat, items in cat_groups.items():
            label = category_labels.get(cat, cat.title())
            icon = CATEGORY_ICONS.get(cat, "fa-map-marker-alt")
            items_html += '<div class="rec-group">'
            items_html += f'<h3 class="rec-group-header"><i class="fas {icon}"></i> {label}</h3>'

            for item in items:
                notes_html = ""
                if item.get("notes"):
                    notes_html = f'<p class="rec-item-notes">{_esc(item["notes"])}</p>'

                links_html = ""
                if item.get("website"):
                    links_html += f'<a href="{_esc(item["website"])}" target="_blank" rel="noopener"><i class="fas fa-globe"></i> Website</a>'
                if item.get("google_maps_link"):
                    links_html += f'<a href="{_esc(item["google_maps_link"])}" target="_blank" rel="noopener"><i class="fas fa-map"></i> Map</a>'

                items_html += f"""
                <div class="rec-item">
                    <h3 class="rec-item-name">{_esc(item.get("title", ""))}</h3>
                    {notes_html}
                    <div class="rec-item-links">{links_html}</div>
                </div>
                """

            items_html += "</div>"  # close rec-group

        items_html += "</div>"  # close rec-location

    # Tips section
    tips_html = ""
    if tips:
        tips_html = '<div class="rec-tips"><h2><i class="fas fa-lightbulb"></i> Tips</h2><ul>'
        for tip in tips:
            tips_html += f"<li>{_esc(tip)}</li>"
        tips_html += "</ul></div>"

    # Map data — collect items with coordinates
    markers_js = "[]"
    map_items = [i for i in all_items if i.get("latitude") and i.get("longitude")]
    if map_items:
        import json

        markers = []
        for item in map_items:
            cat = item.get("category", "other")
            markers.append(
                {
                    "lat": item["latitude"],
                    "lng": item["longitude"],
                    "title": item.get("title", ""),
                    "category": cat,
                }
            )
        markers_js = json.dumps(markers)

    nav = get_nav_html("")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{_esc(title)} - Libertas</title>
    <link rel="icon" type="image/svg+xml" href="/static/favicon.svg">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
    <link rel="stylesheet" href="/static/css/main.css?v=14">
    <link rel="stylesheet" href="/static/css/main-mobile-modal.css?v=1">
    <style>
        .rec-hero {{
            background: #1a1a2e;
            color: white;
            padding: 48px 40px;
            text-align: center;
        }}
        .rec-hero h1 {{
            font-size: 2rem;
            font-weight: 300;
            letter-spacing: 1px;
        }}
        .rec-hero p {{ color: #aaa; margin-top: 8px; }}
        .rec-save-btn {{
            margin-top: 20px;
            background: #667eea;
            color: white;
            border: none;
            padding: 12px 28px;
            border-radius: 8px;
            font-size: 1rem;
            cursor: pointer;
            font-weight: 600;
        }}
        .rec-save-btn:hover {{ background: #5a6fd6; }}
        .rec-save-btn.saved {{
            background: #4caf50;
            cursor: default;
        }}
        .rec-content {{
            max-width: 800px;
            margin: 0 auto;
            padding: 40px 24px;
        }}
        .rec-map {{
            height: 350px;
            border-radius: 12px;
            margin-bottom: 32px;
            overflow: hidden;
        }}
        .rec-location {{
            margin-bottom: 40px;
        }}
        .rec-location-header {{
            font-size: 1.4rem;
            color: #333;
            padding-bottom: 8px;
            border-bottom: 3px solid #667eea;
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        .rec-location-header i {{
            color: #667eea;
            font-size: 1.1rem;
        }}
        .rec-group {{
            margin-bottom: 20px;
            margin-left: 12px;
        }}
        .rec-group-header {{
            font-size: 0.85rem;
            color: #667eea;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            padding-bottom: 6px;
            border-bottom: 1px solid #f0f0f0;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .rec-item {{
            padding: 16px 0;
            border-bottom: 1px solid #f5f5f5;
        }}
        .rec-item:last-child {{ border-bottom: none; }}
        .rec-item-header {{
            display: flex;
            align-items: baseline;
            gap: 12px;
            flex-wrap: wrap;
        }}
        .rec-item-name {{
            font-size: 1.1rem;
            color: #333;
            margin: 0;
        }}
        .rec-item-location {{
            font-size: 0.85rem;
            color: #999;
        }}
        .rec-item-location i {{ font-size: 0.75rem; }}
        .rec-item-notes {{
            color: #666;
            line-height: 1.6;
            margin: 6px 0 8px;
        }}
        .rec-item-links {{
            display: flex;
            gap: 16px;
        }}
        .rec-item-links a {{
            color: #667eea;
            text-decoration: none;
            font-size: 0.85rem;
            display: flex;
            align-items: center;
            gap: 4px;
        }}
        .rec-item-links a:hover {{ text-decoration: underline; }}
        .rec-tips {{
            background: #f8f9fa;
            border-radius: 12px;
            padding: 24px;
            margin-top: 32px;
        }}
        .rec-tips h2 {{
            font-size: 1rem;
            color: #667eea;
            margin-bottom: 12px;
        }}
        .rec-tips li {{
            color: #555;
            line-height: 1.6;
            margin-bottom: 6px;
        }}
    </style>
</head>
<body>
    {nav}

    <div class="rec-hero">
        <h1>{_esc(title)}</h1>
        <p>{len(all_items)} recommendations</p>
        <button class="rec-save-btn" id="rec-save-btn" data-source="{_esc(trip_link)}">
            <i class="fas fa-plus"></i> Save to my trips
        </button>
    </div>

    <div class="rec-content">
        <div class="rec-map" id="rec-map"></div>
        {items_html}
        {tips_html}
    </div>

    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script src="/static/js/main.js?v=7"></script>
    <script>
        // Map and save button use shared functions from main.js
        initRecommendationMap('rec-map', {markers_js});
        document.getElementById('rec-save-btn')?.addEventListener('click', function() {{
            showSaveToTripModal(this.dataset.source, '{_esc(title)}', this);
        }});
    </script>
</body>
</html>"""


def render_writeup_page(
    title: str,
    writeup_text: str,
    itinerary_data: dict[str, Any] | None = None,
    trip_link: str = "",
) -> str:
    """Render the AI-generated narrative write-up with map and venue links."""
    import json

    nav = get_nav_html("")
    content = _md_to_html(writeup_text)

    # Collect items for map and venue reference
    all_items: list = []
    if itinerary_data:
        all_items = list(itinerary_data.get("ideas", []))
        for day in itinerary_data.get("days", []):
            for item in day.get("items", []):
                all_items.append(item)

    # Map markers
    markers_js = "[]"
    map_items = [i for i in all_items if i.get("latitude") and i.get("longitude")]
    if map_items:
        markers = [
            {
                "lat": i["latitude"],
                "lng": i["longitude"],
                "title": i.get("title", ""),
                "category": i.get("category", "other"),
            }
            for i in map_items
        ]
        markers_js = json.dumps(markers)

    # Venue reference links
    venue_links_html = ""
    venues_with_links = [i for i in all_items if i.get("website") or i.get("google_maps_link")]
    if venues_with_links:
        venue_links_html = '<div class="writeup-venues"><h3>Quick Links</h3>'
        for item in venues_with_links:
            links = ""
            if item.get("website") and "google.com/search" not in item["website"]:
                links += f'<a href="{_esc(item["website"])}" target="_blank"><i class="fas fa-globe"></i> Website</a>'
            if item.get("google_maps_link"):
                links += f'<a href="{_esc(item["google_maps_link"])}" target="_blank"><i class="fas fa-map"></i> Map</a>'
            if links:
                venue_links_html += f'<div class="writeup-venue-item"><strong>{_esc(item.get("title", ""))}</strong> {links}</div>'
        venue_links_html += "</div>"

    # Save button
    save_btn = ""
    if trip_link:
        save_btn = f"""
        <button class="rec-save-btn" id="rec-save-btn" data-source="{_esc(trip_link)}">
            <i class="fas fa-plus"></i> Save to my trips
        </button>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{_esc(title)} - Libertas</title>
    <link rel="icon" type="image/svg+xml" href="/static/favicon.svg">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
    <link rel="stylesheet" href="/static/css/main.css?v=14">
    <link rel="stylesheet" href="/static/css/main-mobile-modal.css?v=1">
    <style>
        .writeup-hero {{
            background: #1a1a2e;
            color: white;
            padding: 48px 40px;
            text-align: center;
        }}
        .writeup-hero h1 {{ font-size: 2rem; font-weight: 300; letter-spacing: 1px; }}
        .writeup-hero p {{ color: #aaa; margin-top: 8px; }}
        .rec-save-btn {{
            margin-top: 20px; background: #667eea; color: white; border: none;
            padding: 12px 28px; border-radius: 8px; font-size: 1rem; cursor: pointer; font-weight: 600;
        }}
        .rec-save-btn:hover {{ background: #5a6fd6; }}
        .rec-save-btn.saved {{ background: #4caf50; cursor: default; }}
        .writeup-map {{ height: 300px; border-radius: 12px; margin-bottom: 24px; overflow: hidden; }}
        .writeup-body {{
            max-width: 700px; margin: 0 auto; padding: 40px 24px;
        }}
        .writeup-content {{
            font-size: 1.05rem; color: #333; line-height: 1.8;
        }}
        .writeup-content h1 {{ color: #333; font-size: 1.5rem; margin-top: 32px; }}
        .writeup-content h2 {{ color: #667eea; font-size: 1.3rem; margin-top: 32px; margin-bottom: 8px; }}
        .writeup-content h3 {{ color: #555; font-size: 1.1rem; margin-top: 24px; margin-bottom: 6px; }}
        .writeup-content strong {{ color: #222; }}
        .writeup-content p {{ margin-bottom: 12px; }}
        .writeup-content a {{ color: #667eea; }}
        .writeup-venues {{
            margin-top: 32px; padding: 24px; background: #f8f9fa; border-radius: 12px;
        }}
        .writeup-venues h3 {{ color: #667eea; font-size: 1rem; margin-bottom: 12px; }}
        .writeup-venue-item {{
            padding: 8px 0; border-bottom: 1px solid #eee;
            display: flex; align-items: center; gap: 12px; flex-wrap: wrap;
        }}
        .writeup-venue-item:last-child {{ border-bottom: none; }}
        .writeup-venue-item a {{
            color: #667eea; text-decoration: none; font-size: 0.85rem;
            display: inline-flex; align-items: center; gap: 4px;
        }}
        .writeup-venue-item a:hover {{ text-decoration: underline; }}
    </style>
</head>
<body>
    {nav}
    <div class="writeup-hero">
        <h1>{_esc(title)}</h1>
        {save_btn}
    </div>
    <div class="writeup-body">
        <div class="writeup-map" id="writeup-map"></div>
        <div class="writeup-content">{content}</div>
        {venue_links_html}
    </div>

    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script src="/static/js/main.js?v=7"></script>
    <script>
        // Map and save button use shared functions from main.js
        initRecommendationMap('writeup-map', {markers_js});
        document.getElementById('rec-save-btn')?.addEventListener('click', function() {{
            showSaveToTripModal(this.dataset.source, '{_esc(title)}', this);
        }});
    </script>
</body>
</html>"""
