"""Unit tests for DecisionWorkflowService.

Covers the three-state human-in-the-loop decision workflow:
create (AI_Proposed), confirm (Human_Confirmed), override (Human_Overridden),
conflict detection, audit trail, and filtered listing.
"""

from contextlib import contextmanager
from unittest.mock import MagicMock, call

import pytest

from src.models.prosecutor import (
    ConfidenceLevel,
    DecisionState,
)
from src.services.decision_workflow_service import (
    ConflictError,
    DecisionWorkflowService,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_decision_row(
    decision_id="dec-001",
    case_id="case-001",
    decision_type="statute_recommendation",
    state="ai_proposed",
    recommendation_text="Recommend 18 U.S.C. § 1591",
    legal_reasoning="Strong evidence of trafficking",
    confidence="high",
    source_service="element_assessment",
    related_entity_id=None,
    related_entity_type=None,
    confirmed_at=None,
    confirmed_by=None,
    overridden_at=None,
    overridden_by=None,
    override_rationale=None,
    created_at="2024-01-01T00:00:00+00:00",
    updated_at="2024-01-01T00:00:00+00:00",
):
    """Build a fake ai_decisions row tuple matching SELECT column order."""
    return (
        decision_id, case_id, decision_type, state,
        recommendation_text, legal_reasoning, confidence,
        source_service, related_entity_id, related_entity_type,
        confirmed_at, confirmed_by, overridden_at, overridden_by,
        override_rationale, created_at, updated_at,
    )


def _make_audit_row(
    audit_id="aud-001",
    decision_id="dec-001",
    previous_state=None,
    new_state="ai_proposed",
    actor="system",
    rationale="Recommend 18 U.S.C. § 1591",
    created_at="2024-01-01T00:00:00+00:00",
):
    return (audit_id, decision_id, previous_state, new_state, actor, rationale, created_at)


@pytest.fixture()
def mock_cursor():
    cursor = MagicMock()
    cursor.fetchone.return_value = _make_decision_row()
    cursor.fetchall.return_value = [_make_decision_row()]
    return cursor


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
    return DecisionWorkflowService(aurora_cm=mock_db)


# ---------------------------------------------------------------------------
# Tests: create_decision
# ---------------------------------------------------------------------------

class TestCreateDecision:
    def test_returns_ai_proposed_with_correct_fields(self, service, mock_cursor):
        result = service.create_decision(
            case_id="case-001",
            decision_type="statute_recommendation",
            recommendation_text="Recommend § 1591",
            legal_reasoning="Strong trafficking evidence",
            confidence="high",
            source_service="element_assessment",
        )

        assert result.state == DecisionState.AI_PROPOSED
        assert result.case_id == "case-001"
        assert result.decision_type == "statute_recommendation"
        assert result.recommendation_text == "Recommend § 1591"
        assert result.legal_reasoning == "Strong trafficking evidence"
        assert result.confidence == ConfidenceLevel.HIGH
        assert result.source_service == "element_assessment"
        assert result.decision_id  # non-empty UUID
        assert result.created_at
        assert result.updated_at

    def test_inserts_decision_and_audit_log(self, service, mock_cursor):
        service.create_decision(
            case_id="case-001",
            decision_type="element_rating",
            recommendation_text="Rate element green",
            legal_reasoning="Direct evidence",
            confidence="medium",
            source_service="element_assessment",
        )

        # Two INSERT calls: one for ai_decisions, one for audit log
        assert mock_cursor.execute.call_count == 2
        first_sql = mock_cursor.execute.call_args_list[0][0][0]
        second_sql = mock_cursor.execute.call_args_list[1][0][0]
        assert "INSERT INTO ai_decisions" in first_sql
        assert "INSERT INTO ai_decision_audit_log" in second_sql

    def test_audit_entry_actor_is_system(self, service, mock_cursor):
        service.create_decision(
            case_id="case-001",
            decision_type="statute_recommendation",
            recommendation_text="Test",
            legal_reasoning="Test reasoning",
            confidence="low",
            source_service="test_service",
        )

        audit_params = mock_cursor.execute.call_args_list[1][0][1]
        # actor is at index 4 in the params tuple
        assert audit_params[4] == "system"


# ---------------------------------------------------------------------------
# Tests: confirm_decision
# ---------------------------------------------------------------------------

class TestConfirmDecision:
    def test_transitions_to_human_confirmed(self, service, mock_cursor):
        # get_decision returns ai_proposed row
        mock_cursor.fetchone.return_value = _make_decision_row(state="ai_proposed")

        result = service.confirm_decision("dec-001", "attorney-jane")

        assert result.state == DecisionState.HUMAN_CONFIRMED
        assert result.confirmed_by == "attorney-jane"
        assert result.confirmed_at is not None

    def test_records_confirmation_timestamp(self, service, mock_cursor):
        mock_cursor.fetchone.return_value = _make_decision_row(state="ai_proposed")

        result = service.confirm_decision("dec-001", "attorney-jane")

        assert result.confirmed_at is not None
        assert result.updated_at is not None

    def test_already_confirmed_raises_conflict(self, service, mock_cursor):
        mock_cursor.fetchone.return_value = _make_decision_row(
            state="human_confirmed",
            confirmed_at="2024-01-02T00:00:00+00:00",
            confirmed_by="attorney-bob",
        )

        with pytest.raises(ConflictError, match="already human_confirmed"):
            service.confirm_decision("dec-001", "attorney-jane")

    def test_already_overridden_raises_conflict_on_confirm(self, service, mock_cursor):
        mock_cursor.fetchone.return_value = _make_decision_row(
            state="human_overridden",
            overridden_at="2024-01-02T00:00:00+00:00",
            overridden_by="attorney-bob",
            override_rationale="Disagree with AI",
        )

        with pytest.raises(ConflictError, match="already human_overridden"):
            service.confirm_decision("dec-001", "attorney-jane")

    def test_inserts_audit_log_entry(self, service, mock_cursor):
        mock_cursor.fetchone.return_value = _make_decision_row(state="ai_proposed")

        service.confirm_decision("dec-001", "attorney-jane")

        # get_decision SELECT + UPDATE + audit INSERT = 3 calls
        assert mock_cursor.execute.call_count == 3
        audit_sql = mock_cursor.execute.call_args_list[2][0][0]
        assert "INSERT INTO ai_decision_audit_log" in audit_sql
        audit_params = mock_cursor.execute.call_args_list[2][0][1]
        assert audit_params[3] == "human_confirmed"  # new_state
        assert audit_params[4] == "attorney-jane"  # actor


# ---------------------------------------------------------------------------
# Tests: override_decision
# ---------------------------------------------------------------------------

class TestOverrideDecision:
    def test_requires_non_empty_rationale(self, service):
        with pytest.raises(ValueError, match="override_rationale must not be empty"):
            service.override_decision("dec-001", "attorney-jane", "")

    def test_requires_non_whitespace_rationale(self, service):
        with pytest.raises(ValueError, match="override_rationale must not be empty"):
            service.override_decision("dec-001", "attorney-jane", "   ")

    def test_transitions_to_human_overridden(self, service, mock_cursor):
        mock_cursor.fetchone.return_value = _make_decision_row(state="ai_proposed")

        result = service.override_decision(
            "dec-001", "attorney-jane", "Insufficient evidence for this charge"
        )

        assert result.state == DecisionState.HUMAN_OVERRIDDEN
        assert result.overridden_by == "attorney-jane"
        assert result.overridden_at is not None
        assert result.override_rationale == "Insufficient evidence for this charge"

    def test_already_confirmed_raises_conflict_on_override(self, service, mock_cursor):
        mock_cursor.fetchone.return_value = _make_decision_row(
            state="human_confirmed",
            confirmed_at="2024-01-02T00:00:00+00:00",
            confirmed_by="attorney-bob",
        )

        with pytest.raises(ConflictError, match="already human_confirmed"):
            service.override_decision("dec-001", "attorney-jane", "My rationale")

    def test_already_overridden_raises_conflict_on_re_override(self, service, mock_cursor):
        mock_cursor.fetchone.return_value = _make_decision_row(
            state="human_overridden",
            overridden_at="2024-01-02T00:00:00+00:00",
            overridden_by="attorney-bob",
            override_rationale="Previous override",
        )

        with pytest.raises(ConflictError, match="already human_overridden"):
            service.override_decision("dec-001", "attorney-jane", "New rationale")

    def test_inserts_audit_log_with_rationale(self, service, mock_cursor):
        mock_cursor.fetchone.return_value = _make_decision_row(state="ai_proposed")

        service.override_decision("dec-001", "attorney-jane", "Wrong charge")

        audit_sql = mock_cursor.execute.call_args_list[2][0][0]
        assert "INSERT INTO ai_decision_audit_log" in audit_sql
        audit_params = mock_cursor.execute.call_args_list[2][0][1]
        assert audit_params[3] == "human_overridden"  # new_state
        assert audit_params[4] == "attorney-jane"  # actor
        assert audit_params[5] == "Wrong charge"  # rationale


# ---------------------------------------------------------------------------
# Tests: get_decision
# ---------------------------------------------------------------------------

class TestGetDecision:
    def test_returns_decision(self, service, mock_cursor):
        mock_cursor.fetchone.return_value = _make_decision_row()

        result = service.get_decision("dec-001")

        assert result.decision_id == "dec-001"
        assert result.state == DecisionState.AI_PROPOSED

    def test_not_found_raises_key_error(self, service, mock_cursor):
        mock_cursor.fetchone.return_value = None

        with pytest.raises(KeyError, match="not found"):
            service.get_decision("nonexistent")


# ---------------------------------------------------------------------------
# Tests: get_case_decisions (filtered listing)
# ---------------------------------------------------------------------------

class TestGetCaseDecisions:
    def test_returns_all_decisions_for_case(self, service, mock_cursor):
        mock_cursor.fetchall.return_value = [
            _make_decision_row(decision_id="dec-001", decision_type="statute_recommendation"),
            _make_decision_row(decision_id="dec-002", decision_type="element_rating"),
        ]

        results = service.get_case_decisions("case-001")

        assert len(results) == 2
        assert results[0].decision_id == "dec-001"
        assert results[1].decision_id == "dec-002"

    def test_filters_by_decision_type(self, service, mock_cursor):
        mock_cursor.fetchall.return_value = [
            _make_decision_row(decision_id="dec-001", decision_type="element_rating"),
        ]

        results = service.get_case_decisions("case-001", decision_type="element_rating")

        sql = mock_cursor.execute.call_args[0][0]
        assert "decision_type = %s" in sql
        params = mock_cursor.execute.call_args[0][1]
        assert "element_rating" in params

    def test_filters_by_state(self, service, mock_cursor):
        mock_cursor.fetchall.return_value = [
            _make_decision_row(decision_id="dec-001", state="human_confirmed"),
        ]

        results = service.get_case_decisions("case-001", state="human_confirmed")

        sql = mock_cursor.execute.call_args[0][0]
        assert "state = %s" in sql
        params = mock_cursor.execute.call_args[0][1]
        assert "human_confirmed" in params

    def test_filters_by_both_type_and_state(self, service, mock_cursor):
        mock_cursor.fetchall.return_value = []

        service.get_case_decisions(
            "case-001", decision_type="statute_recommendation", state="ai_proposed"
        )

        sql = mock_cursor.execute.call_args[0][0]
        assert "decision_type = %s" in sql
        assert "state = %s" in sql

    def test_empty_case_returns_empty_list(self, service, mock_cursor):
        mock_cursor.fetchall.return_value = []

        results = service.get_case_decisions("case-empty")

        assert results == []


# ---------------------------------------------------------------------------
# Tests: get_decision_history (audit trail)
# ---------------------------------------------------------------------------

class TestGetDecisionHistory:
    def test_returns_audit_entries_in_chronological_order(self, service, mock_cursor):
        mock_cursor.fetchall.return_value = [
            _make_audit_row(
                audit_id="aud-001", new_state="ai_proposed",
                actor="system", created_at="2024-01-01T00:00:00+00:00",
            ),
            _make_audit_row(
                audit_id="aud-002", previous_state="ai_proposed",
                new_state="human_confirmed", actor="attorney-jane",
                created_at="2024-01-02T00:00:00+00:00",
            ),
        ]

        history = service.get_decision_history("dec-001")

        assert len(history) == 2
        assert history[0].new_state == "ai_proposed"
        assert history[0].actor == "system"
        assert history[1].new_state == "human_confirmed"
        assert history[1].actor == "attorney-jane"
        # Chronological: first entry before second
        assert history[0].created_at < history[1].created_at

    def test_history_query_orders_by_created_at_asc(self, service, mock_cursor):
        mock_cursor.fetchall.return_value = []

        service.get_decision_history("dec-001")

        sql = mock_cursor.execute.call_args[0][0]
        assert "ORDER BY created_at ASC" in sql

    def test_correct_entry_count_after_create_and_confirm(self, service, mock_cursor):
        """After create + confirm, history should have 2 entries."""
        mock_cursor.fetchall.return_value = [
            _make_audit_row(audit_id="aud-001", new_state="ai_proposed", actor="system"),
            _make_audit_row(
                audit_id="aud-002", previous_state="ai_proposed",
                new_state="human_confirmed", actor="attorney-jane",
            ),
        ]

        history = service.get_decision_history("dec-001")

        assert len(history) == 2
        assert history[0].previous_state is None  # initial entry
        assert history[1].previous_state == "ai_proposed"
