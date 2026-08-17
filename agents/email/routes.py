"""Email blueprint: receives SendGrid Inbound Parse webhooks."""

from __future__ import annotations

import logging

from flask import Blueprint, request

from agents.email.handler import process_inbound_email

logger = logging.getLogger(__name__)

email_bp = Blueprint("email", __name__)


@email_bp.post("/api/email/inbound")
def inbound_email():
    """Receive a forwarded booking confirmation from SendGrid Inbound Parse.

    SendGrid POSTs multipart/form-data with fields: from, to, subject, text,
    html, and file attachments. We identify the user by matching the sender
    email, parse the content, and return extracted trip items.

    The response is always 200 - SendGrid retries on non-2xx, which would
    cause duplicate processing. Errors are logged instead.
    """
    result = process_inbound_email(request.form, request.files)

    if not result["success"]:
        logger.warning("Inbound email rejected: %s", result.get("error"))
        # Still return 200 so SendGrid does not retry
        return {"ok": False, "error": result["error"]}, 200

    logger.info(
        "Inbound email processed for user=%s items=%d",
        result["username"],
        result["items_extracted"],
    )
    return {
        "ok": True,
        "user": result["username"],
        "items_extracted": result["items_extracted"],
        "trip_link": result.get("trip_link"),
    }, 200
