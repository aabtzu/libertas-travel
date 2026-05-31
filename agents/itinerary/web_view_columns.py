"""Column and calendar HTML rendering for the trip web view.

Standalone functions extracted from ItineraryWebView to keep file sizes
under the project limit. Called from web_view.py.
"""

from __future__ import annotations

import calendar
import html as html_module
import json
from datetime import date

from agents.common.categories import CATEGORY_ICONS, TRAVEL_CATEGORIES

from .models import Itinerary, ItineraryItem


def _get_category_icon(category: str) -> str:
    """Get Font Awesome icon class for a category.

    Uses the canonical mapping from agents.common.categories.
    """
    return CATEGORY_ICONS.get(category.lower(), "fa-calendar-day")


def build_column_html(itinerary: Itinerary) -> str:
    """Build an HTML table view with columns for Travel, Lodging, Activity, Night Stay, Notes."""
    lines = [
        '<div class="column-table-wrapper">',
        '<table class="column-table">',
        "<thead><tr>",
        "<th>Day</th>",
        "<th>Travel</th>",
        "<th>Activity</th>",
        "<th>Night Stay</th>",
        "<th>Notes</th>",
        "</tr></thead>",
        "<tbody>",
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
            elif cat in TRAVEL_CATEGORIES:
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
            # Use the last lodging item as the night stay.
            # Prefer title (hotel name) over location.name (city).
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
            is_last_day = day_num == last_day
            if not is_last_day and not has_flight:
                current_night_stay = last_night_stay
                current_night_stay_item = last_night_stay_item
                is_carried = True

        # Get date string
        date_str = ""
        if items and items[0].date:
            date_str = items[0].date.strftime("%b %d")

        lines.append("<tr>")

        # Day column
        day_label = f"Day {day_num}"
        if date_str:
            day_label += f"<br><small>{date_str}</small>"
        lines.append(f'<td style="font-weight:600;white-space:nowrap;">{day_label}</td>')

        # Travel column
        lines.append("<td>")
        for item in travel_items:
            lines.append(format_column_item(item))
        lines.append("</td>")

        # Activity column (includes meals)
        lines.append("<td>")
        for item in activity_items:
            lines.append(format_column_item(item))
        lines.append("</td>")

        # Night Stay column
        lines.append("<td>")
        if current_night_stay and current_night_stay_item:
            carried_class = " night-stay-carried" if is_carried else ""
            # Build data attributes for popup
            item = current_night_stay_item
            title = html_module.escape(item.title or current_night_stay)
            time_str = ""
            if item.start_time:
                time_str = item.start_time.strftime("%I:%M %p").lstrip("0")
            loc_name = (
                html_module.escape(item.location.name)
                if item.location and item.location.name
                else ""
            )
            website = html_module.escape(item.website_url) if item.website_url else ""
            notes = (
                html_module.escape(item.notes or item.description or "")[:200]
                if (item.notes or item.description)
                else ""
            )

            lines.append(
                f'<div class="night-stay{carried_class}" '
                f'data-title="{title}" '
                f'data-time="{time_str}" '
                f'data-location="{loc_name}" '
                f'data-category="hotel" '
                f'data-website="{website}" '
                f'data-notes="{notes}">'
            )
            lines.append(f'<i class="fas fa-bed"></i>{html_module.escape(current_night_stay)}')
            lines.append("</div>")
        lines.append("</td>")

        # Notes column
        lines.append("<td>")
        for item in notes_items:
            lines.append(format_column_item(item))
        lines.append("</td>")

        lines.append("</tr>")

    lines.append("</tbody></table>")
    lines.append("</div>")  # Close column-table-wrapper
    return "\n".join(lines)


def format_column_item(item: ItineraryItem) -> str:
    """Format a single item for the column view."""
    category = (item.category or "other").lower()
    icon = _get_category_icon(category)

    # Build data attributes for detail popup
    full_title = html_module.escape(item.title or "Activity")
    time_str = ""
    if item.start_time:
        time_str = item.start_time.strftime("%I:%M %p").lstrip("0")
        if item.end_time:
            time_str += f" - {item.end_time.strftime('%I:%M %p').lstrip('0')}"
    loc_name = ""
    if item.location and item.location.name:
        loc_name = html_module.escape(item.location.name)
    website = html_module.escape(item.website_url) if item.website_url else ""
    notes = (
        html_module.escape(item.notes or item.description or "")[:200]
        if (item.notes or item.description)
        else ""
    )

    parts = [
        f'<div class="column-item {category}" '
        f'data-title="{full_title}" '
        f'data-time="{time_str}" '
        f'data-location="{loc_name}" '
        f'data-category="{category}" '
        f'data-website="{website}" '
        f'data-notes="{notes}">'
    ]

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
        city = location_name.split(",")[0].strip()
        city_lower = city.lower()

        # Only show location if it adds info not in the title
        if city_lower not in title_lower and loc_lower not in title_lower:
            # Location adds new info - show just the city
            short_location = city
            show_location = True
        elif title_lower in city_lower or city_lower in title_lower:
            # Title and location are basically the same thing.
            # Add just the region/country for context if available.
            loc_parts = location_name.split(",")
            if len(loc_parts) > 1:
                short_location = loc_parts[1].strip()
                show_location = True

    # Display title with icon
    parts.append(
        f'<div class="column-item-title"><i class="fas {icon} column-item-icon"></i> {html_module.escape(title)}</div>'
    )

    # Display time if available
    if item.start_time:
        time_display = item.start_time.strftime("%I:%M %p").lstrip("0")
        if item.end_time:
            end_time_str = item.end_time.strftime("%I:%M %p").lstrip("0")
            # For flights/transport, use arrow; for others use dash
            if category in ("flight", "transport"):
                time_display = f"{time_display} → {end_time_str}"
            else:
                time_display = f"{time_display} - {end_time_str}"
        parts.append(
            f'<div class="column-item-time"><i class="fas fa-clock"></i> {time_display}</div>'
        )

    # Display location only if it adds value
    if show_location and short_location:
        parts.append(
            f'<div class="column-item-location"><i class="fas fa-map-marker-alt"></i> {html_module.escape(short_location)}</div>'
        )

    parts.append("</div>")
    return "\n".join(parts)


def build_calendar_html(itinerary: Itinerary) -> str:
    """Build a calendar view HTML showing trip days with activities."""
    if not itinerary.start_date or not itinerary.end_date:
        return """
        <div class="calendar-empty">
            <i class="fas fa-calendar-times"></i>
            <h3>No dates available</h3>
            <p>This itinerary doesn't have date information for a calendar view.</p>
        </div>
        """

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
        lines.append(
            build_month_calendar(
                current_month.year, current_month.month, start_date, end_date, items_by_date
            )
        )

        # Move to next month
        if current_month.month == 12:
            current_month = date(current_month.year + 1, 1, 1)
        else:
            current_month = date(current_month.year, current_month.month + 1, 1)

    lines.append("</div>")
    return "\n".join(lines)


def build_month_calendar(
    year: int,
    month: int,
    trip_start: date,
    trip_end: date,
    items_by_date: dict[date, list[ItineraryItem]],
) -> str:
    """Build a single month calendar grid."""
    month_name = calendar.month_name[month]
    cal = calendar.Calendar(firstweekday=6)  # Start on Sunday

    lines = [
        '<div class="calendar-month">',
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
        "</div>",
        '<div class="calendar-body">',
    ]

    for week in cal.monthdatescalendar(year, month):
        lines.append('<div class="calendar-week">')
        for day_date in week:
            is_trip_day = trip_start <= day_date <= trip_end
            is_current_month = day_date.month == month
            items = items_by_date.get(day_date, [])

            # Determine CSS classes
            classes = ["calendar-day"]
            if not is_current_month:
                classes.append("other-month")
            if is_trip_day:
                classes.append("trip-day")
            if day_date == trip_start:
                classes.append("trip-start")
            if day_date == trip_end:
                classes.append("trip-end")

            lines.append(f'<div class="{" ".join(classes)}">')
            lines.append(f'<div class="calendar-day-number">{day_date.day}</div>')

            if is_trip_day and items:
                lines.append('<div class="calendar-day-items">')
                for item in items[:3]:  # Show max 3 items
                    category = (item.category or "other").lower()
                    title = item.title or "Activity"
                    full_title = html_module.escape(title)
                    # Truncate long titles for display
                    display_title = title
                    if len(display_title) > 25:
                        display_title = display_title[:22] + "..."
                    # Build tooltip data
                    time_str = ""
                    if item.start_time:
                        time_str = item.start_time.strftime("%I:%M %p").lstrip("0")
                        if item.end_time:
                            time_str += f" - {item.end_time.strftime('%I:%M %p').lstrip('0')}"
                    loc = item.location
                    if loc:
                        location = html_module.escape(
                            str(loc.name) if hasattr(loc, "name") else str(loc)
                        )
                    else:
                        location = ""
                    website = html_module.escape(item.website_url) if item.website_url else ""
                    notes = (
                        html_module.escape(item.notes or item.description or "")[:200]
                        if (item.notes or item.description)
                        else ""
                    )
                    lines.append(
                        f'<div class="calendar-item {category}" '
                        f'data-title="{full_title}" '
                        f'data-time="{time_str}" '
                        f'data-location="{location}" '
                        f'data-category="{category}" '
                        f'data-website="{website}" '
                        f'data-notes="{notes}">'
                        f"{html_module.escape(display_title)}</div>"
                    )
                if len(items) > 3:
                    # Build JSON data for hidden items
                    hidden_items = []
                    for item in items[3:]:
                        hi_category = (item.category or "other").lower()
                        hi_title = item.title or "Activity"
                        hi_time = ""
                        if item.start_time:
                            hi_time = item.start_time.strftime("%I:%M %p").lstrip("0")
                            if item.end_time:
                                hi_time += f" - {item.end_time.strftime('%I:%M %p').lstrip('0')}"
                        hi_loc = item.location
                        hi_location = ""
                        if hi_loc:
                            hi_location = (
                                str(hi_loc.name) if hasattr(hi_loc, "name") else str(hi_loc)
                            )
                        hidden_items.append(
                            {
                                "title": hi_title,
                                "time": hi_time,
                                "location": hi_location,
                                "category": hi_category,
                                "website": item.website_url or "",
                                "notes": (item.notes or item.description or "")[:200],
                            }
                        )
                    hidden_json = html_module.escape(json.dumps(hidden_items))
                    lines.append(
                        f'<div class="calendar-item-more" data-hidden-items="{hidden_json}">+{len(items) - 3} more</div>'
                    )
                lines.append("</div>")

            lines.append("</div>")
        lines.append("</div>")

    lines.append("</div>")  # calendar-body
    lines.append("</div>")  # calendar-grid
    lines.append("</div>")  # calendar-month
    return "\n".join(lines)
