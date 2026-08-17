"""Tests for agents/email/handler.py - subject cleaning and draft-save helpers."""

from __future__ import annotations

from unittest.mock import patch

from agents.email.handler import _clean_subject, _save_email_items_as_draft


class TestCleanSubject:
    def test_strips_fwd_prefix(self):
        assert _clean_subject("Fwd: Paris trip") == "Paris trip"

    def test_strips_fw_prefix(self):
        assert _clean_subject("Fw: Paris trip") == "Paris trip"

    def test_strips_re_prefix(self):
        assert _clean_subject("Re: Paris trip") == "Paris trip"

    def test_strips_chained_prefixes(self):
        assert _clean_subject("Re: Fwd: Re: Paris trip") == "Paris trip"

    def test_case_insensitive(self):
        assert _clean_subject("FWD: Tokyo itinerary") == "Tokyo itinerary"

    def test_empty_after_strip_returns_fallback(self):
        assert _clean_subject("Re: ") == "Email trip"

    def test_no_prefix_unchanged(self):
        assert _clean_subject("Hotel confirmation") == "Hotel confirmation"


class TestSaveEmailItemsAsDraft:
    def _make_items(self):
        return [
            {
                "title": "Flight to JFK",
                "category": "flight",
                "date": "2026-09-15",
                "time": "08:00",
                "location": "JFK",
                "notes": "",
            },
            {
                "title": "Hotel check-in",
                "category": "hotel",
                "date": "2026-09-15",
                "time": None,
                "location": "NYC",
                "notes": "",
            },
            {
                "title": "Museum visit",
                "category": "activity",
                "date": None,
                "location": "MoMA",
                "notes": "",
            },
        ]

    def test_returns_trip_link_on_success(self):
        items = self._make_items()
        fake_trip = {"link": "paris_trip.html", "id": 1}

        with (
            patch(
                "agents.email.handler.db.create_draft_trip", return_value=fake_trip
            ) as mock_create,
            patch(
                "agents.email.handler.db.update_trip_itinerary_data", return_value=True
            ) as mock_update,
        ):
            link = _save_email_items_as_draft(42, "Fwd: Paris trip", items)

        assert link == "paris_trip.html"
        mock_create.assert_called_once_with(
            user_id=42,
            title="Paris trip",
            start_date="2026-09-15",
            end_date="2026-09-15",
        )
        # Verify itinerary_data structure passed to update
        call_args = mock_update.call_args
        itinerary_data = call_args[0][2]
        assert itinerary_data["title"] == "Paris trip"
        assert len(itinerary_data["days"]) == 1
        assert itinerary_data["days"][0]["date"] == "2026-09-15"
        assert len(itinerary_data["days"][0]["items"]) == 2
        assert len(itinerary_data["ideas"]) == 1
        assert itinerary_data["ideas"][0]["title"] == "Museum visit"

    def test_items_without_dates_go_into_ideas(self):
        items = [
            {"title": "Browse market", "category": "activity", "date": None, "location": ""},
        ]
        fake_trip = {"link": "email_trip.html", "id": 2}

        with (
            patch("agents.email.handler.db.create_draft_trip", return_value=fake_trip),
            patch(
                "agents.email.handler.db.update_trip_itinerary_data", return_value=True
            ) as mock_update,
        ):
            link = _save_email_items_as_draft(1, "some subject", items)

        assert link == "email_trip.html"
        itinerary_data = mock_update.call_args[0][2]
        assert itinerary_data["days"] == []
        assert len(itinerary_data["ideas"]) == 1
        assert itinerary_data["start_date"] is None

    def test_returns_none_when_create_fails(self):
        with patch("agents.email.handler.db.create_draft_trip", return_value=None):
            link = _save_email_items_as_draft(1, "subject", [{"title": "x", "date": "2026-01-01"}])
        assert link is None

    def test_days_sorted_chronologically(self):
        items = [
            {"title": "Day 2 event", "category": "activity", "date": "2026-09-16"},
            {"title": "Day 1 event", "category": "activity", "date": "2026-09-15"},
        ]
        fake_trip = {"link": "trip.html", "id": 3}

        with (
            patch("agents.email.handler.db.create_draft_trip", return_value=fake_trip),
            patch(
                "agents.email.handler.db.update_trip_itinerary_data", return_value=True
            ) as mock_update,
        ):
            _save_email_items_as_draft(1, "subject", items)

        itinerary_data = mock_update.call_args[0][2]
        assert itinerary_data["days"][0]["date"] == "2026-09-15"
        assert itinerary_data["days"][1]["date"] == "2026-09-16"
        assert itinerary_data["days"][0]["day_number"] == 1
        assert itinerary_data["days"][1]["day_number"] == 2
