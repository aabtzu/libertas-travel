"""Background geocoding worker for async map generation."""

import json
import threading
import time
from pathlib import Path
from queue import Queue
from typing import Optional

import database as db

# Queue for geocoding tasks
_geocoding_queue = Queue()
_worker_thread = None


def get_output_dir():
    """Get the output directory from environment."""
    import os
    return Path(os.environ.get("OUTPUT_DIR", Path(__file__).parent / "output"))


def update_trip_map_status(link, status, error=None):
    """Update the map_status for a specific trip in database."""
    # Find which user owns this trip
    user_id = db.get_trip_owner(link)
    if user_id:
        db.update_trip_map_status(user_id, link, status, error)
        print(f"[GEOCODING] Updated map_status for {link} (user {user_id}): {status}")
    else:
        print(f"[GEOCODING] WARNING: Could not find owner for trip {link}")


def regenerate_map_for_trip(link, itinerary_data):
    """Regenerate the map for a trip with full geocoding.

    Args:
        link: The trip HTML filename (e.g., 'my_trip.html')
        itinerary_data: Serialized itinerary data dict
    """
    from agents.itinerary.models import Itinerary, ItineraryItem, Location
    from agents.itinerary.web_view import ItineraryWebView
    from agents.itinerary.mapper import ItineraryMapper
    from datetime import datetime, date, time as dt_time

    try:
        print(f"[GEOCODING] Starting geocoding for {link}")
        print(f"[GEOCODING] Input data has {len(itinerary_data.get('items', []))} items")
        update_trip_map_status(link, "processing")

        # Reconstruct itinerary from serialized data
        itinerary = deserialize_itinerary(itinerary_data)
        print(f"[GEOCODING] Deserialized {len(itinerary.items)} items")

        # Generate map data with geocoding
        mapper = ItineraryMapper()
        try:
            map_data = mapper.create_map_data(itinerary)
        except Exception as e:
            print(f"[GEOCODING] Map generation failed: {e}")
            map_data = {
                "center": {"lat": 0, "lng": 0},
                "zoom": 2,
                "markers": [],
                "error": f"Map could not be generated: {str(e)}"
            }

        # Store map_data in database
        _store_map_data_in_db(link, map_data)

        # Log marker coordinates for debugging
        for marker in map_data.get('markers', []):
            pos = marker.get('position', {})
            print(f"[GEOCODING] Marker '{marker.get('title')}': lat={pos.get('lat')}, lng={pos.get('lng')}")

        update_trip_map_status(link, "ready")
        print(f"[GEOCODING] Completed geocoding for {link}")

    except Exception as e:
        import traceback
        traceback.print_exc()
        update_trip_map_status(link, "error", str(e))
        print(f"[GEOCODING] Failed for {link}: {e}")


def _store_map_data_in_db(link: str, map_data: dict):
    """Store map_data in the trip's itinerary_data JSON."""
    import json

    user_id = db.get_trip_owner(link)
    if not user_id:
        print(f"[GEOCODING] Cannot store map_data - no owner found for {link}")
        return

    trip = db.get_trip_by_link(user_id, link)
    if not trip:
        print(f"[GEOCODING] Cannot store map_data - trip not found {link}")
        return

    itinerary_data = trip.get('itinerary_data') or {}
    itinerary_data['map_data'] = map_data

    db.update_trip_itinerary_data(user_id, link, itinerary_data)
    print(f"[GEOCODING] Stored map_data for {link}")


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
            website_url=item_data.get("website_url"),
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

        # Test geocoding API connectivity
        _test_geocoding_connectivity()

        # Recover stale pending tasks on startup
        recover_stale_tasks()


def _test_geocoding_connectivity():
    """Test if geocoding APIs are reachable."""
    import requests

    # Test Nominatim
    try:
        resp = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": "Berlin", "format": "json", "limit": 1},
            headers={"User-Agent": "Libertas-Travel/1.0"},
            timeout=10
        )
        print(f"[GEOCODING] Nominatim test: status={resp.status_code}, results={len(resp.json())}")
    except Exception as e:
        print(f"[GEOCODING] Nominatim test FAILED: {e}")

    # Test Photon
    try:
        resp = requests.get(
            "https://photon.komoot.io/api/",
            params={"q": "Berlin", "limit": 1},
            headers={"User-Agent": "Libertas-Travel/1.0"},
            timeout=10
        )
        data = resp.json()
        print(f"[GEOCODING] Photon test: status={resp.status_code}, results={len(data.get('features', []))}")
    except Exception as e:
        print(f"[GEOCODING] Photon test FAILED: {e}")


def recover_stale_tasks():
    """Re-queue any trips stuck in pending/processing status after server restart."""
    try:
        pending_trips = db.get_pending_geocoding_trips()
        if pending_trips:
            print(f"[GEOCODING] Recovering {len(pending_trips)} stale geocoding tasks")
            for trip in pending_trips:
                link = trip['link']
                itinerary_data = trip['itinerary_data']
                trip_title = trip.get('title', 'Untitled Trip')
                # Convert itinerary_data format to worker format
                worker_data = _convert_itinerary_data_to_worker_format(itinerary_data, trip_title)
                if worker_data:
                    _geocoding_queue.put((link, worker_data))
                    print(f"[GEOCODING] Re-queued: {link}")
    except Exception as e:
        print(f"[GEOCODING] Error recovering stale tasks: {e}")
        import traceback
        traceback.print_exc()


def _convert_itinerary_data_to_worker_format(itinerary_data, trip_title=None):
    """Convert itinerary_data from database format to worker format."""
    if not itinerary_data:
        return None

    # The database stores in a different format than the worker expects
    # Convert from {days: [{items: [...]}]} to {items: [...]}
    items = []
    for day in itinerary_data.get('days', []):
        day_date = day.get('date')
        day_number = day.get('day_number')
        for item in day.get('items', []):
            items.append({
                "title": item.get('title'),
                "description": item.get('notes'),
                "category": item.get('category'),
                "day_number": day_number,
                "date": day_date,
                "start_time": item.get('time'),
                "end_time": item.get('end_time'),
                "location_name": item.get('location'),
                "location_address": None,
                "location_lat": None,
                "location_lon": None,
                "confirmation_number": None,
                "notes": item.get('notes'),
                "is_home_location": False,
                "website_url": item.get('website'),
            })

    # Add ideas (items without dates)
    for item in itinerary_data.get('ideas', []):
        items.append({
            "title": item.get('title'),
            "description": item.get('notes'),
            "category": item.get('category'),
            "day_number": None,
            "date": None,
            "start_time": item.get('time'),
            "end_time": item.get('end_time'),
            "location_name": item.get('location'),
            "location_address": None,
            "location_lat": None,
            "location_lon": None,
            "confirmation_number": None,
            "notes": item.get('notes'),
            "is_home_location": False,
            "website_url": item.get('website'),
        })

    # Use trip_title from DB if itinerary_data doesn't have title
    title = itinerary_data.get('title') or trip_title or 'Untitled Trip'

    # Get start_date and end_date - prefer top-level, fall back to computing from days
    start_date = itinerary_data.get('start_date')
    end_date = itinerary_data.get('end_date')

    if not start_date or not end_date:
        # Compute from days array
        days = itinerary_data.get('days', [])
        if days:
            day_dates = [d.get('date') for d in days if d.get('date')]
            if day_dates:
                start_date = start_date or min(day_dates)
                end_date = end_date or max(day_dates)

    return {
        "title": title,
        "start_date": start_date,
        "end_date": end_date,
        "travelers": itinerary_data.get('travelers', []),
        "items": items,
    }


def get_queue_size():
    """Get the number of pending geocoding tasks."""
    return _geocoding_queue.qsize()
