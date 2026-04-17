"""Unit tests for scripts/batch_loader/ledger_integration.py — LedgerIntegration."""

import json
import os
from unittest.mock import patch, MagicMock

import pytest

from scripts.batch_loader.config import BatchConfig
from scripts.batch_loader.ledger_integration import LedgerIntegration, PROGRESS_FILE


@pytest.fixture
def config():
    return BatchConfig(case_id="test-case-id-123")


@pytest.fixture
def integration(config):
    return LedgerIntegration(config)


@pytest.fixture
def sample_stats():
    return {
        "source_files_total": 5000,
        "blanks_skipped": 2250,
        "docs_sent_to_pipeline": 2488,
        "sfn_executions": 50,
        "sfn_succeeded": 49,
        "sfn_failed": 1,
        "entity_resolution_result": {
            "clusters_merged": 45,
            "nodes_dropped": 89,
            "edges_relinked": 234,
            "errors": 0,
        },
        "textract_ocr_count": 750,
        "extraction_method_breakdown": {
            "pypdf2": 3000,
            "textract": 750,
            "failed": 12,
            "cached": 0,
        },
        "notes": "Batch 1. 45% blank rate. 12 extraction failures quarantined.",
    }


class TestRecordBatch:
    """Verify record_batch creates correct ledger entry with all required fields."""

    def test_record_batch_appends_entry_with_all_fields(self, integration, sample_stats):
        """record_batch should append a load entry with every required field."""
        saved_ledger = {}

        def fake_load():
            return {
                "cases": {
                    "test-case-id-123": {
                        "name": "Test Case",
                        "loads": [],
                        "running_total_s3_docs": 0,
                    }
                }
            }

        def fake_save(data):
            saved_ledger.update(data)

        with patch("scripts.batch_loader.ledger_integration.load_ledger", fake_load), \
             patch("scripts.batch_loader.ledger_integration.save_ledger", fake_save):
            integration.record_batch(1, sample_stats)

        case = saved_ledger["cases"]["test-case-id-123"]
        assert len(case["loads"]) == 1
        entry = case["loads"][0]

        # All required fields present
        assert entry["load_id"] == "batch_1"
        assert "timestamp" in entry
        assert entry["source_prefixes"] == ["pdfs/", "bw-documents/"]
        assert entry["source_files_total"] == 5000
        assert entry["blanks_skipped"] == 2250
        assert entry["docs_sent_to_pipeline"] == 2488
        assert entry["sfn_executions"] == 50
        assert entry["sfn_succeeded"] == 49
        assert entry["sfn_failed"] == 1
        assert entry["entity_resolution_result"]["clusters_merged"] == 45
        assert entry["textract_ocr_count"] == 750
        assert entry["extraction_method_breakdown"]["pypdf2"] == 3000
        assert "notes" in entry

    def test_record_batch_creates_case_if_missing(self, integration, sample_stats):
        """record_batch should create the case entry if it doesn't exist."""
        saved_ledger = {}

        def fake_load():
            return {"cases": {}}

        def fake_save(data):
            saved_ledger.update(data)

        with patch("scripts.batch_loader.ledger_integration.load_ledger", fake_load), \
             patch("scripts.batch_loader.ledger_integration.save_ledger", fake_save):
            integration.record_batch(1, sample_stats)

        assert "test-case-id-123" in saved_ledger["cases"]
        case = saved_ledger["cases"]["test-case-id-123"]
        assert len(case["loads"]) == 1

    def test_record_batch_updates_running_total(self, integration, sample_stats):
        """record_batch should update running_total_s3_docs from all loads."""
        saved_ledger = {}

        def fake_load():
            return {
                "cases": {
                    "test-case-id-123": {
                        "name": "Test Case",
                        "loads": [
                            {"load_id": "batch_0", "docs_sent_to_pipeline": 1000}
                        ],
                        "running_total_s3_docs": 1000,
                    }
                }
            }

        def fake_save(data):
            saved_ledger.update(data)

        with patch("scripts.batch_loader.ledger_integration.load_ledger", fake_load), \
             patch("scripts.batch_loader.ledger_integration.save_ledger", fake_save):
            integration.record_batch(2, sample_stats)

        case = saved_ledger["cases"]["test-case-id-123"]
        # 1000 (batch_0) + 2488 (batch_2)
        assert case["running_total_s3_docs"] == 1000 + 2488

    def test_record_batch_load_id_format(self, integration, sample_stats):
        """load_id should follow batch_{batch_number} format."""
        saved_ledger = {}

        def fake_load():
            return {"cases": {"test-case-id-123": {"name": "Test", "loads": []}}}

        def fake_save(data):
            saved_ledger.update(data)

        with patch("scripts.batch_loader.ledger_integration.load_ledger", fake_load), \
             patch("scripts.batch_loader.ledger_integration.save_ledger", fake_save):
            integration.record_batch(42, sample_stats)

        entry = saved_ledger["cases"]["test-case-id-123"]["loads"][0]
        assert entry["load_id"] == "batch_42"

    def test_record_batch_handles_empty_stats(self, integration):
        """record_batch should handle empty stats dict with defaults."""
        saved_ledger = {}

        def fake_load():
            return {"cases": {"test-case-id-123": {"name": "Test", "loads": []}}}

        def fake_save(data):
            saved_ledger.update(data)

        with patch("scripts.batch_loader.ledger_integration.load_ledger", fake_load), \
             patch("scripts.batch_loader.ledger_integration.save_ledger", fake_save):
            integration.record_batch(1, {})

        entry = saved_ledger["cases"]["test-case-id-123"]["loads"][0]
        assert entry["source_files_total"] == 0
        assert entry["blanks_skipped"] == 0
        assert entry["docs_sent_to_pipeline"] == 0
        assert entry["sfn_executions"] == 0
        assert entry["sfn_succeeded"] == 0
        assert entry["sfn_failed"] == 0
        assert entry["entity_resolution_result"] == {}
        assert entry["textract_ocr_count"] == 0
        assert entry["extraction_method_breakdown"] == {}


class TestUpdateProgress:
    """Verify update_progress writes correct batch_progress.json."""

    def test_update_progress_writes_all_fields(self, integration, tmp_path):
        """update_progress should write all required fields to batch_progress.json."""
        progress_file = tmp_path / "batch_progress.json"

        progress = {
            "total_files_discovered": 331000,
            "total_processed": 15000,
            "total_remaining": 316000,
            "current_batch_number": 3,
            "cursor": "pdfs/EPSTEIN_DOC_045123.pdf",
            "cumulative_blanks": 6750,
            "cumulative_quarantined": 23,
            "cumulative_cost": 142.50,
        }

        with patch("scripts.batch_loader.ledger_integration.PROGRESS_FILE", str(progress_file)):
            integration.update_progress(progress)

        data = json.loads(progress_file.read_text())
        assert data["case_id"] == "test-case-id-123"
        assert data["total_files_discovered"] == 331000
        assert data["total_processed"] == 15000
        assert data["total_remaining"] == 316000
        assert data["current_batch_number"] == 3
        assert data["cursor"] == "pdfs/EPSTEIN_DOC_045123.pdf"
        assert data["cumulative_blanks"] == 6750
        assert data["cumulative_quarantined"] == 23
        assert data["cumulative_cost"] == 142.50
        assert "last_updated" in data

    def test_update_progress_overwrites_previous(self, integration, tmp_path):
        """update_progress should overwrite the previous progress file."""
        progress_file = tmp_path / "batch_progress.json"

        with patch("scripts.batch_loader.ledger_integration.PROGRESS_FILE", str(progress_file)):
            integration.update_progress({"total_processed": 5000, "current_batch_number": 1})
            integration.update_progress({"total_processed": 10000, "current_batch_number": 2})

        data = json.loads(progress_file.read_text())
        assert data["total_processed"] == 10000
        assert data["current_batch_number"] == 2

    def test_update_progress_defaults_for_missing_keys(self, integration, tmp_path):
        """update_progress should use defaults for missing progress keys."""
        progress_file = tmp_path / "batch_progress.json"

        with patch("scripts.batch_loader.ledger_integration.PROGRESS_FILE", str(progress_file)):
            integration.update_progress({})

        data = json.loads(progress_file.read_text())
        assert data["total_files_discovered"] == 0
        assert data["total_processed"] == 0
        assert data["total_remaining"] == 0
        assert data["current_batch_number"] == 0
        assert data["cursor"] is None
        assert data["cumulative_blanks"] == 0
        assert data["cumulative_quarantined"] == 0
        assert data["cumulative_cost"] == 0.0


class TestUpdateRunningTotal:
    """Verify running total updates correctly."""

    def test_update_running_total_adds_docs(self, integration):
        """update_running_total should add docs_added to existing total."""
        saved_ledger = {}

        def fake_load():
            return {
                "cases": {
                    "test-case-id-123": {
                        "name": "Test Case",
                        "loads": [],
                        "running_total_s3_docs": 5000,
                    }
                }
            }

        def fake_save(data):
            saved_ledger.update(data)

        with patch("scripts.batch_loader.ledger_integration.load_ledger", fake_load), \
             patch("scripts.batch_loader.ledger_integration.save_ledger", fake_save):
            integration.update_running_total(2500)

        assert saved_ledger["cases"]["test-case-id-123"]["running_total_s3_docs"] == 7500

    def test_update_running_total_noop_for_missing_case(self, integration):
        """update_running_total should do nothing if case doesn't exist."""
        saved_ledger = {}

        def fake_load():
            return {"cases": {}}

        def fake_save(data):
            saved_ledger.update(data)

        with patch("scripts.batch_loader.ledger_integration.load_ledger", fake_load), \
             patch("scripts.batch_loader.ledger_integration.save_ledger", fake_save):
            integration.update_running_total(100)

        # Should not have saved since case doesn't exist
        assert saved_ledger == {}

    def test_update_running_total_from_zero(self, integration):
        """update_running_total should work when starting from zero."""
        saved_ledger = {}

        def fake_load():
            return {
                "cases": {
                    "test-case-id-123": {
                        "name": "Test Case",
                        "loads": [],
                        "running_total_s3_docs": 0,
                    }
                }
            }

        def fake_save(data):
            saved_ledger.update(data)

        with patch("scripts.batch_loader.ledger_integration.load_ledger", fake_load), \
             patch("scripts.batch_loader.ledger_integration.save_ledger", fake_save):
            integration.update_running_total(3000)

        assert saved_ledger["cases"]["test-case-id-123"]["running_total_s3_docs"] == 3000


class TestUpdateAuroraDocCounts:
    """Verify update_aurora_doc_counts calls the existing update pattern."""

    def test_calls_count_and_update(self, integration):
        """update_aurora_doc_counts should count S3 docs and update Aurora."""
        with patch("scripts.batch_loader.ledger_integration.count_s3_docs", return_value=5000) as mock_count, \
             patch("scripts.batch_loader.ledger_integration.update_count") as mock_update:
            integration.update_aurora_doc_counts()

        mock_count.assert_called_once_with("test-case-id-123")
        mock_update.assert_called_once_with("test-case-id-123", 5000)

    def test_skips_update_when_zero_docs(self, integration):
        """update_aurora_doc_counts should skip update when S3 count is 0."""
        with patch("scripts.batch_loader.ledger_integration.count_s3_docs", return_value=0) as mock_count, \
             patch("scripts.batch_loader.ledger_integration.update_count") as mock_update:
            integration.update_aurora_doc_counts()

        mock_count.assert_called_once_with("test-case-id-123")
        mock_update.assert_not_called()
