"""Tests for the archive-trip feature (issue #35).

Archive is a flag independent of is_public, an archived trip can still
be public/recommendable. Archived trips are hidden from the main grid
on the trips page, but remain visible on the map view.
"""

from __future__ import annotations


def _add_trip(link: str, title: str = "Archive Test Trip", **extra) -> None:
    """Helper: insert a minimal trip owned by user 1."""
    import database as db

    trip_data = {"title": title, "link": link, **extra}
    itinerary_data = {
        "ideas": [],
        "days": [
            {
                "day": 1,
                "items": [{"title": "Arrive", "category": "transport", "location": "Boston, MA"}],
            }
        ],
        "tips": [],
    }
    db.add_trip(1, trip_data, itinerary_data)


# ---------------------------------------------------------------------------
# DB layer: set_trip_archived
# ---------------------------------------------------------------------------


class TestSetTripArchived:
    def test_default_is_unarchived(self, client):
        import database as db

        link = "archive_default_test.html"
        _add_trip(link)
        try:
            trip = db.get_trip_by_link(1, link)
            assert bool(trip.get("is_archived")) is False
        finally:
            db.delete_trip(1, link)

    def test_archive_then_unarchive_roundtrip(self, client):
        import database as db

        link = "archive_roundtrip_test.html"
        _add_trip(link)
        try:
            assert db.set_trip_archived(1, link, True) is True
            assert bool(db.get_trip_by_link(1, link).get("is_archived")) is True

            assert db.set_trip_archived(1, link, False) is True
            assert bool(db.get_trip_by_link(1, link).get("is_archived")) is False
        finally:
            db.delete_trip(1, link)

    def test_archive_unknown_trip_returns_false(self, client):
        import database as db

        # No row matches → 0 rows updated → False (route uses this to 404)
        assert db.set_trip_archived(1, "does_not_exist.html", True) is False


# ---------------------------------------------------------------------------
# API: POST /api/toggle-archived
# ---------------------------------------------------------------------------


class TestToggleArchivedEndpoint:
    def test_toggle_archived_success(self, client):
        import database as db

        link = "archive_api_test.html"
        _add_trip(link)
        try:
            resp = client.post("/api/toggle-archived", json={"link": link, "isArchived": True})
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["success"] is True
            assert data["isArchived"] is True

            # State persisted
            assert bool(db.get_trip_by_link(1, link).get("is_archived")) is True
        finally:
            db.delete_trip(1, link)

    def test_toggle_archived_missing_link(self, client):
        resp = client.post("/api/toggle-archived", json={"isArchived": True})
        assert resp.status_code in (400, 200)
        # json_err returns 200 in this codebase but with success=False
        body = resp.get_json()
        assert body.get("success") is not True

    def test_toggle_archived_unknown_trip(self, client):
        resp = client.post(
            "/api/toggle-archived",
            json={"link": "totally_made_up_xyz.html", "isArchived": True},
        )
        body = resp.get_json()
        assert body.get("success") is not True


# ---------------------------------------------------------------------------
# Trips page: archived trips render in their own section, not the main grid
# ---------------------------------------------------------------------------


class TestTripsPageArchivedSection:
    def test_active_and_archived_trips_render_in_separate_sections(self, client):
        import database as db

        active_link = "archive_active_render.html"
        archived_link = "archive_archived_render.html"
        _add_trip(active_link, title="Active Render Test")
        _add_trip(archived_link, title="Archived Render Test")
        db.set_trip_archived(1, archived_link, True)
        try:
            resp = client.get("/trips.html")
            assert resp.status_code == 200
            body = resp.get_data(as_text=True)

            # Both cards present in the page
            assert active_link in body
            assert archived_link in body

            # The archived section + toggle button only appear when there's archived content
            assert 'id="archived-section"' in body
            assert "show-archived-btn" in body

            # Quick locator: the archived section must contain the archived link,
            # and the active grid (#trips-container) must contain only the active link.
            archived_idx = body.find('id="archived-section"')
            container_idx = body.find('id="trips-container"')
            assert archived_idx > -1 and container_idx > -1

            # Find approximate end of trips-container (next major section)
            # Archived link should appear AFTER archived-section starts
            assert body.find(archived_link) > archived_idx
            # Active link should appear AFTER trips-container starts but BEFORE archived-section
            active_pos = body.find(active_link)
            assert container_idx < active_pos < archived_idx
        finally:
            db.delete_trip(1, active_link)
            db.delete_trip(1, archived_link)

    def test_archived_section_always_rendered(self, client):
        """The archived section + toggle are always rendered so JS has a
        target when the user archives their first trip. Visibility (the
        `hidden` attribute) is managed client-side based on count."""
        import database as db

        link = "archive_none_test.html"
        _add_trip(link)
        try:
            resp = client.get("/trips.html")
            body = resp.get_data(as_text=True)
            assert 'id="archived-section"' in body
            assert 'id="show-archived-btn"' in body
        finally:
            db.delete_trip(1, link)
