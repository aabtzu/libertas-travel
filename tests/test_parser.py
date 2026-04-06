"""Tests for itinerary parser — unit tests run without API, integration tests need ANTHROPIC_API_KEY."""

import json
import pytest
from datetime import date, time

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.itinerary.parser import fix_json_string, ItineraryParser


# ---------------------------------------------------------------------------
# Unit tests — no API calls
# ---------------------------------------------------------------------------

class TestFixJsonString:
    def test_removes_trailing_comma_in_object(self):
        raw = '{"a": 1, "b": 2,}'
        assert json.loads(fix_json_string(raw)) == {"a": 1, "b": 2}

    def test_removes_trailing_comma_in_array(self):
        raw = '[1, 2, 3,]'
        assert json.loads(fix_json_string(raw)) == [1, 2, 3]

    def test_removes_trailing_comma_nested(self):
        raw = '{"items": [{"a": 1,}, {"b": 2,},]}'
        result = json.loads(fix_json_string(raw))
        assert result == {"items": [{"a": 1}, {"b": 2}]}

    def test_valid_json_unchanged(self):
        raw = '{"title": "Paris Trip", "items": []}'
        assert json.loads(fix_json_string(raw)) == {"title": "Paris Trip", "items": []}

    def test_removes_control_characters(self):
        raw = '{"a": "hello\x07world"}'
        result = json.loads(fix_json_string(raw))
        assert result == {"a": "helloworld"}


class TestBuildItinerary:
    def setup_method(self):
        self.parser = ItineraryParser()

    def test_basic_itinerary_structure(self):
        data = {
            "title": "Tokyo Trip",
            "start_date": "2026-05-01",
            "end_date": "2026-05-10",
            "travelers": ["Alice"],
            "items": [
                {
                    "title": "Arrival at Narita",
                    "location_name": "Narita, Japan",
                    "category": "flight",
                    "date": "2026-05-01",
                    "start_time": "14:00",
                    "end_time": "16:30",
                    "is_home_location": False,
                }
            ]
        }
        itinerary = self.parser._build_itinerary(data, "test.pdf")
        assert itinerary.title == "Tokyo Trip"
        assert itinerary.start_date == date(2026, 5, 1)
        assert itinerary.end_date == date(2026, 5, 10)
        assert itinerary.travelers == ["Alice"]
        assert len(itinerary.items) == 1
        item = itinerary.items[0]
        assert item.title == "Arrival at Narita"
        assert item.category == "flight"
        assert item.start_time == time(14, 0)
        assert item.end_time == time(16, 30)
        assert item.is_home_location is False

    def test_home_location_flag(self):
        data = {
            "title": "Trip",
            "items": [
                {"title": "Home Departure", "location_name": "Denver, CO", "is_home_location": True},
                {"title": "Hotel Tokyo", "location_name": "Tokyo, Japan", "is_home_location": False},
            ]
        }
        itinerary = self.parser._build_itinerary(data, "test.pdf")
        assert itinerary.items[0].is_home_location is True
        assert itinerary.items[1].is_home_location is False

    def test_missing_fields_use_defaults(self):
        data = {"title": "Minimal Trip", "items": [{"title": "Something"}]}
        itinerary = self.parser._build_itinerary(data, "test.pdf")
        assert itinerary.title == "Minimal Trip"
        assert itinerary.start_date is None
        assert itinerary.travelers == []
        item = itinerary.items[0]
        assert item.title == "Something"
        assert item.date is None
        assert item.start_time is None

    def test_invalid_date_returns_none(self):
        data = {"title": "Trip", "items": [{"title": "X", "date": "not-a-date"}]}
        itinerary = self.parser._build_itinerary(data, "test.pdf")
        assert itinerary.items[0].date is None

    def test_invalid_time_returns_none(self):
        data = {"title": "Trip", "items": [{"title": "X", "start_time": "25:99"}]}
        itinerary = self.parser._build_itinerary(data, "test.pdf")
        assert itinerary.items[0].start_time is None


# ---------------------------------------------------------------------------
# Integration tests — require live API
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_parse_text_basic():
    """Parse a short itinerary text and verify structure comes back correctly."""
    parser = ItineraryParser()
    sample = """
    Tokyo Adventure - May 1-5, 2026
    Traveler: Alice

    Day 1 - May 1:
    14:00 Arrive at Narita International Airport (NRT)
    Check in: Park Hyatt Tokyo, Shinjuku

    Day 2 - May 2:
    10:00 Visit Senso-ji Temple, Asakusa
    19:00 Dinner at Sukiyabashi Jiro
    """
    itinerary = parser.parse_text(sample)
    assert itinerary.title
    assert len(itinerary.items) > 0
    # Should have found at least the hotel and temple
    titles = [i.title.lower() for i in itinerary.items]
    assert any("tokyo" in t or "hyatt" in t or "senso" in t or "narita" in t for t in titles)
