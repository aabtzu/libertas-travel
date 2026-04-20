"""Flask application factory for Libertas."""

from __future__ import annotations

import os

from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix


def create_app() -> Flask:
    app = Flask(__name__, static_folder="static", static_url_path="/static")
    app.secret_key = os.environ["SECRET_KEY"]
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

    from agents.admin.routes import admin_bp
    from agents.auth.routes import auth_bp
    from agents.create.routes import create_bp
    from agents.explore.routes import explore_bp
    from agents.pages.routes import pages_bp
    from agents.trips.routes import trips_bp

    for bp in (pages_bp, auth_bp, trips_bp, create_bp, explore_bp, admin_bp):
        app.register_blueprint(bp)

    # Run DB migrations (adds new columns if missing)
    import database as db

    db.init_db()

    @app.before_request
    def load_user():
        from agents.common.flask_utils import load_current_user

        load_current_user()

    return app


if __name__ == "__main__":
    app = create_app()
    port = int(os.environ.get("PORT", 8080))
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug, use_reloader=debug)
