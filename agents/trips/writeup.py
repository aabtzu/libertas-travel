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
Skip Google search fallback links, only include real URLs.
Write in markdown."""


def _build_items_text(all_items: list[dict]) -> str:
    """Format trip items as structured text for the LLM.

    Items with notes are marked with VERBATIM_NOTES so the LLM knows to
    copy them exactly. This is a last-resort signal; the real guarantee is
    that we do a post-pass substitution in generate_writeup().
    """
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
            line += f"\n  VERBATIM_NOTES (copy this text exactly, word for word): {notes}"
        lines.append(line)
    return "\n".join(lines)


def _enforce_verbatim_notes(text: str, all_items: list[dict]) -> str:
    """Post-processing pass: find each venue title in the output and replace
    whatever the LLM wrote as the description with the original notes.

    This is the only reliable way to guarantee verbatim notes - prompting
    alone is not sufficient when the style template actively rewrites content.
    """
    import re

    for item in all_items:
        notes = (item.get("notes") or "").strip()
        title = (item.get("title") or "").strip()
        if not notes or not title:
            continue

        # Find the venue link or heading in the output. Matches:
        # [title](url), **title**, or bare title followed by a dash/newline.
        title_pattern = re.compile(
            r"(\[" + re.escape(title) + r"\]\([^)]*\)|"
            r"\*\*" + re.escape(title) + r"\*\*|"
            r"(?<!\w)" + re.escape(title) + r"(?!\w))",
            re.IGNORECASE,
        )

        match = title_pattern.search(text)
        if not match:
            continue

        # The bare-title alternation can match inside **title** stopping before
        # the closing **. Skip past any trailing ** so it doesn't get swallowed
        # into the replacement range.
        end_pos = match.end()
        if text[end_pos : end_pos + 2] == "**":
            end_pos += 2

        # Find where the description starts (after the title and any separator)
        after_title = text[end_pos:]
        # Skip separator characters (em dash, hyphen, space, newline)
        sep_match = re.match(r"[\s\-—–]*", after_title)
        desc_start = end_pos + (sep_match.end() if sep_match else 0)

        # Find where the description ends (next blank line or next venue entry)
        rest = text[desc_start:]
        end_match = re.search(r"\n\n|\n\[|\n\*\*", rest)
        desc_end = desc_start + (end_match.start() if end_match else len(rest))

        # Replace only the description portion with the original notes
        text = text[:desc_start] + notes + text[desc_end:]

    return text


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

    data_text = f"Trip: {title}\n\nPlaces:\n{items_text}\n{tips_text}"

    effective_profile = dict(style_profile) if style_profile else {}
    user_rules = effective_profile.get("rules", "")
    effective_profile["rules"] = (
        user_rules + "\nDo not add any vibe summary or editorial sign-off after the description."
        if user_rules
        else "Do not add any vibe summary or editorial sign-off after the description."
    )

    writer = StyleWriterBot(model=SONNET, max_tokens=2048)
    output = writer.generate(
        data=data_text,
        context=_TRAVEL_INSTRUCTIONS,
        style_profile=effective_profile,
        instructions="Use VERBATIM_NOTES text word for word. Do not paraphrase.",
    )

    # Guarantee: replace LLM-generated descriptions with original notes.
    # Prompting cannot guarantee this - post-processing can.
    return _enforce_verbatim_notes(output, all_items)


def extract_style_profile(writing_samples: str) -> dict:
    """Analyze writing samples and extract a style profile.

    Delegates to StyleWriterBot.extract_style().
    """
    writer = StyleWriterBot(model=SONNET, max_tokens=1024)
    return writer.extract_style(writing_samples)
