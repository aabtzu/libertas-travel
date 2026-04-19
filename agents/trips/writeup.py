"""Generate a narrative write-up from trip ideas and tips using Claude.

Default style modeled on NYT 36 Hours — evocative, opinionated, practical.
Style reference: data/style_references/nyt_36_hours_hoi_an.pdf
"""

from __future__ import annotations

from typing import Any

from agents.common.llm import SONNET, make_llm

# Default system prompt — NYT 36 Hours style
_SYSTEM_PROMPT = """You are a travel writer in the style of the New York Times \
"36 Hours" column. Your writing is:

- Evocative but concise — paint a scene in one or two sentences, then move on
- Opinionated — say what's worth doing and what to skip
- Practical — include specific names, neighborhoods, times of day
- Narrative — weave venues into a story, don't just list them
- Atmospheric — capture what makes a place feel different

Structure: Start with a short evocative intro about the destination (2-3 sentences). \
Then group recommendations by area or theme. Each venue gets a sentence or two — \
what it is, why it matters, and any insider tip the recommender provided.

Do NOT use a day-by-day format unless the trip has specific dates and timing. \
For recommendations without dates, group by area and let the reader decide the order.

Include website links as markdown: [venue name](url). \
Skip Google search fallback links — only include real URLs."""


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
) -> str:
    """Turn structured trip ideas + tips into a readable narrative.

    Args:
        title: Trip title
        itinerary_data: Trip data with ideas, days, tips
        style_profile: Optional user writing style profile for personalization.
            If provided, the write-up is generated in the user's voice.

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

    # Build the user prompt
    prompt = f"""Write a recommendation for someone visiting the places below.

Trip: {title}

Places:
{items_text}
{tips_text}

Write in markdown."""

    # Choose system prompt — personalized style or default NYT 36 Hours
    system = _SYSTEM_PROMPT
    if style_profile:
        system = _build_personalized_system_prompt(style_profile)

    llm = make_llm(model=SONNET, max_tokens=2048)
    response = llm.call_api(
        system_prompt=system,
        messages=[{"role": "user", "content": prompt}],
        return_full_response=True,
    )
    return response.content[0].text.strip()


def extract_style_profile(writing_samples: str) -> dict:
    """Analyze writing samples and extract a style profile.

    Returns a dict with tone, sentence_length, vocabulary, emphasis, perspective.
    """
    llm = make_llm(model=SONNET, max_tokens=1024)
    response = llm.call_api(
        system_prompt="You are a writing style analyst. Return ONLY valid JSON.",
        messages=[
            {
                "role": "user",
                "content": f"""Analyze these writing samples and extract the author's style.

Return a JSON object with:
- "tone": overall tone (e.g. "casual, lowercase, direct" or "formal, polished")
- "sentence_style": sentence patterns (e.g. "short and punchy" or "long, flowing")
- "vocabulary": list of distinctive words/abbreviations they use (e.g. ["w/", "def", "tbh"])
- "emphasis": what they focus on (e.g. "practical tips, personal experience")
- "perspective": point of view (e.g. "first person plural - we/us")
- "quirks": any other distinctive patterns (e.g. "ends with casual sign-off", "uses dashes heavily")

Writing samples:
{writing_samples}""",
            }
        ],
        return_full_response=True,
    )

    import json
    import re

    text = response.content[0].text.strip()
    text = re.sub(r"^```\w*\n?", "", text)
    text = re.sub(r"\n?```$", "", text)
    return json.loads(text)


def _build_personalized_system_prompt(style_profile: dict) -> str:
    """Build a system prompt that writes in the user's personal style."""
    tone = style_profile.get("tone", "casual")
    sentence_style = style_profile.get("sentence_style", "concise")
    vocab = style_profile.get("vocabulary", [])
    emphasis = style_profile.get("emphasis", "practical tips")
    perspective = style_profile.get("perspective", "first person")
    quirks = style_profile.get("quirks", "")

    vocab_str = ", ".join(f'"{v}"' for v in vocab[:10]) if vocab else "standard"

    return f"""You are a travel writer ghostwriting in someone's personal voice.

Their style:
- Tone: {tone}
- Sentences: {sentence_style}
- Vocabulary/shortcuts: {vocab_str}
- They emphasize: {emphasis}
- Perspective: {perspective}
- Other patterns: {quirks}

Write exactly as they would — match their tone, sentence length, word choices, \
and what they focus on. Do NOT sound like a generic AI or a formal travel guide. \
Sound like them writing an email to a friend about where to go.

Include website links as markdown: [venue name](url). \
Skip Google search fallback links — only include real URLs.

Do NOT use a day-by-day format unless the trip has specific dates and timing."""
