"""Unit tests for src/storage/s3_helper.py."""

import os
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest

from src.storage.s3_helper import (
    PrefixType,
    build_collection_key,
    build_key,
    case_prefix,
    delete_case_prefix,
    delete_file,
    download_file,
    list_files,
    org_matter_collection_prefix,
    prefix_path,
    resolve_document_path,
    upload_file,
)

BUCKET = "test-bucket"


# ---------------------------------------------------------------------------
# Path builder tests
# ---------------------------------------------------------------------------


class TestPathBuilders:
    def test_case_prefix(self):
        assert case_prefix("abc-123") == "cases/abc-123/"

    @pytest.mark.parametrize(
        "ptype,expected_segment",
        [
            (PrefixType.RAW, "raw"),
            (PrefixType.PROCESSED, "processed"),
            (PrefixType.EXTRACTIONS, "extractions"),
            (PrefixType.BULK_LOAD, "bulk-load"),
        ],
    )
    def test_prefix_path(self, ptype, expected_segment):
        result = prefix_path("case1", ptype)
        assert result == f"cases/case1/{expected_segment}/"

    def test_build_key_with_enum(self):
        key = build_key("case1", PrefixType.RAW, "doc.pdf")
        assert key == "cases/case1/raw/doc.pdf"

    def test_build_key_with_string(self):
        key = build_key("case1", "processed", "doc.json")
        assert key == "cases/case1/processed/doc.json"

    def test_build_key_bulk_load(self):
        key = build_key("case1", "bulk-load", "batch1_nodes.csv")
        assert key == "cases/case1/bulk-load/batch1_nodes.csv"

    def test_build_key_extractions(self):
        key = build_key("case1", "extractions", "doc1_extraction.json")
        assert key == "cases/case1/extractions/doc1_extraction.json"

    def test_build_key_invalid_prefix_type(self):
        with pytest.raises(ValueError):
            build_key("case1", "invalid", "file.txt")

    def test_prefix_path_accepts_string(self):
        assert prefix_path("c1", "raw") == "cases/c1/raw/"


# ---------------------------------------------------------------------------
# S3 operation tests (mocked boto3)
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _set_bucket_env(monkeypatch):
    monkeypatch.setenv("S3_BUCKET_NAME", BUCKET)


@pytest.fixture
def mock_s3():
    with patch("src.storage.s3_helper._get_s3_client") as factory:
        client = MagicMock()
        factory.return_value = client
        yield client


class TestUploadFile:
    def test_upload_bytes(self, mock_s3):
        key = upload_file("c1", "raw", "doc.pdf", b"hello")
        assert key == "cases/c1/raw/doc.pdf"
        mock_s3.put_object.assert_called_once_with(
            Bucket=BUCKET, Key="cases/c1/raw/doc.pdf", Body=b"hello"
        )

    def test_upload_string(self, mock_s3):
        upload_file("c1", "processed", "doc.json", '{"a":1}')
        mock_s3.put_object.assert_called_once_with(
            Bucket=BUCKET,
            Key="cases/c1/processed/doc.json",
            Body=b'{"a":1}',
        )

    def test_upload_fileobj(self, mock_s3):
        fobj = BytesIO(b"data")
        upload_file("c1", "raw", "f.bin", fobj)
        mock_s3.upload_fileobj.assert_called_once_with(
            fobj, BUCKET, "cases/c1/raw/f.bin"
        )

    def test_upload_with_explicit_bucket(self, mock_s3):
        key = upload_file("c1", "raw", "f.txt", b"x", bucket="other-bucket")
        assert key == "cases/c1/raw/f.txt"
        mock_s3.put_object.assert_called_once_with(
            Bucket="other-bucket", Key="cases/c1/raw/f.txt", Body=b"x"
        )


class TestDownloadFile:
    def test_download(self, mock_s3):
        body_mock = MagicMock()
        body_mock.read.return_value = b"content"
        mock_s3.get_object.return_value = {"Body": body_mock}

        result = download_file("c1", "raw", "doc.pdf")
        assert result == b"content"
        mock_s3.get_object.assert_called_once_with(
            Bucket=BUCKET, Key="cases/c1/raw/doc.pdf"
        )


class TestListFiles:
    def test_list_files(self, mock_s3):
        paginator = MagicMock()
        mock_s3.get_paginator.return_value = paginator
        paginator.paginate.return_value = [
            {
                "Contents": [
                    {"Key": "cases/c1/raw/a.pdf"},
                    {"Key": "cases/c1/raw/b.txt"},
                ]
            }
        ]

        result = list_files("c1", "raw")
        assert result == ["a.pdf", "b.txt"]

    def test_list_files_empty(self, mock_s3):
        paginator = MagicMock()
        mock_s3.get_paginator.return_value = paginator
        paginator.paginate.return_value = [{}]

        result = list_files("c1", "raw")
        assert result == []

    def test_list_files_multiple_pages(self, mock_s3):
        paginator = MagicMock()
        mock_s3.get_paginator.return_value = paginator
        paginator.paginate.return_value = [
            {"Contents": [{"Key": "cases/c1/raw/a.pdf"}]},
            {"Contents": [{"Key": "cases/c1/raw/b.pdf"}]},
        ]

        result = list_files("c1", "raw")
        assert result == ["a.pdf", "b.pdf"]


class TestDeleteFile:
    def test_delete(self, mock_s3):
        delete_file("c1", "raw", "doc.pdf")
        mock_s3.delete_object.assert_called_once_with(
            Bucket=BUCKET, Key="cases/c1/raw/doc.pdf"
        )


class TestDeleteCasePrefix:
    def test_delete_case_prefix(self, mock_s3):
        paginator = MagicMock()
        mock_s3.get_paginator.return_value = paginator
        paginator.paginate.return_value = [
            {
                "Contents": [
                    {"Key": "cases/c1/raw/a.pdf"},
                    {"Key": "cases/c1/processed/b.json"},
                ]
            }
        ]

        count = delete_case_prefix("c1")
        assert count == 2
        mock_s3.delete_objects.assert_called_once_with(
            Bucket=BUCKET,
            Delete={
                "Objects": [
                    {"Key": "cases/c1/raw/a.pdf"},
                    {"Key": "cases/c1/processed/b.json"},
                ],
                "Quiet": True,
            },
        )

    def test_delete_case_prefix_empty(self, mock_s3):
        paginator = MagicMock()
        mock_s3.get_paginator.return_value = paginator
        paginator.paginate.return_value = [{}]

        count = delete_case_prefix("c1")
        assert count == 0
        mock_s3.delete_objects.assert_not_called()


class TestMissingBucketEnv:
    def test_upload_raises_without_env(self, monkeypatch):
        monkeypatch.delenv("S3_BUCKET_NAME", raising=False)
        with pytest.raises(EnvironmentError, match="S3_BUCKET_NAME"):
            upload_file("c1", "raw", "f.txt", b"x")


# ---------------------------------------------------------------------------
# New hierarchy path builder tests
# ---------------------------------------------------------------------------


class TestOrgMatterCollectionPrefix:
    def test_basic_prefix(self):
        result = org_matter_collection_prefix("org1", "mat1", "col1")
        assert result == "orgs/org1/matters/mat1/collections/col1/"

    def test_uuid_style_ids(self):
        result = org_matter_collection_prefix(
            "550e8400-e29b-41d4-a716-446655440000",
            "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
            "f47ac10b-58cc-4372-a567-0e02b2c3d479",
        )
        assert result == (
            "orgs/550e8400-e29b-41d4-a716-446655440000/"
            "matters/6ba7b810-9dad-11d1-80b4-00c04fd430c8/"
            "collections/f47ac10b-58cc-4372-a567-0e02b2c3d479/"
        )


class TestBuildCollectionKey:
    def test_raw_prefix(self):
        key = build_collection_key("org1", "mat1", "col1", PrefixType.RAW, "doc.pdf")
        assert key == "orgs/org1/matters/mat1/collections/col1/raw/doc.pdf"

    def test_processed_prefix(self):
        key = build_collection_key("org1", "mat1", "col1", "processed", "doc.json")
        assert key == "orgs/org1/matters/mat1/collections/col1/processed/doc.json"

    def test_extractions_prefix(self):
        key = build_collection_key("org1", "mat1", "col1", "extractions", "ext.json")
        assert key == "orgs/org1/matters/mat1/collections/col1/extractions/ext.json"

    def test_bulk_load_prefix(self):
        key = build_collection_key("org1", "mat1", "col1", "bulk-load", "nodes.csv")
        assert key == "orgs/org1/matters/mat1/collections/col1/bulk-load/nodes.csv"

    def test_invalid_prefix_type(self):
        with pytest.raises(ValueError):
            build_collection_key("org1", "mat1", "col1", "invalid", "f.txt")


class TestResolveDocumentPath:
    def test_new_hierarchy_preferred(self):
        result = resolve_document_path(
            case_id="legacy-case",
            org_id="org1",
            matter_id="mat1",
            collection_id="col1",
            prefix_type=PrefixType.RAW,
            filename="doc.pdf",
        )
        assert result == "orgs/org1/matters/mat1/collections/col1/raw/doc.pdf"

    def test_fallback_to_legacy(self):
        result = resolve_document_path(
            case_id="legacy-case",
            org_id=None,
            matter_id=None,
            collection_id=None,
            prefix_type=PrefixType.RAW,
            filename="doc.pdf",
        )
        assert result == "cases/legacy-case/raw/doc.pdf"

    def test_fallback_when_partial_new_params(self):
        # Only org_id provided, missing matter_id and collection_id
        result = resolve_document_path(
            case_id="legacy-case",
            org_id="org1",
            matter_id=None,
            collection_id=None,
            prefix_type="processed",
            filename="doc.json",
        )
        assert result == "cases/legacy-case/processed/doc.json"

    def test_raises_when_no_ids(self):
        with pytest.raises(ValueError, match="Either.*or case_id must be provided"):
            resolve_document_path(
                case_id=None,
                org_id=None,
                matter_id=None,
                collection_id=None,
                prefix_type=PrefixType.RAW,
                filename="doc.pdf",
            )

    def test_new_hierarchy_without_case_id(self):
        result = resolve_document_path(
            case_id=None,
            org_id="org1",
            matter_id="mat1",
            collection_id="col1",
            prefix_type="raw",
            filename="file.txt",
        )
        assert result == "orgs/org1/matters/mat1/collections/col1/raw/file.txt"
