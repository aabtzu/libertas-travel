"""LLM chat handler for venue recommendations and trip building."""

from __future__ import annotations

from typing import Any

import database as db
from agents.common.llm import SONNET, make_llm
from agents.create.chat_prompt import (
    _build_venue_chat_prompt,
    _clean_response_text,
    _parse_add_items,  # noqa: F401 - imported for callers that may use it directly
    _parse_suggested_items,
)
from agents.create.web_utils import fetch_webpage_for_chat


def _load_curated_venues() -> list[dict]:
    """Load curated venues from database for cross-referencing."""
    try:
        venues = db.get_all_venues()
        return venues if venues else []
    except Exception as e:
        print(f"Error loading curated venues: {e}")
        return []


def _cross_reference_curated(name: str, venues: list[dict]) -> dict | None:
    """Check if a venue name exists in the curated database."""
    name_lower = name.lower().strip()
    for v in venues:
        if v.get("name", "").lower() == name_lower:
            return v
        if name_lower in v.get("name", "").lower() or v.get("name", "").lower() in name_lower:
            return v
    return None


def create_chat_handler(user_id: int, data: dict[str, Any]) -> dict[str, Any]:
    """Handle LLM chat for venue recommendations.

    Supports:
    - Curated venue database cross-referencing
    - Web page fetching for external lists (Eater, etc.)
    - Source tagging (CURATED vs AI_PICK)
    """
    message = data.get("message", "").strip()
    if not message:
        return {"error": "No message provided"}, 400

    history = data.get("history", [])
    trip_context = data.get("trip_context", {})

    curated_venues = _load_curated_venues()
    system_prompt = _build_venue_chat_prompt(trip_context, curated_venues)

    messages = []
    for msg in history[-10:]:
        content = msg.get("content", "").strip()
        if content:
            messages.append({"role": msg.get("role", "user"), "content": content})
    messages.append({"role": "user", "content": message})

    tools = [
        {
            "name": "edit_itinerary_item",
            "description": "Edit an existing item already in the user's itinerary or ideas pile. Use this when the user wants to change the notes, title, category, time, location, or day of an existing item, or move it between days/ideas pile. Identify the item by its current title.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "edits": {
                        "type": "array",
                        "description": "List of edits to apply",
                        "items": {
                            "type": "object",
                            "properties": {
                                "find_title": {
                                    "type": "string",
                                    "description": "The current title of the item to find (case-insensitive match)",
                                },
                                "title": {
                                    "type": "string",
                                    "description": "New title (omit to keep existing)",
                                },
                                "notes": {
                                    "type": "string",
                                    "description": "New notes text (omit to keep existing)",
                                },
                                "category": {
                                    "type": "string",
                                    "enum": [
                                        "flight",
                                        "meal",
                                        "hotel",
                                        "activity",
                                        "attraction",
                                        "transport",
                                        "other",
                                    ],
                                    "description": "New category (omit to keep existing)",
                                },
                                "time": {
                                    "type": "string",
                                    "description": "New time in 24-hour format like '14:30' (omit to keep existing, empty string to clear)",
                                },
                                "location": {
                                    "type": "string",
                                    "description": "New location (omit to keep existing)",
                                },
                                "website": {
                                    "type": "string",
                                    "description": "New website URL (omit to keep existing)",
                                },
                                "day": {
                                    "type": "integer",
                                    "description": "Move item to this day number. Use 0 or omit to move to ideas pile. Omit entirely to keep in current location.",
                                },
                            },
                            "required": ["find_title"],
                        },
                    }
                },
                "required": ["edits"],
            },
        },
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
                                    "description": "Name of the place or activity",
                                },
                                "category": {
                                    "type": "string",
                                    "enum": [
                                        "flight",
                                        "meal",
                                        "hotel",
                                        "activity",
                                        "attraction",
                                        "transport",
                                        "other",
                                    ],
                                    "description": "Type of item",
                                },
                                "location": {
                                    "type": "string",
                                    "description": "City/address. For FLIGHTS: use IATA airport code only (e.g. 'BIH', 'LAX') - do NOT expand to city names",
                                },
                                "notes": {
                                    "type": "string",
                                    "description": "Additional details about the item",
                                },
                                "day": {
                                    "type": "integer",
                                    "description": "Day number to add to (1, 2, 3...). Omit to add to Ideas pile.",
                                },
                                "time": {
                                    "type": "string",
                                    "description": "Time in 24-hour format like '14:30' (optional)",
                                },
                                "website": {
                                    "type": "string",
                                    "description": "Official website URL for the place (e.g., https://example.com)",
                                },
                                "source": {
                                    "type": "string",
                                    "enum": ["CURATED", "AI_PICK"],
                                    "description": "CURATED if from the venue database, AI_PICK if a new recommendation",
                                },
                            },
                            "required": ["title", "category"],
                        },
                    }
                },
                "required": ["items"],
            },
        },
        {
            "name": "delete_itinerary_item",
            "description": "Delete one or more items from the user's itinerary or ideas pile. Use this when the user says 'delete', 'remove', or 'get rid of' an existing item.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "items": {
                        "type": "array",
                        "description": "List of items to delete",
                        "items": {
                            "type": "object",
                            "properties": {
                                "title": {
                                    "type": "string",
                                    "description": "Title of the item to delete (case-insensitive match)",
                                },
                                "day": {
                                    "type": "integer",
                                    "description": "Day number to narrow the match when multiple items share the same title (e.g. Mariners Game on day 7 vs day 8). Omit to delete all matching items.",
                                },
                            },
                            "required": ["title"],
                        },
                    }
                },
                "required": ["items"],
            },
        },
        {
            "name": "fetch_web_page",
            "description": "Fetch a web page to extract venue recommendations. Use this when users mention external lists like Eater, Infatuation, blog posts, or provide URLs.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The URL to fetch. For 'Eater 38 Rome', try 'https://www.eater.com/maps/best-restaurants-rome'",
                    }
                },
                "required": ["url"],
            },
        },
    ]

    try:
        llm = make_llm(model=SONNET, max_tokens=2048)

        max_iterations = 3
        web_fetch_context = None
        add_items = []
        edit_items = []
        delete_items = []
        response_text = ""

        for _iteration in range(max_iterations):
            response = llm.call_api(
                system_prompt=system_prompt,
                messages=messages,
                tools=tools,
                return_full_response=True,
            )

            tool_use_block = None

            for block in response.content:
                if block.type == "text":
                    response_text = block.text
                elif block.type == "tool_use":
                    if block.name == "edit_itinerary_item":
                        tool_input = block.input
                        if "edits" in tool_input:
                            edit_items = tool_input["edits"]
                            for edit in edit_items:
                                print(
                                    f"[CREATE CHAT] Tool edit_item: find_title='{edit.get('find_title')}'"
                                )
                    elif block.name == "delete_itinerary_item":
                        tool_input = block.input
                        if "items" in tool_input:
                            delete_items = tool_input["items"]
                            for d in delete_items:
                                print(
                                    f"[CREATE CHAT] Tool delete_item: title='{d.get('title')}' day={d.get('day')}"
                                )
                    elif block.name == "add_to_itinerary":
                        tool_input = block.input
                        if "items" in tool_input:
                            add_items = tool_input["items"]
                            for item in add_items:
                                print(
                                    f"[CREATE CHAT] Tool add_items: title='{item.get('title')}', category='{item.get('category')}', location='{item.get('location')}'"
                                )
                    elif block.name == "fetch_web_page":
                        tool_use_block = block

            if tool_use_block and tool_use_block.name == "fetch_web_page":
                url = tool_use_block.input.get("url", "")
                print(f"[CREATE CHAT] Fetching web page: {url}")

                fetch_result = fetch_webpage_for_chat(url)

                if fetch_result["success"]:
                    web_fetch_context = {"url": url, "title": fetch_result.get("title", url)}
                    tool_result_content = f"Successfully fetched page: {fetch_result['title']}\n\nContent:\n{fetch_result['text']}"
                else:
                    tool_result_content = (
                        f"Failed to fetch page: {fetch_result.get('error', 'Unknown error')}"
                    )

                messages.append({"role": "assistant", "content": response.content})
                messages.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": tool_use_block.id,
                                "content": tool_result_content,
                            }
                        ],
                    }
                )
                continue

            break

        display_text = _clean_response_text(response_text)
        suggested_items = _parse_suggested_items(
            display_text, curated_venues, web_fetch_context, _cross_reference_curated
        )

        for item in add_items:
            if "source" not in item:
                curated_match = _cross_reference_curated(item.get("title", ""), curated_venues)
                item["source"] = "CURATED" if curated_match else "AI_PICK"
            if web_fetch_context and not item.get("collection"):
                item["collection"] = web_fetch_context.get("title", "")[:50]

        print(f"[CREATE CHAT] Response text length: {len(display_text)}")
        print(f"[CREATE CHAT] Parsed suggested items: {len(suggested_items)}")
        for i, item in enumerate(suggested_items[:5]):
            source = item.get("source", "NONE")
            print(f"[CREATE CHAT] Item {i + 1}: {item.get('title', 'NO TITLE')} - source={source}")

        return {
            "success": True,
            "response": display_text,
            "suggested_items": suggested_items,
            "add_items": add_items,
            "edit_items": edit_items,
            "delete_items": delete_items,
        }, 200

    except Exception as e:
        print(f"Create chat error: {e}")
        import traceback

        traceback.print_exc()
        return {"error": f"Chat service error: {str(e)}"}, 500
