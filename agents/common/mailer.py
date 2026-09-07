"""Thin outbound email wrapper.

Single call site for all app-generated email. Holds the FROM address,
handles provider failures without propagating into request paths, and
provides a kill switch via MAIL_DISABLED env var.

Provider config (in priority order):
  SENDGRID_API_KEY  - SendGrid HTTP API
  SMTP_HOST / SMTP_PORT / SMTP_USER / SMTP_PASS  - SMTP fallback

Both are read at call time by fiat_lux_agents.auth.email.send.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

_FROM_EMAIL = os.environ.get("FROM_EMAIL", "noreply@libertas-travel.onrender.com")
_APP_URL = os.environ.get("APP_URL", "https://libertas-travel.onrender.com")


def send_mail(to: str, subject: str, body_html: str) -> bool:
    """Send an email. Returns True on success, False on failure. Never raises."""
    if os.environ.get("MAIL_DISABLED", "").lower() in ("1", "true", "yes"):
        logger.info("[mailer] MAIL_DISABLED - skipping send to %s", to)
        return False
    try:
        from fiat_lux_agents.auth.email import send

        send(to=to, subject=subject, body_html=body_html, from_email=_FROM_EMAIL)
        logger.info("[mailer] sent %r to %s", subject, to)
        return True
    except Exception as exc:
        logger.error("[mailer] failed to send %r to %s: %s", subject, to, exc)
        return False


def _trip_url(trip_link: str) -> str:
    base = _APP_URL.rstrip("/")
    link = trip_link.rstrip("/")
    return f"{base}/{link}"


def send_import_confirmation(
    to: str,
    n_items: int,
    trip_title: str,
    trip_link: str,
    merged: bool,
) -> bool:
    """Tell the user their forwarded email was successfully imported."""
    action = "added to" if merged else "saved as a new draft trip"
    subject = f"Imported {n_items} item{'s' if n_items != 1 else ''} - Libertas"
    url = _trip_url(trip_link)
    body_html = f"""
<p>Hi,</p>
<p>We imported {n_items} item{"s" if n_items != 1 else ""} from your forwarded email
and {action} <strong>{trip_title}</strong>.</p>
<p><a href="{url}" style="background:#667eea;color:white;padding:10px 20px;
border-radius:6px;text-decoration:none;display:inline-block;margin:8px 0;">
View trip</a></p>
<p style="color:#666;font-size:13px;">Libertas trip planner</p>
"""
    return send_mail(to, subject, body_html)


def send_nothing_extracted(to: str, subject: str) -> bool:
    """Tell the user we received their email but couldn't extract any items."""
    email_subject = "We received your email but couldn't extract items - Libertas"
    body_html = f"""
<p>Hi,</p>
<p>We received your forwarded email ("{subject}") but couldn't extract any
flight, hotel, or activity items from it.</p>
<p>This can happen with plain-text confirmation emails, heavily formatted HTML,
or emails that don't contain booking details. Try forwarding the original
confirmation email rather than a forward of a forward.</p>
<p style="color:#666;font-size:13px;">Libertas trip planner</p>
"""
    return send_mail(to, email_subject, body_html)


def send_unrecognised_sender(to: str) -> bool:
    """Tell an unrecognised sender that their address isn't linked to an account."""
    subject = "Email not recognised - Libertas"
    body_html = f"""
<p>Hi,</p>
<p>We received an email forwarded to Libertas from this address, but we couldn't
match it to a Libertas account.</p>
<p>If you have a Libertas account, make sure you're forwarding from the email
address you used to sign up, or add this address under
<strong>Forwarding addresses</strong> in your profile.</p>
<p><a href="{_APP_URL}/profile" style="background:#667eea;color:white;
padding:10px 20px;border-radius:6px;text-decoration:none;display:inline-block;
margin:8px 0;">Go to profile</a></p>
<p style="color:#666;font-size:13px;">Libertas trip planner</p>
"""
    return send_mail(to, subject, body_html)
