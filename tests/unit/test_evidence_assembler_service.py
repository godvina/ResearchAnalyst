"""Unit tests for EvidenceAssemblerService."""

import json
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest

from services.evidence_assembler_service import EvidenceAssemblerService


# ---------------------------------------------------------------------------
# Helpers — mock Aurora connection manager
# ---------------------------------------------------------------------------

class MockCursor:
    """Simulates a psycopg2 cursor with configurable query results."""

    def __init__(self, results_map=None):
        self._results_map = results_map or {}
        self._current_results = []

    def execute(self, query, params=None):
        # Match on query substring to return appropriate results
        for key, rows in self._results_map.items():
            if key in query:
                self._current_results = list(rows)
                return
        self._current_results = []

    def fetchall(self):
        return self._current_results

    def fetchone(self):
        return self._current_results[0] if self._current_results else None


class MockAuroraCM:
    """Context-manager-based Aurora connection mock."""

    def __init__(self, cursor):
        self._cursor = cursor

    @contextmanager
    def cursor(self):
        yield self._cursor


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

DOC_ROWS = [
    ("doc-1", "report_alpha.pdf", "John Smith met with Jane Doe on 2023-05-15 to discuss the contract.", "2023-05-15"),
    ("doc-2", "memo_beta.txt", "Jane Doe sent a memo regarding the financial audit in 2022.", "2022-11-01"),
    ("doc-3", "notes_gamma.txt", "John Smith was mentioned in passing during the 2021-03-10 hearing.", "2021-03-10"),
]

ENTITY_ROWS = [
    ("John Smith", "person"),
    ("Jane Doe", "person"),
]


@pytest.fixture
def aurora_cm():
    """Aurora connection manager with sample document and entity data."""
    cursor = MockCursor({
        "FROM documents WHERE case_file_id": DOC_ROWS,
        "FROM entities": ENTITY_ROWS,
        "SELECT created_at FROM documents": [("2023-01-01",)],
    })
    return MockAuroraCM(cursor)


@pytest.fixture
def service(aurora_cm):
    """EvidenceAssemblerService with no Neptune endpoint."""
    return EvidenceAssemblerService(
        aurora_cm=aurora_cm,
        neptune_endpoint="",
        neptune_port="8182",
    )


# ---------------------------------------------------------------------------
# Tests — assemble_evidence
# ---------------------------------------------------------------------------

class TestAssembleEvidence:
    def test_returns_evidence_thread(self, service):
        result = service.assemble_evidence(
            case_id="case-1",
            lead_id="lead-1",
            entity_names=["John Smith", "Jane Doe"],
            lead_type="entity_cluster",
            narrative="John Smith and Jane Doe appear together in multiple documents.",
        )
        assert result is not None
        assert hasattr(result, "documents")
        assert hasattr(result, "entities")
        assert hasattr(result, "timeline")
        assert hasattr(result, "relationship_edges")

    def test_documents_capped_at_20(self, aurora_cm):
        """Even with 50 rows returned, documents should be capped at 20."""
        many_rows = [
            (f"doc-{i}", f"file_{i}.txt", f"John Smith content {i}", "2023-01-01")
            for i in range(50)
        ]
        cursor = MockCursor({
            "FROM documents WHERE case_file_id": many_rows,
            "FROM entities": [],
        })
        cm = MockAuroraCM(cursor)
        svc = EvidenceAssemblerService(aurora_cm=cm)
        result = svc.assemble_evidence("c1", "l1", ["John Smith"], "doc", "narrative")
        assert len(result.documents) <= 20

    def test_entities_capped_at_30(self, aurora_cm):
        """Entities should be capped at 30."""
        # Create docs that mention 35 different entity names
        entity_names = [f"Entity{i}" for i in range(35)]
        content = " ".join(entity_names)
        rows = [("doc-1", "file.txt", content, "2023-01-01")]
        cursor = MockCursor({
            "FROM documents WHERE case_file_id": rows,
            "FROM entities": [],
        })
        cm = MockAuroraCM(cursor)
        svc = EvidenceAssemblerService(aurora_cm=cm)
        result = svc.assemble_evidence("c1", "l1", entity_names, "doc", "narrative")
        assert len(result.entities) <= 30

    def test_documents_sorted_by_relevance_desc(self, service):
        result = service.assemble_evidence(
            "case-1", "lead-1", ["John Smith", "Jane Doe"], "cluster", "narrative",
        )
        scores = [d.relevance_score for d in result.documents]
        assert scores == sorted(scores, reverse=True)

    def test_timeline_sorted_ascending(self, service):
        result = service.assemble_evidence(
            "case-1", "lead-1", ["John Smith", "Jane Doe"], "cluster", "narrative",
        )
        dates = [e.date for e in result.timeline]
        assert dates == sorted(dates)

    def test_empty_entity_names_returns_empty_thread(self, service):
        result = service.assemble_evidence("c1", "l1", [], "doc", "narrative")
        assert result.documents == []
        assert result.entities == []
        assert result.timeline == []

    def test_no_neptune_returns_empty_edges(self, service):
        result = service.assemble_evidence(
            "case-1", "lead-1", ["John Smith", "Jane Doe"], "cluster", "narrative",
        )
        assert result.relationship_edges == []


# ---------------------------------------------------------------------------
# Tests — key quote extraction
# ---------------------------------------------------------------------------

class TestExtractKeyQuotes:
    def test_quotes_contain_entity_name(self):
        content = "John Smith attended the meeting. The weather was nice. Jane Doe also came."
        quotes = EvidenceAssemblerService._extract_key_quotes(
            content, ["John Smith", "Jane Doe"],
        )
        assert len(quotes) >= 1
        assert any("John Smith" in q for q in quotes)

    def test_quotes_truncated_to_200_chars(self):
        long_sentence = "John Smith " + "x" * 300
        content = long_sentence + ". End."
        quotes = EvidenceAssemblerService._extract_key_quotes(content, ["John Smith"])
        for q in quotes:
            assert len(q) <= 200

    def test_empty_content_returns_empty(self):
        assert EvidenceAssemblerService._extract_key_quotes("", ["John"]) == []

    def test_no_matching_entity_returns_empty(self):
        content = "The quick brown fox jumps over the lazy dog."
        assert EvidenceAssemblerService._extract_key_quotes(content, ["Nonexistent"]) == []


# ---------------------------------------------------------------------------
# Tests — relevance scoring
# ---------------------------------------------------------------------------

class TestScoreRelevance:
    def test_all_entities_present(self):
        content = "John Smith and Jane Doe met."
        score = EvidenceAssemblerService._score_relevance(content, ["John Smith", "Jane Doe"])
        assert score == 1.0

    def test_partial_match(self):
        content = "John Smith was there."
        score = EvidenceAssemblerService._score_relevance(content, ["John Smith", "Jane Doe"])
        assert score == 0.5

    def test_no_match(self):
        content = "Nothing relevant here."
        score = EvidenceAssemblerService._score_relevance(content, ["John Smith"])
        assert score == 0.0

    def test_empty_inputs(self):
        assert EvidenceAssemblerService._score_relevance("", ["John"]) == 0.0
        assert EvidenceAssemblerService._score_relevance("content", []) == 0.0
