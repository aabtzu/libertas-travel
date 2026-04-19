"""Explore agent handlers: venue loading and explore chat."""

from __future__ import annotations

import json
import re
from pathlib import Path

import database as db

VENUES_SEED_CSV = Path(__file__).parent.parent.parent / "data" / "venues_seed.csv"

_venues_cache: list[dict] | None = None


def load_venues() -> list[dict]:
    """Load venues from database. Auto-imports from CSV seed if database is empty."""
    global _venues_cache
    if _venues_cache is not None:
        return _venues_cache

    if db.get_venue_count() == 0:
        if VENUES_SEED_CSV.exists():
            print(f"[Explore] No venues in database, importing from {VENUES_SEED_CSV}...")
            imported = db.import_venues_from_csv(str(VENUES_SEED_CSV), source="curated")
            print(f"[Explore] Imported {imported} venues from seed CSV")
        else:
            print(f"[Explore] Warning: No venues and seed CSV not found at {VENUES_SEED_CSV}")
            return []

    venues = db.get_all_venues()
    _venues_cache = [
        {
            "id": v.get("id"),
            "name": v.get("name") or "",
            "city": v.get("city") or "",
            "state": v.get("state") or "",
            "country": v.get("country") or "",
            "venue_type": v.get("venue_type") or "",
            "cuisine_type": v.get("cuisine_type") or "",
            "michelin_stars": v.get("michelin_stars"),
            "chef": v.get("chef") or "",
            "collection": v.get("collection") or "",
            "description": v.get("description") or "",
            "notes": v.get("notes") or "",
            "source": v.get("source") or "curated",
            "latitude": v.get("latitude"),
            "longitude": v.get("longitude"),
            "website": v.get("website") or "",
            "google_maps_link": v.get("google_maps_link") or "",
        }
        for v in venues
    ]
    return _venues_cache


def explore_chat_handler(message: str, history: list[dict]) -> tuple[dict, int]:
    """Handle an explore chat message. Returns (result, status_code)."""
    from agents.common.llm import SONNET, make_llm
    from agents.create.web_utils import fetch_webpage_for_chat

    venues = load_venues()

    # Build venue summary stats for system prompt
    venue_types: dict[str, int] = {}
    cities: dict[str, int] = {}
    states: dict[str, int] = {}
    countries: dict[str, int] = {}
    for v in venues:
        vt = v.get("venue_type", "Other")
        venue_types[vt] = venue_types.get(vt, 0) + 1
        if v.get("city"):
            cities[v["city"]] = cities.get(v["city"], 0) + 1
        if v.get("state"):
            states[v["state"]] = states.get(v["state"], 0) + 1
        if v.get("country"):
            countries[v["country"]] = countries.get(v["country"], 0) + 1

    llm = make_llm(model=SONNET, max_tokens=2000)

    system_prompt = f"""You are a helpful travel assistant for Libertas, a travel planning app.
You have access to a curated database of {len(venues)} venues across {len(countries)} countries.

Available venue types: {", ".join(f"{k} ({v})" for k, v in sorted(venue_types.items(), key=lambda x: -x[1])[:10])}

Top cities: {", ".join(f"{k} ({v})" for k, v in sorted(cities.items(), key=lambda x: -x[1])[:20])}

States/Regions: {", ".join(f"{k} ({v})" for k, v in sorted(states.items(), key=lambda x: -x[1])[:30] if k)}

Countries: {", ".join(sorted(countries.keys()))}

## CAPABILITIES

1. **Curated Database Search**: Search the venue list below for trusted, vetted recommendations
2. **Web Fetch**: Use the fetch_web_page tool to read external lists (Eater, Infatuation, blogs, etc.)
3. **AI Suggestions**: Recommend places not in the database (will be marked as AI picks)

## WHEN TO USE WEB FETCH

Use the fetch_web_page tool when users mention:
- External lists: "Eater 38", "Infatuation", "Michelin Guide website", blog posts
- Specific URLs they want to check
- "Check this page for recommendations"

## RESPONSE FORMAT

Return venues in a JSON block with source tags:
```json
{{"venues": [
    {{"name": "Roscioli", "source": "CURATED", "city": "Rome"}},
    {{"name": "Some AI Pick", "source": "AI_PICK", "city": "Rome", "venue_type": "Restaurant", "notes": "Brief description", "website": "https://example.com"}}
]}}
```

- Use "CURATED" for venues from the database (name must match exactly). Always include the city so the correct location is matched.
- Use "AI_PICK" for recommendations not in the database (include city, venue_type, notes)
- For AI_PICK: include "website" with the venue's actual website URL if you know it. Do NOT make up URLs.
- Include collection field if relevant (e.g., "Eater 38 Rome" for web-fetched venues)

## IMPORTANT RULES

- Route queries: Include intermediate stops (SF to Alaska = Oregon, Washington, Vancouver, etc.)
- Up to 30 venues for route queries, 20 for regular searches
- Curated venues should appear first in the list
- Be concise and practical, no flowery language
- Venue cards are displayed in the main panel (not in the chat). Tell the user to check the main panel for full details, especially on mobile where the chat overlays the panel."""

    tools = [
        {
            "name": "fetch_web_page",
            "description": "Fetch a web page to extract venue recommendations.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The URL to fetch. For 'Eater 38 Rome', construct URL like 'https://www.eater.com/maps/best-restaurants-rome'",
                    }
                },
                "required": ["url"],
            },
        }
    ]

    # Build message list from history
    messages = []
    for h in history[-10:]:
        role = h.get("role", "user")
        if role in ("user", "assistant"):
            messages.append({"role": role, "content": h.get("content", "")})

    # Organize venues by region for context
    venues_by_region: dict[str, list] = {}
    for v in venues:
        region = v.get("state") or v.get("country") or "Other"
        venues_by_region.setdefault(region, []).append(v)

    venue_context = "Here are all venues in the database, organized by state/region:\n\n"
    for region in sorted(venues_by_region.keys()):
        region_venues = venues_by_region[region]
        venue_context += f"=== {region} ({len(region_venues)} venues) ===\n"
        for v in region_venues:
            line = f"- {v['name']}"
            if v.get("city"):
                line += f", {v['city']}"
            if v.get("venue_type"):
                line += f" ({v['venue_type']})"
            if v.get("cuisine_type"):
                line += f" [{v['cuisine_type']}]"
            if v.get("michelin_stars"):
                line += f" ⭐{v['michelin_stars']} Michelin"
            if v.get("collection") and v["collection"] not in ("Saved", None):
                line += f" #{v['collection']}"
            if v.get("description"):
                line += f" | {v['description'][:150].replace(chr(10), ' ')}"
            elif v.get("notes"):
                line += f" | {v['notes'][:100].replace(chr(10), ' ')}"
            venue_context += line + "\n"
        venue_context += "\n"

    messages.append({"role": "user", "content": f"{message}\n\n---\n{venue_context}"})

    # Tool-use loop
    max_iterations = 3
    web_fetch_context = None

    for _iteration in range(max_iterations):
        response = llm.call_api(
            system_prompt=system_prompt,
            messages=messages,
            tools=tools,
            return_full_response=True,
        )

        tool_use_block = None
        for block in response.content:
            if block.type == "tool_use":
                tool_use_block = block

        if tool_use_block and tool_use_block.name == "fetch_web_page":
            url = tool_use_block.input.get("url", "")
            print(f"[EXPLORE] Fetching web page: {url}")
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

        break  # No more tool calls

    # Extract final text response
    assistant_response = ""
    for block in response.content:
        if block.type == "text":
            assistant_response = block.text
            break

    # Parse venue JSON from response
    matched_venues = []
    json_match = re.search(r"```json\s*(\{.*?\})\s*```", assistant_response, re.DOTALL)

    if json_match:
        try:
            venue_data = json.loads(json_match.group(1))
            venue_list = venue_data.get("venues", [])

            for item in venue_list:
                if isinstance(item, str):
                    name = item
                    extra: dict = {}
                else:
                    name = item.get("name", "")
                    extra = {k: v for k, v in item.items() if k not in ("name", "source")}

                name_lower = name.lower().strip()
                item_city = extra.get("city", "").lower().strip()

                def _city_matches(v, _city=item_city):
                    if not _city:
                        return True
                    return (
                        _city in (v.get("city") or "").lower()
                        or _city in (v.get("state") or "").lower()
                        or _city in (v.get("country") or "").lower()
                    )

                def _append_curated(v):
                    venue_copy = v.copy()
                    venue_copy["source"] = "CURATED"
                    if web_fetch_context and not venue_copy.get("collection"):
                        venue_copy["collection"] = web_fetch_context.get("title", "")[:50]
                    matched_venues.append(venue_copy)

                matched = False
                exact_any = None
                for v in venues:
                    if v["name"].lower() == name_lower:
                        if _city_matches(v):
                            _append_curated(v)
                            matched = True
                            break
                        elif exact_any is None:
                            exact_any = v

                if not matched:
                    for v in venues:
                        v_name_lower = v["name"].lower()
                        if (
                            len(v_name_lower) >= 5
                            and v_name_lower in name_lower
                            and _city_matches(v)
                        ):
                            _append_curated(v)
                            matched = True
                            break

                if not matched:
                    matched_venues.append(
                        {
                            "name": name,
                            "source": "AI_PICK",
                            "venue_type": extra.get("venue_type", "Restaurant"),
                            "city": extra.get("city", ""),
                            "state": extra.get("state", ""),
                            "country": extra.get("country", ""),
                            "notes": extra.get("notes", ""),
                            "website": extra.get("website", ""),
                            "collection": web_fetch_context.get("title", "")[:50]
                            if web_fetch_context
                            else "",
                        }
                    )

            assistant_response = re.sub(
                r"```json\s*\{.*?\}\s*```", "", assistant_response, flags=re.DOTALL
            ).strip()

        except json.JSONDecodeError:
            pass

    matched_venues.sort(key=lambda v: (0 if v.get("source") == "CURATED" else 1, v.get("name", "")))

    return {"response": assistant_response, "venues": matched_venues}, 200
