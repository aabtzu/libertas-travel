"""Tests for ItinerarySummarizer — unit tests run without API."""

import os
import sys
from datetime import date

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.itinerary.models import Itinerary, ItineraryItem, Location
from agents.itinerary.summarizer import ItinerarySummarizer


def _make_itinerary(**kwargs):
    defaults = dict(
        title="Tokyo Trip",
        items=[],
        start_date=date(2026, 5, 1),
        end_date=date(2026, 5, 5),
        travelers=["Alice"],
        source_file="test.pdf",
    )
    defaults.update(kwargs)
    return Itinerary(**defaults)


def _make_item(
    title="Hotel Hyatt",
    category="hotel",
    location_name="Tokyo, Japan",
    item_date=None,
    start_time=None,
    day_number=1,
):
    return ItineraryItem(
        title=title,
        location=Location(name=location_name),
        category=category,
        date=item_date,
        start_time=start_time,
        day_number=day_number,
    )


# ---------------------------------------------------------------------------
# Unit tests — no API calls
# ---------------------------------------------------------------------------


class TestFormatItineraryForPrompt:
    def setup_method(self):
        self.s = ItinerarySummarizer()

    def test_includes_title(self):
        result = self.s._format_itinerary_for_prompt(_make_itinerary())
        assert "Tokyo Trip" in result

    def test_includes_dates(self):
        result = self.s._format_itinerary_for_prompt(_make_itinerary())
        assert "2026-05-01" in result
        assert "2026-05-05" in result

    def test_includes_travelers(self):
        result = self.s._format_itinerary_for_prompt(_make_itinerary())
        assert "Alice" in result

    def test_includes_item_title(self):
        item = _make_item(title="Senso-ji Temple")
        result = self.s._format_itinerary_for_prompt(_make_itinerary(items=[item]))
        assert "Senso-ji Temple" in result

    def test_includes_item_location(self):
        item = _make_item(location_name="Asakusa, Tokyo")
        result = self.s._format_itinerary_for_prompt(_make_itinerary(items=[item]))
        assert "Asakusa, Tokyo" in result


class TestQuickSummary:
    def setup_method(self):
        self.s = ItinerarySummarizer()

    def test_includes_title_as_heading(self):
        result = self.s.quick_summary(_make_itinerary())
        assert "# Tokyo Trip" in result

    def test_includes_dates(self):
        result = self.s.quick_summary(_make_itinerary())
        assert "May 01" in result or "May 1" in result

    def test_includes_travelers(self):
        result = self.s.quick_summary(_make_itinerary())
        assert "Alice" in result

    def test_item_appears_under_day(self):
        item = _make_item(title="Senso-ji Temple", day_number=1)
        result = self.s.quick_summary(_make_itinerary(items=[item]))
        assert "Senso-ji Temple" in result
        assert "Day 1" in result

    def test_empty_items(self):
        result = self.s.quick_summary(_make_itinerary(items=[]))
        assert "# Tokyo Trip" in result  # Should not crash


# ---------------------------------------------------------------------------
# Integration tests — require live API
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_summarize_returns_text():
    s = ItinerarySummarizer()
    itinerary = _make_itinerary(
        items=[
            _make_item("Park Hyatt Tokyo", "hotel", "Shinjuku, Tokyo"),
            _make_item("Senso-ji Temple", "activity", "Asakusa, Tokyo"),
        ]
    )
    result = s.summarize(itinerary)
    assert isinstance(result, str)
    assert len(result) > 100
    assert "Tokyo" in result
