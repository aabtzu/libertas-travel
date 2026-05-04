"""Unit tests for agents/create/file_parsers.py, _normalize_item and date handling."""

from __future__ import annotations

import pytest

from agents.create.file_parsers import _normalize_item, extract_coords_from_url

# ---------------------------------------------------------------------------
# Title normalisation
# ---------------------------------------------------------------------------


class TestNormalizeItemTitle:
    def test_uses_title_field(self):
        assert _normalize_item({"title": "Eiffel Tower"})["title"] == "Eiffel Tower"

    def test_falls_back_to_name(self):
        assert _normalize_item({"name": "Louvre"})["title"] == "Louvre"

    def test_falls_back_to_summary(self):
        assert _normalize_item({"summary": "City tour"})["title"] == "City tour"

    def test_falls_back_to_event(self):
        assert _normalize_item({"event": "Welcome dinner"})["title"] == "Welcome dinner"

    def test_defaults_to_untitled(self):
        assert _normalize_item({})["title"] == "Untitled"

    def test_title_takes_priority_over_name(self):
        assert _normalize_item({"title": "A", "name": "B"})["title"] == "A"


# ---------------------------------------------------------------------------
# Category normalisation
# ---------------------------------------------------------------------------


class TestNormalizeItemCategory:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("flight", "flight"),
            ("air", "flight"),
            ("plane", "flight"),
            ("train", "train"),
            ("bus", "bus"),
            ("car", "transport"),
            ("transport", "transport"),
            ("transportation", "transport"),
            ("transfer", "transport"),
            ("hotel", "hotel"),
            ("accommodation", "hotel"),
            ("lodging", "hotel"),
            ("stay", "hotel"),
            ("hostel", "hotel"),
            ("meal", "meal"),
            ("restaurant", "meal"),
            ("food", "meal"),
            ("dining", "meal"),
            ("breakfast", "meal"),
            ("lunch", "meal"),
            ("dinner", "meal"),
            ("attraction", "attraction"),
            ("sightseeing", "attraction"),
            ("museum", "attraction"),
            ("tour", "attraction"),
            ("activity", "activity"),
            ("event", "activity"),
        ],
    )
    def test_category_mapping(self, raw, expected):
        result = _normalize_item({"title": "X", "category": raw})
        assert result["category"] == expected

    def test_unknown_category_passed_through(self):
        result = _normalize_item({"title": "X", "category": "yoga"})
        assert result["category"] == "activity"  # unknown values default to activity

    def test_missing_category_defaults_to_activity(self):
        result = _normalize_item({"title": "X"})
        assert result["category"] == "activity"

    def test_type_field_used_as_fallback(self):
        result = _normalize_item({"title": "X", "type": "flight"})
        assert result["category"] == "flight"

    def test_category_case_insensitive(self):
        result = _normalize_item({"title": "X", "category": "FLIGHT"})
        assert result["category"] == "flight"


# ---------------------------------------------------------------------------
# Date normalisation
# ---------------------------------------------------------------------------


class TestNormalizeItemDate:
    def test_iso_date_preserved(self):
        result = _normalize_item({"title": "X", "date": "2026-06-15"})
        assert result["date"] == "2026-06-15"

    def test_iso_date_with_time_truncated(self):
        result = _normalize_item({"title": "X", "date": "2026-06-15T14:30:00"})
        assert result["date"] == "2026-06-15"

    def test_start_date_field_used(self):
        result = _normalize_item({"title": "X", "start_date": "2026-07-01"})
        assert result["date"] == "2026-07-01"

    def test_startDate_camel_case_used(self):
        result = _normalize_item({"title": "X", "startDate": "2026-08-20"})
        assert result["date"] == "2026-08-20"

    def test_date_field_takes_priority(self):
        result = _normalize_item({"title": "X", "date": "2026-06-01", "start_date": "2026-07-01"})
        assert result["date"] == "2026-06-01"

    def test_no_date_field_omitted(self):
        result = _normalize_item({"title": "X"})
        assert "date" not in result

    def test_us_date_format_parsed(self):
        result = _normalize_item({"title": "X", "date": "06/15/2026"})
        assert result.get("date") == "2026-06-15"

    def test_invalid_date_omitted(self):
        result = _normalize_item({"title": "X", "date": "not-a-date"})
        assert "date" not in result


# ---------------------------------------------------------------------------
# Time normalisation
# ---------------------------------------------------------------------------


class TestNormalizeItemTime:
    def test_hhmm_preserved(self):
        result = _normalize_item({"title": "X", "time": "14:30"})
        assert result["time"] == "14:30"

    def test_hhmmss_truncated_to_hhmm(self):
        result = _normalize_item({"title": "X", "time": "14:30:00"})
        assert result["time"] == "14:30"

    def test_four_digit_no_colon_formatted(self):
        result = _normalize_item({"title": "X", "time": "1430"})
        assert result["time"] == "14:30"

    def test_start_time_field_used(self):
        result = _normalize_item({"title": "X", "start_time": "09:00"})
        assert result["time"] == "09:00"

    def test_end_time_normalised(self):
        result = _normalize_item({"title": "X", "end_time": "16:45"})
        assert result["end_time"] == "16:45"

    def test_arrival_time_used_as_end_time(self):
        result = _normalize_item({"title": "X", "arrival_time": "18:00"})
        assert result["end_time"] == "18:00"

    def test_no_time_omitted(self):
        result = _normalize_item({"title": "X"})
        assert "time" not in result


# ---------------------------------------------------------------------------
# Location normalisation
# ---------------------------------------------------------------------------


class TestNormalizeItemLocation:
    def test_string_location(self):
        result = _normalize_item({"title": "X", "location": "Paris"})
        assert result["location"] == "Paris"

    def test_dict_location_name(self):
        result = _normalize_item({"title": "X", "location": {"name": "Paris"}})
        assert result["location"] == "Paris"

    def test_dict_location_city_fallback(self):
        result = _normalize_item({"title": "X", "location": {"city": "Rome"}})
        assert result["location"] == "Rome"

    def test_city_field_as_fallback(self):
        result = _normalize_item({"title": "X", "city": "Madrid"})
        assert result["location"] == "Madrid"

    def test_address_field_as_fallback(self):
        result = _normalize_item({"title": "X", "address": "10 Downing St"})
        assert result["location"] == "10 Downing St"

    def test_no_location_omitted(self):
        result = _normalize_item({"title": "X"})
        assert "location" not in result


# ---------------------------------------------------------------------------
# Notes and day number
# ---------------------------------------------------------------------------


class TestNormalizeItemMisc:
    def test_notes_field(self):
        result = _normalize_item({"title": "X", "notes": "Confirmation: ABC123"})
        assert result["notes"] == "Confirmation: ABC123"

    def test_description_as_notes_fallback(self):
        result = _normalize_item({"title": "X", "description": "Nice place"})
        assert result["notes"] == "Nice place"

    def test_notes_truncated_at_500(self):
        long = "x" * 600
        result = _normalize_item({"title": "X", "notes": long})
        assert len(result["notes"]) == 500

    def test_day_number(self):
        result = _normalize_item({"title": "X", "day": 3})
        assert result["day"] == 3

    def test_day_number_field(self):
        result = _normalize_item({"title": "X", "day_number": 5})
        assert result["day"] == 5


# ---------------------------------------------------------------------------
# Coordinate extraction
# ---------------------------------------------------------------------------


class TestNormalizeItemCoordinates:
    def test_latitude_longitude_fields(self):
        result = _normalize_item({"title": "X", "latitude": 48.8566, "longitude": 2.3522})
        assert result["latitude"] == 48.8566
        assert result["longitude"] == 2.3522

    def test_lat_lng_fields(self):
        result = _normalize_item({"title": "X", "lat": 48.8566, "lng": 2.3522})
        assert result["latitude"] == 48.8566
        assert result["longitude"] == 2.3522

    def test_string_coordinates_converted(self):
        result = _normalize_item({"title": "X", "latitude": "48.8566", "longitude": "2.3522"})
        assert result["latitude"] == 48.8566
        assert result["longitude"] == 2.3522

    def test_missing_longitude_omits_both(self):
        result = _normalize_item({"title": "X", "latitude": 48.8566})
        assert "latitude" not in result
        assert "longitude" not in result

    def test_missing_latitude_omits_both(self):
        result = _normalize_item({"title": "X", "longitude": 2.3522})
        assert "latitude" not in result
        assert "longitude" not in result

    def test_invalid_latitude_range_omitted(self):
        result = _normalize_item({"title": "X", "latitude": 999, "longitude": 2.35})
        assert "latitude" not in result

    def test_invalid_longitude_range_omitted(self):
        result = _normalize_item({"title": "X", "latitude": 48.8, "longitude": 999})
        assert "latitude" not in result

    def test_non_numeric_omitted(self):
        result = _normalize_item({"title": "X", "latitude": "abc", "longitude": "def"})
        assert "latitude" not in result

    def test_dict_location_with_coordinates(self):
        loc = {"name": "Eiffel Tower", "latitude": 48.8584, "longitude": 2.2945}
        result = _normalize_item({"title": "X", "location": loc})
        assert result["latitude"] == 48.8584
        assert result["longitude"] == 2.2945
        assert result["location"] == "Eiffel Tower"

    def test_google_maps_url_extraction(self):
        result = _normalize_item(
            {
                "title": "X",
                "url": "https://www.google.com/maps/place/Eiffel+Tower/@48.8584,2.2945,17z",
            }
        )
        assert result["latitude"] == 48.8584
        assert result["longitude"] == 2.2945

    def test_google_maps_url_in_google_maps_url_field(self):
        result = _normalize_item(
            {
                "title": "X",
                "google_maps_url": "https://www.google.com/maps/place/X/@40.7484,-73.9857,15z",
            }
        )
        assert result["latitude"] == 40.7484
        assert result["longitude"] == -73.9857

    def test_explicit_coords_take_priority_over_url(self):
        result = _normalize_item(
            {
                "title": "X",
                "latitude": 1.0,
                "longitude": 2.0,
                "url": "https://www.google.com/maps/place/X/@48.8,2.3,15z",
            }
        )
        assert result["latitude"] == 1.0
        assert result["longitude"] == 2.0

    def test_negative_coordinates(self):
        result = _normalize_item({"title": "X", "latitude": -33.8688, "longitude": 151.2093})
        assert result["latitude"] == -33.8688
        assert result["longitude"] == 151.2093


# ---------------------------------------------------------------------------
# Google Maps URL coordinate extraction
# ---------------------------------------------------------------------------


class TestExtractCoordsFromUrl:
    def test_at_sign_format(self):
        url = "https://www.google.com/maps/place/Eiffel+Tower/@48.8584,2.2945,17z"
        assert extract_coords_from_url(url) == (48.8584, 2.2945)

    def test_query_format(self):
        url = "https://maps.google.com/?q=48.8566,2.3522"
        assert extract_coords_from_url(url) == (48.8566, 2.3522)

    def test_negative_coords(self):
        url = "https://www.google.com/maps/place/X/@-33.8688,151.2093,15z"
        assert extract_coords_from_url(url) == (-33.8688, 151.2093)

    def test_non_google_url_returns_none(self):
        assert extract_coords_from_url("https://example.com/@48.8,2.3") is None

    def test_none_input(self):
        assert extract_coords_from_url(None) is None

    def test_empty_string(self):
        assert extract_coords_from_url("") is None

    def test_no_coords_in_google_url(self):
        assert extract_coords_from_url("https://www.google.com/maps") is None


# ---------------------------------------------------------------------------
# Coordinate round-trip through itinerary serialization
# ---------------------------------------------------------------------------


class TestCoordinateRoundTrip:
    def test_coordinates_survive_serialization(self):
        """Coords set on Location survive itinerary_to_data -> _create_itinerary_item."""
        from agents.create.itinerary_utils import _create_itinerary_item, itinerary_to_data
        from agents.itinerary.models import Itinerary, ItineraryItem, Location

        loc = Location(name="Eiffel Tower", latitude=48.8584, longitude=2.2945)
        item = ItineraryItem(
            title="Visit Eiffel Tower",
            location=loc,
            category="attraction",
            day_number=1,
        )
        itinerary = Itinerary(title="Paris Trip", items=[item])

        data = itinerary_to_data(itinerary)
        day_items = data["days"][0]["items"]
        assert day_items[0]["latitude"] == 48.8584
        assert day_items[0]["longitude"] == 2.2945
        # location field stays a string for frontend compatibility
        assert day_items[0]["location"] == "Eiffel Tower"

        restored = _create_itinerary_item(day_items[0], 1, None)
        assert restored.location.latitude == 48.8584
        assert restored.location.longitude == 2.2945
        assert restored.location.has_coordinates

    def test_no_coordinates_remains_none(self):
        """Items without coords don't get spurious lat/lng."""
        from agents.create.itinerary_utils import _create_itinerary_item, itinerary_to_data
        from agents.itinerary.models import Itinerary, ItineraryItem, Location

        loc = Location(name="Paris")
        item = ItineraryItem(
            title="Walk around",
            location=loc,
            category="activity",
            day_number=1,
        )
        itinerary = Itinerary(title="Trip", items=[item])

        data = itinerary_to_data(itinerary)
        day_items = data["days"][0]["items"]
        assert day_items[0]["latitude"] is None

        restored = _create_itinerary_item(day_items[0], 1, None)
        assert not restored.location.has_coordinates
