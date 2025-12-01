"""Generate interactive maps from itineraries using Google Maps."""

from __future__ import annotations

import os
import json
import html
import requests
from pathlib import Path
from typing import Optional, Union

from .models import Itinerary, Location


# Maximum number of locations to geocode (to avoid long waits)
MAX_GEOCODE_LOCATIONS = 50

# Google Maps marker colors by category
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
    """Generate interactive maps from itineraries using Google Maps."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("GOOGLE_MAPS_API_KEY", "")
        self._geocode_failures = 0

    def geocode_locations(self, itinerary: Itinerary) -> Itinerary:
        """Add coordinates to all locations in the itinerary using Google Geocoding API."""
        if not self.api_key:
            print("Warning: No GOOGLE_MAPS_API_KEY set, skipping geocoding")
            return itinerary

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
        """Extract a region hint from the itinerary for biasing geocoding."""
        # Look for country/region in title or locations
        regions = []
        if itinerary.title:
            regions.append(itinerary.title)
        for item in itinerary.items[:10]:  # Check first 10 items
            if item.location.name:
                regions.append(item.location.name)

        # Common region patterns
        region_text = " ".join(regions).lower()
        if "italy" in region_text or "venice" in region_text or "rome" in region_text:
            return "Italy"
        elif "france" in region_text or "paris" in region_text:
            return "France"
        elif "spain" in region_text or "barcelona" in region_text:
            return "Spain"
        elif "india" in region_text or "delhi" in region_text or "jaipur" in region_text:
            return "India"
        elif "japan" in region_text or "tokyo" in region_text:
            return "Japan"
        elif "uk" in region_text or "london" in region_text or "england" in region_text:
            return "United Kingdom"
        elif "germany" in region_text or "berlin" in region_text:
            return "Germany"
        return ""

    def _geocode_item(self, item, region_hint: str = "") -> None:
        """Geocode an item using its title and location info."""
        location = item.location

        # Build smart queries - use item title (actual place name) + location context
        queries = []

        # If we have an address, try it first
        if location.address:
            queries.append(location.address)

        # Use item title with location context (e.g., "Sina Centurion Palace Venice Italy")
        if item.title and location.name:
            # Don't add location if title already contains it
            if location.name.lower() not in item.title.lower():
                queries.append(f"{item.title}, {location.name}")
            else:
                queries.append(item.title)
        elif item.title:
            if region_hint:
                queries.append(f"{item.title}, {region_hint}")
            queries.append(item.title)

        # Fall back to just location name
        if location.name:
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
        """Execute a geocoding request and return result or None."""
        try:
            url = "https://maps.googleapis.com/maps/api/geocode/json"
            params = {
                "address": query,
                "key": self.api_key
            }
            # Add region bias if available
            if region_hint:
                # Use component filtering for better regional results
                params["region"] = self._get_region_code(region_hint)

            response = requests.get(url, params=params, timeout=5)
            data = response.json()

            if data.get("status") == "OK" and data.get("results"):
                result = data["results"][0]
                geo = result["geometry"]["location"]
                return {
                    "lat": geo["lat"],
                    "lng": geo["lng"],
                    "address": result.get("formatted_address", "")
                }
            elif data.get("status") == "ZERO_RESULTS":
                return None
            else:
                print(f"Geocoding error for {query}: {data.get('status')}")
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
        }
        return codes.get(region, "")

    def create_map_data(self, itinerary: Itinerary) -> dict:
        """Create map data structure for Google Maps.

        Args:
            itinerary: The itinerary to map

        Returns:
            Dictionary with map data (center, zoom, markers)
        """
        # Ensure locations are geocoded
        self.geocode_locations(itinerary)

        # Get locations with coordinates, excluding home locations
        locations_with_coords = [
            (item, item.location)
            for item in itinerary.items
            if item.location.has_coordinates and not item.is_home_location
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

        lines = [
            f'<div style="font-family: Arial, sans-serif; max-width: 320px; font-size: 15px;">',
            f'<h4 style="margin: 0 0 10px 0; color: #1a73e8; font-size: 17px;">{idx}. {html.escape(item.title)}</h4>',
            f'<p style="margin: 0 0 6px 0; font-weight: bold; font-size: 15px;">{html.escape(item.location.name)}</p>',
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
        query = urllib.parse.quote(f"{item.title} {item.location.name}")
        maps_url = f"https://www.google.com/maps/search/?api=1&query={query}"
        maps_link_text = html.escape(item.location.name[:30]) + ("..." if len(item.location.name) > 30 else "")
        lines.append(f'<a href="{maps_url}" target="_blank" style="display: block; margin-bottom: 8px; color: #1a73e8; text-decoration: none; font-size: 14px;"><i class="fas fa-map-marker-alt" style="margin-right: 6px;"></i>{maps_link_text}</a>')

        # Website link (for hotels, restaurants, activities)
        if item.category in ("hotel", "lodging", "meal", "restaurant", "activity", "attraction"):
            if item.website_url:
                # Use the actual website URL from source data
                website_link = item.website_url
            else:
                # Fall back to DuckDuckGo's "I'm Feeling Ducky" redirect
                search_query = urllib.parse.quote(f"{item.title} {item.location.name} official site")
                website_link = f"https://duckduckgo.com/?q=\\{search_query}"
            lines.append(f'<a href="{website_link}" target="_blank" style="display: block; color: #1a73e8; text-decoration: none; font-size: 14px;"><i class="fas fa-globe" style="margin-right: 6px;"></i>Website</a>')

        lines.append('</div>')
        lines.append('</div>')
        return "".join(lines)
