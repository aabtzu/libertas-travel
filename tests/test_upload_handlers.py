"""Tests for upload handler entry points.

The /trips upload (``upload_file_handler``) and the in-trip upload
(``upload_plan_handler``) are two separate code paths that take different
file types. These unit tests pin down which extensions each path supports
without requiring a live LLM, the LLM call is mocked.

Backstory: a 2517-line handler.py was split into focused modules (commit
1ef25bb) and the image-upload branch silently lost its vision-API call.
PNG uploads started 400-ing on /trips for weeks before a user reported
it. These tests exist so that can't happen again.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from agents.create.upload_handlers import upload_file_handler
from agents.itinerary.parser import Itinerary

# A real 1x1 transparent PNG, smallest possible. Avoids needing Pillow as
# a test dep just to generate a valid file header.
_TINY_PNG_BYTES = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
    "890000000d49444154789c6300010000000500010d0a2db40000000049454e44"
    "ae426082"
)


@pytest.fixture
def stub_itinerary():
    """Empty Itinerary stub for parser mocks."""
    return Itinerary(title="Test Trip", items=[])


def test_png_upload_routes_to_vision_parser(stub_itinerary, tmp_path, app):
    """Regression: PNG goes through ``parser.parse_image``, not parse_file.

    If someone refactors and accidentally drops the image branch again,
    this test fails immediately instead of waiting for a friend to email.
    """
    with (
        patch("agents.itinerary.parser.ItineraryParser") as parser_cls,
        patch("agents.itinerary.web_view.ItineraryWebView") as web_view_cls,
        patch("agents.itinerary.geocoding_worker.queue_geocoding"),
        patch("agents.create.upload_handlers.db.add_trip", return_value=1),
    ):
        parser_cls.return_value.parse_image.return_value = stub_itinerary
        web_view_cls.return_value.generate.return_value = None

        result, status = upload_file_handler(
            user_id=1,
            file_data=_TINY_PNG_BYTES,
            filename="boarding_pass.png",
            output_dir=tmp_path,
        )

        assert status == 200, f"PNG upload returned {status}: {result}"
        assert result.get("success") is True
        # The whole point: vision path was used, not the text path.
        parser_cls.return_value.parse_image.assert_called_once()
        parser_cls.return_value.parse_file.assert_not_called()


def test_jpg_upload_also_uses_vision_parser(stub_itinerary, tmp_path, app):
    """Same regression check for JPG. extract_file_content treats jpg/jpeg
    the same way; this just pins the behavior."""
    with (
        patch("agents.itinerary.parser.ItineraryParser") as parser_cls,
        patch("agents.itinerary.web_view.ItineraryWebView") as web_view_cls,
        patch("agents.itinerary.geocoding_worker.queue_geocoding"),
        patch("agents.create.upload_handlers.db.add_trip", return_value=1),
    ):
        parser_cls.return_value.parse_image.return_value = stub_itinerary
        web_view_cls.return_value.generate.return_value = None

        # Re-use the PNG bytes; the dispatch is purely on file extension,
        # and avoiding a real JPG keeps the test data minimal.
        result, status = upload_file_handler(
            user_id=1,
            file_data=_TINY_PNG_BYTES,
            filename="ticket.jpg",
            output_dir=tmp_path,
        )

        assert status == 200, f"JPG upload returned {status}: {result}"
        parser_cls.return_value.parse_image.assert_called_once()


def test_unsupported_extension_returns_400(tmp_path, app):
    """Confirm the supported-extension gate still rejects junk."""
    result, status = upload_file_handler(
        user_id=1,
        file_data=b"<exe>",
        filename="malware.exe",
        output_dir=tmp_path,
    )
    assert status == 400
    assert "Unsupported" in result.get("error", "")
