"""Unit tests for batch_loader_handler dispatch and sync endpoints."""

import json
from unittest.mock import MagicMock, patch

import pytest

from src.lambdas.api.batch_loader_handler import (
    dispatch_handler,
    handle_discover,
    handle_quarantine,
    handle_start,
    handle_status,
)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _api_event(method, resource, query_params=None, body=None, path_params=None):
    """Build a minimal API Gateway proxy event."""
    event = {
        "httpMethod": method,
        "resource": resource,
        "queryStringParameters": query_params,
        "pathParameters": path_params,
        "body": json.dumps(body) if body else None,
        "requestContext": {"requestId": "test-req-id"},
    }
    return event


def _parse_body(response):
    """Parse the JSON body from a Lambda proxy response."""
    return json.loads(response["body"])


class FakeContext:
    function_name = "test-batch-loader-fn"


CTX = FakeContext()


# ------------------------------------------------------------------
# Dispatch routing tests
# ------------------------------------------------------------------

class TestDispatchRouting:
    """Test that dispatch_handler routes to the correct handler."""

    def test_options_returns_cors(self):
        event = _api_event("OPTIONS", "/batch-loader/discover")
        resp = dispatch_handler(event, CTX)
        assert resp["statusCode"] == 200
        assert "Access-Control-Allow-Origin" in resp["headers"]
        assert resp["headers"]["Access-Control-Allow-Origin"] == "*"

    def test_unknown_route_returns_404(self):
        event = _api_event("GET", "/batch-loader/unknown")
        resp = dispatch_handler(event, CTX)
        assert resp["statusCode"] == 404
        body = _parse_body(resp)
        assert body["error"]["code"] == "NOT_FOUND"

    def test_wrong_method_returns_404(self):
        event = _api_event("DELETE", "/batch-loader/discover")
        resp = dispatch_handler(event, CTX)
        assert resp["statusCode"] == 404

    @patch("src.lambdas.api.batch_loader_handler.handle_discover")
    def test_routes_get_discover(self, mock_handler):
        mock_handler.return_value = {"statusCode": 200, "body": "{}"}
        event = _api_event("GET", "/batch-loader/discover")
        dispatch_handler(event, CTX)
        mock_handler.assert_called_once_with(event, CTX)

    @patch("src.lambdas.api.batch_loader_handler.handle_start")
    def test_routes_post_start(self, mock_handler):
        mock_handler.return_value = {"statusCode": 202, "body": "{}"}
        event = _api_event("POST", "/batch-loader/start")
        dispatch_handler(event, CTX)
        mock_handler.assert_called_once_with(event, CTX)

    @patch("src.lambdas.api.batch_loader_handler.handle_status")
    def test_routes_get_status(self, mock_handler):
        mock_handler.return_value = {"statusCode": 200, "body": "{}"}
        event = _api_event("GET", "/batch-loader/status")
        dispatch_handler(event, CTX)
        mock_handler.assert_called_once_with(event, CTX)

    @patch("src.lambdas.api.batch_loader_handler.handle_list_manifests")
    def test_routes_get_manifests(self, mock_handler):
        mock_handler.return_value = {"statusCode": 200, "body": "{}"}
        event = _api_event("GET", "/batch-loader/manifests")
        dispatch_handler(event, CTX)
        mock_handler.assert_called_once_with(event, CTX)

    @patch("src.lambdas.api.batch_loader_handler.handle_get_manifest")
    def test_routes_get_manifest_by_id(self, mock_handler):
        mock_handler.return_value = {"statusCode": 200, "body": "{}"}
        event = _api_event("GET", "/batch-loader/manifests/{batch_id}")
        dispatch_handler(event, CTX)
        mock_handler.assert_called_once_with(event, CTX)

    @patch("src.lambdas.api.batch_loader_handler.handle_quarantine")
    def test_routes_get_quarantine(self, mock_handler):
        mock_handler.return_value = {"statusCode": 200, "body": "{}"}
        event = _api_event("GET", "/batch-loader/quarantine")
        dispatch_handler(event, CTX)
        mock_handler.assert_called_once_with(event, CTX)

    @patch("src.lambdas.api.batch_loader_handler.handle_history")
    def test_routes_get_history(self, mock_handler):
        mock_handler.return_value = {"statusCode": 200, "body": "{}"}
        event = _api_event("GET", "/batch-loader/history")
        dispatch_handler(event, CTX)
        mock_handler.assert_called_once_with(event, CTX)

    @patch("src.lambdas.api.batch_loader_handler.async_process_batch")
    def test_routes_process_batch_action(self, mock_handler):
        mock_handler.return_value = {"statusCode": 200, "body": "ok"}
        event = {"action": "process_batch", "case_id": "test-case"}
        dispatch_handler(event, CTX)
        mock_handler.assert_called_once_with(event, CTX)


# ------------------------------------------------------------------
# handle_discover tests
# ------------------------------------------------------------------

class TestHandleDiscover:
    """Test the discovery endpoint."""

    def test_discover_missing_case_id_returns_400(self):
        event = _api_event("GET", "/batch-loader/discover", query_params={})
        resp = handle_discover(event, CTX)
        assert resp["statusCode"] == 400
        body = _parse_body(resp)
        assert body["error"]["code"] == "VALIDATION_ERROR"

    @patch("src.lambdas.api.batch_loader_handler.boto3")
    def test_discover_with_case_id(self, mock_boto3):
        """Discover with valid case_id calls discovery modules."""
        mock_s3 = MagicMock()
        mock_boto3.client.return_value = mock_s3

        # Mock the paginator for discovery
        mock_paginator = MagicMock()
        mock_s3.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [
            {"Contents": [{"Key": "pdfs/doc1.pdf"}, {"Key": "pdfs/doc2.pdf"}]}
        ]

        event = _api_event("GET", "/batch-loader/discover", query_params={
            "case_id": "test-case-id",
            "batch_size": "100",
        })

        with patch("scripts.batch_loader.discovery.BatchDiscovery.load_processed_keys", return_value=set()):
            with patch("scripts.batch_loader.cost_estimator.CostEstimator._load_pricing", return_value={"textract": {"per_1000_pages": 1.50}}):
                resp = handle_discover(event, CTX)

        assert resp["statusCode"] == 200
        body = _parse_body(resp)
        assert "total_unprocessed_count" in body
        assert "requested_batch_size" in body
        assert "actual_batch_size" in body
        assert "source_prefix_breakdown" in body


# ------------------------------------------------------------------
# handle_start tests
# ------------------------------------------------------------------

class TestHandleStart:
    """Test the start batch endpoint."""

    @patch("src.lambdas.api.batch_loader_handler.boto3")
    def test_start_returns_202_for_valid_request(self, mock_boto3):
        mock_s3 = MagicMock()
        mock_lambda = MagicMock()

        def client_factory(service, **kwargs):
            if service == "s3":
                return mock_s3
            if service == "lambda":
                return mock_lambda
            return MagicMock()

        mock_boto3.client.side_effect = client_factory

        # Mock state: no batch in progress, no manifests
        from botocore.exceptions import ClientError
        mock_s3.get_object.side_effect = ClientError(
            {"Error": {"Code": "NoSuchKey"}}, "GetObject"
        )
        mock_s3.get_paginator.return_value.paginate.return_value = [{"Contents": []}]

        event = _api_event("POST", "/batch-loader/start", body={
            "case_id": "test-case-id",
            "batch_size": 100,
            "sub_batch_size": 10,
            "source_prefixes": ["pdfs/"],
        })

        resp = handle_start(event, CTX)
        assert resp["statusCode"] == 202
        body = _parse_body(resp)
        assert "batch_id" in body
        assert body["status"] == "discovery"

    @patch("src.lambdas.api.batch_loader_handler.boto3")
    def test_start_returns_409_when_batch_running(self, mock_boto3):
        mock_s3 = MagicMock()
        mock_boto3.client.return_value = mock_s3

        # Mock state: batch in progress
        progress_data = json.dumps({
            "batch_id": "batch_001",
            "status": "extracting",
        }).encode()
        mock_body = MagicMock()
        mock_body.read.return_value = progress_data
        mock_s3.get_object.return_value = {"Body": mock_body}

        event = _api_event("POST", "/batch-loader/start", body={
            "case_id": "test-case-id",
            "batch_size": 100,
            "sub_batch_size": 10,
            "source_prefixes": ["pdfs/"],
        })

        resp = handle_start(event, CTX)
        assert resp["statusCode"] == 409
        body = _parse_body(resp)
        assert body["error"]["code"] == "BATCH_IN_PROGRESS"

    def test_start_missing_case_id_returns_400(self):
        event = _api_event("POST", "/batch-loader/start", body={})
        resp = handle_start(event, CTX)
        assert resp["statusCode"] == 400

    def test_start_invalid_batch_size_returns_400(self):
        event = _api_event("POST", "/batch-loader/start", body={
            "case_id": "test",
            "batch_size": -1,
            "source_prefixes": ["pdfs/"],
        })
        resp = handle_start(event, CTX)
        assert resp["statusCode"] == 400

    def test_start_empty_prefixes_returns_400(self):
        event = _api_event("POST", "/batch-loader/start", body={
            "case_id": "test",
            "batch_size": 100,
            "source_prefixes": [],
        })
        resp = handle_start(event, CTX)
        assert resp["statusCode"] == 400

    def test_start_sub_batch_size_out_of_range_returns_400(self):
        event = _api_event("POST", "/batch-loader/start", body={
            "case_id": "test",
            "batch_size": 100,
            "sub_batch_size": 300,
            "source_prefixes": ["pdfs/"],
        })
        resp = handle_start(event, CTX)
        assert resp["statusCode"] == 400


# ------------------------------------------------------------------
# handle_status tests
# ------------------------------------------------------------------

class TestHandleStatus:
    """Test the status endpoint."""

    @patch("src.lambdas.api.batch_loader_handler._build_state")
    def test_status_returns_progress(self, mock_build_state):
        mock_state = MagicMock()
        mock_build_state.return_value = mock_state
        mock_state.read_progress.return_value = {
            "batch_id": "batch_001",
            "status": "extracting",
            "started_at": "2026-01-01T00:00:00+00:00",
        }

        event = _api_event("GET", "/batch-loader/status", query_params={"case_id": "test"})
        resp = handle_status(event, CTX)
        assert resp["statusCode"] == 200
        body = _parse_body(resp)
        assert body["batch_id"] == "batch_001"
        assert "elapsed_time_seconds" in body

    @patch("src.lambdas.api.batch_loader_handler._build_state")
    def test_status_returns_404_when_no_progress(self, mock_build_state):
        mock_state = MagicMock()
        mock_build_state.return_value = mock_state
        mock_state.read_progress.return_value = None

        event = _api_event("GET", "/batch-loader/status", query_params={"case_id": "test"})
        resp = handle_status(event, CTX)
        assert resp["statusCode"] == 404

    def test_status_missing_case_id_returns_400(self):
        event = _api_event("GET", "/batch-loader/status", query_params={})
        resp = handle_status(event, CTX)
        assert resp["statusCode"] == 400


# ------------------------------------------------------------------
# handle_quarantine tests
# ------------------------------------------------------------------

class TestHandleQuarantine:
    """Test the quarantine endpoint."""

    @patch("src.lambdas.api.batch_loader_handler._build_state")
    def test_quarantine_computes_summary(self, mock_build_state):
        mock_state = MagicMock()
        mock_build_state.return_value = mock_state
        mock_state.read_quarantine.return_value = [
            {"s3_key": "pdfs/a.pdf", "reason": "extraction_failed: PyPDF2 error", "failed_at": "2026-01-01T00:00:00Z", "retry_count": 3, "batch_number": 1},
            {"s3_key": "pdfs/b.pdf", "reason": "timeout during processing", "failed_at": "2026-01-02T00:00:00Z", "retry_count": 3, "batch_number": 1},
            {"s3_key": "pdfs/c.pdf", "reason": "pipeline error", "failed_at": "2026-01-03T00:00:00Z", "retry_count": 3, "batch_number": 2},
        ]

        event = _api_event("GET", "/batch-loader/quarantine", query_params={"case_id": "test"})
        resp = handle_quarantine(event, CTX)
        assert resp["statusCode"] == 200
        body = _parse_body(resp)

        assert body["summary"]["total_quarantined"] == 3
        assert body["summary"]["by_reason"]["extraction_failed"] == 1
        assert body["summary"]["by_reason"]["timeout"] == 1
        assert body["summary"]["by_reason"]["pipeline_failed"] == 1
        assert body["summary"]["most_recent"] == "2026-01-03T00:00:00Z"

    @patch("src.lambdas.api.batch_loader_handler._build_state")
    def test_quarantine_empty_list(self, mock_build_state):
        mock_state = MagicMock()
        mock_build_state.return_value = mock_state
        mock_state.read_quarantine.return_value = []

        event = _api_event("GET", "/batch-loader/quarantine", query_params={"case_id": "test"})
        resp = handle_quarantine(event, CTX)
        assert resp["statusCode"] == 200
        body = _parse_body(resp)
        assert body["summary"]["total_quarantined"] == 0
        assert body["summary"]["most_recent"] is None
