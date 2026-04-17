"""Unit tests for DocumentParser service."""

import pytest

from src.models.document import ParsedDocument
from src.services.document_parser import DocumentParseError, DocumentParser


@pytest.fixture
def parser():
    return DocumentParser()


class TestDocumentParserParse:
    """Tests for DocumentParser.parse() — Requirement 11.1."""

    def test_parse_plain_text(self, parser):
        raw = "This is a simple transcript about ancient aliens."
        doc = parser.parse(raw, "doc-1", "case-1")

        assert doc.document_id == "doc-1"
        assert doc.case_file_id == "case-1"
        assert doc.raw_text == raw
        assert isinstance(doc.sections, list)
        assert len(doc.sections) >= 1
        assert doc.parse_errors == []

    def test_parse_preserves_source_metadata(self, parser):
        meta = {"filename": "transcript.txt", "upload_timestamp": "2024-01-01T00:00:00Z"}
        doc = parser.parse("Some content", "doc-2", "case-1", source_metadata=meta)

        assert doc.source_metadata == meta

    def test_parse_default_source_metadata(self, parser):
        doc = parser.parse("Some content", "doc-3", "case-1")
        assert doc.source_metadata == {}

    def test_parse_extracts_sections_from_paragraphs(self, parser):
        raw = "First paragraph about pyramids.\n\nSecond paragraph about Nazca lines."
        doc = parser.parse(raw, "doc-4", "case-1")

        assert len(doc.sections) == 2
        assert "pyramids" in doc.sections[0]["content"]
        assert "Nazca" in doc.sections[1]["content"]

    def test_parse_extracts_sections_from_markdown_headers(self, parser):
        raw = "# Introduction\n\nOpening text.\n\n# Evidence\n\nSome evidence here."
        doc = parser.parse(raw, "doc-5", "case-1")

        assert len(doc.sections) == 2
        assert doc.sections[0]["title"] == "Introduction"
        assert doc.sections[1]["title"] == "Evidence"

    def test_parse_extracts_sections_from_underline_headers(self, parser):
        raw = "Introduction\n============\n\nOpening text.\n\nEvidence\n--------\n\nSome evidence."
        doc = parser.parse(raw, "doc-6", "case-1")

        assert len(doc.sections) == 2
        assert doc.sections[0]["title"] == "Introduction"
        assert doc.sections[1]["title"] == "Evidence"

    def test_parse_returns_parsed_document_type(self, parser):
        doc = parser.parse("content", "doc-7", "case-1")
        assert isinstance(doc, ParsedDocument)

    def test_parse_content_before_first_header(self, parser):
        raw = "Preamble text.\n\n# Chapter 1\n\nChapter content."
        doc = parser.parse(raw, "doc-8", "case-1")

        assert len(doc.sections) == 2
        assert doc.sections[0]["title"] == ""
        assert "Preamble" in doc.sections[0]["content"]
        assert doc.sections[1]["title"] == "Chapter 1"


class TestDocumentParserFormat:
    """Tests for DocumentParser.format() — Requirement 11.2."""

    def test_format_produces_string(self, parser):
        doc = parser.parse("Hello world", "doc-1", "case-1")
        result = parser.format(doc)
        assert isinstance(result, str)

    def test_format_includes_document_id(self, parser):
        doc = parser.parse("Hello world", "doc-1", "case-1")
        result = parser.format(doc)
        assert "doc-1" in result

    def test_format_includes_case_file_id(self, parser):
        doc = parser.parse("Hello world", "doc-1", "case-1")
        result = parser.format(doc)
        assert "case-1" in result

    def test_format_includes_metadata(self, parser):
        meta = {"filename": "test.txt"}
        doc = parser.parse("Hello world", "doc-1", "case-1", source_metadata=meta)
        result = parser.format(doc)
        assert "filename" in result
        assert "test.txt" in result

    def test_format_includes_section_content(self, parser):
        raw = "# Title\n\nSection body text."
        doc = parser.parse(raw, "doc-1", "case-1")
        result = parser.format(doc)
        assert "Section body text." in result


class TestDocumentParserRoundTrip:
    """Tests for parse/format round-trip — Requirement 11.3."""

    def test_round_trip_simple_text(self, parser):
        raw = "Simple paragraph of text."
        original = parser.parse(raw, "doc-1", "case-1", source_metadata={"filename": "a.txt"})
        formatted = parser.format(original)
        restored = parser.parse_formatted(formatted)

        assert restored.document_id == original.document_id
        assert restored.case_file_id == original.case_file_id
        assert restored.source_metadata == original.source_metadata
        assert restored.sections == original.sections

    def test_round_trip_with_headers(self, parser):
        raw = "## Intro\n\nIntro text.\n\n## Body\n\nBody text."
        meta = {"filename": "transcript.txt", "format": "txt"}
        original = parser.parse(raw, "doc-2", "case-2", source_metadata=meta)
        formatted = parser.format(original)
        restored = parser.parse_formatted(formatted)

        assert restored.document_id == original.document_id
        assert restored.case_file_id == original.case_file_id
        assert restored.sections == original.sections

    def test_round_trip_preserves_section_count(self, parser):
        raw = "Para one.\n\nPara two.\n\nPara three."
        original = parser.parse(raw, "doc-3", "case-1")
        formatted = parser.format(original)
        restored = parser.parse_formatted(formatted)

        assert len(restored.sections) == len(original.sections)


class TestDocumentParserErrors:
    """Tests for error handling — Requirement 11.4."""

    def test_empty_content_raises_error(self, parser):
        with pytest.raises(DocumentParseError) as exc_info:
            parser.parse("", "doc-err-1", "case-1")

        assert exc_info.value.document_id == "doc-err-1"
        assert "empty" in exc_info.value.reason.lower()

    def test_null_bytes_raises_corruption_error(self, parser):
        with pytest.raises(DocumentParseError) as exc_info:
            parser.parse("some\x00binary\x00content", "doc-err-2", "case-1")

        assert exc_info.value.document_id == "doc-err-2"
        assert "corrupt" in exc_info.value.reason.lower()

    def test_unsupported_format_raises_error(self, parser):
        with pytest.raises(DocumentParseError) as exc_info:
            parser.parse("content", "doc-err-3", "case-1", source_metadata={"format": "pdf"})

        assert exc_info.value.document_id == "doc-err-3"
        assert "unsupported" in exc_info.value.reason.lower()

    def test_error_message_includes_document_id(self, parser):
        with pytest.raises(DocumentParseError) as exc_info:
            parser.parse("", "my-special-doc-id", "case-1")

        assert "my-special-doc-id" in str(exc_info.value)

    def test_error_message_includes_reason(self, parser):
        with pytest.raises(DocumentParseError) as exc_info:
            parser.parse("data", "doc-x", "case-1", source_metadata={"format": "docx"})

        assert "docx" in str(exc_info.value)

    def test_various_unsupported_formats(self, parser):
        for fmt in ["pdf", "docx", "xlsx", "pptx", "zip", "binary"]:
            with pytest.raises(DocumentParseError):
                parser.parse("data", f"doc-{fmt}", "case-1", source_metadata={"format": fmt})

    def test_supported_text_format_does_not_raise(self, parser):
        # txt and other text formats should work fine
        doc = parser.parse("data", "doc-ok", "case-1", source_metadata={"format": "txt"})
        assert doc.document_id == "doc-ok"
