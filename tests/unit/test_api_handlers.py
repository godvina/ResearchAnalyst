"""Unit tests for API Lambda handler functions.

Tests cover request parsing, validation, delegation to services, and
structured response formatting for all API endpoints.
"""

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.lambdas.api.response_helper import error_response, success_response
from src.models.case_file import CaseFile, CaseFileStatus, CrossCaseGraph, SearchTier


# -----------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------

def _make_case_file(**overrides) -> CaseFile:
    defaults = dict(
        case_id="cf-001",
        topic_name="Test Topic",
        description="A test case file",
        status=CaseFileStatus.CREATED,
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        s3_prefix="cases/cf-001/",
        neptune_subgraph_label="Entity_cf-001",
        search_tier=SearchTier.STANDARD,
    )
    defaults.update(overrides)
    return CaseFile(**defaults)


def _make_cross_case_graph(**overrides) -> CrossCaseGraph:
    defaults = dict(
        graph_id="g-001",
        name="Test Graph",
        linked_case_ids=["cf-001", "cf-002"],
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        neptune_subgraph_label="CrossCase_g-001",
    )
    defaults.update(overrides)
    return CrossCaseGraph(**defaults)


def _api_event(body=None, path_params=None, query_params=None):
    """Build a minimal API Gateway proxy event."""
    event = {
        "requestContext": {"requestId": "req-123"},
        "pathParameters": path_params,
        "queryStringParameters": query_params,
    }
    if body is not None:
        event["body"] = json.dumps(body)
    return event


# -----------------------------------------------------------------------
# response_helper tests
# -----------------------------------------------------------------------

class TestResponseHelper:
    def test_success_response_includes_request_id(self):
        event = _api_event()
        resp = success_response({"data": 1}, 200, event)
        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        assert body["requestId"] == "req-123"
        assert body["data"] == 1

    def test_error_response_structure(self):
        event = _api_event()
        resp = error_response(400, "VALIDATION_ERROR", "bad input", event)
        assert resp["statusCode"] == 400
        body = json.loads(resp["body"])
        assert body["error"]["code"] == "VALIDATION_ERROR"
        assert body["error"]["message"] == "bad input"
        assert body["requestId"] == "req-123"

    def test_success_response_without_event(self):
        resp = success_response({"ok": True})
        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        assert "requestId" in body


# -----------------------------------------------------------------------
# case_files handler tests
# -----------------------------------------------------------------------

class TestCaseFilesHandlers:
    @patch("src.lambdas.api.case_files._build_case_file_service")
    def test_create_case_file_success(self, mock_build):
        from src.lambdas.api.case_files import create_case_file_handler

        svc = MagicMock()
        svc.create_case_file.return_value = _make_case_file()
        mock_build.return_value = svc

        event = _api_event(body={"topic_name": "Test", "description": "Desc"})
        resp = create_case_file_handler(event, None)

        assert resp["statusCode"] == 201
        body = json.loads(resp["body"])
        assert body["case_id"] == "cf-001"
        assert body["search_tier"] == "standard"
        svc.create_case_file.assert_called_once()

    @patch("src.lambdas.api.case_files._build_case_file_service")
    def test_create_case_file_with_search_tier(self, mock_build):
        from src.lambdas.api.case_files import create_case_file_handler

        svc = MagicMock()
        svc.create_case_file.return_value = _make_case_file(search_tier=SearchTier.ENTERPRISE)
        mock_build.return_value = svc

        event = _api_event(body={
            "topic_name": "Enterprise Case",
            "description": "Big investigation",
            "search_tier": "enterprise",
        })
        resp = create_case_file_handler(event, None)

        assert resp["statusCode"] == 201
        body = json.loads(resp["body"])
        assert body["search_tier"] == "enterprise"
        svc.create_case_file.assert_called_once_with(
            topic_name="Enterprise Case",
            description="Big investigation",
            parent_case_id=None,
            search_tier="enterprise",
        )

    @patch("src.lambdas.api.case_files._build_case_file_service")
    def test_create_case_file_invalid_search_tier(self, mock_build):
        from src.lambdas.api.case_files import create_case_file_handler

        event = _api_event(body={
            "topic_name": "Test",
            "description": "Desc",
            "search_tier": "premium",
        })
        resp = create_case_file_handler(event, None)

        assert resp["statusCode"] == 400
        body = json.loads(resp["body"])
        assert "VALIDATION_ERROR" in body["error"]["code"]
        assert "premium" in body["error"]["message"]

    @patch("src.lambdas.api.case_files._build_case_file_service")
    def test_create_case_file_defaults_to_standard_tier(self, mock_build):
        from src.lambdas.api.case_files import create_case_file_handler

        svc = MagicMock()
        svc.create_case_file.return_value = _make_case_file()
        mock_build.return_value = svc

        event = _api_event(body={"topic_name": "Test", "description": "Desc"})
        resp = create_case_file_handler(event, None)

        assert resp["statusCode"] == 201
        # Verify search_tier defaults to "standard"
        call_kwargs = svc.create_case_file.call_args
        assert call_kwargs[1]["search_tier"] == "standard"

    @patch("src.lambdas.api.case_files._build_case_file_service")
    def test_create_case_file_missing_fields(self, mock_build):
        from src.lambdas.api.case_files import create_case_file_handler

        event = _api_event(body={"topic_name": ""})
        resp = create_case_file_handler(event, None)

        assert resp["statusCode"] == 400
        body = json.loads(resp["body"])
        assert "VALIDATION_ERROR" in body["error"]["code"]

    @patch("src.lambdas.api.case_files._build_case_file_service")
    def test_list_case_files_success(self, mock_build):
        from src.lambdas.api.case_files import list_case_files_handler

        svc = MagicMock()
        svc.list_case_files.return_value = [_make_case_file()]
        mock_build.return_value = svc

        event = _api_event(query_params={"status": "created"})
        resp = list_case_files_handler(event, None)

        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        assert len(body["case_files"]) == 1
        assert body["case_files"][0]["search_tier"] == "standard"

    @patch("src.lambdas.api.case_files._build_case_file_service")
    def test_get_case_file_success(self, mock_build):
        from src.lambdas.api.case_files import get_case_file_handler

        svc = MagicMock()
        svc.get_case_file.return_value = _make_case_file()
        mock_build.return_value = svc

        event = _api_event(path_params={"id": "cf-001"})
        resp = get_case_file_handler(event, None)

        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        assert body["search_tier"] == "standard"

    @patch("src.lambdas.api.case_files._build_case_file_service")
    def test_get_case_file_includes_enterprise_tier(self, mock_build):
        from src.lambdas.api.case_files import get_case_file_handler

        svc = MagicMock()
        svc.get_case_file.return_value = _make_case_file(search_tier=SearchTier.ENTERPRISE)
        mock_build.return_value = svc

        event = _api_event(path_params={"id": "cf-001"})
        resp = get_case_file_handler(event, None)

        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        assert body["search_tier"] == "enterprise"

    @patch("src.lambdas.api.case_files._build_case_file_service")
    def test_list_case_files_includes_search_tier(self, mock_build):
        from src.lambdas.api.case_files import list_case_files_handler

        svc = MagicMock()
        svc.list_case_files.return_value = [
            _make_case_file(search_tier=SearchTier.STANDARD),
            _make_case_file(case_id="cf-002", search_tier=SearchTier.ENTERPRISE),
        ]
        mock_build.return_value = svc

        event = _api_event(query_params={})
        resp = list_case_files_handler(event, None)

        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        assert len(body["case_files"]) == 2
        assert body["case_files"][0]["search_tier"] == "standard"
        assert body["case_files"][1]["search_tier"] == "enterprise"

    @patch("src.lambdas.api.case_files._build_case_file_service")
    def test_get_case_file_not_found(self, mock_build):
        from src.lambdas.api.case_files import get_case_file_handler

        svc = MagicMock()
        svc.get_case_file.side_effect = KeyError("not found")
        mock_build.return_value = svc

        event = _api_event(path_params={"id": "missing"})
        resp = get_case_file_handler(event, None)

        assert resp["statusCode"] == 404

    @patch("src.lambdas.api.case_files._build_case_file_service")
    def test_delete_case_file_success(self, mock_build):
        from src.lambdas.api.case_files import delete_case_file_handler

        svc = MagicMock()
        mock_build.return_value = svc

        event = _api_event(path_params={"id": "cf-001"})
        resp = delete_case_file_handler(event, None)

        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        assert body["deleted"] is True

    @patch("src.lambdas.api.case_files._build_case_file_service")
    def test_archive_case_file_success(self, mock_build):
        from src.lambdas.api.case_files import archive_case_file_handler

        svc = MagicMock()
        svc.archive_case_file.return_value = _make_case_file(status=CaseFileStatus.ARCHIVED)
        mock_build.return_value = svc

        event = _api_event(path_params={"id": "cf-001"})
        resp = archive_case_file_handler(event, None)

        assert resp["statusCode"] == 200

    def test_get_case_file_missing_id(self):
        from src.lambdas.api.case_files import get_case_file_handler

        event = _api_event(path_params={})
        resp = get_case_file_handler(event, None)
        assert resp["statusCode"] == 400


# -----------------------------------------------------------------------
# ingestion handler tests
# -----------------------------------------------------------------------

class TestIngestionHandler:
    @patch("src.lambdas.api.ingestion._build_ingestion_service")
    def test_ingest_success(self, mock_build):
        from src.lambdas.api.ingestion import ingest_handler
        from src.models.document import BatchResult

        svc = MagicMock()
        svc.upload_documents.return_value = ["doc-1"]
        svc.process_batch.return_value = BatchResult(
            case_file_id="cf-001", total_documents=1, successful=1,
            failed=0, document_count=1, entity_count=5, relationship_count=3,
        )
        mock_build.return_value = svc

        event = _api_event(
            path_params={"id": "cf-001"},
            body={"files": [{"filename": "test.txt", "content_base64": "aGVsbG8="}]},
        )
        resp = ingest_handler(event, None)

        assert resp["statusCode"] == 200

    def test_ingest_missing_files(self):
        from src.lambdas.api.ingestion import ingest_handler

        event = _api_event(path_params={"id": "cf-001"}, body={"files": []})
        resp = ingest_handler(event, None)
        assert resp["statusCode"] == 400

    def test_ingest_missing_case_id(self):
        from src.lambdas.api.ingestion import ingest_handler

        event = _api_event(path_params={})
        resp = ingest_handler(event, None)
        assert resp["statusCode"] == 400


# -----------------------------------------------------------------------
# patterns handler tests
# -----------------------------------------------------------------------

class TestPatternsHandlers:
    @patch("src.lambdas.api.patterns._build_pattern_service")
    def test_discover_patterns_success(self, mock_build):
        from src.lambdas.api.patterns import discover_patterns_handler
        from src.models.pattern import PatternReport

        svc = MagicMock()
        svc.generate_pattern_report.return_value = PatternReport(
            report_id="r-001", case_file_id="cf-001",
        )
        mock_build.return_value = svc

        event = _api_event(path_params={"id": "cf-001"})
        resp = discover_patterns_handler(event, None)

        assert resp["statusCode"] == 200

    def test_discover_patterns_missing_id(self):
        from src.lambdas.api.patterns import discover_patterns_handler

        event = _api_event(path_params={})
        resp = discover_patterns_handler(event, None)
        assert resp["statusCode"] == 400


# -----------------------------------------------------------------------
# search handler tests
# -----------------------------------------------------------------------

class TestSearchHandler:
    @patch("src.lambdas.api.search._build_search_service")
    @patch("src.lambdas.api.search._build_case_file_service")
    @patch("src.lambdas.api.search._build_backend_factory")
    def test_search_success(self, mock_build_factory, mock_build_cf, mock_build):
        from src.lambdas.api.search import search_handler
        from src.models.search import SearchResult
        from src.models.case_file import SearchTier

        svc = MagicMock()
        svc.search.return_value = [
            SearchResult(
                document_id="doc-1", passage="found it",
                relevance_score=0.9, source_document_ref="s3://...",
            ),
        ]
        mock_build.return_value = svc

        cf_svc = MagicMock()
        cf_svc.get_case_file.return_value = _make_case_file(search_tier=SearchTier.STANDARD)
        mock_build_cf.return_value = cf_svc

        backend = MagicMock()
        backend.supported_modes = ["semantic"]
        factory = MagicMock()
        factory.get_backend.return_value = backend
        mock_build_factory.return_value = factory

        event = _api_event(
            path_params={"id": "cf-001"},
            body={"query": "ancient aliens"},
        )
        resp = search_handler(event, None)

        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        assert len(body["results"]) == 1
        assert body["search_tier"] == "standard"
        assert body["available_modes"] == ["semantic"]

    @patch("src.lambdas.api.search._build_search_service")
    @patch("src.lambdas.api.search._build_case_file_service")
    @patch("src.lambdas.api.search._build_backend_factory")
    def test_search_with_mode_and_filters(self, mock_build_factory, mock_build_cf, mock_build):
        from src.lambdas.api.search import search_handler
        from src.models.case_file import SearchTier

        svc = MagicMock()
        svc.search.return_value = []
        mock_build.return_value = svc

        cf_svc = MagicMock()
        cf_svc.get_case_file.return_value = _make_case_file(search_tier=SearchTier.ENTERPRISE)
        mock_build_cf.return_value = cf_svc

        backend = MagicMock()
        backend.supported_modes = ["semantic", "keyword", "hybrid"]
        factory = MagicMock()
        factory.get_backend.return_value = backend
        mock_build_factory.return_value = factory

        event = _api_event(
            path_params={"id": "cf-001"},
            body={
                "query": "test",
                "search_mode": "hybrid",
                "filters": {"person": "John", "document_type": "report"},
            },
        )
        resp = search_handler(event, None)

        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        assert body["search_tier"] == "enterprise"
        assert body["available_modes"] == ["semantic", "keyword", "hybrid"]

        # Verify search was called with mode and filters
        call_kwargs = svc.search.call_args
        assert call_kwargs[1]["mode"] == "hybrid"
        assert call_kwargs[1]["filters"] is not None

    @patch("src.lambdas.api.search._build_search_service")
    @patch("src.lambdas.api.search._build_case_file_service")
    @patch("src.lambdas.api.search._build_backend_factory")
    def test_search_unsupported_mode_returns_400(self, mock_build_factory, mock_build_cf, mock_build):
        from src.lambdas.api.search import search_handler
        from src.models.case_file import SearchTier

        svc = MagicMock()
        svc.search.side_effect = ValueError("Search mode 'keyword' is not available for standard tier")
        mock_build.return_value = svc

        cf_svc = MagicMock()
        cf_svc.get_case_file.return_value = _make_case_file(search_tier=SearchTier.STANDARD)
        mock_build_cf.return_value = cf_svc

        backend = MagicMock()
        backend.supported_modes = ["semantic"]
        factory = MagicMock()
        factory.get_backend.return_value = backend
        mock_build_factory.return_value = factory

        event = _api_event(
            path_params={"id": "cf-001"},
            body={"query": "test", "search_mode": "keyword"},
        )
        resp = search_handler(event, None)

        assert resp["statusCode"] == 400
        body = json.loads(resp["body"])
        assert body["error"]["code"] == "UNSUPPORTED_MODE"

    def test_search_missing_query(self):
        from src.lambdas.api.search import search_handler

        event = _api_event(path_params={"id": "cf-001"}, body={})
        resp = search_handler(event, None)
        assert resp["statusCode"] == 400


# -----------------------------------------------------------------------
# drill_down handler tests
# -----------------------------------------------------------------------

class TestDrillDownHandler:
    @patch("src.lambdas.api.drill_down._build_case_file_service")
    def test_drill_down_success(self, mock_build):
        from src.lambdas.api.drill_down import drill_down_handler

        svc = MagicMock()
        svc.create_sub_case_file.return_value = _make_case_file(
            case_id="sub-001", parent_case_id="cf-001",
        )
        mock_build.return_value = svc

        event = _api_event(
            path_params={"id": "cf-001"},
            body={"topic_name": "Sub topic", "description": "Drill down"},
        )
        resp = drill_down_handler(event, None)

        assert resp["statusCode"] == 201

    def test_drill_down_missing_fields(self):
        from src.lambdas.api.drill_down import drill_down_handler

        event = _api_event(path_params={"id": "cf-001"}, body={"topic_name": ""})
        resp = drill_down_handler(event, None)
        assert resp["statusCode"] == 400


# -----------------------------------------------------------------------
# cross_case handler tests
# -----------------------------------------------------------------------

class TestCrossCaseHandlers:
    @patch("src.lambdas.api.cross_case._build_services")
    def test_analyze_success(self, mock_build):
        from src.lambdas.api.cross_case import analyze_handler
        from src.models.pattern import CrossReferenceReport

        cross_svc = MagicMock()
        cross_svc.generate_cross_reference_report.return_value = CrossReferenceReport(
            report_id="r-001", case_ids=["cf-001", "cf-002"],
        )
        mock_build.return_value = (cross_svc, MagicMock())

        event = _api_event(body={"case_ids": ["cf-001", "cf-002"]})
        resp = analyze_handler(event, None)

        assert resp["statusCode"] == 200

    def test_analyze_too_few_cases(self):
        from src.lambdas.api.cross_case import analyze_handler

        event = _api_event(body={"case_ids": ["cf-001"]})
        resp = analyze_handler(event, None)
        assert resp["statusCode"] == 400

    @patch("src.lambdas.api.cross_case._build_services")
    def test_create_graph_success(self, mock_build):
        from src.lambdas.api.cross_case import create_graph_handler

        cf_svc = MagicMock()
        cf_svc.create_cross_case_graph.return_value = _make_cross_case_graph()
        mock_build.return_value = (MagicMock(), cf_svc)

        event = _api_event(body={"name": "My Graph", "case_ids": ["cf-001", "cf-002"]})
        resp = create_graph_handler(event, None)

        assert resp["statusCode"] == 201

    def test_create_graph_missing_name(self):
        from src.lambdas.api.cross_case import create_graph_handler

        event = _api_event(body={"case_ids": ["cf-001", "cf-002"]})
        resp = create_graph_handler(event, None)
        assert resp["statusCode"] == 400

    @patch("src.lambdas.api.cross_case._build_services")
    def test_update_graph_success(self, mock_build):
        from src.lambdas.api.cross_case import update_graph_handler

        cf_svc = MagicMock()
        cf_svc.update_cross_case_graph.return_value = _make_cross_case_graph()
        mock_build.return_value = (MagicMock(), cf_svc)

        event = _api_event(
            path_params={"id": "g-001"},
            body={"add_case_ids": ["cf-003"]},
        )
        resp = update_graph_handler(event, None)

        assert resp["statusCode"] == 200

    def test_update_graph_missing_id(self):
        from src.lambdas.api.cross_case import update_graph_handler

        event = _api_event(path_params={}, body={"add_case_ids": ["cf-003"]})
        resp = update_graph_handler(event, None)
        assert resp["statusCode"] == 400

    @patch("src.lambdas.api.cross_case._build_services")
    def test_get_graph_success(self, mock_build):
        from src.lambdas.api.cross_case import get_graph_handler

        cf_svc = MagicMock()
        cf_svc.get_cross_case_graph.return_value = _make_cross_case_graph()
        mock_build.return_value = (MagicMock(), cf_svc)

        event = _api_event(path_params={"id": "g-001"})
        resp = get_graph_handler(event, None)

        assert resp["statusCode"] == 200

    @patch("src.lambdas.api.cross_case._build_services")
    def test_get_graph_not_found(self, mock_build):
        from src.lambdas.api.cross_case import get_graph_handler

        cf_svc = MagicMock()
        cf_svc.get_cross_case_graph.side_effect = KeyError("not found")
        mock_build.return_value = (MagicMock(), cf_svc)

        event = _api_event(path_params={"id": "missing"})
        resp = get_graph_handler(event, None)

        assert resp["statusCode"] == 404
