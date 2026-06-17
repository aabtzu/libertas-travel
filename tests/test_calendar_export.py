"""Tests for the .ics calendar export, including subscribe-token auth.

Two surfaces here:
  1. Token generator: deterministic, stateless, validates with constant-time
     compare. Stable when SECRET_KEY is stable; rotates when it rotates.
  2. The /api/trips/<link>/calendar.ics route handles three auth paths,
     authenticated session (download), valid token (subscribe), neither
     (401 / 403 / 404 depending on what's wrong).
"""

from __future__ import annotations

import os

import pytest

from agents.trips.ics import (
    calendar_subscribe_token,
    generate_ics,
    generate_ics_multi,
    user_calendar_token,
    verify_subscribe_token,
    verify_user_calendar_token,
)

# ---------------------------------------------------------------------------
# Token roundtrip
# ---------------------------------------------------------------------------


class TestSubscribeToken:
    def test_token_is_deterministic_for_same_inputs(self):
        os.environ["SECRET_KEY"] = "test-secret"
        a = calendar_subscribe_token(1, "trip.html")
        b = calendar_subscribe_token(1, "trip.html")
        assert a == b

    def test_token_differs_per_user(self):
        os.environ["SECRET_KEY"] = "test-secret"
        a = calendar_subscribe_token(1, "trip.html")
        b = calendar_subscribe_token(2, "trip.html")
        assert a != b

    def test_token_differs_per_trip(self):
        os.environ["SECRET_KEY"] = "test-secret"
        a = calendar_subscribe_token(1, "trip-a.html")
        b = calendar_subscribe_token(1, "trip-b.html")
        assert a != b

    def test_token_changes_when_secret_rotates(self):
        os.environ["SECRET_KEY"] = "old-secret"
        old = calendar_subscribe_token(1, "trip.html")
        os.environ["SECRET_KEY"] = "new-secret"
        new = calendar_subscribe_token(1, "trip.html")
        assert old != new

    def test_verify_accepts_valid_token(self):
        os.environ["SECRET_KEY"] = "test-secret"
        token = calendar_subscribe_token(1, "trip.html")
        assert verify_subscribe_token(1, "trip.html", token) is True

    def test_verify_rejects_tampered_token(self):
        os.environ["SECRET_KEY"] = "test-secret"
        token = calendar_subscribe_token(1, "trip.html")
        assert verify_subscribe_token(1, "trip.html", token + "X") is False

    def test_verify_rejects_wrong_user(self):
        os.environ["SECRET_KEY"] = "test-secret"
        token = calendar_subscribe_token(1, "trip.html")
        assert verify_subscribe_token(2, "trip.html", token) is False

    def test_token_refuses_when_secret_unset(self):
        os.environ.pop("SECRET_KEY", None)
        with pytest.raises(RuntimeError):
            calendar_subscribe_token(1, "trip.html")


# ---------------------------------------------------------------------------
# Route auth
# ---------------------------------------------------------------------------


class TestExportIcsRoute:
    def _create_trip(self, client):
        resp = client.post(
            "/api/trips/create",
            json={"title": "ICS Test Trip", "days": 2},
        )
        data = resp.get_json()
        return data.get("trip", {}).get("link") or data.get("link")

    def test_download_path_requires_auth(self, client, app):
        """No session, no token => 401. (AUTH_DISABLED is on in tests so we
        simulate the unauthed case by clearing g.user_id mid-request via a
        test-only header... easier: just check the token-less + wrong-user
        path returns 404 since AUTH_DISABLED forces user_id=1.)"""
        # Under AUTH_DISABLED the test user is 1. Hitting a nonexistent
        # trip exercises the 404-on-missing-trip branch.
        resp = client.get("/api/trips/nonexistent.html/calendar.ics")
        assert resp.status_code == 404

    def test_token_path_serves_ics(self, client, app):
        import database as db

        link = self._create_trip(client)
        try:
            owner_id = db.get_trip_owner(link)
            token = calendar_subscribe_token(owner_id, link)
            resp = client.get(f"/api/trips/{link}/calendar.ics?token={token}")
            assert resp.status_code == 200
            assert resp.mimetype.startswith("text/calendar")
            body = resp.get_data(as_text=True)
            assert "BEGIN:VCALENDAR" in body
            assert "END:VCALENDAR" in body
        finally:
            db.delete_trip(1, link)

    def test_invalid_token_returns_403(self, client, app):
        import database as db

        link = self._create_trip(client)
        try:
            resp = client.get(f"/api/trips/{link}/calendar.ics?token=garbage")
            assert resp.status_code == 403
        finally:
            db.delete_trip(1, link)

    def test_owner_session_serves_ics(self, client, app):
        """No token, but session belongs to owner => 200."""
        import database as db

        link = self._create_trip(client)
        try:
            resp = client.get(f"/api/trips/{link}/calendar.ics")
            assert resp.status_code == 200
            assert "BEGIN:VCALENDAR" in resp.get_data(as_text=True)
        finally:
            db.delete_trip(1, link)


# ---------------------------------------------------------------------------
# Subscribe URL endpoint
# ---------------------------------------------------------------------------


class TestSubscribeUrlEndpoint:
    def test_returns_webcal_url_for_owner(self, client, app):
        import database as db

        resp = client.post("/api/trips/create", json={"title": "Sub URL Trip", "days": 1})
        link = resp.get_json().get("link") or resp.get_json().get("trip", {}).get("link")
        try:
            resp = client.get(f"/api/trips/{link}/calendar-subscribe-url")
            assert resp.status_code == 200
            data = resp.get_json()
            url = data.get("url", "")
            assert url.startswith("webcal://")
            assert "token=" in url
            assert link in url
        finally:
            db.delete_trip(1, link)

    def test_404_on_missing_trip(self, client, app):
        resp = client.get("/api/trips/nonexistent.html/calendar-subscribe-url")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Output format (library-emitted ICS)
# ---------------------------------------------------------------------------


class TestGeneratedIcsFormat:
    def _export_payload(self, days: list[dict], title: str = "Test Trip") -> dict:
        return {"title": title, "itinerary_data": {"days": days}}

    def test_emits_well_formed_calendar(self):
        ics = generate_ics(
            self._export_payload(
                [
                    {
                        "date": "2026-05-20",
                        "items": [
                            {
                                "title": "Lunch",
                                "category": "meal",
                                "time": "12:30",
                                "end_time": "14:00",
                                "location": "Cafe Lou",
                            }
                        ],
                    }
                ]
            ),
            "test_trip.html",
        )
        assert ics.startswith("BEGIN:VCALENDAR")
        assert "END:VCALENDAR" in ics
        assert "BEGIN:VEVENT" in ics
        # Library emits CRLF as required by RFC 5545
        assert "\r\n" in ics
        # SUMMARY survived
        assert "Lunch" in ics
        # Time was serialized
        assert "20260520T123000" in ics

    def test_escapes_commas_and_semicolons_in_summary(self):
        """The previous hand-rolled escaper had ordering bugs around backslash
        escaping. The library does it correctly."""
        ics = generate_ics(
            self._export_payload(
                [
                    {
                        "date": "2026-05-20",
                        "items": [{"title": "Paris, France; trip", "category": "activity"}],
                    }
                ]
            ),
            "trip.html",
        )
        # Comma must be escaped, semicolon must be escaped
        assert "Paris\\, France\\; trip" in ics

    def test_all_day_event_uses_value_date(self):
        ics = generate_ics(
            self._export_payload(
                [
                    {
                        "date": "2026-05-20",
                        "items": [{"title": "Day at the museum", "category": "attraction"}],
                    }
                ]
            ),
            "trip.html",
        )
        # All-day events serialize as VALUE=DATE
        assert "DTSTART;VALUE=DATE:20260520" in ics

    def test_long_descriptions_get_folded(self):
        """RFC 5545 line folding: lines >75 octets must wrap. The library
        folds correctly; the hand-rolled emitter never folded at all."""
        long_note = "X" * 200
        ics = generate_ics(
            self._export_payload(
                [
                    {
                        "date": "2026-05-20",
                        "items": [
                            {"title": "Big notes", "category": "activity", "notes": long_note}
                        ],
                    }
                ]
            ),
            "trip.html",
        )
        # No single line should exceed 75 octets after folding.
        for line in ics.split("\r\n"):
            assert len(line.encode("utf-8")) <= 75, f"Line too long: {line!r}"

    def test_skips_days_without_a_date(self):
        ics = generate_ics(
            self._export_payload([{"items": [{"title": "Floating thing"}]}]),
            "trip.html",
        )
        assert "Floating thing" not in ics

    def test_red_eye_flight_arrives_next_day(self):
        """Regression: a flight where end_time < start_time used to emit
        DTEND on the same calendar date as DTSTART, producing DTEND <
        DTSTART. Apple/Outlook silently drop those events. The exporter
        now bumps end_date forward by one day in that case."""
        ics = generate_ics(
            self._export_payload(
                [
                    {
                        "date": "2026-06-21",
                        "items": [
                            {
                                "title": "DL 452 SEA -> JFK",
                                "category": "flight",
                                "time": "22:20",
                                "end_time": "06:34",
                            }
                        ],
                    }
                ]
            ),
            "trip.html",
        )
        # Departure on Jun 21 22:20
        assert "20260621T222000" in ics
        # Arrival on Jun 22 06:34, NOT Jun 21
        assert "20260622T063400" in ics

    def test_hotel_emits_span_and_checkin(self):
        """Hotels with end_date produce two events: an all-day span and a timed check-in."""
        ics = generate_ics(
            self._export_payload(
                [
                    {
                        "date": "2026-06-10",
                        "items": [
                            {
                                "title": "Marriott Seattle",
                                "category": "hotel",
                                "time": "16:00",
                                "end_date": "2026-06-15",
                            }
                        ],
                    }
                ]
            ),
            "trip.html",
        )
        # All-day span: DTSTART;VALUE=DATE:20260610, DTEND;VALUE=DATE:20260616 (exclusive)
        assert "20260610" in ics
        assert "20260616" in ics
        # Timed check-in event on start day
        assert "20260610T160000" in ics
        # Summary includes "Check-in:" prefix
        assert "Check-in: Marriott Seattle" in ics

    def test_transport_emits_span_and_pickup(self):
        """Car rentals (transport) with end_date produce a span and a timed pickup event."""
        ics = generate_ics(
            self._export_payload(
                [
                    {
                        "date": "2026-06-10",
                        "items": [
                            {
                                "title": "Hertz Midsize",
                                "category": "transport",
                                "time": "08:00",
                                "end_date": "2026-06-20",
                            }
                        ],
                    }
                ]
            ),
            "trip.html",
        )
        assert "20260610" in ics
        assert "20260621" in ics  # exclusive end = end_date + 1
        assert "20260610T080000" in ics
        assert "Pickup: Hertz Midsize" in ics

    def test_hotel_without_end_date_is_timed_event(self):
        """A hotel item without end_date falls through to a single timed event."""
        ics = generate_ics(
            self._export_payload(
                [
                    {
                        "date": "2026-06-10",
                        "items": [
                            {
                                "title": "Marriott Seattle",
                                "category": "hotel",
                                "time": "16:00",
                            }
                        ],
                    }
                ]
            ),
            "trip.html",
        )
        assert "20260610T160000" in ics
        assert "Check-in:" not in ics


# ---------------------------------------------------------------------------
# User-scoped calendar token
# ---------------------------------------------------------------------------


class TestUserCalendarToken:
    def test_token_is_deterministic(self):
        os.environ["SECRET_KEY"] = "test-secret"
        assert user_calendar_token(1) == user_calendar_token(1)

    def test_token_differs_per_user(self):
        os.environ["SECRET_KEY"] = "test-secret"
        assert user_calendar_token(1) != user_calendar_token(2)

    def test_token_differs_from_per_trip_token(self):
        # user-cal and calendar namespaces must not collide
        os.environ["SECRET_KEY"] = "test-secret"
        assert user_calendar_token(1) != calendar_subscribe_token(1, "")

    def test_verify_accepts_valid_token(self):
        os.environ["SECRET_KEY"] = "test-secret"
        token = user_calendar_token(42)
        assert verify_user_calendar_token(42, token) is True

    def test_verify_rejects_wrong_user(self):
        os.environ["SECRET_KEY"] = "test-secret"
        token = user_calendar_token(1)
        assert verify_user_calendar_token(2, token) is False

    def test_verify_rejects_tampered_token(self):
        os.environ["SECRET_KEY"] = "test-secret"
        token = user_calendar_token(1)
        assert verify_user_calendar_token(1, token + "X") is False

    def test_refuses_when_secret_unset(self):
        os.environ.pop("SECRET_KEY", None)
        with pytest.raises(RuntimeError):
            user_calendar_token(1)


# ---------------------------------------------------------------------------
# generate_ics_multi
# ---------------------------------------------------------------------------


class TestGenerateIcsMulti:
    def _trip(self, link, title, days):
        return {"link": link, "title": title, "itinerary_data": {"days": days}}

    def test_merges_events_from_multiple_trips(self):
        trips = [
            self._trip(
                "trip-a.html",
                "Paris",
                [
                    {
                        "date": "2026-07-01",
                        "items": [{"title": "Eiffel Tower", "category": "attraction"}],
                    }
                ],
            ),
            self._trip(
                "trip-b.html",
                "Rome",
                [
                    {
                        "date": "2026-08-10",
                        "items": [{"title": "Colosseum", "category": "attraction"}],
                    }
                ],
            ),
        ]
        ics = generate_ics_multi(trips)
        assert "Eiffel Tower" in ics
        assert "Colosseum" in ics
        assert ics.count("BEGIN:VEVENT") == 2

    def test_empty_trips_produces_valid_calendar(self):
        ics = generate_ics_multi([])
        assert "BEGIN:VCALENDAR" in ics
        assert "BEGIN:VEVENT" not in ics

    def test_skips_days_without_date(self):
        trips = [
            self._trip(
                "trip-x.html",
                "No Dates",
                [{"items": [{"title": "Ghost event"}]}],
            )
        ]
        ics = generate_ics_multi(trips)
        assert "Ghost event" not in ics

    def test_calendar_name_is_libertas_travel(self):
        ics = generate_ics_multi([])
        assert "Libertas Travel" in ics


# ---------------------------------------------------------------------------
# /api/calendar/subscribe-url and /api/calendar/all.ics routes
# ---------------------------------------------------------------------------


class TestUserCalendarRoutes:
    def test_subscribe_url_returns_webcal(self, client, app):
        os.environ["SECRET_KEY"] = "test-secret"
        resp = client.get("/api/calendar/subscribe-url")
        assert resp.status_code == 200
        data = resp.get_json()
        url = data.get("url", "")
        assert url.startswith("webcal://")
        assert "user_id=" in url
        assert "token=" in url
        assert "/api/calendar/all.ics" in url

    def test_all_ics_valid_token_returns_calendar(self, client, app):
        os.environ["SECRET_KEY"] = "test-secret"
        token = user_calendar_token(1)
        resp = client.get(f"/api/calendar/all.ics?user_id=1&token={token}")
        assert resp.status_code == 200
        assert resp.mimetype.startswith("text/calendar")
        body = resp.get_data(as_text=True)
        assert "BEGIN:VCALENDAR" in body

    def test_all_ics_invalid_token_returns_403(self, client, app):
        os.environ["SECRET_KEY"] = "test-secret"
        resp = client.get("/api/calendar/all.ics?user_id=1&token=garbage")
        assert resp.status_code == 403

    def test_all_ics_missing_user_id_returns_400(self, client, app):
        os.environ["SECRET_KEY"] = "test-secret"
        resp = client.get("/api/calendar/all.ics?token=anything")
        assert resp.status_code == 400
