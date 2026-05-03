"""Tests for trip and admin route endpoints."""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Trips list
# ---------------------------------------------------------------------------


class TestTripsListRoute:
    def test_returns_trips_list(self, client):
        resp = client.get("/api/trips/list")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "trips" in data
        assert isinstance(data["trips"], list)

    def test_each_trip_has_link_and_title(self, client):
        resp = client.get("/api/trips/list")
        data = resp.get_json()
        for trip in data["trips"]:
            assert "link" in trip
            assert "title" in trip


# ---------------------------------------------------------------------------
# Trip CRUD
# ---------------------------------------------------------------------------


class TestTripCRUD:
    def test_create_trip(self, client):
        import database as db

        resp = client.post(
            "/api/trips/create",
            json={"title": "Test Trip", "days": 3},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        link = data.get("trip", {}).get("link") or data.get("link")
        assert link
        db.delete_trip(1, link)

    def test_create_trip_missing_title(self, client):
        resp = client.post("/api/trips/create", json={"days": 3})
        assert resp.status_code in (400, 200)

    def test_delete_trip(self, client):
        # Create then delete
        resp = client.post(
            "/api/trips/create",
            json={"title": "Delete Me", "days": 1},
        )
        data = resp.get_json()
        link = data.get("trip", {}).get("link") or data.get("link", "")
        resp = client.post("/api/delete-trip", json={"link": link})
        assert resp.status_code == 200

    def test_delete_nonexistent_trip(self, client):
        resp = client.post("/api/delete-trip", json={"link": "nonexistent.html"})
        assert resp.status_code in (200, 400, 404)


# ---------------------------------------------------------------------------
# Add idea to trip
# ---------------------------------------------------------------------------


class TestAddIdeaToTrip:
    def _create_trip(self, client):
        resp = client.post(
            "/api/trips/create",
            json={"title": "Idea Test Trip", "days": 2},
        )
        data = resp.get_json()
        return data.get("trip", {}).get("link") or data.get("link", "")

    def test_add_idea_success(self, client):
        import database as db

        link = self._create_trip(client)
        try:
            resp = client.post(
                f"/api/trips/{link}/items",
                json={
                    "item": {
                        "title": "Cafe La Trova",
                        "category": "meal",
                        "location": "Miami, FL",
                    }
                },
            )
            assert resp.status_code == 200
            assert resp.get_json().get("success") is True
        finally:
            db.delete_trip(1, link)

    def test_add_idea_no_item(self, client):
        import database as db

        link = self._create_trip(client)
        try:
            resp = client.post(f"/api/trips/{link}/items", json={})
            assert resp.status_code == 400
        finally:
            db.delete_trip(1, link)

    def test_add_idea_no_title(self, client):
        import database as db

        link = self._create_trip(client)
        try:
            resp = client.post(
                f"/api/trips/{link}/items",
                json={"item": {"category": "meal"}},
            )
            assert resp.status_code == 400
        finally:
            db.delete_trip(1, link)


# ---------------------------------------------------------------------------
# Admin endpoints — auth check
# ---------------------------------------------------------------------------


class TestAdminAuth:
    def test_seed_no_key_returns_401(self, client):
        resp = client.post("/api/admin/seed")
        assert resp.status_code == 401

    def test_seed_wrong_key_returns_401(self, client):
        resp = client.post(
            "/api/admin/seed",
            headers={"X-Admin-Key": "wrong"},
        )
        assert resp.status_code == 401

    def test_retry_geocoding_no_key_returns_401(self, client):
        resp = client.post(
            "/api/admin/retry-geocoding",
            json={"link": "test.html"},
        )
        assert resp.status_code == 401

    def test_add_venues_no_key_returns_401(self, client):
        resp = client.post(
            "/api/admin/add-venues",
            json={"venues": []},
        )
        assert resp.status_code == 401

    def test_delete_user_no_key_returns_401(self, client):
        resp = client.post("/api/admin/delete-user", json={"username": "x"})
        assert resp.status_code == 401

    def test_delete_trip_no_key_returns_401(self, client):
        resp = client.post("/api/admin/delete-trip", json={"username": "x", "link": "y.html"})
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Admin endpoints — with valid key
# ---------------------------------------------------------------------------


class TestAdminEndpoints:
    HEADERS = {"X-Admin-Key": "test-secret"}

    def test_retry_geocoding_missing_link(self, client):
        resp = client.post(
            "/api/admin/retry-geocoding",
            headers=self.HEADERS,
            json={},
        )
        assert resp.status_code == 400

    def test_retry_geocoding_nonexistent_trip(self, client):
        resp = client.post(
            "/api/admin/retry-geocoding",
            headers=self.HEADERS,
            json={"link": "nonexistent.html"},
        )
        data = resp.get_json()
        assert data.get("success") is False

    def test_add_venues_empty_list(self, client):
        resp = client.post(
            "/api/admin/add-venues",
            headers=self.HEADERS,
            json={"venues": []},
        )
        assert resp.status_code == 400

    def test_add_venues_success(self, client):
        resp = client.post(
            "/api/admin/add-venues",
            headers=self.HEADERS,
            json={
                "venues": [
                    {
                        "name": f"Test Venue {id(self)}",
                        "venue_type": "Restaurant",
                        "city": "Test City",
                        "country": "US",
                    }
                ]
            },
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["added"] == 1

    def test_add_venues_skips_duplicates(self, client):
        venue = {
            "name": "Duplicate Venue ABC",
            "venue_type": "Restaurant",
            "city": "Test City",
            "country": "US",
        }
        # Add once
        client.post(
            "/api/admin/add-venues",
            headers=self.HEADERS,
            json={"venues": [venue]},
        )
        # Add again
        resp = client.post(
            "/api/admin/add-venues",
            headers=self.HEADERS,
            json={"venues": [venue]},
        )
        data = resp.get_json()
        assert data["skipped"] == 1
        assert data["added"] == 0

    def test_delete_user_missing_username(self, client):
        resp = client.post(
            "/api/admin/delete-user",
            headers=self.HEADERS,
            json={},
        )
        assert resp.status_code in (200, 400)
        assert resp.get_json().get("success") is not True

    def test_delete_user_unknown_returns_404(self, client):
        resp = client.post(
            "/api/admin/delete-user",
            headers=self.HEADERS,
            json={"username": "definitely_not_a_real_user_12345"},
        )
        assert resp.status_code == 404

    def test_delete_user_refuses_demo_user(self, client):
        resp = client.post(
            "/api/admin/delete-user",
            headers=self.HEADERS,
            json={"username": "demo"},
        )
        assert resp.status_code == 400
        body = resp.get_json()
        assert body.get("success") is not True

    def test_delete_trip_round_trip(self, client):
        """Create a user + trip, delete via the admin endpoint, verify gone."""
        import database as db

        username = "trip_owner_for_delete"
        link = "doomed_trip_for_admin_delete.html"
        db.delete_user_by_username(username)  # cleanup any prior run

        user_id = db.create_user(username, f"{username}@test.local", "pw1234")
        assert user_id is not None
        db.add_trip(user_id, {"title": "Doomed", "link": link}, {"days": [], "ideas": []})
        assert db.get_trip_by_link(user_id, link) is not None

        try:
            resp = client.post(
                "/api/admin/delete-trip",
                headers=self.HEADERS,
                json={"username": username, "link": link},
            )
            assert resp.status_code == 200
            assert resp.get_json()["success"] is True
            assert db.get_trip_by_link(user_id, link) is None

            # Re-deleting same trip yields 404
            resp = client.post(
                "/api/admin/delete-trip",
                headers=self.HEADERS,
                json={"username": username, "link": link},
            )
            assert resp.status_code == 404
        finally:
            db.delete_user_by_username(username)

    def test_delete_trip_unknown_user(self, client):
        resp = client.post(
            "/api/admin/delete-trip",
            headers=self.HEADERS,
            json={"username": "no_such_user_xyz", "link": "anything.html"},
        )
        assert resp.status_code == 404

    def test_delete_trip_missing_fields(self, client):
        resp = client.post(
            "/api/admin/delete-trip",
            headers=self.HEADERS,
            json={"username": "x"},  # no link
        )
        assert resp.get_json().get("success") is not True

    def test_delete_user_round_trip(self, client):
        """Create a throw-away user, delete it via the admin endpoint,
        verify it's gone. Also confirms FK CASCADE wipes the user's trips."""
        import database as db

        username = "deleteme_round_trip"
        # Clean up first in case a prior failed run left it behind
        db.delete_user_by_username(username)

        user_id = db.create_user(username, f"{username}@test.local", "pw1234")
        assert user_id is not None

        # Create a trip owned by this user — must vanish on cascade delete
        link = "delete_round_trip_test.html"
        db.add_trip(user_id, {"title": "Doomed Trip", "link": link}, {"days": [], "ideas": []})
        assert db.get_trip_by_link(user_id, link) is not None

        try:
            resp = client.post(
                "/api/admin/delete-user",
                headers=self.HEADERS,
                json={"username": username},
            )
            assert resp.status_code == 200
            assert resp.get_json()["success"] is True

            # User and their trip should both be gone
            assert db.get_user_by_username(username) is None
            assert db.get_trip_by_link(user_id, link) is None
        finally:
            # Defensive: in case the test failed mid-way
            db.delete_user_by_username(username)


# ---------------------------------------------------------------------------
# Explore page
# ---------------------------------------------------------------------------


class TestExplorePage:
    def test_explore_page_loads(self, client):
        resp = client.get("/explore.html")
        assert resp.status_code == 200
        assert b"Explore" in resp.data

    def test_explore_chat_no_message(self, client):
        resp = client.post(
            "/api/explore/chat",
            json={"history": []},
        )
        # Should handle gracefully (400 or empty response)
        assert resp.status_code in (200, 400)


# ---------------------------------------------------------------------------
# Venue database operations
# ---------------------------------------------------------------------------


class TestVenueDB:
    def test_search_venues(self):
        import database as db

        results = db.search_venues("restaurant")
        assert isinstance(results, list)

    def test_find_venue_by_name_and_city(self):
        import database as db

        # Add a venue first
        db.add_venue(
            {
                "name": "Find Me Cafe",
                "venue_type": "Cafe",
                "city": "Testville",
                "country": "US",
            }
        )
        result = db.find_venue_by_name_and_city("Find Me Cafe", "Testville")
        assert result is not None
        assert result["name"] == "Find Me Cafe"

    def test_find_nonexistent_venue(self):
        import database as db

        result = db.find_venue_by_name_and_city("No Such Place", "Nowhere")
        assert result is None
