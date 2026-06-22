"""Auth blueprint - thin shim that delegates to fiat_lux_agents.auth.

All logic lives in the fla-auth plugin. This file just configures it
with the app's DB connection and env vars.
"""

from __future__ import annotations

import os

from fiat_lux_agents.auth import make_auth_blueprint

from database.connection import USE_POSTGRES, get_db

_APP_URL = os.environ.get("APP_URL", "https://libertas-travel.onrender.com")
_FROM_EMAIL = os.environ.get("FROM_EMAIL", "noreply@libertas-travel.onrender.com")

auth_bp = make_auth_blueprint(
    get_connection=get_db,
    use_postgres=USE_POSTGRES,
    invite_code=os.environ.get("INVITE_CODE", ""),
    secret_key=os.environ.get("SECRET_KEY", ""),
    app_url=_APP_URL,
    from_email=_FROM_EMAIL,
    app_name="Libertas",
)
