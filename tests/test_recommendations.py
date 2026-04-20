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
        assert resp.status_code in (200, 400)
        data = resp.get_json()
        assert data.get("success") is not True

    def test_writeup_nonexistent_trip(self, client):
        resp = client.post("/api/trips/ghost.html/writeup")
        assert resp.status_code in (200, 400)

    def test_fill_links_nonexistent_trip(self, client):
        resp = client.post("/api/trips/ghost.html/fill-links")
        assert resp.status_code in (200, 400)

    def test_trips_list_includes_trip_type(self, client):
        # Create a trip first
        client.post("/api/trips/create", json={"title": "Type Test"})
        resp = client.get("/api/trips/list")
        data = resp.get_json()
        for trip in data.get("trips", []):
            assert "trip_type" in trip


# ---------------------------------------------------------------------------
# Data model: ideas with links
# ---------------------------------------------------------------------------


class TestIdeasWithLinks:
    def test_add_idea_with_website_and_maps(self, client):
        # Create trip
        resp = client.post("/api/trips/create", json={"title": "Links Test"})
        link = resp.get_json().get("trip", {}).get("link", "")

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
        import database as db

        trip = db.get_trip_by_link(1, link)
        ideas = trip["itinerary_data"].get("ideas", [])
        assert len(ideas) >= 1
        saved = ideas[-1]
        assert saved["website"] == "https://example.com"
        assert saved["google_maps_link"] == "https://maps.google.com/test"
