"""Upload handlers: file uploads, URL imports, itinerary parsing pipeline."""

from __future__ import annotations

import json
import os
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any

import database as db
from agents.common.llm import SONNET, make_llm
from agents.create.file_parsers import (
    SUPPORTED_EXTENSIONS,
    extract_file_content,
)
from agents.create.flight_utils import parse_google_flights_url
from agents.create.itinerary_utils import format_dates, itinerary_to_data, slugify
from agents.create.web_utils import download_from_url, extract_text_from_html

OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", Path(__file__).parent.parent.parent / "output"))


def _parse_json_with_recovery(text: str) -> list[dict]:
    """Parse a JSON array from LLM output, recovering from truncated responses.

    When max_tokens is hit mid-stream the JSON array is cut off.  We try a
    clean parse first; if that fails we trim back to the last complete object
    (last `}`) and close the array so we keep whatever items were fully output.
    """
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Find the last complete object boundary and close the array
        last_brace = text.rfind("}")
        if last_brace == -1:
            raise  # nothing recoverable
        recovered = text[: last_brace + 1] + "\n]"
        result = json.loads(recovered)  # raises if still invalid
        print(f"[UPLOAD] Recovered truncated JSON, kept {len(result)} items")
        return result


def upload_plan_handler(user_id: int, filename: str, file_data: bytes, ext: str) -> dict[str, Any]:
    """Handle uploaded file and extract trip items using LLM.

    Returns extracted items or error.
    """
    extracted = extract_file_content(file_data, ext)

    if "error" in extracted:
        return {"error": extracted["error"]}, 400

    # ICS/JSON fast path, items already parsed, skip LLM
    if "items" in extracted:
        return {"success": True, "items": extracted["items"], "filename": filename}, 200

    content_for_llm = extracted.get("text")
    image_data = extracted.get("image_data")
    media_type = extracted.get("media_type")

    current_year = datetime.now().year
    current_date = datetime.now().strftime("%Y-%m-%d")
    next_year = current_year + 1

    system_prompt = f"""You are a travel document parser. Extract travel-related items from the uploaded document.

Today's date is {current_date}.

For each item you find, extract:
- title: A clear name for the item (e.g., "LH 2416 MUC → ARN", "Hotel Duomo Firenze", "Hertz Rental Car", "Rafting Class V Inferno Canyon")
- category: One of: flight, transport, train, bus, hotel, meal, activity, attraction, other
- date: The start/pickup date in YYYY-MM-DD format. CRITICAL: When the year is not shown, use the NEXT occurrence of that date:
  * If the month/day is still upcoming this year, use {current_year}
  * If the month/day has already passed this year, use {next_year}
  * Example: Today is {current_date}. "Apr 23" means {current_year}-04-23 (April is after January). "Jan 5" means {next_year}-01-05 (Jan 5 already passed).
- day: Day number (1, 2, 3...) if the document uses "Day 1", "Day 2" format
- end_date: The end/return/dropoff date in YYYY-MM-DD format (for car rentals, hotels)
- time: Start/departure/pickup time (HH:MM format, 24-hour)
- end_time: End/arrival/dropoff time if available (HH:MM format, 24-hour)
- location: City or address (pickup location for rentals, destination airport CODE for flights - keep as IATA code like "BIH", do NOT expand to city name)
- latitude: Latitude coordinate if present in the source data (decimal number like 48.8566). Only include if the source data explicitly contains coordinates.
- longitude: Longitude coordinate if present in the source data (decimal number like 2.2945). Only include if the source data explicitly contains coordinates.
- notes: Any additional relevant details (confirmation numbers, vehicle type, drop-off location if different, etc.)

For FLIGHTS and TRAINS: Always extract both departure time (time) and arrival time (end_time) if shown.
For FLIGHTS: Keep airport IATA codes as-is (e.g., "DEN", "BIH", "LAX"). Do NOT try to expand airport codes to city names - just use the 3-letter code.
For CAR RENTALS: Extract pickup date/time as date/time, drop-off date/time as end_date/end_time. Include confirmation number and vehicle type in notes.

IMPORTANT: For DAY-BY-DAY NARRATIVE ITINERARIES (expedition, adventure, tour itineraries):
- Extract EACH activity mentioned in the daily descriptions as a separate item
- Look for: rafting, kayaking, hiking, yoga, meals, scenic drives, flights, transfers, etc.
- Use category "activity" for adventure activities (rafting, hiking, kayaking, etc.)
- Use category "meal" for specific meals mentioned (welcome dinner, farewell breakfast, etc.)
- Use category "train" for any train (AVE, TGV, Eurostar, Amtrak, regional rail, etc.)
- Use category "bus" for buses or coaches
- Use category "transport" for car drives, rentals, and transfers only
- Use category "flight" for flights
- Include the day number from "Day 1", "Day 2", etc.

IMPORTANT: For ARTICLES, BLOG POSTS, GUIDES, or RECOMMENDATION LISTS (no bookings, no concrete dates):
- This is the "ideas-pile" case. Extract every named place worth visiting as a separate item.
- Each restaurant, hotel, neighborhood, attraction, museum, bar, viewpoint, beach, market, etc. mentioned by name becomes one item.
- Set date, time, end_time, end_date, day to null, these will land in the user's Ideas pile to schedule later.
- Use the right category (meal for restaurants/cafes/bars, hotel for accommodations, attraction for museums/landmarks, activity for hiking/tours, etc.).
- Put the city or neighborhood in location.
- Put a one-line description in notes (what makes this place worth visiting, per the article).
- Skip generic guidance like "try the local cuisine" or "stay near the center", we want named places only.
- An article with 10 places mentioned should return 10 items, not 0.

Return your response as a JSON array of items. Example:
```json
[
  {{
    "title": "LH 2416 MUC → ARN",
    "category": "flight",
    "date": "2025-12-17",
    "time": "12:10",
    "end_time": "14:25",
    "location": "ARN",
    "notes": "Lufthansa, Airbus A321, Economy, 2h 15m nonstop"
  }},
  {{
    "title": "Class V Inferno Canyon Rafting",
    "category": "activity",
    "date": "2026-01-11",
    "day": 4,
    "location": "Futaleufu, Chile",
    "latitude": -43.1833,
    "longitude": -71.8667,
    "notes": "Three-mile canyon of Class V whitewater"
  }}
]
```

If you cannot extract any travel items, return an empty array: []
Only return the JSON array, no other text."""

    try:
        # 4096 tokens accommodates large trips (20+ items); 2048 caused truncation
        llm = make_llm(model=SONNET, max_tokens=4096)

        if image_data:
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": image_data,
                            },
                        },
                        {
                            "type": "text",
                            "text": f"Extract travel items from this document (filename: {filename})",
                        },
                    ],
                }
            ]
        else:
            messages = [
                {
                    "role": "user",
                    "content": f"Extract travel items from this document (filename: {filename}):\n\n{content_for_llm[:10000]}",
                }
            ]

        response = llm.call_api(
            system_prompt=system_prompt, messages=messages, return_full_response=True
        )

        response_text = response.content[0].text.strip()

        if response_text.startswith("```"):
            lines = response_text.split("\n")
            response_text = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])

        items = _parse_json_with_recovery(response_text)
        print(f"[UPLOAD] Parsed {len(items)} items from {filename}")
        for item in items:
            print(
                f"[UPLOAD]   - {item.get('title')}: category={item.get('category')}, location='{item.get('location')}', date={item.get('date')}, time={item.get('time')}"
            )

        if not isinstance(items, list):
            items = []

        return {"success": True, "items": items, "filename": filename}, 200

    except json.JSONDecodeError as e:
        print(f"JSON parse error: {e}")
        print(f"Response was: {response_text if 'response_text' in dir() else '<not set>'}")
        return {"error": "Failed to parse extracted items"}, 500
    except Exception as e:
        print(f"Upload plan error: {e}")
        traceback.print_exc()
        return {"error": f"Error processing file: {str(e)}"}, 500


def upload_file_handler(
    user_id: int, file_data: bytes, filename: str, output_dir: Path | None = None
) -> tuple[dict, int]:
    """Process an uploaded itinerary file. Returns (result, status_code)."""
    import time

    from agents.create.itinerary_utils import _convert_to_itinerary
    from agents.itinerary import geocoding_worker
    from agents.itinerary.parser import ItineraryParser
    from agents.itinerary.web_view import ItineraryWebView

    out_dir = output_dir or OUTPUT_DIR
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        return {"error": f"Unsupported file type '{suffix}'"}, 400

    uploads_dir = out_dir / "uploads"
    uploads_dir.mkdir(exist_ok=True)
    try:
        (uploads_dir / filename).write_bytes(file_data)
    except Exception as e:
        print(f"Warning: Could not save upload copy: {e}")

    try:
        start_time = time.time()
        is_json_file = suffix == ".json"

        if is_json_file:
            print("[UPLOAD] Importing JSON trip data...")
            try:
                import_data = json.loads(file_data.decode("utf-8"))
            except json.JSONDecodeError as e:
                return {"error": f"Invalid JSON file: {e}"}, 400

            if "itinerary_data" not in import_data and "days" not in import_data:
                return {"error": "JSON file is not a valid trip export"}, 400

            itinerary_data = import_data.get("itinerary_data") or import_data
            title = itinerary_data.get("title") or import_data.get("title", "Imported Trip")
            slug = slugify(title)
            output_file = f"{slug}.html"

            trip_for_html = {"itinerary_data": itinerary_data, "title": title}
            itinerary = _convert_to_itinerary(trip_for_html)
            if not itinerary or not itinerary.items:
                return {"error": "Could not parse trip data from JSON"}, 400

            web_view = ItineraryWebView()
            web_view.generate(
                itinerary, out_dir / output_file, use_ai_summary=False, skip_geocoding=True
            )

            locations = {
                item.location.name.split(",")[0]
                for item in itinerary.items
                if item.location.name and not item.is_home_location
            }
            days_count = (
                itinerary.duration_days
                or len({item.day_number for item in itinerary.items if item.day_number})
                or len(itinerary_data.get("days", []))
            )
            trip_data = {
                "title": title,
                "link": output_file,
                "dates": format_dates(itinerary),
                "days": days_count,
                "locations": len(locations),
                "activities": len(itinerary.items),
                "map_status": "pending",
                "is_public": import_data.get("is_public", False),
            }
            db.add_trip(user_id, trip_data, itinerary_data)
            geocoding_worker.queue_geocoding(output_file, itinerary)
            return {"success": True, "title": title, "link": output_file}, 200

        tmp_path = None
        try:
            print("[UPLOAD] Step 1: Parsing file...")
            extracted = extract_file_content(file_data, suffix.lstrip("."))
            if "error" in extracted:
                return {"error": extracted["error"]}, 400

            parser = ItineraryParser()
            if "text" in extracted:
                text = extracted["text"]
                if suffix in (".html", ".htm"):
                    text = extract_text_from_html(file_data)
                    if len(text) < 100:
                        return {
                            "error": "Could not extract meaningful content from the HTML file."
                        }, 400
                itinerary = parser.parse_text(text, source_url=filename)
            elif "image_data" in extracted:
                # Image upload (PNG / JPG / scanned PDF page). Use the parser's
                # vision path; the previous tmp-file + parse_file flow only
                # supported PDF and Excel and 400'd on every image upload.
                itinerary = parser.parse_image(
                    image_data=extracted["image_data"],
                    media_type=extracted.get("media_type", "image/png"),
                    source_file=filename,
                )
            else:
                return {"error": "Could not extract content from file"}, 400
            print(
                f"[UPLOAD] Step 1 done: {time.time() - start_time:.1f}s - {len(itinerary.items)} items"
            )

            print("[UPLOAD] Step 2: Generating web view...")
            slug = slugify(itinerary.title)
            output_file = f"{slug}.html"
            web_view = ItineraryWebView()
            web_view.generate(
                itinerary, out_dir / output_file, use_ai_summary=False, skip_geocoding=True
            )
            print(f"[UPLOAD] Step 2 done: {time.time() - start_time:.1f}s")

            locations = {
                item.location.name.split(",")[0]
                for item in itinerary.items
                if item.location.name and not item.is_home_location
            }
            itinerary_data = itinerary_to_data(itinerary)
            trip_data = {
                "title": itinerary.title,
                "link": output_file,
                "dates": format_dates(itinerary),
                "days": itinerary.duration_days
                or len({item.day_number for item in itinerary.items if item.day_number}),
                "locations": len(locations),
                "activities": len(itinerary.items),
                "map_status": "pending",
            }
            print("[UPLOAD] Step 3: Saving trip data...")
            db.add_trip(user_id, trip_data, itinerary_data)
            geocoding_worker.queue_geocoding(output_file, itinerary)
            print(f"[UPLOAD] SUCCESS - Total time: {time.time() - start_time:.1f}s")
            return {"success": True, "title": itinerary.title, "link": output_file}, 200

        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)

    except Exception as e:
        traceback.print_exc()
        return {"error": str(e)}, 500


def url_import_handler(user_id: int, url: str, output_dir: Path | None = None) -> tuple[dict, int]:
    """Import an itinerary from a URL. Returns (result, status_code)."""
    import tempfile
    from datetime import time as dt_time

    from agents.itinerary import geocoding_worker
    from agents.itinerary.models import Itinerary, ItineraryItem, Location
    from agents.itinerary.parser import ItineraryParser
    from agents.itinerary.web_view import ItineraryWebView

    out_dir = output_dir or OUTPUT_DIR

    try:
        google_flights = parse_google_flights_url(url)
    except ValueError as e:
        return {"error": str(e)}, 400

    if google_flights:

        def _parse_time(time_str):
            if not time_str:
                return None
            try:
                h, m = time_str.split(":")
                return dt_time(int(h), int(m))
            except (ValueError, AttributeError):
                return None

        items = []
        for flight in google_flights:
            date_obj = datetime.strptime(flight["date"], "%Y-%m-%d").date()
            items.append(
                ItineraryItem(
                    title=flight["title"],
                    category=flight["category"],
                    date=date_obj,
                    location=Location(name=flight["location"]),
                    notes=flight["notes"],
                    start_time=_parse_time(flight.get("time")),
                    end_time=_parse_time(flight.get("end_time")),
                )
            )

        if len(google_flights) >= 2:
            title = f"Trip to {google_flights[0]['destination']}"
        elif len(google_flights) == 1:
            title = f"Flight to {google_flights[0]['destination']}"
        else:
            title = "Flight Itinerary"

        dates = [datetime.strptime(f["date"], "%Y-%m-%d").date() for f in google_flights]
        itinerary = Itinerary(title=title, items=items, start_date=min(dates), end_date=max(dates))
        slug = slugify(itinerary.title)
        output_file = f"{slug}.html"
        web_view = ItineraryWebView()
        web_view.generate(
            itinerary, out_dir / output_file, use_ai_summary=False, skip_geocoding=True
        )

        itinerary_data = itinerary_to_data(itinerary)
        start_d, end_d = min(dates), max(dates)
        trip_data = {
            "title": itinerary.title,
            "link": output_file,
            "dates": format_dates(itinerary),
            "days": (end_d - start_d).days + 1 if start_d != end_d else 1,
            "locations": len({f["destination"] for f in google_flights}),
            "activities": len(google_flights),
            "map_status": "pending",
        }
        db.add_trip(user_id, trip_data, itinerary_data)
        geocoding_worker.queue_geocoding(output_file, itinerary)
        return {"success": True, "title": itinerary.title, "link": output_file}, 200

    # Check for Google Maps directions URL
    if "google.com/maps/dir/" in url or "maps.app.goo.gl" in url or "goo.gl/maps" in url:
        from agents.create.google_maps_parser import parse_google_maps_url, stops_to_trip_items

        parsed = parse_google_maps_url(url)
        if parsed["type"] == "directions" and parsed["stops"]:
            items = stops_to_trip_items(parsed["stops"])
            title = parsed["title"] or "Road Trip"

            # Create the trip with stops as ideas
            import re

            safe = re.sub(r"[^\w\s-]", "", title).strip().replace(" ", "_").lower()
            link = f"{safe}.html"

            itinerary_data = {"ideas": items, "days": [], "tips": []}
            trip_data = {
                "title": title,
                "link": link,
                "trip_type": "recommendation",
                "map_status": "ready",  # Already have coordinates
            }
            db.add_trip(user_id, trip_data, itinerary_data)

            return {
                "success": True,
                "title": title,
                "link": link,
                "stops_count": len(parsed["stops"]),
            }, 200

    try:
        file_data, filename, content_type = download_from_url(url)
    except Exception as e:
        return {"error": f"Failed to download from URL: {str(e)}"}, 400

    is_html = "html" in content_type or file_data[:15].lower().startswith((b"<!doctype", b"<html"))
    is_pdf = file_data[:4] == b"%PDF"
    is_xlsx = file_data[:4] == b"PK\x03\x04"

    tmp_path = None
    try:
        if is_html and not is_pdf and not is_xlsx:
            html_text = extract_text_from_html(file_data)
            if len(html_text) < 100:
                return {
                    "error": "Could not extract meaningful content from the page. "
                    "The page might require login or have restricted access."
                }, 400
            parser = ItineraryParser()
            itinerary = parser.parse_text(html_text, source_url=url)
        else:
            suffix = Path(filename).suffix.lower()
            if not suffix or suffix not in (".pdf", ".xlsx", ".xls"):
                suffix = ".xlsx" if is_xlsx else ".pdf" if is_pdf else None
            if not suffix:
                return {
                    "error": "Could not determine file type. Please use PDF, Excel, or HTML pages."
                }, 400

            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                tmp.write(file_data)
                tmp_path = tmp.name

            parser = ItineraryParser()
            try:
                itinerary = parser.parse_file(tmp_path)
            except Exception as e:
                return {"error": f"Failed to parse itinerary: {str(e)}"}, 400

        slug = slugify(itinerary.title)
        output_file = f"{slug}.html"
        web_view = ItineraryWebView()
        web_view.generate(
            itinerary, out_dir / output_file, use_ai_summary=False, skip_geocoding=True
        )

        locations = {
            item.location.name.split(",")[0]
            for item in itinerary.items
            if item.location.name and not item.is_home_location
        }
        itinerary_data = itinerary_to_data(itinerary)
        trip_data = {
            "title": itinerary.title,
            "link": output_file,
            "dates": format_dates(itinerary),
            "days": itinerary.duration_days
            or len({item.day_number for item in itinerary.items if item.day_number}),
            "locations": len(locations),
            "activities": len(itinerary.items),
            "map_status": "pending",
        }
        db.add_trip(user_id, trip_data, itinerary_data)
        geocoding_worker.queue_geocoding(output_file, itinerary)
        return {"success": True, "title": itinerary.title, "link": output_file}, 200

    except Exception as e:
        traceback.print_exc()
        return {"error": str(e)}, 500
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
