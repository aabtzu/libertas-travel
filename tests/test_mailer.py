"""Tests for agents.common.mailer and the email handler notification hooks."""

from __future__ import annotations

from unittest.mock import patch


class TestSendMail:
    def test_calls_fla_send_with_correct_args(self):
        from agents.common.mailer import send_mail

        with patch("fiat_lux_agents.auth.email.send") as mock_send:
            result = send_mail("user@example.com", "Hello", "<p>Hi</p>")

        assert result is True
        assert mock_send.call_count == 1
        _, kwargs = mock_send.call_args
        assert kwargs["to"] == "user@example.com"
        assert kwargs["subject"] == "Hello"

    def test_returns_false_on_exception(self):
        from agents.common.mailer import send_mail

        with patch("fiat_lux_agents.auth.email.send", side_effect=RuntimeError("no provider")):
            result = send_mail("user@example.com", "Hello", "<p>Hi</p>")

        assert result is False

    def test_mail_disabled_env_var_skips_send(self, monkeypatch):
        from agents.common.mailer import send_mail

        monkeypatch.setenv("MAIL_DISABLED", "true")
        with patch("fiat_lux_agents.auth.email.send") as mock_send:
            result = send_mail("user@example.com", "Hello", "<p>Hi</p>")

        assert result is False
        mock_send.assert_not_called()


class TestSendImportConfirmation:
    def test_sends_with_item_count_in_subject(self):
        from agents.common.mailer import send_import_confirmation

        with patch("agents.common.mailer.send_mail") as mock_send:
            send_import_confirmation("u@x.com", 3, "Italy Trip", "italy.html", merged=True)

        subject = mock_send.call_args[0][1]
        assert "3 items" in subject

    def test_singular_item(self):
        from agents.common.mailer import send_import_confirmation

        with patch("agents.common.mailer.send_mail") as mock_send:
            send_import_confirmation("u@x.com", 1, "Italy Trip", "italy.html", merged=False)

        subject = mock_send.call_args[0][1]
        assert "1 item" in subject
        assert "1 items" not in subject


class TestSendUnrecognisedSender:
    def test_sends_to_correct_address(self):
        from agents.common.mailer import send_unrecognised_sender

        with patch("agents.common.mailer.send_mail") as mock_send:
            send_unrecognised_sender("unknown@corp.com")

        assert mock_send.call_args[0][0] == "unknown@corp.com"


class TestShouldSendUnrecognisedNotice:
    def setup_method(self):
        # Clear the module-level cache between tests
        import agents.email.handler as h

        h._unrecognised_notice_sent.clear()

    def test_sends_first_time(self):
        from agents.email.handler import _should_send_unrecognised_notice

        assert _should_send_unrecognised_notice("x@y.com", {}) is True

    def test_rate_limited_same_day(self):
        from agents.email.handler import _should_send_unrecognised_notice

        _should_send_unrecognised_notice("x@y.com", {})  # first call records today
        assert _should_send_unrecognised_notice("x@y.com", {}) is False

    def test_skips_auto_submitted(self):
        from agents.email.handler import _should_send_unrecognised_notice

        assert (
            _should_send_unrecognised_notice("x@y.com", {"Auto-Submitted": "auto-replied"}) is False
        )

    def test_skips_bulk_precedence(self):
        from agents.email.handler import _should_send_unrecognised_notice

        assert _should_send_unrecognised_notice("x@y.com", {"Precedence": "bulk"}) is False

    def test_allows_auto_submitted_no(self):
        from agents.email.handler import _should_send_unrecognised_notice

        assert _should_send_unrecognised_notice("x@y.com", {"Auto-Submitted": "no"}) is True


class TestEmailHandlerNotifications:
    """Verify webhook still returns 200 regardless of mail outcomes."""

    def _make_form(self, sender="user@example.com"):
        return {
            "from": sender,
            "subject": "Flight confirmation",
            "text": "some body text",
            "html": "",
        }

    def test_webhook_returns_success_when_mail_raises(self):
        from agents.email.handler import process_inbound_email

        with (
            patch("agents.email.handler.db") as mock_db,
            patch("agents.email.handler.upload_plan_handler") as mock_parse,
            patch(
                "agents.email.handler.send_import_confirmation",
                side_effect=RuntimeError("smtp down"),
            ),
        ):
            mock_db.get_user_by_email.return_value = {"id": 1, "username": "amit"}
            mock_parse.return_value = ({"success": True, "items": [{"title": "Flight"}]}, 200)
            mock_db.get_user_trips.return_value = []
            mock_db.get_draft_trips.return_value = []
            mock_db.create_draft_trip.return_value = {"link": "trip.html", "title": "Trip"}
            mock_db.update_trip_itinerary_data.return_value = True
            mock_db.get_trip_by_link.return_value = {"title": "Trip"}

            result = process_inbound_email(self._make_form(), {})

        # Must succeed even though mail raised
        assert result["success"] is True

    def test_unrecognised_sender_triggers_notice(self):
        import agents.email.handler as h
        from agents.email.handler import process_inbound_email

        h._unrecognised_notice_sent.clear()

        with (
            patch("agents.email.handler.db") as mock_db,
            patch("agents.email.handler.send_unrecognised_sender") as mock_mail,
        ):
            mock_db.get_user_by_email.return_value = None
            result = process_inbound_email(self._make_form("stranger@x.com"), {})

        assert result["success"] is False
        mock_mail.assert_called_once_with("stranger@x.com")

    def test_nothing_extracted_triggers_notice(self):
        from agents.email.handler import process_inbound_email

        with (
            patch("agents.email.handler.db") as mock_db,
            patch("agents.email.handler.upload_plan_handler") as mock_parse,
            patch("agents.email.handler.send_nothing_extracted") as mock_mail,
        ):
            mock_db.get_user_by_email.return_value = {"id": 1, "username": "amit"}
            mock_parse.return_value = ({"success": True, "items": []}, 200)
            result = process_inbound_email(self._make_form(), {})

        assert result["success"] is True
        mock_mail.assert_called_once()
