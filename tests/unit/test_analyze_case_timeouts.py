"""Tests for per-service timeout protection in analyze_case().

Validates Requirements 1.3, 2.4, 3.6 from the case-file-evidence-starvation bugfix.
Task 4.3: Add LIMIT/sampling to pattern_discovery and hypothesis_generation queries.
"""

import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from unittest.mock import MagicMock, patch

import pytest

from src.services.investigator_ai_engine import (
    InvestigatorAIEngine,
    LARGE_CASE_THRESHOLD,
    SERVICE_CALL_TIMEOUT,
)

# Use a dict for briefing since CaseAnalysisResult uses Pydantic and the
# CaseBriefing class identity differs between src.models and models import paths.
_EMPTY_BRIEFING = {"narrative": "", "key_findings": []}


@pytest.fixture
def mock_cursor():
    cursor = MagicMock()
    cursor.__enter__ = MagicMock(return_value=cursor)
    cursor.__exit__ = MagicMock(return_value=False)
    return cursor


@pytest.fixture
def aurora_cm(mock_cursor):
    cm = MagicMock()
    cm.cursor.return_value = mock_cursor
    return cm


def _make_engine(aurora_cm, pattern_svc=None, hypothesis_svc=None):
    engine = InvestigatorAIEngine(aurora_cm=aurora_cm, bedrock_client=MagicMock())
    engine._pattern_svc = pattern_svc
    engine._hypothesis_svc = hypothesis_svc
    engine._decision_svc = MagicMock()
    engine._decision_svc.create_decision.return_value = MagicMock(
        decision_id="d1", state=MagicMock(value="AI_Proposed")
    )
    return engine


def _common_patches(engine, briefing=None):
    """Return a list of common patches for analyze_case tests."""
    return {
        '_generate_leads': [],
        'generate_subpoena_recommendations': [],
        '_generate_briefing': briefing or _EMPTY_BRIEFING,
        '_cache_analysis': None,
        '_store_leads': None,
    }


# ── Small case: no timeout wrapper applied ─────────────────────────

def test_small_case_calls_services_directly(aurora_cm, mock_cursor):
    """For cases below LARGE_CASE_THRESHOLD, services are called without timeout."""
    mock_cursor.fetchone.return_value = None
    small_stats = {"doc_count": 500, "entity_count": 50, "relationship_count": 10}

    pattern_svc = MagicMock()
    pattern_report = MagicMock()
    pattern_report.patterns = [{"name": "p1"}]
    pattern_svc.generate_pattern_report.return_value = pattern_report

    hypothesis_svc = MagicMock()
    hypothesis_svc.generate_hypotheses.return_value = []

    engine = _make_engine(aurora_cm, pattern_svc=pattern_svc, hypothesis_svc=hypothesis_svc)

    with patch.object(engine, '_get_case_stats', return_value=small_stats), \
         patch.object(engine, '_generate_leads', return_value=[]), \
         patch.object(engine, 'generate_subpoena_recommendations', return_value=[]), \
         patch.object(engine, '_generate_briefing', return_value=_EMPTY_BRIEFING), \
         patch.object(engine, '_cache_analysis'), \
         patch.object(engine, '_store_leads'):
        result = engine.analyze_case("case-small")

    assert result.status == "completed"
    pattern_svc.generate_pattern_report.assert_called_once_with("case-small")
    hypothesis_svc.generate_hypotheses.assert_called_once()


# ── Large case: timeout on pattern_svc ──
# Instead of actually sleeping, we mock ThreadPoolExecutor to simulate timeout.

def test_large_case_pattern_timeout_continues_with_empty(aurora_cm, mock_cursor):
    """When pattern_svc times out on a large case, analysis continues with empty patterns."""
    mock_cursor.fetchone.return_value = None
    large_stats = {"doc_count": 50_000, "entity_count": 5000, "relationship_count": 1000}

    pattern_svc = MagicMock()
    # Pattern svc will be called via ThreadPoolExecutor — we simulate timeout
    # by making the future raise FuturesTimeoutError
    mock_future = MagicMock()
    mock_future.result.side_effect = FuturesTimeoutError()

    mock_executor = MagicMock()
    mock_executor.__enter__ = MagicMock(return_value=mock_executor)
    mock_executor.__exit__ = MagicMock(return_value=False)
    mock_executor.submit.return_value = mock_future

    engine = _make_engine(aurora_cm, pattern_svc=pattern_svc)

    with patch.object(engine, '_get_case_stats', return_value=large_stats), \
         patch.object(engine, '_generate_leads', return_value=[]), \
         patch.object(engine, 'generate_subpoena_recommendations', return_value=[]), \
         patch.object(engine, '_generate_briefing', return_value=_EMPTY_BRIEFING), \
         patch.object(engine, '_cache_analysis'), \
         patch.object(engine, '_store_leads'), \
         patch('src.services.investigator_ai_engine.ThreadPoolExecutor', return_value=mock_executor):
        result = engine.analyze_case("case-large")

    assert result.status == "completed"
    # Pattern timed out, hypothesis also uses the mocked executor (also times out)
    assert result.hypotheses == []


# ── Large case: timeout on hypothesis_svc ──

def test_large_case_hypothesis_timeout_continues_with_empty(aurora_cm, mock_cursor):
    """When hypothesis_svc times out on a large case, analysis continues with empty hypotheses."""
    mock_cursor.fetchone.return_value = None
    large_stats = {"doc_count": 50_000, "entity_count": 5000, "relationship_count": 1000}

    # Pattern succeeds, hypothesis times out
    call_count = [0]

    def make_future(*args, **kwargs):
        call_count[0] += 1
        f = MagicMock()
        if call_count[0] == 1:
            # First call: pattern_svc succeeds
            report = MagicMock()
            report.patterns = []
            f.result.return_value = report
        elif call_count[0] == 2:
            # Second call: hypothesis_svc times out
            f.result.side_effect = FuturesTimeoutError()
        else:
            # Third call: _generate_leads succeeds
            f.result.return_value = []
        return f

    mock_executor = MagicMock()
    mock_executor.__enter__ = MagicMock(return_value=mock_executor)
    mock_executor.__exit__ = MagicMock(return_value=False)
    mock_executor.submit.side_effect = make_future

    pattern_svc = MagicMock()
    hypothesis_svc = MagicMock()

    engine = _make_engine(aurora_cm, pattern_svc=pattern_svc, hypothesis_svc=hypothesis_svc)

    with patch.object(engine, '_get_case_stats', return_value=large_stats), \
         patch.object(engine, 'generate_subpoena_recommendations', return_value=[]), \
         patch.object(engine, '_generate_briefing', return_value=_EMPTY_BRIEFING), \
         patch.object(engine, '_cache_analysis'), \
         patch.object(engine, '_store_leads'), \
         patch('src.services.investigator_ai_engine.ThreadPoolExecutor', return_value=mock_executor):
        result = engine.analyze_case("case-large")

    assert result.status == "completed"
    assert result.hypotheses == []


# ── Large case: _generate_leads timeout ──

def test_large_case_leads_timeout_continues_with_empty(aurora_cm, mock_cursor):
    """When _generate_leads times out on a large case, analysis continues with empty leads."""
    mock_cursor.fetchone.return_value = None
    large_stats = {"doc_count": 50_000, "entity_count": 5000, "relationship_count": 1000}

    # No pattern_svc or hypothesis_svc, so the only executor call is _generate_leads
    mock_future = MagicMock()
    mock_future.result.side_effect = FuturesTimeoutError()

    mock_executor = MagicMock()
    mock_executor.__enter__ = MagicMock(return_value=mock_executor)
    mock_executor.__exit__ = MagicMock(return_value=False)
    mock_executor.submit.return_value = mock_future

    engine = _make_engine(aurora_cm)  # no pattern_svc or hypothesis_svc

    with patch.object(engine, '_get_case_stats', return_value=large_stats), \
         patch.object(engine, 'generate_subpoena_recommendations', return_value=[]), \
         patch.object(engine, '_generate_briefing', return_value=_EMPTY_BRIEFING), \
         patch.object(engine, '_cache_analysis'), \
         patch.object(engine, '_store_leads'), \
         patch('src.services.investigator_ai_engine.ThreadPoolExecutor', return_value=mock_executor):
        result = engine.analyze_case("case-large")

    assert result.status == "completed"
    assert result.leads == []


# ── Large case: services succeed within timeout ──

def test_large_case_services_succeed_within_timeout(aurora_cm, mock_cursor):
    """When services complete within timeout on a large case, results are used normally."""
    mock_cursor.fetchone.return_value = None
    large_stats = {"doc_count": 50_000, "entity_count": 5000, "relationship_count": 1000}

    pattern_svc = MagicMock()
    pattern_report = MagicMock()
    pattern_report.patterns = [{"name": "p1"}, {"name": "p2"}]
    pattern_svc.generate_pattern_report.return_value = pattern_report

    hypothesis_svc = MagicMock()
    hypothesis_svc.generate_hypotheses.return_value = [
        {"hypothesis_text": "Test hypothesis", "confidence": "high",
         "supporting_evidence": [], "recommended_actions": []}
    ]

    engine = _make_engine(aurora_cm, pattern_svc=pattern_svc, hypothesis_svc=hypothesis_svc)

    with patch.object(engine, '_get_case_stats', return_value=large_stats), \
         patch.object(engine, '_generate_leads', return_value=[]), \
         patch.object(engine, 'generate_subpoena_recommendations', return_value=[]), \
         patch.object(engine, '_generate_briefing', return_value=_EMPTY_BRIEFING), \
         patch.object(engine, '_cache_analysis'), \
         patch.object(engine, '_store_leads'):
        result = engine.analyze_case("case-large")

    assert result.status == "completed"
    assert len(result.hypotheses) == 1
    pattern_svc.generate_pattern_report.assert_called_once_with("case-large")


# ── Constants are correctly defined ────────────────────────────────

def test_constants_defined():
    """Verify the timeout constants are defined with sensible values."""
    assert LARGE_CASE_THRESHOLD == 10_000
    assert SERVICE_CALL_TIMEOUT == 60
