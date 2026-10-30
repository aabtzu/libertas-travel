"""Generate a narrative write-up from trip ideas and tips.

Uses StyleWriterBot from fiat-lux-agents for style-aware text generation.
Default style: NYT 36 Hours. Personalized style via user profile.
"""

from __future__ import annotations

from typing import Any

from fiat_lux_agents import StyleWriterBot

from agents.common.llm import SONNET

# Travel-specific instructions appended to all write-ups
_TRAVEL_INSTRUCTIONS = """Write a recommendation narrative for the places provided.
Group by area/city. Do NOT use a day-by-day format unless dates are present.
Include website links as markdown: [venue name](url).
Skip Google search fallback links, only include real URLs.
Use the notes as context to write your own prose - do not copy them verbatim.
IMPORTANT: Only write about the exact places listed. Do not add, invent, or mention any hotels, restaurants, activities, flights, or destinations not explicitly in the list.
Write in markdown."""


def _build_items_text(all_items: list[dict]) -> str:
    """Format trip items as structured text for the LLM."""
    lines = []
    for item in all_items:
        cat = item.get("category", "other")
        loc = item.get("location", "")
        notes = item.get("notes", "")
        website = item.get("website", "")
        maps_link = item.get("google_maps_link", "")
        line = f"- {item.get('title', 'Untitled')} ({cat})"
        if loc:
            line += f", {loc}"
        if website and "google.com/search" not in website:
            line += f"\n  Website: {website}"
        if maps_link:
            line += f"\n  Map: {maps_link}"
        if notes:
            line += f"\n  Notes: {notes}"
        lines.append(line)
    return "\n".join(lines)


def generate_writeup(
    title: str,
    itinerary_data: dict[str, Any],
    style_profile: dict | None = None,
    writing_samples: str = "",
    directive: str = "",
) -> str:
    """Turn structured trip ideas + tips into a readable narrative.

    Args:
        title: Trip title
        itinerary_data: Trip data with ideas, days, tips
        style_profile: Optional user writing style profile for personalization
        writing_samples: Optional raw writing samples for style extraction
        directive: Optional filter like 'Lima only' or 'food only'

    Returns the write-up text, or raises on error.
    """
    # Collect all items, skipping logistical categories that don't belong in a narrative.
    _SKIP = {"flight", "transport", "home"}
    all_items = [i for i in itinerary_data.get("ideas", []) if i.get("category") not in _SKIP]
    for day in itinerary_data.get("days", []):
        for item in day.get("items", []):
            if item.get("category") not in _SKIP:
                all_items.append(item)

    tips = itinerary_data.get("tips", [])

    if not all_items and not tips:
        return "No recommendations to write about yet."

    # Filter by directive if provided (same LLM filter as personalized rec)
    if directive:
        from agents.trips.personalized_rec_handler import _filter_items_with_llm

        all_items = _filter_items_with_llm(all_items, directive)
        if not all_items:
            return "No items matched the directive."

    # Strip booking details before passing to the narrative LLM
    from agents.pages.recommendation_view import _batch_clean_notes

    cleaned = _batch_clean_notes(all_items)
    if cleaned:
        all_items = [
            {**item, "notes": cleaned.get(item.get("title", ""), item.get("notes", ""))}
            for item in all_items
        ]

    items_text = _build_items_text(all_items)

    # When a directive narrows the scope, tips are global and would introduce
    # out-of-scope content (flights, other cities). Drop them.
    tips_text = ""
    if tips and not directive:
        tips_text = "\nGeneral tips:\n" + "\n".join(f"- {t}" for t in tips)

    data_text = f"Trip: {title}\n\nPlaces:\n{items_text}\n{tips_text}"

    effective_profile = dict(style_profile) if style_profile else {}
    user_rules = effective_profile.get("rules", "")
    no_signoff = (
        "Do not add a final closing paragraph after all venue sections. "
        "No document-level sign-offs like 'anything you want more detail on, just ask' "
        "or 'let me know if you have questions' at the very end. "
        "Per-section follow-up invitations that are part of the writing style are fine. "
        "End after the last venue or section."
    )
    effective_profile["rules"] = (user_rules + "\n" + no_signoff) if user_rules else no_signoff

    writer = StyleWriterBot(model=SONNET, max_tokens=2048)
    return writer.generate(
        data=data_text,
        context=_TRAVEL_INSTRUCTIONS,
        style_profile=effective_profile,
    )


def extract_style_profile(writing_samples: str) -> dict:
    """Analyze writing samples and extract a style profile.

    Delegates to StyleWriterBot.extract_style().
    """
    writer = StyleWriterBot(model=SONNET, max_tokens=1024)
    return writer.extract_style(writing_samples)
