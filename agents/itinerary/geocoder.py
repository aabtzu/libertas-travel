"""Geocoding backends: Nominatim (OpenStreetMap) and Photon (Komoot).

Low-level geocoding logic extracted from mapper.py. ItineraryMapper delegates
to Geocoder for all HTTP requests to Nominatim/Photon.
"""

from __future__ import annotations

import time

import requests

# Nominatim requires a delay between requests (1 request per second)
NOMINATIM_DELAY = 1.1

_USER_AGENT = "Libertas-Travel/1.0 (https://github.com/aabtzu/libertas-travel)"


class Geocoder:
    """Handles HTTP requests to Nominatim and Photon geocoding APIs."""

    def __init__(self):
        self._last_geocode_time = 0

    def _rate_limit(self):
        """Enforce Nominatim's 1-request-per-second rate limit."""
        elapsed = time.time() - self._last_geocode_time
        if elapsed < NOMINATIM_DELAY:
            time.sleep(NOMINATIM_DELAY - elapsed)
        self._last_geocode_time = time.time()

    def geocode_structured(
        self, venue_name: str, city: str, region_hint: str = "", category: str = ""
    ) -> dict | None:
        """Nominatim structured search: passes venue name and city as separate params.

        Avoids free-text fuzzy matching where a city like "Gordes" gets confused
        with a similarly-named place like "Gorges" in a different region.
        """
        try:
            self._rate_limit()
            params = {
                "amenity": venue_name,
                "city": city,
                "format": "json",
                "limit": 5,
                "addressdetails": 1,
            }
            if region_hint:
                code = get_region_code(region_hint)
                if code:
                    params["countrycodes"] = code

            response = requests.get(
                "https://nominatim.openstreetmap.org/search",
                params=params,
                headers={"User-Agent": _USER_AGENT},
                timeout=10,
            )
            if response.status_code != 200:
                return None

            data = response.json()
            if data:
                print(
                    f"[GEOCODING] Structured '{venue_name}' in '{city}' → {len(data)} results",
                    flush=True,
                )
                best = select_best_result(data, category)
                if best:
                    print(
                        f"[GEOCODING] Structured selected: {best.get('display_name', '')[:60]}",
                        flush=True,
                    )
                    return {
                        "lat": float(best["lat"]),
                        "lng": float(best["lon"]),
                        "address": best.get("display_name", ""),
                    }
            return None
        except Exception as e:
            print(f"[GEOCODING] Structured search failed for '{venue_name}' in '{city}': {e}")
            return None

    def geocode(self, query: str, region_hint: str = "", category: str = "") -> dict | None:
        """Free-text geocoding via Nominatim, with Photon fallback."""
        try:
            self._rate_limit()
            params = {
                "q": query,
                "format": "json",
                "limit": 10,
                "addressdetails": 1,
            }
            if region_hint:
                code = get_region_code(region_hint)
                if code:
                    params["countrycodes"] = code

            response = requests.get(
                "https://nominatim.openstreetmap.org/search",
                params=params,
                headers={"User-Agent": _USER_AGENT},
                timeout=10,
            )

            if response.status_code != 200:
                print(
                    f"[GEOCODING] Nominatim returned status {response.status_code} for: {query}",
                    flush=True,
                )
                return self.geocode_photon(query, category, region_hint)

            data = response.json()
            if data:
                print(f"[GEOCODING] Query '{query}' ({category}) returned {len(data)} results")
                best = select_best_result(data, category)
                if best:
                    print(f"[GEOCODING] Selected: {best.get('display_name', '')[:60]}")
                    return {
                        "lat": float(best["lat"]),
                        "lng": float(best["lon"]),
                        "address": best.get("display_name", ""),
                    }
                return None
            else:
                print(f"[GEOCODING] No results for: {query}")
                return None
        except requests.Timeout:
            print(f"[GEOCODING] Nominatim timeout for: {query}", flush=True)
        except Exception as e:
            print(f"[GEOCODING] Nominatim failed for {query}: {e}", flush=True)

        return self.geocode_photon(query, category, region_hint)

    def geocode_photon(self, query: str, category: str = "", region_hint: str = "") -> dict | None:
        """Fallback geocoder using Photon (komoot's free OSM geocoder)."""
        try:
            params: dict = {"q": query, "limit": 10}

            # Region bias coordinates
            region_coords = {
                "Germany": (51.1657, 10.4515),
                "Munich, Germany": (48.1351, 11.5820),
                "Nuremberg, Germany": (49.4521, 11.0767),
                "Austria": (47.5162, 14.5501),
                "Italy": (41.8719, 12.5674),
                "France": (46.6034, 1.8883),
                "Spain": (40.4637, -3.7492),
            }
            if region_hint and region_hint in region_coords:
                lat, lon = region_coords[region_hint]
                params["lat"] = lat
                params["lon"] = lon

            response = requests.get(
                "https://photon.komoot.io/api/",
                params=params,
                headers={"User-Agent": "Libertas-Travel/1.0"},
                timeout=10,
            )
            if response.status_code != 200:
                print(f"[GEOCODING] Photon returned status {response.status_code}", flush=True)
                return None

            features = response.json().get("features", [])
            print(f"[GEOCODING] Photon returned {len(features)} features for: {query}", flush=True)

            if features:
                results = _photon_features_to_results(features, region_hint)
                best = select_best_result(results, category)
                if best:
                    print(
                        f"[GEOCODING] Photon found: {best.get('display_name', '')[:60]}",
                        flush=True,
                    )
                    return {
                        "lat": float(best["lat"]),
                        "lng": float(best["lon"]),
                        "address": best.get("display_name", ""),
                    }
            print(f"[GEOCODING] Photon no results for: {query}", flush=True)
            return None
        except Exception as e:
            print(f"[GEOCODING] Photon fallback failed: {e}", flush=True)
            return None


# ---------------------------------------------------------------------------
# Pure functions (no state)
# ---------------------------------------------------------------------------


def _photon_features_to_results(features: list, region_hint: str) -> list:
    """Convert Photon GeoJSON features to our result format for selection."""
    country_mappings = {
        "Germany": ["germany", "deutschland"],
        "Austria": ["austria", "österreich"],
        "Italy": ["italy", "italia"],
        "France": ["france"],
        "Spain": ["spain", "españa"],
    }

    target_countries: list[str] = []
    if region_hint:
        for country, aliases in country_mappings.items():
            if country.lower() in region_hint.lower():
                target_countries = aliases
                break

    results = []
    for f in features:
        props = f.get("properties", {})
        coords = f.get("geometry", {}).get("coordinates", [])
        country = props.get("country", "")

        if target_countries and country:
            if not any(tc in country.lower() for tc in target_countries):
                continue

        if len(coords) >= 2:
            city = props.get("city", "") or props.get("town", "") or props.get("village", "")
            results.append(
                {
                    "lat": str(coords[1]),
                    "lon": str(coords[0]),
                    "class": props.get("osm_key", ""),
                    "type": props.get("osm_value", ""),
                    "display_name": f"{props.get('name', '')} {city} {country}".strip(),
                    "country": country,
                }
            )
    return results


def select_best_result(results: list, category: str) -> dict | None:
    """Select the best geocoding result based on category preferences."""
    if not results:
        return None

    category_preferences = {
        "hotel": [
            ("tourism", "hotel"),
            ("tourism", None),
            ("building", "hotel"),
            ("amenity", None),
        ],
        "lodging": [
            ("tourism", "hotel"),
            ("tourism", None),
            ("building", "hotel"),
            ("amenity", None),
        ],
        "restaurant": [
            ("amenity", "restaurant"),
            ("amenity", "cafe"),
            ("amenity", "fast_food"),
            ("amenity", None),
        ],
        "meal": [("amenity", "restaurant"), ("amenity", "cafe"), ("amenity", None)],
        "attraction": [
            ("tourism", "attraction"),
            ("tourism", None),
            ("historic", None),
            ("leisure", None),
            ("place", "village"),
            ("place", "town"),
            ("place", None),
        ],
        "activity": [("tourism", None), ("leisure", None), ("amenity", None), ("place", None)],
        "flight": [("aeroway", "aerodrome"), ("aeroway", None)],
        "transport": [("railway", "station"), ("railway", None), ("amenity", "bus_station")],
        "train_station": [("railway", "station"), ("railway", None)],
    }

    default_preferences = [
        ("tourism", None),
        ("amenity", None),
        ("place", None),
        ("building", None),
        ("leisure", None),
    ]

    preferences = category_preferences.get(category, default_preferences)

    for pref_class, pref_type in preferences:
        for result in results:
            r_class = result.get("class", "")
            r_type = result.get("type", "")
            if r_class == pref_class:
                if pref_type is None or r_type == pref_type:
                    return result

    # Avoid streets/highways, prefer places
    avoid_classes = ["highway", "boundary", "landuse"]
    for result in results:
        if result.get("class", "") not in avoid_classes:
            return result

    return results[0] if results else None


def get_region_code(region: str) -> str:
    """Convert region name to ISO 3166-1 alpha-2 country code."""
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
