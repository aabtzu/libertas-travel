"""Parse Google Maps URLs to extract stops, coordinates, and route data.

Standalone module, no Flask dependencies. Used by Create page and Explore.

Supported URL formats:
- https://maps.app.goo.gl/... (short links, resolved via redirect)
- https://www.google.com/maps/dir/A/B/C/... (directions with stops)
- https://www.google.com/maps/place/.../@lat,lng,... (single place)
- https://www.google.com/maps/search/?api=1&query=... (search)
"""

from __future__ import annotations

import re
from urllib.parse import unquote_plus

import requests

# Coordinate patterns in Google Maps URLs
_COORD_AT_RE = re.compile(r"@(-?\d+\.\d+),(-?\d+\.\d+)")
_COORD_QUERY_RE = re.compile(r"[?&]q=(-?\d+\.\d+),(-?\d+\.\d+)")
# Data parameter coordinates: !2d=longitude, then !2d or next !1d/!2d=latitude
_DATA_LNG_RE = re.compile(r"!2d(-?\d+\.\d+)")
_DATA_LAT_RE = re.compile(r"!2d(-?\d+\.\d+)!2d(-?\d+\.\d+)")


def resolve_short_url(url: str) -> str:
    """Resolve a shortened Google Maps URL to the full URL."""
    if "goo.gl" not in url and "maps.app" not in url:
        return url
    try:
        resp = requests.head(url, allow_redirects=True, timeout=10)
        return resp.url
    except Exception:
        # Try GET as fallback
        try:
            resp = requests.get(url, allow_redirects=True, timeout=10)
            return resp.url
        except Exception:
            return url


def parse_google_maps_url(url: str) -> dict:
    """Parse a Google Maps URL and extract structured data.

    Returns:
        {
            "type": "directions" | "place" | "search",
            "stops": [{"name": "...", "latitude": ..., "longitude": ...}, ...],
            "title": "suggested trip title",
            "original_url": "...",
        }
    """
    # Resolve short URLs
    if "goo.gl" in url or "maps.app" in url:
        url = resolve_short_url(url)

    result = {
        "type": "unknown",
        "stops": [],
        "title": "",
        "original_url": url,
    }

    if "/maps/dir/" in url:
        result["type"] = "directions"
        result["stops"] = _parse_directions_url(url)
        if result["stops"]:
            first = result["stops"][0]["name"]
            last = result["stops"][-1]["name"]
            result["title"] = f"{first} to {last}"
    elif "/maps/place/" in url:
        result["type"] = "place"
        result["stops"] = _parse_place_url(url)
        if result["stops"]:
            result["title"] = result["stops"][0]["name"]
    elif "/maps/search" in url or "q=" in url:
        result["type"] = "search"
        result["stops"] = _parse_search_url(url)

    return result


def _parse_directions_url(url: str) -> list[dict]:
    """Extract stops from a /maps/dir/A/B/C/... URL."""
    # Split URL path to get stop names
    # URL format: /maps/dir/Stop1/Stop2/Stop3/@lat,lng,.../data=...
    path_part = url.split("?")[0]  # Remove query params
    if "/maps/dir/" not in path_part:
        return []

    dir_path = path_part.split("/maps/dir/")[1]
    segments = dir_path.split("/")

    # Filter out the @lat,lng segment and data segment
    stop_names = []
    for seg in segments:
        if seg.startswith("@") or seg.startswith("data=") or not seg:
            continue
        stop_names.append(unquote_plus(seg))

    # Extract coordinates from the data parameter
    coords = _extract_coordinates_from_data(url)

    # Match stops with coordinates
    stops = []
    for i, name in enumerate(stop_names):
        # Clean up name: remove zip codes, clean formatting
        clean_name = _clean_stop_name(name)
        stop = {
            "name": clean_name,
            "latitude": None,
            "longitude": None,
        }
        if i < len(coords):
            stop["latitude"] = coords[i]["lat"]
            stop["longitude"] = coords[i]["lng"]
        stops.append(stop)

    return stops


def _extract_coordinates_from_data(url: str) -> list[dict]:
    """Extract lat/lng pairs from the data= parameter in a Google Maps URL.

    The data parameter contains coordinate pairs as:
    !2d<longitude>!2d<latitude> (note: longitude comes first)

    Each stop's coordinates appear as !1m5!1m1!1s...!2m2!1d<lng>!2d<lat>
    """
    coords = []

    # Pattern: !1d<lng>!2d<lat>, this is the actual coordinate encoding
    pairs = re.findall(r"!1d(-?\d+\.\d+)!2d(-?\d+\.\d+)", url)
    for lng_str, lat_str in pairs:
        lat = float(lat_str)
        lng = float(lng_str)
        if -90 <= lat <= 90 and -180 <= lng <= 180:
            coords.append({"lat": lat, "lng": lng})

    return coords


def _parse_place_url(url: str) -> list[dict]:
    """Extract place info from a /maps/place/... URL."""
    stops = []

    # Extract place name from path
    if "/maps/place/" in url:
        path_part = url.split("/maps/place/")[1].split("/")[0]
        name = _clean_stop_name(unquote_plus(path_part))
    else:
        name = ""

    # Extract coordinates from @lat,lng
    lat, lng = None, None
    m = _COORD_AT_RE.search(url)
    if m:
        lat, lng = float(m.group(1)), float(m.group(2))

    if name or (lat and lng):
        stops.append({"name": name, "latitude": lat, "longitude": lng})

    return stops


def _parse_search_url(url: str) -> list[dict]:
    """Extract search query from a /maps/search/... URL."""
    stops = []
    m = _COORD_QUERY_RE.search(url)
    if m:
        stops.append(
            {
                "name": "",
                "latitude": float(m.group(1)),
                "longitude": float(m.group(2)),
            }
        )
    return stops


def _clean_stop_name(name: str) -> str:
    """Clean up a stop name from URL encoding.

    "Gold+Beach,+Oregon+97444" → "Gold Beach, Oregon"
    "Shelter+Cove,+California+95589" → "Shelter Cove, California"
    """
    # Remove zip codes (5 digits at end)
    name = re.sub(r"\s*\d{5}(-\d{4})?\s*$", "", name)
    # Clean extra whitespace
    name = " ".join(name.split())
    return name.strip()


def stops_to_trip_items(stops: list[dict]) -> list[dict]:
    """Convert parsed stops to trip idea items.

    First stop is marked as origin (home location).
    Last stop is marked as destination.
    Middle stops are activities/waypoints.
    """
    items = []
    for i, stop in enumerate(stops):
        # Build Google Maps link
        if stop.get("latitude") and stop.get("longitude"):
            maps_link = (
                f"https://www.google.com/maps/search/?api=1"
                f"&query={stop['latitude']},{stop['longitude']}"
            )
        else:
            q = stop["name"].replace(" ", "%20")
            maps_link = f"https://www.google.com/maps/search/?api=1&query={q}"

        item = {
            "title": stop["name"],
            "category": "transport" if i == 0 else "activity",
            "location": stop["name"],
            "latitude": stop.get("latitude"),
            "longitude": stop.get("longitude"),
            "google_maps_link": maps_link,
            "notes": "",
        }

        # Mark first stop as origin
        if i == 0:
            item["is_home_location"] = True
            item["notes"] = "Starting point"

        items.append(item)

    return items
