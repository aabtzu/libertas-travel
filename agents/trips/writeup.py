"""Generate a narrative write-up from trip ideas and tips.

Uses StyleWriterBot from fiat-lux-agents for style-aware text generation.
Default style: NYT 36 Hours. Personalized style via user profile.
"""

from __future__ import annotations

from typing import Any

from fiat_lux_agents import StyleWriterBot

from agents.common.llm import SONNET

# Travel-specific instructions appended to all write-ups
_TRAVEL_INSTRUCTIONS = """Write a recommendation for the places provided.
Group by area/city. Do NOT use a day-by-day format unless dates are present.
Include website links as markdown: [venue name](url).
Skip Google search fallback links — only include real URLs.
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
            line += f" — {loc}"
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
) -> str:
    """Turn structured trip ideas + tips into a readable narrative.

    Args:
        title: Trip title
        itinerary_data: Trip data with ideas, days, tips
        style_profile: Optional user writing style profile for personalization

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

    items_text = _build_items_text(all_items)

    tips_text = ""
    if tips:
        tips_text = "\nGeneral tips:\n" + "\n".join(f"- {t}" for t in tips)

    # Build data string for the writer
    data_text = f"Trip: {title}\n\nPlaces:\n{items_text}\n{tips_text}"

    # Pull user rules to reinforce at the end of the prompt (recency bias)
    rules_reminder = ""
    if style_profile and style_profile.get("rules"):
        rules_reminder = f"\n\nREMINDER — follow these rules strictly:\n{style_profile['rules']}"

    writer = StyleWriterBot(model=SONNET, max_tokens=2048)
    return writer.generate(
        data=data_text + rules_reminder,
        context=_TRAVEL_INSTRUCTIONS,
        style_profile=style_profile,
        style_template="nyt_36_hours",
        instructions="Include the recommender's personal notes — those are the good stuff.",
        # Don't pass writing samples — they can conflict with rules
        # (e.g. casual emails naturally have wrap-up phrases the rules prohibit).
        # The style profile + rules are more controllable.
    )


def extract_style_profile(writing_samples: str) -> dict:
    """Analyze writing samples and extract a style profile.

    Delegates to StyleWriterBot.extract_style().
    """
    writer = StyleWriterBot(model=SONNET, max_tokens=1024)
    return writer.extract_style(writing_samples)
