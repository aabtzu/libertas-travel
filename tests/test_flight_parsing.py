#!/usr/bin/env python3
"""Test flight parsing to ensure IATA codes are handled correctly."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from anthropic import Anthropic
import json

client = Anthropic()

def test_file_upload_parsing():
    """Test the file upload parsing prompt."""
    from datetime import datetime

    current_year = datetime.now().year
    current_date = datetime.now().strftime('%Y-%m-%d')
    next_year = current_year + 1

    # This is the EXACT prompt from handler.py
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
- notes: Any additional relevant details (confirmation numbers, vehicle type, drop-off location if different, etc.)

For FLIGHTS and TRAINS: Always extract both departure time (time) and arrival time (end_time) if shown.
For FLIGHTS: Keep airport IATA codes as-is (e.g., "DEN", "BIH", "LAX"). Do NOT try to expand airport codes to city names - just use the 3-letter code.
For CAR RENTALS: Extract pickup date/time as date/time, drop-off date/time as end_date/end_time. Include confirmation number and vehicle type in notes.

Return your response as a JSON array of items. Example:
```json
[
  {{
    "title": "LH 2416 MUC → ARN",
    "category": "flight",
    "date": "2025-12-17",
    "time": "12:10",
    "end_time": "14:25",
    "location": "ARN",
    "notes": "Lufthansa, Airbus A321, Economy, 2h 15m nonstop"
  }}
]
```

If you cannot extract any travel items, return an empty array: []
Only return the JSON array, no other text."""

    flight_text = """Fri, Mar 20 · 11:36 AM – 1:24 PM    2 hr 48 min    Nonstop
United · Operated by SkyWest DBA United Express    DEN-BIH"""

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=500,
        system=system_prompt,
        messages=[{"role": "user", "content": f"Extract travel items from this document:\n\n{flight_text}"}]
    )

    result = response.content[0].text

    # Parse JSON
    if "```json" in result:
        json_str = result.split("```json")[1].split("```")[0].strip()
    elif "```" in result:
        json_str = result.split("```")[1].split("```")[0].strip()
    else:
        json_str = result.strip()

    items = json.loads(json_str)

    print("=== File Upload Parsing Test ===")
    print(f"Input: DEN-BIH flight")

    if items:
        location = items[0].get('location', '')
        print(f"Location field: {location}")

        if location == 'BIH':
            print("✅ PASS: Location is 'BIH'")
            return True
        elif 'birmingham' in location.lower():
            print("❌ FAIL: Location expanded to Birmingham")
            return False
        else:
            print(f"⚠️ WARNING: Location is '{location}'")
            return False
    else:
        print("❌ FAIL: No items parsed")
        return False


def test_chat_tool_flow():
    """Test the chat tool flow."""

    # This matches the actual tool definition from handler.py
    tools = [
        {
            "name": "add_to_itinerary",
            "description": "Add one or more items to the user's trip itinerary. Use this tool whenever the user asks to add, include, schedule, book, or plan something for their trip.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "items": {
                        "type": "array",
                        "description": "List of items to add to the trip",
                        "items": {
                            "type": "object",
                            "properties": {
                                "title": {
                                    "type": "string",
                                    "description": "Name of the place or activity"
                                },
                                "category": {
                                    "type": "string",
                                    "enum": ["flight", "meal", "hotel", "activity", "attraction", "transport", "other"],
                                    "description": "Type of item"
                                },
                                "location": {
                                    "type": "string",
                                    "description": "City/address. For FLIGHTS: use IATA airport code only (e.g. 'BIH', 'LAX') - do NOT expand to city names"
                                },
                                "notes": {"type": "string", "description": "Additional details about the item"},
                                "day": {"type": "integer", "description": "Day number to add to (1, 2, 3...). Omit to add to Ideas pile."},
                                "time": {"type": "string", "description": "Time in 24-hour format like '14:30' (optional)"},
                                "end_time": {"type": "string", "description": "End/arrival time in 24-hour format (optional)"}
                            },
                            "required": ["title", "category"]
                        }
                    }
                },
                "required": ["items"]
            }
        }
    ]

    # This matches the actual system prompt section from handler.py
    system_prompt = """You are a helpful travel planning assistant for Libertas, a travel itinerary app.

You have the ability to add items to the user's itinerary using the add_to_itinerary tool.

Current trip context:
- Destination: Mammoth, California
- Dates: Mar 20-25, 2026

Categories: flight, meal, hotel, activity, attraction, transport, other

## FLIGHTS
When adding flights:
- category: "flight"
- location: Use the DESTINATION airport IATA code only (e.g., for "DEN-BIH" use "BIH"). Do NOT expand to city name, do NOT use origin airport.
- title: Include route like "United DEN → BIH"
- time: Departure time
- end_time: Arrival time
- notes: Airline, flight number, duration"""

    message = """Add this flight to my trip:
Fri, Mar 20 · 11:36 AM – 1:24 PM    2 hr 48 min    Nonstop
United · Operated by SkyWest DBA United Express    DEN-BIH"""

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1000,
        system=system_prompt,
        tools=tools,
        messages=[{"role": "user", "content": message}]
    )

    print("\n=== Chat Tool Flow Test ===")
    print(f"Input: DEN-BIH flight")

    for block in response.content:
        if block.type == "tool_use":
            items = block.input.get('items', [])
            if items:
                location = items[0].get('location', '')
                print(f"Location field: {location}")

                if location == 'BIH':
                    print("✅ PASS: Location is 'BIH'")
                    return True
                elif 'birmingham' in location.lower():
                    print("❌ FAIL: Location expanded to Birmingham")
                    return False
                else:
                    print(f"⚠️ WARNING: Location is '{location}'")
                    return 'BIH' in location.upper()

    print("❌ FAIL: No tool call made")
    return False


def test_iata_resolution():
    """Test the IATA code resolution."""

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

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=100,
        messages=[{"role": "user", "content": prompt}]
    )

    result = response.content[0].text.strip()

    print("\n=== IATA Resolution Test ===")
    print(f"Input: BIH")
    print(f"Result: {result}")

    if 'bishop' in result.lower():
        print("✅ PASS: Resolved to Bishop, CA")
        return True
    elif 'birmingham' in result.lower():
        print("❌ FAIL: Resolved to Birmingham")
        return False
    else:
        print(f"⚠️ WARNING: Unexpected result")
        return False


if __name__ == "__main__":
    print("=" * 50)
    print("FLIGHT PARSING TESTS")
    print("=" * 50)

    results = []

    results.append(("File Upload Parsing", test_file_upload_parsing()))
    results.append(("Chat Tool Flow", test_chat_tool_flow()))
    results.append(("IATA Resolution", test_iata_resolution()))

    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)

    all_passed = True
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{name}: {status}")
        if not passed:
            all_passed = False

    print()
    if all_passed:
        print("All tests passed!")
        sys.exit(0)
    else:
        print("Some tests failed!")
        sys.exit(1)
