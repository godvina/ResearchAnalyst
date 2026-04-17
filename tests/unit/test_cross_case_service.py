"""Unit tests for CrossCaseService with mocked dependencies."""

import json
import uuid
from unittest.mock import MagicMock, patch, call

import pytest

from src.db.neptune import (
    EDGE_CROSS_CASE_LINK,
    EDGE_PROP_CONFIDENCE,
    EDGE_PROP_CROSS_CASE_GRAPH_ID,
    EDGE_PROP_RELATIONSHIP_TYPE,
    NODE_PROP_CANONICAL_NAME,
    NODE_PROP_CASE_FILE_ID,
    NODE_PROP_CONFIDENCE,
    NODE_PROP_ENTITY_ID,
    NODE_PROP_ENTITY_TYPE,
    NeptuneConnectionManager,
    cross_case_label,
    entity_label,
)
from src.db.connection import ConnectionManager
from src.models.case_file import CrossCaseGraph
from src.models.pattern import CrossCaseMatch, CrossReferenceReport
from src.services.case_file_service import CaseFileService
from src.services.cross_case_service import (
    BEDROCK_MODEL_ID,
    CrossCaseService,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

CASE_A = "case-aaa"
CASE_B = "case-bbb"
CASE_C = "case-ccc"
GRAPH_ID = "graph-001"


@pytest.fixture
def mock_neptune():
    return MagicMock(spec=NeptuneConnectionManager)


@pytest.fixture
def mock_aurora():
    return MagicMock(spec=ConnectionManager)


@pytest.fixture
def mock_case_file_service():
    return MagicMock(spec=CaseFileService)


@pytest.fixture
def mock_bedrock():
    return MagicMock()


@pytest.fixture
def service(mock_neptune, mock_aurora, mock_case_file_service, mock_bedrock):
    return CrossCaseService(
        neptune_conn=mock_neptune,
        aurora_conn=mock_aurora,
        case_file_service=mock_case_file_service,
        bedrock_client=mock_bedrock,
    )


def _setup_traversal(mock_neptune):
    """Set up the traversal_source context manager and return the mock g."""
    mock_g = MagicMock()
    mock_neptune.traversal_source.return_value.__enter__ = MagicMock(return_value=mock_g)
    mock_neptune.traversal_source.return_value.__exit__ = MagicMock(return_value=False)
    return mock_g


def _setup_bedrock_response(mock_bedrock, text: str = "AI analysis text"):
    """Configure mock Bedrock to return a valid response."""
    body_mock = MagicMock()
    body_mock.read.return_value = json.dumps({
        "content": [{"text": text}],
    }).encode()
    mock_bedrock.invoke_model.return_value = {"body": body_mock}


def _make_entity_node(
    entity_id: str = "ent-1",
    name: str = "Erich von Däniken",
    etype: str = "person",
    case_id: str = CASE_A,
) -> dict:
    return {
        "entity_id": entity_id,
        "canonical_name": name,
        "entity_type": etype,
        "case_file_id": case_id,
    }


def _make_cross_case_graph(graph_id: str = GRAPH_ID) -> CrossCaseGraph:
    from datetime import datetime, timezone

    return CrossCaseGraph(
        graph_id=graph_id,
        name="Test Graph",
        linked_case_ids=[CASE_A, CASE_B],
        created_at=datetime.now(timezone.utc),
        neptune_subgraph_label=cross_case_label(graph_id),
    )


# ---------------------------------------------------------------------------
# Constructor
# ---------------------------------------------------------------------------


class TestServiceInit:
    def test_accepts_dependencies(
        self, mock_neptune, mock_aurora, mock_case_file_service, mock_bedrock,
    ):
        svc = CrossCaseService(mock_neptune, mock_aurora, mock_case_file_service, mock_bedrock)
        assert svc._neptune is mock_neptune
        assert svc._aurora is mock_aurora
        assert svc._case_file_service is mock_case_file_service
        assert svc._bedrock is mock_bedrock


# ---------------------------------------------------------------------------
# find_shared_entities
# ---------------------------------------------------------------------------


class TestFindSharedEntities:
    def test_returns_matches_for_shared_canonical_names(self, service, mock_neptune):
        mock_g = _setup_traversal(mock_neptune)

        # Set up Neptune to return entities for each case.
        entity_a = _make_entity_node("ent-a1", "Nazca Lines", "location", CASE_A)
        entity_b = _make_entity_node("ent-b1", "Nazca Lines", "location", CASE_B)

        # The traversal chain: g.V().hasLabel(label).project(...).by(...).toList()
        call_count = [0]
        entities_by_call = [[entity_a], [entity_b]]

        def toList_side_effect():
            idx = call_count[0]
            call_count[0] += 1
            return entities_by_call[idx] if idx < len(entities_by_call) else []

        chain = MagicMock()
        chain.toList = toList_side_effect
        mock_g.V.return_value.hasLabel.return_value.project.return_value \
            .by.return_value.by.return_value.by.return_value.by.return_value = chain

        matches = service.find_shared_entities([CASE_A, CASE_B])

        assert len(matches) == 1
        assert matches[0].entity_a["name"] == "Nazca Lines"
        assert matches[0].entity_b["name"] == "Nazca Lines"
        assert matches[0].entity_a["case_id"] == CASE_A
        assert matches[0].entity_b["case_id"] == CASE_B
        assert matches[0].similarity_score == 1.0

    def test_returns_empty_for_no_shared_names(self, service, mock_neptune):
        mock_g = _setup_traversal(mock_neptune)

        entity_a = _make_entity_node("ent-a1", "Pyramids", "location", CASE_A)
        entity_b = _make_entity_node("ent-b1", "Stonehenge", "location", CASE_B)

        call_count = [0]
        entities_by_call = [[entity_a], [entity_b]]

        def toList_side_effect():
            idx = call_count[0]
            call_count[0] += 1
            return entities_by_call[idx] if idx < len(entities_by_call) else []

        chain = MagicMock()
        chain.toList = toList_side_effect
        mock_g.V.return_value.hasLabel.return_value.project.return_value \
            .by.return_value.by.return_value.by.return_value.by.return_value = chain

        matches = service.find_shared_entities([CASE_A, CASE_B])

        assert matches == []

    def test_returns_empty_for_single_case(self, service):
        matches = service.find_shared_entities([CASE_A])
        assert matches == []

    def test_returns_empty_for_empty_list(self, service):
        matches = service.find_shared_entities([])
        assert matches == []

    def test_multiple_shared_entities(self, service, mock_neptune):
        mock_g = _setup_traversal(mock_neptune)

        entities_a = [
            _make_entity_node("a1", "Nazca Lines", "location", CASE_A),
            _make_entity_node("a2", "Erich von Däniken", "person", CASE_A),
        ]
        entities_b = [
            _make_entity_node("b1", "Nazca Lines", "location", CASE_B),
            _make_entity_node("b2", "Erich von Däniken", "person", CASE_B),
        ]

        call_count = [0]
        entities_by_call = [entities_a, entities_b]

        def toList_side_effect():
            idx = call_count[0]
            call_count[0] += 1
            return entities_by_call[idx] if idx < len(entities_by_call) else []

        chain = MagicMock()
        chain.toList = toList_side_effect
        mock_g.V.return_value.hasLabel.return_value.project.return_value \
            .by.return_value.by.return_value.by.return_value.by.return_value = chain

        matches = service.find_shared_entities([CASE_A, CASE_B])

        assert len(matches) == 2
        names = {m.entity_a["name"] for m in matches}
        assert names == {"Nazca Lines", "Erich von Däniken"}

    def test_three_cases_pairwise_matching(self, service, mock_neptune):
        mock_g = _setup_traversal(mock_neptune)

        entities_a = [_make_entity_node("a1", "Shared", "theme", CASE_A)]
        entities_b = [_make_entity_node("b1", "Shared", "theme", CASE_B)]
        entities_c = [_make_entity_node("c1", "Shared", "theme", CASE_C)]

        call_count = [0]
        entities_by_call = [entities_a, entities_b, entities_c]

        def toList_side_effect():
            idx = call_count[0]
            call_count[0] += 1
            return entities_by_call[idx] if idx < len(entities_by_call) else []

        chain = MagicMock()
        chain.toList = toList_side_effect
        mock_g.V.return_value.hasLabel.return_value.project.return_value \
            .by.return_value.by.return_value.by.return_value.by.return_value = chain

        matches = service.find_shared_entities([CASE_A, CASE_B, CASE_C])

        # 3 pairs: A-B, A-C, B-C
        assert len(matches) == 3


# ---------------------------------------------------------------------------
# generate_cross_reference_report
# ---------------------------------------------------------------------------


class TestGenerateCrossReferenceReport:
    def test_produces_report_with_required_sections(self, service, mock_neptune, mock_bedrock):
        mock_g = _setup_traversal(mock_neptune)

        entity_a = _make_entity_node("a1", "Nazca Lines", "location", CASE_A)
        entity_b = _make_entity_node("b1", "Nazca Lines", "location", CASE_B)

        call_count = [0]
        entities_by_call = [[entity_a], [entity_b]]

        def toList_side_effect():
            idx = call_count[0]
            call_count[0] += 1
            return entities_by_call[idx] if idx < len(entities_by_call) else []

        chain = MagicMock()
        chain.toList = toList_side_effect
        mock_g.V.return_value.hasLabel.return_value.project.return_value \
            .by.return_value.by.return_value.by.return_value.by.return_value = chain

        _setup_bedrock_response(mock_bedrock, "Significant cross-case connection found.")

        report = service.generate_cross_reference_report([CASE_A, CASE_B])

        assert isinstance(report, CrossReferenceReport)
        assert report.report_id
        assert report.case_ids == [CASE_A, CASE_B]
        assert len(report.shared_entities) == 1
        assert len(report.parallel_patterns) >= 1
        assert report.ai_analysis == "Significant cross-case connection found."

    def test_report_with_no_shared_entities(self, service, mock_neptune, mock_bedrock):
        mock_g = _setup_traversal(mock_neptune)

        entity_a = _make_entity_node("a1", "Pyramids", "location", CASE_A)
        entity_b = _make_entity_node("b1", "Stonehenge", "location", CASE_B)

        call_count = [0]
        entities_by_call = [[entity_a], [entity_b]]

        def toList_side_effect():
            idx = call_count[0]
            call_count[0] += 1
            return entities_by_call[idx] if idx < len(entities_by_call) else []

        chain = MagicMock()
        chain.toList = toList_side_effect
        mock_g.V.return_value.hasLabel.return_value.project.return_value \
            .by.return_value.by.return_value.by.return_value.by.return_value = chain

        _setup_bedrock_response(mock_bedrock, "No connections found.")

        report = service.generate_cross_reference_report([CASE_A, CASE_B])

        assert report.shared_entities == []
        assert report.parallel_patterns == []
        assert report.ai_analysis == "No connections found."

    def test_bedrock_failure_uses_fallback(self, service, mock_neptune, mock_bedrock):
        mock_g = _setup_traversal(mock_neptune)

        entity_a = _make_entity_node("a1", "Nazca Lines", "location", CASE_A)
        entity_b = _make_entity_node("b1", "Nazca Lines", "location", CASE_B)

        call_count = [0]
        entities_by_call = [[entity_a], [entity_b]]

        def toList_side_effect():
            idx = call_count[0]
            call_count[0] += 1
            return entities_by_call[idx] if idx < len(entities_by_call) else []

        chain = MagicMock()
        chain.toList = toList_side_effect
        mock_g.V.return_value.hasLabel.return_value.project.return_value \
            .by.return_value.by.return_value.by.return_value.by.return_value = chain

        mock_bedrock.invoke_model.side_effect = Exception("Bedrock timeout")

        report = service.generate_cross_reference_report([CASE_A, CASE_B])

        assert "1 shared entities" in report.ai_analysis
        assert CASE_A in report.ai_analysis

    def test_shared_entity_entries_have_similarity_score(self, service, mock_neptune, mock_bedrock):
        mock_g = _setup_traversal(mock_neptune)

        entity_a = _make_entity_node("a1", "Nazca Lines", "location", CASE_A)
        entity_b = _make_entity_node("b1", "Nazca Lines", "location", CASE_B)

        call_count = [0]
        entities_by_call = [[entity_a], [entity_b]]

        def toList_side_effect():
            idx = call_count[0]
            call_count[0] += 1
            return entities_by_call[idx] if idx < len(entities_by_call) else []

        chain = MagicMock()
        chain.toList = toList_side_effect
        mock_g.V.return_value.hasLabel.return_value.project.return_value \
            .by.return_value.by.return_value.by.return_value.by.return_value = chain

        _setup_bedrock_response(mock_bedrock)

        report = service.generate_cross_reference_report([CASE_A, CASE_B])

        for match in report.shared_entities:
            assert match.similarity_score >= 0.0
            assert match.similarity_score <= 1.0
            assert "entity_id" in match.entity_a
            assert "entity_id" in match.entity_b


# ---------------------------------------------------------------------------
# create_cross_case_graph
# ---------------------------------------------------------------------------


class TestCreateCrossCaseGraph:
    def test_creates_graph_and_returns_id(
        self, service, mock_neptune, mock_case_file_service,
    ):
        mock_g = _setup_traversal(mock_neptune)
        graph = _make_cross_case_graph()
        mock_case_file_service.create_cross_case_graph.return_value = graph

        match = CrossCaseMatch(
            entity_a={"entity_id": "a1", "name": "Nazca Lines", "type": "location", "case_id": CASE_A},
            entity_b={"entity_id": "b1", "name": "Nazca Lines", "type": "location", "case_id": CASE_B},
            similarity_score=1.0,
        )

        result = service.create_cross_case_graph("Test Graph", [CASE_A, CASE_B], [match])

        assert result == GRAPH_ID
        mock_case_file_service.create_cross_case_graph.assert_called_once_with(
            name="Test Graph", case_ids=[CASE_A, CASE_B],
        )

    def test_writes_cross_case_link_edges(
        self, service, mock_neptune, mock_case_file_service,
    ):
        mock_g = _setup_traversal(mock_neptune)
        graph = _make_cross_case_graph()
        mock_case_file_service.create_cross_case_graph.return_value = graph

        match = CrossCaseMatch(
            entity_a={"entity_id": "a1", "name": "Nazca Lines", "type": "location", "case_id": CASE_A},
            entity_b={"entity_id": "b1", "name": "Nazca Lines", "type": "location", "case_id": CASE_B},
            similarity_score=1.0,
        )

        service.create_cross_case_graph("Test Graph", [CASE_A, CASE_B], [match])

        # Verify addV was called (reference nodes created in cross-case subgraph).
        assert mock_g.addV.called

    def test_does_not_modify_original_subgraphs(
        self, service, mock_neptune, mock_case_file_service,
    ):
        mock_g = _setup_traversal(mock_neptune)
        graph = _make_cross_case_graph()
        mock_case_file_service.create_cross_case_graph.return_value = graph

        match = CrossCaseMatch(
            entity_a={"entity_id": "a1", "name": "Nazca Lines", "type": "location", "case_id": CASE_A},
            entity_b={"entity_id": "b1", "name": "Nazca Lines", "type": "location", "case_id": CASE_B},
            similarity_score=1.0,
        )

        service.create_cross_case_graph("Test Graph", [CASE_A, CASE_B], [match])

        # All addV calls should use the cross-case label, not original case labels.
        expected_label = cross_case_label(GRAPH_ID)
        for c in mock_g.addV.call_args_list:
            assert c[0][0] == expected_label

    def test_empty_matches_creates_graph_without_edges(
        self, service, mock_neptune, mock_case_file_service,
    ):
        mock_g = _setup_traversal(mock_neptune)
        graph = _make_cross_case_graph()
        mock_case_file_service.create_cross_case_graph.return_value = graph

        result = service.create_cross_case_graph("Test Graph", [CASE_A, CASE_B], [])

        assert result == GRAPH_ID
        mock_case_file_service.create_cross_case_graph.assert_called_once()
        # No addV calls since no matches.
        assert not mock_g.addV.called


# ---------------------------------------------------------------------------
# scan_for_overlaps
# ---------------------------------------------------------------------------


class TestScanForOverlaps:
    def test_returns_candidates_without_creating_links(
        self, service, mock_neptune, mock_aurora,
    ):
        mock_g = _setup_traversal(mock_neptune)

        # Aurora returns existing case IDs.
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [(CASE_B,)]
        mock_aurora.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_aurora.cursor.return_value.__exit__ = MagicMock(return_value=False)

        # Neptune: new case entities, then existing case entities.
        new_entity = _make_entity_node("a1", "Nazca Lines", "location", CASE_A)
        existing_entity = _make_entity_node("b1", "Nazca Lines", "location", CASE_B)

        call_count = [0]
        entities_by_call = [[new_entity], [existing_entity]]

        def toList_side_effect():
            idx = call_count[0]
            call_count[0] += 1
            return entities_by_call[idx] if idx < len(entities_by_call) else []

        chain = MagicMock()
        chain.toList = toList_side_effect
        mock_g.V.return_value.hasLabel.return_value.project.return_value \
            .by.return_value.by.return_value.by.return_value.by.return_value = chain

        candidates = service.scan_for_overlaps(CASE_A)

        assert len(candidates) == 1
        assert candidates[0].entity_a["case_id"] == CASE_A
        assert candidates[0].entity_b["case_id"] == CASE_B
        # Verify no addE was called (no links created).
        assert not mock_g.addE.called

    def test_returns_empty_when_no_existing_cases(
        self, service, mock_neptune, mock_aurora,
    ):
        mock_g = _setup_traversal(mock_neptune)

        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_aurora.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_aurora.cursor.return_value.__exit__ = MagicMock(return_value=False)

        candidates = service.scan_for_overlaps(CASE_A)

        assert candidates == []

    def test_returns_empty_when_no_overlapping_names(
        self, service, mock_neptune, mock_aurora,
    ):
        mock_g = _setup_traversal(mock_neptune)

        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [(CASE_B,)]
        mock_aurora.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_aurora.cursor.return_value.__exit__ = MagicMock(return_value=False)

        new_entity = _make_entity_node("a1", "Pyramids", "location", CASE_A)
        existing_entity = _make_entity_node("b1", "Stonehenge", "location", CASE_B)

        call_count = [0]
        entities_by_call = [[new_entity], [existing_entity]]

        def toList_side_effect():
            idx = call_count[0]
            call_count[0] += 1
            return entities_by_call[idx] if idx < len(entities_by_call) else []

        chain = MagicMock()
        chain.toList = toList_side_effect
        mock_g.V.return_value.hasLabel.return_value.project.return_value \
            .by.return_value.by.return_value.by.return_value.by.return_value = chain

        candidates = service.scan_for_overlaps(CASE_A)

        assert candidates == []

    def test_returns_empty_when_new_case_has_no_entities(
        self, service, mock_neptune, mock_aurora,
    ):
        mock_g = _setup_traversal(mock_neptune)

        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [(CASE_B,)]
        mock_aurora.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_aurora.cursor.return_value.__exit__ = MagicMock(return_value=False)

        call_count = [0]
        entities_by_call = [[], []]

        def toList_side_effect():
            idx = call_count[0]
            call_count[0] += 1
            return entities_by_call[idx] if idx < len(entities_by_call) else []

        chain = MagicMock()
        chain.toList = toList_side_effect
        mock_g.V.return_value.hasLabel.return_value.project.return_value \
            .by.return_value.by.return_value.by.return_value.by.return_value = chain

        candidates = service.scan_for_overlaps(CASE_A)

        assert candidates == []


# ---------------------------------------------------------------------------
# confirm_connection
# ---------------------------------------------------------------------------


class TestConfirmConnection:
    def test_creates_cross_case_link_edge(
        self, service, mock_neptune, mock_case_file_service,
    ):
        mock_g = _setup_traversal(mock_neptune)
        graph = _make_cross_case_graph()
        mock_case_file_service.get_cross_case_graph.return_value = graph

        match = CrossCaseMatch(
            entity_a={"entity_id": "a1", "name": "Nazca Lines", "type": "location", "case_id": CASE_A},
            entity_b={"entity_id": "b1", "name": "Nazca Lines", "type": "location", "case_id": CASE_B},
            similarity_score=1.0,
        )

        service.confirm_connection(match, GRAPH_ID)

        # Verify graph was looked up.
        mock_case_file_service.get_cross_case_graph.assert_called_once_with(GRAPH_ID)
        # Verify reference nodes were created in the cross-case subgraph.
        assert mock_g.addV.called
        expected_label = cross_case_label(GRAPH_ID)
        for c in mock_g.addV.call_args_list:
            assert c[0][0] == expected_label

    def test_uses_correct_graph_label(
        self, service, mock_neptune, mock_case_file_service,
    ):
        mock_g = _setup_traversal(mock_neptune)
        graph = _make_cross_case_graph()
        mock_case_file_service.get_cross_case_graph.return_value = graph

        match = CrossCaseMatch(
            entity_a={"entity_id": "a1", "name": "X", "type": "person", "case_id": CASE_A},
            entity_b={"entity_id": "b1", "name": "X", "type": "person", "case_id": CASE_B},
            similarity_score=0.95,
        )

        service.confirm_connection(match, GRAPH_ID)

        expected_label = cross_case_label(GRAPH_ID)
        # All addV calls should use the cross-case label.
        for c in mock_g.addV.call_args_list:
            assert c[0][0] == expected_label


# ---------------------------------------------------------------------------
# _build_parallel_patterns
# ---------------------------------------------------------------------------


class TestBuildParallelPatterns:
    def test_groups_by_entity_type(self, service):
        matches = [
            CrossCaseMatch(
                entity_a={"name": "Nazca Lines", "type": "location", "entity_id": "a1", "case_id": CASE_A},
                entity_b={"name": "Nazca Lines", "type": "location", "entity_id": "b1", "case_id": CASE_B},
                similarity_score=1.0,
            ),
            CrossCaseMatch(
                entity_a={"name": "Erich", "type": "person", "entity_id": "a2", "case_id": CASE_A},
                entity_b={"name": "Erich", "type": "person", "entity_id": "b2", "case_id": CASE_B},
                similarity_score=1.0,
            ),
        ]

        patterns = service._build_parallel_patterns(matches)

        assert len(patterns) == 2
        types = {p["entity_type"] for p in patterns}
        assert types == {"location", "person"}

    def test_empty_matches(self, service):
        patterns = service._build_parallel_patterns([])
        assert patterns == []
