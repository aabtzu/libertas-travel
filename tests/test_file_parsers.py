"""Unit tests for agents/create/file_parsers.py — _normalize_item and date handling."""

from __future__ import annotations

import pytest

from agents.create.file_parsers import _normalize_item

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
