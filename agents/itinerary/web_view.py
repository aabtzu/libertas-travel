"""Generate a unified web page with tabs for summary and map."""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Union
import html

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
        <div class="tab" onclick="switchTab('map')">
            <i class="fas fa-map-marked-alt"></i> Map
        </div>
    </div>

    <div id="summary-tab" class="tab-content active">
        <div class="summary-container">
            {summary_html}
        </div>
    </div>

    <div id="map-tab" class="tab-content">
        <iframe id="map-frame" srcdoc="{map_html_escaped}"></iframe>
    </div>

    <script>
{main_js}
    </script>
</body>
</html>
"""


class ItineraryWebView:
    """Generate a unified web page with tabs for summary and map."""

    def __init__(self, api_key: Optional[str] = None):
        self.mapper = ItineraryMapper()
        self.summarizer = ItinerarySummarizer(api_key=api_key)

    def generate(
        self,
        itinerary: Itinerary,
        output_path: str | Path,
        use_ai_summary: bool = True,
    ) -> Path:
        """Generate a unified HTML page with summary and map tabs."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Generate the map - get the raw HTML
        folium_map = self.mapper.create_map(itinerary, show_route=True)
        map_html = self._get_map_html(folium_map)

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

        # Build the full HTML
        full_html = TRIP_PAGE_TEMPLATE.format(
            main_css=get_static_css("main.css"),
            nav_html=get_nav_html("trips"),
            main_js=get_static_js("main.js"),
            title=html.escape(itinerary.title),
            meta_info=html.escape(meta_info),
            summary_html=summary_html,
            map_html_escaped=html.escape(map_html),
        )

        output_path.write_text(full_html)
        return output_path

    def _get_map_html(self, folium_map) -> str:
        """Get the full HTML for the folium map."""
        import tempfile
        import os

        # Save to a temp file and read back
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            temp_path = f.name

        folium_map.save(temp_path)

        with open(temp_path, 'r') as f:
            map_html = f.read()

        os.unlink(temp_path)
        return map_html

    def _build_summary_html(self, itinerary: Itinerary) -> str:
        """Build a compact HTML summary directly from itinerary data."""
        lines = [f"<h2>{html.escape(itinerary.title)}</h2>"]

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
                lines.append(f'<span class="activity-title">{html.escape(title)}</span>')
                lines.append(f'<span class="activity-location">{html.escape(location)}</span>')
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
                lines.append(f'<span class="activity-title">{html.escape(title)}</span>')
                lines.append(f'<span class="activity-location">{html.escape(location)}</span>')
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
                lines.append(f'<span class="location-tag">{html.escape(loc_name)}</span>')
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
