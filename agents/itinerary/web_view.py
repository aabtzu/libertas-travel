"""Generate a unified web page with tabs for summary and map using Google Maps."""

from __future__ import annotations

import html as html_module
import json
import os
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from agents.common.categories import CATEGORY_ICONS, TRAVEL_CATEGORIES

from .mapper import ItineraryMapper
from .models import Itinerary, ItineraryItem
from .summarizer import ItinerarySummarizer
from .templates import get_nav_html
from .web_view_columns import build_calendar_html, build_column_html

_TEMPLATE_DIR = Path(__file__).parent / "templates"
_jinja_env = Environment(loader=FileSystemLoader(str(_TEMPLATE_DIR)), autoescape=True)


def _build_viewer_buttons_html(is_owner: bool, is_authenticated: bool, trip_link: str) -> str:
    """Single source of truth for the header action buttons on the trip view page.

    Returns different buttons depending on who is viewing:
    - Owner: full controls + Copy Link
    - Logged-in non-owner: Copy to My Trips
    - Anonymous: Sign in to edit CTA
    """
    redirect_url = f"/trip/{trip_link}" if trip_link else "/trips"
    return _jinja_env.get_template("viewer_buttons.html").render(
        is_owner=is_owner,
        is_authenticated=is_authenticated,
        redirect_url=redirect_url,
    )


class ItineraryWebView:
    """Generate a unified web page with tabs for summary and map using Google Maps."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("GOOGLE_MAPS_API_KEY", "")
        self.mapper = ItineraryMapper(api_key=self.api_key)
        self.summarizer = ItinerarySummarizer(api_key=api_key)

    def build_context(
        self,
        itinerary: Itinerary,
        map_data: dict | None = None,
        is_owner: bool = False,
        is_authenticated: bool = False,
        trip_link: str = "",
        card_icon: str = "plane",
    ) -> dict:
        """Build template context dict for the trip page.

        Args:
            itinerary: The Itinerary object to render
            map_data: Pre-computed map data (markers, center, zoom). If None, uses placeholder.

        Returns:
            Context dict for render_template("trip.html", ...)
        """
        if map_data is None:
            map_data = {"center": {"lat": 20, "lng": 0}, "zoom": 2, "markers": [], "pending": True}

        summary_html = self._build_summary_html(itinerary)

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

        return {
            "nav": get_nav_html("trips"),
            "title": html_module.escape(itinerary.title),
            "trip_icon": html_module.escape(card_icon or "plane"),
            "meta_info": html_module.escape(" • ".join(meta_parts)),
            "summary_html": summary_html,
            "column_html": build_column_html(itinerary),
            "calendar_html": build_calendar_html(itinerary),
            "map_data_json": json.dumps(map_data),
            "viewer_buttons_html": _build_viewer_buttons_html(
                is_owner, is_authenticated, trip_link
            ),
            "is_owner_json": "true" if is_owner else "false",
            "is_authenticated_json": "true" if is_authenticated else "false",
        }

    def render_html(
        self,
        itinerary: Itinerary,
        map_data: dict | None = None,
        is_owner: bool = False,
        is_authenticated: bool = False,
        trip_link: str = "",
        card_icon: str = "plane",
    ) -> str:
        """Render trip HTML string (used for static file generation)."""
        from flask import render_template

        ctx = self.build_context(
            itinerary, map_data, is_owner, is_authenticated, trip_link, card_icon
        )
        return render_template("trip.html", **ctx)

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
        """Build a compact HTML summary from itinerary data via Jinja2 template."""
        # Group items by day
        items_by_day: dict[int, list[ItineraryItem]] = {}
        items_without_day: list[ItineraryItem] = []

        for item in itinerary.items:
            if item.day_number:
                if item.day_number not in items_by_day:
                    items_by_day[item.day_number] = []
                items_by_day[item.day_number].append(item)
            else:
                items_without_day.append(item)

        days = []
        for day_num in sorted(items_by_day.keys()):
            items = items_by_day[day_num]
            date_str = ""
            if items and items[0].date:
                date_str = items[0].date.strftime("%B %d")
            days.append(
                {
                    "day_num": day_num,
                    "date_str": date_str,
                    "activities": [self._build_activity_dict(it) for it in items],
                }
            )

        undated_activities = [self._build_activity_dict(it) for it in items_without_day]

        location_names = [loc.name or "Unknown" for loc in itinerary.locations if loc.name]

        return _jinja_env.get_template("summary.html").render(
            title=itinerary.title,
            days=days,
            undated_activities=undated_activities,
            locations=location_names,
        )

    def _build_activity_dict(self, item: ItineraryItem) -> dict:
        """Build a context dict for a single activity for the summary template."""
        time_str = ""
        if item.start_time:
            time_str = item.start_time.strftime("%I:%M %p").lstrip("0")
            if item.end_time:
                end_time_str = item.end_time.strftime("%I:%M %p").lstrip("0")
                if item.category in TRAVEL_CATEGORIES:
                    time_str = f"{time_str} -> {end_time_str}"
                else:
                    time_str = f"{time_str} - {end_time_str}"

        category = item.category or "other"
        title = item.title or "Untitled"
        location = (item.location.name if item.location and item.location.name else "") or ""
        website = item.website_url or ""
        notes = (item.notes or item.description or "")[:200]

        return {
            "title": title,
            "time_str": time_str,
            "location": location,
            "category": category,
            "icon": CATEGORY_ICONS.get(category.lower(), "fa-calendar-day"),
            "website": website,
            "notes": notes,
            "maps_url": item.maps_url,
        }

    # The following methods are delegated to web_view_columns.py.
    # They remain as thin wrappers so any code that calls them on an instance
    # still works without changes.

    def _build_column_html(self, itinerary: Itinerary) -> str:
        """Delegate to standalone build_column_html (defined in web_view_columns.py)."""
        return build_column_html(itinerary)

    def _build_calendar_html(self, itinerary: Itinerary) -> str:
        """Delegate to standalone build_calendar_html (defined in web_view_columns.py)."""
        return build_calendar_html(itinerary)
