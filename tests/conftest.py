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

    from app import create_app

    flask_app = create_app()
    flask_app.config["TESTING"] = True
    yield flask_app


@pytest.fixture
def client(app):
    """Flask test client with auth disabled."""
    return app.test_client()
