"""Generate a unified web page with tabs for summary and map using Google Maps."""

from __future__ import annotations

import os
import json
from pathlib import Path
from typing import Optional, Union
import html as html_module

from .models import Itinerary, ItineraryItem
from .mapper import ItineraryMapper
from .summarizer import ItinerarySummarizer
from .templates import get_static_css, get_static_js, get_nav_html


TRIP_PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - Libertas</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
    <style>
{main_css}

/* Google Maps container */
#google-map {{
    width: 100%;
    height: 100%;
    min-height: 500px;
}}
#map-tab {{
    position: relative;
}}
/* Map loading overlay */
.map-loading-overlay {{
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(245, 245, 245, 0.95);
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    z-index: 1000;
}}
.map-loading-overlay.hidden {{
    display: none;
}}
.map-loading-spinner {{
    width: 50px;
    height: 50px;
    border: 4px solid #e0e0e0;
    border-top-color: #667eea;
    border-radius: 50%;
    animation: spin 1s linear infinite;
}}
@keyframes spin {{
    to {{ transform: rotate(360deg); }}
}}
.map-loading-text {{
    margin-top: 20px;
    font-size: 1.1rem;
    color: #666;
}}
.map-loading-subtext {{
    margin-top: 8px;
    font-size: 0.9rem;
    color: #999;
}}
.map-status-ready {{
    color: #27ae60;
}}
.map-status-error {{
    color: #e74c3c;
}}
/* Map legend */
.map-legend {{
    position: absolute;
    bottom: 30px;
    left: 10px;
    background: white;
    padding: 14px 18px;
    border-radius: 8px;
    box-shadow: 0 2px 6px rgba(0,0,0,0.3);
    font-size: 15px;
    z-index: 100;
    max-width: 180px;
}}
.map-legend h4 {{
    margin: 0 0 12px 0;
    font-size: 16px;
    color: #333;
    border-bottom: 1px solid #eee;
    padding-bottom: 8px;
}}
.legend-item {{
    display: flex;
    align-items: center;
    margin: 8px 0;
}}
.legend-dot {{
    width: 24px;
    height: 24px;
    border-radius: 50%;
    margin-right: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    border: 2px solid white;
    box-shadow: 0 1px 3px rgba(0,0,0,0.3);
}}
.legend-dot i {{
    font-size: 11px;
    color: white;
}}
.legend-label {{
    color: #444;
    font-size: 15px;
}}
    </style>
</head>
<body>
    {nav_html}

    <div class="trip-header">
        <h1><i class="fas fa-plane"></i> {title}</h1>
        <div class="meta">{meta_info}</div>
    </div>

    <div class="tabs">
        <div class="tab active" onclick="switchTab('summary')">
            <i class="fas fa-list-alt"></i> Summary
        </div>
        <div class="tab" onclick="switchTab('map')" id="map-tab-btn">
            <i class="fas fa-map-marked-alt"></i> Map <span id="map-status-badge"></span>
        </div>
    </div>

    <div id="summary-tab" class="tab-content active">
        <div class="summary-container">
            {summary_html}
        </div>
    </div>

    <div id="map-tab" class="tab-content">
        <div class="map-loading-overlay" id="map-loading">
            <div class="map-loading-spinner"></div>
            <div class="map-loading-text">Generating map...</div>
            <div class="map-loading-subtext">Geocoding locations, this may take a minute</div>
        </div>
        <div id="google-map"></div>
        <div class="map-legend" id="map-legend">
            <h4>Legend</h4>
            <div class="legend-item">
                <div class="legend-dot" style="background:#EA4335;"><i class="fas fa-plane"></i></div>
                <span class="legend-label">Flight</span>
            </div>
            <div class="legend-item">
                <div class="legend-dot" style="background:#4285F4;"><i class="fas fa-bed"></i></div>
                <span class="legend-label">Hotel</span>
            </div>
            <div class="legend-item">
                <div class="legend-dot" style="background:#34A853;"><i class="fas fa-star"></i></div>
                <span class="legend-label">Activity</span>
            </div>
            <div class="legend-item">
                <div class="legend-dot" style="background:#FF9800;"><i class="fas fa-utensils"></i></div>
                <span class="legend-label">Meal</span>
            </div>
            <div class="legend-item">
                <div class="legend-dot" style="background:#757575;"><i class="fas fa-car"></i></div>
                <span class="legend-label">Transport</span>
            </div>
        </div>
    </div>

    <script>
{main_js}

// Google Maps data
var mapData = {map_data_json};

// Initialize Google Map
var map = null;
var markers = [];
var infoWindow = null;

function initMap() {{
    var mapLoading = document.getElementById('map-loading');

    if (!mapData || mapData.error) {{
        if (mapLoading) {{
            mapLoading.innerHTML = '<div class="map-status-error"><i class="fas fa-exclamation-triangle"></i></div>' +
                '<div class="map-loading-text map-status-error">Map not available</div>' +
                '<div class="map-loading-subtext">' + (mapData.error || 'No location data') + '</div>';
        }}
        return;
    }}

    // Create map with mapId for AdvancedMarkerElement support
    map = new google.maps.Map(document.getElementById('google-map'), {{
        center: mapData.center,
        zoom: mapData.zoom,
        mapId: 'DEMO_MAP_ID',
        mapTypeControl: true,
        mapTypeControlOptions: {{
            style: google.maps.MapTypeControlStyle.HORIZONTAL_BAR,
            position: google.maps.ControlPosition.TOP_RIGHT
        }},
        fullscreenControl: true,
        streetViewControl: false,
    }});

    // Create info window
    infoWindow = new google.maps.InfoWindow();

    // Category icon mapping (using Font Awesome class names)
    var categoryIcons = {{
        'flight': 'fa-plane',
        'hotel': 'fa-bed',
        'lodging': 'fa-bed',
        'meal': 'fa-utensils',
        'restaurant': 'fa-utensils',
        'activity': 'fa-star',
        'attraction': 'fa-star',
        'transport': 'fa-car',
        'other': 'fa-map-marker-alt'
    }};

    // Add markers with category icons using custom HTML
    mapData.markers.forEach(function(markerData, index) {{
        var iconClass = categoryIcons[markerData.category] || 'fa-map-marker-alt';

        // Create custom marker element
        var markerDiv = document.createElement('div');
        markerDiv.style.cssText = 'width: 28px; height: 28px; border-radius: 50%; display: flex; align-items: center; justify-content: center; border: 2px solid white; box-shadow: 0 2px 4px rgba(0,0,0,0.3); cursor: pointer; background-color: ' + markerData.color + ';';
        markerDiv.innerHTML = '<i class="fas ' + iconClass + '" style="color: white; font-size: 12px;"></i>';

        var marker = new google.maps.marker.AdvancedMarkerElement({{
            position: markerData.position,
            map: map,
            title: markerData.title,
            content: markerDiv
        }});

        marker.addListener('click', function() {{
            infoWindow.setContent(markerData.info);
            infoWindow.open(map, marker);
        }});

        markers.push(marker);
    }});

    // Hide loading overlay
    if (mapLoading) mapLoading.classList.add('hidden');
}}

// Map status polling - only poll if map is pending/processing
(function() {{
    var tripLink = window.location.pathname.split('/').pop();
    var mapLoading = document.getElementById('map-loading');
    var mapBadge = document.getElementById('map-status-badge');
    var pollInterval = null;
    var wasNotReady = false;

    function checkMapStatus() {{
        fetch('/api/map-status?link=' + encodeURIComponent(tripLink))
            .then(function(r) {{ return r.json(); }})
            .then(function(data) {{
                if (data.map_status === 'ready') {{
                    if (mapBadge) mapBadge.innerHTML = '';
                    if (pollInterval) clearInterval(pollInterval);
                    if (wasNotReady) {{
                        window.location.reload();
                    }}
                }} else if (data.map_status === 'error') {{
                    if (mapLoading) {{
                        mapLoading.innerHTML = '<div class="map-status-error"><i class="fas fa-exclamation-triangle"></i></div>' +
                            '<div class="map-loading-text map-status-error">Map generation failed</div>' +
                            '<div class="map-loading-subtext">' + (data.map_error || 'Unknown error') + '</div>';
                    }}
                    if (mapBadge) mapBadge.innerHTML = '<i class="fas fa-exclamation-circle" style="color:#e74c3c;margin-left:5px;"></i>';
                    if (pollInterval) clearInterval(pollInterval);
                }} else if (data.map_status === 'pending' || data.map_status === 'processing') {{
                    wasNotReady = true;
                    if (mapLoading) mapLoading.classList.remove('hidden');
                    if (mapBadge) mapBadge.innerHTML = '<i class="fas fa-spinner fa-spin" style="color:#667eea;margin-left:5px;"></i>';
                }}
            }})
            .catch(function(err) {{
                console.log('Map status check failed:', err);
            }});
    }}

    checkMapStatus();
    pollInterval = setInterval(checkMapStatus, 5000);
}})();
    </script>
    <script async defer src="https://maps.googleapis.com/maps/api/js?key={google_maps_api_key}&libraries=marker&callback=initMap"></script>
</body>
</html>
"""


class ItineraryWebView:
    """Generate a unified web page with tabs for summary and map using Google Maps."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("GOOGLE_MAPS_API_KEY", "")
        self.mapper = ItineraryMapper(api_key=self.api_key)
        self.summarizer = ItinerarySummarizer(api_key=api_key)

    def generate(
        self,
        itinerary: Itinerary,
        output_path: str | Path,
        use_ai_summary: bool = True,
        skip_geocoding: bool = False,
    ) -> Path:
        """Generate a unified HTML page with summary and Google Maps tabs.

        Args:
            skip_geocoding: If True, skip geocoding to speed up generation.
                           Map will show placeholder instead of real locations.
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Generate map data for Google Maps
        if skip_geocoding:
            # Create placeholder map data without geocoding
            map_data = {
                "center": {"lat": 20, "lng": 0},
                "zoom": 2,
                "markers": [],
                "error": f"Map for {itinerary.title} - geocoding skipped for speed"
            }
            print(f"[WEB_VIEW] Skipped geocoding for speed")
        else:
            try:
                map_data = self.mapper.create_map_data(itinerary)
            except Exception as e:
                print(f"Warning: Map generation failed: {e}")
                import traceback
                traceback.print_exc()
                map_data = {
                    "center": {"lat": 0, "lng": 0},
                    "zoom": 2,
                    "markers": [],
                    "error": "Map could not be generated - geocoding failed"
                }

        # Generate the summary HTML directly from itinerary data
        summary_html = self._build_summary_html(itinerary)

        # Build meta info
        meta_parts = []
        if itinerary.start_date and itinerary.end_date:
            meta_parts.append(
                f"{itinerary.start_date.strftime('%B %d')} - "
                f"{itinerary.end_date.strftime('%B %d, %Y')}"
            )
        if itinerary.duration_days:
            meta_parts.append(f"{itinerary.duration_days} days")
        if itinerary.travelers:
            meta_parts.append(f"{len(itinerary.travelers)} travelers")
        meta_parts.append(f"{len(itinerary.items)} activities")

        meta_info = " • ".join(meta_parts)

        # Get Google Maps API key
        google_maps_api_key = self.api_key or os.environ.get("GOOGLE_MAPS_API_KEY", "")

        # Build the full HTML
        full_html = TRIP_PAGE_TEMPLATE.format(
            main_css=get_static_css("main.css"),
            nav_html=get_nav_html("trips"),
            main_js=get_static_js("main.js"),
            title=html_module.escape(itinerary.title),
            meta_info=html_module.escape(meta_info),
            summary_html=summary_html,
            map_data_json=json.dumps(map_data),
            google_maps_api_key=google_maps_api_key,
        )

        output_path.write_text(full_html)
        return output_path

    def _build_summary_html(self, itinerary: Itinerary) -> str:
        """Build a compact HTML summary directly from itinerary data."""
        lines = [f"<h2>{html_module.escape(itinerary.title)}</h2>"]

        # Group items by day
        items_by_day: dict[int, list[ItineraryItem]] = {}
        items_without_day: list[ItineraryItem] = []

        for item in itinerary.items:
            if item.day_number:
                if item.day_number not in items_by_day:
                    items_by_day[item.day_number] = []
                items_by_day[item.day_number].append(item)
            elif item.date:
                items_without_day.append(item)
            else:
                items_without_day.append(item)

        # Render days in order
        for day_num in sorted(items_by_day.keys()):
            items = items_by_day[day_num]
            lines.append('<div class="day-card">')

            # Get date if available
            date_str = ""
            if items and items[0].date:
                date_str = f" - {items[0].date.strftime('%B %d')}"
            lines.append(f'<h3>Day {day_num}{date_str}</h3>')

            for item in items:
                time_str = ""
                if item.start_time:
                    time_str = item.start_time.strftime("%I:%M %p").lstrip("0")

                category = item.category or "other"
                category_label = self._get_category_label(category)

                lines.append('<div class="activity">')
                lines.append(f'<span class="activity-category {category}">{category_label}</span>')
                if time_str:
                    lines.append(f'<span class="activity-time">{time_str}</span>')
                else:
                    lines.append('<span class="activity-time"></span>')

                title = item.title or "Untitled"
                location = item.location.name or "Unknown location"
                lines.append(f'<span class="activity-title">{html_module.escape(title)}</span>')
                lines.append(f'<span class="activity-location">{html_module.escape(location)}</span>')
                lines.append('</div>')

            lines.append('</div>')

        # Render items without days
        if items_without_day:
            lines.append('<div class="day-card">')
            lines.append('<h3>Other Activities</h3>')
            for item in items_without_day:
                time_str = ""
                if item.start_time:
                    time_str = item.start_time.strftime("%I:%M %p").lstrip("0")

                category = item.category or "other"
                category_label = self._get_category_label(category)

                lines.append('<div class="activity">')
                lines.append(f'<span class="activity-category {category}">{category_label}</span>')
                if time_str:
                    lines.append(f'<span class="activity-time">{time_str}</span>')
                else:
                    lines.append('<span class="activity-time"></span>')

                title = item.title or "Untitled"
                location = item.location.name or "Unknown location"
                lines.append(f'<span class="activity-title">{html_module.escape(title)}</span>')
                lines.append(f'<span class="activity-location">{html_module.escape(location)}</span>')
                lines.append('</div>')
            lines.append('</div>')

        # Key locations section
        locations = itinerary.locations
        if locations:
            lines.append('<div class="locations-section">')
            lines.append('<h3>Key Locations</h3>')
            lines.append('<div class="location-list">')
            for loc in locations:
                loc_name = loc.name or "Unknown"
                lines.append(f'<span class="location-tag">{html_module.escape(loc_name)}</span>')
            lines.append('</div>')
            lines.append('</div>')

        return "\n".join(lines)

    def _get_category_label(self, category: str) -> str:
        """Get display label for a category."""
        labels = {
            "flight": "Flight",
            "hotel": "Lodging",
            "lodging": "Lodging",
            "activity": "Activity",
            "transport": "Travel",
            "meal": "Meal",
            "home": "Home",
            "other": "Other",
        }
        return labels.get(category.lower(), category.title())
