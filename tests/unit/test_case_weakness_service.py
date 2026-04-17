"""Unit tests for CaseWeaknessService.

Covers:
- Conflicting statement detection with two contradictory documents for same witness
- Bedrock fallback skips AI-dependent checks
- Critical weakness includes remediation
- Brady material weakness contains "Brady v. Maryland" in legal_reasoning
- Suppression risk weakness contains "Mapp v. Ohio" in legal_reasoning
- Missing corroboration detection for single-source elements
"""

import json
from contextlib import contextmanager
from unittest.mock import MagicMock

import pytest

from src.models.prosecutor import (
    WeaknessSeverity,
    WeaknessType,
)
from src.services.case_weakness_service import CaseWeaknessService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FreshBytesIO:
    """Returns fresh bytes on each .read() call."""

    def __init__(self, data: bytes):
        self._data = data

    def read(self):
        return self._data


def _bedrock_response(payload: dict | list) -> dict:
    """Build a mock Bedrock invoke_model response."""
    body_text = json.dumps(payload)
    content = json.dumps({"content": [{"text": body_text}]})
    return {"body": _FreshBytesIO(content.encode())}


def _make_mock_db(
    witness_docs=None,
    element_assessments=None,
    case_documents=None,
):
    """Build a mock Aurora connection manager.

    Parameters
    ----------
    witness_docs : list[tuple]
        Rows for witness document query:
        (document_id, filename, doc_type, content_snippet, attributed_entity_id)
    element_assessments : list[tuple]
        Rows for element assessment query:
        (element_id, display_name, evidence_id, rating, element_order)
    case_documents : list[tuple]
        Rows for case document query:
        (document_id, filename, doc_type)
    """
    if witness_docs is None:
        witness_docs = []
    if element_assessments is None:
        element_assessments = []
    if case_documents is None:
        case_documents = []

    cursor = MagicMock()

    def _execute(sql, params=None):
        sql_lower = sql.strip().lower()
        if "attributed_entity_id" in sql_lower:
            cursor.fetchall.return_value = witness_docs
        elif "element_assessments" in sql_lower:
            cursor.fetchall.return_value = element_assessments
        elif "case_documents" in sql_lower:
            cursor.fetchall.return_value = case_documents
        else:
            cursor.fetchall.return_value = []

    cursor.execute = _execute

    db = MagicMock()

    @contextmanager
    def _cursor_ctx():
        yield cursor

    db.cursor = _cursor_ctx
    return db


def _make_mock_neptune(witness_relationships=None):
    """Build a mock Neptune connection manager."""
    cursor = MagicMock()
    cursor.fetchall.return_value = witness_relationships or []

    cm = MagicMock()

    @contextmanager
    def _cursor_ctx():
        yield cursor

    cm.cursor = _cursor_ctx
    return cm


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_neptune():
    return _make_mock_neptune()


# ---------------------------------------------------------------------------
# Tests: Conflicting statement detection
# ---------------------------------------------------------------------------


class TestConflictingStatements:
    """Detect conflicting statements from the same witness."""

    def test_two_contradictory_docs_for_same_witness(self, mock_neptune):
        """Two documents attributed to the same witness → weakness flagged."""
        witness_docs = [
            ("doc-1", "statement_jan.pdf", "document", "I was at home", "witness-A"),
            ("doc-2", "statement_feb.pdf", "document", "I was at the office", "witness-A"),
        ]
        db = _make_mock_db(witness_docs=witness_docs)

        svc = CaseWeaknessService(
            aurora_cm=db, neptune_cm=mock_neptune, bedrock_client=None
        )

        weaknesses = svc.detect_conflicting_statements("case-1")

        assert len(weaknesses) == 1
        w = weaknesses[0]
        assert w.weakness_type == WeaknessType.CONFLICTING_STATEMENTS
        assert "witness-A" in w.description
        assert "Crawford v. Washington" in w.legal_reasoning
        assert len(w.affected_evidence) == 2
        assert "doc-1" in w.affected_evidence
        assert "doc-2" in w.affected_evidence

    def test_single_doc_per_witness_no_weakness(self, mock_neptune):
        """One document per witness → no conflicting statement weakness."""
        witness_docs = [
            ("doc-1", "statement.pdf", "document", "Content", "witness-A"),
        ]
        db = _make_mock_db(witness_docs=witness_docs)

        svc = CaseWeaknessService(
            aurora_cm=db, neptune_cm=mock_neptune, bedrock_client=None
        )

        weaknesses = svc.detect_conflicting_statements("case-1")

        assert len(weaknesses) == 0

    def test_multiple_contradictions_escalate_to_critical(self, mock_neptune):
        """Three docs for same witness → 3 contradiction pairs → critical severity."""
        witness_docs = [
            ("doc-1", "stmt_1.pdf", "document", "Version A", "witness-A"),
            ("doc-2", "stmt_2.pdf", "document", "Version B", "witness-A"),
            ("doc-3", "stmt_3.pdf", "document", "Version C", "witness-A"),
        ]
        db = _make_mock_db(witness_docs=witness_docs)

        svc = CaseWeaknessService(
            aurora_cm=db, neptune_cm=mock_neptune, bedrock_client=None
        )

        weaknesses = svc.detect_conflicting_statements("case-1")

        assert len(weaknesses) == 1
        w = weaknesses[0]
        assert w.severity == WeaknessSeverity.CRITICAL
        assert w.remediation is not None
        assert len(w.remediation) > 0


# ---------------------------------------------------------------------------
# Tests: Bedrock fallback
# ---------------------------------------------------------------------------


class TestBedrockFallback:
    """When Bedrock is unavailable, skip AI-dependent checks."""

    def test_analyze_weaknesses_skips_suppression_and_brady(self, mock_neptune):
        """With bedrock_client=None, only deterministic checks run."""
        witness_docs = [
            ("doc-1", "stmt_1.pdf", "document", "A", "witness-A"),
            ("doc-2", "stmt_2.pdf", "document", "B", "witness-A"),
        ]
        db = _make_mock_db(witness_docs=witness_docs)

        svc = CaseWeaknessService(
            aurora_cm=db, neptune_cm=mock_neptune, bedrock_client=None
        )

        weaknesses = svc.analyze_weaknesses("case-1", statute_id="stat-1")

        # Should have conflicting_statements but no suppression_risk or brady_material
        types = {w.weakness_type for w in weaknesses}
        assert WeaknessType.CONFLICTING_STATEMENTS in types
        assert WeaknessType.SUPPRESSION_RISK not in types
        assert WeaknessType.BRADY_MATERIAL not in types

    def test_detect_suppression_risks_returns_empty_without_bedrock(self, mock_neptune):
        db = _make_mock_db()
        svc = CaseWeaknessService(
            aurora_cm=db, neptune_cm=mock_neptune, bedrock_client=None
        )

        result = svc.detect_suppression_risks("case-1")

        assert result == []

    def test_detect_brady_material_returns_empty_without_bedrock(self, mock_neptune):
        db = _make_mock_db()
        svc = CaseWeaknessService(
            aurora_cm=db, neptune_cm=mock_neptune, bedrock_client=None
        )

        result = svc.detect_brady_material("case-1")

        assert result == []


# ---------------------------------------------------------------------------
# Tests: Critical weakness includes remediation
# ---------------------------------------------------------------------------


class TestCriticalRemediation:
    """Critical weaknesses must include remediation text."""

    def test_critical_conflicting_statements_has_remediation(self, mock_neptune):
        """3+ docs for same witness → critical → remediation present."""
        witness_docs = [
            ("doc-1", "stmt_1.pdf", "document", "A", "witness-A"),
            ("doc-2", "stmt_2.pdf", "document", "B", "witness-A"),
            ("doc-3", "stmt_3.pdf", "document", "C", "witness-A"),
        ]
        db = _make_mock_db(witness_docs=witness_docs)

        svc = CaseWeaknessService(
            aurora_cm=db, neptune_cm=mock_neptune, bedrock_client=None
        )

        weaknesses = svc.detect_conflicting_statements("case-1")

        critical = [w for w in weaknesses if w.severity == WeaknessSeverity.CRITICAL]
        assert len(critical) >= 1
        for w in critical:
            assert w.remediation is not None
            assert len(w.remediation) > 0

    def test_critical_brady_material_has_remediation(self, mock_neptune):
        """Critical Brady material weakness includes remediation."""
        brady_results = [
            {
                "document_id": "doc-1",
                "description": "Exculpatory witness statement found",
                "severity": "critical",
                "affected_elements": ["elem-1"],
            }
        ]

        bedrock = MagicMock()
        bedrock.invoke_model.return_value = _bedrock_response(brady_results)

        case_docs = [("doc-1", "witness_statement.pdf", "document")]
        db = _make_mock_db(case_documents=case_docs)

        svc = CaseWeaknessService(
            aurora_cm=db, neptune_cm=mock_neptune, bedrock_client=bedrock
        )

        weaknesses = svc.detect_brady_material("case-1")

        assert len(weaknesses) == 1
        w = weaknesses[0]
        assert w.severity == WeaknessSeverity.CRITICAL
        assert w.remediation is not None
        assert "disclose" in w.remediation.lower()

    def test_critical_suppression_risk_has_remediation(self, mock_neptune):
        """Critical suppression risk weakness includes remediation."""
        suppression_results = [
            {
                "document_id": "doc-1",
                "description": "Warrantless search of vehicle",
                "severity": "critical",
                "affected_elements": [],
            }
        ]

        bedrock = MagicMock()
        bedrock.invoke_model.return_value = _bedrock_response(suppression_results)

        case_docs = [("doc-1", "search_report.pdf", "document")]
        db = _make_mock_db(case_documents=case_docs)

        svc = CaseWeaknessService(
            aurora_cm=db, neptune_cm=mock_neptune, bedrock_client=bedrock
        )

        weaknesses = svc.detect_suppression_risks("case-1")

        assert len(weaknesses) == 1
        w = weaknesses[0]
        assert w.severity == WeaknessSeverity.CRITICAL
        assert w.remediation is not None
        assert len(w.remediation) > 0


# ---------------------------------------------------------------------------
# Tests: Brady material legal reasoning
# ---------------------------------------------------------------------------


class TestBradyMaterialCitation:
    """Brady material weakness must cite Brady v. Maryland."""

    def test_brady_weakness_cites_brady_v_maryland(self, mock_neptune):
        brady_results = [
            {
                "document_id": "doc-1",
                "description": "Exculpatory evidence found",
                "severity": "critical",
                "affected_elements": [],
            }
        ]

        bedrock = MagicMock()
        bedrock.invoke_model.return_value = _bedrock_response(brady_results)

        case_docs = [("doc-1", "evidence.pdf", "document")]
        db = _make_mock_db(case_documents=case_docs)

        svc = CaseWeaknessService(
            aurora_cm=db, neptune_cm=mock_neptune, bedrock_client=bedrock
        )

        weaknesses = svc.detect_brady_material("case-1")

        assert len(weaknesses) == 1
        w = weaknesses[0]
        assert "Brady v. Maryland" in w.legal_reasoning

    def test_brady_weakness_cites_giglio(self, mock_neptune):
        """Brady weakness should also cite Giglio v. United States."""
        brady_results = [
            {
                "document_id": "doc-1",
                "description": "Impeachment evidence",
                "severity": "warning",
                "affected_elements": [],
            }
        ]

        bedrock = MagicMock()
        bedrock.invoke_model.return_value = _bedrock_response(brady_results)

        case_docs = [("doc-1", "evidence.pdf", "document")]
        db = _make_mock_db(case_documents=case_docs)

        svc = CaseWeaknessService(
            aurora_cm=db, neptune_cm=mock_neptune, bedrock_client=bedrock
        )

        weaknesses = svc.detect_brady_material("case-1")

        assert len(weaknesses) == 1
        w = weaknesses[0]
        assert "Giglio v. United States" in w.legal_reasoning


# ---------------------------------------------------------------------------
# Tests: Suppression risk legal reasoning
# ---------------------------------------------------------------------------


class TestSuppressionRiskCitation:
    """Suppression risk weakness must cite Mapp v. Ohio."""

    def test_suppression_weakness_cites_mapp_v_ohio(self, mock_neptune):
        suppression_results = [
            {
                "document_id": "doc-1",
                "description": "Warrantless search",
                "severity": "warning",
                "affected_elements": [],
            }
        ]

        bedrock = MagicMock()
        bedrock.invoke_model.return_value = _bedrock_response(suppression_results)

        case_docs = [("doc-1", "search_report.pdf", "document")]
        db = _make_mock_db(case_documents=case_docs)

        svc = CaseWeaknessService(
            aurora_cm=db, neptune_cm=mock_neptune, bedrock_client=bedrock
        )

        weaknesses = svc.detect_suppression_risks("case-1")

        assert len(weaknesses) == 1
        w = weaknesses[0]
        assert "Mapp v. Ohio" in w.legal_reasoning


# ---------------------------------------------------------------------------
# Tests: Missing corroboration
# ---------------------------------------------------------------------------


class TestMissingCorroboration:
    """Detect elements with only one evidence source."""

    def test_single_source_element_flagged(self, mock_neptune):
        """Element with one green/yellow source → missing_corroboration."""
        element_assessments = [
            ("elem-1", "Interstate Commerce", "doc-1", "green", 1),
        ]
        db = _make_mock_db(element_assessments=element_assessments)

        svc = CaseWeaknessService(
            aurora_cm=db, neptune_cm=mock_neptune, bedrock_client=None
        )

        weaknesses = svc.detect_missing_corroboration("case-1", "stat-1")

        assert len(weaknesses) == 1
        w = weaknesses[0]
        assert w.weakness_type == WeaknessType.MISSING_CORROBORATION
        assert "elem-1" in w.affected_elements
        assert "doc-1" in w.affected_evidence
        assert "Interstate Commerce" in w.description

    def test_multi_source_element_not_flagged(self, mock_neptune):
        """Element with two green/yellow sources → no weakness."""
        element_assessments = [
            ("elem-1", "Interstate Commerce", "doc-1", "green", 1),
            ("elem-1", "Interstate Commerce", "doc-2", "yellow", 1),
        ]
        db = _make_mock_db(element_assessments=element_assessments)

        svc = CaseWeaknessService(
            aurora_cm=db, neptune_cm=mock_neptune, bedrock_client=None
        )

        weaknesses = svc.detect_missing_corroboration("case-1", "stat-1")

        assert len(weaknesses) == 0

    def test_no_assessments_returns_empty(self, mock_neptune):
        """No element assessments → no weaknesses."""
        db = _make_mock_db(element_assessments=[])

        svc = CaseWeaknessService(
            aurora_cm=db, neptune_cm=mock_neptune, bedrock_client=None
        )

        weaknesses = svc.detect_missing_corroboration("case-1", "stat-1")

        assert len(weaknesses) == 0
