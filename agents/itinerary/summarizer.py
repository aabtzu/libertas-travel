"""Generate text summaries of itineraries using Claude."""

import os
from typing import Optional

import anthropic

from .models import Itinerary


SUMMARY_PROMPT = """You are a helpful travel assistant. Create a clear, well-organized text summary of this travel itinerary.

The summary should include:
1. A brief overview (destination, dates, duration, travelers)
2. Day-by-day breakdown of activities
3. Key logistics (flights, hotels, important times)
4. Any notable highlights or recommendations

Format the summary in a readable way with clear sections and bullet points where appropriate.

Itinerary data:
"""


class ItinerarySummarizer:
    """Generate text summaries of itineraries."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Anthropic API key required. Set ANTHROPIC_API_KEY env var or pass api_key."
            )
        self.client = anthropic.Anthropic(api_key=self.api_key)

    def summarize(self, itinerary: Itinerary) -> str:
        """Generate a text summary of the itinerary."""
        itinerary_json = self._format_itinerary_for_prompt(itinerary)

        message = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2048,
            messages=[
                {
                    "role": "user",
                    "content": SUMMARY_PROMPT + itinerary_json,
                }
            ],
        )

        return message.content[0].text

    def _format_itinerary_for_prompt(self, itinerary: Itinerary) -> str:
        """Format itinerary data for the summary prompt."""
        lines = []

        lines.append(f"Title: {itinerary.title}")

        if itinerary.start_date:
            lines.append(f"Start Date: {itinerary.start_date}")
        if itinerary.end_date:
            lines.append(f"End Date: {itinerary.end_date}")
        if itinerary.duration_days:
            lines.append(f"Duration: {itinerary.duration_days} days")
        if itinerary.travelers:
            lines.append(f"Travelers: {', '.join(itinerary.travelers)}")

        lines.append("\nItems:")

        # Group by date if available
        items_by_date = itinerary.items_by_date()

        if items_by_date:
            for item_date, items in items_by_date.items():
                lines.append(f"\n--- {item_date.strftime('%A, %B %d, %Y')} ---")
                for item in items:
                    lines.append(self._format_item(item))
        else:
            # Items without dates - group by day number or list sequentially
            for item in itinerary.items:
                if item.day_number:
                    lines.append(f"\n--- Day {item.day_number} ---")
                lines.append(self._format_item(item))

        return "\n".join(lines)

    def _format_item(self, item) -> str:
        """Format a single itinerary item."""
        parts = [f"  - {item.title}"]

        if item.location.name:
            parts.append(f"    Location: {item.location.name}")
        if item.start_time:
            time_str = item.start_time.strftime("%I:%M %p")
            if item.end_time:
                time_str += f" - {item.end_time.strftime('%I:%M %p')}"
            parts.append(f"    Time: {time_str}")
        if item.category:
            parts.append(f"    Type: {item.category}")
        if item.description:
            parts.append(f"    Description: {item.description}")
        if item.confirmation_number:
            parts.append(f"    Confirmation: {item.confirmation_number}")
        if item.notes:
            parts.append(f"    Notes: {item.notes}")

        return "\n".join(parts)

    def quick_summary(self, itinerary: Itinerary) -> str:
        """Generate a quick, local summary without using the API."""
        lines = []

        # Header
        lines.append(f"# {itinerary.title}")
        lines.append("")

        # Overview
        if itinerary.start_date and itinerary.end_date:
            lines.append(
                f"**Dates:** {itinerary.start_date.strftime('%b %d')} - "
                f"{itinerary.end_date.strftime('%b %d, %Y')}"
            )
        if itinerary.duration_days:
            lines.append(f"**Duration:** {itinerary.duration_days} days")
        if itinerary.travelers:
            lines.append(f"**Travelers:** {', '.join(itinerary.travelers)}")

        lines.append("")
        lines.append("## Itinerary")

        # Group items
        items_by_date = itinerary.items_by_date()

        if items_by_date:
            for item_date, items in items_by_date.items():
                lines.append(f"\n### {item_date.strftime('%A, %B %d')}")
                for item in items:
                    time_str = ""
                    if item.start_time:
                        time_str = f" ({item.start_time.strftime('%I:%M %p')})"
                    lines.append(f"- **{item.title}**{time_str}")
                    lines.append(f"  - {item.location.name}")
        else:
            current_day = None
            for item in itinerary.items:
                if item.day_number and item.day_number != current_day:
                    current_day = item.day_number
                    lines.append(f"\n### Day {current_day}")
                time_str = ""
                if item.start_time:
                    time_str = f" ({item.start_time.strftime('%I:%M %p')})"
                lines.append(f"- **{item.title}**{time_str}")
                lines.append(f"  - {item.location.name}")

        # Locations summary
        locations = itinerary.locations
        if locations:
            lines.append("\n## Key Locations")
            for loc in locations:
                loc_type = f" ({loc.location_type})" if loc.location_type else ""
                lines.append(f"- {loc.name}{loc_type}")

        return "\n".join(lines)
