"""Tests for agents.import_url.handler."""

from __future__ import annotations

from unittest.mock import patch


class TestGetUserTripsForPicker:
    def test_returns_published_and_drafts(self):
        from agents.import_url.handler import get_user_trips_for_picker

        published = [{"link": "trip1.html", "title": "Trip 1", "is_archived": False}]
        drafts = [{"link": "draft1.html", "title": "Draft 1"}]

        with patch("agents.import_url.handler.db") as mock_db:
            mock_db.get_user_trips.return_value = published
            mock_db.get_draft_trips.return_value = drafts
            result = get_user_trips_for_picker(1)

        assert len(result) == 2
        assert result[0]["link"] == "trip1.html"
        assert result[0]["is_draft"] is False
        assert result[1]["link"] == "draft1.html"
        assert "(draft)" in result[1]["title"]

    def test_excludes_archived_trips(self):
        from agents.import_url.handler import get_user_trips_for_picker

        published = [
            {"link": "trip1.html", "title": "Active", "is_archived": False},
            {"link": "trip2.html", "title": "Archived", "is_archived": True},
        ]

        with patch("agents.import_url.handler.db") as mock_db:
            mock_db.get_user_trips.return_value = published
            mock_db.get_draft_trips.return_value = []
            result = get_user_trips_for_picker(1)

        assert len(result) == 1
        assert result[0]["link"] == "trip1.html"

    def test_empty_trips(self):
        from agents.import_url.handler import get_user_trips_for_picker

        with patch("agents.import_url.handler.db") as mock_db:
            mock_db.get_user_trips.return_value = []
            mock_db.get_draft_trips.return_value = []
            result = get_user_trips_for_picker(1)

        assert result == []


class TestAddItemsToTrip:
    def test_adds_items_to_existing_ideas(self):
        from agents.import_url.handler import add_items_to_trip

        existing = {
            "title": "My Trip",
            "days": [],
            "ideas": [{"title": "Existing"}],
        }
        new_items = [{"title": "New Place", "category": "restaurant"}]

        with patch("agents.import_url.handler.db") as mock_db:
            mock_db.get_trip_by_link.return_value = {"itinerary_data": existing}
            mock_db.update_trip_itinerary_data.return_value = True
            result = add_items_to_trip(1, "trip.html", new_items, "https://example.com", "Example")

        assert result is True
        saved_data = mock_db.update_trip_itinerary_data.call_args[0][2]
        assert len(saved_data["ideas"]) == 2
        assert saved_data["ideas"][1]["title"] == "New Place"
        assert saved_data["ideas"][1]["source_url"] == "https://example.com"

    def test_creates_ideas_list_if_missing(self):
        from agents.import_url.handler import add_items_to_trip

        existing = {"title": "My Trip", "days": []}

        with patch("agents.import_url.handler.db") as mock_db:
            mock_db.get_trip_by_link.return_value = {"itinerary_data": existing}
            mock_db.update_trip_itinerary_data.return_value = True
            add_items_to_trip(1, "trip.html", [{"title": "Item"}], "https://x.com", "X")

        saved_data = mock_db.update_trip_itinerary_data.call_args[0][2]
        assert "ideas" in saved_data
        assert len(saved_data["ideas"]) == 1

    def test_returns_false_if_trip_not_found(self):
        from agents.import_url.handler import add_items_to_trip

        with patch("agents.import_url.handler.db") as mock_db:
            mock_db.get_trip_by_link.return_value = None
            result = add_items_to_trip(1, "missing.html", [{"title": "Item"}], "https://x.com", "X")

        assert result is False


class TestFetchAndExtract:
    def test_returns_items_on_success(self):
        from agents.import_url.handler import fetch_and_extract

        with (
            patch("agents.import_url.handler.fetch_webpage_for_chat") as mock_fetch,
            patch("agents.import_url.handler.upload_plan_handler") as mock_parse,
        ):
            mock_fetch.return_value = {"success": True, "text": "some text", "title": "Page Title"}
            mock_parse.return_value = ({"success": True, "items": [{"title": "Item A"}]}, 200)
            result = fetch_and_extract("https://example.com")

        assert result["success"] is True
        assert result["title"] == "Page Title"
        assert len(result["items"]) == 1

    def test_returns_error_on_fetch_failure(self):
        from agents.import_url.handler import fetch_and_extract

        with patch("agents.import_url.handler.fetch_webpage_for_chat") as mock_fetch:
            mock_fetch.return_value = {"success": False, "error": "Connection refused"}
            result = fetch_and_extract("https://broken.example.com")

        assert result["success"] is False
        assert "Connection refused" in result["error"]

    def test_returns_error_on_empty_text(self):
        from agents.import_url.handler import fetch_and_extract

        with patch("agents.import_url.handler.fetch_webpage_for_chat") as mock_fetch:
            mock_fetch.return_value = {"success": True, "text": "   ", "title": "Blank"}
            result = fetch_and_extract("https://blank.example.com")

        assert result["success"] is False
        assert "no readable text" in result["error"].lower()
