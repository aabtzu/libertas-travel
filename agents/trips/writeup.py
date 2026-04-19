"""Generate a narrative write-up from trip ideas and tips using Claude."""

from __future__ import annotations

from typing import Any

from agents.common.llm import SONNET, make_llm


def generate_writeup(title: str, itinerary_data: dict[str, Any]) -> str:
    """Turn structured trip ideas + tips into a readable narrative.

    Returns the write-up text, or raises on error.
    """
    # Collect all items
    all_items = list(itinerary_data.get("ideas", []))
    for day in itinerary_data.get("days", []):
        for item in day.get("items", []):
            all_items.append(item)

    tips = itinerary_data.get("tips", [])

    if not all_items and not tips:
        return "No recommendations to write about yet."

    # Build structured input for the LLM
    items_text = ""
    for item in all_items:
        cat = item.get("category", "other")
        loc = item.get("location", "")
        notes = item.get("notes", "")
        line = f"- {item.get('title', 'Untitled')} ({cat})"
        if loc:
            line += f" — {loc}"
        if notes:
            line += f"\n  Notes: {notes}"
        items_text += line + "\n"

    tips_text = ""
    if tips:
        tips_text = "\nGeneral tips:\n"
        for tip in tips:
            tips_text += f"- {tip}\n"

    prompt = f"""Write a concise, practical recommendation for someone visiting the places below.
Group by area/city. Be direct and opinionated — say what's worth doing and why.
Keep it casual and personal, like an email to a friend. No filler sentences.
Include the specific notes/tips the recommender provided — those are the good stuff.

Trip: {title}

Places:
{items_text}
{tips_text}

Write the recommendation now. No greeting or sign-off — just the content."""

    llm = make_llm(model=SONNET, max_tokens=2048)
    response = llm.ask(prompt)
    return response
