"""Background geocoding worker for async map generation."""

import json
import threading
import time
from pathlib import Path
from queue import Queue
from typing import Optional

# Queue for geocoding tasks
_geocoding_queue = Queue()
_worker_thread = None


def get_output_dir():
    """Get the output directory from environment."""
    import os
    return Path(os.environ.get("OUTPUT_DIR", Path(__file__).parent / "output"))


def load_trips_data():
    """Load trips data from JSON file."""
    trips_file = get_output_dir() / "trips_data.json"
    if trips_file.exists():
        with open(trips_file) as f:
            return json.load(f)
    return []


def save_trips_data(trips):
    """Save trips data to JSON file."""
    trips_file = get_output_dir() / "trips_data.json"
    with open(trips_file, "w") as f:
        json.dump(trips, f, indent=2)


def update_trip_map_status(link, status, error=None):
    """Update the map_status for a specific trip."""
    trips = load_trips_data()
    for trip in trips:
        if trip.get("link") == link:
            trip["map_status"] = status
            if error:
                trip["map_error"] = error
            elif "map_error" in trip:
                del trip["map_error"]
            break
    save_trips_data(trips)
    print(f"[GEOCODING] Updated map_status for {link}: {status}")


def regenerate_map_for_trip(link, itinerary_data):
    """Regenerate the map for a trip with full geocoding.

    Args:
        link: The trip HTML filename (e.g., 'my_trip.html')
        itinerary_data: Serialized itinerary data dict
    """
    from agents.itinerary.models import Itinerary, ItineraryItem, Location
    from agents.itinerary.web_view import ItineraryWebView
    from datetime import datetime, date, time as dt_time

    output_dir = get_output_dir()
    output_path = output_dir / link

    try:
        print(f"[GEOCODING] Starting geocoding for {link}")
        update_trip_map_status(link, "processing")

        # Reconstruct itinerary from serialized data
        itinerary = deserialize_itinerary(itinerary_data)

        # Generate web view WITH geocoding
        web_view = ItineraryWebView()
        web_view.generate(itinerary, output_path, use_ai_summary=False, skip_geocoding=False)

        update_trip_map_status(link, "ready")
        print(f"[GEOCODING] Completed geocoding for {link}")

    except Exception as e:
        import traceback
        traceback.print_exc()
        update_trip_map_status(link, "error", str(e))
        print(f"[GEOCODING] Failed for {link}: {e}")


def serialize_itinerary(itinerary):
    """Serialize an Itinerary object to a dict for queue storage."""
    def serialize_date(d):
        if d is None:
            return None
        if hasattr(d, 'isoformat'):
            return d.isoformat()
        return str(d)

    def serialize_time(t):
        if t is None:
            return None
        if hasattr(t, 'isoformat'):
            return t.isoformat()
        return str(t)

    items = []
    for item in itinerary.items:
        items.append({
            "title": item.title,
            "description": item.description,
            "category": item.category,
            "day_number": item.day_number,
            "date": serialize_date(item.date),
            "start_time": serialize_time(item.start_time),
            "end_time": serialize_time(item.end_time),
            "location_name": item.location.name if item.location else None,
            "location_address": item.location.address if item.location else None,
            "location_lat": item.location.latitude if item.location else None,
            "location_lon": item.location.longitude if item.location else None,
            "confirmation_number": item.confirmation_number,
            "notes": item.notes,
            "is_home_location": item.is_home_location,
        })

    return {
        "title": itinerary.title,
        "start_date": serialize_date(itinerary.start_date),
        "end_date": serialize_date(itinerary.end_date),
        "duration_days": itinerary.duration_days,
        "travelers": itinerary.travelers,
        "items": items,
    }


def deserialize_itinerary(data):
    """Deserialize an Itinerary from a dict."""
    from agents.itinerary.models import Itinerary, ItineraryItem, Location
    from datetime import datetime, date, time as dt_time

    def parse_date(s):
        if s is None:
            return None
        try:
            return datetime.fromisoformat(s).date()
        except:
            return None

    def parse_time(s):
        if s is None:
            return None
        try:
            return datetime.fromisoformat(s).time()
        except:
            try:
                return dt_time.fromisoformat(s)
            except:
                return None

    items = []
    for item_data in data.get("items", []):
        location = Location(
            name=item_data.get("location_name"),
            address=item_data.get("location_address"),
            latitude=item_data.get("location_lat"),
            longitude=item_data.get("location_lon"),
        )
        item = ItineraryItem(
            title=item_data.get("title"),
            description=item_data.get("description"),
            category=item_data.get("category"),
            day_number=item_data.get("day_number"),
            date=parse_date(item_data.get("date")),
            start_time=parse_time(item_data.get("start_time")),
            end_time=parse_time(item_data.get("end_time")),
            location=location,
            confirmation_number=item_data.get("confirmation_number"),
            notes=item_data.get("notes"),
            is_home_location=item_data.get("is_home_location", False),
        )
        items.append(item)

    return Itinerary(
        title=data.get("title", "Untitled Trip"),
        start_date=parse_date(data.get("start_date")),
        end_date=parse_date(data.get("end_date")),
        travelers=data.get("travelers", []),
        items=items,
    )


def queue_geocoding(link, itinerary):
    """Add a trip to the geocoding queue."""
    itinerary_data = serialize_itinerary(itinerary)
    _geocoding_queue.put((link, itinerary_data))
    print(f"[GEOCODING] Queued {link} for background geocoding")

    # Ensure worker is running
    start_worker()


def _worker_loop():
    """Background worker that processes the geocoding queue."""
    print("[GEOCODING] Worker started")
    while True:
        try:
            # Wait for a task (with timeout to allow thread to exit gracefully)
            try:
                link, itinerary_data = _geocoding_queue.get(timeout=5)
            except:
                continue

            # Add a small delay between geocoding tasks to avoid rate limits
            time.sleep(2)

            # Process the task
            regenerate_map_for_trip(link, itinerary_data)
            _geocoding_queue.task_done()

        except Exception as e:
            print(f"[GEOCODING] Worker error: {e}")
            import traceback
            traceback.print_exc()


def start_worker():
    """Start the background worker thread if not already running."""
    global _worker_thread

    if _worker_thread is None or not _worker_thread.is_alive():
        _worker_thread = threading.Thread(target=_worker_loop, daemon=True)
        _worker_thread.start()
        print("[GEOCODING] Background worker thread started")


def get_queue_size():
    """Get the number of pending geocoding tasks."""
    return _geocoding_queue.qsize()
