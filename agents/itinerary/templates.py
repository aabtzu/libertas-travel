"""Trip-specific HTML templates for Libertas Itinerary agent."""

import json
from datetime import datetime
from pathlib import Path

from agents.common.categories import CATEGORY_ICONS  # noqa: F401 – re-exported for callers
from agents.common.templates import get_nav_html
from agents.common.templates import get_static_css as common_get_static_css
from agents.common.templates import get_static_js as common_get_static_js


def format_trip_date(date_str: str | None) -> str:
    """Format a date string as 'Mon YYYY' (e.g., 'Dec 2025')."""
    if not date_str:
        return "Date unknown"
    try:
        # Parse ISO format date (YYYY-MM-DD)
        dt = datetime.strptime(date_str[:10], "%Y-%m-%d")
        return dt.strftime("%b %Y")
    except (ValueError, TypeError):
        return "Date unknown"


def get_trip_start_date(itinerary_data: dict) -> str | None:
    """Extract start date from itinerary_data, checking multiple locations."""
    if not itinerary_data:
        return None
    # Check start_date field first
    if itinerary_data.get("start_date"):
        return itinerary_data["start_date"]
    # Check first day's date
    days = itinerary_data.get("days", [])
    if days and len(days) > 0:
        first_day = days[0]
        if isinstance(first_day, dict) and first_day.get("date"):
            return first_day["date"]
    return None


# CATEGORY_ICONS imported from agents.common.categories — do not redefine here

# Path to itinerary-specific static files and templates
STATIC_DIR = Path(__file__).parent / "static"
TEMPLATES_DIR = Path(__file__).parent / "templates"


def get_static_css(filename: str) -> str:
    """Read a CSS file from itinerary static directory, falling back to common."""
    css_path = STATIC_DIR / "css" / filename
    if css_path.exists():
        return css_path.read_text()
    # Fall back to common static directory
    return common_get_static_css(filename)


def get_static_js(filename: str) -> str:
    """Read a JS file from itinerary static directory, falling back to common."""
    js_path = STATIC_DIR / "js" / filename
    if js_path.exists():
        return js_path.read_text()
    # Fall back to common static directory
    return common_get_static_js(filename)


def get_template(filename: str) -> str:
    """Read an HTML template file from itinerary templates directory."""
    template_path = TEMPLATES_DIR / filename
    if template_path.exists():
        return template_path.read_text()
    return ""


def _get_trip_card_template() -> str:
    """Get the trip card template from external file."""
    return get_template("trip_card.html")


def _get_public_trip_card_template() -> str:
    """Get the public trip card template from external file."""
    return get_template("public_trip_card.html")


# Destination-specific background images (using Unsplash for free images)
DESTINATION_IMAGES = {
    "india": "https://images.unsplash.com/photo-1524492412937-b28074a5d7da?w=600&q=80",  # Taj Mahal
    "rajasthan": "https://images.unsplash.com/photo-1477587458883-47145ed94245?w=600&q=80",  # Jaipur Palace
    "delhi": "https://images.unsplash.com/photo-1587474260584-136574528ed5?w=600&q=80",  # India Gate
    "jaipur": "https://images.unsplash.com/photo-1599661046289-e31897846e41?w=600&q=80",  # Hawa Mahal
    "agra": "https://images.unsplash.com/photo-1564507592333-c60657eea523?w=600&q=80",  # Taj Mahal
    "jaisalmer": "https://images.unsplash.com/photo-1477587458883-47145ed94245?w=600&q=80",  # Desert fort
    "alaska": "https://images.unsplash.com/photo-1531176175280-33e139f1fbb3?w=600&q=80",  # Alaska mountains
    "vietnam": "https://images.unsplash.com/photo-1528127269322-539801943592?w=600&q=80",  # Ha Long Bay
    "cambodia": "https://images.unsplash.com/photo-1539650116574-8efeb43e2750?w=600&q=80",  # Angkor Wat
    "singapore": "https://images.unsplash.com/photo-1525625293386-3f8f99389edd?w=600&q=80",  # Marina Bay
    "japan": "https://images.unsplash.com/photo-1493976040374-85c8e12f0c0e?w=600&q=80",  # Mt Fuji
    "thailand": "https://images.unsplash.com/photo-1528181304800-259b08848526?w=600&q=80",  # Thai temple
    "europe": "https://images.unsplash.com/photo-1499856871958-5b9627545d1a?w=600&q=80",  # Paris
    "france": "https://images.unsplash.com/photo-1502602898657-3e91760cbb34?w=600&q=80",  # Eiffel Tower
    "italy": "https://images.unsplash.com/photo-1523906834658-6e24ef2386f9?w=600&q=80",  # Venice
    "africa": "https://images.unsplash.com/photo-1516426122078-c23e76319801?w=600&q=80",  # Safari
    "hawaii": "https://images.unsplash.com/photo-1507876466758-bc54f384809c?w=600&q=80",  # Beach
    "caribbean": "https://images.unsplash.com/photo-1548574505-5e239809ee19?w=600&q=80",  # Tropical beach
}

# Fallback accent colors for trip cards (when no image matches)
TRIP_COLORS = [
    "#667eea",
    "#f5576c",
    "#1976d2",
    "#43a047",
    "#fa709a",
    "#26a69a",
]


def get_destination_image(title: str):
    """Get a destination-specific image URL based on trip title."""
    title_lower = title.lower()
    for destination, url in DESTINATION_IMAGES.items():
        if destination in title_lower:
            return url
    return None


def get_region_icon(itinerary_data: str | dict | None = None) -> str:
    """Return the trip's card icon.

    The real picker is the LLM in `agents.itinerary.icon_picker`, whose
    result lives in `itinerary_data["card_icon"]` (populated lazily by
    /api/trips/<link>/card-icon and persisted there). This function just
    reads that cached value, falling back to "plane" so the server-side
    initial render isn't blank while the LLM call is in flight.
    """
    if not itinerary_data:
        return "plane"
    if isinstance(itinerary_data, str):
        try:
            itinerary_data = json.loads(itinerary_data)
        except (json.JSONDecodeError, ValueError):
            return "plane"
    return itinerary_data.get("card_icon") or "plane"


def extract_category_counts(itinerary_data: str | dict | None) -> dict:
    """Extract category counts from itinerary_data JSON.

    Returns dict with category names as keys and counts as values.
    """
    if not itinerary_data:
        return {}

    try:
        if isinstance(itinerary_data, str):
            data = json.loads(itinerary_data)
        else:
            data = itinerary_data
    except (json.JSONDecodeError, TypeError):
        return {}

    counts = {}

    # Count items in days
    for day in data.get("days", []):
        for item in day.get("items", []):
            category = item.get("category", "other")
            counts[category] = counts.get(category, 0) + 1

    # Count items in ideas pile
    for item in data.get("ideas", []):
        category = item.get("category", "other")
        counts[category] = counts.get(category, 0) + 1

    return counts


def generate_category_stats_html(
    category_counts: dict, locations: int = 0, activities: int = 0
) -> str:
    """Generate HTML for category stats icons.

    If category_counts is empty, falls back to locations/activities numbers.
    """
    # Category display order
    DISPLAY_ORDER = [
        "attraction",
        "activity",
        "meal",
        "hotel",
        "flight",
        "train",
        "bus",
        "transport",
        "other",
    ]

    # Category tooltips
    TOOLTIPS = {
        "meal": "Meals",
        "hotel": "Hotels",
        "lodging": "Lodging",
        "flight": "Flights",
        "train": "Trains",
        "bus": "Buses",
        "transport": "Transport",
        "activity": "Activities",
        "attraction": "Attractions",
        "other": "Other",
    }

    if category_counts:
        # Use category breakdown
        html_parts = []
        for cat in DISPLAY_ORDER:
            count = category_counts.get(cat, 0)
            if count > 0:
                icon = CATEGORY_ICONS.get(cat, "fa-calendar-day")
                tooltip = TOOLTIPS.get(cat, cat.title())
                html_parts.append(
                    f'<span class="category-stat cat-{cat}" title="{tooltip}">'
                    f'<i class="fas {icon}"></i> {count}</span>'
                )
        return "\n                            ".join(html_parts)
    else:
        # Fallback to locations/activities
        html_parts = []
        if locations > 0:
            html_parts.append(
                f'<span class="category-stat cat-locations" title="Locations">'
                f'<i class="fas fa-map-marker-alt"></i> {locations}</span>'
            )
        if activities > 0:
            html_parts.append(
                f'<span class="category-stat cat-activity" title="Activities">'
                f'<i class="fas fa-star"></i> {activities}</span>'
            )
        return "\n                            ".join(html_parts)


def _extract_map_location(itinerary_data) -> str:
    """Extract a representative location string from itinerary data for the trips map.

    Looks for the most common location across items, preferring ones with state/country.
    """
    if not itinerary_data:
        return ""

    if isinstance(itinerary_data, str):
        import json

        try:
            itinerary_data = json.loads(itinerary_data)
        except (json.JSONDecodeError, ValueError):
            return ""

    locations: list[str] = []
    for day in itinerary_data.get("days", []):
        for item in day.get("items", []):
            loc = item.get("location", "")
            if loc:
                locations.append(loc)
    for item in itinerary_data.get("ideas", []):
        loc = item.get("location", "")
        if loc:
            locations.append(loc)

    if not locations:
        return ""

    # Prefer locations with commas (more specific — "Jackson, NH" > "Jackson")
    with_context = [loc for loc in locations if "," in loc]
    if with_context:
        return with_context[0]
    return locations[0]


def generate_trip_card(
    title: str,
    link: str,
    dates: str,
    days: int,
    locations: int,
    activities: int,
    index: int = 0,
    is_public: bool = False,
    is_draft: bool = False,
    is_archived: bool = False,
    itinerary_data: str | dict | None = None,
    trip_type: str = "itinerary",
) -> str:
    """Generate HTML for a single trip card."""
    # Use accent colors for trip card backgrounds
    color = TRIP_COLORS[index % len(TRIP_COLORS)]
    icon = get_region_icon(itinerary_data)

    # Public visibility settings
    public_badge = (
        '<span class="public-badge"><i class="fas fa-globe"></i></span>' if is_public else ""
    )
    public_class = "active" if is_public else ""
    public_icon = "globe" if is_public else "lock"
    public_title = "Make private" if is_public else "Make public"

    # Draft settings - drafts link to create/edit page
    draft_badge = (
        '<span class="draft-badge"><i class="fas fa-pencil-alt"></i> Draft</span>'
        if is_draft
        else ""
    )
    draft_class = " is-draft" if is_draft else ""
    card_link = f"/create.html?edit={link}" if is_draft else link

    # Archive settings — archived trips are hidden from main grid by default
    archived_badge = (
        '<span class="archived-badge"><i class="fas fa-box-archive"></i> Archived</span>'
        if is_archived
        else ""
    )
    archived_class = " is-archived" if is_archived else ""
    archived_btn_class = "active" if is_archived else ""
    archived_title = "Unarchive trip" if is_archived else "Archive trip"

    # Generate category stats (icons with counts)
    category_counts = extract_category_counts(itinerary_data)
    category_stats = generate_category_stats_html(category_counts, locations, activities)

    # Extract a representative location for the trips map
    map_location = _extract_map_location(itinerary_data)

    return _get_trip_card_template().format(
        link=link,
        card_link=card_link,
        color=color,
        icon=icon,
        title=title,
        dates=dates,
        days=days,
        locations=locations,
        activities=activities,
        category_stats=category_stats,
        public_badge=public_badge,
        public_class=public_class,
        public_icon=public_icon,
        public_title=public_title,
        is_public="true" if is_public else "false",
        draft_badge=draft_badge,
        draft_class=draft_class,
        is_draft="true" if is_draft else "false",
        archived_badge=archived_badge,
        archived_class=archived_class,
        archived_btn_class=archived_btn_class,
        archived_title=archived_title,
        is_archived="true" if is_archived else "false",
        trip_type=trip_type,
        map_location=map_location,
    )


def generate_public_trip_card(
    title: str,
    link: str,
    dates: str,
    days: int,
    locations: int,
    activities: int,
    owner_username: str,
    index: int = 0,
    itinerary_data: str | dict | None = None,
) -> str:
    """Generate HTML for a public trip card (from another user)."""
    color = TRIP_COLORS[index % len(TRIP_COLORS)]
    icon = get_region_icon(itinerary_data)

    # Generate category stats (icons with counts)
    category_counts = extract_category_counts(itinerary_data)
    category_stats = generate_category_stats_html(category_counts, locations, activities)

    return _get_public_trip_card_template().format(
        link=link,
        color=color,
        icon=icon,
        title=title,
        dates=dates,
        days=days,
        locations=locations,
        activities=activities,
        owner_username=owner_username,
        category_stats=category_stats,
    )


def generate_trips_page(trips: list[dict], public_trips: list[dict] = None) -> str:
    """Generate the My Trips page HTML.

    Args:
        trips: List of trip dicts with keys: title, link, dates, days, locations, activities, is_public
        public_trips: List of public trip dicts from other users (with owner_username)
    """
    if public_trips is None:
        public_trips = []

    active_cards_list = []
    archived_cards_list = []
    for i, trip in enumerate(trips):
        try:
            # Ensure all required fields have defaults
            is_public = trip.get("is_public", False)
            is_draft = trip.get("is_draft", False)
            is_archived = trip.get("is_archived", False)
            # Handle SQLite integer (1/0) vs PostgreSQL boolean
            if isinstance(is_public, int):
                is_public = bool(is_public)
            if isinstance(is_draft, int):
                is_draft = bool(is_draft)
            if isinstance(is_archived, int):
                is_archived = bool(is_archived)

            # Get date display - always format from start_date for consistency
            itinerary_data = trip.get("itinerary_data") or {}
            if isinstance(itinerary_data, str):
                try:
                    itinerary_data = json.loads(itinerary_data)
                except (json.JSONDecodeError, ValueError):
                    itinerary_data = {}
            start_date = get_trip_start_date(itinerary_data) or trip.get("start_date")
            formatted_date = format_trip_date(start_date)

            card = generate_trip_card(
                title=trip.get("title", "Untitled Trip"),
                link=trip.get("link", "#"),
                dates=formatted_date,
                days=trip.get("days", 0) or 0,
                locations=trip.get("locations", 0) or 0,
                activities=trip.get("activities", 0) or 0,
                index=i,
                is_public=is_public,
                is_draft=is_draft,
                is_archived=is_archived,
                itinerary_data=trip.get("itinerary_data"),
                trip_type=trip.get("trip_type", "itinerary"),
            )
            if is_archived:
                archived_cards_list.append(card)
            else:
                active_cards_list.append(card)
        except Exception as e:
            print(f"Warning: Could not generate card for trip {trip}: {e}")
            continue
    trip_cards = "\n".join(active_cards_list)
    archived_cards = "\n".join(archived_cards_list)

    # Generate public trips section if there are any
    public_trips_section = ""
    if public_trips:
        public_cards_list = []
        for i, trip in enumerate(public_trips):
            try:
                # Get date display - always format from start_date for consistency
                pub_itinerary_data = trip.get("itinerary_data") or {}
                if isinstance(pub_itinerary_data, str):
                    try:
                        pub_itinerary_data = json.loads(pub_itinerary_data)
                    except (json.JSONDecodeError, ValueError):
                        pub_itinerary_data = {}
                pub_start_date = get_trip_start_date(pub_itinerary_data) or trip.get("start_date")
                pub_formatted_date = format_trip_date(pub_start_date)

                card = generate_public_trip_card(
                    title=trip.get("title", "Untitled Trip"),
                    link=trip.get("link", "#"),
                    dates=pub_formatted_date,
                    days=trip.get("days", 0) or 0,
                    locations=trip.get("locations", 0) or 0,
                    activities=trip.get("activities", 0) or 0,
                    owner_username=trip.get("owner_username", "Unknown"),
                    index=i,
                    itinerary_data=trip.get("itinerary_data"),
                )
                public_cards_list.append(card)
            except Exception as e:
                print(f"Warning: Could not generate public card for trip {trip}: {e}")
                continue
        public_cards = "\n".join(public_cards_list)
        public_trips_section = f"""
        <div class="public-trips-section">
            <div class="trips-header-row">
                <h2><i class="fas fa-globe"></i> Public Trips</h2>
            </div>
            <div class="trips-grid public-trips-grid">
{public_cards}
            </div>
        </div>
"""

    # Archived section + toggle are always rendered (starts collapsed). JS
    # flips visibility based on count and on the user clicking the toggle.
    # Markup lives in templates/archived_{section,toggle}.html.
    archived_section = get_template("archived_section.html").format(archived_cards=archived_cards)
    archived_toggle = get_template("archived_toggle.html").format(
        hidden_attr="" if archived_cards_list else 'hidden=""',
        count=len(archived_cards_list),
    )

    template = get_template("trips.html")
    return template.format(
        nav_html=get_nav_html("trips"),
        trip_cards=trip_cards,
        public_trips_section=public_trips_section,
        archived_section=archived_section,
        archived_toggle=archived_toggle,
    )
