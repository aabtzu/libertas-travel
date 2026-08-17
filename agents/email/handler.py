"""Email inbound handler: parse forwarded booking confirmations into trip items."""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from typing import Any

import database as db
from agents.create.upload_handlers import upload_plan_handler

logger = logging.getLogger(__name__)

# Prefixes to strip when deriving a trip title from an email subject
_SUBJECT_PREFIX_RE = re.compile(r"^\s*(fwd?|re)\s*:\s*", re.IGNORECASE)


def _extract_sender_email(from_header: str) -> str:
    """Pull the bare email address out of a From header like 'Name <addr@example.com>'."""
    match = re.search(r"<([^>]+)>", from_header)
    if match:
        return match.group(1).strip().lower()
    return from_header.strip().lower()


def _clean_subject(subject: str) -> str:
    """Strip reply/forward prefixes and return a clean title string."""
    title = subject.strip()
    # Remove chains like "Re: Fwd: Re: ..."
    while _SUBJECT_PREFIX_RE.match(title):
        title = _SUBJECT_PREFIX_RE.sub("", title)
    return title.strip() or "Email trip"


def _save_email_items_as_draft(user_id: int, subject: str, items: list[dict]) -> str | None:
    """Convert a flat items list into itinerary_data and save as a new draft trip.

    Items that carry a date are grouped into days; items without a date go into
    ideas. Returns the trip link on success, or None if the DB write fails.
    """
    title = _clean_subject(subject)

    # Group by date
    days_dict: dict[str, list[dict]] = defaultdict(list)
    ideas: list[dict] = []
    for item in items:
        date = item.get("date")
        if date:
            days_dict[date].append(item)
        else:
            ideas.append(item)

    # Build days list sorted chronologically
    sorted_dates = sorted(days_dict.keys())
    start_date = sorted_dates[0] if sorted_dates else None
    end_date = sorted_dates[-1] if sorted_dates else None

    days = [
        {"day_number": idx + 1, "date": date, "items": days_dict[date]}
        for idx, date in enumerate(sorted_dates)
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


def process_inbound_email(form_data: dict, files: dict) -> dict[str, Any]:
    """Process a SendGrid Inbound Parse webhook POST.

    Identifies the Libertas user by matching the sender email, then runs the
    body/attachments through the same parser used for file uploads.

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
        print(
            f"[email-inbound] text_len={len(body)} html_len={len(html_body)} preview={body[:200]!r}",
            flush=True,
        )

        # Prefer plain text; strip HTML tags as a last resort
        content = body if body.strip() else re.sub(r"<[^>]+>", " ", html_body)
        content = content.strip()

        if content:
            result, _status = upload_plan_handler(
                user_id, f"{subject}.txt", content.encode("utf-8"), "txt"
            )
            if result.get("success") and result.get("items"):
                results.extend(result["items"])

    trip_link = None
    if results:
        trip_link = _save_email_items_as_draft(user_id, subject, results)
        if trip_link:
            print(f"[email-inbound] saved draft trip link={trip_link}", flush=True)
        else:
            logger.error("[email-inbound] failed to save draft trip for user_id=%s", user_id)

    return {
        "success": True,
        "user_id": user_id,
        "username": user["username"],
        "items_extracted": len(results),
        "trip_link": trip_link,
    }
