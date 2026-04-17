"""Unit tests for scripts/batch_loader/config.py — BatchConfig and parse_args."""

import sys
from unittest.mock import patch

import pytest

from scripts.batch_loader.config import BatchConfig, parse_args


class TestBatchConfigDefaults:
    """Verify BatchConfig dataclass has correct default values."""

    def test_default_batch_size(self):
        config = BatchConfig()
        assert config.batch_size == 5000

    def test_default_case_id(self):
        config = BatchConfig()
        assert config.case_id == "ed0b6c27-3b6b-4255-b9d0-efe8f4383a99"

    def test_default_sub_batch_size(self):
        config = BatchConfig()
        assert config.sub_batch_size == 50

    def test_default_flags(self):
        config = BatchConfig()
        assert config.dry_run is False
        assert config.confirm is False
        assert config.no_entity_resolution is False

    def test_default_max_batches(self):
        config = BatchConfig()
        assert config.max_batches == 1

    def test_default_thresholds(self):
        config = BatchConfig()
        assert config.ocr_threshold == 50
        assert config.blank_threshold == 10

    def test_default_source_prefixes(self):
        config = BatchConfig()
        assert config.source_prefixes == ["pdfs/", "bw-documents/"]

    def test_default_buckets(self):
        config = BatchConfig()
        assert config.source_bucket == "doj-cases-974220725866-us-east-1"
        assert config.data_lake_bucket == "research-analyst-data-lake-974220725866"

    def test_default_api_url(self):
        config = BatchConfig()
        assert config.api_url == "https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1"

    def test_default_timing(self):
        config = BatchConfig()
        assert config.sub_batch_delay == 2.0
        assert config.poll_initial_delay == 30
        assert config.poll_max_delay == 300

    def test_default_retry_and_failure(self):
        config = BatchConfig()
        assert config.max_retries == 3
        assert config.failure_threshold == 0.10

    def test_source_prefixes_are_independent_across_instances(self):
        a = BatchConfig()
        b = BatchConfig()
        a.source_prefixes.append("extra/")
        assert "extra/" not in b.source_prefixes


class TestParseArgs:
    """Verify parse_args maps CLI flags to BatchConfig correctly."""

    def test_all_defaults(self):
        with patch.object(sys, "argv", ["batch_loader"]):
            config = parse_args()
        assert config.batch_size == 5000
        assert config.dry_run is False
        assert config.confirm is False
        assert config.source_prefixes == ["pdfs/", "bw-documents/"]

    def test_batch_size_override(self):
        with patch.object(sys, "argv", ["batch_loader", "--batch-size", "1000"]):
            config = parse_args()
        assert config.batch_size == 1000

    def test_case_id_override(self):
        with patch.object(sys, "argv", ["batch_loader", "--case-id", "abc-123"]):
            config = parse_args()
        assert config.case_id == "abc-123"

    def test_sub_batch_size_override(self):
        with patch.object(sys, "argv", ["batch_loader", "--sub-batch-size", "25"]):
            config = parse_args()
        assert config.sub_batch_size == 25

    def test_dry_run_flag(self):
        with patch.object(sys, "argv", ["batch_loader", "--dry-run"]):
            config = parse_args()
        assert config.dry_run is True

    def test_confirm_flag(self):
        with patch.object(sys, "argv", ["batch_loader", "--confirm"]):
            config = parse_args()
        assert config.confirm is True

    def test_no_entity_resolution_flag(self):
        with patch.object(sys, "argv", ["batch_loader", "--no-entity-resolution"]):
            config = parse_args()
        assert config.no_entity_resolution is True

    def test_max_batches_override(self):
        with patch.object(sys, "argv", ["batch_loader", "--max-batches", "5"]):
            config = parse_args()
        assert config.max_batches == 5

    def test_ocr_threshold_override(self):
        with patch.object(sys, "argv", ["batch_loader", "--ocr-threshold", "100"]):
            config = parse_args()
        assert config.ocr_threshold == 100

    def test_blank_threshold_override(self):
        with patch.object(sys, "argv", ["batch_loader", "--blank-threshold", "20"]):
            config = parse_args()
        assert config.blank_threshold == 20

    def test_source_prefixes_override(self):
        with patch.object(sys, "argv", ["batch_loader", "--source-prefixes", "a/", "b/", "c/"]):
            config = parse_args()
        assert config.source_prefixes == ["a/", "b/", "c/"]

    def test_multiple_flags_combined(self):
        with patch.object(sys, "argv", [
            "batch_loader",
            "--batch-size", "2000",
            "--dry-run",
            "--max-batches", "3",
            "--no-entity-resolution",
        ]):
            config = parse_args()
        assert config.batch_size == 2000
        assert config.dry_run is True
        assert config.max_batches == 3
        assert config.no_entity_resolution is True
        # Non-overridden fields keep defaults
        assert config.sub_batch_size == 50
        assert config.confirm is False
