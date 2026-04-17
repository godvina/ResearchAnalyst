"""Unit tests for batch loader filter and aggregation helpers."""

import pytest

from src.services.batch_loader_state import (
    compute_cumulative_stats,
    compute_quarantine_summary,
    filter_manifest_files,
    filter_quarantine,
    sort_history_entries,
)


# ---------------------------------------------------------------------------
# filter_manifest_files  (Task 5.1 — Requirement 6.4)
# ---------------------------------------------------------------------------

class TestFilterManifestFiles:
    def test_no_filters_returns_all(self):
        files = [
            {"s3_key": "a.pdf", "pipeline_status": "succeeded", "extraction_method": "pypdf2"},
            {"s3_key": "b.pdf", "pipeline_status": "failed", "extraction_method": "textract"},
        ]
        assert filter_manifest_files(files) == files

    def test_filter_by_pipeline_status(self):
        files = [
            {"s3_key": "a.pdf", "pipeline_status": "succeeded"},
            {"s3_key": "b.pdf", "pipeline_status": "failed"},
            {"s3_key": "c.pdf", "pipeline_status": "succeeded"},
        ]
        result = filter_manifest_files(files, pipeline_status="succeeded")
        assert len(result) == 2
        assert all(f["pipeline_status"] == "succeeded" for f in result)

    def test_filter_by_extraction_method(self):
        files = [
            {"s3_key": "a.pdf", "extraction_method": "pypdf2"},
            {"s3_key": "b.pdf", "extraction_method": "textract"},
        ]
        result = filter_manifest_files(files, extraction_method="textract")
        assert result == [files[1]]

    def test_filter_by_both(self):
        files = [
            {"s3_key": "a.pdf", "pipeline_status": "succeeded", "extraction_method": "pypdf2"},
            {"s3_key": "b.pdf", "pipeline_status": "succeeded", "extraction_method": "textract"},
            {"s3_key": "c.pdf", "pipeline_status": "failed", "extraction_method": "pypdf2"},
        ]
        result = filter_manifest_files(files, pipeline_status="succeeded", extraction_method="pypdf2")
        assert len(result) == 1
        assert result[0]["s3_key"] == "a.pdf"

    def test_no_matches(self):
        files = [{"s3_key": "a.pdf", "pipeline_status": "succeeded"}]
        assert filter_manifest_files(files, pipeline_status="failed") == []

    def test_empty_list(self):
        assert filter_manifest_files([]) == []
        assert filter_manifest_files([], pipeline_status="succeeded") == []

    def test_none_filters_explicitly(self):
        files = [{"s3_key": "a.pdf", "pipeline_status": "succeeded"}]
        assert filter_manifest_files(files, pipeline_status=None, extraction_method=None) == files


# ---------------------------------------------------------------------------
# compute_quarantine_summary  (Task 5.2 — Requirements 7.3)
# ---------------------------------------------------------------------------

class TestComputeQuarantineSummary:
    def test_empty_entries(self):
        result = compute_quarantine_summary([])
        assert result == {"total_quarantined": 0, "by_reason": {}, "most_recent": None}

    def test_categorises_extraction_failed(self):
        entries = [
            {"s3_key": "a.pdf", "reason": "PyPDF2 PdfReadError: EOF", "failed_at": "2026-01-01T00:00:00Z"},
            {"s3_key": "b.pdf", "reason": "Textract timeout on page 3", "failed_at": "2026-01-02T00:00:00Z"},
            {"s3_key": "c.pdf", "reason": "extraction failed: corrupt header", "failed_at": "2026-01-03T00:00:00Z"},
        ]
        result = compute_quarantine_summary(entries)
        assert result["total_quarantined"] == 3
        # "Textract timeout" contains both "textract" and "timeout" — textract check comes first
        assert result["by_reason"].get("extraction_failed", 0) >= 2

    def test_categorises_timeout(self):
        entries = [
            {"s3_key": "a.pdf", "reason": "timeout after 300s", "failed_at": "2026-01-01T00:00:00Z"},
        ]
        result = compute_quarantine_summary(entries)
        assert result["by_reason"]["timeout"] == 1

    def test_categorises_pipeline_failed(self):
        entries = [
            {"s3_key": "a.pdf", "reason": "SFN execution FAILED", "failed_at": "2026-01-01T00:00:00Z"},
        ]
        result = compute_quarantine_summary(entries)
        assert result["by_reason"]["pipeline_failed"] == 1

    def test_most_recent_is_max_timestamp(self):
        entries = [
            {"s3_key": "a.pdf", "reason": "failed", "failed_at": "2026-01-01T00:00:00Z"},
            {"s3_key": "b.pdf", "reason": "failed", "failed_at": "2026-06-15T12:00:00Z"},
            {"s3_key": "c.pdf", "reason": "failed", "failed_at": "2026-03-10T08:00:00Z"},
        ]
        result = compute_quarantine_summary(entries)
        assert result["most_recent"] == "2026-06-15T12:00:00Z"

    def test_by_reason_sums_to_total(self):
        entries = [
            {"s3_key": "a.pdf", "reason": "extraction failed", "failed_at": "2026-01-01T00:00:00Z"},
            {"s3_key": "b.pdf", "reason": "timeout", "failed_at": "2026-01-02T00:00:00Z"},
            {"s3_key": "c.pdf", "reason": "SFN FAILED", "failed_at": "2026-01-03T00:00:00Z"},
        ]
        result = compute_quarantine_summary(entries)
        assert sum(result["by_reason"].values()) == result["total_quarantined"]

    def test_entries_without_failed_at(self):
        entries = [{"s3_key": "a.pdf", "reason": "unknown"}]
        result = compute_quarantine_summary(entries)
        assert result["total_quarantined"] == 1
        assert result["most_recent"] is None


# ---------------------------------------------------------------------------
# filter_quarantine  (Task 5.2 — Requirement 7.4)
# ---------------------------------------------------------------------------

class TestFilterQuarantine:
    def test_empty_search_returns_all(self):
        entries = [{"s3_key": "a.pdf", "reason": "failed"}]
        assert filter_quarantine(entries, "") == entries

    def test_matches_s3_key_case_insensitive(self):
        entries = [
            {"s3_key": "pdfs/IMPORTANT_DOC.pdf", "reason": "timeout"},
            {"s3_key": "pdfs/other.pdf", "reason": "failed"},
        ]
        result = filter_quarantine(entries, "important")
        assert len(result) == 1
        assert result[0]["s3_key"] == "pdfs/IMPORTANT_DOC.pdf"

    def test_matches_reason_case_insensitive(self):
        entries = [
            {"s3_key": "a.pdf", "reason": "PyPDF2 PdfReadError"},
            {"s3_key": "b.pdf", "reason": "timeout"},
        ]
        result = filter_quarantine(entries, "pypdf2")
        assert len(result) == 1
        assert result[0]["s3_key"] == "a.pdf"

    def test_no_matches(self):
        entries = [{"s3_key": "a.pdf", "reason": "failed"}]
        assert filter_quarantine(entries, "zzz_nonexistent") == []

    def test_empty_entries(self):
        assert filter_quarantine([], "anything") == []

    def test_matches_both_fields(self):
        entries = [
            {"s3_key": "pdfs/error_doc.pdf", "reason": "extraction error"},
        ]
        # "error" appears in both s3_key and reason
        result = filter_quarantine(entries, "error")
        assert len(result) == 1


# ---------------------------------------------------------------------------
# sort_history_entries  (Task 5.3 — Requirement 8.2)
# ---------------------------------------------------------------------------

class TestSortHistoryEntries:
    def test_sorts_reverse_chronological(self):
        entries = [
            {"load_id": "batch_001", "timestamp": "2026-01-01T00:00:00Z"},
            {"load_id": "batch_003", "timestamp": "2026-03-01T00:00:00Z"},
            {"load_id": "batch_002", "timestamp": "2026-02-01T00:00:00Z"},
        ]
        result = sort_history_entries(entries)
        assert [e["load_id"] for e in result] == ["batch_003", "batch_002", "batch_001"]

    def test_empty_list(self):
        assert sort_history_entries([]) == []

    def test_single_entry(self):
        entries = [{"load_id": "batch_001", "timestamp": "2026-01-01T00:00:00Z"}]
        assert sort_history_entries(entries) == entries

    def test_already_sorted(self):
        entries = [
            {"load_id": "batch_002", "timestamp": "2026-02-01T00:00:00Z"},
            {"load_id": "batch_001", "timestamp": "2026-01-01T00:00:00Z"},
        ]
        result = sort_history_entries(entries)
        assert result == entries

    def test_missing_timestamp_sorts_to_end(self):
        entries = [
            {"load_id": "batch_001", "timestamp": "2026-01-01T00:00:00Z"},
            {"load_id": "batch_no_ts"},
        ]
        result = sort_history_entries(entries)
        assert result[0]["load_id"] == "batch_001"
        assert result[1]["load_id"] == "batch_no_ts"


# ---------------------------------------------------------------------------
# compute_cumulative_stats  (Task 5.3 — Requirements 8.2, 8.3)
# ---------------------------------------------------------------------------

class TestComputeCumulativeStats:
    def test_sums_fields(self):
        entries = [
            {"docs_sent_to_pipeline": 100, "blanks_skipped": 50, "cost_actual": 10.5},
            {"docs_sent_to_pipeline": 200, "blanks_skipped": 80, "cost_actual": 20.0},
        ]
        result = compute_cumulative_stats(entries)
        assert result == {
            "total_processed": 300,
            "total_blanks_filtered": 130,
            "total_estimated_cost": 30.5,
        }

    def test_empty_list(self):
        result = compute_cumulative_stats([])
        assert result == {
            "total_processed": 0,
            "total_blanks_filtered": 0,
            "total_estimated_cost": 0,
        }

    def test_missing_fields_default_to_zero(self):
        entries = [{"docs_sent_to_pipeline": 50}, {"blanks_skipped": 30}]
        result = compute_cumulative_stats(entries)
        assert result["total_processed"] == 50
        assert result["total_blanks_filtered"] == 30
        assert result["total_estimated_cost"] == 0

    def test_single_entry(self):
        entries = [{"docs_sent_to_pipeline": 42, "blanks_skipped": 10, "cost_actual": 5.0}]
        result = compute_cumulative_stats(entries)
        assert result == {
            "total_processed": 42,
            "total_blanks_filtered": 10,
            "total_estimated_cost": 5.0,
        }
