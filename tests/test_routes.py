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
        resp = client.post(
            "/api/trips/create",
            json={"title": "Test Trip", "days": 3},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get("trip", {}).get("link") or data.get("link")

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
        link = self._create_trip(client)
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

    def test_add_idea_no_item(self, client):
        link = self._create_trip(client)
        resp = client.post(f"/api/trips/{link}/items", json={})
        assert resp.status_code == 400

    def test_add_idea_no_title(self, client):
        link = self._create_trip(client)
        resp = client.post(
            f"/api/trips/{link}/items",
            json={"item": {"category": "meal"}},
        )
        assert resp.status_code == 400


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
                        "name": "Test Venue XYZ",
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
