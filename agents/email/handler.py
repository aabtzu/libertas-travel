"""Email inbound handler: parse forwarded booking confirmations into trip items."""

from __future__ import annotations

import email as email_lib
import json
import logging
import os
import re
from collections import defaultdict
from datetime import date, timedelta
from typing import Any

import anthropic

import database as db
from agents.create.upload_handlers import upload_plan_handler

logger = logging.getLogger(__name__)

# Prefixes to strip when deriving a trip title from an email subject
_SUBJECT_PREFIX_RE = re.compile(r"^\s*(fwd?|re)\s*:\s*", re.IGNORECASE)

# Marker Gmail inserts at the start of a forwarded message block
_FORWARD_MARKER_RE = re.compile(
    r"^-{3,}\s*Forwarded message\s*-{3,}",
    re.IGNORECASE | re.MULTILINE,
)

# Trips that ended more than this many days ago are ignored for auto-routing
_RECENCY_CUTOFF_DAYS = 180

_HAIKU_MODEL = "claude-haiku-4-5-20251001"


def _extract_sender_email(from_header: str) -> str:
    """Pull the bare email address out of a From header like 'Name <addr@example.com>'."""
    match = re.search(r"<([^>]+)>", from_header)
    if match:
        return match.group(1).strip().lower()
    return from_header.strip().lower()


def _clean_subject(subject: str) -> str:
    """Strip reply/forward prefixes and return a clean title string."""
    title = subject.strip()
    while _SUBJECT_PREFIX_RE.match(title):
        title = _SUBJECT_PREFIX_RE.sub("", title)
    return title.strip() or "Email trip"


def _extract_user_instruction(body: str) -> str:
    """Return text the user typed above the forwarded-message marker, if any."""
    match = _FORWARD_MARKER_RE.search(body)
    if not match:
        return ""
    prefix = body[: match.start()].strip()
    return prefix


def _trip_date_range(itinerary_data: dict) -> tuple[str, str]:
    """Return (start_date, end_date) for a trip, falling back to days array if needed."""
    start = itinerary_data.get("start_date") or ""
    end = itinerary_data.get("end_date") or ""
    if start and end:
        return start, end
    # Derive from days array when top-level fields are absent
    day_dates = [d["date"] for d in itinerary_data.get("days", []) if d.get("date")]
    if day_dates:
        return min(day_dates), max(day_dates)
    return "", ""


def _candidate_trips(user_id: int) -> list[dict]:
    """Return non-archived trips with parsed itinerary_data, recency-filtered."""
    cutoff = (date.today() - timedelta(days=_RECENCY_CUTOFF_DAYS)).isoformat()
    trips = db.get_user_trips(user_id)
    candidates = []
    for t in trips:
        if t.get("is_archived"):
            continue
        raw = t.get("itinerary_data")
        if isinstance(raw, str):
            try:
                t["itinerary_data"] = json.loads(raw)
            except Exception:
                t["itinerary_data"] = {}
        elif not isinstance(raw, dict):
            t["itinerary_data"] = {}
        _, end = _trip_date_range(t["itinerary_data"])
        # Keep trips with no end date (undated/ongoing) or end date within cutoff
        if end and end < cutoff:
            continue
        candidates.append(t)
    return candidates


def _match_by_instruction(instruction: str, trips: list[dict]) -> dict | None:
    """Use Haiku to extract a trip name from the instruction, then fuzzy-match."""
    if not instruction.strip():
        return None

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return None

    client = anthropic.Anthropic(api_key=api_key)
    trip_titles = [t["title"] for t in trips if t.get("title")]
    if not trip_titles:
        return None

    titles_list = "\n".join(f"- {t}" for t in trip_titles)
    prompt = (
        f'The user typed this instruction before forwarding an email:\n"{instruction}"\n\n'
        f"Available trips:\n{titles_list}\n\n"
        "Which trip title best matches the user's instruction? "
        "Reply with ONLY the exact trip title from the list, or 'NONE' if no match is clear."
    )
    try:
        msg = client.messages.create(
            model=_HAIKU_MODEL,
            max_tokens=100,
            messages=[{"role": "user", "content": prompt}],
        )
        chosen = msg.content[0].text.strip().strip('"').strip("'")
        if chosen.upper() == "NONE" or not chosen:
            return None
        for t in trips:
            if t.get("title", "").strip() == chosen:
                return t
        # Fallback: case-insensitive partial match
        chosen_lower = chosen.lower()
        for t in trips:
            if chosen_lower in (t.get("title") or "").lower():
                return t
    except Exception as e:
        print(f"[email-inbound] Haiku instruction match failed: {e}", flush=True)
    return None


def _match_by_dates(item_dates: list[str], trips: list[dict]) -> dict | None:
    """Return the single trip whose date range overlaps the item dates, or None."""
    if not item_dates:
        return None
    min_date = min(item_dates)
    max_date = max(item_dates)
    matches = []
    for t in trips:
        start, end = _trip_date_range(t["itinerary_data"])
        if not start or not end:
            continue
        # Overlap: item range intersects trip range
        if start <= max_date and end >= min_date:
            matches.append(t)
    if len(matches) == 1:
        return matches[0]
    return None


def _merge_items_into_trip(user_id: int, trip: dict, items: list[dict]) -> bool:
    """Append new items into an existing trip's itinerary_data in-place."""
    itinerary_data = trip["itinerary_data"]
    days: list[dict] = itinerary_data.get("days") or []
    ideas: list[dict] = itinerary_data.get("ideas") or []

    days_by_date = {d["date"]: d for d in days if d.get("date")}

    for item in items:
        item_date = item.get("date")
        if item_date and item_date in days_by_date:
            days_by_date[item_date].setdefault("items", []).append(item)
        elif item_date:
            # New date not yet in the trip - add a day entry
            new_day = {"date": item_date, "items": [item]}
            days.append(new_day)
            days_by_date[item_date] = new_day
        else:
            ideas.append(item)

    # Re-sort days chronologically and renumber
    days.sort(key=lambda d: d.get("date") or "")
    for idx, day in enumerate(days):
        day["day_number"] = idx + 1

    itinerary_data["days"] = days
    itinerary_data["ideas"] = ideas

    # Expand trip date range if items fall outside it
    all_dates = [d["date"] for d in days if d.get("date")]
    if all_dates:
        itinerary_data["start_date"] = min(all_dates)
        itinerary_data["end_date"] = max(all_dates)

    return db.update_trip_itinerary_data(user_id, trip["link"], itinerary_data)


def _save_email_items_as_draft(user_id: int, subject: str, items: list[dict]) -> str | None:
    """Convert a flat items list into itinerary_data and save as a new draft trip."""
    title = _clean_subject(subject)

    days_dict: dict[str, list[dict]] = defaultdict(list)
    ideas: list[dict] = []
    for item in items:
        date_val = item.get("date")
        if date_val:
            days_dict[date_val].append(item)
        else:
            ideas.append(item)

    sorted_dates = sorted(days_dict.keys())
    start_date = sorted_dates[0] if sorted_dates else None
    end_date = sorted_dates[-1] if sorted_dates else None

    days = [
        {"day_number": idx + 1, "date": d, "items": days_dict[d]}
        for idx, d in enumerate(sorted_dates)
    ]

    itinerary_data = {
        "title": title,
        "start_date": start_date,
        "end_date": end_date,
        "travelers": [],
        "days": days,
        "ideas": ideas,
    }

    trip = db.create_draft_trip(
        user_id=user_id,
        title=title,
        start_date=start_date,
        end_date=end_date,
    )
    if not trip:
        logger.error("[email-inbound] create_draft_trip failed for user_id=%s", user_id)
        return None

    link = trip["link"]
    ok = db.update_trip_itinerary_data(user_id, link, itinerary_data)
    if not ok:
        logger.warning(
            "[email-inbound] update_trip_itinerary_data returned False for link=%s", link
        )

    return link


def _extract_body_from_raw_mime(raw_mime: str) -> tuple[str, str]:
    """Parse a raw MIME email string and return (plain_text, html_text)."""
    msg = email_lib.message_from_string(raw_mime)
    plain = ""
    html = ""
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            if ct == "text/plain" and not plain:
                payload = part.get_payload(decode=True)
                if payload:
                    plain = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
            elif ct == "text/html" and not html:
                payload = part.get_payload(decode=True)
                if payload:
                    html = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            text = payload.decode(msg.get_content_charset() or "utf-8", errors="replace")
            if msg.get_content_type() == "text/html":
                html = text
            else:
                plain = text
    return plain, html


def _route_items_to_trip(
    user_id: int,
    subject: str,
    items: list[dict],
    user_instruction: str,
) -> tuple[str | None, bool]:
    """Decide where items go and save them. Returns (trip_link, merged_into_existing).

    Priority:
    1. Explicit user instruction above the forwarded-message marker
    2. Date overlap with a single existing trip
    3. New draft
    """
    candidates = _candidate_trips(user_id)

    # 1. Explicit instruction
    matched = _match_by_instruction(user_instruction, candidates)
    if matched:
        print(
            f"[email-inbound] routing by instruction -> trip={matched['title']!r}",
            flush=True,
        )
        ok = _merge_items_into_trip(user_id, matched, items)
        return (matched["link"] if ok else None), True

    # 2. Date overlap
    item_dates = [item["date"] for item in items if item.get("date")]
    matched = _match_by_dates(item_dates, candidates)
    if matched:
        print(
            f"[email-inbound] routing by date overlap -> trip={matched['title']!r}",
            flush=True,
        )
        ok = _merge_items_into_trip(user_id, matched, items)
        return (matched["link"] if ok else None), True

    # 3. New draft
    print("[email-inbound] no matching trip found, creating new draft", flush=True)
    link = _save_email_items_as_draft(user_id, subject, items)
    return link, False


def process_inbound_email(form_data: dict, files: dict) -> dict[str, Any]:
    """Process a SendGrid Inbound Parse webhook POST.

    Identifies the Libertas user by matching the sender email, runs the
    body/attachments through the same parser used for file uploads, then
    routes extracted items to an existing trip or a new draft.

    Returns a result dict with keys: success, user_id, items_extracted, error.
    """
    from_header = form_data.get("from", "")
    sender_email = _extract_sender_email(from_header)

    print(f"[email-inbound] from={sender_email}", flush=True)
    user = db.get_user_by_email(sender_email)
    print(f"[email-inbound] user lookup result={user}", flush=True)
    if user is None:
        print(f"[email-inbound] no user for email={sender_email}", flush=True)
        return {
            "success": False,
            "error": f"No Libertas account found for sender: {sender_email}",
        }

    user_id = user["id"]
    subject = form_data.get("subject", "forwarded email")
    results = []
    user_instruction = ""

    # Try attachments first (PDFs, images) - they usually have richer data
    for _field_name, file_storage in files.items():
        filename = file_storage.filename or "attachment"
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext not in ("pdf", "png", "jpg", "jpeg", "gif", "webp", "xlsx", "xls"):
            continue
        file_data = file_storage.read()
        result, _status = upload_plan_handler(user_id, filename, file_data, ext)
        if result.get("success") and result.get("items"):
            results.extend(result["items"])

    # Fall back to email body text if no useful attachments
    if not results:
        body = form_data.get("text") or ""
        html_body = form_data.get("html") or ""

        # When SendGrid "POST raw MIME" is enabled, text/html may be empty.
        # Parse the raw email field ourselves.
        if not body.strip() and not html_body.strip():
            raw_mime = form_data.get("email") or ""
            if raw_mime:
                body, html_body = _extract_body_from_raw_mime(raw_mime)

        print(
            f"[email-inbound] text_len={len(body)} html_len={len(html_body)} preview={body[:200]!r}",
            flush=True,
        )

        user_instruction = _extract_user_instruction(body)
        if user_instruction:
            print(f"[email-inbound] user_instruction={user_instruction!r}", flush=True)

        content = body if body.strip() else re.sub(r"<[^>]+>", " ", html_body)
        content = content.strip()

        if content:
            result, _status = upload_plan_handler(
                user_id, f"{subject}.txt", content.encode("utf-8"), "txt"
            )
            if result.get("success") and result.get("items"):
                results.extend(result["items"])

    trip_link = None
    merged = False
    if results:
        trip_link, merged = _route_items_to_trip(user_id, subject, results, user_instruction)
        if trip_link:
            action = "merged into existing trip" if merged else "saved as new draft"
            print(f"[email-inbound] {action} link={trip_link}", flush=True)
        else:
            logger.error("[email-inbound] failed to save items for user_id=%s", user_id)

    return {
        "success": True,
        "user_id": user_id,
        "username": user["username"],
        "items_extracted": len(results),
        "trip_link": trip_link,
        "merged_into_existing": merged,
    }
