"""ICS calendar file generation from trip data.

Uses the icalendar library so escaping, line folding, and date/time
serialization match RFC 5545 by construction. The previous hand-rolled
emitter worked for the common case but had latent bugs in edge cases
(unfolded long DESCRIPTIONs, escape order, no UTC normalization).
"""

from __future__ import annotations

import hashlib
import hmac
import os
from datetime import date as _date
from datetime import datetime, timedelta

from icalendar import Calendar, Event


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


def _parse_hhmm(value: str) -> tuple[int, int] | None:
    """Parse 'HH:MM' into (hour, minute), or None if malformed."""
    try:
        h, m = value.split(":", 1)
        return int(h), int(m)
    except (ValueError, AttributeError):
        return None


def generate_ics(export_data: dict, link: str) -> str:
    """Generate ICS calendar format from trip export data.

    Returns a string (CRLF-terminated lines) suitable for serving as
    text/calendar. Each scheduled item becomes one VEVENT. Items without
    a ``date`` on their day are skipped. Items without a ``time`` become
    all-day events; with a ``time``, they get a 1-hour default unless an
    ``end_time`` is set.
    """
    title = export_data.get("title", "Trip")
    itinerary_data = export_data.get("itinerary_data", {})
    days = itinerary_data.get("days", [])

    cal = Calendar()
    cal.add("VERSION", "2.0")
    cal.add("PRODID", "-//Libertas Travel//Trip Planner//EN")
    cal.add("CALSCALE", "GREGORIAN")
    cal.add("METHOD", "PUBLISH")
    cal.add("X-WR-CALNAME", title)

    now_utc = datetime.utcnow()
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
            item_title = item.get("title", "Activity")
            item_time = item.get("time")
            item_end_time = item.get("end_time")
            item_location = item.get("location", "")
            item_notes = item.get("notes", "")
            item_category = item.get("category", "activity")
            item_website = item.get("website", "")

            event = Event()
            event.add("UID", f"{link}-{day_date_str}-{event_count}@libertas.app")
            event.add("DTSTAMP", now_utc)
            event.add("SUMMARY", item_title)

            if item_time:
                start_hm = _parse_hhmm(item_time)
                if start_hm is None:
                    # Fall back to all-day if the time string is malformed
                    event.add("DTSTART", day_date)
                    event.add("DTEND", day_date)
                else:
                    start = datetime.combine(
                        day_date, datetime.min.time().replace(hour=start_hm[0], minute=start_hm[1])
                    )
                    end_hm = _parse_hhmm(item_end_time) if item_end_time else None
                    end = (
                        datetime.combine(
                            day_date,
                            datetime.min.time().replace(hour=end_hm[0], minute=end_hm[1]),
                        )
                        if end_hm
                        else start + timedelta(hours=1)
                    )
                    event.add("DTSTART", start)
                    event.add("DTEND", end)
            else:
                # All-day event
                event.add("DTSTART", day_date)
                event.add("DTEND", day_date)

            if item_location:
                event.add("LOCATION", item_location)

            desc_parts = []
            if item_category:
                desc_parts.append(f"Category: {item_category.title()}")
            if item_notes:
                desc_parts.append(item_notes)
            if item_website:
                desc_parts.append(f"Website: {item_website}")
            if desc_parts:
                # icalendar handles the literal-newline escaping for us.
                event.add("DESCRIPTION", "\n".join(desc_parts))

            cal.add_component(event)

    # to_ical() returns bytes; the route layer wants str.
    return cal.to_ical().decode("utf-8")
