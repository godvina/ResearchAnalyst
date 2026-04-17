"""Unit tests for frontend input validation (Requirement 6.7)."""

import pytest

from src.frontend.validation import (
    validate_topic_name,
    validate_description,
    validate_analyst_note,
    validate_search_query,
    validate_graph_name,
    validate_confidence_threshold,
    validate_top_k,
    validate_entity_tags,
    MAX_TOPIC_NAME_LEN,
    MAX_DESCRIPTION_LEN,
    MAX_NOTE_LEN,
    MAX_QUERY_LEN,
    MAX_GRAPH_NAME_LEN,
)


class TestValidateTopicName:
    def test_valid(self):
        assert validate_topic_name("Ancient Aliens").valid is True

    def test_empty(self):
        r = validate_topic_name("")
        assert r.valid is False
        assert "required" in r.error.lower()

    def test_whitespace_only(self):
        assert validate_topic_name("   ").valid is False

    def test_too_long(self):
        r = validate_topic_name("x" * (MAX_TOPIC_NAME_LEN + 1))
        assert r.valid is False
        assert "255" in r.error

    def test_control_chars_rejected(self):
        r = validate_topic_name("bad\x00input")
        assert r.valid is False


class TestValidateDescription:
    def test_valid(self):
        assert validate_description("A research case about pyramids.").valid is True

    def test_empty(self):
        assert validate_description("").valid is False

    def test_too_long(self):
        r = validate_description("x" * (MAX_DESCRIPTION_LEN + 1))
        assert r.valid is False


class TestValidateAnalystNote:
    def test_valid(self):
        assert validate_analyst_note("Observed pattern between Giza and Nazca.").valid is True

    def test_empty(self):
        assert validate_analyst_note("").valid is False

    def test_too_long(self):
        r = validate_analyst_note("x" * (MAX_NOTE_LEN + 1))
        assert r.valid is False


class TestValidateSearchQuery:
    def test_valid(self):
        assert validate_search_query("What connections exist between pyramids?").valid is True

    def test_empty(self):
        assert validate_search_query("").valid is False

    def test_too_long(self):
        r = validate_search_query("x" * (MAX_QUERY_LEN + 1))
        assert r.valid is False


class TestValidateGraphName:
    def test_valid(self):
        assert validate_graph_name("Pyramid Connections").valid is True

    def test_empty(self):
        assert validate_graph_name("").valid is False

    def test_too_long(self):
        r = validate_graph_name("x" * (MAX_GRAPH_NAME_LEN + 1))
        assert r.valid is False


class TestValidateConfidenceThreshold:
    def test_valid_range(self):
        assert validate_confidence_threshold(0.0).valid is True
        assert validate_confidence_threshold(0.5).valid is True
        assert validate_confidence_threshold(1.0).valid is True

    def test_below_range(self):
        assert validate_confidence_threshold(-0.1).valid is False

    def test_above_range(self):
        assert validate_confidence_threshold(1.1).valid is False


class TestValidateTopK:
    def test_valid(self):
        assert validate_top_k(1).valid is True
        assert validate_top_k(50).valid is True
        assert validate_top_k(100).valid is True

    def test_below_range(self):
        assert validate_top_k(0).valid is False

    def test_above_range(self):
        assert validate_top_k(101).valid is False


class TestValidateEntityTags:
    def test_valid(self):
        assert validate_entity_tags("Giza, Nazca Lines").valid is True

    def test_empty_is_ok(self):
        assert validate_entity_tags("").valid is True

    def test_extra_commas(self):
        r = validate_entity_tags("Giza,,Nazca")
        assert r.valid is False
        assert "Empty tag" in r.error

    def test_tag_too_long(self):
        r = validate_entity_tags("x" * 256)
        assert r.valid is False
