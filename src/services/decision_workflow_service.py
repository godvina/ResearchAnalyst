"""Decision Workflow Service — three-state human-in-the-loop decision engine.

Manages the AI_Proposed → Human_Confirmed / Human_Overridden lifecycle
with full audit trail.  Pure Aurora CRUD — no Bedrock dependency.
"""

import logging
import uuid
from datetime import datetime, timezone

from models.prosecutor import (
    AIDecision,
    ConfidenceLevel,
    DecisionAuditEntry,
    DecisionState,
)

logger = logging.getLogger(__name__)


class ConflictError(Exception):
    """Raised when a decision has already been confirmed or overridden (409)."""

    pass


class DecisionWorkflowService:
    """Three-state decision workflow backed by Aurora PostgreSQL."""

    def __init__(self, aurora_cm):
        self._db = aurora_cm

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create_decision(
        self,
        case_id: str,
        decision_type: str,
        recommendation_text: str,
        legal_reasoning: str,
        confidence: str,
        source_service: str,
    ) -> AIDecision:
        """Create a new AI_Proposed decision with an initial audit entry."""
        decision_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        with self._db.cursor() as cur:
            cur.execute(
                """
                INSERT INTO ai_decisions (
                    decision_id, case_id, decision_type, state,
                    recommendation_text, legal_reasoning, confidence,
                    source_service, created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    decision_id, case_id, decision_type,
                    DecisionState.AI_PROPOSED.value,
                    recommendation_text, legal_reasoning, confidence,
                    source_service, now, now,
                ),
            )
            # Initial audit log entry
            cur.execute(
                """
                INSERT INTO ai_decision_audit_log (
                    audit_id, decision_id, previous_state, new_state,
                    actor, rationale, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    str(uuid.uuid4()), decision_id, None,
                    DecisionState.AI_PROPOSED.value, "system",
                    recommendation_text, now,
                ),
            )

        return AIDecision(
            decision_id=decision_id,
            case_id=case_id,
            decision_type=decision_type,
            state=DecisionState.AI_PROPOSED,
            recommendation_text=recommendation_text,
            legal_reasoning=legal_reasoning,
            confidence=ConfidenceLevel(confidence),
            source_service=source_service,
            created_at=now,
            updated_at=now,
        )

    def confirm_decision(self, decision_id: str, attorney_id: str) -> AIDecision:
        """Transition a decision to Human_Confirmed.

        Raises ConflictError (409) if already confirmed or overridden.
        """
        decision = self.get_decision(decision_id)
        if decision.state != DecisionState.AI_PROPOSED:
            raise ConflictError(
                f"Decision {decision_id} is already {decision.state.value}; "
                "cannot confirm."
            )

        now = datetime.now(timezone.utc).isoformat()

        with self._db.cursor() as cur:
            cur.execute(
                """
                UPDATE ai_decisions
                SET state = %s, confirmed_at = %s, confirmed_by = %s,
                    updated_at = %s
                WHERE decision_id = %s
                """,
                (
                    DecisionState.HUMAN_CONFIRMED.value, now,
                    attorney_id, now, decision_id,
                ),
            )
            cur.execute(
                """
                INSERT INTO ai_decision_audit_log (
                    audit_id, decision_id, previous_state, new_state,
                    actor, rationale, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    str(uuid.uuid4()), decision_id,
                    DecisionState.AI_PROPOSED.value,
                    DecisionState.HUMAN_CONFIRMED.value,
                    attorney_id, None, now,
                ),
            )

        return AIDecision(
            decision_id=decision.decision_id,
            case_id=decision.case_id,
            decision_type=decision.decision_type,
            state=DecisionState.HUMAN_CONFIRMED,
            recommendation_text=decision.recommendation_text,
            legal_reasoning=decision.legal_reasoning,
            confidence=decision.confidence,
            source_service=decision.source_service,
            confirmed_at=now,
            confirmed_by=attorney_id,
            created_at=decision.created_at,
            updated_at=now,
        )

    def override_decision(
        self, decision_id: str, attorney_id: str, override_rationale: str
    ) -> AIDecision:
        """Transition a decision to Human_Overridden.

        Raises ValueError if override_rationale is empty.
        Raises ConflictError (409) if already confirmed or overridden.
        """
        if not override_rationale or not override_rationale.strip():
            raise ValueError("override_rationale must not be empty")

        decision = self.get_decision(decision_id)
        if decision.state != DecisionState.AI_PROPOSED:
            raise ConflictError(
                f"Decision {decision_id} is already {decision.state.value}; "
                "cannot override."
            )

        now = datetime.now(timezone.utc).isoformat()

        with self._db.cursor() as cur:
            cur.execute(
                """
                UPDATE ai_decisions
                SET state = %s, overridden_at = %s, overridden_by = %s,
                    override_rationale = %s, updated_at = %s
                WHERE decision_id = %s
                """,
                (
                    DecisionState.HUMAN_OVERRIDDEN.value, now,
                    attorney_id, override_rationale, now, decision_id,
                ),
            )
            cur.execute(
                """
                INSERT INTO ai_decision_audit_log (
                    audit_id, decision_id, previous_state, new_state,
                    actor, rationale, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    str(uuid.uuid4()), decision_id,
                    DecisionState.AI_PROPOSED.value,
                    DecisionState.HUMAN_OVERRIDDEN.value,
                    attorney_id, override_rationale, now,
                ),
            )

        return AIDecision(
            decision_id=decision.decision_id,
            case_id=decision.case_id,
            decision_type=decision.decision_type,
            state=DecisionState.HUMAN_OVERRIDDEN,
            recommendation_text=decision.recommendation_text,
            legal_reasoning=decision.legal_reasoning,
            confidence=decision.confidence,
            source_service=decision.source_service,
            overridden_at=now,
            overridden_by=attorney_id,
            override_rationale=override_rationale,
            created_at=decision.created_at,
            updated_at=now,
        )

    def get_decision(self, decision_id: str) -> AIDecision:
        """Retrieve a single decision by ID."""
        with self._db.cursor() as cur:
            cur.execute(
                """
                SELECT decision_id, case_id, decision_type, state,
                       recommendation_text, legal_reasoning, confidence,
                       source_service, related_entity_id, related_entity_type,
                       confirmed_at, confirmed_by, overridden_at, overridden_by,
                       override_rationale, created_at, updated_at
                FROM ai_decisions
                WHERE decision_id = %s
                """,
                (decision_id,),
            )
            row = cur.fetchone()
            if row is None:
                raise KeyError(f"Decision {decision_id} not found")
            return self._row_to_decision(row)

    def get_case_decisions(
        self,
        case_id: str,
        decision_type: str | None = None,
        state: str | None = None,
    ) -> list[AIDecision]:
        """List decisions for a case with optional filters."""
        query = "SELECT decision_id, case_id, decision_type, state, " \
                "recommendation_text, legal_reasoning, confidence, " \
                "source_service, related_entity_id, related_entity_type, " \
                "confirmed_at, confirmed_by, overridden_at, overridden_by, " \
                "override_rationale, created_at, updated_at " \
                "FROM ai_decisions WHERE case_id = %s"
        params: list = [case_id]

        if decision_type is not None:
            query += " AND decision_type = %s"
            params.append(decision_type)
        if state is not None:
            query += " AND state = %s"
            params.append(state)

        query += " ORDER BY created_at ASC"

        with self._db.cursor() as cur:
            cur.execute(query, tuple(params))
            return [self._row_to_decision(r) for r in cur.fetchall()]

    def get_decision_history(self, decision_id: str) -> list[DecisionAuditEntry]:
        """Get chronological audit trail for a decision, ordered by created_at ASC."""
        with self._db.cursor() as cur:
            cur.execute(
                """
                SELECT audit_id, decision_id, previous_state, new_state,
                       actor, rationale, created_at
                FROM ai_decision_audit_log
                WHERE decision_id = %s
                ORDER BY created_at ASC
                """,
                (decision_id,),
            )
            return [
                DecisionAuditEntry(
                    audit_id=str(row[0]),
                    decision_id=str(row[1]),
                    previous_state=row[2],
                    new_state=row[3],
                    actor=row[4],
                    rationale=row[5],
                    created_at=str(row[6]),
                )
                for row in cur.fetchall()
            ]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_decision(row) -> AIDecision:
        """Map a database row tuple to an AIDecision model."""
        return AIDecision(
            decision_id=str(row[0]),
            case_id=str(row[1]),
            decision_type=row[2],
            state=DecisionState(row[3]),
            recommendation_text=row[4],
            legal_reasoning=row[5],
            confidence=ConfidenceLevel(row[6]),
            source_service=row[7],
            related_entity_id=str(row[8]) if row[8] else None,
            related_entity_type=row[9],
            confirmed_at=str(row[10]) if row[10] else None,
            confirmed_by=row[11],
            overridden_at=str(row[12]) if row[12] else None,
            overridden_by=row[13],
            override_rationale=row[14],
            created_at=str(row[15]),
            updated_at=str(row[16]),
        )

