"""Prompt building and response parsing for the create chat handler."""

from __future__ import annotations

import json
import re
from typing import Any


def _build_venue_chat_prompt(
    trip_context: dict[str, Any],
    curated_venues: list[dict] = None,
    style_rules: str | None = None,
) -> str:
    """Build the system prompt for venue-focused chat."""
    destination = trip_context.get("destination", "your destination")
    dates = trip_context.get("dates", "")
    days = trip_context.get("days", [])
    ideas = trip_context.get("ideas", [])
    curated_venues = curated_venues or []

    itinerary_context = ""

    if days:
        itinerary_context += "\n\nCurrent itinerary by day:"
        for day in days:
            day_num = day.get("day_number", "?")
            day_date = day.get("date", "TBD")
            items = day.get("items", [])
            if items:
                itinerary_context += f"\n  Day {day_num} ({day_date}):"
                for item in items:
                    title = item.get("title", "Untitled")
                    category = item.get("category", "")
                    time = item.get("time", "")
                    location = item.get("location", "")
                    time_str = f" at {time}" if time else ""
                    loc_str = f" - {location}" if location else ""
                    itinerary_context += f"\n    - [{category}] {title}{time_str}{loc_str}"
            else:
                itinerary_context += f"\n  Day {day_num} ({day_date}): No activities planned yet"

    if ideas:
        itinerary_context += "\n\nIdeas pile (items user is considering but hasn't scheduled):"
        for item in ideas:
            title = item.get("title", "Untitled")
            category = item.get("category", "")
            notes = item.get("notes", "")
            notes_str = (
                f" - {notes[:50]}..."
                if notes and len(notes) > 50
                else (f" - {notes}" if notes else "")
            )
            itinerary_context += f"\n  - [{category}] {title}{notes_str}"

    day_reference = ""
    if days:
        day_reference = "\n\nAvailable days to add items to:"
        for day in days:
            day_num = day.get("day_number", "?")
            day_date = day.get("date", "TBD")
            day_reference += f"\n  - Day {day_num} ({day_date})"
    else:
        day_reference = "\n\nNo days set up yet. When adding items, use day=1 (or appropriate day number) to create days automatically. Only omit day for items that are truly unscheduled ideas."
        if dates:
            day_reference += f"\n\nIMPORTANT: The trip dates are {dates}. The first date is Day 1. Calculate day numbers for items with specific dates (e.g., if trip starts Apr 23 and item is on Apr 25, that's Day 3)."

    existing_titles = set()
    for day in days:
        for item in day.get("items", []):
            title = item.get("title", "").lower().strip()
            if title:
                existing_titles.add(title)
    for item in ideas:
        title = item.get("title", "").lower().strip()
        if title:
            existing_titles.add(title)

    existing_list = (
        "\n".join(f"  - {t}" for t in sorted(existing_titles))
        if existing_titles
        else "  (none yet)"
    )

    curated_context = ""
    if curated_venues:
        dest_lower = destination.lower() if destination else ""
        relevant_venues = [
            v
            for v in curated_venues
            if dest_lower in (v.get("city", "") or "").lower()
            or dest_lower in (v.get("country", "") or "").lower()
            or dest_lower in (v.get("state", "") or "").lower()
        ]

        if relevant_venues:
            curated_context = f"\n\n## CURATED VENUES DATABASE\n\nYou have access to {len(curated_venues)} vetted venues. Here are {len(relevant_venues)} venues near {destination}:\n"
            for v in relevant_venues[:50]:
                curated_context += f"- {v['name']}"
                if v.get("city"):
                    curated_context += f", {v['city']}"
                if v.get("venue_type"):
                    curated_context += f" ({v['venue_type']})"
                if v.get("michelin_stars"):
                    curated_context += f" ⭐{v['michelin_stars']} Michelin"
                if v.get("collection") and v["collection"] not in ("Saved", None):
                    curated_context += f" #{v['collection']}"
                curated_context += "\n"
            curated_context += "\nVenues from this list should be marked as source: CURATED\n"

    prompt = f"""You are a helpful travel planning assistant for Libertas, a travel itinerary app.

You have the ability to:
1. Add items to the user's itinerary using the add_to_itinerary tool
2. Edit existing items using the edit_itinerary_item tool (change notes, title, category, time, location, day, or move between days/ideas pile)
3. Delete items using the delete_itinerary_item tool
4. Fetch web pages using the fetch_web_page tool for external lists (Eater, Infatuation, blogs)

Current trip context:
- Destination: {destination}
- Dates: {dates if dates else "Not set yet"}
{itinerary_context}
{day_reference}
{curated_context}

## CRITICAL: AVOID DUPLICATES

The user already has these items in their trip (DO NOT suggest or add these again):
{existing_list}

When the user asks for "other", "more", "different", or "alternative" options, you MUST suggest DIFFERENT places than those listed above.

## WEB FETCH

Use the fetch_web_page tool when users mention:
- External lists: "Eater 38", "Infatuation", "Michelin Guide", blog posts
- Specific URLs they want to check
- "Check this page for recommendations"

## WHEN TO USE delete_itinerary_item TOOL

Use delete_itinerary_item when the user says "delete", "remove", or "get rid of" an existing item.
- "delete the Hertz rental" - pass title="Hertz Rental Car"
- "remove the flight on Jun 15" - pass the flight title and day number
- "delete the mariners game on jun 16" - pass title="Mariners Game", day=7 (the day number for Jun 16)
- When multiple items share the same title, ALWAYS include the day number to avoid deleting the wrong one.

Always confirm with something like "Removed Mariners Game from Day 7 (Jun 16)."

## WHEN TO USE edit_itinerary_item TOOL

Use edit_itinerary_item when the user wants to change something about an existing item:
- "switch the notes on X and Y" - swap notes between two items (use two edits)
- "change the notes for X to ..." - update notes
- "rename X to Y" - update title
- "move X to day 3" - change day
- "move X to the ideas pile" - set day=0
- "change the time for X to 2pm" - update time
- "the category for X should be meal" - update category

Always use the item's current title in find_title (case-insensitive match). Include ONLY the fields you're changing.
After calling edit_itinerary_item, write a short confirmation like "Updated the notes on Konomegi and Hanayatsu."

## WHEN TO USE add_to_itinerary TOOL

Use the tool when the user clearly wants to add a specific item, including:
- "add this", "add it", "add these", "put this in my trip", "include this", "yes add it"
- Direct add requests with specifics: "add mariners game at 6:40pm on Jun 17", "add dinner at Canlis on Jun 12"
- Confirmations after a proposal: "yes", "ok", "do it", "ok do it", "yes please"

NEVER use the tool when the user:
- Just mentions a place name (e.g., "ABBA Museum", "what about Noma?")
- Asks for information about a place
- Asks for suggestions or recommendations
- Says "maybe", "considering", "thinking about"

When in doubt, DO NOT use the tool. Just describe the place and let the user click the suggestion card to add it.

IMPORTANT: When you use add_to_itinerary, you MUST also write a short confirmation message in plain text (e.g. "Added Mariners Game to Day 8 (Jun 17) at 6:40 PM."). Never call the tool without accompanying text - a silent tool call leaves the user with a blank chat bubble and no idea what happened.

MULTIPLE ITEMS: When the user asks to add the same thing on multiple dates (e.g. "add Mariners game at 6:40pm on Jun 16 and 17, and 1:10pm on Jun 18"), add ALL of them in a SINGLE tool call as separate entries in the items array. Never add only the first one and ignore the rest.

When using add_to_itinerary, include the source field:
- source: "CURATED" - if the venue is in the curated database above
- source: "AI_PICK" - if it's a new recommendation not in the database

Categories: flight, meal, hotel, activity, attraction, transport, other
Day: ALWAYS use day number (1, 2, 3...) for scheduled items. Days will be auto-created if they don't exist yet. Only omit day for truly unscheduled "ideas" the user wants to consider later.

## FLIGHTS
When adding flights:
- category: "flight"
- location: Use the DESTINATION airport IATA code only (e.g., for "DEN-BIH" use "BIH"). Do NOT expand to city name, do NOT use origin airport.
- title: Include route like "United DEN → BIH"
- time: Departure time
- end_time: Arrival time
- notes: Airline, flight number, duration
- day: CRITICAL - Calculate the day number from the flight date! If trip starts on Apr 23 and flight is on Apr 23, that's day=1. If flight is on Apr 26, that's day=4 (Apr 23=1, Apr 24=2, Apr 25=3, Apr 26=4). Always calculate and include the day number so flights go to the correct day, not the ideas pile.
- YEAR: If no year is shown, use the NEXT occurrence of that date from today. E.g., if today is Jan 2026 and flight shows "Apr 23", use 2026. If today is Dec 2026 and flight shows "Apr 23", use 2027. Only use an explicit year if one is actually displayed.

## RESOLVING APPROXIMATE OR FUZZY PLACE NAMES

When the user says "something like X", "a place like X", or gives a name that sounds garbled or wrong:
- Use your knowledge to find the REAL place they mean. "Pizza by cranza" is likely "Pizza by Chakra". "The big museum" near Paris is the Louvre.
- If you are not confident, use fetch_web_page to search for the correct venue before responding.
- NEVER echo the garbled name back as a suggestion card. Find the real place.

## SPECIFIC PLACE REQUESTS

When the user names a SPECIFIC place (e.g., "ABBA Museum", "Eiffel Tower", "Noma"):
- Only create a card if you are CERTAIN the place is real and you know accurate facts about it.
- If you are not sure the place exists or you don't have reliable information about it, say so honestly: "I'm not sure that place exists - did you mean X?" Do NOT invent a description.
- Use the real, correct name - not what the user typed if they got it wrong.

When you are confident it is real, respond with:
**Exact Venue Name** - Brief description using only facts you know to be true.

Example: user says "abba museum stockholm"
**ABBA Museum** - Interactive museum on Djurgarden celebrating Sweden's legendary pop group. Book tickets in advance.

## VAGUE OR CATEGORY REQUESTS - ALWAYS EXPAND TO SPECIFIC NAMED PLACES

When the user gives a vague or category-level request (e.g., "dead sea beach", "FL beach", "a restaurant in Rome", "things to do in Paris"), do NOT create a suggestion card for the vague phrase itself. Instead:
- Think of the specific real named places that fit
- Return a numbered list of 3-5 actual named venues using **Venue Name** format
- Use your knowledge; fetch_web_page if you need current info

Examples:
- "dead sea beach" - list specific beaches like Kalia Beach, Ein Gedi Beach, Ein Bokek public beach, Mineral Beach
- "FL beach" or "Florida beach" - list specific beaches like Clearwater Beach, Siesta Key Beach, South Beach Miami
- "restaurant in Rome" - list specific restaurants by name
- "things to do in Paris" - list specific attractions by name

NEVER create a card that says "Dead Sea Beach" or "Florida Beach" - those are categories, not places.

## GENERAL SUGGESTIONS (only when asked)

When the user asks for general suggestions ("recommend restaurants", "what should I see", "ideas for activities"):
- Provide 3-5 options in a numbered list
- Format: **Venue Name** - Brief description. [Website](url)
- Do NOT use bold text (**) for anything except venue names

## FORMATTING RULES

CRITICAL: Only use **bold** for venue/place names that can be added to the itinerary.

NEVER use bold for:
- Features, highlights, exhibits, menu items
- Options like "Get more information" or "Add to itinerary"
- Questions or action choices
- Dates, times, or day references

Bad examples (creates multiple unwanted suggestions):
- **ABBA Museum** with **Costume exhibits** and **Audio guide**
- What would you prefer? **Get more info** or **Add to itinerary**?

Good example (creates exactly one suggestion):
**ABBA Museum** - Interactive museum celebrating Sweden's famous pop group, featuring costumes, holograms, and singalong booths. Book tickets in advance online.

Want me to add it to a specific day?
"""

    if style_rules:
        prompt += f"""

## WRITING STYLE RULES - follow these strictly

{style_rules}

Additional rule that always applies:
- If a curated venue has notes already written, prefer that wording for the description - it was written in the right style. Only supplement with extra details if the notes are very sparse.
"""

    return prompt


def _parse_add_items(response_text: str) -> list[dict[str, Any]]:
    """Parse items to add from JSON block in LLM response."""
    json_pattern = r'```json\s*(\{[\s\S]*?"add_items"[\s\S]*?\})\s*```'
    match = re.search(json_pattern, response_text)

    if match:
        try:
            data = json.loads(match.group(1))
            if "add_items" in data and isinstance(data["add_items"], list):
                return data["add_items"]
        except json.JSONDecodeError as e:
            print(f"Failed to parse add_items JSON: {e}")

    return []


def _clean_response_text(response_text: str) -> str:
    """Remove the JSON block from the response text for display."""
    cleaned = re.sub(r'```json\s*\{[\s\S]*?"add_items"[\s\S]*?\}\s*```', "", response_text)
    return cleaned.strip()


def _parse_suggested_items(
    response_text: str,
    curated_venues: list[dict] = None,
    web_fetch_context: dict = None,
    cross_reference_fn=None,
) -> list[dict[str, Any]]:
    """Parse suggested items from the LLM response.

    Cross-references with curated database to add source field.
    Returns a list of items that can be added to the trip.

    cross_reference_fn: callable(name, venues) -> dict|None, injected to avoid
    circular imports. Defaults to a local inline lookup if not provided.
    """
    items = []
    curated_venues = curated_venues or []

    def _default_cross_ref(name: str, venues: list[dict]) -> dict | None:
        name_lower = name.lower().strip()
        for v in venues:
            if v.get("name", "").lower() == name_lower:
                return v
            if name_lower in v.get("name", "").lower() or v.get("name", "").lower() in name_lower:
                return v
        return None

    _cross_ref = cross_reference_fn if cross_reference_fn is not None else _default_cross_ref

    pattern1 = r"\d+\.\s+\*\*([^*]+)\*\*\s*[-–—:]?\s*(.+?)(?=\n\d+\.|\n\n|$)"
    matches = re.findall(pattern1, response_text, re.DOTALL)

    if not matches:
        pattern2 = r"[-•]\s+\*\*([^*]+)\*\*\s*[-–—:]?\s*(.+?)(?=\n[-•]|\n\n|$)"
        matches = re.findall(pattern2, response_text, re.DOTALL)

    if not matches:
        pattern3 = r"\*\*([^*]+)\*\*\s*[-–—:]?\s*([^\n*]+)?"
        matches = re.findall(pattern3, response_text)

    if not matches:
        pattern4 = r"^([A-Z][A-Za-z\s&\']+?)\s*[-–—]\s*(.+?)$"
        matches = re.findall(pattern4, response_text, re.MULTILINE)
        matches = [(m[0].strip(), m[1].strip()) for m in matches if len(m[0].strip()) < 50]

    for match in matches:
        name = match[0].strip() if match[0] else ""
        description = match[1].strip() if len(match) > 1 and match[1] else ""

        if not name:
            continue

        name_lower = name.lower()
        skip_phrases = [
            "want me to",
            "would you like",
            "shall i",
            "should i",
            "let me know",
            "add it to",
            "get more",
            "suggest other",
            "nearby",
            "something else",
            "more information",
            "what you",
            "i can",
            "i already",
            "i shared",
            "your itinerary",
            "your trip",
            "which day",
            "if so",
            "available days",
            "day 1",
            "day 2",
            "day 3",
            "day 4",
            "day 5",
            "dec ",
            "december",
            "january",
            "february",
            "march",
            "april",
            "may ",
            "june",
            "july",
            "august",
            "september",
            "october",
            "november",
            "option",
            "prefer",
            "choose",
            "select",
            "pick one",
        ]
        if any(q in name_lower for q in skip_phrases):
            continue
        if name.rstrip().endswith("?") or name.rstrip().endswith(":"):
            continue
        skip_exact = [
            "yes",
            "no",
            "here",
            "there",
            "this",
            "that",
            "more",
            "other",
            "something else",
            "get more information",
            "add it to your itinerary",
        ]
        if name_lower.strip() in skip_exact:
            continue
        if len(name) > 60:
            continue
        if name_lower.startswith(
            ("i ", "you ", "we ", "let ", "if ", "what ", "how ", "why ", "when ", "where ")
        ):
            continue
        feature_words = [
            "exhibit",
            "guide",
            "tour",
            "technology",
            "experience",
            "section",
            "area",
            "room",
            "floor",
            "wing",
            "collection",
            "display",
            "booth",
            "interactive",
            "audio",
            "video",
            "virtual",
            "costume",
            "memorabilia",
        ]
        if any(fw in name_lower for fw in feature_words):
            continue

        website = None
        any_link_pattern = r"\[([^\]]+)\]\((https?://[^\)]+)\)"
        url_match = re.search(any_link_pattern, description)
        if url_match:
            website = url_match.group(2)
            description = re.sub(any_link_pattern, "", description).strip()
        else:
            plain_url = r"(https?://[^\s\)\]]+)"
            plain_match = re.search(plain_url, description)
            if plain_match:
                website = plain_match.group(1)
                description = re.sub(plain_url, "", description).strip()

        description = description.rstrip(" .-–")

        category = "activity"
        combined_lower = (name + " " + description).lower()
        if any(
            word in combined_lower
            for word in [
                "restaurant",
                "cafe",
                "bakery",
                "deli",
                "trattoria",
                "food",
                "cuisine",
                "dishes",
                "dining",
                "bistro",
            ]
        ):
            category = "meal"
        elif any(
            word in combined_lower
            for word in ["hotel", "hostel", "stay", "accommodation", "rooms", "inn", "lodge"]
        ):
            category = "hotel"
        elif any(
            word in combined_lower
            for word in [
                "museum",
                "gallery",
                "cathedral",
                "church",
                "monument",
                "palace",
                "castle",
                "theater",
                "theatre",
                "opera",
                "concert hall",
            ]
        ):
            category = "attraction"
        elif any(word in combined_lower for word in ["hike", "trail", "trek", "walk", "cycling"]):
            category = "activity"

        curated_match = _cross_ref(name, curated_venues)
        source = "CURATED" if curated_match else "AI_PICK"

        item = {
            "title": name,
            "category": category,
            "notes": description[:200] if len(description) > 200 else description,
            "source": source,
        }

        if curated_match and curated_match.get("collection"):
            item["collection"] = curated_match["collection"]
        elif web_fetch_context:
            item["collection"] = web_fetch_context.get("title", "")[:50]

        if website:
            item["website"] = website

        if curated_match:
            if curated_match.get("website") and not website:
                item["website"] = curated_match["website"]
            if curated_match.get("city"):
                item["location"] = curated_match["city"]

        items.append(item)

    items.sort(key=lambda x: (0 if x.get("source") == "CURATED" else 1, x.get("title", "")))

    return items
