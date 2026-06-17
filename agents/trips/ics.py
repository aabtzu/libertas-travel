"""ICS calendar file generation from trip data.

Uses the icalendar library so escaping, line folding, and date/time
serialization match RFC 5545 by construction. The previous hand-rolled
emitter worked for the common case but had latent bugs in edge cases
(unfolded long DESCRIPTIONs, escape order, no UTC normalization).

Timezone strategy:
- Each item's DTSTART/DTEND is tagged with the IANA timezone of its
  geocoded location, derived from the map_data markers that the geocoding
  worker already computed and stored. This is the TripIt model: a dinner in
  NY is America/New_York, a hotel in LA is America/Los_Angeles.
- Transit items (flight, train, bus) remain floating: departure and arrival
  are in different timezones and we only store one location per item.
- Items without geocoded coordinates remain floating (RFC 5545 correct for
  wall-clock local time at the destination).
- timezonefinder does the lat/lng -> IANA lookup entirely offline.
"""

from __future__ import annotations

import hashlib
import hmac
import os
from datetime import UTC, datetime, timedelta
from datetime import date as _date
from typing import TYPE_CHECKING

from icalendar import Calendar, Event, vDatetime

if TYPE_CHECKING:
    from timezonefinder import TimezoneFinder as _TFType

# Categories that represent a stay or rental spanning multiple days.
# Items in these categories with an end_date get:
#   1. An all-day multi-day span event (the "bar" across the calendar)
#   2. A separate timed check-in/pickup event on the start day
_SPAN_CATEGORIES = frozenset(["hotel", "lodging", "transport"])

# Labels for the timed companion event by category.
_CHECKIN_LABEL = {
    "hotel": "Check-in: ",
    "lodging": "Check-in: ",
    "transport": "Pickup: ",
}

# Transit categories: departure and arrival are in different timezones.
# Using a single TZID would tag the departure time with the arrival timezone
# (or vice versa), which is wrong. Floating times are the RFC 5545 correct
# representation for these items.
_TRANSIT_CATEGORIES = frozenset(["flight", "train", "bus"])

# Module-level TimezoneFinder singleton - loaded once, reused across requests.
# Loading reads ~20 MB of polygon data from disk; we don't want that per call.
_TF: _TFType | None = None
_TF_LOADED = False  # tracks whether we've attempted to load (even if it failed)


def _get_tf() -> _TFType | None:
    """Return the shared TimezoneFinder instance, or None if unavailable."""
    global _TF, _TF_LOADED
    if _TF_LOADED:
        return _TF
    _TF_LOADED = True
    try:
        from timezonefinder import TimezoneFinder

        _TF = TimezoneFinder()
    except Exception:
        _TF = None
    return _TF


def _tz_from_latlon(lat: float, lng: float) -> str | None:
    """Return IANA timezone name for a lat/lng, or None on failure."""
    tf = _get_tf()
    if tf is None:
        return None
    try:
        return tf.timezone_at(lat=lat, lng=lng)
    except Exception:
        return None


def _build_tz_lookup(itinerary_data: dict) -> dict[str, str]:
    """Build a title-to-IANA-timezone mapping from geocoded map_data markers.

    The geocoding worker already computed lat/lng for each item and stored the
    result in itinerary_data["map_data"]["markers"]. We derive the timezone
    from those coordinates so ICS generation doesn't need to do any geocoding.

    Returns an empty dict when map_data is absent or timezonefinder is not
    installed - callers treat missing entries as "use floating time."
    """
    lookup: dict[str, str] = {}
    markers = (itinerary_data.get("map_data") or {}).get("markers", [])
    if not markers:
        return lookup
    tf = _get_tf()
    if tf is None:
        return lookup
    for marker in markers:
        title = (marker.get("title") or "").strip()
        pos = marker.get("position") or {}
        lat = pos.get("lat")
        lng = pos.get("lng")
        if not title or lat is None or lng is None:
            continue
        tz = _tz_from_latlon(float(lat), float(lng))
        if tz:
            lookup[title] = tz
    return lookup


def calendar_subscribe_token(user_id: int, link: str) -> str:
    """Build a deterministic per-(user, trip) HMAC token.

    Used in subscribe URLs (``/api/trips/<link>/calendar.ics?token=...``) so
    the user's calendar app can poll without sending a session cookie.
    Stateless: the server validates by recomputing. SECRET_KEY must be set
    (it always is in prod and dev), the same env var Flask uses for cookies.

    Why HMAC and not a stored random token: zero DB changes, revoked
    automatically when SECRET_KEY rotates, and matches what the rest of
    the auth surface uses. Downside: rotating SECRET_KEY invalidates every
    existing subscribe URL (see memory/todo_secret_key_rotation_breaks_subscribes.md).
    """
    secret = os.environ.get("SECRET_KEY", "")
    if not secret:
        # Should never happen in prod; refuse rather than emit a forgeable token.
        raise RuntimeError("SECRET_KEY not set, cannot generate subscribe token")
    payload = f"calendar:{user_id}:{link}".encode()
    digest = hmac.new(secret.encode(), payload, hashlib.sha256).digest()
    # 16 bytes (32 hex chars) is plenty: 2^128 search space, and these tokens
    # are only useful as URL params on a per-trip basis.
    return digest.hex()[:32]


def verify_subscribe_token(user_id: int, link: str, provided: str) -> bool:
    """Constant-time check of a subscribe token."""
    expected = calendar_subscribe_token(user_id, link)
    return hmac.compare_digest(expected, provided)


def user_calendar_token(user_id: int) -> str:
    """Build a deterministic per-user HMAC token for the all-trips feed.

    Same HMAC approach as calendar_subscribe_token but scoped to the user
    (no trip link), so one URL covers all their published trips. The "user-cal"
    prefix prevents token reuse between the two surfaces.
    """
    secret = os.environ.get("SECRET_KEY", "")
    if not secret:
        raise RuntimeError("SECRET_KEY not set, cannot generate user calendar token")
    payload = f"user-cal:{user_id}".encode()
    digest = hmac.new(secret.encode(), payload, hashlib.sha256).digest()
    return digest.hex()[:32]


def verify_user_calendar_token(user_id: int, provided: str) -> bool:
    """Constant-time check of a user calendar token."""
    expected = user_calendar_token(user_id)
    return hmac.compare_digest(expected, provided)


def generate_ics_multi(trips: list[dict]) -> str:
    """Generate a single ICS feed containing all events from multiple trips.

    Each trip dict must have ``title``, ``link``, and ``itinerary_data``
    (already parsed from JSON). Only days with a ``date`` are included;
    items without a date on their day are skipped.

    Each item's timezone is derived from its geocoded location in map_data,
    so events show in the correct local time in Google Calendar. Transit items
    (flights, trains, buses) use floating times since departure and arrival
    are in different timezones.
    """
    cal = Calendar()
    cal.add("VERSION", "2.0")
    cal.add("PRODID", "-//Libertas Travel//Trip Planner//EN")
    cal.add("CALSCALE", "GREGORIAN")
    cal.add("METHOD", "PUBLISH")
    cal.add("X-WR-CALNAME", "Libertas Travel")

    now_utc = datetime.now(UTC)
    event_count = 0

    for trip in trips:
        link = trip.get("link", "unknown")
        itinerary_data = trip.get("itinerary_data") or {}
        days = itinerary_data.get("days", [])
        tz_lookup = _build_tz_lookup(itinerary_data)

        for day in days:
            day_date_str = day.get("date")
            if not day_date_str:
                continue
            try:
                day_date = _date.fromisoformat(day_date_str)
            except ValueError:
                continue

            for item in day.get("items", []):
                event_count += 1
                uid_prefix = f"{link}-{day_date_str}-{event_count}"
                for event in _build_events(item, day_date, uid_prefix, now_utc, tz_lookup):
                    cal.add_component(event)

    return cal.to_ical().decode("utf-8")


def generate_ics(export_data: dict, link: str) -> str:
    """Generate ICS calendar format from trip export data.

    Returns a string (CRLF-terminated lines) suitable for serving as
    text/calendar. Each scheduled item becomes one VEVENT. Items without
    a ``date`` on their day are skipped. Items without a ``time`` become
    all-day events; with a ``time``, they get a 1-hour default unless an
    ``end_time`` is set.

    Timezones are derived from geocoded map_data markers - same logic as
    generate_ics_multi.
    """
    title = export_data.get("title", "Trip")
    itinerary_data = export_data.get("itinerary_data", {})
    days = itinerary_data.get("days", [])
    tz_lookup = _build_tz_lookup(itinerary_data)

    cal = Calendar()
    cal.add("VERSION", "2.0")
    cal.add("PRODID", "-//Libertas Travel//Trip Planner//EN")
    cal.add("CALSCALE", "GREGORIAN")
    cal.add("METHOD", "PUBLISH")
    cal.add("X-WR-CALNAME", title)

    # RFC 5545 requires DTSTAMP to be a UTC datetime (Z suffix).
    now_utc = datetime.now(UTC)
    event_count = 0

    for day in days:
        day_date_str = day.get("date")
        if not day_date_str:
            continue

        try:
            day_date = _date.fromisoformat(day_date_str)
        except ValueError:
            continue

        for item in day.get("items", []):
            event_count += 1
            uid_prefix = f"{link}-{day_date_str}-{event_count}"
            for event in _build_events(item, day_date, uid_prefix, now_utc, tz_lookup):
                cal.add_component(event)

    return cal.to_ical().decode("utf-8")


def _build_events(
    item: dict,
    day_date: _date,
    uid_prefix: str,
    now_utc: datetime,
    tz_lookup: dict[str, str],
) -> list[Event]:
    """Build one or two VEVENT objects for a single itinerary item.

    Hotels and car rentals with an end_date produce two events:
      - An all-day span across the full stay/rental period (the "bar")
      - A timed check-in/pickup event on the start day

    Everything else (flights, meals, activities) produces one timed event,
    or an all-day event when no time is given.

    Transit items (flights, trains, buses) always get floating times.
    All other items get TZID from their geocoded location in tz_lookup,
    so a 9pm dinner in NY shows as 9pm ET regardless of where the viewer is.
    """
    category = (item.get("category") or "activity").lower()
    title = item.get("title", "Activity")
    item_time = item.get("time")
    item_end_time = item.get("end_time")
    end_date_str = item.get("end_date")
    location = item.get("location", "")
    notes = item.get("notes", "")
    website = item.get("website", "")

    # Derive timezone from geocoded location. Transit items stay floating:
    # a flight has departure timezone != arrival timezone, and we only have
    # one location per item (the destination).
    tzid: str | None = None
    if category not in _TRANSIT_CATEGORIES:
        tzid = tz_lookup.get(title)

    desc_parts = []
    if category:
        desc_parts.append(f"Category: {category.title()}")
    if notes:
        desc_parts.append(notes)
    if website:
        desc_parts.append(f"Website: {website}")
    description = "\n".join(desc_parts) if desc_parts else None

    if category in _SPAN_CATEGORIES and end_date_str:
        return _build_span_events(
            title,
            category,
            day_date,
            end_date_str,
            item_time,
            location,
            description,
            uid_prefix,
            now_utc,
            tzid,
        )

    return [
        _build_timed_event(
            title,
            day_date,
            item_time,
            item_end_time,
            end_date_str,
            location,
            description,
            uid_prefix,
            now_utc,
            tzid,
        )
    ]


def _build_span_events(
    title: str,
    category: str,
    day_date: _date,
    end_date_str: str,
    item_time: str | None,
    location: str,
    description: str | None,
    uid_prefix: str,
    now_utc: datetime,
    tzid: str | None,
) -> list[Event]:
    """Two events for a multi-day stay or rental."""
    try:
        end_date = _date.fromisoformat(end_date_str)
    except ValueError:
        end_date = day_date

    events: list[Event] = []

    # All-day span event (the colored bar across the calendar week view).
    # DTEND is exclusive for all-day events per RFC 5545.
    span = Event()
    span.add("UID", f"{uid_prefix}-span@libertas.app")
    span.add("DTSTAMP", now_utc)
    span.add("SUMMARY", title)
    span.add("DTSTART", day_date)
    span.add("DTEND", end_date + timedelta(days=1))
    if location:
        span.add("LOCATION", location)
    if description:
        span.add("DESCRIPTION", description)
    events.append(span)

    # Timed companion event on the start day for the check-in/pickup time.
    # Always 1 hour long: end_time on a rental/hotel is the dropoff/checkout
    # time on end_date, not a duration for this event.
    if item_time:
        start_hm = _parse_hhmm(item_time)
        if start_hm:
            start = datetime.combine(
                day_date,
                datetime.min.time().replace(hour=start_hm[0], minute=start_hm[1]),
            )
            end = start + timedelta(hours=1)
            label = _CHECKIN_LABEL.get(category, "")
            checkin = Event()
            checkin.add("UID", f"{uid_prefix}-checkin@libertas.app")
            checkin.add("DTSTAMP", now_utc)
            checkin.add("SUMMARY", label + title)
            checkin.add("DTSTART", _dtstart(start, tzid))
            checkin.add("DTEND", _dtstart(end, tzid))
            if location:
                checkin.add("LOCATION", location)
            events.append(checkin)

    return events


def _build_timed_event(
    title: str,
    day_date: _date,
    item_time: str | None,
    item_end_time: str | None,
    end_date_str: str | None,
    location: str,
    description: str | None,
    uid_prefix: str,
    now_utc: datetime,
    tzid: str | None,
) -> Event:
    """Single timed (or all-day) event for flights, meals, activities, etc."""
    event = Event()
    event.add("UID", f"{uid_prefix}@libertas.app")
    event.add("DTSTAMP", now_utc)
    event.add("SUMMARY", title)

    if item_time:
        start_hm = _parse_hhmm(item_time)
        if start_hm is None:
            event.add("DTSTART", day_date)
            event.add("DTEND", day_date)
        else:
            start = datetime.combine(
                day_date,
                datetime.min.time().replace(hour=start_hm[0], minute=start_hm[1]),
            )
            end_hm = _parse_hhmm(item_end_time) if item_end_time else None

            # End-date resolution priority:
            #   1. explicit item["end_date"] (cross-day flights)
            #   2. inferred next-day if end_time < start_time (red-eye, midnight crossings)
            #   3. same day as start
            end_date = day_date
            if end_date_str:
                try:
                    end_date = _date.fromisoformat(end_date_str)
                except ValueError:
                    pass
            elif end_hm and (end_hm[0], end_hm[1]) < (start_hm[0], start_hm[1]):
                end_date = day_date + timedelta(days=1)

            end = (
                datetime.combine(
                    end_date,
                    datetime.min.time().replace(hour=end_hm[0], minute=end_hm[1]),
                )
                if end_hm
                else start + timedelta(hours=1)
            )
            event.add("DTSTART", _dtstart(start, tzid))
            event.add("DTEND", _dtstart(end, tzid))
    else:
        event.add("DTSTART", day_date)
        event.add("DTEND", day_date)

    if location:
        event.add("LOCATION", location)
    if description:
        event.add("DESCRIPTION", description)

    return event


def _dtstart(dt: datetime, tzid: str | None):
    """Return a vDatetime tagged with TZID, or a floating datetime if tzid is None."""
    if tzid:
        v = vDatetime(dt)
        v.params["TZID"] = tzid
        return v
    return dt


def _parse_hhmm(value: str) -> tuple[int, int] | None:
    """Parse 'HH:MM' into (hour, minute), or None if malformed."""
    try:
        h, m = value.split(":", 1)
        return int(h), int(m)
    except (ValueError, AttributeError):
        return None
