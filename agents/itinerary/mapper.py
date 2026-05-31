"""Generate interactive maps from itineraries using OpenStreetMap/Nominatim."""

from __future__ import annotations

import html

from .geocoder import Geocoder
from .mapper_geocode import (
    extract_destination_with_llm,
    geocode_item,
    get_region_hint_fallback,
)
from .models import Itinerary

# Maximum number of locations to geocode (to avoid long waits)
MAX_GEOCODE_LOCATIONS = 50

# Marker colors by category
MARKER_COLORS = {
    "hotel": "#4285F4",  # Google blue
    "lodging": "#4285F4",
    "restaurant": "#FF9800",  # Orange
    "meal": "#FF9800",
    "attraction": "#34A853",  # Google green
    "activity": "#34A853",
    "airport": "#EA4335",  # Google red
    "flight": "#EA4335",
    "train_station": "#9C27B0",  # Purple
    "transport": "#757575",  # Gray
    "other": "#00BCD4",  # Cyan
}


class ItineraryMapper:
    """Generate interactive maps from itineraries using OpenStreetMap/Nominatim."""

    def __init__(self, api_key: str | None = None):
        # api_key kept for backwards compatibility but not used (Nominatim is free)
        self._geocode_failures = 0
        self._cached_region_hint = None  # Cache region hint to avoid duplicate LLM calls
        self._cached_region_itinerary_id = None  # Track which itinerary the cache is for
        self._geocoder = Geocoder()  # Handles Nominatim/Photon HTTP requests
        self._origin_check_cache: dict = {}

    def geocode_locations(self, itinerary: Itinerary) -> Itinerary:
        """Add coordinates to all locations in the itinerary using Nominatim (OpenStreetMap)."""
        print(
            f"[GEOCODING] Starting geocode_locations with {len(itinerary.items)} items", flush=True
        )

        # Determine the trip's region for biasing geocoding results
        region_hint = self._get_region_hint(itinerary)
        print(f"[GEOCODING] Region hint: {region_hint}", flush=True)

        # Limit geocoding to avoid long waits
        items_to_geocode = [item for item in itinerary.items if not item.location.has_coordinates]
        print(f"[GEOCODING] Items needing geocoding: {len(items_to_geocode)}", flush=True)

        # Log first few items for debugging
        for item in items_to_geocode[:3]:
            loc = item.location
            print(
                f"[GEOCODING] Item: '{item.title}' category='{item.category}' location='{loc.name if loc else None}'",
                flush=True,
            )

        # Only geocode up to MAX_GEOCODE_LOCATIONS
        for item in items_to_geocode[:MAX_GEOCODE_LOCATIONS]:
            # Stop if too many failures (likely network/rate limit issue)
            if self._geocode_failures >= 5:  # Increased from 3
                print(
                    f"[GEOCODING] Stopping after {self._geocode_failures} consecutive failures",
                    flush=True,
                )
                break
            failure = geocode_item(item, region_hint, self._geocoder)
            if failure:
                self._geocode_failures += 1
            else:
                self._geocode_failures = 0

        if len(items_to_geocode) > MAX_GEOCODE_LOCATIONS:
            print(
                f"[GEOCODING] Note: Only geocoded {MAX_GEOCODE_LOCATIONS} of {len(items_to_geocode)} locations",
                flush=True,
            )

        # Count successful geocodes
        geocoded_count = sum(1 for item in itinerary.items if item.location.has_coordinates)
        print(
            f"[GEOCODING] Completed: {geocoded_count}/{len(itinerary.items)} items have coordinates",
            flush=True,
        )

        return itinerary

    def _get_region_hint(self, itinerary: Itinerary) -> str:
        """Extract a region hint from the itinerary using LLM for accuracy."""
        # Check cache first - use itinerary identity as cache key
        cache_key = id(itinerary)
        if self._cached_region_itinerary_id == cache_key and self._cached_region_hint is not None:
            return self._cached_region_hint

        # Collect context for the LLM
        context_parts = []
        if itinerary.title:
            context_parts.append(f"Trip title: {itinerary.title}")

        # Get non-flight items (flights often have origin city)
        non_flight_items = [item for item in itinerary.items if item.category != "flight"][:15]
        if non_flight_items:
            items_text = []
            for item in non_flight_items:
                loc = item.location.name if item.location else ""
                items_text.append(f"- {item.title}" + (f" ({loc})" if loc else ""))
            context_parts.append("Activities/Places:\n" + "\n".join(items_text))

        if not context_parts:
            self._cached_region_hint = ""
            self._cached_region_itinerary_id = cache_key
            return ""

        # Try LLM extraction
        try:
            region = extract_destination_with_llm("\n\n".join(context_parts))
            if region:
                print(f"[GEOCODING] LLM extracted destination: {region}")
                self._cached_region_hint = region
                self._cached_region_itinerary_id = cache_key
                return region
        except Exception as e:
            print(f"[GEOCODING] LLM extraction failed: {e}")

        # Fallback to simple pattern matching
        result = get_region_hint_fallback(itinerary)
        self._cached_region_hint = result
        self._cached_region_itinerary_id = cache_key
        return result

    def _is_transport_outside_destination(self, item, destination: str) -> bool:
        """Check if a transport item's location is outside the destination region.

        Applies to flights, trains, cars, buses, ferries, any transport mode.
        We want to EXCLUDE origin cities, home airports, transit/connecting stops,
        and departure points that are not part of the actual trip destination.
        """
        category = (item.category or "").lower()
        title = (item.title or "").lower()
        location = item.location.name or ""

        # Log every item for debugging
        print(
            f"[MAP DEBUG] Item: '{item.title}' category='{category}' location='{location}'",
            flush=True,
        )

        # Check all transport modes: flights, trains, cars, buses, ferries
        transport_categories = [
            "flight",
            "air",
            "plane",
            "airport",
            "transport",
            "train",
            "car",
            "bus",
            "ferry",
        ]
        transport_keywords = [
            "flight",
            "fly",
            "airport",
            "train",
            "rail",
            "rental car",
            "car rental",
            "ferry",
            "bus",
        ]

        is_transport_category = category in transport_categories
        is_transport_title = any(kw in title for kw in transport_keywords)

        if not is_transport_category and not is_transport_title:
            return False

        if not destination:
            print("[MAP DEBUG] No destination set, keeping item", flush=True)
            return False

        if not location:
            print("[MAP DEBUG] No location for item, keeping item", flush=True)
            return False

        # Quick check: if destination name appears in location, keep it
        dest_lower = destination.lower()
        loc_lower = location.lower()
        if dest_lower in loc_lower:
            print(
                f"[MAP DEBUG] Destination '{destination}' found in location '{location}', keeping item",
                flush=True,
            )
            return False

        # Check if location is in destination region using LLM
        print(f"[MAP DEBUG] Checking if '{location}' is in '{destination}' via LLM...", flush=True)
        is_in_destination = self._is_location_in_destination(
            location, item.title or "", destination
        )

        # If location is NOT in destination, filter it out (origin, home city, transit stop, etc.)
        if not is_in_destination:
            print(
                f"[MAP] Filtering transport outside destination: '{item.title}' at '{location}' (not in {destination})",
                flush=True,
            )
            return True

        print(f"[MAP DEBUG] Keeping item: '{item.title}' - location is in destination", flush=True)
        return False

    def _is_location_in_destination(self, location: str, title: str, destination: str) -> bool:
        """Use LLM to check if a location/airport is in or near the destination region."""
        # Check cache first
        cache_key = f"{location}|{destination}"
        if cache_key in self._origin_check_cache:
            return self._origin_check_cache[cache_key]

        try:
            from agents.common.llm import HAIKU, make_llm

            prompt = f"""Is the location "{location}" part of the trip destination {destination}?

Transport item for context: "{title}"

Answer with just YES or NO.
- YES if the location is in or near {destination} (it's a real stop in the destination)
- NO if it's the traveler's home city, origin airport, a transit/connecting stop, or anywhere outside {destination}

Examples where destination is "Sweden":
- "Stockholm Arlanda" -> YES (it's in Sweden)
- "Munich Airport" -> NO (Germany, likely home/origin)
- "London Heathrow" -> NO (UK, likely a connecting transit stop)
- "New York JFK" -> NO (USA, likely home/end destination)
- "Copenhagen" -> NO (Denmark, not Sweden, even if geographically close)"""

            answer = (
                make_llm(model=HAIKU, max_tokens=10)
                .call_api(system_prompt="", messages=[{"role": "user", "content": prompt}])
                .strip()
                .upper()
            )
            result = answer.startswith("YES")

            # Cache the result
            self._origin_check_cache[cache_key] = result
            print(f"[MAP] Location check: '{location}' in '{destination}'? {result}", flush=True)

            return result

        except Exception as e:
            print(f"[MAP] LLM location check failed: {e}", flush=True)
            # Default to keeping the location if LLM fails
            return True

    def create_map_data(self, itinerary: Itinerary) -> dict:
        """Create map data structure for Google Maps.

        Args:
            itinerary: The itinerary to map

        Returns:
            Dictionary with map data (center, zoom, markers)
        """
        # Clear the origin check cache to ensure fresh LLM calls
        self._origin_check_cache.clear()
        print("[MAP] === Starting create_map_data ===", flush=True)
        print(f"[MAP] Trip title: '{itinerary.title}'", flush=True)
        print(f"[MAP] Total items: {len(itinerary.items)}", flush=True)

        # Ensure locations are geocoded
        self.geocode_locations(itinerary)

        # Get the destination region to identify origin flights
        destination = self._get_region_hint(itinerary)
        print(f"[MAP] Destination region identified: '{destination}'", flush=True)

        # Log all items with coordinates before filtering
        print("[MAP] === Checking items for origin flights ===", flush=True)

        # Get locations with coordinates, excluding home locations and origin flights
        locations_with_coords = []
        for item in itinerary.items:
            if not item.location.has_coordinates:
                continue
            if item.is_home_location:
                print(f"[MAP] Skipping home location: '{item.title}'", flush=True)
                continue
            if self._is_transport_outside_destination(item, destination):
                # Already logged in _is_transport_outside_destination
                continue
            locations_with_coords.append((item, item.location))

        print(
            f"[MAP] === Items remaining after filtering: {len(locations_with_coords)} ===",
            flush=True,
        )

        if not locations_with_coords:
            return {
                "center": {"lat": 0, "lng": 0},
                "zoom": 2,
                "markers": [],
                "route": [],
                "error": "No locations could be geocoded",
            }

        # Calculate map center and bounds
        lats = [loc.latitude for _, loc in locations_with_coords]
        lons = [loc.longitude for _, loc in locations_with_coords]

        # Calculate center
        center_lat = sum(lats) / len(lats)
        center_lon = sum(lons) / len(lons)

        # Calculate appropriate zoom level based on span
        lat_span = max(lats) - min(lats)
        lon_span = max(lons) - min(lons)
        max_span = max(lat_span, lon_span)

        # Determine zoom level based on geographic span
        if max_span > 10:
            zoom = 5
        elif max_span > 5:
            zoom = 6
        elif max_span > 2:
            zoom = 7
        elif max_span > 1:
            zoom = 8
        elif max_span > 0.5:
            zoom = 9
        elif max_span > 0.1:
            zoom = 10
        else:
            zoom = 12

        # Build markers data
        markers = []
        for idx, (item, location) in enumerate(locations_with_coords, 1):
            # Determine marker color based on category
            category = item.category or "other"
            color = MARKER_COLORS.get(
                location.location_type, MARKER_COLORS.get(category, "#00BCD4")
            )

            # Build info window content
            info_html = self._build_info_window(item, idx)

            markers.append(
                {
                    "position": {"lat": location.latitude, "lng": location.longitude},
                    "title": item.title,
                    "category": category,
                    "color": color,
                    "info": info_html,
                }
            )

        return {
            "center": {"lat": center_lat, "lng": center_lon},
            "zoom": zoom,
            "markers": markers,
        }

    def _build_info_window(self, item, idx: int) -> str:
        """Build HTML content for a Google Maps info window."""
        import urllib.parse

        location_name = item.location.name or item.title
        lines = [
            '<div style="font-family: Arial, sans-serif; max-width: 320px; font-size: 15px;">',
            f'<h4 style="margin: 0 0 10px 0; color: #1a73e8; font-size: 17px;">{idx}. {html.escape(item.title)}</h4>',
            f'<p style="margin: 0 0 6px 0; font-weight: bold; font-size: 15px;">{html.escape(location_name)}</p>',
        ]

        if item.date:
            date_str = item.date.strftime("%B %d, %Y")
            lines.append(
                f'<p style="margin: 0 0 6px 0; color: #666; font-size: 14px;"><em>{date_str}</em></p>'
            )

        if item.start_time:
            time_str = item.start_time.strftime("%I:%M %p")
            if item.end_time:
                time_str += f" - {item.end_time.strftime('%I:%M %p')}"
            lines.append(f'<p style="margin: 0 0 6px 0; font-size: 14px;">Time: {time_str}</p>')

        if item.description:
            desc = html.escape(item.description[:200])
            if len(item.description) > 200:
                desc += "..."
            lines.append(f'<p style="margin: 0 0 6px 0; font-size: 14px;">{desc}</p>')

        if item.confirmation_number:
            lines.append(
                f'<p style="margin: 0 0 6px 0; font-size: 13px; color: #888;">Conf: {html.escape(item.confirmation_number)}</p>'
            )

        if item.location.address:
            lines.append(
                f'<p style="margin: 0 0 10px 0; font-size: 13px; color: #888;">{html.escape(item.location.address)}</p>'
            )

        # Add action links
        lines.append(
            '<div style="margin-top: 12px; padding-top: 10px; border-top: 1px solid #eee;">'
        )

        # Google Maps link - search by place name for better results
        query = urllib.parse.quote(f"{item.title} {location_name}")
        maps_url = f"https://www.google.com/maps/search/?api=1&query={query}"
        maps_link_text = html.escape(location_name[:30]) + (
            "..." if len(location_name) > 30 else ""
        )
        lines.append(
            f'<a href="{maps_url}" target="_blank" style="display: block; margin-bottom: 8px; color: #1a73e8; text-decoration: none; font-size: 14px;"><i class="fas fa-map-marker-alt" style="margin-right: 6px;"></i>{maps_link_text}</a>'
        )

        # Website link (for hotels, restaurants, activities)
        if item.category in ("hotel", "lodging", "meal", "restaurant", "activity", "attraction"):
            if item.website_url:
                # Use the actual website URL from source data
                website_link = item.website_url
            else:
                # Fall back to DuckDuckGo's "I'm Feeling Ducky" redirect
                search_query = urllib.parse.quote(f"{item.title} {location_name} official site")
                website_link = f"https://duckduckgo.com/?q=\\{search_query}"
            lines.append(
                f'<a href="{website_link}" target="_blank" style="display: block; color: #1a73e8; text-decoration: none; font-size: 14px;"><i class="fas fa-globe" style="margin-right: 6px;"></i>Website</a>'
            )

        lines.append("</div>")
        lines.append("</div>")
        return "".join(lines)
