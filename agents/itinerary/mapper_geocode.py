"""Geocoding helpers for ItineraryMapper - standalone functions called by the mapper class."""

from __future__ import annotations

import re

# Cache for IATA code lookups to avoid repeated LLM calls (module-level, shared across instances)
_iata_cache: dict = {}


def extract_destination_with_llm(context: str) -> str:
    """Use LLM to extract the primary destination from trip context."""
    from agents.common.llm import SONNET, make_llm

    prompt = f"""Based on this trip information, identify the PRIMARY DESTINATION city and country.
Ignore origin/departure locations (like home airports). Focus on where the traveler is actually visiting.

{context}

Respond with ONLY the destination in format: "City, Country" (e.g., "Vienna, Austria" or "Tokyo, Japan").
If multiple destinations, pick the main one. If unclear, respond with just the country."""

    result = make_llm(model=SONNET, max_tokens=50).call_api(
        system_prompt="", messages=[{"role": "user", "content": prompt}]
    )
    # Clean up response - remove quotes, periods, etc.
    result = result.strip("\"'.")
    return result if result and len(result) < 100 else ""


def resolve_iata_code(iata: str, context: str = "") -> str:
    """Use LLM to resolve an IATA airport code to full airport name for geocoding.

    Args:
        iata: The 3-letter IATA airport code
        context: Optional context like flight title or trip destination to help disambiguate
    """
    # Check cache first (include context in cache key for disambiguation)
    cache_key = f"{iata}|{context}" if context else iata
    if cache_key in _iata_cache:
        return _iata_cache[cache_key]

    # Skip common non-airport 3-letter words
    skip_words = {"THE", "AND", "FOR", "DAY", "VIA", "NON", "ONE", "TWO", "NEW", "OLD"}
    if iata in skip_words:
        _iata_cache[cache_key] = ""
        return ""

    try:
        from agents.common.llm import SONNET, make_llm

        # Build a smarter prompt with context
        prompt = f"""What airport has the IATA code "{iata}"?

IATA codes are official 3-letter airport identifiers assigned by the International Air Transport Association.
Be precise - many codes are similar but refer to different airports.

{f"Context: This is for a flight with details: {context}" if context else ""}

Reply with ONLY the full airport name and location in this format:
"Airport Name, City, Country/State"

Examples:
- LAX -> "Los Angeles International Airport, Los Angeles, California"
- BIH -> "Eastern Sierra Regional Airport, Bishop, California"
- LHR -> "Heathrow Airport, London, United Kingdom"

If "{iata}" is not a valid IATA airport code, reply with just: NONE"""

        result = (
            make_llm(model=SONNET, max_tokens=100)
            .call_api(system_prompt="", messages=[{"role": "user", "content": prompt}])
            .strip('"')
        )
        if result and "NONE" not in result.upper() and len(result) < 150:
            _iata_cache[cache_key] = result
            print(f"[GEOCODING] Resolved IATA {iata} -> {result}")
            return result
    except Exception as e:
        print(f"[GEOCODING] Failed to resolve IATA {iata}: {e}")

    _iata_cache[cache_key] = ""
    return ""


def get_region_hint_fallback(itinerary) -> str:
    """Fallback when LLM extraction fails - try simpler LLM call with just the title."""
    if not itinerary.title:
        return ""

    try:
        from agents.common.llm import HAIKU, make_llm

        result = make_llm(model=HAIKU, max_tokens=30).call_api(
            system_prompt="",
            messages=[
                {
                    "role": "user",
                    "content": f"What country is this trip to? '{itinerary.title}'. Reply with ONLY the country name, or 'UNKNOWN' if unclear.",
                }
            ],
        )
        if result and "UNKNOWN" not in result.upper() and len(result) < 50:
            print(f"[GEOCODING] Fallback resolved region: {result}")
            return result
    except Exception as e:
        print(f"[GEOCODING] Fallback region extraction failed: {e}")

    return ""


def build_flight_queries(item, loc_name: str, region_hint: str) -> list:
    """Build geocoding queries for flight items."""
    queries = []

    # Build context for smarter IATA resolution
    context_parts = [f"Flight: {item.title}"]
    if region_hint:
        context_parts.append(f"Trip destination: {region_hint}")
    if loc_name:
        context_parts.append(f"Location field: {loc_name}")
    context = ", ".join(context_parts)

    # PRIORITY 1: Use the location field if it's an IATA code (this is the DESTINATION)
    print(f"[GEOCODING] _build_flight_queries: loc_name='{loc_name}', title='{item.title}'")
    loc_stripped = loc_name.strip() if loc_name else ""
    is_iata = bool(re.match(r"^[A-Z]{3}$", loc_stripped))
    print(f"[GEOCODING] loc_stripped='{loc_stripped}', is_iata={is_iata}")

    if loc_stripped and is_iata:
        airport_name = resolve_iata_code(loc_stripped, context)
        print(f"[GEOCODING] Resolved '{loc_stripped}' -> '{airport_name}'")
        if airport_name:
            queries.append(airport_name)
            print(f"[GEOCODING] Using location field IATA: {loc_stripped} -> {airport_name}")

    # PRIORITY 2: If location isn't an IATA code, try extracting from title (use LAST code = destination)
    if not queries:
        text_to_search = f"{item.title} {loc_name}"
        iata_codes = re.findall(r"\b([A-Z]{3})\b", text_to_search)
        # Use the LAST IATA code (typically the destination in "DEN to BIH")
        for iata in reversed(iata_codes):
            airport_name = resolve_iata_code(iata, context)
            if airport_name:
                queries.append(airport_name)
                print(f"[GEOCODING] Using title IATA (last): {iata} -> {airport_name}")
                break

    if loc_name:
        # Extract city from location like "Vienna (Vienna International, Terminal 3)"
        match = re.match(r"^([^(]+)", loc_name)
        city = match.group(1).strip() if match else loc_name.split()[0]

        # Add explicit airport queries
        queries.append(f"{city} International Airport")
        queries.append(f"{city} Airport")

        if "airport" not in loc_name.lower():
            queries.append(f"{loc_name} Airport")

        queries.append(loc_name)

    return queries


def geocode_item(item, region_hint: str, geocoder) -> int:
    """Geocode a single itinerary item using its title and location info.

    Args:
        item: The itinerary item to geocode
        region_hint: Region hint string for biasing geocoding results
        geocoder: A Geocoder instance for HTTP requests

    Returns:
        1 if geocoding failed, 0 if successful
    """
    location = item.location
    category = item.category or "other"

    # Build smart queries based on category
    queries = []

    # Get location context
    loc_name = location.name or ""
    title = item.title or ""

    # For restaurant/meal items, strip common meal-prefix words so "Dinner at
    # Le Mas Tourteron" becomes "Le Mas Tourteron" for geocoding queries.
    _MEAL_PREFIXES = (
        "dinner at ",
        "lunch at ",
        "breakfast at ",
        "brunch at ",
        "dinner - ",
        "lunch - ",
        "breakfast - ",
    )
    venue_title = title
    if category in ("restaurant", "meal"):
        lower = title.lower()
        for prefix in _MEAL_PREFIXES:
            if lower.startswith(prefix):
                venue_title = title[len(prefix) :]
                break

    # For flights, use special airport logic
    if category == "flight":
        queries = build_flight_queries(item, loc_name, region_hint)

    # For hotels/lodging - search venue name + city
    elif category in ("hotel", "lodging"):
        # Structured search first: separates venue name from city so Nominatim
        # can't fuzzy-match the city to a similarly-named place elsewhere.
        city_only = loc_name.split(",")[0].strip() if loc_name else ""
        if title and city_only:
            result = geocoder.geocode_structured(title, city_only, region_hint, category)
            if result:
                location.latitude = result["lat"]
                location.longitude = result["lng"]
                if not location.address:
                    location.address = result.get("address", "")
                return 0
        if title and loc_name:
            queries.append(f"{title}, {loc_name}")  # "Sofitel Munich, Munich"
            queries.append(f"{title} Hotel, {loc_name}")  # "Sofitel Munich Hotel, Munich"
        if title:
            queries.append(title)  # "Sofitel Munich"
            if region_hint:
                queries.append(f"{title}, {region_hint}")
        if loc_name:
            queries.append(loc_name)

    # For restaurants/meals - search venue name + city
    elif category in ("restaurant", "meal"):
        # Structured search first: separates venue name from city so Nominatim
        # can't fuzzy-match the city to a similarly-named place elsewhere.
        # e.g. "Le Mas Tourteron, Gordes" was matching "Gorges" (Loire-Atlantique).
        # Use venue_title (prefix-stripped) and extract just the city from loc_name.
        city_only = loc_name.split(",")[0].strip() if loc_name else ""
        if venue_title and city_only:
            result = geocoder.geocode_structured(venue_title, city_only, region_hint, category)
            if result:
                location.latitude = result["lat"]
                location.longitude = result["lng"]
                if not location.address:
                    location.address = result.get("address", "")
                return 0
        if venue_title and loc_name:
            queries.append(f"{venue_title}, {loc_name}")
            queries.append(f"{venue_title} Restaurant, {loc_name}")
        if venue_title:
            queries.append(venue_title)
            if region_hint:
                queries.append(f"{venue_title}, {region_hint}")
        if loc_name:
            queries.append(loc_name)

    # For attractions/activities - location name is usually the place itself
    elif category in ("attraction", "activity"):
        # If location looks like a specific place, search it directly
        if loc_name:
            if region_hint and region_hint.lower() not in loc_name.lower():
                queries.append(f"{loc_name}, {region_hint}")
            queries.append(loc_name)
        # Also try title if it's different from location
        if title and title.lower() != loc_name.lower():
            if loc_name:
                queries.append(f"{title}, {loc_name}")
            if region_hint:
                queries.append(f"{title}, {region_hint}")
            queries.append(title)

    # For transport (trains, etc)
    elif category in ("transport", "train_station"):
        if loc_name:
            queries.append(f"{loc_name} Station")
            queries.append(f"{loc_name} Train Station")
            queries.append(loc_name)
        if title:
            queries.append(title)

    # Default fallback for other categories
    else:
        if loc_name:
            if region_hint and region_hint.lower() not in loc_name.lower():
                queries.append(f"{loc_name}, {region_hint}")
            queries.append(loc_name)
        if title:
            if loc_name and loc_name.lower() not in title.lower():
                queries.append(f"{title}, {loc_name}")
            if region_hint:
                queries.append(f"{title}, {region_hint}")
            queries.append(title)

    # Try each query until we find a result
    for query in queries:
        result = geocoder.geocode(query, region_hint, category)
        if result:
            location.latitude = result["lat"]
            location.longitude = result["lng"]
            if not location.address:
                location.address = result.get("address", "")
            return 0

    # No results found - signal failure
    return 1
