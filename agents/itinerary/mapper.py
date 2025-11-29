"""Generate interactive maps from itineraries using Folium."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Union

import folium
from folium import plugins
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
from geopy.exc import GeocoderTimedOut, GeocoderServiceError

from .models import Itinerary, Location


# Maximum number of locations to geocode (to avoid long waits)
MAX_GEOCODE_LOCATIONS = 20

# Map marker colors by location type
MARKER_COLORS = {
    "hotel": "blue",
    "restaurant": "orange",
    "attraction": "green",
    "airport": "red",
    "train_station": "purple",
    "transport": "gray",
    "other": "lightblue",
}

# Font Awesome icons by category
MARKER_ICONS = {
    "hotel": "bed",
    "restaurant": "utensils",
    "attraction": "camera",
    "airport": "plane",
    "train_station": "train",
    "transport": "car",
    "flight": "plane",
    "meal": "utensils",
    "activity": "star",
    "other": "map-marker",
}


class ItineraryMapper:
    """Generate interactive maps from itineraries."""

    def __init__(self, user_agent: str = "libertas-itinerary-agent"):
        # Add timeout of 5 seconds to avoid hanging on slow responses
        self.geolocator = Nominatim(user_agent=user_agent, timeout=5)
        self.geocode = RateLimiter(
            self.geolocator.geocode, min_delay_seconds=1, max_retries=1
        )
        self._geocode_failures = 0

    def geocode_locations(self, itinerary: Itinerary) -> Itinerary:
        """Add coordinates to all locations in the itinerary."""
        # Limit geocoding to avoid long waits
        locations_to_geocode = [
            item for item in itinerary.items
            if not item.location.has_coordinates
        ]

        # Only geocode up to MAX_GEOCODE_LOCATIONS
        for item in locations_to_geocode[:MAX_GEOCODE_LOCATIONS]:
            # Stop if too many failures (likely network/rate limit issue)
            if self._geocode_failures >= 3:
                print(f"Stopping geocoding after {self._geocode_failures} consecutive failures")
                break
            self._geocode_location(item.location)

        if len(locations_to_geocode) > MAX_GEOCODE_LOCATIONS:
            print(f"Note: Only geocoded {MAX_GEOCODE_LOCATIONS} of {len(locations_to_geocode)} locations")

        return itinerary

    def _geocode_location(self, location: Location) -> None:
        """Geocode a single location."""
        # Try with address first, then just name
        queries = []
        if location.address:
            queries.append(location.address)
        queries.append(location.name)

        for query in queries:
            try:
                result = self.geocode(query)
                if result:
                    location.latitude = result.latitude
                    location.longitude = result.longitude
                    if not location.address:
                        location.address = result.address
                    self._geocode_failures = 0  # Reset on success
                    break
            except GeocoderTimedOut:
                print(f"Geocoding timed out for: {query}")
                self._geocode_failures += 1
                continue
            except GeocoderServiceError as e:
                print(f"Geocoding service error for {query}: {e}")
                self._geocode_failures += 1
                continue
            except Exception as e:
                print(f"Geocoding failed for {query}: {e}")
                self._geocode_failures += 1
                continue

    def create_map(
        self,
        itinerary: Itinerary,
        output_path: Optional[str | Path] = None,
        show_route: bool = True,
        cluster_markers: bool = False,
    ) -> folium.Map:
        """Create an interactive map from an itinerary.

        Args:
            itinerary: The itinerary to map
            output_path: Path to save the HTML file (optional)
            show_route: Whether to draw lines connecting locations in order
            cluster_markers: Whether to cluster nearby markers

        Returns:
            The folium Map object
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
            # Create empty map centered on a default location
            m = folium.Map(location=[0, 0], zoom_start=2)
            folium.Marker(
                [0, 0],
                popup="No locations could be geocoded",
                icon=folium.Icon(color="red", icon="exclamation-triangle", prefix="fa"),
            ).add_to(m)
            return m

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

        # Create map centered on locations with calculated zoom
        m = folium.Map(
            location=[center_lat, center_lon],
            zoom_start=zoom,
            tiles="cartodbpositron"
        )

        # Add markers
        if cluster_markers:
            marker_cluster = plugins.MarkerCluster()
            m.add_child(marker_cluster)
            marker_target = marker_cluster
        else:
            marker_target = m

        for idx, (item, location) in enumerate(locations_with_coords, 1):
            # Determine marker style
            color = MARKER_COLORS.get(
                location.location_type, MARKER_COLORS.get(item.category, "lightblue")
            )
            icon = MARKER_ICONS.get(
                item.category, MARKER_ICONS.get(location.location_type, "map-marker")
            )

            # Build popup content
            popup_html = self._build_popup(item, idx)

            # Create marker
            folium.Marker(
                [location.latitude, location.longitude],
                popup=folium.Popup(popup_html, max_width=300),
                tooltip=f"{idx}. {item.title}",
                icon=folium.Icon(color=color, icon=icon, prefix="fa"),
            ).add_to(marker_target)

        # Draw route connecting locations
        if show_route and len(locations_with_coords) > 1:
            route_coords = [
                [loc.latitude, loc.longitude] for _, loc in locations_with_coords
            ]
            folium.PolyLine(
                route_coords,
                weight=2,
                color="blue",
                opacity=0.6,
                dash_array="5, 10",
            ).add_to(m)

            # Add numbered circle markers for order
            for idx, (lat, lon) in enumerate(route_coords, 1):
                folium.CircleMarker(
                    [lat, lon],
                    radius=12,
                    color="white",
                    fill=True,
                    fill_color="blue",
                    fill_opacity=0.8,
                    weight=2,
                ).add_to(m)

                # Add number label
                folium.DivIcon

        # Add layer control and fullscreen
        folium.LayerControl().add_to(m)
        plugins.Fullscreen().add_to(m)

        # Save if output path provided
        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            m.save(str(output_path))

        return m

    def _build_popup(self, item, idx: int) -> str:
        """Build HTML content for a marker popup."""
        lines = [
            f"<h4>{idx}. {item.title}</h4>",
            f"<p><strong>{item.location.name}</strong></p>",
        ]

        if item.date:
            date_str = item.date.strftime("%B %d, %Y")
            lines.append(f"<p><em>{date_str}</em></p>")

        if item.start_time:
            time_str = item.start_time.strftime("%I:%M %p")
            if item.end_time:
                time_str += f" - {item.end_time.strftime('%I:%M %p')}"
            lines.append(f"<p>Time: {time_str}</p>")

        if item.description:
            lines.append(f"<p>{item.description}</p>")

        if item.confirmation_number:
            lines.append(f"<p><small>Conf: {item.confirmation_number}</small></p>")

        if item.location.address:
            lines.append(f"<p><small>{item.location.address}</small></p>")

        return "".join(lines)
