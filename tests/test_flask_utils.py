"""Unit tests for agents/common/flask_utils.py — auth middleware and response helpers."""

from __future__ import annotations

import os

import pytest
from flask import Flask, g

from agents.common.flask_utils import json_err, json_ok, load_current_user, require_auth

# ---------------------------------------------------------------------------
# App fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def app():
    """Minimal Flask app with the auth utils wired in."""
    flask_app = Flask(__name__)
    flask_app.secret_key = "test-secret"
    flask_app.config["TESTING"] = True

    @flask_app.before_request
    def before():
        load_current_user()

    @flask_app.get("/api/protected")
    @require_auth
    def api_protected():
        return json_ok({"user_id": g.user_id})

    @flask_app.get("/page/protected")
    @require_auth
    def page_protected():
        return "<h1>Secret</h1>", 200

    @flask_app.get("/api/public")
    def api_public():
        return json_ok({"ok": True})

    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


# ---------------------------------------------------------------------------
# load_current_user
# ---------------------------------------------------------------------------


class TestLoadCurrentUser:
    def test_no_session_no_auth_disabled(self, app, client):
        with app.test_request_context("/"):
            os.environ.pop("AUTH_DISABLED", None)
            load_current_user()
            assert g.user_id is None
            assert g.auth_disabled is False

    def test_session_sets_user_id(self, app, client):
        with client.session_transaction() as sess:
            sess["user_id"] = 42
            sess["username"] = "alice"
        with client:
            resp = client.get("/api/protected")
            assert resp.status_code == 200
            assert resp.get_json()["user_id"] == 42

    def test_auth_disabled_sets_user_id_1(self, app, client, monkeypatch):
        monkeypatch.setenv("AUTH_DISABLED", "true")
        with client:
            resp = client.get("/api/protected")
            assert resp.status_code == 200
            assert resp.get_json()["user_id"] == 1

    def test_auth_disabled_false_string_not_disabled(self, app, client, monkeypatch):
        monkeypatch.setenv("AUTH_DISABLED", "false")
        resp = client.get("/api/protected")
        assert resp.status_code == 401

    def test_auth_disabled_uppercase(self, app, client, monkeypatch):
        monkeypatch.setenv("AUTH_DISABLED", "TRUE")
        with client:
            resp = client.get("/api/protected")
            assert resp.status_code == 200


# ---------------------------------------------------------------------------
# require_auth
# ---------------------------------------------------------------------------


class TestRequireAuth:
    def test_api_route_unauthenticated_returns_401(self, client, monkeypatch):
        monkeypatch.delenv("AUTH_DISABLED", raising=False)
        resp = client.get("/api/protected")
        assert resp.status_code == 401
        assert resp.get_json()["error"] == "Unauthorized"

    def test_page_route_unauthenticated_redirects(self, client, monkeypatch):
        monkeypatch.delenv("AUTH_DISABLED", raising=False)
        resp = client.get("/page/protected")
        assert resp.status_code == 302
        assert "login" in resp.headers["Location"]

    def test_page_redirect_includes_path(self, client, monkeypatch):
        monkeypatch.delenv("AUTH_DISABLED", raising=False)
        resp = client.get("/page/protected")
        assert "/page/protected" in resp.headers["Location"]

    def test_authenticated_api_passes_through(self, app, client):
        with client.session_transaction() as sess:
            sess["user_id"] = 7
        with client:
            resp = client.get("/api/protected")
            assert resp.status_code == 200

    def test_authenticated_page_passes_through(self, app, client):
        with client.session_transaction() as sess:
            sess["user_id"] = 7
        resp = client.get("/page/protected")
        assert resp.status_code == 200

    def test_public_route_always_accessible(self, client, monkeypatch):
        monkeypatch.delenv("AUTH_DISABLED", raising=False)
        resp = client.get("/api/public")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# json_ok / json_err helpers
# ---------------------------------------------------------------------------


class TestJsonHelpers:
    def test_json_ok_status_200(self, app):
        with app.test_request_context("/"):
            resp, status = json_ok({"result": "success"})
            assert status == 200
            assert resp.get_json()["result"] == "success"

    def test_json_err_default_400(self, app):
        with app.test_request_context("/"):
            resp, status = json_err("Something went wrong")
            assert status == 400
            assert resp.get_json()["error"] == "Something went wrong"

    def test_json_err_custom_status(self, app):
        with app.test_request_context("/"):
            resp, status = json_err("Not found", 404)
            assert status == 404

    def test_json_err_includes_success_false(self, app):
        with app.test_request_context("/"):
            resp, _ = json_err("oops")
            assert resp.get_json()["success"] is False
