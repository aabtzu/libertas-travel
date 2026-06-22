"""Trip-level handlers, business logic that route handlers should not own.

Per CLAUDE.md: "Keep LLM calls out of route handlers, they belong in agent
handlers." Routes call into this module; this module owns DB orchestration,
caching policy, and LLM invocation.
"""

from __future__ import annotations

import json
from typing import Any

import database as db


def get_card_icon(user_id: int, link: str) -> tuple[dict, int]:
    """Return the cached trip-card icon, computing + persisting on first call.

    Returns (response_body, status_code), same shape every other handler
    in this codebase uses.
    """
    trip = db.get_trip_by_link(user_id, link)
    if not trip:
        return {"error": "Trip not found"}, 404

    itinerary_data = trip.get("itinerary_data") or {}
    if isinstance(itinerary_data, str):
        try:
            itinerary_data = json.loads(itinerary_data)
        except (json.JSONDecodeError, ValueError):
            itinerary_data = {}

    icon = itinerary_data.get("card_icon")
    if not icon:
        # Lazy import, keeps the route file decoupled from the LLM
        # picker so importing routes doesn't pull the LLM client.
        from agents.itinerary.icon_picker import pick_card_icon

        icon = pick_card_icon(trip.get("title", ""), itinerary_data)
        itinerary_data["card_icon"] = icon
        try:
            db.update_trip_itinerary_data(user_id, link, itinerary_data)
        except Exception as e:
            # Persistence failure is non-fatal, recompute next call.
            print(f"[card-icon] failed to persist for {link}: {e}")

    return {"icon": icon}, 200


def _load_trip_with_itinerary(user_id: int, link: str) -> tuple[dict | None, dict]:
    """Fetch a trip + parsed itinerary_data, or (None, {}) if missing."""
    trip = db.get_trip_by_link(user_id, link)
    if not trip:
        return None, {}
    itinerary_data = trip.get("itinerary_data") or {}
    if isinstance(itinerary_data, str):
        try:
            itinerary_data = json.loads(itinerary_data)
        except (json.JSONDecodeError, ValueError):
            itinerary_data = {}
    return trip, itinerary_data


def generate_writeup_for_trip(user_id: int, link: str) -> tuple[dict, int]:
    """Generate an AI narrative write-up for a trip, using the user's style
    profile + writing samples if present."""
    trip, itinerary_data = _load_trip_with_itinerary(user_id, link)
    if not trip:
        return {"error": "Trip not found"}, 404

    from agents.trips.writeup import generate_writeup

    style_profile = None
    writing_samples = ""
    profile = db.get_user_profile(user_id)
    if profile:
        style_profile = profile.get("style_profile")
        writing_samples = profile.get("writing_samples", "")

    try:
        text = generate_writeup(
            trip.get("title", "Trip"),
            itinerary_data,
            style_profile=style_profile,
            writing_samples=writing_samples,
        )
    except Exception as e:
        return {"error": f"Write-up generation failed: {e}"}, 500

    # Persist so the /w/ public page uses this version without regenerating.
    itinerary_data["writeup"] = text
    try:
        db.update_trip_itinerary_data(user_id, link, itinerary_data)
    except Exception as e:
        print(f"[writeup] failed to persist for {link}: {e}")

    return {"writeup": text, "personalized": bool(style_profile)}, 200


def fill_links_for_trip(user_id: int, link: str) -> tuple[dict, int]:
    """Fill in missing locations / website URLs / Google Maps URLs across
    every item in a trip. Trip title is passed for LLM context so
    ambiguous item names ("Marienplatz", "Hofbräuhaus") resolve to the
    right city instead of the geocoder's silent guess."""
    trip, itinerary_data = _load_trip_with_itinerary(user_id, link)
    if not trip:
        return {"error": "Trip not found"}, 404

    from agents.trips.link_resolver import fill_missing_links

    try:
        result = fill_missing_links(itinerary_data, trip_title=trip.get("title", ""))
        db.update_trip_itinerary_data(user_id, link, itinerary_data)
    except Exception as e:
        return {"error": f"Link resolution failed: {e}"}, 500
    return result, 200


def clone_ideas_between_trips(user_id: int, source_link: str, target_link: str) -> tuple[dict, int]:
    """Clone every idea from a public source trip into a target trip."""
    if not source_link or not target_link:
        return {"error": "source_link and target_link required"}, 400

    owner_id = db.get_trip_owner(source_link)
    if not owner_id:
        return {"error": "Source trip not found"}, 404

    source = db.get_trip_by_link(owner_id, source_link)
    if not source or not source.get("is_public"):
        return {"error": "Source trip not found"}, 404

    source_data = source.get("itinerary_data") or {}
    if isinstance(source_data, str):
        try:
            source_data = json.loads(source_data)
        except (json.JSONDecodeError, ValueError):
            source_data = {}

    source_ideas = source_data.get("ideas", [])
    if not source_ideas:
        return {"error": "No ideas to clone"}, 400

    added = 0
    for idea in source_ideas:
        db.add_item_to_trip(user_id, target_link, idea)
        added += 1
    return {"added": added}, 200


def regenerate_trip_map(user_id: int, link: str) -> tuple[dict, int]:
    """Recompute the map for a trip, used by the "Regen Map" button."""
    trip, itinerary_data = _load_trip_with_itinerary(user_id, link)
    if not trip:
        return {"error": "Trip not found"}, 404
    if not itinerary_data:
        return {"error": "No itinerary data available for this trip"}, 400

    # Drop any cached map data so the mapper recomputes from scratch
    if "map_data" in itinerary_data:
        del itinerary_data["map_data"]
        db.update_trip_itinerary_data(user_id, link, itinerary_data)

    # Lazy imports, geocoding pulls heavy deps, only loaded when needed
    from agents.create.handler import _convert_to_itinerary
    from agents.itinerary.mapper import ItineraryMapper

    itinerary = _convert_to_itinerary(
        {"itinerary_data": itinerary_data, "title": trip.get("title", "Trip")}
    )
    if not itinerary:
        return {"error": "Could not parse itinerary data"}, 400

    db.update_trip_map_status(user_id, link, "processing", None)
    try:
        mapper = ItineraryMapper()
        map_data = mapper.create_map_data(itinerary)
        itinerary_data["map_data"] = map_data
        db.update_trip_itinerary_data(user_id, link, itinerary_data)
        db.update_trip_map_status(user_id, link, "ready", None)
        markers_count = len(map_data.get("markers", []))
        return {"message": f"Map regenerated with {markers_count} locations."}, 200
    except Exception as e:
        db.update_trip_map_status(user_id, link, "error", str(e))
        return {"error": f"Geocoding failed: {e}"}, 500


def extract_user_writing_style(user_id: int, samples: str) -> tuple[dict, int]:
    """Run style extraction on samples and persist alongside the user profile."""
    if not samples or len(samples) < 50:
        return {"error": "Provide at least a few sentences of writing samples"}, 400

    from agents.trips.writeup import extract_style_profile

    try:
        profile_dict: dict[str, Any] = extract_style_profile(samples)
    except Exception as e:
        return {"error": f"Style extraction failed: {e}"}, 500

    existing = db.get_user_profile(user_id) or {}
    existing["style_profile"] = profile_dict
    existing["writing_samples"] = samples
    existing["samples_preview"] = samples[:200]
    db.set_user_profile(user_id, existing)

    return {"profile": profile_dict}, 200
