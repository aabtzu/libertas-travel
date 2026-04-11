"""Integration tests — require live Anthropic API and/or network access.

These tests exercise the full pipeline end-to-end using fixture files in
tests/fixtures/. Run with:

    .venv/bin/python3 -m pytest tests/test_integration.py -m integration -v

All tests are marked @pytest.mark.integration and are excluded from the
default test run.
"""

from __future__ import annotations

from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Itinerary parsing — upload_plan_handler
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_parse_text_fixture_paris_trip():
    """Parsing a multi-day text itinerary returns structured items with expected fields."""
    from agents.create.upload_handlers import upload_plan_handler

    fixture = (FIXTURES / "paris_trip.txt").read_bytes()
    result, status = upload_plan_handler(
        user_id=1,
        filename="paris_trip.txt",
        file_data=fixture,
        ext="txt",
    )

    assert status == 200, f"Handler error: {result}"
    items = result.get("items", [])
    assert len(items) >= 5, (
        f"Expected ≥5 items, got {len(items)}: {[i.get('title') for i in items]}"
    )

    # Should find at least one flight, hotel, and activity
    categories = {i.get("category") for i in items}
    assert "flight" in categories, f"No flight found. Categories: {categories}"
    assert "hotel" in categories, f"No hotel found. Categories: {categories}"

    # Flight should use IATA codes, not expanded city names
    flights = [i for i in items if i.get("category") == "flight"]
    for flight in flights:
        loc = (flight.get("location") or "").lower()
        assert "paris" not in loc or loc in ("cdg", "ory"), (
            f"Flight location should be IATA code, not city name: {flight.get('location')!r}"
        )


@pytest.mark.integration
def test_parse_json_fixture_tokyo_trip():
    """Parsing a JSON fixture returns items with dates and categories preserved."""
    from agents.create.upload_handlers import upload_plan_handler

    fixture_path = FIXTURES / "tokyo_trip.json"
    fixture = fixture_path.read_bytes()
    result, status = upload_plan_handler(
        user_id=1,
        filename="tokyo_trip.json",
        file_data=fixture,
        ext="json",
    )

    assert status == 200, f"Handler error: {result}"
    items = result.get("items", [])
    assert len(items) >= 5, f"Expected ≥5 items, got {len(items)}"

    # Verify at least one item has a date preserved
    dated = [i for i in items if i.get("date")]
    assert len(dated) > 0, "No items have dates set"

    # Verify flights kept IATA codes
    flights = [i for i in items if i.get("category") == "flight"]
    assert len(flights) >= 1, "No flights found in parsed result"
    for f in flights:
        loc = (f.get("location") or "").upper()
        assert loc in ("NRT", "KIX", "HND", ""), (
            f"Expected IATA code for flight location, got {loc!r}"
        )


@pytest.mark.integration
def test_parse_flight_text_fixture():
    """Single-flight text fixture: BIH location preserved as IATA code."""
    from agents.create.upload_handlers import upload_plan_handler

    fixture = (FIXTURES / "mammoth_flight.txt").read_bytes()
    result, status = upload_plan_handler(
        user_id=1,
        filename="mammoth_flight.txt",
        file_data=fixture,
        ext="txt",
    )

    assert status == 200, f"Handler error: {result}"
    items = result.get("items", [])
    assert len(items) >= 1, "No items parsed"

    location = (items[0].get("location") or "").upper()
    assert "BIRMINGHAM" not in location, f"IATA code expanded to city: {location!r}"
    assert location == "BIH", f"Expected 'BIH', got {location!r}"


# ---------------------------------------------------------------------------
# Geocoding with region hint — ItineraryMapper
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_geocode_paris_items():
    """geocode_locations adds coordinates to Paris items using region hint."""
    from agents.itinerary.mapper import ItineraryMapper
    from agents.itinerary.models import Itinerary, ItineraryItem, Location

    def _make_paris_item(title: str, loc: str) -> ItineraryItem:
        return ItineraryItem(
            title=title,
            location=Location(name=loc, address=None, location_type="activity"),
            category="activity",
        )

    itinerary = Itinerary(
        title="Paris Trip",
        items=[
            _make_paris_item("Eiffel Tower", "Eiffel Tower, Paris"),
            _make_paris_item("Louvre Museum", "Louvre Museum, Paris"),
        ],
    )

    mapper = ItineraryMapper()
    result = mapper.geocode_locations(itinerary)

    geocoded = [i for i in result.items if i.location.has_coordinates]
    assert len(geocoded) >= 1, "Expected at least one item to be geocoded"

    # Eiffel Tower should be in Paris bounding box (roughly lat 48.8, lng 2.3)
    eiffel = next((i for i in geocoded if "eiffel" in i.title.lower()), None)
    if eiffel:
        assert 48.0 < eiffel.location.latitude < 49.5, (
            f"Unexpected latitude for Eiffel Tower: {eiffel.location.latitude}"
        )
        assert 1.0 < eiffel.location.longitude < 3.5, (
            f"Unexpected longitude for Eiffel Tower: {eiffel.location.longitude}"
        )


@pytest.mark.integration
def test_region_hint_extracted_for_paris_itinerary():
    """_get_region_hint returns 'France' or 'Paris' for a Paris-titled itinerary."""
    from agents.itinerary.mapper import ItineraryMapper
    from agents.itinerary.models import Itinerary, ItineraryItem, Location

    itinerary = Itinerary(
        title="Paris Summer Trip",
        items=[
            ItineraryItem(
                title="Louvre",
                location=Location(name="Paris, France", address=None, location_type="attraction"),
                category="attraction",
            )
        ],
    )

    mapper = ItineraryMapper()
    hint = mapper._get_region_hint(itinerary)

    assert hint != "", "Expected a non-empty region hint"
    assert any(kw in hint.lower() for kw in ("france", "paris", "europe")), (
        f"Expected region hint to mention France/Paris/Europe, got: {hint!r}"
    )


# ---------------------------------------------------------------------------
# Explore chat — venue recommendations
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_explore_chat_returns_venue_recommendations():
    """explore_chat_handler returns at least one venue for a food query."""
    from agents.explore.handler import explore_chat_handler

    result, status = explore_chat_handler(
        message="Recommend a great restaurant in Paris",
        history=[],
    )

    assert status == 200, f"Handler error: {result}"
    reply = result.get("response", "")
    assert len(reply) > 20, f"Reply too short: {reply!r}"
    # Should mention some place or provide useful context
    assert any(
        kw in reply.lower()
        for kw in ("paris", "restaurant", "café", "bistro", "michelin", "recommend")
    ), f"Reply doesn't seem to contain restaurant recommendation: {reply[:200]!r}"


@pytest.mark.integration
def test_explore_chat_handles_followup():
    """explore_chat_handler uses conversation history for follow-up questions."""
    from agents.explore.handler import explore_chat_handler

    history = [
        {"role": "user", "content": "Recommend a restaurant in Tokyo"},
        {
            "role": "assistant",
            "content": "I recommend Sukiyabashi Jiro in Ginza, Tokyo — one of the world's most renowned sushi restaurants with three Michelin stars.",
        },
    ]

    result, status = explore_chat_handler(
        message="What about something more casual?",
        history=history,
    )

    assert status == 200, f"Handler error: {result}"
    reply = result.get("response", "")
    assert len(reply) > 20, f"Reply too short: {reply!r}"
