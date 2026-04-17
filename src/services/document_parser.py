"""Document parser for converting raw text into structured ParsedDocument representations."""

import re
from datetime import datetime, timezone

from models.document import ParsedDocument


class DocumentParseError(Exception):
    """Raised when a document cannot be parsed due to unsupported format or corruption."""

    def __init__(self, document_id: str, reason: str) -> None:
        self.document_id = document_id
        self.reason = reason
        super().__init__(f"Failed to parse document '{document_id}': {reason}")


# Regex for markdown-style headers (e.g. "# Title", "## Subtitle")
_HEADER_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)

# Regex for underline-style headers (e.g. "Title\n=====", "Subtitle\n-----")
_UNDERLINE_HEADER_RE = re.compile(
    r"^([^\n]+)\n([=\-]{3,})$", re.MULTILINE
)

# Section separator used in formatted output
_SECTION_SEP = "\n\n---\n\n"

# Metadata block markers used in formatted output
_META_START = "[SOURCE_METADATA]"
_META_END = "[/SOURCE_METADATA]"
_SECTION_MARKER = "[SECTION]"
_SECTION_END_MARKER = "[/SECTION]"


class DocumentParser:
    """Parses raw documents into structured internal representation.

    Handles plain text documents (the primary format for Ancient Aliens transcripts).
    Sections are extracted by splitting on common section markers such as
    double newlines and header patterns.
    """

    def parse(
        self,
        raw_content: str,
        document_id: str,
        case_file_id: str,
        source_metadata: dict | None = None,
    ) -> ParsedDocument:
        """Parse raw document content into a structured ParsedDocument.

        Args:
            raw_content: The raw text content of the document.
            document_id: Unique identifier for the document.
            case_file_id: The case file this document belongs to.
            source_metadata: Optional metadata about the source (filename, format, etc.).

        Returns:
            A ParsedDocument with extracted sections.

        Raises:
            DocumentParseError: If the content is unsupported or corrupt.
        """
        if source_metadata is None:
            source_metadata = {}

        self._validate(raw_content, document_id, source_metadata)

        sections = self._extract_sections(raw_content)

        return ParsedDocument(
            document_id=document_id,
            case_file_id=case_file_id,
            source_metadata=source_metadata,
            raw_text=raw_content,
            sections=sections,
        )

    def format(self, parsed_doc: ParsedDocument) -> str:
        """Convert a structured ParsedDocument back to human-readable text.

        The output is designed so that re-parsing it produces an equivalent
        ParsedDocument (round-trip property).

        Args:
            parsed_doc: The structured document to format.

        Returns:
            A human-readable string representation.
        """
        parts: list[str] = []

        # Header line with document and case IDs
        parts.append(f"Document: {parsed_doc.document_id}")
        parts.append(f"Case File: {parsed_doc.case_file_id}")

        # Source metadata block
        parts.append(f"{_META_START}")
        for key, value in sorted(parsed_doc.source_metadata.items()):
            parts.append(f"  {key}: {value}")
        parts.append(f"{_META_END}")

        # Sections
        for section in parsed_doc.sections:
            title = section.get("title", "")
            content = section.get("content", "")
            parts.append(f"{_SECTION_MARKER}")
            if title:
                parts.append(f"## {title}")
            parts.append(content)
            parts.append(f"{_SECTION_END_MARKER}")

        return "\n".join(parts)

    def parse_formatted(
        self, formatted_text: str, source_metadata_override: dict | None = None
    ) -> ParsedDocument:
        """Parse text produced by format() back into a ParsedDocument.

        This is the inverse of format(), enabling the round-trip property.

        Args:
            formatted_text: Text previously produced by format().
            source_metadata_override: If provided, overrides parsed metadata.

        Returns:
            A ParsedDocument equivalent to the original.

        Raises:
            DocumentParseError: If the formatted text is malformed.
        """
        lines = formatted_text.split("\n")

        # Extract document_id
        if not lines or not lines[0].startswith("Document: "):
            raise DocumentParseError("unknown", "Malformed formatted text: missing Document header")
        document_id = lines[0][len("Document: "):]

        # Extract case_file_id
        if len(lines) < 2 or not lines[1].startswith("Case File: "):
            raise DocumentParseError(document_id, "Malformed formatted text: missing Case File header")
        case_file_id = lines[1][len("Case File: "):]

        # Extract source metadata
        source_metadata: dict = {}
        in_meta = False
        meta_end_idx = 2
        for i, line in enumerate(lines[2:], start=2):
            if line.strip() == _META_START:
                in_meta = True
                continue
            if line.strip() == _META_END:
                in_meta = False
                meta_end_idx = i
                break
            if in_meta:
                stripped = line.strip()
                if ": " in stripped:
                    key, value = stripped.split(": ", 1)
                    source_metadata[key] = value

        if source_metadata_override is not None:
            source_metadata = source_metadata_override

        # Extract sections
        sections: list[dict] = []
        remaining_lines = lines[meta_end_idx + 1:]
        in_section = False
        current_title = ""
        current_content_lines: list[str] = []

        for line in remaining_lines:
            if line.strip() == _SECTION_MARKER:
                in_section = True
                current_title = ""
                current_content_lines = []
                continue
            if line.strip() == _SECTION_END_MARKER:
                in_section = False
                sections.append({
                    "title": current_title,
                    "content": "\n".join(current_content_lines),
                })
                continue
            if in_section:
                if not current_title and not current_content_lines and line.startswith("## "):
                    current_title = line[3:]
                else:
                    current_content_lines.append(line)

        # Reconstruct raw_text from sections
        raw_text = self._reconstruct_raw_text(sections)

        return ParsedDocument(
            document_id=document_id,
            case_file_id=case_file_id,
            source_metadata=source_metadata,
            raw_text=raw_text,
            sections=sections,
        )

    def _validate(self, raw_content: str, document_id: str, source_metadata: dict) -> None:
        """Validate that the content can be parsed.

        Raises:
            DocumentParseError: If the content is empty, binary, or unsupported.
        """
        if not raw_content:
            raise DocumentParseError(document_id, "Document content is empty")

        if not isinstance(raw_content, str):
            raise DocumentParseError(document_id, "Unsupported format: content is not text")

        # Check for binary/corrupt content (null bytes)
        if "\x00" in raw_content:
            raise DocumentParseError(
                document_id, "Document appears to be corrupt: contains null bytes"
            )

        # Check format from metadata if provided
        fmt = source_metadata.get("format", "").lower()
        unsupported_formats = {"pdf", "docx", "xlsx", "pptx", "zip", "tar", "gz", "binary"}
        if fmt in unsupported_formats:
            raise DocumentParseError(
                document_id, f"Unsupported format: '{fmt}'"
            )

    def _extract_sections(self, raw_text: str) -> list[dict]:
        """Extract sections from raw text by detecting headers and paragraph breaks.

        Strategy:
        1. If markdown-style headers exist, split on those.
        2. If underline-style headers exist, split on those.
        3. Otherwise, split on double newlines into untitled sections.
        """
        # Try markdown headers first
        headers = list(_HEADER_RE.finditer(raw_text))
        if headers:
            return self._split_by_headers(raw_text, headers)

        # Try underline-style headers
        underline_headers = list(_UNDERLINE_HEADER_RE.finditer(raw_text))
        if underline_headers:
            return self._split_by_underline_headers(raw_text, underline_headers)

        # Fall back to paragraph splitting
        return self._split_by_paragraphs(raw_text)

    def _split_by_headers(self, raw_text: str, headers: list[re.Match]) -> list[dict]:
        """Split text into sections based on markdown-style headers."""
        sections: list[dict] = []

        # Content before the first header
        pre_content = raw_text[: headers[0].start()].strip()
        if pre_content:
            sections.append({"title": "", "content": pre_content})

        for i, match in enumerate(headers):
            title = match.group(2).strip()
            start = match.end()
            end = headers[i + 1].start() if i + 1 < len(headers) else len(raw_text)
            content = raw_text[start:end].strip()
            sections.append({"title": title, "content": content})

        return sections

    def _split_by_underline_headers(
        self, raw_text: str, headers: list[re.Match]
    ) -> list[dict]:
        """Split text into sections based on underline-style headers."""
        sections: list[dict] = []

        pre_content = raw_text[: headers[0].start()].strip()
        if pre_content:
            sections.append({"title": "", "content": pre_content})

        for i, match in enumerate(headers):
            title = match.group(1).strip()
            start = match.end()
            end = headers[i + 1].start() if i + 1 < len(headers) else len(raw_text)
            content = raw_text[start:end].strip()
            sections.append({"title": title, "content": content})

        return sections

    def _split_by_paragraphs(self, raw_text: str) -> list[dict]:
        """Split text into sections based on double newlines (paragraph breaks)."""
        paragraphs = re.split(r"\n\n+", raw_text.strip())
        sections: list[dict] = []
        for para in paragraphs:
            stripped = para.strip()
            if stripped:
                sections.append({"title": "", "content": stripped})
        return sections

    def _reconstruct_raw_text(self, sections: list[dict]) -> str:
        """Reconstruct raw text from sections for round-trip parsing."""
        parts: list[str] = []
        for section in sections:
            title = section.get("title", "")
            content = section.get("content", "")
            if title:
                parts.append(f"## {title}\n\n{content}")
            else:
                parts.append(content)
        return "\n\n".join(parts)
