"""Auth blueprint - thin shim that delegates to fiat_lux_agents.auth.

All logic lives in the fla-auth plugin. This file just configures it
with the app's DB connection and invite-code env var.
"""

from __future__ import annotations

import os

from fiat_lux_agents.auth import make_auth_blueprint

from database.connection import USE_POSTGRES, get_db

auth_bp = make_auth_blueprint(
    get_connection=get_db,
    use_postgres=USE_POSTGRES,
    invite_code=os.environ.get("INVITE_CODE", ""),
)
