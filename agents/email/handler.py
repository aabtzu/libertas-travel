"""Email inbound handler: parse forwarded booking confirmations into trip items."""

from __future__ import annotations

import logging
import re
from typing import Any

import database as db
from agents.create.upload_handlers import upload_plan_handler

logger = logging.getLogger(__name__)


def _extract_sender_email(from_header: str) -> str:
    """Pull the bare email address out of a From header like 'Name <addr@example.com>'."""
    match = re.search(r"<([^>]+)>", from_header)
    if match:
        return match.group(1).strip().lower()
    return from_header.strip().lower()


def process_inbound_email(form_data: dict, files: dict) -> dict[str, Any]:
    """Process a SendGrid Inbound Parse webhook POST.

    Identifies the Libertas user by matching the sender email, then runs the
    body/attachments through the same parser used for file uploads.

    Returns a result dict with keys: success, user_id, items_extracted, error.
    """
    from_header = form_data.get("from", "")
    sender_email = _extract_sender_email(from_header)

    logger.info("Inbound email from: %s", sender_email)
    user = db.get_user_by_email(sender_email)
    if user is None:
        logger.info("No user found for email: %s", sender_email)
        return {
            "success": False,
            "error": f"No Libertas account found for sender: {sender_email}",
        }

    user_id = user["id"]
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
        subject = form_data.get("subject", "forwarded email")

        # Prefer plain text; strip HTML tags as a last resort
        content = body if body.strip() else re.sub(r"<[^>]+>", " ", html_body)
        content = content.strip()

        if content:
            result, _status = upload_plan_handler(
                user_id, f"{subject}.txt", content.encode("utf-8"), "txt"
            )
            if result.get("success") and result.get("items"):
                results.extend(result["items"])

    return {
        "success": True,
        "user_id": user_id,
        "username": user["username"],
        "items_extracted": len(results),
        "items": results,
    }
