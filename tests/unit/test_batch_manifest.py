"""Unit tests for scripts/batch_loader/manifest.py — BatchManifest, FileEntry, BatchManifestData."""

import json
import os
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest

from scripts.batch_loader.config import BatchConfig
from scripts.batch_loader.manifest import (
    BatchManifest,
    BatchManifestData,
    FileEntry,
    LOCAL_MANIFESTS_DIR,
)


def _make_config(**overrides) -> BatchConfig:
    defaults = dict(
        case_id="test-case-id",
        data_lake_bucket="test-data-lake",
        source_bucket="test-source",
    )
    defaults.update(overrides)
    return BatchConfig(**defaults)


def _make_file_entry(**overrides) -> FileEntry:
    defaults = dict(
        s3_key="pdfs/doc_001.pdf",
        file_size_bytes=12345,
        extraction_method="pypdf2",
        extracted_char_count=5000,
        blank_filtered=False,
        pipeline_status="succeeded",
        sfn_execution_arn="arn:aws:states:us-east-1:123:execution:test",
        error_message=None,
    )
    defaults.update(overrides)
    return FileEntry(**defaults)


class TestFileEntry:
    """Verify FileEntry dataclass fields and defaults."""

    def test_required_fields(self):
        entry = _make_file_entry()
        assert entry.s3_key == "pdfs/doc_001.pdf"
        assert entry.file_size_bytes == 12345
        assert entry.extraction_method == "pypdf2"
        assert entry.extracted_char_count == 5000
        assert entry.blank_filtered is False
        assert entry.pipeline_status == "succeeded"

    def test_optional_fields_default_none(self):
        entry = FileEntry(
            s3_key="k",
            file_size_bytes=0,
            extraction_method="pypdf2",
            extracted_char_count=0,
            blank_filtered=False,
            pipeline_status="sent",
        )
        assert entry.sfn_execution_arn is None
        assert entry.error_message is None

    def test_error_message_set(self):
        entry = _make_file_entry(
            pipeline_status="failed",
            error_message="Timeout",
        )
        assert entry.error_message == "Timeout"


class TestBatchManifestData:
    """Verify BatchManifestData dataclass."""

    def test_all_fields_present(self):
        data = BatchManifestData(
            batch_id="batch_001",
            batch_number=1,
            started_at="2026-01-01T00:00:00Z",
            completed_at=None,
            source_prefix=["pdfs/"],
            files=[],
        )
        assert data.batch_id == "batch_001"
        assert data.batch_number == 1
        assert data.completed_at is None
        assert data.files == []

    def test_files_default_empty(self):
        data = BatchManifestData(
            batch_id="batch_002",
            batch_number=2,
            started_at="2026-01-01T00:00:00Z",
            completed_at=None,
            source_prefix=["pdfs/"],
        )
        assert data.files == []


class TestBatchManifestCreate:
    """Verify BatchManifest.create initializes a manifest correctly."""

    def test_create_sets_batch_id(self):
        config = _make_config()
        manifest_mgr = BatchManifest(config, MagicMock())
        manifest = manifest_mgr.create(1, ["pdfs/", "bw-documents/"])
        assert manifest.batch_id == "batch_001"
        assert manifest.batch_number == 1

    def test_create_sets_source_prefixes(self):
        config = _make_config()
        manifest_mgr = BatchManifest(config, MagicMock())
        manifest = manifest_mgr.create(5, ["pdfs/"])
        assert manifest.source_prefix == ["pdfs/"]

    def test_create_started_at_is_set(self):
        config = _make_config()
        manifest_mgr = BatchManifest(config, MagicMock())
        manifest = manifest_mgr.create(1, ["pdfs/"])
        assert manifest.started_at is not None
        assert len(manifest.started_at) > 0

    def test_create_completed_at_is_none(self):
        config = _make_config()
        manifest_mgr = BatchManifest(config, MagicMock())
        manifest = manifest_mgr.create(1, ["pdfs/"])
        assert manifest.completed_at is None

    def test_create_files_empty(self):
        config = _make_config()
        manifest_mgr = BatchManifest(config, MagicMock())
        manifest = manifest_mgr.create(1, ["pdfs/"])
        assert manifest.files == []

    def test_create_does_not_mutate_input_list(self):
        config = _make_config()
        manifest_mgr = BatchManifest(config, MagicMock())
        prefixes = ["pdfs/"]
        manifest = manifest_mgr.create(1, prefixes)
        manifest.source_prefix.append("extra/")
        assert prefixes == ["pdfs/"]


class TestBatchManifestAddFile:
    """Verify BatchManifest.add_file appends entries."""

    def test_add_single_file(self):
        config = _make_config()
        manifest_mgr = BatchManifest(config, MagicMock())
        manifest = manifest_mgr.create(1, ["pdfs/"])
        entry = _make_file_entry()
        manifest_mgr.add_file(manifest, entry)
        assert len(manifest.files) == 1
        assert manifest.files[0].s3_key == "pdfs/doc_001.pdf"

    def test_add_multiple_files(self):
        config = _make_config()
        manifest_mgr = BatchManifest(config, MagicMock())
        manifest = manifest_mgr.create(1, ["pdfs/"])
        for i in range(5):
            entry = _make_file_entry(s3_key=f"pdfs/doc_{i:03d}.pdf")
            manifest_mgr.add_file(manifest, entry)
        assert len(manifest.files) == 5
        keys = [f.s3_key for f in manifest.files]
        assert keys == [f"pdfs/doc_{i:03d}.pdf" for i in range(5)]


class TestBatchManifestSave:
    """Verify BatchManifest.save writes to S3 and local filesystem."""

    def test_save_writes_to_s3(self, tmp_path):
        config = _make_config()
        s3 = MagicMock()
        manifest_mgr = BatchManifest(config, s3)
        manifest = manifest_mgr.create(1, ["pdfs/"])
        manifest_mgr.add_file(manifest, _make_file_entry())

        with patch("scripts.batch_loader.manifest.LOCAL_MANIFESTS_DIR", str(tmp_path)):
            manifest_mgr.save(manifest)

        s3.put_object.assert_called_once()
        call_kwargs = s3.put_object.call_args[1]
        assert call_kwargs["Bucket"] == "test-data-lake"
        assert call_kwargs["Key"] == "batch-manifests/test-case-id/batch_001.json"
        assert call_kwargs["ContentType"] == "application/json"

        # Verify the body is valid JSON with expected structure
        body = json.loads(call_kwargs["Body"].decode("utf-8"))
        assert body["batch_id"] == "batch_001"
        assert body["batch_number"] == 1
        assert len(body["files"]) == 1
        assert body["files"][0]["s3_key"] == "pdfs/doc_001.pdf"

    def test_save_writes_local_file(self, tmp_path):
        config = _make_config()
        s3 = MagicMock()
        manifest_mgr = BatchManifest(config, s3)
        manifest = manifest_mgr.create(2, ["pdfs/"])
        manifest_mgr.add_file(manifest, _make_file_entry(s3_key="pdfs/local_test.pdf"))

        with patch("scripts.batch_loader.manifest.LOCAL_MANIFESTS_DIR", str(tmp_path)):
            manifest_mgr.save(manifest)

        local_file = tmp_path / "batch_002.json"
        assert local_file.exists()
        data = json.loads(local_file.read_text())
        assert data["batch_id"] == "batch_002"
        assert data["files"][0]["s3_key"] == "pdfs/local_test.pdf"

    def test_save_sets_completed_at(self, tmp_path):
        config = _make_config()
        s3 = MagicMock()
        manifest_mgr = BatchManifest(config, s3)
        manifest = manifest_mgr.create(1, ["pdfs/"])
        assert manifest.completed_at is None

        with patch("scripts.batch_loader.manifest.LOCAL_MANIFESTS_DIR", str(tmp_path)):
            manifest_mgr.save(manifest)

        assert manifest.completed_at is not None

    def test_save_preserves_existing_completed_at(self, tmp_path):
        config = _make_config()
        s3 = MagicMock()
        manifest_mgr = BatchManifest(config, s3)
        manifest = manifest_mgr.create(1, ["pdfs/"])
        manifest.completed_at = "2026-01-01T12:00:00Z"

        with patch("scripts.batch_loader.manifest.LOCAL_MANIFESTS_DIR", str(tmp_path)):
            manifest_mgr.save(manifest)

        assert manifest.completed_at == "2026-01-01T12:00:00Z"

    def test_save_handles_s3_error_gracefully(self, tmp_path):
        config = _make_config()
        s3 = MagicMock()
        s3.put_object.side_effect = Exception("S3 error")
        manifest_mgr = BatchManifest(config, s3)
        manifest = manifest_mgr.create(1, ["pdfs/"])

        # Should not raise — logs the error and continues to local save
        with patch("scripts.batch_loader.manifest.LOCAL_MANIFESTS_DIR", str(tmp_path)):
            manifest_mgr.save(manifest)

        # Local file should still be written
        local_file = tmp_path / "batch_001.json"
        assert local_file.exists()


class TestBatchManifestLoadCompletedKeys:
    """Verify BatchManifest.load_completed_keys reads keys from S3 manifests."""

    def _mock_s3_with_manifests(self, manifests: dict[str, dict]) -> MagicMock:
        """Create a mock S3 client that returns the given manifests.

        manifests: {s3_key: manifest_dict}
        """
        s3 = MagicMock()

        # Mock paginator
        contents = [{"Key": k} for k in manifests]
        paginator = MagicMock()
        paginator.paginate.return_value = [{"Contents": contents}]
        s3.get_paginator.return_value = paginator

        # Mock get_object for each manifest
        def get_object_side_effect(Bucket, Key):
            data = manifests[Key]
            body = MagicMock()
            body.read.return_value = json.dumps(data).encode("utf-8")
            return {"Body": body}

        s3.get_object.side_effect = get_object_side_effect
        return s3

    def test_load_keys_from_single_manifest(self):
        config = _make_config()
        manifest_data = {
            "files": [
                {"s3_key": "pdfs/doc_001.pdf"},
                {"s3_key": "pdfs/doc_002.pdf"},
            ]
        }
        s3 = self._mock_s3_with_manifests({
            "batch-manifests/test-case-id/batch_001.json": manifest_data,
        })
        manifest_mgr = BatchManifest(config, s3)
        keys = manifest_mgr.load_completed_keys()
        assert keys == {"pdfs/doc_001.pdf", "pdfs/doc_002.pdf"}

    def test_load_keys_from_multiple_manifests(self):
        config = _make_config()
        s3 = self._mock_s3_with_manifests({
            "batch-manifests/test-case-id/batch_001.json": {
                "files": [{"s3_key": "pdfs/a.pdf"}]
            },
            "batch-manifests/test-case-id/batch_002.json": {
                "files": [{"s3_key": "pdfs/b.pdf"}, {"s3_key": "pdfs/c.pdf"}]
            },
        })
        manifest_mgr = BatchManifest(config, s3)
        keys = manifest_mgr.load_completed_keys()
        assert keys == {"pdfs/a.pdf", "pdfs/b.pdf", "pdfs/c.pdf"}

    def test_load_keys_empty_when_no_manifests(self):
        config = _make_config()
        s3 = MagicMock()
        paginator = MagicMock()
        paginator.paginate.return_value = [{"Contents": []}]
        s3.get_paginator.return_value = paginator
        manifest_mgr = BatchManifest(config, s3)
        keys = manifest_mgr.load_completed_keys()
        assert keys == set()

    def test_load_keys_skips_non_json_files(self):
        config = _make_config()
        s3 = MagicMock()
        paginator = MagicMock()
        paginator.paginate.return_value = [
            {"Contents": [{"Key": "batch-manifests/test-case-id/README.txt"}]}
        ]
        s3.get_paginator.return_value = paginator
        manifest_mgr = BatchManifest(config, s3)
        keys = manifest_mgr.load_completed_keys()
        assert keys == set()
        # get_object should not be called for non-JSON files
        s3.get_object.assert_not_called()

    def test_load_keys_handles_corrupt_manifest(self):
        config = _make_config()
        s3 = MagicMock()
        paginator = MagicMock()
        paginator.paginate.return_value = [
            {"Contents": [
                {"Key": "batch-manifests/test-case-id/batch_001.json"},
            ]}
        ]
        s3.get_paginator.return_value = paginator

        # Return invalid JSON
        body = MagicMock()
        body.read.return_value = b"not valid json"
        s3.get_object.return_value = {"Body": body}

        manifest_mgr = BatchManifest(config, s3)
        keys = manifest_mgr.load_completed_keys()
        # Should return empty set, not raise
        assert keys == set()

    def test_load_keys_handles_s3_list_error(self):
        config = _make_config()
        s3 = MagicMock()
        paginator = MagicMock()
        paginator.paginate.side_effect = Exception("S3 list error")
        s3.get_paginator.return_value = paginator

        manifest_mgr = BatchManifest(config, s3)
        keys = manifest_mgr.load_completed_keys()
        assert keys == set()


class TestManifestCompleteness:
    """Verify that manifests contain all required fields per Requirement 11.1."""

    def test_all_required_fields_in_serialized_manifest(self, tmp_path):
        config = _make_config()
        s3 = MagicMock()
        manifest_mgr = BatchManifest(config, s3)
        manifest = manifest_mgr.create(1, ["pdfs/", "bw-documents/"])

        entries = [
            _make_file_entry(s3_key=f"pdfs/doc_{i:03d}.pdf")
            for i in range(3)
        ]
        for entry in entries:
            manifest_mgr.add_file(manifest, entry)

        with patch("scripts.batch_loader.manifest.LOCAL_MANIFESTS_DIR", str(tmp_path)):
            manifest_mgr.save(manifest)

        # Read back the saved JSON
        local_file = tmp_path / "batch_001.json"
        data = json.loads(local_file.read_text())

        # Top-level required fields
        assert "batch_id" in data
        assert "batch_number" in data
        assert "started_at" in data
        assert "completed_at" in data
        assert "source_prefix" in data
        assert "files" in data

        # Per-file required fields
        required_file_fields = {
            "s3_key", "file_size_bytes", "extraction_method",
            "extracted_char_count", "blank_filtered", "pipeline_status",
            "sfn_execution_arn", "error_message",
        }
        for file_data in data["files"]:
            assert required_file_fields.issubset(file_data.keys()), (
                f"Missing fields: {required_file_fields - file_data.keys()}"
            )

    def test_manifest_keys_match_input_keys(self):
        config = _make_config()
        manifest_mgr = BatchManifest(config, MagicMock())
        manifest = manifest_mgr.create(1, ["pdfs/"])

        input_keys = {f"pdfs/doc_{i:03d}.pdf" for i in range(10)}
        for key in sorted(input_keys):
            manifest_mgr.add_file(manifest, _make_file_entry(s3_key=key))

        manifest_keys = {f.s3_key for f in manifest.files}
        assert manifest_keys == input_keys
