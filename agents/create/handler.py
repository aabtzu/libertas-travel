"""API handlers for the Create Trip agent."""

import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from anthropic import Anthropic

import database as db


def create_trip_handler(user_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new draft trip.

    Args:
        user_id: The user's ID
        data: Request data containing title, start_date, end_date, num_days

    Returns:
        The created trip data or error
    """
    title = data.get('title', '').strip()
    if not title:
        return {'error': 'Trip title is required'}, 400

    start_date = data.get('start_date')
    end_date = data.get('end_date')
    num_days = data.get('num_days')

    # Validate num_days
    if num_days is not None:
        try:
            num_days = int(num_days)
            if num_days < 1 or num_days > 365:
                return {'error': 'Number of days must be between 1 and 365'}, 400
        except (ValueError, TypeError):
            return {'error': 'Invalid number of days'}, 400

    trip = db.create_draft_trip(
        user_id=user_id,
        title=title,
        start_date=start_date,
        end_date=end_date,
        num_days=num_days
    )

    if trip:
        return {'success': True, 'trip': trip}, 200
    else:
        return {'error': 'Failed to create trip'}, 500


def save_trip_handler(user_id: int, link: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Auto-save trip itinerary data.

    Args:
        user_id: The user's ID
        link: The trip's unique link
        data: Request data containing itinerary_data

    Returns:
        Success or error response
    """
    itinerary_data = data.get('itinerary_data')
    if itinerary_data is None:
        return {'error': 'No itinerary data provided'}, 400

    success = db.update_trip_itinerary_data(user_id, link, itinerary_data)

    if success:
        return {'success': True, 'saved_at': datetime.now().isoformat()}, 200
    else:
        return {'error': 'Failed to save trip'}, 500


def publish_trip_handler(user_id: int, link: str) -> Dict[str, Any]:
    """Publish a draft trip (set is_draft=False).

    Args:
        user_id: The user's ID
        link: The trip's unique link

    Returns:
        Success or error response
    """
    success = db.publish_draft(user_id, link)

    if success:
        return {'success': True}, 200
    else:
        return {'error': 'Failed to publish trip'}, 500


def get_trip_data_handler(user_id: int, link: str) -> Dict[str, Any]:
    """Get trip data for editing.

    Args:
        user_id: The user's ID
        link: The trip's unique link

    Returns:
        Trip data or error
    """
    trip = db.get_trip_by_link(user_id, link)

    if trip:
        return {'success': True, 'trip': trip}, 200
    else:
        return {'error': 'Trip not found'}, 404


def add_item_to_trip_handler(user_id: int, link: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Add an item to trip's ideas pile.

    Args:
        user_id: The user's ID
        link: The trip's unique link
        data: Request data containing the item

    Returns:
        Success or error response
    """
    item = data.get('item')
    if not item:
        return {'error': 'No item provided'}, 400

    # Ensure item has required fields
    if 'title' not in item:
        return {'error': 'Item must have a title'}, 400

    success = db.add_item_to_trip(user_id, link, item)

    if success:
        return {'success': True}, 200
    else:
        return {'error': 'Failed to add item to trip'}, 500


def create_chat_handler(user_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
    """Handle LLM chat for venue recommendations.

    Args:
        user_id: The user's ID
        data: Request data containing message and history

    Returns:
        LLM response with suggested items
    """
    message = data.get('message', '').strip()
    if not message:
        return {'error': 'No message provided'}, 400

    history = data.get('history', [])
    trip_context = data.get('trip_context', {})

    # Build system prompt for venue-focused chat
    system_prompt = _build_venue_chat_prompt(trip_context)

    # Build messages for LLM (filter out empty messages)
    messages = []
    for msg in history[-10:]:  # Last 10 messages for context
        content = msg.get('content', '').strip()
        if content:  # Only include messages with non-empty content
            messages.append({
                'role': msg.get('role', 'user'),
                'content': content
            })
    messages.append({'role': 'user', 'content': message})

    # Define tool for adding items to the trip
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
                                    "enum": ["meal", "hotel", "activity", "attraction", "transport", "other"],
                                    "description": "Type of item"
                                },
                                "location": {
                                    "type": "string",
                                    "description": "City or address"
                                },
                                "notes": {
                                    "type": "string",
                                    "description": "Additional details about the item"
                                },
                                "day": {
                                    "type": "integer",
                                    "description": "Day number to add to (1, 2, 3...). Omit to add to Ideas pile."
                                },
                                "time": {
                                    "type": "string",
                                    "description": "Time in 24-hour format like '14:30' (optional)"
                                }
                            },
                            "required": ["title", "category"]
                        }
                    }
                },
                "required": ["items"]
            }
        }
    ]

    try:
        client = Anthropic()
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2048,
            system=system_prompt,
            messages=messages,
            tools=tools
        )

        # Extract text response and tool use
        response_text = ""
        add_items = []

        for block in response.content:
            if block.type == "text":
                response_text = block.text
            elif block.type == "tool_use" and block.name == "add_to_itinerary":
                # Extract items from tool call
                tool_input = block.input
                if "items" in tool_input:
                    add_items = tool_input["items"]

        # Clean response text (remove any leftover JSON block for display)
        display_text = _clean_response_text(response_text)

        # Also parse any suggested items (for suggestions without add)
        suggested_items = _parse_suggested_items(display_text)

        return {
            'success': True,
            'response': display_text,
            'suggested_items': suggested_items,
            'add_items': add_items
        }, 200

    except Exception as e:
        print(f"Create chat error: {e}")
        return {'error': f'Chat service error: {str(e)}'}, 500


def _build_venue_chat_prompt(trip_context: Dict[str, Any]) -> str:
    """Build the system prompt for venue-focused chat."""

    destination = trip_context.get('destination', 'your destination')
    dates = trip_context.get('dates', '')
    days = trip_context.get('days', [])
    ideas = trip_context.get('ideas', [])

    # Build context about what's already planned
    itinerary_context = ""

    if days:
        itinerary_context += "\n\nCurrent itinerary by day:"
        for day in days:
            day_num = day.get('day_number', '?')
            day_date = day.get('date', 'TBD')
            items = day.get('items', [])
            if items:
                itinerary_context += f"\n  Day {day_num} ({day_date}):"
                for item in items:
                    title = item.get('title', 'Untitled')
                    category = item.get('category', '')
                    time = item.get('time', '')
                    location = item.get('location', '')
                    time_str = f" at {time}" if time else ""
                    loc_str = f" - {location}" if location else ""
                    itinerary_context += f"\n    - [{category}] {title}{time_str}{loc_str}"
            else:
                itinerary_context += f"\n  Day {day_num} ({day_date}): No activities planned yet"

    if ideas:
        itinerary_context += "\n\nIdeas pile (items user is considering but hasn't scheduled):"
        for item in ideas:
            title = item.get('title', 'Untitled')
            category = item.get('category', '')
            notes = item.get('notes', '')
            notes_str = f" - {notes[:50]}..." if notes and len(notes) > 50 else (f" - {notes}" if notes else "")
            itinerary_context += f"\n  - [{category}] {title}{notes_str}"

    # Build day reference for adding to specific days
    day_reference = ""
    if days:
        day_reference = "\n\nAvailable days to add items to:"
        for day in days:
            day_num = day.get('day_number', '?')
            day_date = day.get('date', 'TBD')
            day_reference += f"\n  - Day {day_num} ({day_date})"

    prompt = f"""You are a helpful travel planning assistant for Libertas, a travel itinerary app.

You have the ability to add items directly to the user's itinerary using the add_to_itinerary tool.

Current trip context:
- Destination: {destination}
- Dates: {dates if dates else 'Not set yet'}
{itinerary_context}
{day_reference}

## ADDING ITEMS TO THE ITINERARY

When the user asks you to ADD, include, schedule, book, or plan something:
1. Use the add_to_itinerary tool to add the item(s)
2. Provide a brief confirmation in your text response

Categories: meal, hotel, activity, attraction, transport, other
Day: Use day number (1, 2, 3...) or omit to add to Ideas pile
Time: 24-hour format like "14:30" (optional)

## SUGGESTING (when NOT asked to add)

When recommending options without being asked to add:
1. **Venue Name** - Description and why it's worth visiting.

Use the user's itinerary context to:
- Avoid suggesting places already added
- Suggest complementary activities nearby
- Help fill gaps in their schedule
"""
    return prompt


def _parse_add_items(response_text: str) -> List[Dict[str, Any]]:
    """Parse items to add from JSON block in LLM response.

    Looks for ```json blocks with add_items array.
    Returns list of items to directly add to the trip.
    """
    import re

    # Look for JSON code block with add_items
    json_pattern = r'```json\s*(\{[\s\S]*?"add_items"[\s\S]*?\})\s*```'
    match = re.search(json_pattern, response_text)

    if match:
        try:
            data = json.loads(match.group(1))
            if 'add_items' in data and isinstance(data['add_items'], list):
                return data['add_items']
        except json.JSONDecodeError as e:
            print(f"Failed to parse add_items JSON: {e}")

    return []


def _clean_response_text(response_text: str) -> str:
    """Remove the JSON block from the response text for display."""
    import re
    # Remove the JSON code block
    cleaned = re.sub(r'```json\s*\{[\s\S]*?"add_items"[\s\S]*?\}\s*```', '', response_text)
    return cleaned.strip()


def _parse_suggested_items(response_text: str) -> List[Dict[str, Any]]:
    """Parse suggested items from the LLM response.

    This is a simple parser that looks for structured suggestions.
    Returns a list of items that can be added to the trip.
    """
    items = []

    # Look for numbered items with bold names like "1. **Name**"
    import re
    pattern = r'\d+\.\s+\*\*([^*]+)\*\*\s*[-–—]?\s*(.+?)(?=\n\d+\.|\n\n|$)'
    matches = re.findall(pattern, response_text, re.DOTALL)

    for name, description in matches:
        name = name.strip()
        description = description.strip()

        # Try to determine category from keywords
        category = 'activity'
        desc_lower = description.lower()
        if any(word in desc_lower for word in ['restaurant', 'cafe', 'bakery', 'deli', 'trattoria', 'food', 'cuisine', 'dishes']):
            category = 'meal'
        elif any(word in desc_lower for word in ['hotel', 'hostel', 'stay', 'accommodation', 'rooms']):
            category = 'hotel'
        elif any(word in desc_lower for word in ['museum', 'gallery', 'cathedral', 'church', 'monument', 'palace', 'castle']):
            category = 'attraction'
        elif any(word in desc_lower for word in ['hike', 'trail', 'tour', 'trek', 'walk']):
            category = 'activity'

        items.append({
            'title': name,
            'category': category,
            'notes': description[:200] if len(description) > 200 else description
        })

    return items


def upload_plan_handler(user_id: int, filename: str, file_data: bytes, ext: str) -> Dict[str, Any]:
    """Handle uploaded file and extract trip items using LLM.

    Args:
        user_id: The user's ID
        filename: Original filename
        file_data: Raw file bytes
        ext: File extension

    Returns:
        Extracted items or error
    """
    import base64

    # Determine how to process the file
    content_for_llm = None
    image_data = None

    if ext in ['txt', 'html', 'eml']:
        # Text-based files - decode as text
        try:
            content_for_llm = file_data.decode('utf-8')
        except UnicodeDecodeError:
            content_for_llm = file_data.decode('latin-1')

    elif ext in ['png', 'jpg', 'jpeg', 'gif', 'webp']:
        # Image files - send as base64 to vision model
        image_data = base64.standard_b64encode(file_data).decode('utf-8')
        media_type = f"image/{ext}" if ext != 'jpg' else 'image/jpeg'

    elif ext == 'pdf':
        # PDF files - try to extract text, or use vision for scanned PDFs
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(stream=file_data, filetype="pdf")
            text_content = []
            for page in doc:
                text_content.append(page.get_text())
            content_for_llm = "\n".join(text_content)

            # If no text extracted, it might be a scanned PDF - try first page as image
            if not content_for_llm.strip():
                page = doc[0]
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                image_data = base64.standard_b64encode(pix.tobytes("png")).decode('utf-8')
                media_type = "image/png"

            doc.close()
        except ImportError:
            return {'error': 'PDF processing not available. Please install PyMuPDF: pip install pymupdf'}, 500
        except Exception as e:
            return {'error': f'Error reading PDF: {str(e)}'}, 400

    else:
        return {'error': f'Unsupported file type: {ext}'}, 400

    # Build the LLM prompt
    system_prompt = """You are a travel document parser. Extract travel-related items from the uploaded document.

For each item you find, extract:
- title: A clear name for the item (e.g., "Train to Florence", "Hotel Duomo Firenze")
- category: One of: flight, transport, hotel, meal, activity, attraction, other
- date: The date if available (YYYY-MM-DD format)
- time: The time if available (HH:MM format, 24-hour)
- location: City or address
- notes: Any additional relevant details (confirmation numbers, seat assignments, etc.)

Return your response as a JSON array of items. Example:
```json
[
  {
    "title": "Eurostar to Paris",
    "category": "transport",
    "date": "2024-06-15",
    "time": "08:30",
    "location": "London St Pancras",
    "notes": "Booking ref: ABC123, Seat 42A, Car 5"
  }
]
```

If you cannot extract any travel items, return an empty array: []
Only return the JSON array, no other text."""

    try:
        client = Anthropic()

        if image_data:
            # Use vision for images
            messages = [{
                'role': 'user',
                'content': [
                    {
                        'type': 'image',
                        'source': {
                            'type': 'base64',
                            'media_type': media_type,
                            'data': image_data
                        }
                    },
                    {
                        'type': 'text',
                        'text': f'Extract travel items from this document (filename: {filename})'
                    }
                ]
            }]
        else:
            # Use text content
            messages = [{
                'role': 'user',
                'content': f'Extract travel items from this document (filename: {filename}):\n\n{content_for_llm[:10000]}'  # Limit content
            }]

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2048,
            system=system_prompt,
            messages=messages
        )

        response_text = response.content[0].text.strip()

        # Parse the JSON response
        # Remove markdown code block if present
        if response_text.startswith('```'):
            lines = response_text.split('\n')
            response_text = '\n'.join(lines[1:-1] if lines[-1] == '```' else lines[1:])

        items = json.loads(response_text)

        if not isinstance(items, list):
            items = []

        return {
            'success': True,
            'items': items,
            'filename': filename
        }, 200

    except json.JSONDecodeError as e:
        print(f"JSON parse error: {e}")
        print(f"Response was: {response_text}")
        return {'error': 'Failed to parse extracted items'}, 500
    except Exception as e:
        print(f"Upload plan error: {e}")
        import traceback
        traceback.print_exc()
        return {'error': f'Error processing file: {str(e)}'}, 500
