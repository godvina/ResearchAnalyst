"""Tests for QuestionAnswerService JSON parsing robustness.

Verifies that _parse_json_response and _extract_text_from_analysis
handle all the edge cases from Bedrock responses.
"""
import json
import pytest
from unittest.mock import MagicMock

# We need to test the static methods directly
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from services.question_answer_service import QuestionAnswerService


class TestParseJsonResponse:
    """Test _parse_json_response with various Bedrock output formats."""

    def test_clean_json(self):
        text = '{"analysis": "Some analysis text.", "citations": []}'
        result = QuestionAnswerService._parse_json_response(text)
        assert result["analysis"] == "Some analysis text."

    def test_markdown_fenced_json(self):
        text = '```json\n{"analysis": "Fenced text.", "citations": []}\n```'
        result = QuestionAnswerService._parse_json_response(text)
        assert result["analysis"] == "Fenced text."

    def test_json_with_preamble(self):
        text = 'Here is my analysis:\n{"analysis": "After preamble.", "citations": []}'
        result = QuestionAnswerService._parse_json_response(text)
        assert result["analysis"] == "After preamble."

    def test_json_with_trailing_text(self):
        text = '{"analysis": "Main text.", "citations": []}\n\nLet me know if you need more.'
        result = QuestionAnswerService._parse_json_response(text)
        assert result["analysis"] == "Main text."

    def test_json_with_trailing_comma(self):
        text = '{"analysis": "Trailing comma.", "citations": [],}'
        result = QuestionAnswerService._parse_json_response(text)
        assert result["analysis"] == "Trailing comma."

    def test_completely_invalid(self):
        text = 'This is just plain text with no JSON at all.'
        result = QuestionAnswerService._parse_json_response(text)
        assert result == {}

    def test_empty_string(self):
        result = QuestionAnswerService._parse_json_response("")
        assert result == {}


class TestExtractTextFromAnalysis:
    """Test _extract_text_from_analysis for nested JSON cleanup."""

    def test_plain_text_passthrough(self):
        text = "This is a normal analysis paragraph."
        result = QuestionAnswerService._extract_text_from_analysis(text)
        assert result == text

    def test_json_wrapped_analysis(self):
        """The main bug: analysis field contains JSON with inner 'analysis' key."""
        inner = {"analysis": "The actual analysis text.", "citations": []}
        text = json.dumps(inner)
        result = QuestionAnswerService._extract_text_from_analysis(text)
        assert result == "The actual analysis text."

    def test_malformed_json_with_analysis_key(self):
        """JSON that doesn't parse but has extractable analysis via regex."""
        text = '{"analysis": "Extractable text here", "citations": [truncated'
        result = QuestionAnswerService._extract_text_from_analysis(text)
        assert result == "Extractable text here"

    def test_json_without_analysis_key(self):
        """JSON object but no 'analysis' key — return as-is."""
        text = '{"summary": "Some summary"}'
        result = QuestionAnswerService._extract_text_from_analysis(text)
        assert result == text

    def test_empty_string(self):
        result = QuestionAnswerService._extract_text_from_analysis("")
        assert result == ""

    def test_none_value(self):
        result = QuestionAnswerService._extract_text_from_analysis(None)
        assert result == ""

    def test_multiline_json_analysis(self):
        """Bedrock often returns pretty-printed JSON."""
        text = '{\n  "analysis": "Multi-line analysis text.",\n  "citations": []\n}'
        result = QuestionAnswerService._extract_text_from_analysis(text)
        assert result == "Multi-line analysis text."

    def test_analysis_with_escaped_quotes(self):
        """Analysis text containing escaped quotes."""
        inner = {"analysis": 'He said "hello" to the witness.', "citations": []}
        text = json.dumps(inner)
        result = QuestionAnswerService._extract_text_from_analysis(text)
        assert result == 'He said "hello" to the witness.'


class TestLevel2Integration:
    """Integration test: verify _generate_level2 produces clean analysis text."""

    def test_bedrock_returns_clean_json(self):
        """When Bedrock returns parseable JSON, analysis should be plain text."""
        svc = QuestionAnswerService.__new__(QuestionAnswerService)
        svc.bedrock_client = MagicMock()
        svc.aurora_cm = MagicMock()
        svc.neptune_endpoint = ""
        svc.neptune_port = "8182"
        svc.opensearch_endpoint = ""

        bedrock_response = json.dumps({
            "analysis": "Jeffrey Epstein had connections to multiple entities.",
            "citations": [{"document_name": "doc1.pdf", "relevance": "high", "excerpt": "test"}]
        })
        svc._invoke_bedrock = MagicMock(return_value=bedrock_response)

        result = svc._generate_level2("What role?", "Jeffrey Epstein", [], [])
        assert result["analysis"] == "Jeffrey Epstein had connections to multiple entities."
        assert not result["analysis"].startswith("{")

    def test_bedrock_returns_unparseable_json(self):
        """When Bedrock returns malformed JSON, we should still extract analysis text."""
        svc = QuestionAnswerService.__new__(QuestionAnswerService)
        svc.bedrock_client = MagicMock()
        svc.aurora_cm = MagicMock()
        svc.neptune_endpoint = ""
        svc.neptune_port = "8182"
        svc.opensearch_endpoint = ""

        # Simulate Bedrock returning JSON-like text that doesn't fully parse
        bedrock_response = '{\n  "analysis": "Epstein was connected to many people.",\n  "citations": [truncated'
        svc._invoke_bedrock = MagicMock(return_value=bedrock_response)

        result = svc._generate_level2("What role?", "Jeffrey Epstein", [], [])
        # Should extract the analysis text, not show raw JSON
        assert "Epstein was connected" in result["analysis"]
        assert not result["analysis"].startswith("{")
