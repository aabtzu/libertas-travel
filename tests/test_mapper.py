"""Unit tests for ItineraryMapper — caching logic and is_home_location exclusion.

All tests are pure unit tests: no live API calls, no network, no DB.
LLM calls are patched out wherever mapper methods would invoke them.
"""

from __future__ import annotations

from unittest.mock import patch

from agents.itinerary.mapper import ItineraryMapper
from agents.itinerary.models import Itinerary, ItineraryItem, Location

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_item(
    title: str,
    location: str = "Paris",
    category: str = "activity",
    lat: float | None = 48.8,
    lng: float | None = 2.3,
    is_home: bool = False,
) -> ItineraryItem:
    loc = Location(name=location, address=None, location_type=category)
    if lat is not None:
        loc.latitude = lat
        loc.longitude = lng
    return ItineraryItem(
        title=title,
        location=loc,
        category=category,
        is_home_location=is_home,
    )


def _make_itinerary(title: str = "Paris Trip", items=None) -> Itinerary:
    return Itinerary(title=title, items=items or [])


# ---------------------------------------------------------------------------
# IATA cache
# ---------------------------------------------------------------------------


class TestIataCache:
    def setup_method(self):
        # Clear the class-level cache between tests
        ItineraryMapper._iata_cache.clear()

    def test_skip_words_return_empty_without_llm(self):
        mapper = ItineraryMapper()
        for word in ["THE", "AND", "FOR", "DAY", "VIA"]:
            result = mapper._resolve_iata_code(word)
            assert result == "", f"Expected empty for skip word {word}"

    def test_skip_words_cached(self):
        mapper = ItineraryMapper()
        mapper._resolve_iata_code("THE")
        assert "THE" in ItineraryMapper._iata_cache
        assert ItineraryMapper._iata_cache["THE"] == ""

    def test_cache_hit_skips_llm(self):
        ItineraryMapper._iata_cache["LAX"] = "Los Angeles International Airport, Los Angeles, CA"
        mapper = ItineraryMapper()
        with patch("agents.common.llm.make_llm") as mock_make_llm:
            result = mapper._resolve_iata_code("LAX")
            mock_make_llm.assert_not_called()
        assert "Los Angeles" in result

    def test_cache_key_includes_context(self):
        mapper = ItineraryMapper()
        ItineraryMapper._iata_cache["BIH|Flight: DEN → BIH"] = (
            "Eastern Sierra Regional Airport, Bishop, CA"
        )
        result = mapper._resolve_iata_code("BIH", context="Flight: DEN → BIH")
        assert "Bishop" in result

    def test_llm_failure_caches_empty(self):
        mapper = ItineraryMapper()
        with patch(
            "agents.itinerary.mapper.ItineraryMapper._resolve_iata_code",
            wraps=mapper._resolve_iata_code,
        ):
            with patch("agents.common.llm.make_llm") as mock_make_llm:
                mock_make_llm.return_value.call_api.side_effect = Exception("API error")
                result = mapper._resolve_iata_code("XYZ")
        assert result == ""
        assert ItineraryMapper._iata_cache.get("XYZ") == ""

    def test_none_response_caches_empty(self):
        mapper = ItineraryMapper()
        with patch("agents.common.llm.make_llm") as mock_make_llm:
            mock_make_llm.return_value.call_api.return_value = "NONE"
            result = mapper._resolve_iata_code("ZZZ")
        assert result == ""


# ---------------------------------------------------------------------------
# Region hint cache
# ---------------------------------------------------------------------------


class TestRegionHintCache:
    def test_cache_hit_same_itinerary(self):
        mapper = ItineraryMapper()
        itinerary = _make_itinerary("Tokyo Trip", [_make_item("Sushi dinner", "Tokyo")])

        with patch.object(
            mapper, "_extract_destination_with_llm", return_value="Japan"
        ) as mock_llm:
            result1 = mapper._get_region_hint(itinerary)
            result2 = mapper._get_region_hint(itinerary)

        # LLM should only be called once despite two calls
        assert mock_llm.call_count == 1
        assert result1 == result2 == "Japan"

    def test_cache_miss_different_itinerary(self):
        mapper = ItineraryMapper()
        itin1 = _make_itinerary("Tokyo Trip", [_make_item("Sushi", "Tokyo")])
        itin2 = _make_itinerary("Paris Trip", [_make_item("Croissant", "Paris")])

        with patch.object(
            mapper, "_extract_destination_with_llm", return_value="somewhere"
        ) as mock_llm:
            mapper._get_region_hint(itin1)
            mapper._get_region_hint(itin2)

        # Different itinerary objects → two separate LLM calls
        assert mock_llm.call_count == 2

    def test_no_title_no_items_returns_empty_without_llm(self):
        # context_parts is empty only when there's no title AND no items
        mapper = ItineraryMapper()
        itinerary = _make_itinerary("", items=[])

        with patch.object(mapper, "_extract_destination_with_llm") as mock_llm:
            result = mapper._get_region_hint(itinerary)

        mock_llm.assert_not_called()
        assert result == ""

    def test_llm_failure_falls_back_to_fallback(self):
        mapper = ItineraryMapper()
        itinerary = _make_itinerary("Tokyo Trip", [_make_item("Sushi", "Tokyo")])

        with patch.object(mapper, "_extract_destination_with_llm", side_effect=Exception("fail")):
            with patch.object(
                mapper, "_get_region_hint_fallback", return_value="Japan"
            ) as mock_fallback:
                result = mapper._get_region_hint(itinerary)

        mock_fallback.assert_called_once()
        assert result == "Japan"

    def test_cached_value_is_stored(self):
        mapper = ItineraryMapper()
        itinerary = _make_itinerary("Rome Trip", [_make_item("Colosseum", "Rome")])

        with patch.object(mapper, "_extract_destination_with_llm", return_value="Italy"):
            mapper._get_region_hint(itinerary)

        assert mapper._cached_region_hint == "Italy"
        assert mapper._cached_region_itinerary_id == id(itinerary)


# ---------------------------------------------------------------------------
# is_home_location exclusion from create_map_data
# ---------------------------------------------------------------------------


class TestHomeLocationExclusion:
    def _make_mapper_with_mocked_geocode(self):
        """Return a mapper that skips real geocoding and LLM calls."""
        mapper = ItineraryMapper()
        # Prevent network calls — geocode_locations is a no-op
        mapper.geocode_locations = lambda itin: itin
        # Prevent LLM call for region hint
        mapper._get_region_hint = lambda itin: "France"
        # Prevent origin-check LLM call
        mapper._is_transport_outside_destination = lambda item, dest: False
        return mapper

    def test_home_location_excluded_from_markers(self):
        home = _make_item("My Home", "New York", lat=40.7, lng=-74.0, is_home=True)
        paris = _make_item("Eiffel Tower", "Paris", lat=48.8, lng=2.3)
        itinerary = _make_itinerary("Paris Trip", [home, paris])

        mapper = self._make_mapper_with_mocked_geocode()
        result = mapper.create_map_data(itinerary)

        marker_titles = [m["title"] for m in result.get("markers", [])]
        assert "Eiffel Tower" in marker_titles
        assert "My Home" not in marker_titles

    def test_non_home_locations_included(self):
        item1 = _make_item("Louvre", "Paris", lat=48.86, lng=2.33)
        item2 = _make_item("Notre Dame", "Paris", lat=48.85, lng=2.35)
        itinerary = _make_itinerary("Paris Trip", [item1, item2])

        mapper = self._make_mapper_with_mocked_geocode()
        result = mapper.create_map_data(itinerary)

        marker_titles = [m["title"] for m in result.get("markers", [])]
        assert "Louvre" in marker_titles
        assert "Notre Dame" in marker_titles

    def test_all_home_locations_returns_empty_markers(self):
        home1 = _make_item("Home", "New York", lat=40.7, lng=-74.0, is_home=True)
        home2 = _make_item("Office", "New York", lat=40.71, lng=-74.01, is_home=True)
        itinerary = _make_itinerary("Trip", [home1, home2])

        mapper = self._make_mapper_with_mocked_geocode()
        result = mapper.create_map_data(itinerary)

        assert result.get("markers") == [] or result.get("error") is not None

    def test_items_without_coordinates_excluded(self):
        no_coords = _make_item("Unknown Spot", "Somewhere", lat=None, lng=None)
        has_coords = _make_item("Eiffel Tower", "Paris", lat=48.8, lng=2.3)
        itinerary = _make_itinerary("Trip", [no_coords, has_coords])

        mapper = self._make_mapper_with_mocked_geocode()
        result = mapper.create_map_data(itinerary)

        marker_titles = [m["title"] for m in result.get("markers", [])]
        assert "Eiffel Tower" in marker_titles
        assert "Unknown Spot" not in marker_titles

    def test_origin_check_cache_cleared_on_create_map_data(self):
        itinerary = _make_itinerary("Trip", [_make_item("Louvre", "Paris", lat=48.86, lng=2.33)])
        mapper = self._make_mapper_with_mocked_geocode()
        mapper._origin_check_cache["stale_key"] = True

        mapper.create_map_data(itinerary)

        assert "stale_key" not in mapper._origin_check_cache


# ---------------------------------------------------------------------------
# _build_flight_queries (no LLM — uses cached IATA or loc_name directly)
# ---------------------------------------------------------------------------


class TestBuildFlightQueries:
    def setup_method(self):
        ItineraryMapper._iata_cache.clear()

    def test_iata_location_field_used_first(self):
        # Stub the IATA resolver instead of poking _iata_cache directly — the
        # cache key includes context (f"{iata}|{context}"), so seeding by
        # bare code misses and the real resolver hits Claude (and 401s in CI).
        from unittest.mock import patch

        mapper = ItineraryMapper()
        item = _make_item("UA 100 JFK → CDG", "CDG", category="flight")
        with patch.object(
            mapper,
            "_resolve_iata_code",
            return_value="Charles de Gaulle Airport, Paris, France",
        ):
            queries = mapper._build_flight_queries(item, "CDG", "France")
        assert any("Charles de Gaulle" in q for q in queries)

    def test_skip_word_iata_falls_through_to_city_queries(self):
        ItineraryMapper._iata_cache["THE"] = ""
        mapper = ItineraryMapper()
        item = _make_item("Flight to THE", "THE", category="flight")
        queries = mapper._build_flight_queries(item, "THE", "")
        # Should still produce city-based airport queries
        assert any("Airport" in q for q in queries)

    def test_non_iata_location_generates_airport_queries(self):
        mapper = ItineraryMapper()
        item = _make_item("Flight to Vienna", "Vienna", category="flight")
        queries = mapper._build_flight_queries(item, "Vienna", "Austria")
        assert any("Vienna" in q and "Airport" in q for q in queries)
