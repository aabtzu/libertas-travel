"""Tests for the upcoming/past/undated grouping on /trips."""

from __future__ import annotations

from agents.itinerary.templates import _bucket_trip_by_date, _sort_trips_for_display

TODAY = "2026-05-03"


class TestBucketTripByDate:
    def test_future_date_is_upcoming(self):
        trip = {"itinerary_data": {"start_date": "2026-12-15"}}
        assert _bucket_trip_by_date(trip, TODAY) == "upcoming"

    def test_today_is_upcoming(self):
        trip = {"itinerary_data": {"start_date": TODAY}}
        assert _bucket_trip_by_date(trip, TODAY) == "upcoming"

    def test_past_date_is_past(self):
        trip = {"itinerary_data": {"start_date": "2025-01-01"}}
        assert _bucket_trip_by_date(trip, TODAY) == "past"

    def test_no_date_is_undated(self):
        trip = {"itinerary_data": {}}
        assert _bucket_trip_by_date(trip, TODAY) == "undated"

    def test_first_day_date_is_used_when_no_start_date(self):
        trip = {"itinerary_data": {"days": [{"date": "2026-08-10"}]}}
        assert _bucket_trip_by_date(trip, TODAY) == "upcoming"

    def test_string_itinerary_data_is_parsed(self):
        trip = {"itinerary_data": '{"start_date": "2026-09-01"}'}
        assert _bucket_trip_by_date(trip, TODAY) == "upcoming"


class TestSortTripsForDisplay:
    def test_upcoming_then_past_then_undated(self):
        # Sort key already groups buckets in this order; verify ordering.
        trips = [
            {"title": "Past A", "itinerary_data": {"start_date": "2025-01-01"}},
            {"title": "Future B", "itinerary_data": {"start_date": "2027-01-01"}},
            {"title": "Undated", "itinerary_data": {}},
            {"title": "Future A", "itinerary_data": {"start_date": "2026-12-01"}},
        ]
        sorted_titles = [t["title"] for t in _sort_trips_for_display(trips)]
        # Future A (2026-12) before Future B (2027), then Past, then Undated
        assert sorted_titles == ["Future A", "Future B", "Past A", "Undated"]
