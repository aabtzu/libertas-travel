"""Tests for agents/common/venue_capture.py and auto-import from trip publish."""

from __future__ import annotations

from unittest.mock import patch

from agents.common.venue_capture import is_place_category, save_venue_to_curated


class TestIsPlaceCategory:
    def test_restaurant_is_place(self):
        assert is_place_category("restaurant") is True

    def test_hotel_is_place(self):
        assert is_place_category("hotel") is True

    def test_activity_is_place(self):
        assert is_place_category("activity") is True

    def test_flight_is_not_place(self):
        assert is_place_category("flight") is False

    def test_transport_is_not_place(self):
        assert is_place_category("transport") is False

    def test_train_is_not_place(self):
        assert is_place_category("train") is False

    def test_unknown_category_treated_as_place(self):
        # Unknown categories default to yes
        assert is_place_category("some_new_type") is True

    def test_empty_category_treated_as_place(self):
        assert is_place_category("") is True

    def test_case_insensitive(self):
        assert is_place_category("FLIGHT") is False
        assert is_place_category("Restaurant") is True


class TestSaveVenueToCurated:
    def test_skips_empty_name(self):
        result = save_venue_to_curated("", "Paris")
        assert result["saved"] is False
        assert result["skipped"] is True
        assert result["reason"] == "no name"

    def test_skips_duplicate(self):
        existing = {"id": 42, "name": "Roscioli", "city": "Rome"}
        with patch("agents.common.venue_capture.db.find_venue_by_name_and_city", return_value=existing):
            result = save_venue_to_curated("Roscioli", "Rome")
        assert result["saved"] is False
        assert result["skipped"] is True
        assert result["reason"] == "already exists"
        assert result["venue_id"] == 42

    def test_saves_new_venue(self):
        with (
            patch("agents.common.venue_capture.db.find_venue_by_name_and_city", return_value=None),
            patch("agents.common.venue_capture._enrich_with_haiku", return_value={"venue_type": "Restaurant", "cuisine_type": "Italian", "description": "A great trattoria."}),
            patch("agents.common.venue_capture.db.add_venue", return_value=99),
        ):
            result = save_venue_to_curated("Trattoria da Mario", "Florence")
        assert result["saved"] is True
        assert result["venue_id"] == 99
        assert result["reason"] == "added"

    def test_returns_db_error_on_add_failure(self):
        with (
            patch("agents.common.venue_capture.db.find_venue_by_name_and_city", return_value=None),
            patch("agents.common.venue_capture._enrich_with_haiku", return_value={}),
            patch("agents.common.venue_capture.db.add_venue", return_value=None),
        ):
            result = save_venue_to_curated("Mystery Place", "Berlin")
        assert result["saved"] is False
        assert result["reason"] == "db error"

    def test_invalidates_venues_cache_on_save(self):
        import agents.explore.handler as eh

        eh._venues_cache = [{"name": "old"}]
        with (
            patch("agents.common.venue_capture.db.find_venue_by_name_and_city", return_value=None),
            patch("agents.common.venue_capture._enrich_with_haiku", return_value={}),
            patch("agents.common.venue_capture.db.add_venue", return_value=7),
        ):
            save_venue_to_curated("New Place", "NYC")
        assert eh._venues_cache is None


class TestAutoImportTripVenues:
    def _itinerary(self, items_by_day=None, ideas=None):
        days = []
        for date, items in (items_by_day or {}).items():
            days.append({"date": date, "items": items})
        return {"days": days, "ideas": ideas or []}

    def test_skips_flight_items(self):
        from agents.create.handler import _auto_import_trip_venues

        itinerary = self._itinerary({"2026-09-15": [{"title": "Flight to JFK", "category": "flight"}]})
        with patch("agents.common.venue_capture.db.find_venue_by_name_and_city", return_value=None):
            count = _auto_import_trip_venues(1, itinerary)
        assert count == 0

    def test_saves_restaurant_items(self):
        from agents.create.handler import _auto_import_trip_venues

        itinerary = self._itinerary(
            {"2026-09-15": [{"title": "Roscioli", "category": "restaurant", "notes": "great pasta", "location": {"city": "Rome"}}]}
        )
        with (
            patch("agents.common.venue_capture.db.find_venue_by_name_and_city", return_value=None),
            patch("agents.common.venue_capture._enrich_with_haiku", return_value={}),
            patch("agents.common.venue_capture.db.add_venue", return_value=5),
        ):
            count = _auto_import_trip_venues(1, itinerary)
        assert count == 1

    def test_saves_ideas_too(self):
        from agents.create.handler import _auto_import_trip_venues

        itinerary = self._itinerary(ideas=[{"title": "Blue Lagoon", "category": "activity", "location": {"city": "Reykjavik"}}])
        with (
            patch("agents.common.venue_capture.db.find_venue_by_name_and_city", return_value=None),
            patch("agents.common.venue_capture._enrich_with_haiku", return_value={}),
            patch("agents.common.venue_capture.db.add_venue", return_value=8),
        ):
            count = _auto_import_trip_venues(1, itinerary)
        assert count == 1

    def test_skips_items_without_title(self):
        from agents.create.handler import _auto_import_trip_venues

        itinerary = self._itinerary({"2026-09-15": [{"category": "restaurant"}]})
        with patch("agents.common.venue_capture.db.find_venue_by_name_and_city", return_value=None):
            count = _auto_import_trip_venues(1, itinerary)
        assert count == 0
