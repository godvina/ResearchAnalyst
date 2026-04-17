"""Unit tests for PatternDiscoveryService with mocked dependencies."""

import json
import uuid
from unittest.mock import MagicMock, patch, call

import pytest

from src.db.neptune import (
    NODE_PROP_CANONICAL_NAME,
    NODE_PROP_CASE_FILE_ID,
    NODE_PROP_CONFIDENCE,
    NODE_PROP_ENTITY_TYPE,
    NODE_PROP_OCCURRENCE_COUNT,
    EDGE_RELATED_TO,
    NeptuneConnectionManager,
    entity_label,
)
from src.db.connection import ConnectionManager
from src.models.pattern import Pattern, PatternReport
from src.services.pattern_discovery_service import (
    BEDROCK_MODEL_ID,
    SIMILARITY_THRESHOLD,
    TOP_CENTRALITY_NODES,
    PatternDiscoveryService,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

CASE_ID = "case-001"


@pytest.fixture
def mock_neptune():
    return MagicMock(spec=NeptuneConnectionManager)


@pytest.fixture
def mock_aurora():
    return MagicMock(spec=ConnectionManager)


@pytest.fixture
def mock_bedrock():
    return MagicMock()


@pytest.fixture
def service(mock_neptune, mock_aurora, mock_bedrock):
    return PatternDiscoveryService(
        neptune_conn=mock_neptune,
        aurora_conn=mock_aurora,
        bedrock_client=mock_bedrock,
    )


def _make_gremlin_node(
    node_id: str = "node-1",
    name: str = "Erich von Däniken",
    etype: str = "person",
    confidence: float = 0.9,
    degree: int = 5,
) -> dict:
    return {
        "id": node_id,
        "name": name,
        "type": etype,
        "confidence": confidence,
        "degree": degree,
    }


def _setup_traversal(mock_neptune):
    """Set up the traversal_source context manager and return the mock g."""
    mock_g = MagicMock()
    mock_neptune.traversal_source.return_value.__enter__ = MagicMock(return_value=mock_g)
    mock_neptune.traversal_source.return_value.__exit__ = MagicMock(return_value=False)
    return mock_g


def _setup_bedrock_response(mock_bedrock, text: str = "AI explanation"):
    """Configure mock Bedrock to return a valid response."""
    body_mock = MagicMock()
    body_mock.read.return_value = json.dumps({
        "content": [{"text": text}],
    }).encode()
    mock_bedrock.invoke_model.return_value = {"body": body_mock}


# ---------------------------------------------------------------------------
# discover_graph_patterns
# ---------------------------------------------------------------------------


class TestDiscoverGraphPatterns:
    def test_returns_patterns_from_centrality(self, service, mock_neptune):
        mock_g = _setup_traversal(mock_neptune)

        # Centrality query chain
        centrality_chain = MagicMock()
        centrality_chain.toList.return_value = [
            _make_gremlin_node("n1", "Entity A", "person", 0.9, 5),
        ]
        mock_g.V.return_value.hasLabel.return_value.project.return_value \
            .by.return_value.by.return_value.by.return_value.by.return_value \
            .by.return_value.order.return_value.by.return_value \
            .limit.return_value = centrality_chain

        # Community detection: no nodes
        mock_g.V.return_value.hasLabel.return_value.values.return_value.toList.return_value = []

        # High centrality nodes for path discovery
        path_chain = MagicMock()
        path_chain.toList.return_value = [
            {"id": "n1", "name": "Entity A", "type": "person"},
        ]
        mock_g.V.return_value.hasLabel.return_value.project.return_value \
            .by.return_value.by.return_value.by.return_value \
            .order.return_value.by.return_value \
            .limit.return_value = path_chain

        patterns = service.discover_graph_patterns(CASE_ID)

        assert isinstance(patterns, list)
        # Should have at least the centrality pattern
        for p in patterns:
            assert isinstance(p, Pattern)
            assert p.connection_type == "graph-based"

    def test_empty_graph_returns_empty(self, service, mock_neptune):
        mock_g = _setup_traversal(mock_neptune)

        # All queries return empty
        empty_chain = MagicMock()
        empty_chain.toList.return_value = []
        mock_g.V.return_value.hasLabel.return_value.project.return_value \
            .by.return_value.by.return_value.by.return_value.by.return_value \
            .by.return_value.order.return_value.by.return_value \
            .limit.return_value = empty_chain
        mock_g.V.return_value.hasLabel.return_value.values.return_value.toList.return_value = []
        mock_g.V.return_value.hasLabel.return_value.project.return_value \
            .by.return_value.by.return_value.by.return_value \
            .order.return_value.by.return_value \
            .limit.return_value = empty_chain

        patterns = service.discover_graph_patterns(CASE_ID)

        assert patterns == []

    def test_uses_correct_label(self, service, mock_neptune):
        mock_g = _setup_traversal(mock_neptune)

        empty_chain = MagicMock()
        empty_chain.toList.return_value = []
        mock_g.V.return_value.hasLabel.return_value.project.return_value \
            .by.return_value.by.return_value.by.return_value.by.return_value \
            .by.return_value.order.return_value.by.return_value \
            .limit.return_value = empty_chain
        mock_g.V.return_value.hasLabel.return_value.values.return_value.toList.return_value = []
        mock_g.V.return_value.hasLabel.return_value.project.return_value \
            .by.return_value.by.return_value.by.return_value \
            .order.return_value.by.return_value \
            .limit.return_value = empty_chain

        service.discover_graph_patterns(CASE_ID)

        expected_label = entity_label(CASE_ID)
        mock_g.V.return_value.hasLabel.assert_called_with(expected_label)


# ---------------------------------------------------------------------------
# discover_vector_patterns
# ---------------------------------------------------------------------------


class TestDiscoverVectorPatterns:
    def test_returns_patterns_from_similar_documents(self, service, mock_aurora):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("doc-1", "doc-2", 0.92),
            ("doc-1", "doc-3", 0.88),
        ]
        mock_aurora.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_aurora.cursor.return_value.__exit__ = MagicMock(return_value=False)

        patterns = service.discover_vector_patterns(CASE_ID)

        assert len(patterns) >= 1
        for p in patterns:
            assert isinstance(p, Pattern)
            assert p.connection_type == "vector-based"
            assert p.confidence_score > 0
            assert len(p.entities_involved) >= 2

    def test_empty_results_returns_empty(self, service, mock_aurora):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_aurora.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_aurora.cursor.return_value.__exit__ = MagicMock(return_value=False)

        patterns = service.discover_vector_patterns(CASE_ID)

        assert patterns == []

    def test_queries_with_correct_case_id_and_threshold(self, service, mock_aurora):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_aurora.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_aurora.cursor.return_value.__exit__ = MagicMock(return_value=False)

        service.discover_vector_patterns(CASE_ID)

        mock_cursor.execute.assert_called_once()
        args = mock_cursor.execute.call_args
        params = args[0][1]
        assert params == (CASE_ID, SIMILARITY_THRESHOLD)

    def test_source_documents_populated(self, service, mock_aurora):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("doc-a", "doc-b", 0.85),
        ]
        mock_aurora.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_aurora.cursor.return_value.__exit__ = MagicMock(return_value=False)

        patterns = service.discover_vector_patterns(CASE_ID)

        assert len(patterns) == 1
        assert "doc-a" in patterns[0].source_documents
        assert "doc-b" in patterns[0].source_documents

    def test_multiple_clusters(self, service, mock_aurora):
        mock_cursor = MagicMock()
        # Two separate clusters: (doc-1, doc-2) and (doc-3, doc-4)
        mock_cursor.fetchall.return_value = [
            ("doc-1", "doc-2", 0.90),
            ("doc-3", "doc-4", 0.85),
        ]
        mock_aurora.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_aurora.cursor.return_value.__exit__ = MagicMock(return_value=False)

        patterns = service.discover_vector_patterns(CASE_ID)

        assert len(patterns) == 2


# ---------------------------------------------------------------------------
# _deduplicate_patterns
# ---------------------------------------------------------------------------


class TestDeduplicatePatterns:
    def test_removes_exact_duplicates(self):
        p1 = Pattern(
            pattern_id="p1",
            entities_involved=[{"name": "A"}, {"name": "B"}],
            connection_type="graph-based",
            explanation="",
            confidence_score=0.9,
            novelty_score=0.8,
        )
        p2 = Pattern(
            pattern_id="p2",
            entities_involved=[{"name": "B"}, {"name": "A"}],
            connection_type="graph-based",
            explanation="",
            confidence_score=0.7,
            novelty_score=0.6,
        )

        result = PatternDiscoveryService._deduplicate_patterns([p1, p2])

        assert len(result) == 1
        assert result[0].pattern_id == "p1"

    def test_keeps_different_connection_types(self):
        p1 = Pattern(
            pattern_id="p1",
            entities_involved=[{"name": "A"}, {"name": "B"}],
            connection_type="graph-based",
            explanation="",
            confidence_score=0.9,
            novelty_score=0.8,
        )
        p2 = Pattern(
            pattern_id="p2",
            entities_involved=[{"name": "A"}, {"name": "B"}],
            connection_type="vector-based",
            explanation="",
            confidence_score=0.7,
            novelty_score=0.6,
        )

        result = PatternDiscoveryService._deduplicate_patterns([p1, p2])

        assert len(result) == 2

    def test_keeps_different_entity_sets(self):
        p1 = Pattern(
            pattern_id="p1",
            entities_involved=[{"name": "A"}, {"name": "B"}],
            connection_type="graph-based",
            explanation="",
            confidence_score=0.9,
            novelty_score=0.8,
        )
        p2 = Pattern(
            pattern_id="p2",
            entities_involved=[{"name": "A"}, {"name": "C"}],
            connection_type="graph-based",
            explanation="",
            confidence_score=0.7,
            novelty_score=0.6,
        )

        result = PatternDiscoveryService._deduplicate_patterns([p1, p2])

        assert len(result) == 2

    def test_empty_input(self):
        result = PatternDiscoveryService._deduplicate_patterns([])
        assert result == []

    def test_single_pattern(self):
        p = Pattern(
            pattern_id="p1",
            entities_involved=[{"name": "A"}],
            connection_type="graph-based",
            explanation="",
            confidence_score=0.9,
            novelty_score=0.8,
        )
        result = PatternDiscoveryService._deduplicate_patterns([p])
        assert len(result) == 1


# ---------------------------------------------------------------------------
# _cluster_documents
# ---------------------------------------------------------------------------


class TestClusterDocuments:
    def test_single_pair(self):
        rows = [("doc-1", "doc-2", 0.9)]
        clusters = PatternDiscoveryService._cluster_documents(rows)

        assert len(clusters) == 1
        docs, avg_sim = clusters[0]
        assert docs == {"doc-1", "doc-2"}
        assert avg_sim == pytest.approx(0.9)

    def test_transitive_clustering(self):
        rows = [
            ("doc-1", "doc-2", 0.9),
            ("doc-2", "doc-3", 0.85),
        ]
        clusters = PatternDiscoveryService._cluster_documents(rows)

        assert len(clusters) == 1
        docs, _ = clusters[0]
        assert docs == {"doc-1", "doc-2", "doc-3"}

    def test_separate_clusters(self):
        rows = [
            ("doc-1", "doc-2", 0.9),
            ("doc-3", "doc-4", 0.85),
        ]
        clusters = PatternDiscoveryService._cluster_documents(rows)

        assert len(clusters) == 2
        all_docs = [docs for docs, _ in clusters]
        assert {"doc-1", "doc-2"} in all_docs
        assert {"doc-3", "doc-4"} in all_docs

    def test_empty_input(self):
        clusters = PatternDiscoveryService._cluster_documents([])
        assert clusters == []


# ---------------------------------------------------------------------------
# generate_pattern_report
# ---------------------------------------------------------------------------


class TestGeneratePatternReport:
    def test_produces_report_with_correct_structure(
        self, service, mock_neptune, mock_aurora, mock_bedrock,
    ):
        # Set up Neptune to return empty graph patterns
        mock_g = _setup_traversal(mock_neptune)
        empty_chain = MagicMock()
        empty_chain.toList.return_value = []
        mock_g.V.return_value.hasLabel.return_value.project.return_value \
            .by.return_value.by.return_value.by.return_value.by.return_value \
            .by.return_value.order.return_value.by.return_value \
            .limit.return_value = empty_chain
        mock_g.V.return_value.hasLabel.return_value.values.return_value.toList.return_value = []
        mock_g.V.return_value.hasLabel.return_value.project.return_value \
            .by.return_value.by.return_value.by.return_value \
            .order.return_value.by.return_value \
            .limit.return_value = empty_chain

        # Set up Aurora to return vector patterns
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("doc-1", "doc-2", 0.88),
        ]
        mock_aurora.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_aurora.cursor.return_value.__exit__ = MagicMock(return_value=False)

        # Set up Bedrock
        _setup_bedrock_response(mock_bedrock, "This pattern shows semantic similarity.")

        report = service.generate_pattern_report(CASE_ID)

        assert isinstance(report, PatternReport)
        assert report.case_file_id == CASE_ID
        assert report.report_id  # non-empty
        assert report.graph_patterns_count == 0
        assert report.vector_patterns_count == 1
        assert report.combined_count == 1

    def test_patterns_ranked_by_confidence_times_novelty(
        self, service, mock_neptune, mock_aurora, mock_bedrock,
    ):
        # Patch discover methods to return controlled patterns
        with patch.object(service, "discover_graph_patterns") as mock_graph, \
             patch.object(service, "discover_vector_patterns") as mock_vector:

            mock_graph.return_value = [
                Pattern(
                    pattern_id="p1",
                    entities_involved=[{"name": "A"}],
                    connection_type="graph-based",
                    explanation="",
                    confidence_score=0.5,
                    novelty_score=0.5,  # score = 0.25
                ),
                Pattern(
                    pattern_id="p2",
                    entities_involved=[{"name": "B"}],
                    connection_type="graph-based",
                    explanation="",
                    confidence_score=0.9,
                    novelty_score=0.9,  # score = 0.81
                ),
            ]
            mock_vector.return_value = [
                Pattern(
                    pattern_id="p3",
                    entities_involved=[{"name": "C"}],
                    connection_type="vector-based",
                    explanation="",
                    confidence_score=0.7,
                    novelty_score=0.8,  # score = 0.56
                ),
            ]

            _setup_bedrock_response(mock_bedrock)

            # Mock Aurora cursor for _store_report
            mock_cursor = MagicMock()
            mock_aurora.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
            mock_aurora.cursor.return_value.__exit__ = MagicMock(return_value=False)

            report = service.generate_pattern_report(CASE_ID)

        scores = [p.confidence_score * p.novelty_score for p in report.patterns]
        assert scores == sorted(scores, reverse=True)
        assert report.patterns[0].pattern_id == "p2"

    def test_deduplication_applied(
        self, service, mock_neptune, mock_aurora, mock_bedrock,
    ):
        with patch.object(service, "discover_graph_patterns") as mock_graph, \
             patch.object(service, "discover_vector_patterns") as mock_vector:

            # Same entity set and connection type = duplicate
            mock_graph.return_value = [
                Pattern(
                    pattern_id="p1",
                    entities_involved=[{"name": "A"}, {"name": "B"}],
                    connection_type="graph-based",
                    explanation="",
                    confidence_score=0.9,
                    novelty_score=0.8,
                ),
                Pattern(
                    pattern_id="p2",
                    entities_involved=[{"name": "B"}, {"name": "A"}],
                    connection_type="graph-based",
                    explanation="",
                    confidence_score=0.7,
                    novelty_score=0.6,
                ),
            ]
            mock_vector.return_value = []

            _setup_bedrock_response(mock_bedrock)

            mock_cursor = MagicMock()
            mock_aurora.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
            mock_aurora.cursor.return_value.__exit__ = MagicMock(return_value=False)

            report = service.generate_pattern_report(CASE_ID)

        assert report.combined_count == 1

    def test_stores_report_in_aurora(
        self, service, mock_neptune, mock_aurora, mock_bedrock,
    ):
        with patch.object(service, "discover_graph_patterns", return_value=[]), \
             patch.object(service, "discover_vector_patterns", return_value=[]):

            _setup_bedrock_response(mock_bedrock)

            mock_cursor = MagicMock()
            mock_aurora.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
            mock_aurora.cursor.return_value.__exit__ = MagicMock(return_value=False)

            service.generate_pattern_report(CASE_ID)

        mock_cursor.execute.assert_called_once()
        sql = mock_cursor.execute.call_args[0][0]
        assert "INSERT INTO pattern_reports" in sql

    def test_bedrock_failure_uses_fallback_explanation(
        self, service, mock_neptune, mock_aurora, mock_bedrock,
    ):
        with patch.object(service, "discover_graph_patterns") as mock_graph, \
             patch.object(service, "discover_vector_patterns", return_value=[]):

            mock_graph.return_value = [
                Pattern(
                    pattern_id="p1",
                    entities_involved=[{"name": "A", "type": "person"}],
                    connection_type="graph-based",
                    explanation="",
                    confidence_score=0.9,
                    novelty_score=0.8,
                ),
            ]

            # Bedrock raises an exception
            mock_bedrock.invoke_model.side_effect = Exception("Bedrock timeout")

            mock_cursor = MagicMock()
            mock_aurora.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
            mock_aurora.cursor.return_value.__exit__ = MagicMock(return_value=False)

            report = service.generate_pattern_report(CASE_ID)

        assert len(report.patterns) == 1
        # Fallback explanation should contain entity name
        assert "A" in report.patterns[0].explanation
        assert "graph-based" in report.patterns[0].explanation


# ---------------------------------------------------------------------------
# _generate_explanation
# ---------------------------------------------------------------------------


class TestGenerateExplanation:
    def test_calls_bedrock_with_pattern_info(self, service, mock_bedrock):
        _setup_bedrock_response(mock_bedrock, "Explanation text")

        pattern = Pattern(
            pattern_id="p1",
            entities_involved=[
                {"name": "Erich von Däniken", "type": "person"},
                {"name": "Nazca Lines", "type": "location"},
            ],
            connection_type="graph-based",
            explanation="",
            confidence_score=0.85,
            novelty_score=0.7,
        )

        result = service._generate_explanation(pattern)

        assert result == "Explanation text"
        mock_bedrock.invoke_model.assert_called_once()
        call_kwargs = mock_bedrock.invoke_model.call_args[1]
        assert call_kwargs["modelId"] == BEDROCK_MODEL_ID
        body = json.loads(call_kwargs["body"])
        assert "Erich von Däniken" in body["messages"][0]["content"]
        assert "Nazca Lines" in body["messages"][0]["content"]

    def test_returns_fallback_on_error(self, service, mock_bedrock):
        mock_bedrock.invoke_model.side_effect = RuntimeError("API error")

        pattern = Pattern(
            pattern_id="p1",
            entities_involved=[{"name": "X", "type": "artifact"}],
            connection_type="vector-based",
            explanation="",
            confidence_score=0.6,
            novelty_score=0.5,
        )

        result = service._generate_explanation(pattern)

        assert "X" in result
        assert "vector-based" in result


# ---------------------------------------------------------------------------
# Constructor
# ---------------------------------------------------------------------------


class TestServiceInit:
    def test_accepts_dependencies(self, mock_neptune, mock_aurora, mock_bedrock):
        svc = PatternDiscoveryService(mock_neptune, mock_aurora, mock_bedrock)

        assert svc._neptune is mock_neptune
        assert svc._aurora is mock_aurora
        assert svc._bedrock is mock_bedrock
