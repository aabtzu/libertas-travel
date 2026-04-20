"""Resolve missing website URLs and Google Maps links for trip items."""

from __future__ import annotations

import json
import re
from typing import Any

from agents.common.llm import SONNET, make_llm


def fill_missing_links(itinerary_data: dict[str, Any]) -> dict:
    """Find and fill missing website/maps links for all items.

    Returns {"updated": count, "items": [{"title": ..., "website": ...}, ...]}
    """
    all_items = list(itinerary_data.get("ideas", []))
    for day in itinerary_data.get("days", []):
        all_items.extend(day.get("items", []))

    # Add maps links for items missing them
    maps_added = 0
    for item in all_items:
        if not item.get("google_maps_link"):
            title = item.get("title", "")
            loc = item.get("location", "")
            if title:
                q = f"{title} {loc}".strip().replace(" ", "%20")
                item["google_maps_link"] = f"https://www.google.com/maps/search/?api=1&query={q}"
                maps_added += 1

    # Find items needing real websites
    need_website = [
        i
        for i in all_items
        if not i.get("website") or "google.com/search" in str(i.get("website", ""))
    ]

    websites_added = 0
    if need_website:
        names = "\n".join(f"- {i['title']} in {i.get('location', '')}" for i in need_website)
        try:
            llm = make_llm(model=SONNET, max_tokens=2048)
            response = llm.call_api(
                system_prompt="Return ONLY valid JSON, no markdown fences, no other text.",
                messages=[
                    {
                        "role": "user",
                        "content": (
                            "Find official website URLs for these venues. "
                            "Return JSON mapping name to url. Omit if unknown.\n\n"
                            f"{names}"
                        ),
                    }
                ],
                return_full_response=True,
            )

            text = response.content[0].text.strip()
            text = re.sub(r"^```\w*\n?", "", text)
            text = re.sub(r"\n?```$", "", text)

            websites = json.loads(text)
            for item in need_website:
                url = websites.get(item["title"])
                if url and isinstance(url, str) and url.startswith("http"):
                    item["website"] = url
                    websites_added += 1
                elif (
                    isinstance(item.get("website"), str) and "google.com/search" in item["website"]
                ):
                    item["website"] = ""  # Clear Google search fallback
        except Exception as e:
            print(f"[LINKS] Website lookup failed: {e}")

    return {"maps_added": maps_added, "websites_added": websites_added}
