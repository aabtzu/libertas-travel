"""Tests for the link/location filler that wires the 'Fill Missing Links'
button. The LLM is stubbed — these tests cover the orchestration logic,
not the model's choices."""

from __future__ import annotations

from unittest.mock import MagicMock, patch


def _stub_llm(text: str):
    """Build a MagicMock that mimics fiat-lux-agents' LLMBase.call_api
    when called with return_full_response=True."""
    fake = MagicMock()
    fake.call_api.return_value.content = [MagicMock(text=text)]
    return fake


class TestFillMissingLocations:
    def test_fills_location_for_items_with_none(self):
        from agents.trips.link_resolver import _fill_missing_locations

        items = [
            {"title": "Christkindlmarkt at Marienplatz"},
            {"title": "Hotel Drei Raben", "location": "Nuremberg, Germany"},
        ]
        with patch(
            "agents.trips.link_resolver.make_llm",
            return_value=_stub_llm('{"Christkindlmarkt at Marienplatz": "Munich, Germany"}'),
        ):
            added = _fill_missing_locations(items, trip_title="German Xmas Markets")
        assert added == 1
        assert items[0]["location"] == "Munich, Germany"
        assert items[1]["location"] == "Nuremberg, Germany"  # unchanged

    def test_skips_items_when_llm_omits_them(self):
        """Per the prompt, the model is told to OMIT items it can't place
        with confidence rather than guess. Make sure we honor that."""
        from agents.trips.link_resolver import _fill_missing_locations

        items = [{"title": "Some Generic Cafe"}]
        with patch(
            "agents.trips.link_resolver.make_llm",
            return_value=_stub_llm("{}"),
        ):
            added = _fill_missing_locations(items, trip_title="Trip")
        assert added == 0
        assert "location" not in items[0] or not items[0]["location"]

    def test_no_items_need_filling_short_circuits(self):
        from agents.trips.link_resolver import _fill_missing_locations

        items = [
            {"title": "A", "location": "Munich, Germany"},
            {"title": "B", "location": "Paris, France"},
        ]
        with patch("agents.trips.link_resolver.make_llm") as mk:
            added = _fill_missing_locations(items, trip_title="x")
        assert added == 0
        mk.assert_not_called()  # no items need filling -> no LLM call

    def test_rejects_response_without_comma(self):
        """A 'City, Country' string should have a comma — single-word
        responses are rejected as low-confidence."""
        from agents.trips.link_resolver import _fill_missing_locations

        items = [{"title": "Mystery"}]
        with patch(
            "agents.trips.link_resolver.make_llm",
            return_value=_stub_llm('{"Mystery": "somewhere"}'),
        ):
            added = _fill_missing_locations(items, trip_title="Trip")
        assert added == 0

    def test_empty_string_location_is_treated_as_missing(self):
        """An item with `location: ""` should be considered location-less."""
        from agents.trips.link_resolver import _fill_missing_locations

        items = [{"title": "X", "location": ""}, {"title": "Y", "location": "  "}]
        with patch(
            "agents.trips.link_resolver.make_llm",
            return_value=_stub_llm('{"X": "Munich, Germany", "Y": "Berlin, Germany"}'),
        ):
            added = _fill_missing_locations(items, trip_title="Germany trip")
        assert added == 2


class TestFillMissingLinks:
    """Orchestration: locations fill first so maps URLs include the city."""

    def test_locations_run_before_maps_so_query_includes_city(self):
        from agents.trips.link_resolver import fill_missing_links

        item = {"title": "Marienplatz"}
        with patch(
            "agents.trips.link_resolver.make_llm",
            return_value=_stub_llm('{"Marienplatz": "Munich, Germany"}'),
        ):
            result = fill_missing_links(
                {"days": [{"items": [item]}], "ideas": []},
                trip_title="Germany",
            )
        assert result["locations_added"] == 1
        # Maps URL should include the freshly-added city, not just the title
        assert "Munich" in item["google_maps_link"]
