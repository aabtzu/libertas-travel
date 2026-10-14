"""Column and calendar HTML rendering for the trip web view.

Standalone functions extracted from ItineraryWebView to keep file sizes
under the project limit. Called from web_view.py.
"""

from __future__ import annotations

import calendar
import json
from datetime import date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from agents.common.categories import CATEGORY_ICONS, TRAVEL_CATEGORIES

from .models import Itinerary, ItineraryItem

_TEMPLATE_DIR = Path(__file__).parent / "templates"
_jinja_env = Environment(loader=FileSystemLoader(_TEMPLATE_DIR), autoescape=True)


def _get_category_icon(category: str) -> str:
    return CATEGORY_ICONS.get(category.lower(), "fa-calendar-day")


def _item_time_str(item: ItineraryItem) -> str:
    if not item.start_time:
        return ""
    t = item.start_time.strftime("%I:%M %p").lstrip("0")
    if item.end_time:
        t += f" - {item.end_time.strftime('%I:%M %p').lstrip('0')}"
    return t


def _item_context(item: ItineraryItem) -> dict:
    """Compute display context dict for a single column-view item."""
    category = (item.category or "other").lower()
    title = item.title or "Untitled"
    location_name = item.location.name if item.location else None

    show_location = False
    short_location = ""
    if location_name:
        title_lower = title.lower()
        loc_lower = location_name.lower()
        city = location_name.split(",")[0].strip()
        city_lower = city.lower()
        if city_lower not in title_lower and loc_lower not in title_lower:
            short_location = city
            show_location = True
        elif title_lower in city_lower or city_lower in title_lower:
            parts = location_name.split(",")
            if len(parts) > 1:
                short_location = parts[1].strip()
                show_location = True

    time_str = _item_time_str(item)
    return {
        "category": category,
        "icon": _get_category_icon(category),
        "full_title": item.title or "Activity",
        "display_title": title,
        "time_str": time_str,
        "loc_name": location_name or "",
        "website": item.website_url or "",
        "notes": (item.notes or item.description or "")[:200],
        "show_location": show_location,
        "short_location": short_location,
        "maps_url": item.maps_url,
    }


def _night_stay_context(item: ItineraryItem, text: str, is_carried: bool) -> dict:
    """Compute display context for a night-stay cell."""
    time_str = _item_time_str(item)
    return {
        "text": text,
        "is_carried": is_carried,
        "title": item.title or text,
        "time_str": time_str,
        "loc_name": item.location.name if item.location and item.location.name else "",
        "website": item.website_url or "",
        "notes": (item.notes or item.description or "")[:200],
    }


def _compute_column_days(itinerary: Itinerary) -> list[dict]:
    """Build structured day data for the column (grid) view template."""
    items_by_day: dict[int, list[ItineraryItem]] = {}
    for item in itinerary.items:
        if item.day_number:
            items_by_day.setdefault(item.day_number, []).append(item)

    sorted_days = sorted(items_by_day.keys())
    last_day = sorted_days[-1] if sorted_days else 0
    last_night_stay: str | None = None
    last_night_stay_item: ItineraryItem | None = None

    days = []
    for day_num in sorted_days:
        items = items_by_day[day_num]

        travel_items, lodging_items, activity_items, notes_items = [], [], [], []
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

        current_night_stay_item: ItineraryItem | None = None
        current_night_stay: str | None = None
        is_carried = False
        if lodging_items:
            current_night_stay_item = lodging_items[-1]
            if current_night_stay_item.title:
                current_night_stay = current_night_stay_item.title
            elif current_night_stay_item.location and current_night_stay_item.location.name:
                current_night_stay = current_night_stay_item.location.name
            last_night_stay = current_night_stay
            last_night_stay_item = current_night_stay_item
        elif last_night_stay and day_num != last_day and not has_flight:
            current_night_stay = last_night_stay
            current_night_stay_item = last_night_stay_item
            is_carried = True

        date_str = items[0].date.strftime("%b %d") if items and items[0].date else ""

        night_stay = None
        if current_night_stay and current_night_stay_item:
            night_stay = _night_stay_context(
                current_night_stay_item, current_night_stay, is_carried
            )

        days.append(
            {
                "day_num": day_num,
                "date_str": date_str,
                "travel_items": [_item_context(i) for i in travel_items],
                "activity_items": [_item_context(i) for i in activity_items],
                "notes_items": [_item_context(i) for i in notes_items],
                "night_stay": night_stay,
            }
        )
    return days


def build_column_html(itinerary: Itinerary) -> str:
    """Render the grid/column view for a trip."""
    days = _compute_column_days(itinerary)
    return _jinja_env.get_template("column.html").render(days=days)


def _calendar_item_context(item: ItineraryItem) -> dict:
    """Compute context for a single calendar cell item."""
    category = (item.category or "other").lower()
    title = item.title or "Activity"
    display_title = title[:22] + "..." if len(title) > 25 else title
    loc = item.location
    location = (str(loc.name) if hasattr(loc, "name") else str(loc)) if loc else ""
    return {
        "category": category,
        "full_title": title,
        "display_title": display_title,
        "time_str": _item_time_str(item),
        "location": location,
        "website": item.website_url or "",
        "notes": (item.notes or item.description or "")[:200],
    }


def _compute_calendar_months(itinerary: Itinerary) -> list[dict]:
    """Build structured month data for the calendar view template."""
    if not itinerary.start_date or not itinerary.end_date:
        return []

    items_by_date = itinerary.items_by_date()
    start_date = itinerary.start_date
    end_date = itinerary.end_date

    months = []
    current_month = date(start_date.year, start_date.month, 1)
    end_month = date(end_date.year, end_date.month, 1)

    while current_month <= end_month:
        year, month = current_month.year, current_month.month
        cal = calendar.Calendar(firstweekday=6)

        weeks = []
        for week in cal.monthdatescalendar(year, month):
            week_data = []
            for day_date in week:
                is_trip_day = start_date <= day_date <= end_date
                is_current_month = day_date.month == month
                all_items = items_by_date.get(day_date, [])

                classes = ["calendar-day"]
                if not is_current_month:
                    classes.append("other-month")
                if is_trip_day:
                    classes.append("trip-day")
                if day_date == start_date:
                    classes.append("trip-start")
                if day_date == end_date:
                    classes.append("trip-end")

                visible_items = []
                hidden_items_json = "[]"
                extra_count = 0
                if is_trip_day and all_items:
                    visible_items = [_calendar_item_context(i) for i in all_items[:3]]
                    if len(all_items) > 3:
                        extra_count = len(all_items) - 3
                        hidden = []
                        for item in all_items[3:]:
                            cat = (item.category or "other").lower()
                            hi_time = _item_time_str(item)
                            hi_loc = item.location
                            hi_location = (
                                (str(hi_loc.name) if hasattr(hi_loc, "name") else str(hi_loc))
                                if hi_loc
                                else ""
                            )
                            hidden.append(
                                {
                                    "title": item.title or "Activity",
                                    "time": hi_time,
                                    "location": hi_location,
                                    "category": cat,
                                    "website": item.website_url or "",
                                    "notes": (item.notes or item.description or "")[:200],
                                }
                            )
                        hidden_items_json = json.dumps(hidden)

                week_data.append(
                    {
                        "date": day_date,
                        "day": day_date.day,
                        "classes": " ".join(classes),
                        "cal_items": visible_items,
                        "extra_count": extra_count,
                        "hidden_items_json": hidden_items_json,
                    }
                )
            weeks.append(week_data)

        months.append(
            {
                "year": year,
                "month": month,
                "month_name": calendar.month_name[month],
                "weeks": weeks,
            }
        )

        if current_month.month == 12:
            current_month = date(current_month.year + 1, 1, 1)
        else:
            current_month = date(current_month.year, current_month.month + 1, 1)

    return months


def build_calendar_html(itinerary: Itinerary) -> str:
    """Render the calendar view for a trip."""
    months = _compute_calendar_months(itinerary)
    if not months:
        return """
        <div class="calendar-empty">
            <i class="fas fa-calendar-times"></i>
            <h3>No dates available</h3>
            <p>This itinerary doesn't have date information for a calendar view.</p>
        </div>
        """
    return _jinja_env.get_template("calendar.html").render(months=months)
