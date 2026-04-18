"""Generate the shareable recommendation view HTML."""

from __future__ import annotations

import html as html_mod
from typing import Any

from agents.common.categories import CATEGORY_ICONS
from agents.common.templates import get_nav_html


def _esc(text: str) -> str:
    return html_mod.escape(str(text)) if text else ""


def generate_recommendation_page(
    title: str, itinerary_data: dict[str, Any], trip_link: str = ""
) -> str:
    """Build a public recommendation page from trip ideas."""
    ideas = itinerary_data.get("ideas", [])
    tips = itinerary_data.get("tips", [])

    # Group by category
    groups: dict[str, list] = {}
    for item in ideas:
        cat = item.get("category", "other")
        if cat not in groups:
            groups[cat] = []
        groups[cat].append(item)

    category_labels = {
        "meal": "Restaurants",
        "activity": "Activities",
        "attraction": "Attractions",
        "hotel": "Hotels",
        "other": "Other",
    }

    # Build items HTML
    items_html = ""
    for cat, items in groups.items():
        label = category_labels.get(cat, cat.title())
        icon = CATEGORY_ICONS.get(cat, "fa-map-marker-alt")
        items_html += '<div class="rec-group">'
        items_html += f'<h2 class="rec-group-header"><i class="fas {icon}"></i> {label}</h2>'

        for item in items:
            notes_html = ""
            if item.get("notes"):
                notes_html = f'<p class="rec-item-notes">{_esc(item["notes"])}</p>'

            links_html = ""
            if item.get("website"):
                links_html += f'<a href="{_esc(item["website"])}" target="_blank" rel="noopener"><i class="fas fa-globe"></i> Website</a>'
            if item.get("google_maps_link"):
                links_html += f'<a href="{_esc(item["google_maps_link"])}" target="_blank" rel="noopener"><i class="fas fa-map"></i> Map</a>'

            location_html = ""
            if item.get("location"):
                location_html = f'<span class="rec-item-location"><i class="fas fa-map-pin"></i> {_esc(item["location"])}</span>'

            items_html += f"""
                <div class="rec-item">
                    <div class="rec-item-header">
                        <h3 class="rec-item-name">{_esc(item.get("title", ""))}</h3>
                        {location_html}
                    </div>
                    {notes_html}
                    <div class="rec-item-links">{links_html}</div>
                </div>
            """

        items_html += "</div>"

    # Tips section
    tips_html = ""
    if tips:
        tips_html = '<div class="rec-tips"><h2><i class="fas fa-lightbulb"></i> Tips</h2><ul>'
        for tip in tips:
            tips_html += f"<li>{_esc(tip)}</li>"
        tips_html += "</ul></div>"

    # Map data — collect items with coordinates
    markers_js = "[]"
    map_items = [i for i in ideas if i.get("latitude") and i.get("longitude")]
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
        .rec-group {{
            margin-bottom: 32px;
        }}
        .rec-group-header {{
            font-size: 1rem;
            color: #667eea;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            padding-bottom: 8px;
            border-bottom: 2px solid #f0f0f0;
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
        <p>{len(ideas)} recommendations</p>
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
        document.getElementById('rec-save-btn')?.addEventListener('click', async function() {{
            const btn = this;
            const sourceLink = btn.dataset.source;

            // Check if logged in
            const listRes = await fetch('/api/trips/list');
            if (listRes.status === 401) {{
                window.location.href = '/register?redirect=' + encodeURIComponent(window.location.pathname);
                return;
            }}

            const listData = await listRes.json();
            const trips = listData.trips || [];

            // Create a new trip or pick existing
            let targetLink;
            if (trips.length === 0) {{
                // Create new trip with same title
                const createRes = await fetch('/api/trips/create', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{title: '{_esc(title)}'}})
                }});
                const createData = await createRes.json();
                targetLink = createData.trip?.link || createData.link;
            }} else {{
                const names = trips.map((t, i) => `${{i+1}}. ${{t.title}}`).join('\\n');
                const choice = prompt(`Save to which trip?\\n\\n0. Create new trip\\n${{names}}\\n\\nEnter number:`);
                if (choice === null) return;
                const idx = parseInt(choice, 10);
                if (idx === 0) {{
                    const createRes = await fetch('/api/trips/create', {{
                        method: 'POST',
                        headers: {{'Content-Type': 'application/json'}},
                        body: JSON.stringify({{title: '{_esc(title)}'}})
                    }});
                    const createData = await createRes.json();
                    targetLink = createData.trip?.link || createData.link;
                }} else if (idx > 0 && idx <= trips.length) {{
                    targetLink = trips[idx - 1].link;
                }} else {{
                    return;
                }}
            }}

            if (!targetLink) return;

            // Clone ideas
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
        }});
    </script>
</body>
</html>"""
