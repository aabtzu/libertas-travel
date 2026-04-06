"""ICS calendar file generation from trip data."""

from __future__ import annotations

from datetime import datetime


def generate_ics(export_data: dict, link: str) -> str:
    """Generate ICS calendar format from trip export data."""
    title = export_data.get("title", "Trip")
    itinerary_data = export_data.get("itinerary_data", {})
    days = itinerary_data.get("days", [])

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Libertas Travel//Trip Planner//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{_ics_escape(title)}",
    ]

    event_count = 0
    for day in days:
        day_date = day.get("date")
        if not day_date:
            continue

        for item in day.get("items", []):
            event_count += 1
            item_title = item.get("title", "Activity")
            item_time = item.get("time")
            item_end_time = item.get("end_time")
            item_location = item.get("location", "")
            item_notes = item.get("notes", "")
            item_category = item.get("category", "activity")
            item_website = item.get("website", "")

            uid = f"{link}-{day_date}-{event_count}@libertas.app"

            if item_time:
                dt_start = f"{day_date.replace('-', '')}T{item_time.replace(':', '')}00"
                dt_end = (
                    f"{day_date.replace('-', '')}T{item_end_time.replace(':', '')}00"
                    if item_end_time
                    else _add_hour_to_ics_time(dt_start)
                )
                dtstart_line = f"DTSTART:{dt_start}"
                dtend_line = f"DTEND:{dt_end}"
            else:
                dtstart_line = f"DTSTART;VALUE=DATE:{day_date.replace('-', '')}"
                dtend_line = f"DTEND;VALUE=DATE:{day_date.replace('-', '')}"

            desc_parts = []
            if item_category:
                desc_parts.append(f"Category: {item_category.title()}")
            if item_notes:
                desc_parts.append(item_notes)
            if item_website:
                desc_parts.append(f"Website: {item_website}")
            description = "\\n".join(desc_parts)

            lines.extend(
                [
                    "BEGIN:VEVENT",
                    f"UID:{uid}",
                    f"DTSTAMP:{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}",
                    dtstart_line,
                    dtend_line,
                    f"SUMMARY:{_ics_escape(item_title)}",
                ]
            )

            if item_location:
                lines.append(f"LOCATION:{_ics_escape(item_location)}")
            if description:
                lines.append(f"DESCRIPTION:{_ics_escape(description)}")

            lines.append("END:VEVENT")

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines)


def _ics_escape(text: str) -> str:
    """Escape special characters for ICS format."""
    if not text:
        return ""
    text = text.replace("\\", "\\\\")
    text = text.replace(";", "\\;")
    text = text.replace(",", "\\,")
    text = text.replace("\n", "\\n")
    text = text.replace("\r", "")
    return text


def _add_hour_to_ics_time(dt_str: str) -> str:
    """Add one hour to an ICS datetime string (YYYYMMDDTHHMMSS)."""
    time_part = dt_str.split("T")[1] if "T" in dt_str else "000000"
    date_part = dt_str.split("T")[0] if "T" in dt_str else dt_str
    hour = int(time_part[0:2])
    minute = time_part[2:4]
    second = time_part[4:6] if len(time_part) >= 6 else "00"
    hour = (hour + 1) % 24
    return f"{date_part}T{hour:02d}{minute}{second}"
