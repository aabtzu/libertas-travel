"""Tests for trip recommendations: city extraction, markdown, routes."""

from __future__ import annotations

from agents.pages.recommendation_view import _extract_city, _md_to_html

# ---------------------------------------------------------------------------
# City extraction from location strings
# ---------------------------------------------------------------------------


class TestExtractCity:
    def test_venue_city_country(self):
        assert _extract_city("Plaza Mayor, Madrid, Spain") == "Madrid"

    def test_city_country(self):
        assert _extract_city("Madrid, Spain") == "Madrid"

    def test_city_only(self):
        assert _extract_city("Seville") == "Seville"

    def test_empty_string(self):
        assert _extract_city("") == "Other"

    def test_none(self):
        assert _extract_city(None) == "Other"

    def test_city_state(self):
        assert _extract_city("Jackson, NH") == "Jackson"

    def test_venue_city_state_country(self):
        assert _extract_city("Alhambra, Granada, Spain") == "Granada"

    def test_long_venue_name(self):
        assert _extract_city("Mosque-Cathedral of Córdoba, Córdoba, Spain") == "Córdoba"

    def test_paris_france(self):
        assert _extract_city("Café de Flore, Paris, France") == "Paris"


# ---------------------------------------------------------------------------
# Markdown to HTML rendering
# ---------------------------------------------------------------------------


class TestMdToHtml:
    def test_bold(self):
        result = _md_to_html("**hello**")
        assert "<strong>hello</strong>" in result

    def test_italic(self):
        result = _md_to_html("*hello*")
        assert "<em>hello</em>" in result

    def test_h1(self):
        result = _md_to_html("# Title")
        assert "<h1>Title</h1>" in result

    def test_h2(self):
        result = _md_to_html("## Section")
        assert "<h2>Section</h2>" in result

    def test_h3(self):
        result = _md_to_html("### Subsection")
        assert "<h3>Subsection</h3>" in result

    def test_link(self):
        result = _md_to_html("[click](https://example.com)")
        assert 'href="https://example.com"' in result
        assert ">click</a>" in result

    def test_paragraph_break(self):
        result = _md_to_html("first\n\nsecond")
        assert "</p><p>" in result

    def test_line_break(self):
        result = _md_to_html("first\nsecond")
        assert "<br>" in result

    def test_html_escaped(self):
        result = _md_to_html("<script>alert('xss')</script>")
        assert "<script>" not in result
        assert "&lt;script&gt;" in result

    def test_combined(self):
        result = _md_to_html(
            "## Jackson\n\n**White Mountain Cider** — great [dinner](https://example.com)"
        )
        assert "<h2>Jackson</h2>" in result
        assert "<strong>White Mountain Cider</strong>" in result
        assert 'href="https://example.com"' in result


# ---------------------------------------------------------------------------
# Recommendation routes
# ---------------------------------------------------------------------------


class TestRecommendationRoutes:
    def test_r_page_404_for_nonexistent(self, client):
        resp = client.get("/r/nonexistent")
        assert resp.status_code == 404

    def test_w_page_404_for_nonexistent(self, client):
        resp = client.get("/w/nonexistent")
        assert resp.status_code == 404

    def test_clone_ideas_missing_params(self, client):
        resp = client.post("/api/trips/clone-ideas", json={})
        assert resp.status_code == 400

    def test_clone_ideas_nonexistent_source(self, client):
        resp = client.post(
            "/api/trips/clone-ideas",
            json={"source_link": "ghost.html", "target_link": "ghost2.html"},
        )
        assert resp.status_code in (200, 400, 404)
        data = resp.get_json()
        assert data.get("success") is not True

    def test_writeup_nonexistent_trip(self, client):
        resp = client.post("/api/trips/ghost.html/writeup")
        assert resp.status_code in (200, 400, 404)

    def test_fill_links_nonexistent_trip(self, client):
        resp = client.post("/api/trips/ghost.html/fill-links")
        assert resp.status_code in (200, 400, 404)

    def test_trips_list_includes_trip_type(self, client):
        import database as db

        create_resp = client.post("/api/trips/create", json={"title": "Type Test"})
        link = create_resp.get_json().get("trip", {}).get("link", "")
        try:
            resp = client.get("/api/trips/list")
            data = resp.get_json()
            for trip in data.get("trips", []):
                assert "trip_type" in trip
        finally:
            if link:
                db.delete_trip(1, link)

    def test_recommendation_trip_html_uses_recommendation_view(self, client):
        """Recommendation trips must not hit the day-by-day view — its map-status
        polling triggers an infinite reload when no map_data is stored.
        Regression for the Google Maps URL import bug."""
        import database as db

        trip_data = {
            "title": "Seattle to Moraga",
            "link": "seattle_to_moraga_test.html",
            "trip_type": "recommendation",
            "map_status": "ready",
        }
        itinerary_data = {
            "ideas": [
                {"title": "Seattle", "location": "Seattle, WA", "category": "transport"},
                {"title": "Moraga", "location": "Moraga, CA", "category": "activity"},
            ],
            "days": [],
            "tips": [],
        }
        db.add_trip(1, trip_data, itinerary_data)
        try:
            resp = client.get("/seattle_to_moraga_test.html")
            assert resp.status_code == 200
            body = resp.get_data(as_text=True)
            # No map polling → no mapData with pending=true, no trip.js
            assert "trip.js" not in body
            assert '"pending": true' not in body
        finally:
            db.delete_trip(1, "seattle_to_moraga_test.html")


# ---------------------------------------------------------------------------
# Data model: ideas with links
# ---------------------------------------------------------------------------


class TestIdeasWithLinks:
    def test_add_idea_with_website_and_maps(self, client):
        import database as db

        # Create trip
        resp = client.post("/api/trips/create", json={"title": "Links Test"})
        link = resp.get_json().get("trip", {}).get("link", "")

        try:
            # Add idea with links
            resp = client.post(
                f"/api/trips/{link}/items",
                json={
                    "item": {
                        "title": "Test Venue",
                        "category": "meal",
                        "location": "Jackson, NH",
                        "website": "https://example.com",
                        "google_maps_link": "https://maps.google.com/test",
                        "latitude": 44.05,
                        "longitude": -71.18,
                    }
                },
            )
            assert resp.status_code == 200

            # Verify links survived
            trip = db.get_trip_by_link(1, link)
            ideas = trip["itinerary_data"].get("ideas", [])
            assert len(ideas) >= 1
            saved = ideas[-1]
            assert saved["website"] == "https://example.com"
            assert saved["google_maps_link"] == "https://maps.google.com/test"
        finally:
            if link:
                db.delete_trip(1, link)


# ---------------------------------------------------------------------------
# Recommendation trips render via the recommendation view
#
# Regression guard: a recommendation trip (ideas-only, no days) used to be
# served by the day-by-day map view, which set mapData.pending=True while
# the DB had map_status="ready" — that combo made trip.js infinite-reload.
# trip_html() now branches on trip_type and serves the recommendation view.
# ---------------------------------------------------------------------------


class TestRecommendationTripRoute:
    def test_recommendation_trip_html_uses_recommendation_view(self, client):
        import database as db

        link = "rec_route_test.html"
        itinerary_data = {
            "ideas": [
                {
                    "title": "Test Cafe",
                    "category": "meal",
                    "location": "Seattle, WA",
                    "latitude": 47.6,
                    "longitude": -122.3,
                }
            ],
            "days": [],
            "tips": [],
        }
        trip_data = {
            "title": "Rec Route Test",
            "link": link,
            "trip_type": "recommendation",
            "map_status": "ready",
        }
        db.add_trip(1, trip_data, itinerary_data)
        try:
            resp = client.get(f"/{link}")
            assert resp.status_code == 200
            body = resp.get_data(as_text=True)

            # Recommendation-view markers should be present.
            assert "rec-hero" in body or "rec-content" in body, (
                "expected recommendation view markup"
            )
            # The day-by-day view's map-polling JS (trip.js) and mapData var
            # are what cause the infinite reload — must not be present here.
            assert "trip.js" not in body
            assert "var mapData" not in body
        finally:
            db.delete_trip(1, link)

    def test_itinerary_trip_html_still_uses_day_view(self, client):
        """Non-recommendation trips must still render via the day-by-day view."""
        import database as db

        link = "day_view_route_test.html"
        itinerary_data = {
            "ideas": [],
            "days": [
                {
                    "day": 1,
                    "items": [
                        {
                            "title": "Arrive",
                            "category": "transport",
                            "location": "Seattle, WA",
                        }
                    ],
                }
            ],
            "tips": [],
        }
        trip_data = {
            "title": "Day View Test",
            "link": link,
            "trip_type": "itinerary",
            "map_status": "pending",
        }
        db.add_trip(1, trip_data, itinerary_data)
        try:
            resp = client.get(f"/{link}")
            assert resp.status_code == 200
            body = resp.get_data(as_text=True)
            # Day view includes the map-status polling JS; recommendation view doesn't.
            assert "trip.js" in body
            assert "var mapData" in body
            assert "rec-hero" not in body
        finally:
            db.delete_trip(1, link)
