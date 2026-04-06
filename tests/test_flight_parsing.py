"""Regression tests for flight parsing — IATA code handling (BIH = Bishop CA, not Birmingham).

These tests call the live Anthropic API and are marked @pytest.mark.integration.
Run with: .venv/bin/python3 -m pytest tests/test_flight_parsing.py -m integration -v
"""

from __future__ import annotations

import pytest

from agents.common.llm import SONNET, make_llm
from agents.create.upload_handlers import upload_plan_handler
from agents.itinerary.mapper import ItineraryMapper


_FLIGHT_TEXT = """\
Fri, Mar 20 · 11:36 AM – 1:24 PM    2 hr 48 min    Nonstop
United · Operated by SkyWest DBA United Express    DEN-BIH
"""

_CHAT_TOOLS = [
    {
        "name": "add_to_itinerary",
        "description": "Add one or more items to the user's trip itinerary.",
        "input_schema": {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "category": {
                                "type": "string",
                                "enum": [
                                    "flight", "meal", "hotel", "activity",
                                    "attraction", "transport", "other",
                                ],
                            },
                            "location": {
                                "type": "string",
                                "description": (
                                    "For FLIGHTS: use IATA airport code only (e.g. 'BIH', 'LAX')"
                                    " — do NOT expand to city names"
                                ),
                            },
                            "notes": {"type": "string"},
                            "day": {"type": "integer"},
                            "time": {"type": "string"},
                            "end_time": {"type": "string"},
                        },
                        "required": ["title", "category"],
                    },
                }
            },
            "required": ["items"],
        },
    }
]

_CHAT_SYSTEM = """\
You are a helpful travel planning assistant for Libertas, a travel itinerary app.

Current trip context:
- Destination: Mammoth, California
- Dates: Mar 20-25, 2026

## FLIGHTS
When adding flights:
- category: "flight"
- location: Use the DESTINATION airport IATA code only (e.g., for "DEN-BIH" use "BIH"). \
Do NOT expand to city name.
- title: Include route like "United DEN → BIH"
- time: Departure time
- end_time: Arrival time"""


@pytest.mark.integration
def test_file_upload_parsing():
    """upload_plan_handler keeps IATA codes as-is — BIH stays 'BIH', not 'Birmingham'."""
    result, status = upload_plan_handler(
        user_id=1,
        filename="flight.txt",
        file_data=_FLIGHT_TEXT.encode(),
        ext="txt",
    )

    assert status == 200, f"Handler returned error: {result}"
    items = result.get("items", [])
    assert len(items) > 0, "No items parsed from flight text"

    location = items[0].get("location", "")
    assert "birmingham" not in location.lower(), f"Location expanded to Birmingham: {location!r}"
    assert location.upper() == "BIH", f"Expected 'BIH', got {location!r}"


@pytest.mark.integration
def test_chat_tool_flow():
    """Chat tool uses IATA destination code — BIH not Birmingham for DEN-BIH flight."""
    llm = make_llm(model=SONNET, max_tokens=1000)
    response = llm.call_api(
        system_prompt=_CHAT_SYSTEM,
        messages=[{"role": "user", "content": f"Add this flight to my trip:\n{_FLIGHT_TEXT}"}],
        tools=_CHAT_TOOLS,
        return_full_response=True,
    )

    tool_call = next((b for b in response.content if b.type == "tool_use"), None)
    assert tool_call is not None, "Expected a tool_use block but got none"

    items = tool_call.input.get("items", [])
    assert len(items) > 0, "No items in tool call"

    location = items[0].get("location", "")
    assert "birmingham" not in location.lower(), f"Location expanded to Birmingham: {location!r}"
    assert "BIH" in location.upper(), f"Expected 'BIH' in location, got {location!r}"


@pytest.mark.integration
def test_iata_resolution():
    """ItineraryMapper._resolve_iata_code identifies BIH as Bishop CA, not Birmingham."""
    ItineraryMapper._iata_cache.clear()
    mapper = ItineraryMapper()

    result = mapper._resolve_iata_code("BIH", context="Flight: DEN → BIH, Trip destination: Mammoth, California")

    assert result != "", "Expected a non-empty resolution for BIH"
    assert "birmingham" not in result.lower(), f"Resolved to Birmingham: {result!r}"
    assert "bishop" in result.lower(), f"Expected Bishop CA, got: {result!r}"
