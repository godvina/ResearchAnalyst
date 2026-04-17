"""Unit tests for the frontend API client."""

import json
from unittest.mock import patch, MagicMock

import pytest

from src.frontend.api_client import (
    _url,
    _handle,
    APIError,
    create_case_file,
    list_case_files,
    get_case_file,
    delete_case_file,
    archive_case_file,
    ingest_documents,
    discover_patterns,
    get_patterns,
    search,
    drill_down,
    analyze_cross_case,
    create_cross_case_graph,
    update_cross_case_graph,
    get_cross_case_graph,
)


def _mock_response(status_code=200, body=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.ok = 200 <= status_code < 300
    resp.json.return_value = body or {}
    resp.text = json.dumps(body or {})
    return resp


class TestUrlBuilder:
    def test_url(self):
        assert _url("/case-files").endswith("/case-files")


class TestHandleResponse:
    def test_success(self):
        resp = _mock_response(200, {"case_id": "abc"})
        assert _handle(resp) == {"case_id": "abc"}

    def test_error_raises(self):
        resp = _mock_response(400, {"error": {"message": "bad request"}, "requestId": "r1"})
        with pytest.raises(APIError) as exc_info:
            _handle(resp)
        assert exc_info.value.status_code == 400
        assert "bad request" in exc_info.value.detail


class TestCaseFileEndpoints:
    @patch("src.frontend.api_client.requests.post")
    def test_create_case_file(self, mock_post):
        mock_post.return_value = _mock_response(201, {"case_id": "123"})
        result = create_case_file("Topic", "Desc")
        assert result["case_id"] == "123"
        mock_post.assert_called_once()

    @patch("src.frontend.api_client.requests.get")
    def test_list_case_files(self, mock_get):
        mock_get.return_value = _mock_response(200, {"case_files": []})
        result = list_case_files(status="created")
        assert result["case_files"] == []

    @patch("src.frontend.api_client.requests.get")
    def test_get_case_file(self, mock_get):
        mock_get.return_value = _mock_response(200, {"case_id": "abc"})
        assert get_case_file("abc")["case_id"] == "abc"

    @patch("src.frontend.api_client.requests.delete")
    def test_delete_case_file(self, mock_del):
        mock_del.return_value = _mock_response(200, {"deleted": True})
        assert delete_case_file("abc")["deleted"] is True

    @patch("src.frontend.api_client.requests.post")
    def test_archive_case_file(self, mock_post):
        mock_post.return_value = _mock_response(200, {"status": "archived"})
        assert archive_case_file("abc")["status"] == "archived"


class TestIngestionEndpoint:
    @patch("src.frontend.api_client.requests.post")
    def test_ingest(self, mock_post):
        mock_post.return_value = _mock_response(200, {"successful": 2, "failed": 0})
        result = ingest_documents("abc", [{"filename": "f.txt", "content_base64": "dGVzdA=="}])
        assert result["successful"] == 2


class TestPatternEndpoints:
    @patch("src.frontend.api_client.requests.post")
    def test_discover(self, mock_post):
        mock_post.return_value = _mock_response(200, {"report_id": "r1"})
        assert discover_patterns("abc")["report_id"] == "r1"

    @patch("src.frontend.api_client.requests.get")
    def test_get_patterns(self, mock_get):
        mock_get.return_value = _mock_response(200, {"reports": []})
        assert get_patterns("abc")["reports"] == []


class TestSearchEndpoint:
    @patch("src.frontend.api_client.requests.post")
    def test_search(self, mock_post):
        mock_post.return_value = _mock_response(200, {"results": [{"passage": "text"}]})
        result = search("abc", "query")
        assert len(result["results"]) == 1


class TestDrillDownEndpoint:
    @patch("src.frontend.api_client.requests.post")
    def test_drill_down(self, mock_post):
        mock_post.return_value = _mock_response(201, {"case_id": "sub1"})
        result = drill_down("abc", "Sub topic", "Desc", entity_names=["Giza"])
        assert result["case_id"] == "sub1"


class TestCrossCaseEndpoints:
    @patch("src.frontend.api_client.requests.post")
    def test_analyze(self, mock_post):
        mock_post.return_value = _mock_response(200, {"report_id": "cr1"})
        assert analyze_cross_case(["a", "b"])["report_id"] == "cr1"

    @patch("src.frontend.api_client.requests.post")
    def test_create_graph(self, mock_post):
        mock_post.return_value = _mock_response(201, {"graph_id": "g1"})
        assert create_cross_case_graph("G", ["a", "b"])["graph_id"] == "g1"

    @patch("src.frontend.api_client.requests.patch")
    def test_update_graph(self, mock_patch):
        mock_patch.return_value = _mock_response(200, {"graph_id": "g1"})
        assert update_cross_case_graph("g1", add_case_ids=["c"])["graph_id"] == "g1"

    @patch("src.frontend.api_client.requests.get")
    def test_get_graph(self, mock_get):
        mock_get.return_value = _mock_response(200, {"graph_id": "g1"})
        assert get_cross_case_graph("g1")["graph_id"] == "g1"
