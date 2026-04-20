"""Tests for Google Maps URL parser."""

from __future__ import annotations

from agents.create.google_maps_parser import (
    _clean_stop_name,
    _extract_coordinates_from_data,
    _parse_directions_url,
    parse_google_maps_url,
    stops_to_trip_items,
)


class TestCleanStopName:
    def test_removes_zip_code(self):
        assert _clean_stop_name("Gold Beach, Oregon 97444") == "Gold Beach, Oregon"

    def test_removes_zip_plus_4(self):
        assert _clean_stop_name("Shelter Cove, California 95589-1234") == "Shelter Cove, California"

    def test_no_zip(self):
        assert _clean_stop_name("Seattle, Washington") == "Seattle, Washington"

    def test_url_decoded(self):
        assert _clean_stop_name("Gold Beach, Oregon") == "Gold Beach, Oregon"


class TestExtractCoordinates:
    def test_extracts_pairs(self):
        url = "data=!1d-122.3328481!2d47.6061389!1d-124.4217741!2d42.4073334"
        coords = _extract_coordinates_from_data(url)
        assert len(coords) == 2
        assert abs(coords[0]["lat"] - 47.6061) < 0.001
        assert abs(coords[0]["lng"] - (-122.3328)) < 0.001

    def test_no_data(self):
        assert _extract_coordinates_from_data("https://example.com") == []


class TestParseDirectionsUrl:
    FULL_URL = (
        "https://www.google.com/maps/dir/Seattle,+Washington/Gold+Beach,+Oregon+97444"
        "/Moraga,+California/@44.2,125.5,6z/data=!4m20!4m19"
        "!1m5!1m1!1s0x5490102c93e83355:0x1!2m2!1d-122.33!2d47.61"
        "!1m5!1m1!1s0x54dace49bf9ae73d:0x1!2m2!1d-124.42!2d42.41"
        "!1m5!1m1!1s0x808f89b60d99b98d:0x1!2m2!1d-122.13!2d37.83!3e0"
    )

    def test_extracts_stop_names(self):
        stops = _parse_directions_url(self.FULL_URL)
        names = [s["name"] for s in stops]
        assert "Seattle, Washington" in names
        assert "Gold Beach, Oregon" in names
        assert "Moraga, California" in names

    def test_extracts_coordinates(self):
        stops = _parse_directions_url(self.FULL_URL)
        assert stops[0]["latitude"] is not None
        assert stops[0]["longitude"] is not None

    def test_skips_at_segment(self):
        stops = _parse_directions_url(self.FULL_URL)
        names = [s["name"] for s in stops]
        assert not any(n.startswith("@") for n in names)


class TestParseGoogleMapsUrl:
    def test_directions_type(self):
        url = "https://www.google.com/maps/dir/A/B/C/@0,0,5z/data=!4m2!4m1!3e0"
        result = parse_google_maps_url(url)
        assert result["type"] == "directions"

    def test_place_type(self):
        url = "https://www.google.com/maps/place/Eiffel+Tower/@48.8584,2.2945,17z"
        result = parse_google_maps_url(url)
        assert result["type"] == "place"
        assert result["stops"][0]["name"] == "Eiffel Tower"
        assert abs(result["stops"][0]["latitude"] - 48.8584) < 0.001

    def test_title_from_first_last(self):
        url = "https://www.google.com/maps/dir/Seattle/Portland/SF/@0,0,5z/data=!4m2!4m1!3e0"
        result = parse_google_maps_url(url)
        assert result["title"] == "Seattle to SF"


class TestStopsToTripItems:
    def test_first_stop_is_home(self):
        stops = [
            {"name": "Seattle", "latitude": 47.6, "longitude": -122.3},
            {"name": "Portland", "latitude": 45.5, "longitude": -122.7},
        ]
        items = stops_to_trip_items(stops)
        assert items[0]["is_home_location"] is True
        assert items[0]["category"] == "transport"

    def test_other_stops_are_activities(self):
        stops = [
            {"name": "A", "latitude": 1.0, "longitude": 2.0},
            {"name": "B", "latitude": 3.0, "longitude": 4.0},
        ]
        items = stops_to_trip_items(stops)
        assert items[1]["category"] == "activity"

    def test_has_maps_link(self):
        stops = [{"name": "Seattle", "latitude": 47.6, "longitude": -122.3}]
        items = stops_to_trip_items(stops)
        assert "google.com/maps" in items[0]["google_maps_link"]

    def test_has_coordinates(self):
        stops = [{"name": "X", "latitude": 47.6, "longitude": -122.3}]
        items = stops_to_trip_items(stops)
        assert items[0]["latitude"] == 47.6
        assert items[0]["longitude"] == -122.3
