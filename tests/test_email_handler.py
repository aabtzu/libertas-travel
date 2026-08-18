"""Tests for agents/email/handler.py - subject cleaning, draft-save, and routing."""

from __future__ import annotations

from unittest.mock import patch

from agents.email.handler import (
    _candidate_trips,
    _clean_subject,
    _extract_user_instruction,
    _match_by_dates,
    _merge_items_into_trip,
    _save_email_items_as_draft,
)


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


class TestExtractUserInstruction:
    def test_returns_text_above_marker(self):
        body = "Add to Tokyo trip\n---------- Forwarded message ---------\nFrom: someone"
        assert _extract_user_instruction(body) == "Add to Tokyo trip"

    def test_no_marker_returns_empty(self):
        body = "Just a plain email body with no forwarding."
        assert _extract_user_instruction(body) == ""

    def test_nothing_above_marker_returns_empty(self):
        body = "---------- Forwarded message ---------\nFrom: someone"
        assert _extract_user_instruction(body) == ""

    def test_multiline_instruction(self):
        body = "Please add this\nto the September trip\n-----Forwarded message-----\ncontent"
        result = _extract_user_instruction(body)
        assert "Please add this" in result
        assert "September trip" in result


class TestCandidateTrips:
    def _make_trip(self, title, end_date, is_archived=False, itinerary_data=None):
        return {
            "title": title,
            "link": f"{title.lower().replace(' ', '_')}.html",
            "is_archived": is_archived,
            "itinerary_data": itinerary_data or {"end_date": end_date, "start_date": end_date},
        }

    def test_excludes_archived_trips(self):
        trips = [
            self._make_trip("Active trip", "2027-01-01"),
            self._make_trip("Archived trip", "2027-01-01", is_archived=True),
        ]
        with patch("agents.email.handler.db.get_user_trips", return_value=trips):
            result = _candidate_trips(1)
        assert len(result) == 1
        assert result[0]["title"] == "Active trip"

    def test_excludes_old_trips(self):
        trips = [
            self._make_trip("Recent trip", "2026-09-01"),
            self._make_trip("Old trip", "2024-01-01"),  # over 180 days ago
        ]
        with patch("agents.email.handler.db.get_user_trips", return_value=trips):
            result = _candidate_trips(1)
        assert len(result) == 1
        assert result[0]["title"] == "Recent trip"

    def test_keeps_trips_with_no_end_date(self):
        trips = [self._make_trip("Undated trip", None, itinerary_data={})]
        with patch("agents.email.handler.db.get_user_trips", return_value=trips):
            result = _candidate_trips(1)
        assert len(result) == 1

    def test_parses_json_itinerary_data(self):
        import json

        trips = [
            {
                "title": "JSON trip",
                "link": "json_trip.html",
                "is_archived": False,
                "itinerary_data": json.dumps(
                    {"start_date": "2026-09-01", "end_date": "2026-09-10"}
                ),
            }
        ]
        with patch("agents.email.handler.db.get_user_trips", return_value=trips):
            result = _candidate_trips(1)
        assert len(result) == 1
        assert result[0]["itinerary_data"]["start_date"] == "2026-09-01"


class TestMatchByDates:
    def _trip(self, title, start, end):
        return {
            "title": title,
            "link": f"{title}.html",
            "itinerary_data": {"start_date": start, "end_date": end},
        }

    def test_matches_single_overlapping_trip(self):
        trips = [
            self._trip("Tokyo trip", "2026-09-10", "2026-09-20"),
            self._trip("Paris trip", "2026-10-01", "2026-10-10"),
        ]
        result = _match_by_dates(["2026-09-11"], trips)
        assert result is not None
        assert result["title"] == "Tokyo trip"

    def test_returns_none_when_multiple_match(self):
        trips = [
            self._trip("Trip A", "2026-09-01", "2026-09-30"),
            self._trip("Trip B", "2026-09-15", "2026-10-05"),
        ]
        result = _match_by_dates(["2026-09-20"], trips)
        assert result is None

    def test_returns_none_when_no_match(self):
        trips = [self._trip("Tokyo trip", "2026-09-10", "2026-09-20")]
        result = _match_by_dates(["2026-10-05"], trips)
        assert result is None

    def test_returns_none_for_empty_dates(self):
        trips = [self._trip("Tokyo trip", "2026-09-10", "2026-09-20")]
        assert _match_by_dates([], trips) is None


class TestMergeItemsIntoTrip:
    def _trip(self, existing_items_by_date=None, ideas=None):
        days = []
        for date_str, items in (existing_items_by_date or {}).items():
            days.append({"date": date_str, "day_number": len(days) + 1, "items": items})
        return {
            "link": "trip.html",
            "itinerary_data": {
                "start_date": "2026-09-10",
                "end_date": "2026-09-20",
                "days": days,
                "ideas": ideas or [],
            },
        }

    def test_appends_to_existing_day(self):
        trip = self._trip({"2026-09-15": [{"title": "Existing item"}]})
        new_item = {"title": "New flight", "date": "2026-09-15"}

        with patch(
            "agents.email.handler.db.update_trip_itinerary_data", return_value=True
        ) as mock_up:
            _merge_items_into_trip(1, trip, [new_item])

        itinerary = mock_up.call_args[0][2]
        day = itinerary["days"][0]
        assert len(day["items"]) == 2
        assert day["items"][1]["title"] == "New flight"

    def test_creates_new_day_for_new_date(self):
        trip = self._trip({"2026-09-15": [{"title": "Existing"}]})
        new_item = {"title": "New hotel", "date": "2026-09-16"}

        with patch(
            "agents.email.handler.db.update_trip_itinerary_data", return_value=True
        ) as mock_up:
            _merge_items_into_trip(1, trip, [new_item])

        itinerary = mock_up.call_args[0][2]
        assert len(itinerary["days"]) == 2
        dates = [d["date"] for d in itinerary["days"]]
        assert "2026-09-16" in dates

    def test_undated_items_go_to_ideas(self):
        trip = self._trip()
        new_item = {"title": "Restaurant idea", "date": None}

        with patch(
            "agents.email.handler.db.update_trip_itinerary_data", return_value=True
        ) as mock_up:
            _merge_items_into_trip(1, trip, [new_item])

        itinerary = mock_up.call_args[0][2]
        assert len(itinerary["ideas"]) == 1
        assert itinerary["ideas"][0]["title"] == "Restaurant idea"

    def test_days_renumbered_after_merge(self):
        trip = self._trip({"2026-09-15": [], "2026-09-17": []})
        new_item = {"title": "New item", "date": "2026-09-16"}

        with patch(
            "agents.email.handler.db.update_trip_itinerary_data", return_value=True
        ) as mock_up:
            _merge_items_into_trip(1, trip, [new_item])

        itinerary = mock_up.call_args[0][2]
        for idx, day in enumerate(itinerary["days"]):
            assert day["day_number"] == idx + 1


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
            user_id=42, title="Paris trip", start_date="2026-09-15", end_date="2026-09-15"
        )
        itinerary_data = mock_update.call_args[0][2]
        assert itinerary_data["title"] == "Paris trip"
        assert len(itinerary_data["days"]) == 1
        assert len(itinerary_data["days"][0]["items"]) == 2
        assert len(itinerary_data["ideas"]) == 1

    def test_items_without_dates_go_into_ideas(self):
        items = [{"title": "Browse market", "category": "activity", "date": None, "location": ""}]
        fake_trip = {"link": "email_trip.html", "id": 2}

        with (
            patch("agents.email.handler.db.create_draft_trip", return_value=fake_trip),
            patch(
                "agents.email.handler.db.update_trip_itinerary_data", return_value=True
            ) as mock_update,
        ):
            _save_email_items_as_draft(1, "some subject", items)

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
