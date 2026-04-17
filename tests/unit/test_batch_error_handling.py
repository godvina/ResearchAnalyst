"""Tests for error handling: quarantine management, retry exhaustion, and failure threshold.

Covers:
- QuarantineManager load/save round-trip
- QuarantineManager add and get_quarantined_keys
- Retry exhaustion leads to failed result
- Failure threshold check
"""

import json
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from scripts.batch_loader.config import BatchConfig
from scripts.batch_loader.extractor import ExtractionResult, TextExtractor
from scripts.batch_loader.quarantine import (
    QuarantineEntry,
    QuarantineManager,
    check_failure_threshold,
)


# ── QuarantineManager tests ──────────────────────────────────────────


class TestQuarantineManagerLoadSaveRoundTrip:
    """QuarantineManager load/save round-trip."""

    def test_save_then_load_returns_same_entries(self, tmp_path):
        path = str(tmp_path / "quarantine.json")
        mgr = QuarantineManager(quarantine_path=path)
        mgr.add("pdfs/file1.pdf", "corrupted", retry_count=3, batch_number=1)
        mgr.add("pdfs/file2.pdf", "timeout", retry_count=2, batch_number=2)
        mgr.save()

        mgr2 = QuarantineManager(quarantine_path=path)
        entries = mgr2.load()
        assert len(entries) == 2
        keys = {e.s3_key for e in entries}
        assert keys == {"pdfs/file1.pdf", "pdfs/file2.pdf"}

    def test_load_empty_when_no_file(self, tmp_path):
        path = str(tmp_path / "nonexistent.json")
        mgr = QuarantineManager(quarantine_path=path)
        entries = mgr.load()
        assert entries == []

    def test_load_empty_on_corrupt_json(self, tmp_path):
        path = str(tmp_path / "quarantine.json")
        with open(path, "w") as f:
            f.write("NOT JSON")
        mgr = QuarantineManager(quarantine_path=path)
        entries = mgr.load()
        assert entries == []

    def test_round_trip_preserves_all_fields(self, tmp_path):
        path = str(tmp_path / "quarantine.json")
        mgr = QuarantineManager(quarantine_path=path)
        mgr.add("pdfs/test.pdf", "PyPDF2 PdfReadError", retry_count=3, batch_number=5)
        mgr.save()

        mgr2 = QuarantineManager(quarantine_path=path)
        entries = mgr2.load()
        assert len(entries) == 1
        e = entries[0]
        assert e.s3_key == "pdfs/test.pdf"
        assert e.reason == "PyPDF2 PdfReadError"
        assert e.retry_count == 3
        assert e.batch_number == 5
        assert e.failed_at  # non-empty timestamp


class TestQuarantineManagerAddAndQuery:
    """QuarantineManager add and get_quarantined_keys."""

    def test_add_populates_quarantined_keys(self):
        mgr = QuarantineManager(quarantine_path="/dev/null")
        mgr.add("pdfs/a.pdf", "error", retry_count=1, batch_number=1)
        mgr.add("pdfs/b.pdf", "error", retry_count=2, batch_number=1)
        assert mgr.get_quarantined_keys() == {"pdfs/a.pdf", "pdfs/b.pdf"}

    def test_is_quarantined_true_for_added_key(self):
        mgr = QuarantineManager(quarantine_path="/dev/null")
        mgr.add("pdfs/x.pdf", "reason", retry_count=1, batch_number=1)
        assert mgr.is_quarantined("pdfs/x.pdf") is True

    def test_is_quarantined_false_for_unknown_key(self):
        mgr = QuarantineManager(quarantine_path="/dev/null")
        assert mgr.is_quarantined("pdfs/unknown.pdf") is False

    def test_get_quarantined_keys_empty_initially(self):
        mgr = QuarantineManager(quarantine_path="/dev/null")
        assert mgr.get_quarantined_keys() == set()


# ── Retry exhaustion → failed result ─────────────────────────────────


class TestRetryExhaustion:
    """Retry exhaustion leads to failed ExtractionResult."""

    def _make_extractor(self, max_retries=3):
        config = BatchConfig(max_retries=max_retries)
        s3_client = MagicMock()
        textract_client = MagicMock()
        return TextExtractor(config, s3_client, textract_client)

    @patch("time.sleep", return_value=None)
    def test_all_retries_fail_returns_failed_method(self, mock_sleep):
        extractor = self._make_extractor(max_retries=3)
        # Make S3 download always fail
        extractor.s3.get_object.side_effect = Exception("connection timeout")

        result = extractor.extract("pdfs/bad.pdf", batch_id="b1")
        assert result.method == "failed"
        assert result.s3_key == "pdfs/bad.pdf"
        assert result.char_count == 0
        assert "connection timeout" in result.error

    @patch("time.sleep", return_value=None)
    def test_retries_called_max_retries_times(self, mock_sleep):
        extractor = self._make_extractor(max_retries=3)
        extractor.s3.get_object.side_effect = Exception("fail")

        extractor.extract("pdfs/bad.pdf", batch_id="b1")
        # 1 call for cache check + 3 retry attempts = 4 total
        assert extractor.s3.get_object.call_count == 4

    @patch("time.sleep", return_value=None)
    def test_succeeds_on_second_attempt(self, mock_sleep):
        extractor = self._make_extractor(max_retries=3)

        # First call fails, second succeeds
        mock_body = MagicMock()
        mock_body.read.return_value = b"%PDF-1.4 fake pdf"
        extractor.s3.get_object.side_effect = [
            Exception("transient error"),
            {"Body": mock_body},
        ]

        # Mock PyPDF2 to return some text
        with patch.object(extractor, "_extract_pypdf2", return_value=("Hello world " * 100, 2)):
            with patch.object(extractor, "_save_to_cache"):
                result = extractor.extract("pdfs/ok.pdf", batch_id="b1")

        assert result.method == "pypdf2"
        assert result.s3_key == "pdfs/ok.pdf"

    @patch("time.sleep", return_value=None)
    def test_single_retry_config(self, mock_sleep):
        extractor = self._make_extractor(max_retries=1)
        extractor.s3.get_object.side_effect = Exception("fail")

        result = extractor.extract("pdfs/bad.pdf", batch_id="b1")
        assert result.method == "failed"
        # 1 call for cache check + 1 retry attempt = 2 total
        assert extractor.s3.get_object.call_count == 2


# ── Failure threshold check ───────────────────────────────────────────


class TestFailureThreshold:
    """check_failure_threshold returns True when ratio exceeds threshold."""

    def test_above_threshold_returns_true(self):
        # 20 failed out of 100 = 20% > 10%
        assert check_failure_threshold(20, 100, 0.10) is True

    def test_at_threshold_returns_false(self):
        # 10 failed out of 100 = 10% == 10% (not strictly greater)
        assert check_failure_threshold(10, 100, 0.10) is False

    def test_below_threshold_returns_false(self):
        assert check_failure_threshold(5, 100, 0.10) is False

    def test_zero_total_returns_false(self):
        assert check_failure_threshold(0, 0, 0.10) is False

    def test_all_failed_returns_true(self):
        assert check_failure_threshold(50, 50, 0.10) is True

    def test_zero_failures_returns_false(self):
        assert check_failure_threshold(0, 100, 0.10) is False

    def test_negative_total_returns_false(self):
        assert check_failure_threshold(5, -1, 0.10) is False
