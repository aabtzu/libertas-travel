import os

import pytest


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "integration: marks tests that require a live ANTHROPIC_API_KEY"
    )


# Titles that test code creates via /api/trips/create or db.add_trip. If a test
# crashes before its try/finally cleanup runs, rows can pile up in libertas.db.
# Sweep them at session end as a safety net so the trips page stays clean.
_TEST_TRIP_TITLES = (
    "Type Test",
    "Links Test",
    "Test Trip",
    "Idea Test Trip",
    "Delete Me",
    "Day View Test",
    "Rec Route Test",
    "Active Render Test",
    "Archived Render Test",
    "Archive Test Trip",
    "Cached Test",
    "Compute Test",
)


@pytest.fixture(scope="session", autouse=True)
def _cleanup_test_trips_at_session_end():
    """Sweep stray test trips after the session — defense against test crashes."""
    yield
    try:
        from database.connection import USE_POSTGRES, get_db

        placeholders = ",".join("%s" if USE_POSTGRES else "?" for _ in _TEST_TRIP_TITLES)
        sql = f"DELETE FROM trips WHERE title IN ({placeholders})"
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(sql, _TEST_TRIP_TITLES)
    except Exception as e:
        # Never break the test session over cleanup
        print(f"[conftest] Test-trip cleanup failed: {e}")


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
