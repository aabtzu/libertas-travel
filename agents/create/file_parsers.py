"""File format parsers: ICS, JSON trip data, Excel, Word documents."""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any


def _normalize_item(item: dict[str, Any]) -> dict[str, Any]:
    """Normalize an item dict to our expected format."""
    normalized = {}

    # Title can be in various fields
    normalized["title"] = (
        item.get("title")
        or item.get("name")
        or item.get("summary")
        or item.get("event")
        or "Untitled"
    )

    # Category normalization
    cat = (item.get("category") or item.get("type") or "").lower()
    if cat in ["flight", "air", "plane"]:
        normalized["category"] = "flight"
    elif cat in ["train", "bus", "car", "transport", "transportation", "transfer"]:
        normalized["category"] = "transport"
    elif cat in ["hotel", "accommodation", "lodging", "stay", "hostel"]:
        normalized["category"] = "hotel"
    elif cat in ["meal", "restaurant", "food", "dining", "breakfast", "lunch", "dinner"]:
        normalized["category"] = "meal"
    elif cat in ["attraction", "sightseeing", "museum", "tour"]:
        normalized["category"] = "attraction"
    elif cat in ["activity", "event"]:
        normalized["category"] = "activity"
    else:
        normalized["category"] = cat or "activity"

    # Date handling
    date = item.get("date") or item.get("start_date") or item.get("startDate")
    if date:
        if isinstance(date, str):
            if len(date) >= 10 and date[4] == "-":
                normalized["date"] = date[:10]
            else:
                for fmt in ["%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%B %d, %Y"]:
                    try:
                        parsed = datetime.strptime(date[:10], fmt)
                        normalized["date"] = parsed.strftime("%Y-%m-%d")
                        break
                    except ValueError:
                        pass

    # Time handling
    time = item.get("time") or item.get("start_time") or item.get("startTime")
    if time:
        if isinstance(time, str):
            if ":" in time and len(time) >= 5:
                normalized["time"] = time[:5]
            elif len(time) == 4 and time.isdigit():
                normalized["time"] = f"{time[:2]}:{time[2:]}"

    # End time handling (for flights, trains, etc.)
    end_time = item.get("end_time") or item.get("endTime") or item.get("arrival_time")
    if end_time:
        if isinstance(end_time, str):
            if ":" in end_time and len(end_time) >= 5:
                normalized["end_time"] = end_time[:5]
            elif len(end_time) == 4 and end_time.isdigit():
                normalized["end_time"] = f"{end_time[:2]}:{end_time[2:]}"

    # Location
    loc = item.get("location")
    if isinstance(loc, dict):
        normalized["location"] = loc.get("name") or loc.get("address") or loc.get("city")
    elif isinstance(loc, str):
        normalized["location"] = loc
    elif item.get("city"):
        normalized["location"] = item.get("city")
    elif item.get("address"):
        normalized["location"] = item.get("address")

    # Notes
    notes = item.get("notes") or item.get("description") or item.get("details")
    if notes:
        normalized["notes"] = str(notes)[:500]

    # Day number if present
    if item.get("day") or item.get("day_number"):
        normalized["day"] = item.get("day") or item.get("day_number")

    return normalized


def _parse_ics_file(file_data: bytes) -> list[dict[str, Any]]:
    """Parse ICS calendar file to extract travel events.

    Returns list of items with title, category, date, time, location, notes.
    """
    try:
        content = file_data.decode("utf-8")
    except UnicodeDecodeError:
        content = file_data.decode("latin-1")

    items = []
    current_event = {}
    in_event = False

    lines = content.replace("\r\n ", "").replace("\r\n\t", "").split("\r\n")
    if len(lines) == 1:
        lines = content.replace("\n ", "").replace("\n\t", "").split("\n")

    for line in lines:
        line = line.strip()
        if line == "BEGIN:VEVENT":
            in_event = True
            current_event = {}
        elif line == "END:VEVENT":
            if current_event.get("title"):
                title = current_event.get("title", "").lower()
                description = current_event.get("notes", "").lower()
                combined = f"{title} {description}"

                category = "activity"
                if any(w in combined for w in ["flight", "airline", "airport", "terminal"]):
                    category = "flight"
                elif any(
                    w in combined
                    for w in ["train", "bus", "car rental", "uber", "taxi", "transfer"]
                ):
                    category = "transport"
                elif any(
                    w in combined
                    for w in [
                        "hotel",
                        "hostel",
                        "airbnb",
                        "accommodation",
                        "check-in",
                        "check in",
                        "stay",
                    ]
                ):
                    category = "hotel"
                elif any(
                    w in combined
                    for w in [
                        "restaurant",
                        "dinner",
                        "lunch",
                        "breakfast",
                        "cafe",
                        "brunch",
                        "reservation",
                    ]
                ):
                    category = "meal"
                elif any(
                    w in combined
                    for w in ["museum", "tour", "visit", "cathedral", "palace", "gallery"]
                ):
                    category = "attraction"

                current_event["category"] = category

                # Use UTC time as fallback if no local time was extracted from description
                if not current_event.get("time") and current_event.get("_utc_time"):
                    current_event["time"] = current_event["_utc_time"]

                current_event.pop("_utc_time", None)
                items.append(current_event)
            in_event = False
        elif in_event:
            if line.startswith("SUMMARY:"):
                current_event["title"] = line[8:].strip()
            elif line.startswith("DTSTART"):
                value = line.split(":", 1)[-1]
                if "T" in value:
                    date_part = value[:8]
                    time_part = value[9:13] if len(value) > 12 else None
                    try:
                        current_event["date"] = f"{date_part[:4]}-{date_part[4:6]}-{date_part[6:8]}"
                        if time_part:
                            current_event["_utc_time"] = f"{time_part[:2]}:{time_part[2:4]}"
                    except (ValueError, IndexError):
                        pass
                else:
                    try:
                        current_event["date"] = f"{value[:4]}-{value[4:6]}-{value[6:8]}"
                    except (ValueError, IndexError):
                        pass
            elif line.startswith("LOCATION:"):
                current_event["location"] = line[9:].strip()
            elif line.startswith("DESCRIPTION:"):
                desc = line[12:].strip()
                desc = desc.replace("\\n", "\n").replace("\\,", ",").replace("\\;", ";")
                current_event["notes"] = desc[:500]

                # Extract local departure time from description (more accurate than UTC)
                time_match = re.search(
                    r"(?:Departure time|Departs?):\s*(\d{1,2}):(\d{2})", desc, re.IGNORECASE
                )
                if time_match:
                    hour = int(time_match.group(1))
                    minute = time_match.group(2)
                    current_event["time"] = f"{hour:02d}:{minute}"

    return items


def _parse_json_trip(file_data: bytes) -> list[dict[str, Any]]:
    """Parse JSON file that might contain trip data.

    Handles various JSON formats:
    - Our own export format with itinerary_data
    - Our own itinerary format with items array
    - Array of events
    - TripIt-style JSON exports
    """
    try:
        content = file_data.decode("utf-8")
    except UnicodeDecodeError:
        content = file_data.decode("latin-1")

    data = json.loads(content)
    items = []

    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                items.append(_normalize_item(item))
    elif isinstance(data, dict):
        if "export_version" in data and "itinerary_data" in data:
            itinerary_data = data.get("itinerary_data", {})
            for day in itinerary_data.get("days", []):
                day_num = day.get("day_number") or day.get("day")
                day_date = day.get("date")
                for item in day.get("items", []):
                    normalized = _normalize_item(item)
                    if day_num and not normalized.get("day"):
                        normalized["day"] = day_num
                    if day_date and not normalized.get("date"):
                        normalized["date"] = day_date
                    items.append(normalized)
            for item in itinerary_data.get("ideas", []):
                items.append(_normalize_item(item))
        elif "items" in data:
            for item in data.get("items", []):
                if isinstance(item, dict):
                    items.append(_normalize_item(item))
        elif "days" in data:
            for day in data.get("days", []):
                day_num = day.get("day_number") or day.get("day")
                day_date = day.get("date")
                for item in day.get("items", []):
                    normalized = _normalize_item(item)
                    if day_num and not normalized.get("day"):
                        normalized["day"] = day_num
                    if day_date and not normalized.get("date"):
                        normalized["date"] = day_date
                    items.append(normalized)
        elif "itinerary_data" in data:
            return _parse_json_trip(json.dumps(data["itinerary_data"]).encode())
        elif "events" in data:
            for item in data.get("events", []):
                if isinstance(item, dict):
                    items.append(_normalize_item(item))

    # Smart day assignment: if no items have dates but some have times,
    # this is likely a single-day itinerary - assign all to Day 1
    has_any_date = any(item.get("date") for item in items)
    has_any_time = any(item.get("time") for item in items)
    has_any_day = any(item.get("day") for item in items)

    if not has_any_date and not has_any_day and has_any_time:
        for item in items:
            item["day"] = 1

    return items


def _parse_excel_to_text(file_data: bytes, ext: str) -> str:
    """Parse Excel file and convert to text table for LLM processing."""
    from io import BytesIO

    try:
        import openpyxl
    except ImportError as e:
        raise ImportError("openpyxl not installed") from e

    text_parts = []

    if ext == "xlsx":
        wb = openpyxl.load_workbook(BytesIO(file_data), data_only=True)

        for sheet_name in wb.sheetnames:
            sheet = wb[sheet_name]
            text_parts.append(f"=== Sheet: {sheet_name} ===\n")

            rows = list(sheet.iter_rows(values_only=True))
            if not rows:
                continue

            header_row = None
            for i, row in enumerate(rows):
                if any(cell is not None for cell in row):
                    header_row = i
                    break

            if header_row is None:
                continue

            for row in rows[header_row:]:
                row_text = [str(cell) if cell is not None else "" for cell in row]
                if any(row_text):
                    text_parts.append(" | ".join(row_text))

            text_parts.append("")

        wb.close()
    elif ext == "xls":
        try:
            import xlrd

            wb = xlrd.open_workbook(file_contents=file_data)

            for sheet_name in wb.sheet_names():
                sheet = wb.sheet_by_name(sheet_name)
                text_parts.append(f"=== Sheet: {sheet_name} ===\n")

                for row_idx in range(sheet.nrows):
                    row_text = [
                        str(sheet.cell_value(row_idx, col_idx)) or ""
                        for col_idx in range(sheet.ncols)
                    ]
                    if any(row_text):
                        text_parts.append(" | ".join(row_text))

                text_parts.append("")
        except ImportError as e:
            raise ImportError("xlrd not installed for .xls files") from e

    return "\n".join(text_parts)


def _parse_word_to_text(file_data: bytes, ext: str) -> str:
    """Parse Word document and extract text for LLM processing."""
    from io import BytesIO

    if ext == "docx":
        try:
            from docx import Document
        except ImportError as e:
            raise ImportError("python-docx not installed") from e

        doc = Document(BytesIO(file_data))
        text_parts = []

        for para in doc.paragraphs:
            if para.text.strip():
                text_parts.append(para.text)

        for table in doc.tables:
            text_parts.append("\n--- Table ---")
            for row in table.rows:
                row_text = [cell.text.strip() for cell in row.cells]
                text_parts.append(" | ".join(row_text))

        return "\n".join(text_parts)

    elif ext == "doc":
        raise ValueError("Legacy .doc format not supported. Please save as .docx")
