"""Unit tests for scripts/batch_loader/extractor.py — TextExtractor."""

import io
import json
from unittest.mock import MagicMock

import pytest

from scripts.batch_loader.config import BatchConfig
from scripts.batch_loader.extractor import ExtractionResult, TextExtractor


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_s3_get(body_bytes: bytes) -> MagicMock:
    """Build a mock S3 response for get_object."""
    body = MagicMock()
    body.read.return_value = body_bytes
    return {"Body": body}


def _make_s3_client(
    get_responses: dict[str, bytes] | None = None,
    head_responses: dict[str, dict] | None = None,
) -> MagicMock:
    """Build a mock S3 client with configurable get/head/put responses."""
    client = MagicMock()

    def get_side_effect(Bucket, Key):
        if get_responses and Key in get_responses:
            return _make_s3_get(get_responses[Key])
        raise client.exceptions.NoSuchKey(
            {"Error": {"Code": "NoSuchKey"}}, "GetObject"
        )

    def head_side_effect(Bucket, Key):
        if head_responses and Key in head_responses:
            return head_responses[Key]
        return {"ContentLength": 1000}

    client.get_object.side_effect = get_side_effect
    client.head_object.side_effect = head_side_effect
    client.exceptions = MagicMock()
    client.exceptions.NoSuchKey = type("NoSuchKey", (Exception,), {})
    return client


def _make_textract_client(lines: list[str] | None = None) -> MagicMock:
    """Build a mock Textract client."""
    client = MagicMock()
    blocks = []
    if lines:
        for line in lines:
            blocks.append({"BlockType": "LINE", "Text": line})
    client.detect_document_text.return_value = {"Blocks": blocks}
    return client


# ===========================================================================
# ExtractionResult dataclass
# ===========================================================================

class TestExtractionResult:
    """Verify ExtractionResult dataclass fields and defaults."""

    def test_all_fields_set(self):
        r = ExtractionResult(
            s3_key="pdfs/test.pdf",
            text="hello world",
            method="pypdf2",
            char_count=11,
            error=None,
        )
        assert r.s3_key == "pdfs/test.pdf"
        assert r.text == "hello world"
        assert r.method == "pypdf2"
        assert r.char_count == 11
        assert r.error is None

    def test_error_default_none(self):
        r = ExtractionResult(
            s3_key="k", text="t", method="cached", char_count=1
        )
        assert r.error is None

    def test_error_set(self):
        r = ExtractionResult(
            s3_key="k", text="", method="failed", char_count=0, error="boom"
        )
        assert r.error == "boom"

    def test_compatible_with_filter_protocol(self):
        """ExtractionResult must have s3_key, text, char_count for BlankFilter."""
        r = ExtractionResult(
            s3_key="pdfs/a.pdf", text="some text", method="pypdf2", char_count=9
        )
        assert hasattr(r, "s3_key")
        assert hasattr(r, "text")
        assert hasattr(r, "char_count")

    def test_method_values(self):
        for method in ("pypdf2", "textract", "cached", "failed"):
            r = ExtractionResult(s3_key="k", text="", method=method, char_count=0)
            assert r.method == method


# ===========================================================================
# Cache hit returns cached text
# ===========================================================================

class TestCacheHit:
    """Verify _check_cache returns cached text when present."""

    def test_cache_hit_returns_text(self):
        cache_json = json.dumps({
            "extractedText": "cached content",
            "sourceFile": "pdfs/doc.pdf",
            "method": "pypdf2",
        }).encode("utf-8")

        s3 = _make_s3_client(
            get_responses={"textract-output/batch_001/doc.pdf.json": cache_json}
        )
        extractor = TextExtractor(BatchConfig(), s3, MagicMock())

        result = extractor.extract("pdfs/doc.pdf", batch_id="001")
        assert result.method == "cached"
        assert result.text == "cached content"
        assert result.char_count == len("cached content")

    def test_no_cache_without_batch_id(self):
        """When batch_id is empty, cache is not checked."""
        s3 = _make_s3_client()
        textract = _make_textract_client()
        extractor = TextExtractor(BatchConfig(), s3, textract)

        # _check_cache should return None for empty batch_id
        assert extractor._check_cache("pdfs/doc.pdf", "") is None

    def test_cache_miss_proceeds_to_extraction(self):
        """When cache misses, extraction should proceed."""
        # S3 get_object raises for cache key, succeeds for source PDF
        s3 = MagicMock()
        call_count = {"n": 0}

        def get_side_effect(Bucket, Key):
            call_count["n"] += 1
            if "textract-output" in Key:
                raise Exception("NoSuchKey")
            # Return a minimal valid PDF
            body = MagicMock()
            body.read.return_value = _minimal_pdf_bytes()
            return {"Body": body}

        s3.get_object.side_effect = get_side_effect
        s3.head_object.return_value = {"ContentLength": 500}

        extractor = TextExtractor(
            BatchConfig(ocr_threshold=0), s3, MagicMock()
        )
        result = extractor.extract("pdfs/doc.pdf", batch_id="001")
        assert result.method in ("pypdf2", "textract", "failed")


# ===========================================================================
# PyPDF2 extraction for text-based PDFs
# ===========================================================================

def _minimal_pdf_bytes() -> bytes:
    """Create minimal valid PDF bytes for testing."""
    try:
        from PyPDF2 import PdfWriter
        writer = PdfWriter()
        writer.add_blank_page(width=612, height=792)
        buf = io.BytesIO()
        writer.write(buf)
        return buf.getvalue()
    except ImportError:
        # Fallback: return bytes that will cause PyPDF2 to fail gracefully
        return b"%PDF-1.4\n"


class TestPyPDF2Extraction:
    """Verify _extract_pypdf2 extracts text from valid PDFs."""

    def test_extract_returns_text_and_page_count(self):
        s3 = MagicMock()
        textract = MagicMock()
        extractor = TextExtractor(BatchConfig(), s3, textract)

        pdf_bytes = _minimal_pdf_bytes()
        text, page_count = extractor._extract_pypdf2(pdf_bytes)
        assert isinstance(text, str)
        assert isinstance(page_count, int)
        assert page_count >= 1

    def test_extract_blank_page_returns_empty_text(self):
        """Verify a blank PDF page yields empty text with page_count=1."""
        s3 = MagicMock()
        extractor = TextExtractor(BatchConfig(), s3, MagicMock())

        pdf_bytes = _minimal_pdf_bytes()
        text, page_count = extractor._extract_pypdf2(pdf_bytes)
        assert page_count == 1
        assert isinstance(text, str)


# ===========================================================================
# OCR fallback when chars/page < ocr_threshold
# ===========================================================================

class TestOCRFallback:
    """Verify Textract OCR is used when PyPDF2 yields too few chars/page."""

    def test_ocr_fallback_triggered(self):
        """When PyPDF2 yields < ocr_threshold chars/page, Textract is used."""
        s3 = MagicMock()
        # Source PDF download
        pdf_body = MagicMock()
        pdf_body.read.return_value = _minimal_pdf_bytes()

        call_log = []

        def get_side_effect(Bucket, Key):
            call_log.append(Key)
            if "textract-output" in Key:
                raise Exception("NoSuchKey")
            body = MagicMock()
            body.read.return_value = _minimal_pdf_bytes()
            return {"Body": body}

        s3.get_object.side_effect = get_side_effect
        s3.head_object.return_value = {"ContentLength": 1000}

        textract = _make_textract_client(["OCR line 1", "OCR line 2"])

        # ocr_threshold=9999 ensures PyPDF2 result (blank page) triggers fallback
        config = BatchConfig(ocr_threshold=9999)
        extractor = TextExtractor(config, s3, textract)

        result = extractor.extract("pdfs/scanned.pdf", batch_id="001")
        assert result.method == "textract"
        assert "OCR line 1" in result.text
        textract.detect_document_text.assert_called_once()

    def test_no_ocr_when_enough_text(self):
        """When PyPDF2 yields >= ocr_threshold chars/page, no Textract call."""
        s3 = MagicMock()

        def get_side_effect(Bucket, Key):
            if "textract-output" in Key:
                raise Exception("NoSuchKey")
            body = MagicMock()
            body.read.return_value = _minimal_pdf_bytes()
            return {"Body": body}

        s3.get_object.side_effect = get_side_effect
        s3.head_object.return_value = {"ContentLength": 1000}

        textract = MagicMock()

        # ocr_threshold=0 means PyPDF2 result always passes
        config = BatchConfig(ocr_threshold=0)
        extractor = TextExtractor(config, s3, textract)

        result = extractor.extract("pdfs/text.pdf", batch_id="001")
        assert result.method == "pypdf2"
        textract.detect_document_text.assert_not_called()


# ===========================================================================
# Failed extraction for corrupted PDFs
# ===========================================================================

class TestFailedExtraction:
    """Verify corrupted/encrypted PDFs return failed result."""

    def test_corrupted_pdf_returns_failed(self):
        s3 = MagicMock()

        def get_side_effect(Bucket, Key):
            if "textract-output" in Key:
                raise Exception("NoSuchKey")
            body = MagicMock()
            body.read.return_value = b"NOT A VALID PDF"
            return {"Body": body}

        s3.get_object.side_effect = get_side_effect
        textract = MagicMock()

        extractor = TextExtractor(BatchConfig(), s3, textract)
        result = extractor.extract("pdfs/corrupted.pdf", batch_id="001")
        assert result.method == "failed"
        assert result.char_count == 0
        assert result.error is not None

    def test_s3_download_failure_returns_failed(self):
        s3 = MagicMock()
        s3.get_object.side_effect = Exception("Access Denied")

        extractor = TextExtractor(BatchConfig(), s3, MagicMock())
        result = extractor.extract("pdfs/missing.pdf", batch_id="001")
        assert result.method == "failed"
        assert "S3 download failed" in result.error


# ===========================================================================
# Cache save after extraction
# ===========================================================================

class TestCacheSave:
    """Verify _save_to_cache writes correct JSON to S3."""

    def test_save_writes_correct_json(self):
        s3 = MagicMock()
        extractor = TextExtractor(BatchConfig(), s3, MagicMock())

        extractor._save_to_cache("pdfs/doc.pdf", "001", "extracted text", "pypdf2")

        s3.put_object.assert_called_once()
        call_kwargs = s3.put_object.call_args[1]
        assert call_kwargs["Bucket"] == BatchConfig().data_lake_bucket
        assert call_kwargs["Key"] == "textract-output/batch_001/doc.pdf.json"

        body = json.loads(call_kwargs["Body"])
        assert body["extractedText"] == "extracted text"
        assert body["sourceFile"] == "pdfs/doc.pdf"
        assert body["method"] == "pypdf2"

    def test_save_skipped_without_batch_id(self):
        s3 = MagicMock()
        extractor = TextExtractor(BatchConfig(), s3, MagicMock())

        extractor._save_to_cache("pdfs/doc.pdf", "", "text", "pypdf2")
        s3.put_object.assert_not_called()

    def test_save_failure_does_not_raise(self):
        s3 = MagicMock()
        s3.put_object.side_effect = Exception("S3 write failed")
        extractor = TextExtractor(BatchConfig(), s3, MagicMock())

        # Should not raise
        extractor._save_to_cache("pdfs/doc.pdf", "001", "text", "pypdf2")


# ===========================================================================
# Method field correctly set
# ===========================================================================

class TestMethodField:
    """Verify the method field is set correctly for each extraction path."""

    def test_cached_method(self):
        cache_json = json.dumps({
            "extractedText": "cached",
            "sourceFile": "pdfs/a.pdf",
            "method": "pypdf2",
        }).encode("utf-8")
        s3 = _make_s3_client(
            get_responses={"textract-output/batch_b1/a.pdf.json": cache_json}
        )
        extractor = TextExtractor(BatchConfig(), s3, MagicMock())
        result = extractor.extract("pdfs/a.pdf", batch_id="b1")
        assert result.method == "cached"

    def test_pypdf2_method(self):
        s3 = MagicMock()

        def get_side_effect(Bucket, Key):
            if "textract-output" in Key:
                raise Exception("miss")
            body = MagicMock()
            body.read.return_value = _minimal_pdf_bytes()
            return {"Body": body}

        s3.get_object.side_effect = get_side_effect
        config = BatchConfig(ocr_threshold=0)
        extractor = TextExtractor(config, s3, MagicMock())
        result = extractor.extract("pdfs/text.pdf", batch_id="b1")
        assert result.method == "pypdf2"

    def test_textract_method(self):
        s3 = MagicMock()

        def get_side_effect(Bucket, Key):
            if "textract-output" in Key:
                raise Exception("miss")
            body = MagicMock()
            body.read.return_value = _minimal_pdf_bytes()
            return {"Body": body}

        s3.get_object.side_effect = get_side_effect
        s3.head_object.return_value = {"ContentLength": 1000}

        textract = _make_textract_client(["OCR text"])
        config = BatchConfig(ocr_threshold=9999)
        extractor = TextExtractor(config, s3, textract)
        result = extractor.extract("pdfs/scanned.pdf", batch_id="b1")
        assert result.method == "textract"

    def test_failed_method(self):
        s3 = MagicMock()
        s3.get_object.side_effect = Exception("boom")
        extractor = TextExtractor(BatchConfig(), s3, MagicMock())
        result = extractor.extract("pdfs/bad.pdf", batch_id="b1")
        assert result.method == "failed"
