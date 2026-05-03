"""Database package, re-exports all public functions for backward-compatible imports.

All callers use `import database as db` or `from database import X`, so this
__init__.py must expose the full public API that database.py previously provided.
"""

from database.connection import (  # noqa: F401
    DATABASE_URL,
    HAS_POSTGRES,
    USE_POSTGRES,
    get_connection,
    get_db,
    init_db,
)
from database.drafts import (  # noqa: F401
    add_item_to_trip,
    create_draft_trip,
    get_draft_trips,
    publish_draft,
    update_trip_itinerary_data,
)
from database.sharing import (  # noqa: F401
    copy_trip_by_link,
    copy_trip_to_user,
    get_public_trips,
    is_trip_public,
    set_trip_public,
    share_trip_with_all,
)
from database.trips import (  # noqa: F401
    add_trip,
    delete_trip,
    get_pending_geocoding_trips,
    get_trip_by_link,
    get_trip_owner,
    get_user_trips,
    set_trip_archived,
    update_trip,
    update_trip_map_status,
)
from database.users import (  # noqa: F401
    authenticate_user,
    create_user,
    delete_user_by_username,
    email_exists,
    ensure_demo_user,
    get_all_users,
    get_user_by_id,
    get_user_by_username,
    get_user_profile,
    hash_password,
    set_user_profile,
    username_exists,
    verify_password,
)
from database.venues import (  # noqa: F401
    add_venue,
    find_venue_by_name_and_city,
    flexible_venue_search,
    get_all_venues,
    get_venue_by_id,
    get_venue_count,
    get_venue_stats,
    import_venues_from_csv,
    search_venues,
    update_venue_coordinates,
)
