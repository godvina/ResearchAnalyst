"""Unit tests for scripts/batch_loader/ingestion.py — PipelineIngestion."""

import base64
import json
import math
from unittest.mock import MagicMock, patch, call

import pytest

from scripts.batch_loader.config import BatchConfig
from scripts.batch_loader.ingestion import PipelineIngestion, TERMINAL_STATES


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_config(**overrides) -> BatchConfig:
    defaults = dict(sub_batch_size=3, sub_batch_delay=0.0, max_retries=2, poll_initial_delay=1, poll_max_delay=8)
    defaults.update(overrides)
    return BatchConfig(**defaults)


def _fake_urlopen_response(execution_arn="arn:aws:states:us-east-1:123:execution:pipe:abc"):
    """Return a context-manager mock that behaves like urllib.request.urlopen."""
    resp_body = json.dumps({"execution_arn": execution_arn, "documents_uploaded": 3}).encode()
    mock_resp = MagicMock()
    mock_resp.read.return_value = resp_body
    mock_resp.__enter__ = MagicMock(return_value=mock_resp)
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


# ===========================================================================
# Sub-batch partitioning
# ===========================================================================

class TestSubBatchPartitioning:
    """Verify documents are correctly partitioned into sub-batches."""

    def test_exact_multiple(self):
        config = _make_config(sub_batch_size=2)
        ingestion = PipelineIngestion(config)
        docs = [("a.txt", "aaa"), ("b.txt", "bbb"), ("c.txt", "ccc"), ("d.txt", "ddd")]

        with patch("scripts.batch_loader.ingestion.urllib.request.urlopen") as mock_open:
            mock_open.return_value = _fake_urlopen_response()
            arns = ingestion.send_sub_batches(docs)

        # 4 docs / 2 per batch = 2 API calls
        assert mock_open.call_count == 2
        assert len(arns) == 2

    def test_remainder_batch(self):
        config = _make_config(sub_batch_size=3)
        ingestion = PipelineIngestion(config)
        docs = [("a.txt", "aaa"), ("b.txt", "bbb"), ("c.txt", "ccc"), ("d.txt", "ddd"), ("e.txt", "eee")]

        with patch("scripts.batch_loader.ingestion.urllib.request.urlopen") as mock_open:
            mock_open.return_value = _fake_urlopen_response()
            arns = ingestion.send_sub_batches(docs)

        # ceil(5/3) = 2 API calls
        assert mock_open.call_count == 2
        assert len(arns) == 2

    def test_single_doc(self):
        config = _make_config(sub_batch_size=50)
        ingestion = PipelineIngestion(config)
        docs = [("only.txt", "content")]

        with patch("scripts.batch_loader.ingestion.urllib.request.urlopen") as mock_open:
            mock_open.return_value = _fake_urlopen_response()
            arns = ingestion.send_sub_batches(docs)

        assert mock_open.call_count == 1
        assert len(arns) == 1

    def test_empty_documents(self):
        config = _make_config()
        ingestion = PipelineIngestion(config)
        arns = ingestion.send_sub_batches([])
        assert arns == []


# ===========================================================================
# _send_single_batch request format
# ===========================================================================

class TestSendSingleBatch:
    """Verify _send_single_batch builds the correct HTTP request."""

    def test_request_format(self):
        config = _make_config()
        ingestion = PipelineIngestion(config)
        texts = [("doc1.txt", "Hello world"), ("doc2.txt", "Second doc")]

        with patch("scripts.batch_loader.ingestion.urllib.request.urlopen") as mock_open:
            mock_open.return_value = _fake_urlopen_response("arn:test:123")
            arn = ingestion._send_single_batch("case-abc", texts)

        assert arn == "arn:test:123"
        # Verify the request was made
        assert mock_open.call_count == 1
        req = mock_open.call_args[0][0]
        assert req.full_url == f"{config.api_url}/case-files/case-abc/ingest"
        assert req.method == "POST"
        assert req.get_header("Content-type") == "application/json"

        # Verify payload
        payload = json.loads(req.data.decode())
        assert "files" in payload
        assert len(payload["files"]) == 2
        assert payload["files"][0]["filename"] == "doc1.txt"
        decoded = base64.b64decode(payload["files"][0]["content_base64"]).decode("utf-8")
        assert decoded == "Hello world"

    def test_base64_encoding(self):
        config = _make_config()
        ingestion = PipelineIngestion(config)
        text = "Special chars: àéîõü 日本語"
        texts = [("unicode.txt", text)]

        with patch("scripts.batch_loader.ingestion.urllib.request.urlopen") as mock_open:
            mock_open.return_value = _fake_urlopen_response()
            ingestion._send_single_batch("case-1", texts)

        req = mock_open.call_args[0][0]
        payload = json.loads(req.data.decode())
        decoded = base64.b64decode(payload["files"][0]["content_base64"]).decode("utf-8")
        assert decoded == text

    def test_empty_texts_returns_none(self):
        config = _make_config()
        ingestion = PipelineIngestion(config)
        result = ingestion._send_single_batch("case-1", [])
        assert result is None

    def test_retry_on_failure(self):
        config = _make_config(max_retries=3)
        ingestion = PipelineIngestion(config)
        texts = [("doc.txt", "content")]

        with patch("scripts.batch_loader.ingestion.urllib.request.urlopen") as mock_open, \
             patch("scripts.batch_loader.ingestion.time.sleep"):
            # Fail twice, succeed on third
            mock_open.side_effect = [
                Exception("Connection refused"),
                Exception("Timeout"),
                _fake_urlopen_response("arn:success"),
            ]
            arn = ingestion._send_single_batch("case-1", texts)

        assert arn == "arn:success"
        assert mock_open.call_count == 3

    def test_all_retries_exhausted(self):
        config = _make_config(max_retries=2)
        ingestion = PipelineIngestion(config)
        texts = [("doc.txt", "content")]

        with patch("scripts.batch_loader.ingestion.urllib.request.urlopen") as mock_open, \
             patch("scripts.batch_loader.ingestion.time.sleep"):
            mock_open.side_effect = Exception("Always fails")
            arn = ingestion._send_single_batch("case-1", texts)

        assert arn is None
        assert mock_open.call_count == 2


# ===========================================================================
# poll_executions with mocked SFN client
# ===========================================================================

class TestPollExecutions:
    """Verify poll_executions polls until all ARNs reach terminal state."""

    def test_all_succeed_immediately(self):
        config = _make_config()
        ingestion = PipelineIngestion(config)
        arns = ["arn:exec:1", "arn:exec:2"]

        mock_sfn = MagicMock()
        mock_sfn.describe_execution.side_effect = [
            {"status": "SUCCEEDED"},
            {"status": "SUCCEEDED"},
        ]

        with patch("scripts.batch_loader.ingestion.boto3.client", return_value=mock_sfn), \
             patch("scripts.batch_loader.ingestion.time.sleep"):
            result = ingestion.poll_executions(arns)

        assert result == {"arn:exec:1": "SUCCEEDED", "arn:exec:2": "SUCCEEDED"}

    def test_mixed_terminal_states(self):
        config = _make_config()
        ingestion = PipelineIngestion(config)
        arns = ["arn:1", "arn:2", "arn:3"]

        mock_sfn = MagicMock()
        mock_sfn.describe_execution.side_effect = [
            {"status": "SUCCEEDED"},
            {"status": "FAILED"},
            {"status": "TIMED_OUT"},
        ]

        with patch("scripts.batch_loader.ingestion.boto3.client", return_value=mock_sfn), \
             patch("scripts.batch_loader.ingestion.time.sleep"):
            result = ingestion.poll_executions(arns)

        assert result["arn:1"] == "SUCCEEDED"
        assert result["arn:2"] == "FAILED"
        assert result["arn:3"] == "TIMED_OUT"

    def test_polling_with_running_then_terminal(self):
        config = _make_config(poll_initial_delay=1, poll_max_delay=4)
        ingestion = PipelineIngestion(config)
        arns = ["arn:slow"]

        mock_sfn = MagicMock()
        # First poll: RUNNING, second poll: SUCCEEDED
        mock_sfn.describe_execution.side_effect = [
            {"status": "RUNNING"},
            {"status": "SUCCEEDED"},
        ]

        with patch("scripts.batch_loader.ingestion.boto3.client", return_value=mock_sfn), \
             patch("scripts.batch_loader.ingestion.time.sleep") as mock_sleep:
            result = ingestion.poll_executions(arns)

        assert result == {"arn:slow": "SUCCEEDED"}
        # Should have slept once with initial delay
        mock_sleep.assert_called_once_with(1.0)

    def test_empty_arns(self):
        config = _make_config()
        ingestion = PipelineIngestion(config)
        result = ingestion.poll_executions([])
        assert result == {}

    def test_aborted_is_terminal(self):
        config = _make_config()
        ingestion = PipelineIngestion(config)
        arns = ["arn:aborted"]

        mock_sfn = MagicMock()
        mock_sfn.describe_execution.return_value = {"status": "ABORTED"}

        with patch("scripts.batch_loader.ingestion.boto3.client", return_value=mock_sfn), \
             patch("scripts.batch_loader.ingestion.time.sleep"):
            result = ingestion.poll_executions(arns)

        assert result == {"arn:aborted": "ABORTED"}


# ===========================================================================
# compute_backoff_delay
# ===========================================================================

class TestComputeBackoffDelay:
    """Verify exponential backoff formula: min(initial * 2^i, max)."""

    def test_iteration_zero(self):
        assert PipelineIngestion.compute_backoff_delay(0, 30, 300) == 30.0

    def test_iteration_one(self):
        assert PipelineIngestion.compute_backoff_delay(1, 30, 300) == 60.0

    def test_iteration_two(self):
        assert PipelineIngestion.compute_backoff_delay(2, 30, 300) == 120.0

    def test_iteration_three(self):
        assert PipelineIngestion.compute_backoff_delay(3, 30, 300) == 240.0

    def test_capped_at_max(self):
        # 30 * 2^4 = 480 > 300, so capped
        assert PipelineIngestion.compute_backoff_delay(4, 30, 300) == 300.0

    def test_stays_capped(self):
        assert PipelineIngestion.compute_backoff_delay(10, 30, 300) == 300.0

    def test_sequence_monotonically_nondecreasing(self):
        delays = [PipelineIngestion.compute_backoff_delay(i, 5, 100) for i in range(20)]
        for i in range(1, len(delays)):
            assert delays[i] >= delays[i - 1]

    def test_small_initial_delay(self):
        assert PipelineIngestion.compute_backoff_delay(0, 1, 10) == 1.0
        assert PipelineIngestion.compute_backoff_delay(3, 1, 10) == 8.0
        assert PipelineIngestion.compute_backoff_delay(4, 1, 10) == 10.0
