"""Regression tests for flight parsing — IATA code handling (BIH = Bishop CA, not Birmingham).

These tests call the live API and are marked @pytest.mark.integration.
Run with: .venv/bin/python3 -m pytest tests/test_flight_parsing.py -m integration -v
"""

import json
import pytest

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.common.llm import make_llm, SONNET


@pytest.mark.integration
def test_file_upload_parsing():
    """File upload prompt keeps IATA codes as-is — BIH stays 'BIH', not 'Birmingham'."""
    from datetime import datetime
    current_year = datetime.now().year
    current_date = datetime.now().strftime('%Y-%m-%d')
    next_year = current_year + 1

    system_prompt = f"""You are a travel document parser. Extract travel-related items from the uploaded document.

Today's date is {current_date} (December {current_year}).

For each item you find, extract:
- title: A clear name for the item (e.g., "LH 2416 MUC → ARN", "Hotel Duomo Firenze", "Hertz Rental Car")
- category: One of: flight, transport, train, bus, hotel, meal, activity, attraction, other
- date: The start/pickup date in YYYY-MM-DD format. CRITICAL: When the year is not shown:
  * For months January through November, use year {next_year}
  * For December dates after today, use year {current_year}
  * Example: "Sep 10" without a year means {next_year}-09-10
- end_date: The end/return/dropoff date in YYYY-MM-DD format (for car rentals, hotels)
- time: Start/departure/pickup time (HH:MM format, 24-hour)
- end_time: End/arrival/dropoff time if available (HH:MM format, 24-hour)
- location: City or address (pickup location for rentals, destination airport CODE for flights - keep as IATA code like "BIH", do NOT expand to city name)
- notes: Any additional relevant details

For FLIGHTS: Keep airport IATA codes as-is (e.g., "DEN", "BIH", "LAX"). Do NOT expand airport codes to city names.

Return your response as a JSON array of items.
Only return the JSON array, no other text."""

    flight_text = """Fri, Mar 20 · 11:36 AM – 1:24 PM    2 hr 48 min    Nonstop
United · Operated by SkyWest DBA United Express    DEN-BIH"""

    llm = make_llm(model=SONNET, max_tokens=500)
    result = llm.call_api(
        system_prompt=system_prompt,
        messages=[{"role": "user", "content": f"Extract travel items from this document:\n\n{flight_text}"}]
    )

    # Strip markdown fences if present
    if "```json" in result:
        result = result.split("```json")[1].split("```")[0].strip()
    elif "```" in result:
        result = result.split("```")[1].split("```")[0].strip()

    items = json.loads(result.strip())
    assert len(items) > 0, "No items parsed from flight text"

    location = items[0].get('location', '')
    assert 'birmingham' not in location.lower(), f"Location expanded to Birmingham: {location!r}"
    assert location.upper() == 'BIH', f"Expected 'BIH', got {location!r}"


@pytest.mark.integration
def test_chat_tool_flow():
    """Chat tool uses IATA destination code — adds BIH not Birmingham when adding a DEN-BIH flight."""
    tools = [
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
                                    "enum": ["flight", "meal", "hotel", "activity", "attraction", "transport", "other"]
                                },
                                "location": {
                                    "type": "string",
                                    "description": "For FLIGHTS: use IATA airport code only (e.g. 'BIH', 'LAX') - do NOT expand to city names"
                                },
                                "notes": {"type": "string"},
                                "day": {"type": "integer"},
                                "time": {"type": "string"},
                                "end_time": {"type": "string"}
                            },
                            "required": ["title", "category"]
                        }
                    }
                },
                "required": ["items"]
            }
        }
    ]

    system_prompt = """You are a helpful travel planning assistant for Libertas, a travel itinerary app.

Current trip context:
- Destination: Mammoth, California
- Dates: Mar 20-25, 2026

## FLIGHTS
When adding flights:
- category: "flight"
- location: Use the DESTINATION airport IATA code only (e.g., for "DEN-BIH" use "BIH"). Do NOT expand to city name.
- title: Include route like "United DEN → BIH"
- time: Departure time
- end_time: Arrival time"""

    message = """Add this flight to my trip:
Fri, Mar 20 · 11:36 AM – 1:24 PM    2 hr 48 min    Nonstop
United · Operated by SkyWest DBA United Express    DEN-BIH"""

    llm = make_llm(model=SONNET, max_tokens=1000)
    response = llm.call_api(
        system_prompt=system_prompt,
        messages=[{"role": "user", "content": message}],
        tools=tools,
        return_full_response=True
    )

    tool_call = next((b for b in response.content if b.type == "tool_use"), None)
    assert tool_call is not None, "Expected a tool_use block but got none"

    items = tool_call.input.get('items', [])
    assert len(items) > 0, "No items in tool call"

    location = items[0].get('location', '')
    assert 'birmingham' not in location.lower(), f"Location expanded to Birmingham: {location!r}"
    assert 'BIH' in location.upper(), f"Expected 'BIH' in location, got {location!r}"


@pytest.mark.integration
def test_iata_resolution():
    """IATA resolver identifies BIH as Bishop, CA — not Birmingham."""
    iata = "BIH"
    context = "Flight: DEN → BIH, Trip destination: Mammoth, California"

    prompt = f"""What airport has the IATA code "{iata}"?

IATA codes are official 3-letter airport identifiers assigned by the International Air Transport Association.
Be precise - many codes are similar but refer to different airports.

Context: This is for a flight with details: {context}

Reply with ONLY the full airport name and location in this format:
"Airport Name, City, Country/State"

Examples:
- LAX -> "Los Angeles International Airport, Los Angeles, California"
- BIH -> "Eastern Sierra Regional Airport, Bishop, California"
- LHR -> "Heathrow Airport, London, United Kingdom"

If "{iata}" is not a valid IATA airport code, reply with just: NONE"""

    llm = make_llm(model=SONNET, max_tokens=100)
    result = llm.call_api(
        system_prompt="",
        messages=[{"role": "user", "content": prompt}]
    )

    assert 'birmingham' not in result.lower(), f"Resolved to Birmingham: {result!r}"
    assert 'bishop' in result.lower(), f"Expected Bishop CA, got: {result!r}"
