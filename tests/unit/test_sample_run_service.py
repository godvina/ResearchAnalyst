"""Unit tests for SampleRunService."""

import json
from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest

from src.models.entity import EntityType
from src.models.pipeline_config import (
    EffectiveConfig,
    QualityScore,
    SampleRun,
    SampleRunComparison,
    SampleRunSnapshot,
)
from src.services.config_resolution_service import ConfigResolutionService
from src.services.sample_run_service import SampleRunService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

CASE_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
USER = "investigator@doj.gov"
NOW = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
RUN_ID_A = str(uuid4())
RUN_ID_B = str(uuid4())
SNAPSHOT_ID_A = uuid4()
SNAPSHOT_ID_B = uuid4()


def _make_effective_config(version=1):
    return EffectiveConfig(
        case_id=UUID(CASE_ID),
        config_version=version,
        effective_json={
            "extract": {"confidence_threshold": 0.5},
            "parse": {"pdf_method": "text"},
        },
        origins={"extract.confidence_threshold": "system_default"},
    )


def _make_snapshot(
    run_id, snapshot_id, entities=None, relationships=None, config=None
):
    return SampleRunSnapshot(
        snapshot_id=snapshot_id,
        run_id=UUID(run_id) if isinstance(run_id, str) else run_id,
        case_id=UUID(CASE_ID),
        config_version=1,
        snapshot_name="test_snapshot",
        entities=entities or [],
        relationships=relationships or [],
        quality_metrics={"config": config or {"extract": {"confidence_threshold": 0.5}}},
        created_at=NOW,
    )


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
def mock_sf_client():
    client = MagicMock()
    client.start_execution.return_value = {
        "executionArn": "arn:aws:states:us-east-1:123456789:execution:pipeline:sample-test",
    }
    return client


@pytest.fixture()
def mock_resolution(mock_db):
    resolution = ConfigResolutionService(mock_db)
    resolution.resolve_effective_config = MagicMock(
        return_value=_make_effective_config()
    )
    return resolution


@pytest.fixture()
def service(mock_db, mock_sf_client, mock_resolution):
    return SampleRunService(mock_db, mock_sf_client, mock_resolution)


# ---------------------------------------------------------------------------
# start_sample_run tests
# ---------------------------------------------------------------------------


class TestStartSampleRun:
    def test_starts_execution_with_sample_mode(
        self, service, mock_sf_client, mock_cursor
    ):
        doc_ids = ["doc-1", "doc-2", "doc-3"]
        result = service.start_sample_run(CASE_ID, doc_ids, USER)

        assert isinstance(result, SampleRun)
        assert result.status == "running"
        assert result.document_ids == doc_ids
        assert result.config_version == 1
        assert result.created_by == USER

        # Verify Step Functions was called with sample_mode
        call_args = mock_sf_client.start_execution.call_args
        sfn_input = json.loads(call_args[1]["input"])
        assert sfn_input["sample_mode"] is True
        assert sfn_input["document_ids"] == doc_ids
        assert sfn_input["case_id"] == CASE_ID

    def test_inserts_pipeline_runs_record(self, service, mock_cursor):
        doc_ids = ["doc-1"]
        service.start_sample_run(CASE_ID, doc_ids, USER)

        mock_cursor.execute.assert_called_once()
        sql = mock_cursor.execute.call_args[0][0]
        assert "INSERT INTO pipeline_runs" in sql

        params = mock_cursor.execute.call_args[0][1]
        # is_sample_run should be True
        assert params[4] is True
        # document_ids
        assert params[5] == ["doc-1"]
        # document_count
        assert params[6] == 1

    def test_rejects_empty_document_list(self, service):
        with pytest.raises(ValueError, match="At least 1 document"):
            service.start_sample_run(CASE_ID, [], USER)

    def test_rejects_more_than_50_documents(self, service):
        doc_ids = [f"doc-{i}" for i in range(51)]
        with pytest.raises(ValueError, match="at most 50"):
            service.start_sample_run(CASE_ID, doc_ids, USER)

    def test_accepts_exactly_50_documents(self, service, mock_cursor):
        doc_ids = [f"doc-{i}" for i in range(50)]
        result = service.start_sample_run(CASE_ID, doc_ids, USER)
        assert len(result.document_ids) == 50

    def test_accepts_exactly_1_document(self, service, mock_cursor):
        result = service.start_sample_run(CASE_ID, ["doc-1"], USER)
        assert len(result.document_ids) == 1

    def test_resolves_effective_config(self, service, mock_resolution, mock_cursor):
        service.start_sample_run(CASE_ID, ["doc-1"], USER)
        mock_resolution.resolve_effective_config.assert_called_once_with(CASE_ID)


# ---------------------------------------------------------------------------
# get_sample_run tests
# ---------------------------------------------------------------------------


class TestGetSampleRun:
    def test_returns_sample_run(self, service, mock_cursor):
        run_id = str(uuid4())
        mock_cursor.fetchone.return_value = (
            run_id,
            CASE_ID,
            1,
            ["doc-1", "doc-2"],
            "completed",
            NOW,
            NOW,
            USER,
        )

        result = service.get_sample_run(run_id)
        assert isinstance(result, SampleRun)
        assert result.status == "completed"
        assert result.document_ids == ["doc-1", "doc-2"]

    def test_raises_when_not_found(self, service, mock_cursor):
        mock_cursor.fetchone.return_value = None
        with pytest.raises(ValueError, match="not found"):
            service.get_sample_run(str(uuid4()))


# ---------------------------------------------------------------------------
# list_sample_runs tests
# ---------------------------------------------------------------------------


class TestListSampleRuns:
    def test_returns_list_of_runs(self, service, mock_cursor):
        run_id_1 = str(uuid4())
        run_id_2 = str(uuid4())
        mock_cursor.fetchall.return_value = [
            (run_id_1, CASE_ID, 1, ["doc-1"], "completed", NOW, NOW, USER),
            (run_id_2, CASE_ID, 2, ["doc-2"], "running", NOW, None, USER),
        ]

        result = service.list_sample_runs(CASE_ID)
        assert len(result) == 2
        assert result[0].status == "completed"
        assert result[1].status == "running"

    def test_returns_empty_list(self, service, mock_cursor):
        mock_cursor.fetchall.return_value = []
        result = service.list_sample_runs(CASE_ID)
        assert result == []


# ---------------------------------------------------------------------------
# compute_quality_score tests
# ---------------------------------------------------------------------------


class TestComputeQualityScore:
    def test_empty_entities_returns_zero_scores(self):
        snapshot = _make_snapshot(RUN_ID_A, SNAPSHOT_ID_A, entities=[], relationships=[])
        score = SampleRunService.compute_quality_score(snapshot)

        assert score.overall == 20.0  # only noise_ratio_score contributes (1.0 * 100 * 0.20)
        assert score.confidence_avg == 0.0
        assert score.type_diversity == 0.0
        assert score.relationship_density == 0.0
        assert score.noise_ratio_score == 100.0  # no entities = no noise

    def test_perfect_score_scenario(self):
        """All entities high confidence, all 14 types, dense relationships."""
        entities = []
        for et in EntityType:
            entities.append({
                "canonical_name": f"entity_{et.value}",
                "entity_type": et.value,
                "confidence": 1.0,
            })
        # 3 relationships per entity = density of 3.0 → capped at 100
        relationships = []
        for i in range(len(entities) * 3):
            relationships.append({
                "source_entity": f"entity_{i % len(entities)}",
                "target_entity": f"entity_{(i + 1) % len(entities)}",
                "relationship_type": "co-occurrence",
            })

        snapshot = _make_snapshot(
            RUN_ID_A, SNAPSHOT_ID_A,
            entities=entities,
            relationships=relationships,
            config={"extract": {"confidence_threshold": 0.5}},
        )
        score = SampleRunService.compute_quality_score(snapshot)

        assert score.confidence_avg == 100.0
        assert score.type_diversity == 100.0
        assert score.relationship_density == 100.0
        assert score.noise_ratio_score == 100.0
        assert score.overall == 100.0

    def test_weighted_formula_correctness(self):
        """Verify the weighted formula matches design doc weights."""
        entities = [
            {"canonical_name": "Alice", "entity_type": "person", "confidence": 0.8},
            {"canonical_name": "Bob", "entity_type": "person", "confidence": 0.6},
        ]
        relationships = [
            {
                "source_entity": "Alice",
                "target_entity": "Bob",
                "relationship_type": "co-occurrence",
            }
        ]
        snapshot = _make_snapshot(
            RUN_ID_A, SNAPSHOT_ID_A,
            entities=entities,
            relationships=relationships,
            config={"extract": {"confidence_threshold": 0.5}},
        )
        score = SampleRunService.compute_quality_score(snapshot)

        # Manual calculation:
        # confidence_avg = ((0.8 + 0.6) / 2) * 100 = 70.0
        assert score.confidence_avg == 70.0

        # type_diversity = (1 / 14) * 100 ≈ 7.1
        expected_diversity = round((1 / len(EntityType)) * 100, 1)
        assert score.type_diversity == expected_diversity

        # relationship_density = min((1/2) / 3.0, 1.0) * 100 ≈ 16.7
        expected_density = round(min((1 / 2) / 3.0, 1.0) * 100, 1)
        assert score.relationship_density == expected_density

        # noise_ratio_score = (1.0 - 0/2) * 100 = 100.0 (both above 0.5)
        assert score.noise_ratio_score == 100.0

        # overall = 70.0*0.35 + 7.1*0.20 + 16.7*0.25 + 100.0*0.20
        expected_overall = round(
            score.confidence_avg * 0.35
            + score.type_diversity * 0.20
            + score.relationship_density * 0.25
            + score.noise_ratio_score * 0.20,
            1,
        )
        assert score.overall == expected_overall

    def test_noise_ratio_with_low_confidence_entities(self):
        """Entities below threshold increase noise, lowering noise_ratio_score."""
        entities = [
            {"canonical_name": "A", "entity_type": "person", "confidence": 0.3},
            {"canonical_name": "B", "entity_type": "location", "confidence": 0.2},
            {"canonical_name": "C", "entity_type": "date", "confidence": 0.8},
            {"canonical_name": "D", "entity_type": "event", "confidence": 0.9},
        ]
        snapshot = _make_snapshot(
            RUN_ID_A, SNAPSHOT_ID_A,
            entities=entities,
            relationships=[],
            config={"extract": {"confidence_threshold": 0.5}},
        )
        score = SampleRunService.compute_quality_score(snapshot)

        # 2 out of 4 below threshold → noise_ratio = 0.5 → score = 50.0
        assert score.noise_ratio_score == 50.0

    def test_score_bounded_0_to_100(self):
        """All component scores should be in [0, 100]."""
        entities = [
            {"canonical_name": "X", "entity_type": "person", "confidence": 0.5},
        ]
        snapshot = _make_snapshot(
            RUN_ID_A, SNAPSHOT_ID_A, entities=entities, relationships=[]
        )
        score = SampleRunService.compute_quality_score(snapshot)

        assert 0 <= score.overall <= 100
        assert 0 <= score.confidence_avg <= 100
        assert 0 <= score.type_diversity <= 100
        assert 0 <= score.relationship_density <= 100
        assert 0 <= score.noise_ratio_score <= 100

    def test_relationship_density_capped_at_100(self):
        """Even with very dense graphs, density score caps at 100."""
        entities = [
            {"canonical_name": "A", "entity_type": "person", "confidence": 0.9},
        ]
        # 10 relationships for 1 entity → raw_density = 10.0
        relationships = [
            {"source_entity": "A", "target_entity": f"B{i}", "relationship_type": "co-occurrence"}
            for i in range(10)
        ]
        snapshot = _make_snapshot(
            RUN_ID_A, SNAPSHOT_ID_A,
            entities=entities,
            relationships=relationships,
        )
        score = SampleRunService.compute_quality_score(snapshot)
        assert score.relationship_density == 100.0


# ---------------------------------------------------------------------------
# compare_runs tests
# ---------------------------------------------------------------------------


class TestCompareRuns:
    def _setup_snapshots(self, service, mock_cursor, entities_a, entities_b,
                         rels_a=None, rels_b=None):
        """Helper to set up mock cursor for two snapshot loads."""
        snap_a = (
            str(SNAPSHOT_ID_A), RUN_ID_A, CASE_ID, 1, "snap_a",
            entities_a, rels_a or [],
            {"config": {"extract": {"confidence_threshold": 0.5}}},
            NOW,
        )
        snap_b = (
            str(SNAPSHOT_ID_B), RUN_ID_B, CASE_ID, 2, "snap_b",
            entities_b, rels_b or [],
            {"config": {"extract": {"confidence_threshold": 0.5}}},
            NOW,
        )
        mock_cursor.fetchone.side_effect = [snap_a, snap_b]

    def test_detects_added_entities(self, service, mock_cursor):
        entities_a = [
            {"canonical_name": "Alice", "entity_type": "person", "confidence": 0.8},
        ]
        entities_b = [
            {"canonical_name": "Alice", "entity_type": "person", "confidence": 0.8},
            {"canonical_name": "Bob", "entity_type": "person", "confidence": 0.7},
        ]
        self._setup_snapshots(service, mock_cursor, entities_a, entities_b)

        result = service.compare_runs(RUN_ID_A, RUN_ID_B)
        assert len(result.entities_added) == 1
        assert result.entities_added[0]["canonical_name"] == "Bob"
        assert len(result.entities_removed) == 0

    def test_detects_removed_entities(self, service, mock_cursor):
        entities_a = [
            {"canonical_name": "Alice", "entity_type": "person", "confidence": 0.8},
            {"canonical_name": "Bob", "entity_type": "person", "confidence": 0.7},
        ]
        entities_b = [
            {"canonical_name": "Alice", "entity_type": "person", "confidence": 0.8},
        ]
        self._setup_snapshots(service, mock_cursor, entities_a, entities_b)

        result = service.compare_runs(RUN_ID_A, RUN_ID_B)
        assert len(result.entities_removed) == 1
        assert result.entities_removed[0]["canonical_name"] == "Bob"

    def test_detects_changed_entities(self, service, mock_cursor):
        entities_a = [
            {"canonical_name": "Alice", "entity_type": "person", "confidence": 0.6},
        ]
        entities_b = [
            {"canonical_name": "Alice", "entity_type": "person", "confidence": 0.9},
        ]
        self._setup_snapshots(service, mock_cursor, entities_a, entities_b)

        result = service.compare_runs(RUN_ID_A, RUN_ID_B)
        assert len(result.entities_changed) == 1
        assert result.entities_changed[0]["name"] == "Alice"
        assert result.entities_changed[0]["before"]["confidence"] == 0.6
        assert result.entities_changed[0]["after"]["confidence"] == 0.9

    def test_detects_relationship_changes(self, service, mock_cursor):
        entities = [
            {"canonical_name": "Alice", "entity_type": "person", "confidence": 0.8},
            {"canonical_name": "Bob", "entity_type": "person", "confidence": 0.7},
        ]
        rels_a = [
            {"source_entity": "Alice", "target_entity": "Bob", "relationship_type": "co-occurrence"},
        ]
        rels_b = [
            {"source_entity": "Alice", "target_entity": "Bob", "relationship_type": "co-occurrence"},
            {"source_entity": "Bob", "target_entity": "Alice", "relationship_type": "causal"},
        ]
        self._setup_snapshots(service, mock_cursor, entities, entities, rels_a, rels_b)

        result = service.compare_runs(RUN_ID_A, RUN_ID_B)
        added_rels = [r for r in result.relationship_changes if r["change"] == "added"]
        assert len(added_rels) == 1

    def test_quality_deltas_computed(self, service, mock_cursor):
        entities_a = [
            {"canonical_name": "A", "entity_type": "person", "confidence": 0.5},
        ]
        entities_b = [
            {"canonical_name": "A", "entity_type": "person", "confidence": 0.9},
        ]
        self._setup_snapshots(service, mock_cursor, entities_a, entities_b)

        result = service.compare_runs(RUN_ID_A, RUN_ID_B)
        assert isinstance(result.quality_a, QualityScore)
        assert isinstance(result.quality_b, QualityScore)
        assert "overall" in result.quality_delta
        assert "confidence_avg" in result.quality_delta
        # B has higher confidence → positive delta
        assert result.quality_delta["confidence_avg"] > 0

    def test_raises_when_snapshot_not_found(self, service, mock_cursor):
        mock_cursor.fetchone.return_value = None
        with pytest.raises(ValueError, match="Snapshot not found"):
            service.compare_runs(RUN_ID_A, RUN_ID_B)
