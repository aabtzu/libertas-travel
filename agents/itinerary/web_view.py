"""Generate a unified web page with tabs for summary and map using Google Maps."""

from __future__ import annotations

import os
import json
import calendar
from datetime import date, timedelta
from pathlib import Path
from typing import Optional, Union
import html as html_module

from .models import Itinerary, ItineraryItem
from .mapper import ItineraryMapper
from .summarizer import ItinerarySummarizer
from .templates import get_nav_html, get_template


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

        # Generate column view HTML
        column_html = self._build_column_html(itinerary)

        # Generate calendar view HTML
        calendar_html = self._build_calendar_html(itinerary)

        # Build the full HTML
        full_html = get_template("trip.html").format(
            nav_html=get_nav_html("trips"),
            title=html_module.escape(itinerary.title),
            meta_info=html_module.escape(meta_info),
            summary_html=summary_html,
            column_html=column_html,
            calendar_html=calendar_html,
            map_data_json=json.dumps(map_data),
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
                category_icon = self._get_category_html(category)

                # Build data attributes for popup
                title = item.title or "Untitled"
                location = item.location.name if item.location else "Unknown location"
                website = html_module.escape(item.website_url) if item.website_url else ''
                notes = html_module.escape(item.notes or item.description or '')[:200] if (item.notes or item.description) else ''

                lines.append(f'<div class="activity" '
                            f'data-title="{html_module.escape(title)}" '
                            f'data-time="{time_str}" '
                            f'data-location="{html_module.escape(location)}" '
                            f'data-category="{category}" '
                            f'data-website="{website}" '
                            f'data-notes="{notes}">')
                lines.append(f'<span class="activity-category {category}">{category_icon}</span>')
                if time_str:
                    lines.append(f'<span class="activity-time">{time_str}</span>')
                else:
                    lines.append('<span class="activity-time"></span>')

                lines.append('<div class="activity-info">')
                lines.append(f'<span class="activity-title">{html_module.escape(title)}</span>')
                lines.append(f'<span class="activity-location">{html_module.escape(location)}</span>')
                lines.append('</div>')
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
                category_icon = self._get_category_html(category)

                # Build data attributes for popup
                title = item.title or "Untitled"
                location = item.location.name if item.location else "Unknown location"
                website = html_module.escape(item.website_url) if item.website_url else ''
                notes = html_module.escape(item.notes or item.description or '')[:200] if (item.notes or item.description) else ''

                lines.append(f'<div class="activity" '
                            f'data-title="{html_module.escape(title)}" '
                            f'data-time="{time_str}" '
                            f'data-location="{html_module.escape(location)}" '
                            f'data-category="{category}" '
                            f'data-website="{website}" '
                            f'data-notes="{notes}">')
                lines.append(f'<span class="activity-category {category}">{category_icon}</span>')
                if time_str:
                    lines.append(f'<span class="activity-time">{time_str}</span>')
                else:
                    lines.append('<span class="activity-time"></span>')

                lines.append('<div class="activity-info">')
                lines.append(f'<span class="activity-title">{html_module.escape(title)}</span>')
                lines.append(f'<span class="activity-location">{html_module.escape(location)}</span>')
                lines.append('</div>')
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

    def _get_category_icon(self, category: str) -> str:
        """Get Font Awesome icon class for a category."""
        icons = {
            "flight": "fa-plane",
            "hotel": "fa-bed",
            "lodging": "fa-bed",
            "activity": "fa-star",
            "attraction": "fa-landmark",
            "transport": "fa-car",
            "meal": "fa-utensils",
            "home": "fa-home",
            "other": "fa-calendar-day",
        }
        return icons.get(category.lower(), "fa-calendar-day")

    def _get_category_html(self, category: str) -> str:
        """Get icon-based HTML for a category badge."""
        icon = self._get_category_icon(category)
        return f'<i class="fas {icon}"></i>'

    def _build_column_html(self, itinerary: Itinerary) -> str:
        """Build an HTML table view with columns for Travel, Lodging, Activity, Night Stay, Notes."""
        lines = [
            '<div class="column-table-wrapper">',
            '<table class="column-table">',
            '<thead><tr>',
            '<th>Day</th>',
            '<th>Travel</th>',
            '<th>Activity</th>',
            '<th>Night Stay</th>',
            '<th>Notes</th>',
            '</tr></thead>',
            '<tbody>'
        ]

        # Group items by day
        items_by_day: dict[int, list[ItineraryItem]] = {}
        for item in itinerary.items:
            if item.day_number:
                if item.day_number not in items_by_day:
                    items_by_day[item.day_number] = []
                items_by_day[item.day_number].append(item)

        # Track night stay for carry-forward
        last_night_stay: str | None = None
        last_night_stay_item = None  # Track the item for data attributes
        sorted_days = sorted(items_by_day.keys())
        last_day = sorted_days[-1] if sorted_days else 0

        # Render each day as a row
        for day_num in sorted_days:
            items = items_by_day[day_num]

            # Categorize items
            travel_items = []
            lodging_items = []
            activity_items = []
            notes_items = []
            has_flight = False

            for item in items:
                cat = (item.category or "other").lower()
                if cat == "flight":
                    travel_items.append(item)
                    has_flight = True
                elif cat == "transport":
                    travel_items.append(item)
                elif cat in ("hotel", "lodging"):
                    lodging_items.append(item)
                elif cat in ("activity", "attraction", "meal"):
                    activity_items.append(item)
                else:
                    notes_items.append(item)

            # Determine night stay for this day
            current_night_stay: str | None = None
            current_night_stay_item = None  # Track the actual item for data attributes
            is_carried = False
            if lodging_items:
                # Use the last lodging item as the night stay
                # Prefer title (hotel name) over location.name (city)
                current_night_stay_item = lodging_items[-1]
                if current_night_stay_item.title:
                    current_night_stay = current_night_stay_item.title
                elif current_night_stay_item.location and current_night_stay_item.location.name:
                    current_night_stay = current_night_stay_item.location.name
                last_night_stay = current_night_stay
                last_night_stay_item = current_night_stay_item
            elif last_night_stay:
                # Only carry forward if:
                # - Not the last day of the trip
                # - No flight on this day (implies flying home)
                is_last_day = (day_num == last_day)
                if not is_last_day and not has_flight:
                    current_night_stay = last_night_stay
                    current_night_stay_item = last_night_stay_item
                    is_carried = True

            # Get date string
            date_str = ""
            if items and items[0].date:
                date_str = items[0].date.strftime("%b %d")

            lines.append('<tr>')

            # Day column
            day_label = f"Day {day_num}"
            if date_str:
                day_label += f"<br><small>{date_str}</small>"
            lines.append(f'<td style="font-weight:600;white-space:nowrap;">{day_label}</td>')

            # Travel column
            lines.append('<td>')
            for item in travel_items:
                lines.append(self._format_column_item(item))
            lines.append('</td>')

            # Activity column (includes meals)
            lines.append('<td>')
            for item in activity_items:
                lines.append(self._format_column_item(item))
            lines.append('</td>')

            # Night Stay column
            lines.append('<td>')
            if current_night_stay and current_night_stay_item:
                carried_class = " night-stay-carried" if is_carried else ""
                # Build data attributes for popup
                item = current_night_stay_item
                title = html_module.escape(item.title or current_night_stay)
                time_str = ''
                if item.start_time:
                    time_str = item.start_time.strftime('%I:%M %p').lstrip('0')
                loc_name = html_module.escape(item.location.name) if item.location and item.location.name else ''
                website = html_module.escape(item.website_url) if item.website_url else ''
                notes = html_module.escape(item.notes or item.description or '')[:200] if (item.notes or item.description) else ''

                lines.append(f'<div class="night-stay{carried_class}" '
                            f'data-title="{title}" '
                            f'data-time="{time_str}" '
                            f'data-location="{loc_name}" '
                            f'data-category="hotel" '
                            f'data-website="{website}" '
                            f'data-notes="{notes}">')
                lines.append(f'<i class="fas fa-bed"></i>{html_module.escape(current_night_stay)}')
                lines.append('</div>')
            lines.append('</td>')

            # Notes column
            lines.append('<td>')
            for item in notes_items:
                lines.append(self._format_column_item(item))
            lines.append('</td>')

            lines.append('</tr>')

        lines.append('</tbody></table>')
        lines.append('</div>')  # Close column-table-wrapper
        return "\n".join(lines)

    def _format_column_item(self, item: ItineraryItem) -> str:
        """Format a single item for the column view."""
        category = (item.category or "other").lower()
        icon = self._get_category_icon(category)

        # Build data attributes for detail popup
        full_title = html_module.escape(item.title or 'Activity')
        time_str = ''
        if item.start_time:
            time_str = item.start_time.strftime('%I:%M %p').lstrip('0')
            if item.end_time:
                time_str += f' - {item.end_time.strftime("%I:%M %p").lstrip("0")}'
        loc_name = ''
        if item.location and item.location.name:
            loc_name = html_module.escape(item.location.name)
        website = html_module.escape(item.website_url) if item.website_url else ''
        notes = html_module.escape(item.notes or item.description or '')[:200] if (item.notes or item.description) else ''

        parts = [f'<div class="column-item {category}" '
                 f'data-title="{full_title}" '
                 f'data-time="{time_str}" '
                 f'data-location="{loc_name}" '
                 f'data-category="{category}" '
                 f'data-website="{website}" '
                 f'data-notes="{notes}">']

        # Build display text - combine title and location smartly
        title = item.title or "Untitled"
        location_name = item.location.name if item.location else None

        # Check if title already contains the location info or vice versa
        title_lower = title.lower()
        show_location = False
        short_location = None

        if location_name:
            loc_lower = location_name.lower()
            # Extract just the city (first part before comma)
            city = location_name.split(',')[0].strip()
            city_lower = city.lower()

            # Only show location if it adds info not in the title
            if city_lower not in title_lower and loc_lower not in title_lower:
                # Location adds new info - show just the city
                short_location = city
                show_location = True
            elif title_lower in city_lower or city_lower in title_lower:
                # Title and location are basically the same thing
                # Just show title with city context if different
                loc_parts = location_name.split(',')
                if len(loc_parts) > 1:
                    # Add just the region/country for context
                    short_location = loc_parts[1].strip()
                    show_location = True

        # Display title with icon
        parts.append(f'<div class="column-item-title"><i class="fas {icon} column-item-icon"></i> {html_module.escape(title)}</div>')

        # Display time if available
        if item.start_time:
            time_str = item.start_time.strftime("%I:%M %p").lstrip("0")
            parts.append(f'<div class="column-item-time"><i class="fas fa-clock"></i> {time_str}</div>')

        # Display location only if it adds value
        if show_location and short_location:
            parts.append(f'<div class="column-item-location"><i class="fas fa-map-marker-alt"></i> {html_module.escape(short_location)}</div>')

        parts.append('</div>')
        return "\n".join(parts)

    def _build_calendar_html(self, itinerary: Itinerary) -> str:
        """Build a calendar view HTML showing trip days with activities."""
        if not itinerary.start_date or not itinerary.end_date:
            return '''
            <div class="calendar-empty">
                <i class="fas fa-calendar-times"></i>
                <h3>No dates available</h3>
                <p>This itinerary doesn't have date information for a calendar view.</p>
            </div>
            '''

        # Group items by date
        items_by_date = itinerary.items_by_date()

        # Get the range of months to display
        start_date = itinerary.start_date
        end_date = itinerary.end_date

        lines = ['<div class="calendar-view">']

        # Generate calendar for each month in the trip
        current_month = date(start_date.year, start_date.month, 1)
        end_month = date(end_date.year, end_date.month, 1)

        while current_month <= end_month:
            lines.append(self._build_month_calendar(
                current_month.year,
                current_month.month,
                start_date,
                end_date,
                items_by_date
            ))

            # Move to next month
            if current_month.month == 12:
                current_month = date(current_month.year + 1, 1, 1)
            else:
                current_month = date(current_month.year, current_month.month + 1, 1)

        lines.append('</div>')
        return "\n".join(lines)

    def _build_month_calendar(
        self,
        year: int,
        month: int,
        trip_start: date,
        trip_end: date,
        items_by_date: dict[date, list[ItineraryItem]]
    ) -> str:
        """Build a single month calendar grid."""
        month_name = calendar.month_name[month]
        cal = calendar.Calendar(firstweekday=6)  # Start on Sunday

        lines = [
            f'<div class="calendar-month">',
            f'<h3 class="calendar-month-title">{month_name} {year}</h3>',
            '<div class="calendar-grid">',
            '<div class="calendar-header">',
            '<div class="calendar-day-name">Sun</div>',
            '<div class="calendar-day-name">Mon</div>',
            '<div class="calendar-day-name">Tue</div>',
            '<div class="calendar-day-name">Wed</div>',
            '<div class="calendar-day-name">Thu</div>',
            '<div class="calendar-day-name">Fri</div>',
            '<div class="calendar-day-name">Sat</div>',
            '</div>',
            '<div class="calendar-body">'
        ]

        for week in cal.monthdatescalendar(year, month):
            lines.append('<div class="calendar-week">')
            for day_date in week:
                is_trip_day = trip_start <= day_date <= trip_end
                is_current_month = day_date.month == month
                items = items_by_date.get(day_date, [])

                # Determine CSS classes
                classes = ['calendar-day']
                if not is_current_month:
                    classes.append('other-month')
                if is_trip_day:
                    classes.append('trip-day')
                if day_date == trip_start:
                    classes.append('trip-start')
                if day_date == trip_end:
                    classes.append('trip-end')

                lines.append(f'<div class="{" ".join(classes)}">')
                lines.append(f'<div class="calendar-day-number">{day_date.day}</div>')

                if is_trip_day and items:
                    lines.append('<div class="calendar-day-items">')
                    for item in items[:3]:  # Show max 3 items
                        category = (item.category or 'other').lower()
                        title = item.title or 'Activity'
                        full_title = html_module.escape(title)
                        # Truncate long titles for display
                        display_title = title
                        if len(display_title) > 25:
                            display_title = display_title[:22] + '...'
                        # Build tooltip data
                        time_str = ''
                        if item.start_time:
                            time_str = item.start_time.strftime('%I:%M %p').lstrip('0')
                            if item.end_time:
                                time_str += f' - {item.end_time.strftime("%I:%M %p").lstrip("0")}'
                        loc = item.location
                        if loc:
                            location = html_module.escape(str(loc.name) if hasattr(loc, 'name') else str(loc))
                        else:
                            location = ''
                        website = html_module.escape(item.website_url) if item.website_url else ''
                        notes = html_module.escape(item.notes or item.description or '')[:200] if (item.notes or item.description) else ''
                        lines.append(
                            f'<div class="calendar-item {category}" '
                            f'data-title="{full_title}" '
                            f'data-time="{time_str}" '
                            f'data-location="{location}" '
                            f'data-category="{category}" '
                            f'data-website="{website}" '
                            f'data-notes="{notes}">'
                            f'{html_module.escape(display_title)}</div>'
                        )
                    if len(items) > 3:
                        # Build JSON data for hidden items
                        hidden_items = []
                        for item in items[3:]:
                            hi_category = (item.category or 'other').lower()
                            hi_title = item.title or 'Activity'
                            hi_time = ''
                            if item.start_time:
                                hi_time = item.start_time.strftime('%I:%M %p').lstrip('0')
                                if item.end_time:
                                    hi_time += f' - {item.end_time.strftime("%I:%M %p").lstrip("0")}'
                            hi_loc = item.location
                            hi_location = ''
                            if hi_loc:
                                hi_location = str(hi_loc.name) if hasattr(hi_loc, 'name') else str(hi_loc)
                            hidden_items.append({
                                'title': hi_title,
                                'time': hi_time,
                                'location': hi_location,
                                'category': hi_category,
                                'website': item.website_url or '',
                                'notes': (item.notes or item.description or '')[:200]
                            })
                        hidden_json = html_module.escape(json.dumps(hidden_items))
                        lines.append(
                            f'<div class="calendar-item-more" data-hidden-items="{hidden_json}">+{len(items) - 3} more</div>'
                        )
                    lines.append('</div>')

                lines.append('</div>')
            lines.append('</div>')

        lines.append('</div>')  # calendar-body
        lines.append('</div>')  # calendar-grid
        lines.append('</div>')  # calendar-month
        return "\n".join(lines)
