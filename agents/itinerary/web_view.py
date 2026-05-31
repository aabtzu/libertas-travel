"""Generate a unified web page with tabs for summary and map using Google Maps."""

from __future__ import annotations

import html as html_module
import json
import os
from pathlib import Path

from agents.common.categories import CATEGORY_ICONS, TRAVEL_CATEGORIES

from .mapper import ItineraryMapper
from .models import Itinerary, ItineraryItem
from .summarizer import ItinerarySummarizer
from .templates import get_nav_html, get_template
from .web_view_columns import build_calendar_html, build_column_html


def _build_viewer_buttons_html(is_owner: bool, is_authenticated: bool, trip_link: str) -> str:
    """Single source of truth for the header action buttons on the trip view page.

    Returns different buttons depending on who is viewing:
    - Owner: full controls + Copy Link
    - Logged-in non-owner: Copy to My Trips
    - Anonymous: Sign in to edit CTA
    """
    if is_owner:
        return (
            '<button class="export-btn" onclick="editTrip()" title="Edit this trip">'
            '<i class="fas fa-edit"></i> Edit</button>'
            '<button class="export-btn" onclick="regenerateMap()" title="Regenerate map">'
            '<i class="fas fa-sync-alt"></i> Regen Map</button>'
            '<button class="export-btn" onclick="exportTrip()" title="Download trip data">'
            '<i class="fas fa-download"></i> Export</button>'
            '<button class="export-btn" onclick="copyShareLink()" title="Copy shareable link">'
            '<i class="fas fa-link"></i> Copy Link</button>'
        )
    if is_authenticated:
        return (
            '<button class="export-btn" onclick="copyTripToMyTrips()" title="Add a copy to your trips">'
            '<i class="fas fa-copy"></i> Copy to My Trips</button>'
        )
    # Anonymous viewer
    redirect = html_module.escape(f"/trip/{trip_link}" if trip_link else "/trips")
    return (
        f'<a class="export-btn" href="/login?redirect={redirect}" style="text-decoration:none;">'
        '<i class="fas fa-sign-in-alt"></i> Sign in to edit</a>'
    )


class ItineraryWebView:
    """Generate a unified web page with tabs for summary and map using Google Maps."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("GOOGLE_MAPS_API_KEY", "")
        self.mapper = ItineraryMapper(api_key=self.api_key)
        self.summarizer = ItinerarySummarizer(api_key=api_key)

    def render_html(
        self,
        itinerary: Itinerary,
        map_data: dict | None = None,
        is_owner: bool = False,
        is_authenticated: bool = False,
        trip_link: str = "",
        card_icon: str = "plane",
    ) -> str:
        """Render trip HTML without writing to file.

        Args:
            itinerary: The Itinerary object to render
            map_data: Pre-computed map data (markers, center, zoom). If None, uses placeholder.

        Returns:
            HTML string for the trip page
        """
        # Use provided map_data or placeholder
        if map_data is None:
            map_data = {"center": {"lat": 20, "lng": 0}, "zoom": 2, "markers": [], "pending": True}

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

        # Generate column view HTML (defined in web_view_columns.py)
        column_html = build_column_html(itinerary)

        # Generate calendar view HTML (defined in web_view_columns.py)
        calendar_html = build_calendar_html(itinerary)

        # Build the full HTML
        return get_template("trip.html").format(
            nav_html=get_nav_html("trips"),
            title=html_module.escape(itinerary.title),
            trip_icon=html_module.escape(card_icon or "plane"),
            meta_info=html_module.escape(meta_info),
            summary_html=summary_html,
            column_html=column_html,
            calendar_html=calendar_html,
            map_data_json=json.dumps(map_data),
            viewer_buttons_html=_build_viewer_buttons_html(is_owner, is_authenticated, trip_link),
            is_owner_json="true" if is_owner else "false",
            is_authenticated_json="true" if is_authenticated else "false",
        )

    def generate(
        self,
        itinerary: Itinerary,
        output_path: str | Path,
        use_ai_summary: bool = True,
        skip_geocoding: bool = False,
    ) -> tuple[Path, dict]:
        """Generate a unified HTML page with summary and Google Maps tabs.

        Args:
            skip_geocoding: If True, skip geocoding to speed up generation.
                           Map will show placeholder instead of real locations.

        Returns:
            Tuple of (output_path, map_data) so map_data can be stored in database
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
                "error": f"Map for {itinerary.title} - geocoding skipped for speed",
            }
            print("[WEB_VIEW] Skipped geocoding for speed")
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
                    "error": "Map could not be generated - geocoding failed",
                }

        # Render HTML using the new method
        full_html = self.render_html(itinerary, map_data)

        output_path.write_text(full_html)
        return output_path, map_data

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
            lines.append(f"<h3>Day {day_num}{date_str}</h3>")

            for item in items:
                lines.extend(self._render_summary_item(item))

            lines.append("</div>")

        # Render items without days
        if items_without_day:
            lines.append('<div class="day-card">')
            lines.append("<h3>Other Activities</h3>")
            for item in items_without_day:
                lines.extend(self._render_summary_item(item))
            lines.append("</div>")

        # Key locations section
        locations = itinerary.locations
        if locations:
            lines.append('<div class="locations-section">')
            lines.append("<h3>Key Locations</h3>")
            lines.append('<div class="location-list">')
            for loc in locations:
                loc_name = loc.name or "Unknown"
                lines.append(f'<span class="location-tag">{html_module.escape(loc_name)}</span>')
            lines.append("</div>")
            lines.append("</div>")

        return "\n".join(lines)

    def _render_summary_item(self, item: ItineraryItem) -> list[str]:
        """Render a single activity row for the summary view."""
        time_str = ""
        if item.start_time:
            time_str = item.start_time.strftime("%I:%M %p").lstrip("0")
            if item.end_time:
                end_time_str = item.end_time.strftime("%I:%M %p").lstrip("0")
                # For flights/transport, use arrow; for others use dash
                if item.category in TRAVEL_CATEGORIES:
                    time_str = f"{time_str} → {end_time_str}"
                else:
                    time_str = f"{time_str} - {end_time_str}"

        category = item.category or "other"
        category_icon = self._get_category_html(category)

        # Build data attributes for popup
        title = item.title or "Untitled"
        location = (item.location.name if item.location and item.location.name else "") or ""
        website = html_module.escape(item.website_url) if item.website_url else ""
        notes = (
            html_module.escape(item.notes or item.description or "")[:200]
            if (item.notes or item.description)
            else ""
        )

        lines = []
        lines.append(
            f'<div class="activity" '
            f'data-title="{html_module.escape(title)}" '
            f'data-time="{time_str}" '
            f'data-location="{html_module.escape(location)}" '
            f'data-category="{category}" '
            f'data-website="{website}" '
            f'data-notes="{notes}">'
        )
        lines.append(f'<span class="activity-category {category}">{category_icon}</span>')
        if time_str:
            lines.append(f'<span class="activity-time">{time_str}</span>')
        else:
            lines.append('<span class="activity-time"></span>')

        lines.append('<div class="activity-info">')
        lines.append(f'<span class="activity-title">{html_module.escape(title)}</span>')
        lines.append(f'<span class="activity-location">{html_module.escape(location)}</span>')
        lines.append("</div>")
        lines.append("</div>")
        return lines

    def _get_category_label(self, category: str) -> str:
        """Get display label for a category."""
        labels = {
            "flight": "Flight",
            "train": "Train",
            "bus": "Bus",
            "transport": "Transport",
            "hotel": "Lodging",
            "lodging": "Lodging",
            "activity": "Activity",
            "meal": "Meal",
            "home": "Home",
            "other": "Other",
        }
        return labels.get(category.lower(), category.title())

    def _get_category_icon(self, category: str) -> str:
        """Get Font Awesome icon class for a category.

        Uses the canonical mapping from agents.common.categories, do not
        add a local copy here.
        """
        return CATEGORY_ICONS.get(category.lower(), "fa-calendar-day")

    def _get_category_html(self, category: str) -> str:
        """Get icon-based HTML for a category badge."""
        icon = self._get_category_icon(category)
        return f'<i class="fas {icon}"></i>'

    # The following methods are delegated to web_view_columns.py.
    # They remain as thin wrappers so any code that calls them on an instance
    # still works without changes.

    def _build_column_html(self, itinerary: Itinerary) -> str:
        """Delegate to standalone build_column_html (defined in web_view_columns.py)."""
        return build_column_html(itinerary)

    def _build_calendar_html(self, itinerary: Itinerary) -> str:
        """Delegate to standalone build_calendar_html (defined in web_view_columns.py)."""
        return build_calendar_html(itinerary)
