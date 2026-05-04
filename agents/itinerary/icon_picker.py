"""LLM-driven trip-card icon picker.

Uses Haiku (speed/cost) with a curated list of FontAwesome 6 free icons
so the model can't hallucinate non-existent icon names.

Result is cached per-trip in `itinerary_data["card_icon"]`, we only call
the LLM once per trip, ever (until the trip is renamed and the cache is
manually invalidated). `templates.get_region_icon` reads the cached value
for the synchronous server-side render; the trips-page JS calls
/api/trips/<link>/card-icon to compute and persist it on first view.
"""

from __future__ import annotations

from typing import Any

from agents.common.llm import HAIKU, make_llm

# Curated FA6 free solid icons appropriate for trip card art. Keep this list
# tight, adding rare icons increases the chance the model picks one we
# can't render. Validated against fontawesome.com/v6/search?o=r&m=free.
ICON_OPTIONS: list[str] = [
    # transport
    "plane",
    "train",
    "ship",
    "car",
    "bus",
    "road",
    "route",
    # nature / outdoors
    "mountain",
    "mountain-sun",
    "tree-city",
    "umbrella-beach",
    "sailboat",
    "anchor",
    "leaf",
    "snowflake",
    "sun",
    # cityscape / landmarks
    "city",
    "landmark",
    "monument",
    "bridge",
    "archway",
    "tower-observation",
    # cultural / religious
    "torii-gate",
    "mosque",
    "church",
    "place-of-worship",
    "om",
    # globes (last-resort regional)
    "globe-americas",
    "globe-europe",
    "globe-asia",
    "globe-africa",
    # activities
    "person-hiking",
    "person-skiing",
    "person-snowboarding",
    "person-swimming",
    # food / leisure
    "utensils",
    "wine-glass",
    "mug-hot",
    "spa",
    # exploration
    "camera",
    "binoculars",
    "compass",
    "map",
]
_ICON_SET = frozenset(ICON_OPTIONS)
FALLBACK_ICON = "plane"

_SYSTEM_PROMPT = f"""You pick a FontAwesome icon for a travel trip card.

Choose ONE icon name from this exact list, picking outside the list is
forbidden:
{", ".join(ICON_OPTIONS)}

Hints, use specific icons over generic ones:
- San Francisco / NYC -> bridge
- Paris -> archway or tower-observation
- Generic European city or museum-heavy trip -> landmark
- Beach destinations (Hawaii, Caribbean, Greek islands) -> umbrella-beach
- Mountain trips -> mountain or mountain-sun
- Road trips with multiple stops -> road or route
- Buddhist / Shinto / Japan -> torii-gate
- Hindu / India -> om
- Islamic destinations -> mosque
- Christian heritage -> church
- Activity-focused trips -> person-hiking / person-skiing / person-swimming etc.
- Food / wine trips -> utensils or wine-glass
- Photography / wildlife -> camera or binoculars

Reply with ONLY the icon name, lowercase, no quotes, no `fa-` prefix, no
explanation. Example reply: bridge"""


def _summarize_trip(title: str, itinerary_data: dict[str, Any] | None) -> str:
    """Build the user-message payload for the LLM, title + destinations + mix."""
    items: list[dict] = []
    if itinerary_data:
        for day in itinerary_data.get("days", []) or []:
            for item in day.get("items", []) or []:
                items.append(item)
        for item in itinerary_data.get("ideas", []) or []:
            items.append(item)

    # Distinct top-level location names, keep the prompt small
    locations: list[str] = []
    seen: set[str] = set()
    for it in items:
        loc = (it.get("location") or "").split(",")[0].strip()
        if loc and loc.lower() not in seen:
            seen.add(loc.lower())
            locations.append(loc)
        if len(locations) >= 8:
            break

    # Category histogram
    cat_counts: dict[str, int] = {}
    for it in items:
        c = (it.get("category") or "other").lower()
        cat_counts[c] = cat_counts.get(c, 0) + 1
    top_cats = sorted(cat_counts.items(), key=lambda x: -x[1])[:5]
    cat_summary = ", ".join(f"{k}:{v}" for k, v in top_cats) or "n/a"

    return (
        f"Trip:\n"
        f"- Title: {title}\n"
        f"- Destinations: {', '.join(locations) if locations else 'n/a'}\n"
        f"- Activity mix: {cat_summary}\n\n"
        f"Pick the best icon."
    )


def pick_card_icon(title: str, itinerary_data: dict[str, Any] | None = None) -> str:
    """Return a FontAwesome icon name (no `fa-` prefix) for the trip card.

    Falls back to `FALLBACK_ICON` if the LLM is unavailable or returns
    something not in the curated list.
    """
    if not title:
        return FALLBACK_ICON

    user_msg = _summarize_trip(title, itinerary_data)

    try:
        llm = make_llm(model=HAIKU, max_tokens=16)
        response = llm.call_api(
            system_prompt=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )
        # call_api returns text by default
        text = (response or "").strip().lower()
        # Strip a leading `fa-` if the model added it despite instructions
        if text.startswith("fa-"):
            text = text[3:]
        # Strip surrounding quotes/punctuation
        text = text.strip("'\".,!:;`")
        if text in _ICON_SET:
            return text
        # Soft retry: model sometimes returns a phrase, pick the first valid token
        for tok in text.replace(",", " ").split():
            tok = tok.strip("'\".,!:;`")
            if tok.startswith("fa-"):
                tok = tok[3:]
            if tok in _ICON_SET:
                return tok
    except Exception as e:
        print(f"[icon-picker] LLM call failed: {e}")

    return FALLBACK_ICON
