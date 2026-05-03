"""Tests for the LLM-driven card icon picker.

The unit tests stub the LLM call so they don't require a live key. An
optional integration test exercises the real LLM end-to-end and only
runs when ANTHROPIC_API_KEY is set to a real value (marker:
@pytest.mark.integration).
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from agents.itinerary.icon_picker import (
    FALLBACK_ICON,
    ICON_OPTIONS,
    _summarize_trip,
    pick_card_icon,
)

# ---------------------------------------------------------------------------
# Prompt builder — destinations + category mix extraction
# ---------------------------------------------------------------------------


class TestSummarizeTrip:
    def test_extracts_distinct_locations(self):
        data = {
            "days": [
                {
                    "items": [
                        {"location": "Paris, France", "category": "attraction"},
                        {"location": "Paris, France", "category": "meal"},
                        {"location": "Lyon, France", "category": "meal"},
                    ]
                }
            ]
        }
        out = _summarize_trip("French Trip", data)
        assert "Paris" in out
        assert "Lyon" in out
        # Deduplicated — Paris appears once
        assert out.count("Paris") == 1

    def test_includes_category_histogram(self):
        data = {"ideas": [{"category": "meal"}, {"category": "meal"}, {"category": "attraction"}]}
        out = _summarize_trip("Foodie", data)
        assert "meal:2" in out
        assert "attraction:1" in out

    def test_handles_empty_itinerary(self):
        out = _summarize_trip("Mystery Trip", {"days": [], "ideas": []})
        assert "Mystery Trip" in out
        assert "n/a" in out


# ---------------------------------------------------------------------------
# pick_card_icon — LLM stubbed
# ---------------------------------------------------------------------------


class TestPickCardIcon:
    def test_returns_valid_icon_from_llm(self):
        with patch("agents.itinerary.icon_picker.make_llm") as mock_make:
            mock_make.return_value.call_api.return_value = "bridge"
            icon = pick_card_icon("San Francisco Weekend", {"days": []})
            assert icon == "bridge"

    def test_strips_fa_prefix_if_present(self):
        with patch("agents.itinerary.icon_picker.make_llm") as mock_make:
            mock_make.return_value.call_api.return_value = "fa-bridge"
            icon = pick_card_icon("SF", {})
            assert icon == "bridge"

    def test_strips_quotes_and_punctuation(self):
        with patch("agents.itinerary.icon_picker.make_llm") as mock_make:
            mock_make.return_value.call_api.return_value = '"landmark".'
            icon = pick_card_icon("Spain", {})
            assert icon == "landmark"

    def test_extracts_valid_icon_from_phrase(self):
        # Model occasionally explains itself despite instructions
        with patch("agents.itinerary.icon_picker.make_llm") as mock_make:
            mock_make.return_value.call_api.return_value = "I would pick: mountain"
            icon = pick_card_icon("Alps", {})
            assert icon == "mountain"

    def test_invalid_response_falls_back(self):
        with patch("agents.itinerary.icon_picker.make_llm") as mock_make:
            mock_make.return_value.call_api.return_value = "fa-eiffel-tower-not-real"
            icon = pick_card_icon("Paris", {})
            assert icon == FALLBACK_ICON

    def test_llm_exception_falls_back(self):
        with patch("agents.itinerary.icon_picker.make_llm") as mock_make:
            mock_make.return_value.call_api.side_effect = RuntimeError("API down")
            icon = pick_card_icon("Anywhere", {})
            assert icon == FALLBACK_ICON

    def test_empty_title_falls_back_without_calling_llm(self):
        with patch("agents.itinerary.icon_picker.make_llm") as mock_make:
            icon = pick_card_icon("", None)
            assert icon == FALLBACK_ICON
            mock_make.assert_not_called()


# ---------------------------------------------------------------------------
# API endpoint — caches result in itinerary_data
# ---------------------------------------------------------------------------


class TestCardIconEndpoint:
    def test_returns_cached_icon_without_llm_call(self, client):
        import database as db

        link = "icon_cached_test.html"
        db.add_trip(
            1,
            {"title": "Cached Test", "link": link},
            {"card_icon": "bridge", "days": [], "ideas": [], "tips": []},
        )
        try:
            with patch("agents.itinerary.icon_picker.make_llm") as mock_make:
                resp = client.get(f"/api/trips/{link}/card-icon")
                assert resp.status_code == 200
                assert resp.get_json()["icon"] == "bridge"
                mock_make.assert_not_called()  # cached -> no LLM
        finally:
            db.delete_trip(1, link)

    def test_computes_and_persists_when_missing(self, client):
        import database as db

        link = "icon_compute_test.html"
        db.add_trip(
            1,
            {"title": "Compute Test", "link": link},
            {"days": [], "ideas": [], "tips": []},
        )
        try:
            with patch("agents.itinerary.icon_picker.make_llm") as mock_make:
                mock_make.return_value.call_api.return_value = "compass"
                resp = client.get(f"/api/trips/{link}/card-icon")
                assert resp.status_code == 200
                assert resp.get_json()["icon"] == "compass"

                # Second call should hit the cache, not the LLM
                mock_make.reset_mock()
                resp2 = client.get(f"/api/trips/{link}/card-icon")
                assert resp2.get_json()["icon"] == "compass"
                mock_make.assert_not_called()
        finally:
            db.delete_trip(1, link)

    def test_unknown_trip_returns_404(self, client):
        resp = client.get("/api/trips/totally_made_up_xyz.html/card-icon")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Integration smoke test (skipped unless real key available)
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_real_llm_picks_bridge_for_san_francisco():
    icon = pick_card_icon(
        "San Francisco Weekend",
        {"days": [{"items": [{"location": "Golden Gate Bridge, SF", "category": "attraction"}]}]},
    )
    assert icon in ICON_OPTIONS
    # Soft expectation: SF should land on bridge or a city-scape icon, not plane
    assert icon in {"bridge", "city", "landmark", "tower-observation"}
