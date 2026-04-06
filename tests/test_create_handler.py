"""Tests for create/handler.py pure helper functions — no API calls needed."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.create.chat_handler import (
    _clean_response_text,
    _cross_reference_curated,
    _parse_suggested_items,
)

# ---------------------------------------------------------------------------
# _cross_reference_curated
# ---------------------------------------------------------------------------


class TestCrossReferenceCurated:
    VENUES = [
        {"name": "Nobu Malibu", "category": "restaurant"},
        {"name": "The Getty Center", "category": "attraction"},
    ]

    def test_exact_match(self):
        result = _cross_reference_curated("Nobu Malibu", self.VENUES)
        assert result is not None
        assert result["name"] == "Nobu Malibu"

    def test_case_insensitive(self):
        result = _cross_reference_curated("nobu malibu", self.VENUES)
        assert result is not None

    def test_partial_match_substring(self):
        result = _cross_reference_curated("Getty Center", self.VENUES)
        assert result is not None

    def test_no_match(self):
        result = _cross_reference_curated("Random Restaurant", self.VENUES)
        assert result is None

    def test_empty_venues(self):
        result = _cross_reference_curated("Nobu Malibu", [])
        assert result is None


# ---------------------------------------------------------------------------
# _clean_response_text
# ---------------------------------------------------------------------------


class TestCleanResponseText:
    def test_removes_json_add_items_block(self):
        text = 'Here are some great spots!\n```json\n{"add_items": [{"title": "Nobu"}]}\n```'
        result = _clean_response_text(text)
        assert "Here are some great spots!" in result
        assert "add_items" not in result
        assert "```" not in result

    def test_plain_text_unchanged(self):
        text = "Here are some restaurant suggestions for your trip."
        assert _clean_response_text(text) == text

    def test_strips_whitespace(self):
        result = _clean_response_text("  some text  ")
        assert result == "some text"


# ---------------------------------------------------------------------------
# _parse_suggested_items
# ---------------------------------------------------------------------------


class TestParseSuggestedItems:
    def test_numbered_bold_items(self):
        text = "1. **Nobu Malibu** - Great sushi\n2. **Shutters on the Beach** - Luxury hotel"
        items = _parse_suggested_items(text)
        titles = [i["title"] for i in items]
        assert "Nobu Malibu" in titles
        assert "Shutters on the Beach" in titles

    def test_bullet_bold_items(self):
        text = "- **Griffith Observatory** - Amazing views\n- **The Getty Center** - Art museum"
        items = _parse_suggested_items(text)
        titles = [i["title"] for i in items]
        assert "Griffith Observatory" in titles

    def test_curated_source_tag(self):
        venues = [{"name": "Nobu Malibu", "category": "restaurant"}]
        text = "1. **Nobu Malibu** - Great sushi\n2. **Unknown Spot** - Nice place"
        items = _parse_suggested_items(text, curated_venues=venues)
        sources = {i["title"]: i["source"] for i in items}
        assert sources.get("Nobu Malibu") == "CURATED"
        assert sources.get("Unknown Spot") == "AI_PICK"

    def test_empty_response(self):
        items = _parse_suggested_items("")
        assert items == []

    def test_skips_question_phrases(self):
        text = "1. **Want me to add it** - sure\n2. **Nobu Malibu** - great sushi"
        items = _parse_suggested_items(text)
        titles = [i["title"] for i in items]
        assert "Nobu Malibu" in titles
        assert not any("want me" in t.lower() for t in titles)
