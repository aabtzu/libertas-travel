#!/usr/bin/env python3
"""Geocode venues missing lat/lng coordinates using OpenStreetMap Nominatim (free)."""

import time
import urllib.request
import urllib.parse
import json
import ssl
import database as db


def geocode_address(name: str, city: str, country: str) -> tuple:
    """Geocode an address using Nominatim (OpenStreetMap). Returns (lat, lng) or (None, None)."""
    # Build search query
    query_parts = []
    if name:
        query_parts.append(name)
    if city:
        query_parts.append(city)
    if country:
        query_parts.append(country)

    query = ", ".join(query_parts)
    if not query:
        return None, None

    # Nominatim API endpoint
    base_url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": query,
        "format": "json",
        "limit": 1
    }
    url = f"{base_url}?{urllib.parse.urlencode(params)}"

    # Required: User-Agent header for Nominatim
    headers = {
        "User-Agent": "Libertas Travel App (contact@example.com)"
    }

    try:
        ctx = ssl.create_default_context()
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, context=ctx, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))

        if data and len(data) > 0:
            lat = float(data[0]["lat"])
            lng = float(data[0]["lon"])
            return lat, lng
    except Exception as e:
        print(f"  Error geocoding: {e}")

    return None, None


def geocode_missing_venues():
    """Find and geocode all venues missing coordinates."""
    venues = db.get_all_venues()
    missing = [v for v in venues if not v.get('latitude') or not v.get('longitude')]

    print(f"Found {len(missing)} venues missing coordinates")

    if not missing:
        print("All venues have coordinates!")
        return

    success = 0
    failed = 0

    for i, venue in enumerate(missing):
        name = venue.get('name', '')
        city = venue.get('city', '')
        country = venue.get('country', '')

        print(f"[{i+1}/{len(missing)}] Geocoding: {name}, {city}, {country}...")

        lat, lng = geocode_address(name, city, country)

        if lat and lng:
            # Update venue in database
            db.update_venue_coordinates(venue['id'], lat, lng)
            print(f"  -> Found: {lat}, {lng}")
            success += 1
        else:
            # Try with just city and country
            lat, lng = geocode_address("", city, country)
            if lat and lng:
                db.update_venue_coordinates(venue['id'], lat, lng)
                print(f"  -> Found (city-level): {lat}, {lng}")
                success += 1
            else:
                print(f"  -> NOT FOUND")
                failed += 1

        # Rate limit: 1 request per second (Nominatim policy)
        time.sleep(1.1)

    print(f"\nDone! Geocoded {success} venues, {failed} failed.")


if __name__ == "__main__":
    geocode_missing_venues()
