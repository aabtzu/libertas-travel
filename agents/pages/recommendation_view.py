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
    """Minimal markdown to HTML: bold, italic, headers, line breaks."""
    text = html_mod.escape(text)
    # Headers: ### Header → <h3>
    text = re.sub(r"^### (.+)$", r"<h3>\1</h3>", text, flags=re.MULTILINE)
    text = re.sub(r"^## (.+)$", r"<h2>\1</h2>", text, flags=re.MULTILINE)
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
    <link rel="stylesheet" href="/static/css/main.css?v=9">
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
    <script src="/static/js/main.js?v=6"></script>
    <script>
        const markers = {markers_js};
        if (markers.length > 0) {{
            const map = L.map('rec-map');
            L.tileLayer(LibertasMap.tileUrl, LibertasMap.tileOptions).addTo(map);

            const colors = {{
                meal: '#FF9800', activity: '#34A853', attraction: '#34A853',
                hotel: '#4285F4', other: '#667eea'
            }};

            const bounds = [];
            markers.forEach(m => {{
                const color = colors[m.category] || '#667eea';
                L.circleMarker([m.lat, m.lng], {{
                    radius: 8, fillColor: color, color: '#fff',
                    weight: 2, fillOpacity: 0.9
                }}).addTo(map).bindPopup(m.title);
                bounds.push([m.lat, m.lng]);
            }});

            if (bounds.length === 1) map.setView(bounds[0], 13);
            else map.fitBounds(bounds, {{ padding: [30, 30] }});
        }} else {{
            document.getElementById('rec-map').style.display = 'none';
        }}

        // Save to my trips
        async function cloneToTrip(sourceLink, targetLink, btn) {{
            const res = await fetch('/api/trips/clone-ideas', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{source_link: sourceLink, target_link: targetLink}})
            }});
            const data = await res.json();
            if (data.success) {{
                btn.innerHTML = '<i class="fas fa-check"></i> Saved!';
                btn.classList.add('saved');
                btn.disabled = true;
            }}
        }}

        async function createAndClone(sourceLink, title, btn) {{
            const res = await fetch('/api/trips/create', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{title: title}})
            }});
            const data = await res.json();
            const link = data.trip?.link || data.link;
            if (link) await cloneToTrip(sourceLink, link, btn);
        }}

        function showSaveModal(trips, sourceLink, btn) {{
            const old = document.getElementById('save-modal');
            if (old) old.remove();

            const overlay = document.createElement('div');
            overlay.id = 'save-modal';
            overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.5);display:flex;align-items:center;justify-content:center;z-index:10000';
            overlay.innerHTML = `
                <div style="background:white;border-radius:14px;width:90%;max-width:400px;max-height:70vh;overflow:hidden;box-shadow:0 8px 40px rgba(0,0,0,0.2)">
                    <div style="display:flex;align-items:center;justify-content:space-between;padding:20px 24px 16px;border-bottom:1px solid #eee">
                        <h3 style="margin:0;font-size:1.1rem;color:#333">Save to trip</h3>
                        <button id="save-modal-close" style="background:none;border:none;font-size:1.1rem;color:#999;cursor:pointer;padding:4px 8px"><i class="fas fa-times"></i></button>
                    </div>
                    <div style="overflow-y:auto;max-height:50vh;padding:8px">
                        <button class="save-modal-item" data-action="new" style="display:flex;align-items:center;gap:12px;width:100%;padding:14px 16px;border:none;background:none;border-radius:10px;font-size:0.95rem;color:#667eea;cursor:pointer;text-align:left;font-weight:600;border-bottom:1px solid #eee">
                            <i class="fas fa-plus-circle"></i> New trip
                        </button>
                        ${{trips.map(t => `
                            <button class="save-modal-item" data-link="${{t.link}}" style="display:flex;align-items:center;gap:12px;width:100%;padding:14px 16px;border:none;background:none;border-radius:10px;font-size:0.95rem;color:#333;cursor:pointer;text-align:left">
                                <i class="fas fa-suitcase" style="color:#667eea"></i> ${{t.title}}
                            </button>
                        `).join('')}}
                    </div>
                </div>
            `;

            overlay.addEventListener('click', async (e) => {{
                if (e.target === overlay || e.target.closest('#save-modal-close')) {{
                    overlay.remove();
                    return;
                }}
                const item = e.target.closest('.save-modal-item');
                if (!item) return;
                overlay.remove();
                if (item.dataset.action === 'new') {{
                    await createAndClone(sourceLink, '{_esc(title)}', btn);
                }} else {{
                    await cloneToTrip(sourceLink, item.dataset.link, btn);
                }}
            }});

            const onEsc = (e) => {{ if (e.key === 'Escape') {{ overlay.remove(); document.removeEventListener('keydown', onEsc); }} }};
            document.addEventListener('keydown', onEsc);
            document.body.appendChild(overlay);
        }}

        document.getElementById('rec-save-btn')?.addEventListener('click', async function() {{
            const btn = this;
            const sourceLink = btn.dataset.source;

            const listRes = await fetch('/api/trips/list');
            if (listRes.status === 401) {{
                window.location.href = '/register?redirect=' + encodeURIComponent(window.location.pathname);
                return;
            }}

            const trips = (await listRes.json()).trips || [];

            if (trips.length === 0) {{
                await createAndClone(sourceLink, '{_esc(title)}', btn);
            }} else {{
                showSaveModal(trips, sourceLink, btn);
            }}
        }});
    </script>
</body>
</html>"""


def render_writeup_page(title: str, writeup_text: str) -> str:
    """Render the AI-generated narrative write-up as a clean page."""
    nav = get_nav_html("")
    content = _md_to_html(writeup_text)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{_esc(title)} - Libertas</title>
    <link rel="icon" type="image/svg+xml" href="/static/favicon.svg">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
    <link rel="stylesheet" href="/static/css/main.css?v=9">
    <style>
        .writeup-hero {{
            background: #1a1a2e;
            color: white;
            padding: 48px 40px;
            text-align: center;
        }}
        .writeup-hero h1 {{
            font-size: 2rem;
            font-weight: 300;
            letter-spacing: 1px;
        }}
        .writeup-hero p {{ color: #aaa; margin-top: 8px; }}
        .writeup-content {{
            max-width: 700px;
            margin: 0 auto;
            padding: 40px 24px;
            font-size: 1.05rem;
            color: #333;
            line-height: 1.8;
        }}
        .writeup-content h2 {{
            color: #667eea;
            font-size: 1.3rem;
            margin-top: 32px;
            margin-bottom: 8px;
        }}
        .writeup-content h3 {{
            color: #555;
            font-size: 1.1rem;
            margin-top: 24px;
            margin-bottom: 6px;
        }}
        .writeup-content strong {{ color: #222; }}
        .writeup-content p {{ margin-bottom: 12px; }}
    </style>
</head>
<body>
    {nav}
    <div class="writeup-hero">
        <h1>{_esc(title)}</h1>
        <p><i class="fas fa-pen-fancy"></i> AI-generated recommendation</p>
    </div>
    <div class="writeup-content">
        {content}
    </div>
    <script src="/static/js/main.js?v=6"></script>
</body>
</html>"""
