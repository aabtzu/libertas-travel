"""Flight and airline utilities: IATA lookups, flight time scraping, Google Flights URL parsing."""

from __future__ import annotations

import re
import ssl
import urllib.request
from pathlib import Path

_DATA_DIR = Path(__file__).parent.parent.parent / "data"
_AIRLINE_CODES_CSV = _DATA_DIR / "airline_codes.csv"

# Cached lookup tables — loaded on first use
_airline_names: dict[str, str] | None = None  # IATA code -> display name
_airline_url_names: dict[str, str] | None = None  # IATA code -> URL-encoded name for flightera
_airports_db: dict | None = None  # airportsdata IATA lookup


def _load_airline_codes() -> tuple[dict[str, str], dict[str, str]]:
    """Load airline code -> name mappings from data/airline_codes.csv."""
    global _airline_names, _airline_url_names
    if _airline_names is not None and _airline_url_names is not None:
        return _airline_names, _airline_url_names
    import csv

    names: dict[str, str] = {}
    url_names: dict[str, str] = {}
    if _AIRLINE_CODES_CSV.exists():
        with open(_AIRLINE_CODES_CSV, newline="") as f:
            for row in csv.DictReader(f):
                code = row["code"].strip()
                names[code] = row["name"].strip()
                url_names[code] = row["url_name"].strip()
    _airline_names = names
    _airline_url_names = url_names
    return _airline_names, _airline_url_names


def _get_airport_city(iata_code: str) -> str:
    """Return URL-encoded city name for an IATA airport code.

    Uses the airportsdata package (~55,000 airports worldwide) so any airport
    code works without maintaining a local lookup file.
    Falls back to the raw IATA code if the airport is not found.
    """
    global _airports_db
    if _airports_db is None:
        try:
            import airportsdata

            _airports_db = airportsdata.load("IATA")
        except ImportError:
            _airports_db = {}

    airport = _airports_db.get(iata_code.upper())
    if airport and airport.get("city"):
        return airport["city"].replace(" ", "+")
    return iata_code  # Fall back to raw code — flightera may still resolve it


def lookup_flight_times(airline_code: str, flight_num: str, origin: str, dest: str) -> dict | None:
    """Look up departure/arrival times for a flight from flightera.net."""
    _, airline_url_names = _load_airline_codes()
    try:
        airline_name = airline_url_names.get(airline_code, airline_code)
        origin_city = _get_airport_city(origin)
        dest_city = _get_airport_city(dest)
        url = f"https://www.flightera.net/en/flight/{airline_name}-{origin_city}-{dest_city}/{airline_code}{flight_num}"
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
            },
        )
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
            html_bytes = resp.read()
        html_text = html_bytes.decode("utf-8", errors="ignore")
        dep_match = re.search(r'"departure_time"[:\s]+"?(\d{2}:\d{2})', html_text)
        arr_match = re.search(r'"arrival_time"[:\s]+"?(\d{2}:\d{2})', html_text)
        if dep_match and arr_match:
            return {"departure_time": dep_match.group(1), "arrival_time": arr_match.group(1)}
    except Exception:
        pass
    return None


def parse_google_flights_url(url: str) -> list | None:
    """Parse flight data from Google Flights URL. Returns list of flight dicts or None."""
    import base64
    from urllib.parse import parse_qs, urlparse

    parsed = urlparse(url)
    if "google.com" not in parsed.netloc or "/travel/flights" not in parsed.path:
        return None

    if "/flights/s/" in parsed.path:
        raise ValueError(
            "Shared Google Flights links (/flights/s/...) cannot be parsed directly. "
            "Please use the full booking URL from Google Flights."
        )

    params = parse_qs(parsed.query)
    tfs = params.get("tfs", [None])[0]
    if not tfs:
        return None

    try:
        missing_padding = (4 - len(tfs) % 4) % 4
        tfs_padded = tfs + "=" * missing_padding
        try:
            decoded = base64.urlsafe_b64decode(tfs_padded)
        except Exception:
            decoded = base64.b64decode(tfs_padded)
        decoded_str = decoded.decode("utf-8", errors="ignore")

        flights = []
        segment_pattern = r"\n.([A-Z]{3}).\n(\d{4}-\d{2}-\d{2})..([A-Z]{3})\*"
        segments = re.findall(segment_pattern, decoded_str)
        airline_flight_pattern = r"([A-Z]{2})2.(\d{3,4})"
        airline_matches = re.findall(airline_flight_pattern, decoded_str)

        airline_display_names, _ = _load_airline_codes()

        for i, (origin, date, dest) in enumerate(segments):
            if i < len(airline_matches):
                airline = airline_matches[i][0]
                flight_num = airline_matches[i][1]
                airline_name = airline_display_names.get(airline, airline)
                times = lookup_flight_times(airline, flight_num, origin, dest)
                flight_data = {
                    "title": f"{airline_name} {origin} → {dest}",
                    "category": "flight",
                    "origin": origin,
                    "destination": dest,
                    "date": date,
                    "location": dest,
                    "notes": f"Flight {airline}{flight_num}",
                    "time": times["departure_time"] if times else None,
                    "end_time": times["arrival_time"] if times else None,
                }
                flights.append(flight_data)

        return flights if flights else None
    except Exception:
        return None
