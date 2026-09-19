"""Handlers for trip collaboration: invite, accept, list, remove."""

from __future__ import annotations

import os
from typing import Any

import database as db
from agents.common.mailer import send_collaboration_invite

_APP_URL = os.environ.get("APP_URL", "https://libertas-travel.onrender.com")


def _accept_url(token: str) -> str:
    return f"{_APP_URL.rstrip('/')}/api/trips/invite/accept?token={token}"


def _register_url(token: str) -> str:
    return f"{_APP_URL.rstrip('/')}/register?invite_token={token}"


def invite_handler(
    trip_link: str, invited_email: str, inviter_user_id: int
) -> tuple[dict[str, Any], int]:
    """Send a collaboration invite. Only the trip owner may invite."""
    owner_id = db.get_trip_owner(trip_link)
    if owner_id is None:
        return {"error": "Trip not found"}, 404
    if owner_id != inviter_user_id:
        return {"error": "Only the trip owner can invite collaborators"}, 403

    inviter = db.get_user_by_id(inviter_user_id)
    if not inviter:
        return {"error": "Inviter not found"}, 404

    token = db.invite_collaborator(trip_link, invited_email, inviter_user_id)
    if token is None:
        return {"error": "This email has already been invited to this trip"}, 409

    trip = db.get_trip_by_link(owner_id, trip_link)
    trip_title = trip["title"] if trip else trip_link

    existing_user = db.get_user_by_email(invited_email)
    send_collaboration_invite(
        to=invited_email,
        inviter_name=inviter.get("username", "Someone"),
        trip_title=trip_title,
        accept_url=_accept_url(token),
        register_url=_register_url(token),
        already_registered=existing_user is not None,
    )

    return {"success": True, "pending": existing_user is None}, 200


def accept_invite_handler(token: str, user_id: int) -> tuple[dict[str, Any], int]:
    """Accept a collaboration invite for the logged-in user."""
    invite = db.get_invite_by_token(token)
    if not invite:
        return {"error": "Invalid or expired invite link"}, 404
    if invite.get("accepted_at"):
        # Already accepted - just redirect to the trip
        return {"success": True, "link": invite["link"]}, 200

    ok = db.accept_invite(token, user_id)
    if not ok:
        return {"error": "Could not accept invite"}, 500

    return {"success": True, "link": invite["link"]}, 200


def list_collaborators_handler(
    trip_link: str, requester_user_id: int
) -> tuple[dict[str, Any], int]:
    """List collaborators. Only the trip owner can see the full list."""
    owner_id = db.get_trip_owner(trip_link)
    if owner_id is None:
        return {"error": "Trip not found"}, 404
    if owner_id != requester_user_id:
        return {"error": "Only the trip owner can list collaborators"}, 403

    collaborators = db.get_collaborators_for_trip(trip_link)
    result = []
    for c in collaborators:
        result.append(
            {
                "id": c["id"],
                "email": c["invited_email"],
                "username": c.get("username"),
                "role": c["role"],
                "accepted": c["accepted_at"] is not None,
            }
        )
    return {"collaborators": result}, 200


def remove_collaborator_handler(
    trip_link: str, collaborator_id: int, requester_user_id: int
) -> tuple[dict[str, Any], int]:
    """Remove a collaborator. Only the trip owner may remove."""
    owner_id = db.get_trip_owner(trip_link)
    if owner_id is None:
        return {"error": "Trip not found"}, 404
    if owner_id != requester_user_id:
        return {"error": "Only the trip owner can remove collaborators"}, 403

    ok = db.remove_collaborator(trip_link, collaborator_id)
    if not ok:
        return {"error": "Collaborator not found"}, 404
    return {"success": True}, 200
