"""Generate interactive maps from itineraries using OpenStreetMap/Nominatim."""

from __future__ import annotations

import os
import json
import html
import requests
import time
from pathlib import Path
from typing import Optional, Union

from .models import Itinerary, Location


# Maximum number of locations to geocode (to avoid long waits)
MAX_GEOCODE_LOCATIONS = 50

# Nominatim requires a delay between requests (1 request per second)
NOMINATIM_DELAY = 1.1

# Marker colors by category
MARKER_COLORS = {
    "hotel": "#4285F4",      # Google blue
    "lodging": "#4285F4",
    "restaurant": "#FF9800", # Orange
    "meal": "#FF9800",
    "attraction": "#34A853", # Google green
    "activity": "#34A853",
    "airport": "#EA4335",    # Google red
    "flight": "#EA4335",
    "train_station": "#9C27B0", # Purple
    "transport": "#757575",  # Gray
    "other": "#00BCD4",      # Cyan
}


class ItineraryMapper:
    """Generate interactive maps from itineraries using OpenStreetMap/Nominatim."""

    def __init__(self, api_key: Optional[str] = None):
        # api_key kept for backwards compatibility but not used (Nominatim is free)
        self._geocode_failures = 0
        self._cached_region_hint = None  # Cache region hint to avoid duplicate LLM calls
        self._cached_region_itinerary_id = None  # Track which itinerary the cache is for
        self._last_geocode_time = 0  # Rate limiting for Nominatim

    def geocode_locations(self, itinerary: Itinerary) -> Itinerary:
        """Add coordinates to all locations in the itinerary using Nominatim (OpenStreetMap)."""
        # Determine the trip's region for biasing geocoding results
        region_hint = self._get_region_hint(itinerary)

        # Limit geocoding to avoid long waits
        items_to_geocode = [
            item for item in itinerary.items
            if not item.location.has_coordinates
        ]

        # Only geocode up to MAX_GEOCODE_LOCATIONS
        for item in items_to_geocode[:MAX_GEOCODE_LOCATIONS]:
            # Stop if too many failures (likely network/rate limit issue)
            if self._geocode_failures >= 3:
                print(f"Stopping geocoding after {self._geocode_failures} consecutive failures")
                break
            self._geocode_item(item, region_hint)

        if len(items_to_geocode) > MAX_GEOCODE_LOCATIONS:
            print(f"Note: Only geocoded {MAX_GEOCODE_LOCATIONS} of {len(items_to_geocode)} locations")

        return itinerary

    def _get_region_hint(self, itinerary: Itinerary) -> str:
        """Extract a region hint from the itinerary using LLM for accuracy."""
        # Check cache first - use itinerary title as cache key
        cache_key = id(itinerary)
        if self._cached_region_itinerary_id == cache_key and self._cached_region_hint is not None:
            return self._cached_region_hint

        # Collect context for the LLM
        context_parts = []
        if itinerary.title:
            context_parts.append(f"Trip title: {itinerary.title}")

        # Get non-flight items (flights often have origin city)
        non_flight_items = [item for item in itinerary.items if item.category != 'flight'][:15]
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
            region = self._extract_destination_with_llm("\n\n".join(context_parts))
            if region:
                print(f"[GEOCODING] LLM extracted destination: {region}")
                self._cached_region_hint = region
                self._cached_region_itinerary_id = cache_key
                return region
        except Exception as e:
            print(f"[GEOCODING] LLM extraction failed: {e}")

        # Fallback to simple pattern matching
        result = self._get_region_hint_fallback(itinerary)
        self._cached_region_hint = result
        self._cached_region_itinerary_id = cache_key
        return result

    def _extract_destination_with_llm(self, context: str) -> str:
        """Use LLM to extract the primary destination from trip context."""
        import anthropic

        client = anthropic.Anthropic()

        prompt = f"""Based on this trip information, identify the PRIMARY DESTINATION city and country.
Ignore origin/departure locations (like home airports). Focus on where the traveler is actually visiting.

{context}

Respond with ONLY the destination in format: "City, Country" (e.g., "Vienna, Austria" or "Tokyo, Japan").
If multiple destinations, pick the main one. If unclear, respond with just the country."""

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=50,
            messages=[{"role": "user", "content": prompt}]
        )

        result = response.content[0].text.strip()
        # Clean up response - remove quotes, periods, etc.
        result = result.strip('"\'.')
        return result if result and len(result) < 100 else ""

    # Cache for IATA code lookups to avoid repeated LLM calls
    _iata_cache: dict = {}

    def _resolve_iata_code(self, iata: str) -> str:
        """Use LLM to resolve an IATA airport code to full airport name for geocoding."""
        # Check cache first
        if iata in self._iata_cache:
            return self._iata_cache[iata]

        # Skip common non-airport 3-letter words
        skip_words = {'THE', 'AND', 'FOR', 'DAY', 'VIA', 'NON', 'ONE', 'TWO', 'NEW', 'OLD'}
        if iata in skip_words:
            self._iata_cache[iata] = ""
            return ""

        try:
            import anthropic
            client = anthropic.Anthropic()

            response = client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=50,
                messages=[{"role": "user", "content": f"What airport has IATA code {iata}? Reply with ONLY the airport name and city, e.g. 'Munich Airport, Germany' or 'NONE' if not a valid airport code."}]
            )

            result = response.content[0].text.strip()
            if result and 'NONE' not in result.upper() and len(result) < 100:
                self._iata_cache[iata] = result
                print(f"[GEOCODING] Resolved IATA {iata} -> {result}")
                return result
        except Exception as e:
            print(f"[GEOCODING] Failed to resolve IATA {iata}: {e}")

        self._iata_cache[iata] = ""
        return ""

    def _get_region_hint_fallback(self, itinerary: Itinerary) -> str:
        """Fallback when LLM extraction fails - try simpler LLM call with just the title."""
        if not itinerary.title:
            return ""

        try:
            import anthropic
            client = anthropic.Anthropic()

            response = client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=30,
                messages=[{"role": "user", "content": f"What country is this trip to? '{itinerary.title}'. Reply with ONLY the country name, or 'UNKNOWN' if unclear."}]
            )

            result = response.content[0].text.strip()
            if result and 'UNKNOWN' not in result.upper() and len(result) < 50:
                print(f"[GEOCODING] Fallback resolved region: {result}")
                return result
        except Exception as e:
            print(f"[GEOCODING] Fallback region extraction failed: {e}")

        return ""

    def _geocode_item(self, item, region_hint: str = "") -> None:
        """Geocode an item using its title and location info."""
        location = item.location
        is_flight = item.category == 'flight'

        # Build smart queries - use item title (actual place name) + location context
        queries = []

        # If we have an address, try it first
        if location.address:
            queries.append(location.address)

        # For flights, try to geocode the airport specifically
        if is_flight:
            import re

            # Try to extract IATA code from title or location and resolve via LLM
            text_to_search = f"{item.title} {location.name or ''}"

            # Look for IATA codes (3 uppercase letters)
            iata_codes = re.findall(r'\b([A-Z]{3})\b', text_to_search)
            for iata in iata_codes:
                airport_name = self._resolve_iata_code(iata)
                if airport_name:
                    queries.append(airport_name)
                    break  # Use first valid airport found

            if location.name:
                loc_name = location.name
                # Extract city from location like "Vienna (Vienna International, Terminal 3)"
                match = re.match(r'^([^(]+)', loc_name)
                city = match.group(1).strip() if match else loc_name.split()[0]

                # Add explicit airport queries
                queries.append(f"{city} International Airport")
                queries.append(f"{city} Airport")

                if 'airport' not in loc_name.lower():
                    queries.append(f"{loc_name} Airport")

                queries.append(loc_name)

        # Use item title with location context (e.g., "Sina Centurion Palace Venice Italy")
        elif item.title and location.name:
            # Don't add location if title already contains it
            if location.name.lower() not in item.title.lower():
                queries.append(f"{item.title}, {location.name}")
            else:
                queries.append(item.title)
        elif item.title:
            if region_hint:
                queries.append(f"{item.title}, {region_hint}")
            queries.append(item.title)

        # Fall back to just location name with region hint
        if location.name:
            if region_hint and region_hint.lower() not in location.name.lower():
                queries.append(f"{location.name}, {region_hint}")
            queries.append(location.name)

        for query in queries:
            result = self._do_geocode(query, region_hint)
            if result:
                location.latitude = result["lat"]
                location.longitude = result["lng"]
                if not location.address:
                    location.address = result.get("address", "")
                self._geocode_failures = 0
                return

        # No results found
        self._geocode_failures += 1

    def _do_geocode(self, query: str, region_hint: str = "") -> Optional[dict]:
        """Execute a geocoding request using Nominatim (OpenStreetMap) and return result or None."""
        try:
            # Rate limiting - Nominatim requires max 1 request per second
            elapsed = time.time() - self._last_geocode_time
            if elapsed < NOMINATIM_DELAY:
                time.sleep(NOMINATIM_DELAY - elapsed)

            url = "https://nominatim.openstreetmap.org/search"
            params = {
                "q": query,
                "format": "json",
                "limit": 5,  # Get multiple results to filter
                "addressdetails": 1
            }
            # Add country code bias if available
            if region_hint:
                country_code = self._get_region_code(region_hint)
                if country_code:
                    params["countrycodes"] = country_code

            headers = {
                "User-Agent": "Libertas-Travel/1.0 (https://github.com/aabtzu/libertas-travel)"
            }

            self._last_geocode_time = time.time()
            response = requests.get(url, params=params, headers=headers, timeout=10)
            data = response.json()

            if data and len(data) > 0:
                # Prefer non-street results (places, tourism, buildings over highways/roads)
                preferred_classes = ['place', 'tourism', 'building', 'amenity', 'leisure', 'aeroway']

                # First try to find a preferred result
                for result in data:
                    result_class = result.get('class', '')
                    if result_class in preferred_classes:
                        return {
                            "lat": float(result["lat"]),
                            "lng": float(result["lon"]),
                            "address": result.get("display_name", "")
                        }

                # Fall back to first result if no preferred match
                result = data[0]
                return {
                    "lat": float(result["lat"]),
                    "lng": float(result["lon"]),
                    "address": result.get("display_name", "")
                }
            else:
                return None
        except requests.Timeout:
            print(f"Geocoding timed out for: {query}")
            return None
        except Exception as e:
            print(f"Geocoding failed for {query}: {e}")
            return None

    def _get_region_code(self, region: str) -> str:
        """Convert region name to ISO 3166-1 alpha-2 code for Google."""
        codes = {
            "Italy": "it",
            "France": "fr",
            "Spain": "es",
            "India": "in",
            "Japan": "jp",
            "United Kingdom": "gb",
            "Germany": "de",
            "USA": "us",
            "United States": "us",
            "Austria": "at",
            "Slovakia": "sk",
            "Switzerland": "ch",
            "Netherlands": "nl",
            "Czech Republic": "cz",
            "Hungary": "hu",
            "Greece": "gr",
            "Portugal": "pt",
        }
        return codes.get(region, "")

    def _is_origin_flight(self, item, destination: str) -> bool:
        """Check if an item is a flight from the origin/home city (not the destination).

        We want to EXCLUDE flights that depart from home (e.g., FCO-VIE when going to Vienna)
        We want to INCLUDE flights that depart from destination (e.g., VIE-FCO returning home)
        """
        if item.category != 'flight':
            return False

        if not destination:
            return False

        dest_lower = destination.lower()
        location = (item.location.name or '').lower()
        title = (item.title or '').lower()

        # If location contains the destination city/country, KEEP it (not an origin flight)
        if dest_lower in location:
            return False

        # Check for destination-related terms in location
        dest_terms = {
            'vienna': ['vienna', 'wien', 'vie'],
            'austria': ['austria', 'vienna', 'wien', 'vie'],
            'bratislava': ['bratislava', 'bts'],
            'slovakia': ['slovakia', 'bratislava'],
        }
        for dest_key, terms in dest_terms.items():
            if dest_key in dest_lower:
                for term in terms:
                    if term in location:
                        return False  # Location is at destination, keep it

        # Common home/origin airports - filter these OUT
        home_airports = ['fco', 'fiumicino', 'jfk', 'lax', 'sfo', 'ord', 'lhr', 'cdg', 'ewr']
        for home in home_airports:
            if home in location:
                return True  # This is a home airport flight, filter it

        # Common home cities - filter these OUT
        home_cities = ['rome', 'new york', 'los angeles', 'san francisco', 'chicago', 'london', 'paris']
        for city in home_cities:
            if city in location:
                return True  # This is from a home city, filter it

        return False

    def create_map_data(self, itinerary: Itinerary) -> dict:
        """Create map data structure for Google Maps.

        Args:
            itinerary: The itinerary to map

        Returns:
            Dictionary with map data (center, zoom, markers)
        """
        # Ensure locations are geocoded
        self.geocode_locations(itinerary)

        # Get the destination region to identify origin flights
        destination = self._get_region_hint(itinerary)

        # Get locations with coordinates, excluding home locations and origin flights
        locations_with_coords = [
            (item, item.location)
            for item in itinerary.items
            if item.location.has_coordinates
            and not item.is_home_location
            and not self._is_origin_flight(item, destination)
        ]

        if not locations_with_coords:
            return {
                "center": {"lat": 0, "lng": 0},
                "zoom": 2,
                "markers": [],
                "route": [],
                "error": "No locations could be geocoded"
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

            markers.append({
                "position": {"lat": location.latitude, "lng": location.longitude},
                "title": item.title,
                "category": category,
                "color": color,
                "info": info_html,
            })

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
            f'<div style="font-family: Arial, sans-serif; max-width: 320px; font-size: 15px;">',
            f'<h4 style="margin: 0 0 10px 0; color: #1a73e8; font-size: 17px;">{idx}. {html.escape(item.title)}</h4>',
            f'<p style="margin: 0 0 6px 0; font-weight: bold; font-size: 15px;">{html.escape(location_name)}</p>',
        ]

        if item.date:
            date_str = item.date.strftime("%B %d, %Y")
            lines.append(f'<p style="margin: 0 0 6px 0; color: #666; font-size: 14px;"><em>{date_str}</em></p>')

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
            lines.append(f'<p style="margin: 0 0 6px 0; font-size: 13px; color: #888;">Conf: {html.escape(item.confirmation_number)}</p>')

        if item.location.address:
            lines.append(f'<p style="margin: 0 0 10px 0; font-size: 13px; color: #888;">{html.escape(item.location.address)}</p>')

        # Add action links
        lines.append('<div style="margin-top: 12px; padding-top: 10px; border-top: 1px solid #eee;">')

        # Google Maps link - search by place name for better results
        query = urllib.parse.quote(f"{item.title} {location_name}")
        maps_url = f"https://www.google.com/maps/search/?api=1&query={query}"
        maps_link_text = html.escape(location_name[:30]) + ("..." if len(location_name) > 30 else "")
        lines.append(f'<a href="{maps_url}" target="_blank" style="display: block; margin-bottom: 8px; color: #1a73e8; text-decoration: none; font-size: 14px;"><i class="fas fa-map-marker-alt" style="margin-right: 6px;"></i>{maps_link_text}</a>')

        # Website link (for hotels, restaurants, activities)
        if item.category in ("hotel", "lodging", "meal", "restaurant", "activity", "attraction"):
            if item.website_url:
                # Use the actual website URL from source data
                website_link = item.website_url
            else:
                # Fall back to DuckDuckGo's "I'm Feeling Ducky" redirect
                search_query = urllib.parse.quote(f"{item.title} {location_name} official site")
                website_link = f"https://duckduckgo.com/?q=\\{search_query}"
            lines.append(f'<a href="{website_link}" target="_blank" style="display: block; color: #1a73e8; text-decoration: none; font-size: 14px;"><i class="fas fa-globe" style="margin-right: 6px;"></i>Website</a>')

        lines.append('</div>')
        lines.append('</div>')
        return "".join(lines)
