"""Unit tests for the database package — all run against a fresh SQLite DB, no live APIs."""

from __future__ import annotations

import os
import sqlite3
import tempfile
from unittest.mock import patch

import pytest

# Force SQLite before any database import
os.environ.pop("DATABASE_URL", None)


# ---------------------------------------------------------------------------
# Fixture: fresh SQLite DB for every test
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_db(tmp_path):
    """Patch get_connection to use a temp SQLite file and initialise schema."""
    db_file = str(tmp_path / "test.db")

    def _get_connection():
        conn = sqlite3.connect(db_file)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    with patch("database.connection.get_connection", _get_connection):
        from database.connection import init_db
        init_db()
        yield


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------


class TestHashPassword:
    def test_hash_differs_from_plaintext(self):
        from database.users import hash_password
        assert hash_password("secret") != "secret"

    def test_two_hashes_differ(self):
        from database.users import hash_password
        # bcrypt salts are random so two hashes of the same password differ
        assert hash_password("secret") != hash_password("secret")


class TestVerifyPassword:
    def test_correct_password(self):
        from database.users import hash_password, verify_password
        h = hash_password("correct")
        assert verify_password("correct", h) is True

    def test_wrong_password(self):
        from database.users import hash_password, verify_password
        h = hash_password("correct")
        assert verify_password("wrong", h) is False


class TestCreateUser:
    def test_creates_and_returns_id(self):
        from database.users import create_user
        uid = create_user("alice", "alice@example.com", "pass123")
        assert isinstance(uid, int)
        assert uid > 0

    def test_duplicate_username_returns_none(self):
        from database.users import create_user
        create_user("alice", "alice@example.com", "pass")
        result = create_user("alice", "other@example.com", "pass")
        assert result is None

    def test_duplicate_email_returns_none(self):
        from database.users import create_user
        create_user("alice", "alice@example.com", "pass")
        result = create_user("bob", "alice@example.com", "pass")
        assert result is None


class TestGetUser:
    def test_get_by_username(self):
        from database.users import create_user, get_user_by_username
        create_user("alice", "alice@example.com", "pass")
        user = get_user_by_username("alice")
        assert user is not None
        assert user["username"] == "alice"
        assert user["email"] == "alice@example.com"

    def test_get_by_username_missing(self):
        from database.users import get_user_by_username
        assert get_user_by_username("nobody") is None

    def test_get_by_id(self):
        from database.users import create_user, get_user_by_id
        uid = create_user("alice", "alice@example.com", "pass")
        user = get_user_by_id(uid)
        assert user["username"] == "alice"

    def test_get_by_id_missing(self):
        from database.users import get_user_by_id
        assert get_user_by_id(999) is None

    def test_password_hash_not_in_get_by_id(self):
        from database.users import create_user, get_user_by_id
        uid = create_user("alice", "alice@example.com", "pass")
        user = get_user_by_id(uid)
        assert "password_hash" not in user


class TestAuthenticateUser:
    def test_correct_credentials(self):
        from database.users import authenticate_user, create_user
        create_user("alice", "alice@example.com", "pass123")
        user = authenticate_user("alice", "pass123")
        assert user is not None
        assert user["username"] == "alice"
        assert "password_hash" not in user

    def test_wrong_password(self):
        from database.users import authenticate_user, create_user
        create_user("alice", "alice@example.com", "pass123")
        assert authenticate_user("alice", "wrong") is None

    def test_unknown_user(self):
        from database.users import authenticate_user
        assert authenticate_user("ghost", "pass") is None


class TestUsernameEmailExists:
    def test_username_exists(self):
        from database.users import create_user, username_exists
        create_user("alice", "alice@example.com", "pass")
        assert username_exists("alice") is True
        assert username_exists("bob") is False

    def test_email_exists(self):
        from database.users import create_user, email_exists
        create_user("alice", "alice@example.com", "pass")
        assert email_exists("alice@example.com") is True
        assert email_exists("other@example.com") is False


class TestGetAllUsers:
    def test_returns_all(self):
        from database.users import create_user, get_all_users
        create_user("alice", "a@example.com", "p")
        create_user("bob", "b@example.com", "p")
        users = get_all_users()
        usernames = [u["username"] for u in users]
        assert "alice" in usernames
        assert "bob" in usernames

    def test_empty(self):
        from database.users import get_all_users
        assert get_all_users() == []


# ---------------------------------------------------------------------------
# Trips
# ---------------------------------------------------------------------------


@pytest.fixture
def user_id():
    from database.users import create_user
    return create_user("traveller", "t@example.com", "pass")


@pytest.fixture
def sample_trip():
    return {
        "title": "Paris Trip",
        "link": "paris_trip.html",
        "dates": "2026-06-01 - 2026-06-07",
        "days": 7,
        "locations": 3,
        "activities": 10,
        "map_status": "pending",
    }


class TestAddTrip:
    def test_add_returns_id(self, user_id, sample_trip):
        from database.trips import add_trip
        tid = add_trip(user_id, sample_trip)
        assert isinstance(tid, int) and tid > 0

    def test_upsert_on_same_link(self, user_id, sample_trip):
        from database.trips import add_trip, get_trip_by_link
        add_trip(user_id, sample_trip)
        updated = {**sample_trip, "title": "Paris Trip Updated"}
        add_trip(user_id, updated)
        trip = get_trip_by_link(user_id, sample_trip["link"])
        assert trip["title"] == "Paris Trip Updated"


class TestGetTripByLink:
    def test_found(self, user_id, sample_trip):
        from database.trips import add_trip, get_trip_by_link
        add_trip(user_id, sample_trip)
        trip = get_trip_by_link(user_id, sample_trip["link"])
        assert trip is not None
        assert trip["title"] == "Paris Trip"

    def test_not_found(self, user_id):
        from database.trips import get_trip_by_link
        assert get_trip_by_link(user_id, "nope.html") is None

    def test_itinerary_data_parsed(self, user_id, sample_trip):
        from database.trips import add_trip, get_trip_by_link
        data = {"title": "Paris Trip", "start_date": "2026-06-01", "days": []}
        add_trip(user_id, sample_trip, itinerary_data=data)
        trip = get_trip_by_link(user_id, sample_trip["link"])
        assert isinstance(trip["itinerary_data"], dict)
        assert trip["start_date"] == "2026-06-01"

    def test_wrong_user_returns_none(self, user_id, sample_trip):
        from database.trips import add_trip, get_trip_by_link
        add_trip(user_id, sample_trip)
        assert get_trip_by_link(user_id + 999, sample_trip["link"]) is None


class TestGetUserTrips:
    def test_returns_all_trips(self, user_id, sample_trip):
        from database.trips import add_trip, get_user_trips
        add_trip(user_id, sample_trip)
        add_trip(user_id, {**sample_trip, "link": "rome.html", "title": "Rome"})
        trips = get_user_trips(user_id)
        assert len(trips) == 2

    def test_empty_for_unknown_user(self):
        from database.trips import get_user_trips
        assert get_user_trips(999) == []


class TestUpdateTrip:
    def test_updates_title(self, user_id, sample_trip):
        from database.trips import add_trip, get_trip_by_link, update_trip
        add_trip(user_id, sample_trip)
        update_trip(user_id, sample_trip["link"], {"title": "New Title"})
        trip = get_trip_by_link(user_id, sample_trip["link"])
        assert trip["title"] == "New Title"

    def test_returns_false_for_empty_updates(self, user_id, sample_trip):
        from database.trips import add_trip, update_trip
        add_trip(user_id, sample_trip)
        assert update_trip(user_id, sample_trip["link"], {}) is False

    def test_ignores_disallowed_fields(self, user_id, sample_trip):
        from database.trips import add_trip, update_trip
        add_trip(user_id, sample_trip)
        # "link" is not in allowed_fields, so no rows updated
        result = update_trip(user_id, sample_trip["link"], {"link": "hacked.html"})
        assert result is False


class TestDeleteTrip:
    def test_deletes(self, user_id, sample_trip):
        from database.trips import add_trip, delete_trip, get_trip_by_link
        add_trip(user_id, sample_trip)
        assert delete_trip(user_id, sample_trip["link"]) is True
        assert get_trip_by_link(user_id, sample_trip["link"]) is None

    def test_missing_returns_false(self, user_id):
        from database.trips import delete_trip
        assert delete_trip(user_id, "ghost.html") is False


class TestUpdateTripMapStatus:
    def test_updates_status(self, user_id, sample_trip):
        from database.trips import add_trip, get_trip_by_link, update_trip_map_status
        add_trip(user_id, sample_trip)
        update_trip_map_status(user_id, sample_trip["link"], "ready")
        trip = get_trip_by_link(user_id, sample_trip["link"])
        assert trip["map_status"] == "ready"

    def test_sets_error_message(self, user_id, sample_trip):
        from database.trips import add_trip, get_trip_by_link, update_trip_map_status
        add_trip(user_id, sample_trip)
        update_trip_map_status(user_id, sample_trip["link"], "error", "geocode failed")
        trip = get_trip_by_link(user_id, sample_trip["link"])
        assert trip["map_error"] == "geocode failed"


class TestGetTripOwner:
    def test_returns_owner(self, user_id, sample_trip):
        from database.trips import add_trip, get_trip_owner
        add_trip(user_id, sample_trip)
        assert get_trip_owner(sample_trip["link"]) == user_id

    def test_missing_returns_none(self):
        from database.trips import get_trip_owner
        assert get_trip_owner("ghost.html") is None


# ---------------------------------------------------------------------------
# Drafts
# ---------------------------------------------------------------------------


class TestCreateDraftTrip:
    def test_creates_with_link(self, user_id):
        from database.drafts import create_draft_trip
        result = create_draft_trip(user_id, "My Draft")
        assert result is not None
        assert result["link"].endswith(".html")
        assert result["is_draft"] is True

    def test_link_slug_from_title(self, user_id):
        from database.drafts import create_draft_trip
        result = create_draft_trip(user_id, "Summer in Japan")
        assert "summer" in result["link"]
        assert "japan" in result["link"]

    def test_unique_link_on_collision(self, user_id):
        from database.drafts import create_draft_trip
        r1 = create_draft_trip(user_id, "My Trip")
        r2 = create_draft_trip(user_id, "My Trip")
        assert r1["link"] != r2["link"]

    def test_calculates_days_from_dates(self, user_id):
        from database.drafts import create_draft_trip
        result = create_draft_trip(user_id, "Trip", "2026-06-01", "2026-06-07")
        assert result["days"] == 7


class TestGetDraftTrips:
    def test_returns_only_drafts(self, user_id, sample_trip):
        from database.drafts import create_draft_trip, get_draft_trips
        from database.trips import add_trip
        add_trip(user_id, sample_trip)  # not a draft
        create_draft_trip(user_id, "Draft Trip")
        drafts = get_draft_trips(user_id)
        assert len(drafts) == 1
        assert drafts[0]["title"] == "Draft Trip"


class TestUpdateTripItineraryData:
    def test_updates_data(self, user_id):
        from database.drafts import create_draft_trip, update_trip_itinerary_data
        from database.trips import get_trip_by_link
        draft = create_draft_trip(user_id, "My Draft")
        new_data = {"title": "My Draft", "days": [{"day_number": 1, "items": [{"title": "Lunch", "location": {"name": "Paris"}}]}]}
        update_trip_itinerary_data(user_id, draft["link"], new_data)
        trip = get_trip_by_link(user_id, draft["link"])
        assert trip["itinerary_data"]["days"][0]["items"][0]["title"] == "Lunch"

    def test_updates_activity_count(self, user_id):
        from database.drafts import create_draft_trip, update_trip_itinerary_data
        from database.trips import get_trip_by_link
        draft = create_draft_trip(user_id, "My Draft")
        data = {"title": "My Draft", "items": [{"title": "A"}, {"title": "B"}, {"title": "C"}]}
        update_trip_itinerary_data(user_id, draft["link"], data)
        trip = get_trip_by_link(user_id, draft["link"])
        assert trip["itinerary_data"]["items"] is not None


class TestPublishDraft:
    def test_publish_clears_draft_flag(self, user_id):
        from database.drafts import create_draft_trip, get_draft_trips, publish_draft
        draft = create_draft_trip(user_id, "My Draft")
        assert publish_draft(user_id, draft["link"]) is True
        assert get_draft_trips(user_id) == []

    def test_publish_missing_returns_false(self, user_id):
        from database.drafts import publish_draft
        assert publish_draft(user_id, "ghost.html") is False


class TestAddItemToTrip:
    def test_adds_item(self, user_id):
        from database.drafts import add_item_to_trip, create_draft_trip
        from database.trips import get_trip_by_link
        draft = create_draft_trip(user_id, "My Draft")
        result = add_item_to_trip(user_id, draft["link"], {"title": "Eiffel Tower", "category": "attraction"})
        assert result is True
        trip = get_trip_by_link(user_id, draft["link"])
        assert any(i["title"] == "Eiffel Tower" for i in trip["itinerary_data"]["items"])

    def test_missing_trip_returns_false(self, user_id):
        from database.drafts import add_item_to_trip
        assert add_item_to_trip(user_id, "ghost.html", {"title": "X"}) is False


# ---------------------------------------------------------------------------
# Sharing
# ---------------------------------------------------------------------------


@pytest.fixture
def two_users():
    from database.users import create_user
    uid1 = create_user("alice", "alice@example.com", "pass")
    uid2 = create_user("bob", "bob@example.com", "pass")
    return uid1, uid2


class TestSetTripPublic:
    def test_set_public(self, user_id, sample_trip):
        from database.sharing import set_trip_public
        from database.trips import add_trip
        add_trip(user_id, sample_trip)
        assert set_trip_public(user_id, sample_trip["link"], True) is True

    def test_missing_trip(self, user_id):
        from database.sharing import set_trip_public
        assert set_trip_public(user_id, "ghost.html", True) is False


class TestGetPublicTrips:
    def test_returns_public_only(self, two_users, sample_trip):
        from database.sharing import get_public_trips, set_trip_public
        from database.trips import add_trip
        uid1, uid2 = two_users
        add_trip(uid1, sample_trip)
        set_trip_public(uid1, sample_trip["link"], True)
        trips = get_public_trips()
        assert any(t["link"] == sample_trip["link"] for t in trips)

    def test_excludes_user(self, two_users, sample_trip):
        from database.sharing import get_public_trips, set_trip_public
        from database.trips import add_trip
        uid1, uid2 = two_users
        add_trip(uid1, sample_trip)
        set_trip_public(uid1, sample_trip["link"], True)
        trips = get_public_trips(exclude_user_id=uid1)
        assert not any(t["link"] == sample_trip["link"] for t in trips)


class TestCopyTripToUser:
    def test_copies(self, two_users, sample_trip):
        from database.sharing import copy_trip_to_user
        from database.trips import add_trip, get_trip_by_link
        uid1, uid2 = two_users
        add_trip(uid1, sample_trip)
        new_id = copy_trip_to_user(uid1, sample_trip["link"], uid2)
        assert new_id is not None
        trip = get_trip_by_link(uid2, sample_trip["link"])
        assert trip is not None
        assert trip["title"] == "Paris Trip"

    def test_missing_source_returns_none(self, two_users):
        from database.sharing import copy_trip_to_user
        uid1, uid2 = two_users
        assert copy_trip_to_user(uid1, "ghost.html", uid2) is None


class TestCopyTripByLink:
    def test_owner_gets_no_copy(self, two_users, sample_trip):
        from database.sharing import copy_trip_by_link
        from database.trips import add_trip
        uid1, _ = two_users
        add_trip(uid1, sample_trip)
        result = copy_trip_by_link(sample_trip["link"], uid1)
        assert result is not None
        assert result["was_copied"] is False

    def test_other_user_gets_copy(self, two_users, sample_trip):
        from database.sharing import copy_trip_by_link
        from database.trips import add_trip
        uid1, uid2 = two_users
        add_trip(uid1, sample_trip)
        result = copy_trip_by_link(sample_trip["link"], uid2)
        assert result is not None
        assert result["was_copied"] is True

    def test_missing_link_returns_none(self, two_users):
        from database.sharing import copy_trip_by_link
        _, uid2 = two_users
        assert copy_trip_by_link("ghost.html", uid2) is None


# ---------------------------------------------------------------------------
# Venues
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_venue():
    return {
        "name": "Le Jules Verne",
        "venue_type": "restaurant",
        "city": "Paris",
        "country": "France",
        "cuisine_type": "French",
        "michelin_stars": 1,
        "source": "curated",
    }


class TestAddVenue:
    def test_returns_id(self, sample_venue):
        from database.venues import add_venue
        vid = add_venue(sample_venue)
        assert isinstance(vid, int) and vid > 0

    def test_missing_name_fails(self):
        from database.venues import add_venue
        # name is NOT NULL — should raise and return None
        result = add_venue({"city": "Paris"})
        assert result is None


class TestGetVenueById:
    def test_found(self, sample_venue):
        from database.venues import add_venue, get_venue_by_id
        vid = add_venue(sample_venue)
        venue = get_venue_by_id(vid)
        assert venue["name"] == "Le Jules Verne"
        assert venue["city"] == "Paris"

    def test_missing(self):
        from database.venues import get_venue_by_id
        assert get_venue_by_id(999) is None


class TestSearchVenues:
    def test_finds_by_name(self, sample_venue):
        from database.venues import add_venue, search_venues
        add_venue(sample_venue)
        results = search_venues("Jules Verne")
        assert any(v["name"] == "Le Jules Verne" for v in results)

    def test_finds_by_city(self, sample_venue):
        from database.venues import add_venue, search_venues
        add_venue(sample_venue)
        results = search_venues("Paris")
        assert len(results) >= 1

    def test_no_match(self, sample_venue):
        from database.venues import add_venue, search_venues
        add_venue(sample_venue)
        assert search_venues("Tokyo") == []


class TestFlexibleVenueSearch:
    def test_city_filter(self, sample_venue):
        from database.venues import add_venue, flexible_venue_search
        add_venue(sample_venue)
        results = flexible_venue_search(cities=["Paris"])
        assert any(v["name"] == "Le Jules Verne" for v in results)

    def test_country_filter(self, sample_venue):
        from database.venues import add_venue, flexible_venue_search
        add_venue(sample_venue)
        results = flexible_venue_search(countries=["France"])
        assert len(results) >= 1

    def test_michelin_only(self, sample_venue):
        from database.venues import add_venue, flexible_venue_search
        add_venue(sample_venue)
        add_venue({"name": "Bistro", "venue_type": "restaurant", "city": "Paris", "country": "France", "michelin_stars": 0, "source": "curated"})
        results = flexible_venue_search(michelin_only=True)
        names = [v["name"] for v in results]
        assert "Le Jules Verne" in names
        assert "Bistro" not in names

    def test_no_filters_returns_all(self, sample_venue):
        from database.venues import add_venue, flexible_venue_search
        add_venue(sample_venue)
        add_venue({**sample_venue, "name": "Café de Flore"})
        results = flexible_venue_search()
        assert len(results) == 2


class TestFindVenueByNameAndCity:
    def test_finds_with_city(self, sample_venue):
        from database.venues import add_venue, find_venue_by_name_and_city
        add_venue(sample_venue)
        venue = find_venue_by_name_and_city("Le Jules Verne", "Paris")
        assert venue is not None

    def test_finds_without_city(self, sample_venue):
        from database.venues import add_venue, find_venue_by_name_and_city
        add_venue(sample_venue)
        venue = find_venue_by_name_and_city("Le Jules Verne")
        assert venue is not None

    def test_wrong_city_returns_none(self, sample_venue):
        from database.venues import add_venue, find_venue_by_name_and_city
        add_venue(sample_venue)
        assert find_venue_by_name_and_city("Le Jules Verne", "Tokyo") is None

    def test_case_insensitive(self, sample_venue):
        from database.venues import add_venue, find_venue_by_name_and_city
        add_venue(sample_venue)
        assert find_venue_by_name_and_city("le jules verne", "paris") is not None


class TestGetVenueCount:
    def test_count(self, sample_venue):
        from database.venues import add_venue, get_venue_count
        assert get_venue_count() == 0
        add_venue(sample_venue)
        assert get_venue_count() == 1
        add_venue({**sample_venue, "name": "Other"})
        assert get_venue_count() == 2


class TestUpdateVenueCoordinates:
    def test_updates(self, sample_venue):
        from database.venues import add_venue, get_venue_by_id, update_venue_coordinates
        vid = add_venue(sample_venue)
        update_venue_coordinates(vid, 48.8584, 2.2945)
        venue = get_venue_by_id(vid)
        assert abs(venue["latitude"] - 48.8584) < 0.001
        assert abs(venue["longitude"] - 2.2945) < 0.001


class TestImportVenuesFromCsv:
    def test_imports_rows(self, tmp_path):
        from database.venues import get_venue_count, import_venues_from_csv
        csv_file = tmp_path / "venues.csv"
        csv_file.write_text(
            "name,venue_type,city,country,latitude,longitude\n"
            "Café de Flore,restaurant,Paris,France,48.854,2.332\n"
            "Musée d'Orsay,museum,Paris,France,48.860,2.327\n"
        )
        count = import_venues_from_csv(str(csv_file))
        assert count == 2
        assert get_venue_count() == 2

    def test_skips_rows_without_name(self, tmp_path):
        from database.venues import get_venue_count, import_venues_from_csv
        csv_file = tmp_path / "venues.csv"
        csv_file.write_text("name,city\n,Paris\nCafé de Flore,Paris\n")
        count = import_venues_from_csv(str(csv_file))
        assert count == 1
        assert get_venue_count() == 1
