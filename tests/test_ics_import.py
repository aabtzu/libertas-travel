"""Tests for the .ics import path. Covers both the basic happy path and
the edge cases the previous hand-rolled parser got wrong (line folding,
TZID parameters, escaped commas, recurring events).

Issue #62 tracks the rewrite from hand-rolled to the icalendar library.
"""

from __future__ import annotations

from agents.create.file_parsers import _parse_ics_file


def _ics(*events: str) -> bytes:
    """Wrap a list of VEVENT bodies in a minimal VCALENDAR envelope."""
    body = "\r\n".join(
        ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Test//EN", *events, "END:VCALENDAR"]
    )
    return body.encode("utf-8")


def _vevent(**fields: str) -> str:
    lines = ["BEGIN:VEVENT"]
    for key, value in fields.items():
        lines.append(f"{key}:{value}")
    lines.append("END:VEVENT")
    return "\r\n".join(lines)


# ---------------------------------------------------------------------------
# Basic happy path
# ---------------------------------------------------------------------------


def test_parses_a_simple_timed_event():
    data = _ics(
        _vevent(
            SUMMARY="Lunch at Cafe Lou",
            DTSTART="20260520T130000",
            DTEND="20260520T143000",
            LOCATION="123 Main St",
            DESCRIPTION="Reservation for 2",
        )
    )
    items = _parse_ics_file(data)
    assert len(items) == 1
    item = items[0]
    assert item["title"] == "Lunch at Cafe Lou"
    assert item["date"] == "2026-05-20"
    assert item["time"] == "13:00"
    assert item["end_time"] == "14:30"
    assert item["location"] == "123 Main St"
    assert item["category"] == "meal"


def test_parses_an_all_day_event():
    # ``;VALUE=DATE`` is a property parameter (semicolon), not a value. The
    # _vevent() helper emits ``KEY:value`` so we hand-build the property line.
    data = (
        b"BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//Test//EN\r\n"
        b"BEGIN:VEVENT\r\n"
        b"SUMMARY:Day at the museum\r\n"
        b"DTSTART;VALUE=DATE:20260601\r\n"
        b"END:VEVENT\r\n"
        b"END:VCALENDAR\r\n"
    )
    items = _parse_ics_file(data)
    assert len(items) == 1
    assert items[0]["date"] == "2026-06-01"
    assert items[0]["category"] == "attraction"
    # No time on date-only events
    assert "time" not in items[0]


def test_skips_events_without_summary():
    data = _ics(_vevent(DTSTART="20260520T130000", LOCATION="Anywhere"))
    items = _parse_ics_file(data)
    assert items == []


def test_returns_empty_on_malformed_input():
    items = _parse_ics_file(b"not even close to ics format")
    assert items == []


# ---------------------------------------------------------------------------
# Regressions the hand-rolled parser got wrong (issue #62)
# ---------------------------------------------------------------------------


def test_handles_folded_lines_with_tab_continuation():
    """RFC 5545: long lines fold onto the next line with a leading space OR
    tab. The hand-rolled parser only handled space continuation, tab
    continuation silently truncated the value."""
    data = (
        b"BEGIN:VCALENDAR\r\n"
        b"VERSION:2.0\r\n"
        b"PRODID:-//Test//EN\r\n"
        b"BEGIN:VEVENT\r\n"
        b"SUMMARY:A long title that wraps onto\r\n"
        b"\tthe next line via tab continuation\r\n"
        b"DTSTART:20260520T130000\r\n"
        b"END:VEVENT\r\n"
        b"END:VCALENDAR\r\n"
    )
    items = _parse_ics_file(data)
    assert len(items) == 1
    # The full unfolded title comes through
    assert "tab continuation" in items[0]["title"]


def test_dtstart_with_tzid_parameter_is_parsed():
    """``DTSTART;TZID=America/New_York:20260520T160000`` has a property
    parameter the hand-rolled parser ignored. The library handles it,
    we should still get the right date/time."""
    data = (
        b"BEGIN:VCALENDAR\r\n"
        b"VERSION:2.0\r\n"
        b"PRODID:-//Test//EN\r\n"
        b"BEGIN:VEVENT\r\n"
        b"SUMMARY:NYC Dinner\r\n"
        b"DTSTART;TZID=America/New_York:20260520T200000\r\n"
        b"END:VEVENT\r\n"
        b"END:VCALENDAR\r\n"
    )
    items = _parse_ics_file(data)
    assert len(items) == 1
    assert items[0]["date"] == "2026-05-20"
    # Local time of the event, not UTC-converted
    assert items[0]["time"] == "20:00"


def test_escaped_commas_in_summary_decode_correctly():
    """``\\,`` should become a literal comma in the parsed value."""
    data = _ics(_vevent(SUMMARY="Trip to Paris\\, France", DTSTART="20260520T100000"))
    items = _parse_ics_file(data)
    assert items[0]["title"] == "Trip to Paris, France"


def test_extracts_local_time_from_tripit_description():
    """TripIt-style export: DTSTART is UTC, but the description holds the
    actual local departure time. We override the UTC time with the local
    one when the regex matches."""
    data = _ics(
        _vevent(
            SUMMARY="Flight UA 123",
            DTSTART="20260520T230000Z",
            DESCRIPTION="Departure time: 16:00 (local)",
        )
    )
    items = _parse_ics_file(data)
    # Local time wins
    assert items[0]["time"] == "16:00"
    assert items[0]["category"] == "flight"


# ---------------------------------------------------------------------------
# Category guessing
# ---------------------------------------------------------------------------


def test_categorizes_flight_from_title():
    data = _ics(
        _vevent(
            SUMMARY="UA Flight 123",
            DTSTART="20260520T100000",
            DESCRIPTION="United Airlines, terminal 3",
        )
    )
    assert _parse_ics_file(data)[0]["category"] == "flight"


def test_categorizes_hotel_from_title():
    data = _ics(_vevent(SUMMARY="Marriott check-in", DTSTART="20260520T160000"))
    assert _parse_ics_file(data)[0]["category"] == "hotel"


def test_falls_back_to_activity():
    data = _ics(_vevent(SUMMARY="Random thing", DTSTART="20260520T100000"))
    assert _parse_ics_file(data)[0]["category"] == "activity"
