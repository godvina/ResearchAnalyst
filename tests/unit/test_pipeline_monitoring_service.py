"""Unit tests for PipelineMonitoringService."""

import json
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest

from src.models.pipeline_config import (
    PipelineRunMetrics,
    PipelineRunSummary,
    PipelineStatus,
    StepDetail,
)
from src.services.pipeline_monitoring_service import (
    BEDROCK_PRICING,
    PipelineMonitoringService,
    estimate_bedrock_cost,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

CASE_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
RUN_ID = "11111111-2222-3333-4444-555555555555"
NOW = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
LATER = NOW + timedelta(minutes=5)


@pytest.fixture()
def mock_cursor():
    return MagicMock()


@pytest.fixture()
def mock_db(mock_cursor):
    db = MagicMock()

    @contextmanager
    def _cursor_ctx():
        yield mock_cursor

    db.cursor = _cursor_ctx
    return db


@pytest.fixture()
def service(mock_db):
    return PipelineMonitoringService(mock_db)


# ---------------------------------------------------------------------------
# estimate_bedrock_cost tests
# ---------------------------------------------------------------------------


class TestEstimateBedrockCost:
    def test_sonnet_cost(self):
        cost = estimate_bedrock_cost(
            "anthropic.claude-3-sonnet-20240229-v1:0", 1_000_000, 1_000_000
        )
        assert cost == pytest.approx(3.0 + 15.0)

    def test_haiku_cost(self):
        cost = estimate_bedrock_cost(
            "anthropic.claude-3-haiku-20240307-v1:0", 1_000_000, 1_000_000
        )
        assert cost == pytest.approx(0.25 + 1.25)

    def test_titan_embed_cost(self):
        cost = estimate_bedrock_cost(
            "amazon.titan-embed-text-v1", 1_000_000, 0
        )
        assert cost == pytest.approx(0.1)

    def test_unknown_model_uses_default_rates(self):
        cost = estimate_bedrock_cost("unknown-model", 1_000_000, 1_000_000)
        # Falls back to Sonnet rates
        assert cost == pytest.approx(3.0 + 15.0)

    def test_zero_tokens(self):
        cost = estimate_bedrock_cost(
            "anthropic.claude-3-sonnet-20240229-v1:0", 0, 0
        )
        assert cost == 0.0

    def test_deterministic(self):
        args = ("anthropic.claude-3-haiku-20240307-v1:0", 5000, 2000)
        assert estimate_bedrock_cost(*args) == estimate_bedrock_cost(*args)


# ---------------------------------------------------------------------------
# get_pipeline_status tests
# ---------------------------------------------------------------------------


class TestGetPipelineStatus:
    def test_returns_idle_when_no_runs(self, service, mock_cursor):
        mock_cursor.fetchone.return_value = None
        result = service.get_pipeline_status(CASE_ID)
        assert isinstance(result, PipelineStatus)
        assert result.status == "idle"
        assert result.case_id == UUID(CASE_ID)

    def test_returns_running_status(self, service, mock_cursor):
        step_statuses = {"parse": "completed", "extract": "running"}
        mock_cursor.fetchone.side_effect = [
            # First call: pipeline_runs row
            (RUN_ID, "running", 10, step_statuses, NOW, None),
            # Second call: docs processed count
            (3,),
        ]
        result = service.get_pipeline_status(CASE_ID)
        assert result.status == "running"
        assert result.current_step == "extract"
        assert result.docs_processed == 3
        assert result.docs_remaining == 7
        assert result.elapsed_seconds is not None

    def test_returns_completed_status(self, service, mock_cursor):
        step_statuses = {
            "parse": "completed",
            "extract": "completed",
            "embed": "completed",
            "graph_load": "completed",
            "store_artifact": "completed",
        }
        mock_cursor.fetchone.side_effect = [
            (RUN_ID, "completed", 5, step_statuses, NOW, LATER),
            (5,),
        ]
        result = service.get_pipeline_status(CASE_ID)
        assert result.status == "completed"
        assert result.docs_processed == 5
        assert result.docs_remaining == 0
        assert result.elapsed_seconds == pytest.approx(300.0)

    def test_handles_json_string_step_statuses(self, service, mock_cursor):
        step_statuses_json = json.dumps({"parse": "completed", "extract": "running"})
        mock_cursor.fetchone.side_effect = [
            (RUN_ID, "running", 10, step_statuses_json, NOW, None),
            (2,),
        ]
        result = service.get_pipeline_status(CASE_ID)
        assert result.current_step == "extract"
        assert result.step_statuses == {"parse": "completed", "extract": "running"}


# ---------------------------------------------------------------------------
# get_run_metrics tests
# ---------------------------------------------------------------------------


class TestGetRunMetrics:
    def test_returns_metrics_from_stored_values(self, service, mock_cursor):
        mock_cursor.fetchone.return_value = (
            RUN_ID,       # run_id
            150,          # total_entities
            75,           # total_relationships
            {"person": 80, "organization": 70},  # entity_type_counts
            0.85,         # avg_confidence
            0.05,         # noise_ratio
            12.5,         # docs_per_minute
            3.0,          # avg_entities_per_doc
            2,            # failed_doc_count
            0.04,         # failure_rate
            0.054,        # estimated_cost_usd
            10000,        # total_input_tokens
            2000,         # total_output_tokens
            82.5,         # quality_score
            {"confidence_avg": 85.0},  # quality_breakdown
            50,           # document_count
            NOW,          # started_at
            LATER,        # completed_at
            {},           # effective_config
        )
        result = service.get_run_metrics(RUN_ID)
        assert isinstance(result, PipelineRunMetrics)
        assert result.total_entities == 150
        assert result.total_relationships == 75
        assert result.avg_confidence == 0.85
        assert result.failed_doc_count == 2
        assert result.estimated_cost_usd == 0.054
        assert result.quality_score == 82.5

    def test_raises_when_run_not_found(self, service, mock_cursor):
        mock_cursor.fetchone.return_value = None
        with pytest.raises(ValueError, match="not found"):
            service.get_run_metrics(RUN_ID)

    def test_computes_cost_from_tokens_when_not_stored(self, service, mock_cursor):
        effective_config = {
            "extract": {"llm_model_id": "anthropic.claude-3-haiku-20240307-v1:0"}
        }
        mock_cursor.fetchone.return_value = (
            RUN_ID, None, None, None, None, None,
            None,   # docs_per_minute
            None, 0, None,
            None,   # estimated_cost_usd (not stored)
            1_000_000,  # total_input_tokens
            500_000,    # total_output_tokens
            None, None,
            50, NOW, LATER,
            effective_config,
        )
        result = service.get_run_metrics(RUN_ID)
        expected_cost = estimate_bedrock_cost(
            "anthropic.claude-3-haiku-20240307-v1:0", 1_000_000, 500_000
        )
        assert result.estimated_cost_usd == pytest.approx(round(expected_cost, 6))

    def test_computes_docs_per_minute_when_not_stored(self, service, mock_cursor):
        mock_cursor.fetchone.return_value = (
            RUN_ID, None, None, None, None, None,
            None,   # docs_per_minute not stored
            None, 0, None, None, None, None, None, None,
            100,    # document_count
            NOW,    # started_at
            NOW + timedelta(minutes=10),  # completed_at
            {},
        )
        result = service.get_run_metrics(RUN_ID)
        assert result.docs_per_minute == pytest.approx(10.0)


# ---------------------------------------------------------------------------
# list_runs tests
# ---------------------------------------------------------------------------


class TestListRuns:
    def test_returns_run_summaries(self, service, mock_cursor):
        run_id_1 = uuid4()
        run_id_2 = uuid4()
        mock_cursor.fetchall.return_value = [
            (run_id_1, UUID(CASE_ID), 3, False, 50, "completed", NOW, LATER, 85.0),
            (run_id_2, UUID(CASE_ID), 2, True, 10, "running", NOW, None, None),
        ]
        result = service.list_runs(CASE_ID)
        assert len(result) == 2
        assert all(isinstance(r, PipelineRunSummary) for r in result)
        assert result[0].run_id == run_id_1
        assert result[0].quality_score == 85.0
        assert result[1].is_sample_run is True

    def test_returns_empty_list(self, service, mock_cursor):
        mock_cursor.fetchall.return_value = []
        result = service.list_runs(CASE_ID)
        assert result == []

    def test_respects_limit(self, service, mock_cursor):
        mock_cursor.fetchall.return_value = []
        service.list_runs(CASE_ID, limit=5)
        call_args = mock_cursor.execute.call_args
        assert call_args[0][1] == (CASE_ID, 5)


# ---------------------------------------------------------------------------
# get_step_details tests
# ---------------------------------------------------------------------------


class TestGetStepDetails:
    def test_returns_parse_step_details(self, service, mock_cursor):
        step_rows = [
            ("completed", 120, {"ocr_used": True, "tables_extracted": 2}, None, "doc1", NOW, LATER),
            ("completed", 80, {"ocr_used": False, "tables_extracted": 0}, None, "doc2", NOW, LATER),
            ("failed", None, {}, "Parse error", "doc3", NOW, None),
        ]
        effective_config = {"parse": {"pdf_method": "text", "ocr_enabled": False}}
        mock_cursor.fetchone.side_effect = [
            (json.dumps(effective_config),),  # _get_step_config
        ]
        mock_cursor.fetchall.side_effect = [
            step_rows,   # step results
            [],           # recent runs
            [("doc3", "Parse error", NOW)],  # recent errors
        ]
        result = service.get_step_details(RUN_ID, "parse")
        assert isinstance(result, StepDetail)
        assert result.step_name == "parse"
        assert result.service_status == "Active"
        assert result.item_count == 3
        assert result.metrics["ocr_usage_count"] == 1
        assert result.metrics["table_extraction_count"] == 1
        assert result.metrics["completed"] == 2
        assert result.metrics["failed"] == 1
        assert len(result.recent_errors) == 1

    def test_returns_extract_step_details(self, service, mock_cursor):
        step_rows = [
            (
                "completed", 500,
                {
                    "entity_count": 25,
                    "input_tokens": 5000,
                    "output_tokens": 1000,
                    "confidences": [0.8, 0.9, 0.7],
                    "entity_type_counts": {"person": 10, "organization": 15},
                },
                None, "doc1", NOW, LATER,
            ),
        ]
        effective_config = {
            "extract": {
                "llm_model_id": "anthropic.claude-3-sonnet-20240229-v1:0",
                "confidence_threshold": 0.5,
            }
        }
        mock_cursor.fetchone.side_effect = [
            (effective_config,),
        ]
        mock_cursor.fetchall.side_effect = [
            step_rows,
            [],  # recent runs
            [],  # recent errors
        ]
        result = service.get_step_details(RUN_ID, "extract")
        assert result.metrics["entities_extracted"] == 25
        assert result.metrics["total_input_tokens"] == 5000
        assert result.metrics["avg_confidence"] is not None
        assert result.metrics["entity_type_distribution"] == {"person": 10, "organization": 15}

    def test_returns_inactive_when_no_step_rows(self, service, mock_cursor):
        mock_cursor.fetchone.side_effect = [
            (json.dumps({}),),
        ]
        mock_cursor.fetchall.side_effect = [
            [],  # no step results
            [],  # recent runs
            [],  # recent errors
        ]
        result = service.get_step_details(RUN_ID, "embed")
        assert result.service_status == "Inactive"
        assert result.item_count == 0
        assert result.metrics == {}

    def test_returns_graph_load_step_details(self, service, mock_cursor):
        step_rows = [
            (
                "completed", 2000,
                {"nodes_loaded": 100, "edges_loaded": 50, "load_strategy": "bulk_csv"},
                None, "doc1", NOW, LATER,
            ),
        ]
        mock_cursor.fetchone.side_effect = [
            (json.dumps({"graph_load": {"load_strategy": "bulk_csv", "batch_size": 500}}),),
        ]
        mock_cursor.fetchall.side_effect = [
            step_rows,
            [],
            [],
        ]
        result = service.get_step_details(RUN_ID, "graph_load")
        assert result.metrics["nodes_loaded"] == 100
        assert result.metrics["edges_loaded"] == 50
        assert result.metrics["load_strategy"] == "bulk_csv"

    def test_config_origins_populated(self, service, mock_cursor):
        effective_config = {
            "embed": {
                "embedding_model_id": "amazon.titan-embed-text-v1",
                "search_tier": "standard",
                "opensearch_settings": {
                    "index_refresh_interval": "30s",
                    "number_of_replicas": 1,
                },
            }
        }
        mock_cursor.fetchone.side_effect = [
            (effective_config,),
        ]
        mock_cursor.fetchall.side_effect = [
            [],  # step results
            [],  # recent runs
            [],  # recent errors
        ]
        result = service.get_step_details(RUN_ID, "embed")
        assert "embed.embedding_model_id" in result.config_origins
        assert "embed.search_tier" in result.config_origins
        assert "embed.opensearch_settings.index_refresh_interval" in result.config_origins


# ---------------------------------------------------------------------------
# _determine_current_step tests
# ---------------------------------------------------------------------------


class TestDetermineCurrentStep:
    def test_returns_running_step(self):
        step_statuses = {"parse": "completed", "extract": "running"}
        result = PipelineMonitoringService._determine_current_step(step_statuses)
        assert result == "extract"

    def test_returns_last_completed_when_none_running(self):
        step_statuses = {"parse": "completed", "extract": "completed"}
        result = PipelineMonitoringService._determine_current_step(step_statuses)
        assert result == "extract"

    def test_returns_none_for_empty(self):
        result = PipelineMonitoringService._determine_current_step({})
        assert result is None


# ---------------------------------------------------------------------------
# Error rate and docs_per_minute edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_get_run_metrics_handles_json_string_fields(self, service, mock_cursor):
        mock_cursor.fetchone.return_value = (
            RUN_ID, 10, 5,
            json.dumps({"person": 8, "location": 2}),  # JSON string
            0.9, 0.02, 5.0, 2.0, 0, 0.0, 0.01,
            1000, 200, 90.0,
            json.dumps({"confidence_avg": 90.0}),  # JSON string
            20, NOW, LATER, {},
        )
        result = service.get_run_metrics(RUN_ID)
        assert result.entity_type_counts == {"person": 8, "location": 2}
        assert result.quality_breakdown == {"confidence_avg": 90.0}
