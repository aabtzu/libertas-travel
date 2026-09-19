"""Auth blueprint - thin shim that delegates to fiat_lux_agents.auth.

All logic lives in the fla-auth plugin. This file just configures it
with the app's DB connection and env vars.

Extra route here: GET /api/auth/collab-invite-code?token=<collab_token>
Validates that the token is a real pending collaboration invite and if so
returns the site INVITE_CODE so the register page can pre-fill it without
the invitee needing to know it.
"""

from __future__ import annotations

import os

from fiat_lux_agents.auth import make_auth_blueprint
from flask import jsonify, request

import database as db
from database.connection import USE_POSTGRES, get_db

_APP_URL = os.environ.get("APP_URL", "https://libertas-travel.onrender.com")
_FROM_EMAIL = os.environ.get("FROM_EMAIL", "noreply@libertas-travel.onrender.com")
_INVITE_CODE = os.environ.get("INVITE_CODE", "")

auth_bp = make_auth_blueprint(
    get_connection=get_db,
    use_postgres=USE_POSTGRES,
    invite_code=_INVITE_CODE,
    secret_key=os.environ.get("SECRET_KEY", ""),
    app_url=_APP_URL,
    from_email=_FROM_EMAIL,
    app_name="Libertas",
)


@auth_bp.get("/api/auth/collab-invite-code")
def collab_invite_code():
    """Return the site INVITE_CODE when a valid collaboration invite token is provided.

    The collab token proves the caller was invited by an existing user, so
    requiring them to also know the separate site INVITE_CODE is redundant.
    Only returns the code when the token maps to a real, unaccepted invite.
    """
    token = request.args.get("token", "").strip()
    if not token or not _INVITE_CODE:
        return jsonify({"invite_code": ""}), 200
    invite = db.get_invite_by_token(token)
    if invite and not invite.get("accepted_at"):
        return jsonify({"invite_code": _INVITE_CODE}), 200
    return jsonify({"invite_code": ""}), 200
