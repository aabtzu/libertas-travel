"""Itinerary conversion utilities: trip data <-> Itinerary object, slugify, date formatting."""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime
from typing import Any


def slugify(text: str) -> str:
    """Convert text to URL-friendly slug."""
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "_", text)
    return text.strip("_")


def format_dates(itinerary) -> str:
    """Format itinerary start/end dates for display."""
    if itinerary.start_date and itinerary.end_date:
        if itinerary.start_date.year == itinerary.end_date.year:
            if itinerary.start_date.month == itinerary.end_date.month:
                return f"{itinerary.start_date.strftime('%B')} {itinerary.start_date.year}"
            return f"{itinerary.start_date.strftime('%b')} - {itinerary.end_date.strftime('%b %Y')}"
        return f"{itinerary.start_date.strftime('%b %Y')} - {itinerary.end_date.strftime('%b %Y')}"
    elif itinerary.start_date:
        return itinerary.start_date.strftime("%B %Y")
    return "Date unknown"


def itinerary_to_data(itinerary) -> dict:
    """Convert a parsed Itinerary object to itinerary_data format for database storage."""
    days_dict = defaultdict(list)
    ideas = []
    start_date = itinerary.start_date

    for item in itinerary.items:
        # is_home_location only controls map rendering (mapper.py skips geocoding
        # for these items). The item should still appear in the itinerary editor
        # so the user can see their departure flight, etc.

        item_data = {
            "title": item.title,
            "category": item.category or "activity",
            "location": item.location.name if item.location else "",
            "latitude": item.location.latitude if item.location else None,
            "longitude": item.location.longitude if item.location else None,
            "time": item.start_time.strftime("%H:%M") if item.start_time else None,
            "notes": item.notes or item.description,
        }

        day_number = item.day_number
        if not day_number and item.date and start_date:
            day_number = (item.date - start_date).days + 1
            if day_number < 1:
                day_number = None

        if day_number:
            days_dict[day_number].append(
                {**item_data, "date": item.date.isoformat() if item.date else None}
            )
        else:
            ideas.append(item_data)

    days = []
    if days_dict:
        # Fill every day number from 1 to the last day that has items.
        # Without this, gaps (e.g. days 2 and 3 when only 1 and 4 have items)
        # are invisible in the editor and can't receive new items.
        max_day = max(days_dict.keys())
        from datetime import timedelta

        for day_num in range(1, max_day + 1):
            day_items = days_dict.get(day_num, [])
            # Compute date from start_date + offset if not embedded in items
            day_date = None
            for it in day_items:
                if it.get("date"):
                    day_date = it["date"]
                    break
            if day_date is None and start_date:
                day_date = (start_date + timedelta(days=day_num - 1)).isoformat()
            days.append({"day_number": day_num, "date": day_date, "items": day_items})

    return {
        "title": itinerary.title,
        "start_date": itinerary.start_date.isoformat() if itinerary.start_date else None,
        "end_date": itinerary.end_date.isoformat() if itinerary.end_date else None,
        "travelers": itinerary.travelers or [],
        "days": days,
        "ideas": ideas,
    }


def _create_itinerary_item(
    item_data: dict[str, Any], day_number: int | None, day_date
) -> Any | None:
    """Create an ItineraryItem from create trip item data."""
    from datetime import time

    from agents.itinerary.models import ItineraryItem, Location

    if not item_data.get("title"):
        return None

    location_data = item_data.get("location", "")
    if isinstance(location_data, dict):
        location_name = location_data.get("name", "") or location_data.get("city", "")
    else:
        location_name = str(location_data) if location_data else ""

    # Restore coordinates if stored (from Google Maps exports or prior geocoding)
    latitude = item_data.get("latitude")
    longitude = item_data.get("longitude")

    location = Location(
        name=location_name,
        address=None,
        location_type=item_data.get("category"),
        latitude=latitude,
        longitude=longitude,
    )

    start_time = None
    time_str = item_data.get("time")
    if time_str and isinstance(time_str, str) and ":" in time_str:
        try:
            parts = time_str.split(":")
            start_time = time(int(parts[0]), int(parts[1]))
        except (ValueError, IndexError):
            pass

    end_time_obj = None
    end_time_str = item_data.get("end_time")
    if end_time_str and isinstance(end_time_str, str) and ":" in end_time_str:
        try:
            parts = end_time_str.split(":")
            end_time_obj = time(int(parts[0]), int(parts[1]))
        except (ValueError, IndexError):
            pass

    category = item_data.get("category", "activity")

    return ItineraryItem(
        title=item_data.get("title", "Untitled"),
        location=location,
        date=day_date,
        start_time=start_time,
        end_time=end_time_obj,
        description=item_data.get("notes"),
        category=category,
        confirmation_number=None,
        notes=item_data.get("notes"),
        day_number=day_number,
        is_home_location=item_data.get("is_home_location", False),
        website_url=item_data.get("website"),
    )


def _convert_to_itinerary(trip: dict[str, Any]):
    """Convert trip data from database to Itinerary object for HTML generation."""
    from agents.itinerary.models import Itinerary

    itinerary_data = trip.get("itinerary_data") or {}

    title = itinerary_data.get("title") or trip.get("title", "Untitled Trip")

    items = []

    days = itinerary_data.get("days", [])
    for day in days:
        day_number = day.get("day_number")
        day_date_str = day.get("date")
        day_date = None
        if day_date_str:
            try:
                day_date = datetime.strptime(day_date_str, "%Y-%m-%d").date()
            except ValueError:
                pass

        for item_data in day.get("items", []):
            item = _create_itinerary_item(item_data, day_number, day_date)
            if item:
                items.append(item)

    ideas = itinerary_data.get("ideas", [])
    for item_data in ideas:
        item = _create_itinerary_item(item_data, None, None)
        if item:
            items.append(item)

    start_date = None
    end_date = None
    if itinerary_data.get("start_date"):
        try:
            start_date = datetime.strptime(itinerary_data["start_date"], "%Y-%m-%d").date()
        except ValueError:
            pass
    if itinerary_data.get("end_date"):
        try:
            end_date = datetime.strptime(itinerary_data["end_date"], "%Y-%m-%d").date()
        except ValueError:
            pass

    return Itinerary(
        title=title,
        items=items,
        start_date=start_date,
        end_date=end_date,
        travelers=itinerary_data.get("travelers", []),
        source_file=None,
    )
