"""Unit tests for BatchLoaderState service."""

import io
import json
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from src.services.batch_loader_state import BatchLoaderState, TERMINAL_STATUSES, VALID_STATUSES


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

BUCKET = "test-data-lake-bucket"
CASE_ID = "ed0b6c27-3b6b-4255-b9d0-efe8f4383a99"


def _make_s3_body(data):
    """Create a mock S3 response body from a Python dict."""
    body = io.BytesIO(json.dumps(data).encode("utf-8"))
    return {"Body": body}


def _no_such_key_error():
    """Return a ClientError simulating NoSuchKey."""
    return ClientError(
        {"Error": {"Code": "NoSuchKey", "Message": "Not found"}},
        "GetObject",
    )


@pytest.fixture
def s3_client():
    return MagicMock()


@pytest.fixture
def state(s3_client):
    return BatchLoaderState(s3_client, BUCKET, CASE_ID)


# ---------------------------------------------------------------------------
# Constructor / key paths
# ---------------------------------------------------------------------------

class TestConstructor:
    def test_key_paths(self, state):
        assert state.progress_key == f"batch-progress/{CASE_ID}/batch_progress.json"
        assert state.quarantine_key == f"batch-progress/{CASE_ID}/quarantine.json"
        assert state.ledger_key == f"batch-progress/{CASE_ID}/ingestion_ledger.json"
        assert state.manifests_prefix == f"batch-manifests/{CASE_ID}/"


# ---------------------------------------------------------------------------
# read_progress / write_progress
# ---------------------------------------------------------------------------

class TestProgress:
    def test_read_progress_returns_dict(self, state, s3_client):
        progress = {"batch_id": "batch_001", "status": "extracting"}
        s3_client.get_object.return_value = _make_s3_body(progress)

        result = state.read_progress()

        assert result == progress
        s3_client.get_object.assert_called_once_with(
            Bucket=BUCKET, Key=state.progress_key
        )

    def test_read_progress_returns_none_when_missing(self, state, s3_client):
        s3_client.get_object.side_effect = _no_such_key_error()

        result = state.read_progress()

        assert result is None

    def test_read_progress_raises_on_other_errors(self, state, s3_client):
        s3_client.get_object.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "Forbidden"}},
            "GetObject",
        )
        with pytest.raises(ClientError):
            state.read_progress()

    def test_write_progress(self, state, s3_client):
        progress = {"batch_id": "batch_002", "status": "discovery"}

        state.write_progress(progress)

        s3_client.put_object.assert_called_once()
        call_kwargs = s3_client.put_object.call_args[1]
        assert call_kwargs["Bucket"] == BUCKET
        assert call_kwargs["Key"] == state.progress_key
        assert call_kwargs["ContentType"] == "application/json"
        written = json.loads(call_kwargs["Body"].decode("utf-8"))
        assert written == progress


# ---------------------------------------------------------------------------
# read_quarantine / write_quarantine
# ---------------------------------------------------------------------------

class TestQuarantine:
    def test_read_quarantine_returns_entries(self, state, s3_client):
        entries = [
            {"s3_key": "pdfs/bad.pdf", "reason": "extraction_failed", "failed_at": "2026-01-01T00:00:00Z", "retry_count": 3, "batch_number": 1}
        ]
        s3_client.get_object.return_value = _make_s3_body({"quarantined_keys": entries})

        result = state.read_quarantine()

        assert result == entries

    def test_read_quarantine_returns_empty_list_when_missing(self, state, s3_client):
        s3_client.get_object.side_effect = _no_such_key_error()

        result = state.read_quarantine()

        assert result == []

    def test_write_quarantine(self, state, s3_client):
        entries = [{"s3_key": "pdfs/bad.pdf", "reason": "timeout"}]

        state.write_quarantine(entries)

        call_kwargs = s3_client.put_object.call_args[1]
        written = json.loads(call_kwargs["Body"].decode("utf-8"))
        assert written == {"quarantined_keys": entries}


# ---------------------------------------------------------------------------
# read_ledger / append_ledger_entry
# ---------------------------------------------------------------------------

class TestLedger:
    def test_read_ledger_returns_data(self, state, s3_client):
        ledger = {"cases": {CASE_ID: {"name": "Test", "loads": [], "running_total_s3_docs": 0}}}
        s3_client.get_object.return_value = _make_s3_body(ledger)

        result = state.read_ledger()

        assert result == ledger

    def test_read_ledger_returns_empty_structure_when_missing(self, state, s3_client):
        s3_client.get_object.side_effect = _no_such_key_error()

        result = state.read_ledger()

        assert result == {"cases": {}}

    def test_append_ledger_entry_creates_case_if_missing(self, state, s3_client):
        # First read returns empty ledger
        s3_client.get_object.side_effect = _no_such_key_error()
        entry = {"load_id": "batch_001", "timestamp": "2026-01-01T00:00:00Z"}

        state.append_ledger_entry(entry)

        call_kwargs = s3_client.put_object.call_args[1]
        written = json.loads(call_kwargs["Body"].decode("utf-8"))
        assert CASE_ID in written["cases"]
        assert written["cases"][CASE_ID]["loads"] == [entry]

    def test_append_ledger_entry_appends_to_existing(self, state, s3_client):
        existing_entry = {"load_id": "batch_001"}
        ledger = {"cases": {CASE_ID: {"name": "Test", "loads": [existing_entry], "running_total_s3_docs": 100}}}
        s3_client.get_object.return_value = _make_s3_body(ledger)
        new_entry = {"load_id": "batch_002"}

        state.append_ledger_entry(new_entry)

        call_kwargs = s3_client.put_object.call_args[1]
        written = json.loads(call_kwargs["Body"].decode("utf-8"))
        loads = written["cases"][CASE_ID]["loads"]
        assert len(loads) == 2
        assert loads[0] == existing_entry
        assert loads[1] == new_entry


# ---------------------------------------------------------------------------
# list_manifests / read_manifest
# ---------------------------------------------------------------------------

class TestManifests:
    def _manifest(self, batch_id, batch_number, files):
        return {
            "batch_id": batch_id,
            "batch_number": batch_number,
            "started_at": "2026-01-01T00:00:00Z",
            "completed_at": "2026-01-01T01:00:00Z",
            "files": files,
        }

    def test_list_manifests_aggregates_stats(self, state, s3_client):
        files = [
            {"s3_key": "a.pdf", "pipeline_status": "succeeded", "blank_filtered": False},
            {"s3_key": "b.pdf", "pipeline_status": "failed", "blank_filtered": False},
            {"s3_key": "c.pdf", "pipeline_status": "succeeded", "blank_filtered": True},
            {"s3_key": "d.pdf", "pipeline_status": "quarantined", "blank_filtered": False},
        ]
        manifest = self._manifest("batch_001", 1, files)

        paginator = MagicMock()
        s3_client.get_paginator.return_value = paginator
        paginator.paginate.return_value = [
            {"Contents": [{"Key": f"batch-manifests/{CASE_ID}/batch_001.json"}]}
        ]
        s3_client.get_object.return_value = _make_s3_body(manifest)

        result = state.list_manifests()

        assert len(result) == 1
        summary = result[0]
        assert summary["batch_id"] == "batch_001"
        assert summary["batch_number"] == 1
        assert summary["total_files"] == 4
        assert summary["succeeded"] == 2
        assert summary["failed"] == 1
        assert summary["blank_filtered"] == 1
        assert summary["quarantined"] == 1

    def test_list_manifests_multiple_manifests(self, state, s3_client):
        m1 = self._manifest("batch_001", 1, [
            {"s3_key": "a.pdf", "pipeline_status": "succeeded", "blank_filtered": False},
        ])
        m2 = self._manifest("batch_002", 2, [
            {"s3_key": "b.pdf", "pipeline_status": "failed", "blank_filtered": False},
            {"s3_key": "c.pdf", "pipeline_status": "succeeded", "blank_filtered": False},
        ])

        paginator = MagicMock()
        s3_client.get_paginator.return_value = paginator
        paginator.paginate.return_value = [
            {"Contents": [
                {"Key": f"batch-manifests/{CASE_ID}/batch_001.json"},
                {"Key": f"batch-manifests/{CASE_ID}/batch_002.json"},
            ]}
        ]
        s3_client.get_object.side_effect = [
            _make_s3_body(m1),
            _make_s3_body(m2),
        ]

        result = state.list_manifests()

        assert len(result) == 2
        assert result[0]["total_files"] == 1
        assert result[1]["total_files"] == 2

    def test_list_manifests_skips_non_json(self, state, s3_client):
        paginator = MagicMock()
        s3_client.get_paginator.return_value = paginator
        paginator.paginate.return_value = [
            {"Contents": [{"Key": f"batch-manifests/{CASE_ID}/readme.txt"}]}
        ]

        result = state.list_manifests()

        assert result == []
        s3_client.get_object.assert_not_called()

    def test_list_manifests_empty(self, state, s3_client):
        paginator = MagicMock()
        s3_client.get_paginator.return_value = paginator
        paginator.paginate.return_value = [{"Contents": []}]

        result = state.list_manifests()

        assert result == []

    def test_read_manifest_returns_full_json(self, state, s3_client):
        manifest = {"batch_id": "batch_005", "files": [{"s3_key": "x.pdf"}]}
        s3_client.get_object.return_value = _make_s3_body(manifest)

        result = state.read_manifest("batch_005")

        assert result == manifest
        s3_client.get_object.assert_called_once_with(
            Bucket=BUCKET,
            Key=f"batch-manifests/{CASE_ID}/batch_005.json",
        )

    def test_read_manifest_returns_none_when_missing(self, state, s3_client):
        s3_client.get_object.side_effect = _no_such_key_error()

        result = state.read_manifest("batch_999")

        assert result is None


# ---------------------------------------------------------------------------
# is_batch_in_progress
# ---------------------------------------------------------------------------

class TestIsBatchInProgress:
    def test_returns_false_when_no_progress(self, state, s3_client):
        s3_client.get_object.side_effect = _no_such_key_error()

        running, batch_id = state.is_batch_in_progress()

        assert running is False
        assert batch_id is None

    @pytest.mark.parametrize("status", ["completed", "failed"])
    def test_returns_false_for_terminal_statuses(self, state, s3_client, status):
        progress = {"batch_id": "batch_010", "status": status}
        s3_client.get_object.return_value = _make_s3_body(progress)

        running, batch_id = state.is_batch_in_progress()

        assert running is False
        assert batch_id is None

    @pytest.mark.parametrize("status", [
        "discovery", "extracting", "filtering", "ingesting",
        "polling_sfn", "entity_resolution", "paused",
    ])
    def test_returns_true_for_non_terminal_statuses(self, state, s3_client, status):
        progress = {"batch_id": "batch_010", "status": status}
        s3_client.get_object.return_value = _make_s3_body(progress)

        running, batch_id = state.is_batch_in_progress()

        assert running is True
        assert batch_id == "batch_010"

    def test_returns_false_when_status_missing_from_progress(self, state, s3_client):
        progress = {"batch_id": "batch_010"}
        s3_client.get_object.return_value = _make_s3_body(progress)

        running, batch_id = state.is_batch_in_progress()

        assert running is False
        assert batch_id is None
