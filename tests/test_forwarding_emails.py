"""Tests for forwarding email addresses (issue #151)."""

from __future__ import annotations


class TestForwardingEmailDB:
    def test_add_and_list(self, app):
        import database as db

        with app.app_context():
            user_id = db.ensure_demo_user()
            db.remove_forwarding_email(user_id, "fwd@test.com")  # clean up first

            added = db.add_forwarding_email(user_id, "fwd@test.com")
            assert added is True
            emails = db.get_forwarding_emails(user_id)
            assert "fwd@test.com" in emails

            db.remove_forwarding_email(user_id, "fwd@test.com")

    def test_add_duplicate_returns_false(self, app):
        import database as db

        with app.app_context():
            user_id = db.ensure_demo_user()
            db.remove_forwarding_email(user_id, "dup@test.com")

            db.add_forwarding_email(user_id, "dup@test.com")
            second = db.add_forwarding_email(user_id, "dup@test.com")
            assert second is False

            db.remove_forwarding_email(user_id, "dup@test.com")

    def test_remove_returns_false_if_missing(self, app):
        import database as db

        with app.app_context():
            user_id = db.ensure_demo_user()
            removed = db.remove_forwarding_email(user_id, "nothere@test.com")
            assert removed is False

    def test_get_user_by_forwarding_email(self, app):
        import database as db

        with app.app_context():
            user_id = db.ensure_demo_user()
            db.add_forwarding_email(user_id, "secondary@test.com")

            user = db.get_user_by_email("secondary@test.com")
            assert user is not None
            assert user["id"] == user_id

            db.remove_forwarding_email(user_id, "secondary@test.com")

    def test_get_user_by_forwarding_email_case_insensitive(self, app):
        import database as db

        with app.app_context():
            user_id = db.ensure_demo_user()
            db.add_forwarding_email(user_id, "UPPER@test.com")

            user = db.get_user_by_email("upper@test.com")
            assert user is not None

            db.remove_forwarding_email(user_id, "UPPER@test.com")

    def test_primary_email_still_works(self, app):
        import database as db

        with app.app_context():
            user_id = db.ensure_demo_user()
            user = db.get_user_by_id(user_id)
            primary_email = user["email"]

            result = db.get_user_by_email(primary_email)
            assert result is not None
            assert result["id"] == user_id


class TestForwardingEmailAPI:
    def test_list_empty(self, client):
        res = client.get("/api/user/forwarding-emails")
        assert res.status_code == 200
        data = res.get_json()
        assert "emails" in data

    def test_add_and_list(self, client):
        res = client.post(
            "/api/user/forwarding-emails",
            json={"email": "apitest@example.com"},
        )
        assert res.status_code == 200
        assert res.get_json()["email"] == "apitest@example.com"

        res = client.get("/api/user/forwarding-emails")
        assert "apitest@example.com" in res.get_json()["emails"]

        client.delete("/api/user/forwarding-emails/apitest@example.com")

    def test_add_invalid_email(self, client):
        res = client.post(
            "/api/user/forwarding-emails",
            json={"email": "notanemail"},
        )
        assert res.status_code == 400

    def test_add_duplicate_returns_409(self, client):
        client.post("/api/user/forwarding-emails", json={"email": "dup2@example.com"})
        res = client.post("/api/user/forwarding-emails", json={"email": "dup2@example.com"})
        assert res.status_code == 409
        client.delete("/api/user/forwarding-emails/dup2@example.com")

    def test_delete_not_found(self, client):
        res = client.delete("/api/user/forwarding-emails/missing@example.com")
        assert res.status_code == 404

    def test_delete_removes_address(self, client):
        client.post("/api/user/forwarding-emails", json={"email": "del@example.com"})
        res = client.delete("/api/user/forwarding-emails/del@example.com")
        assert res.status_code == 200
        emails = client.get("/api/user/forwarding-emails").get_json()["emails"]
        assert "del@example.com" not in emails
