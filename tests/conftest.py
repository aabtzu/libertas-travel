import os

import pytest


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "integration: marks tests that require a live ANTHROPIC_API_KEY"
    )


@pytest.fixture
def app():
    """Create a Flask app configured for testing (AUTH_DISABLED, SQLite)."""
    os.environ["AUTH_DISABLED"] = "true"
    os.environ["SECRET_KEY"] = "test-secret"
    # Routes that render trips construct an LLM client (ItineraryWebView →
    # ItinerarySummarizer). Unit tests must not require a live key — set a
    # dummy if one is missing or empty. CI does the same; see 2eb312a.
    # (setdefault won't help: the parent shell may export an empty string.)
    if not os.environ.get("ANTHROPIC_API_KEY"):
        os.environ["ANTHROPIC_API_KEY"] = "test-dummy-key"

    import database as db
    from app import create_app

    db.init_db()

    flask_app = create_app()
    flask_app.config["TESTING"] = True
    yield flask_app


@pytest.fixture
def client(app):
    """Flask test client with auth disabled."""
    return app.test_client()
