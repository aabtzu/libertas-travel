"""Shared helper for saving a place to the curated venue database."""

from __future__ import annotations

import json
import os

import database as db

_HAIKU_MODEL = "claude-haiku-4-5-20251001"

# Item categories that represent real places worth capturing
_PLACE_CATEGORIES = {
    "restaurant",
    "hotel",
    "activity",
    "bar",
    "cafe",
    "attraction",
    "museum",
    "accommodation",
    "food",
    "drink",
    "entertainment",
    "shopping",
    "spa",
    "beach",
}

# Categories that are logistics, not places
_SKIP_CATEGORIES = {
    "flight",
    "transport",
    "train",
    "bus",
    "ferry",
    "car",
    "transit",
    "transfer",
    "drive",
}


def is_place_category(category: str) -> bool:
    """Return True if the category represents a real place worth capturing."""
    cat = (category or "").lower().strip()
    if cat in _SKIP_CATEGORIES:
        return False
    # If it's explicitly a place category, yes. Otherwise default to yes
    # (unknown categories are more likely places than logistics).
    return cat not in _SKIP_CATEGORIES


def _enrich_with_haiku(name: str, city: str, notes: str, venue_type: str) -> dict:
    """Use Haiku to fill missing venue fields. Returns partial dict of enriched fields."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return {}
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)
        notes_str = notes or "(none)"
        city_str = city or "unknown city"
        prompt = (
            f'Venue: "{name}" in {city_str}.\n'
            f"Notes: {notes_str}.\n"
            "Return a JSON object with these fields (best guess, no explanations):\n"
            '{"venue_type": "Restaurant|Hotel|Bar|Cafe|Museum|Attraction|...", '
            '"cuisine_type": "Italian|Japanese|... or empty if not food", '
            '"description": "one sentence about the venue"}\n'
            "Reply with only the JSON object."
        )
        msg = client.messages.create(
            model=_HAIKU_MODEL,
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = msg.content[0].text.strip()
        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw.strip())
    except Exception as e:
        print(f"[venue_capture] Haiku enrichment failed for {name!r}: {e}", flush=True)
        return {}


def save_venue_to_curated(
    name: str,
    city: str,
    notes: str = "",
    venue_type: str = "",
    user_id: int | None = None,
) -> dict:
    """Save a place to the curated venue database.

    Returns a dict with keys: saved (bool), skipped (bool), venue_id (int or None), reason (str).
    """
    name = (name or "").strip()
    city = (city or "").strip()
    if not name:
        return {"saved": False, "skipped": True, "venue_id": None, "reason": "no name"}

    # Dedup check
    existing = db.find_venue_by_name_and_city(name, city)
    if existing:
        return {
            "saved": False,
            "skipped": True,
            "venue_id": existing.get("id"),
            "reason": "already exists",
        }

    # Enrich thin records
    enriched = _enrich_with_haiku(name, city, notes, venue_type)
    venue_data = {
        "name": name,
        "city": city,
        "notes": notes,
        "venue_type": enriched.get("venue_type") or venue_type or "",
        "cuisine_type": enriched.get("cuisine_type") or "",
        "description": enriched.get("description") or "",
        "source": "trip",
    }

    venue_id = db.add_venue(venue_data, created_by=user_id)
    if venue_id:
        # Invalidate explore handler cache so new venue appears immediately
        try:
            import agents.explore.handler as _eh

            _eh._venues_cache = None
        except Exception:
            pass
        print(f"[venue_capture] saved {name!r} ({city}) id={venue_id}", flush=True)
        return {"saved": True, "skipped": False, "venue_id": venue_id, "reason": "added"}

    return {"saved": False, "skipped": False, "venue_id": None, "reason": "db error"}
