"""Unit tests for the resolve_config_handler Lambda."""

import sys
import types
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest


@pytest.fixture(autouse=True)
def _stub_lambda_imports(monkeypatch):
    """Stub out Lambda-style imports (db.connection, services.*)."""
    fake_db = types.ModuleType("db")
    fake_db_conn = types.ModuleType("db.connection")
    fake_services = types.ModuleType("services")
    fake_crs = types.ModuleType("services.config_resolution_service")

    monkeypatch.setitem(sys.modules, "db", fake_db)
    monkeypatch.setitem(sys.modules, "db.connection", fake_db_conn)
    monkeypatch.setitem(sys.modules, "services", fake_services)
    monkeypatch.setitem(sys.modules, "services.config_resolution_service", fake_crs)

    # Use plain callables (not MagicMock) to avoid InvalidSpecError
    # when ConfigResolutionService(cm) tries to use cm as a spec.
    mock_cm_instance = MagicMock()
    fake_db_conn.ConnectionManager = lambda: mock_cm_instance

    mock_service_instance = MagicMock()
    fake_crs.ConfigResolutionService = lambda cm: mock_service_instance

    yield mock_cm_instance, mock_service_instance


def test_handler_returns_effective_json(_stub_lambda_imports):
    """Handler should call resolve_effective_config and return effective_json."""
    _, mock_service = _stub_lambda_imports

    expected_config = {
        "parse": {"pdf_method": "hybrid"},
        "extract": {"llm_model_id": "anthropic.claude-3-haiku-20240307-v1:0"},
        "embed": {"embedding_model_id": "amazon.titan-embed-text-v1"},
        "graph_load": {"load_strategy": "bulk_csv", "batch_size": 500},
    }

    mock_result = MagicMock()
    mock_result.effective_json = expected_config
    mock_service.resolve_effective_config.return_value = mock_result

    from src.lambdas.ingestion.resolve_config_handler import handler

    case_id = str(uuid4())
    result = handler({"case_id": case_id}, None)

    assert result == expected_config
    mock_service.resolve_effective_config.assert_called_once_with(case_id)


def test_handler_passes_case_id_from_event(_stub_lambda_imports):
    """Handler should extract case_id from the event dict."""
    _, mock_service = _stub_lambda_imports

    mock_result = MagicMock()
    mock_result.effective_json = {"parse": {}}
    mock_service.resolve_effective_config.return_value = mock_result

    from src.lambdas.ingestion.resolve_config_handler import handler

    handler({"case_id": "test-case-123"}, None)

    mock_service.resolve_effective_config.assert_called_once_with("test-case-123")
