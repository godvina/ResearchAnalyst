"""ProcessTracker — succession pipeline stage management.

Tracks candidate progression through the recruitment/succession pipeline,
enforces stage ordering, and monitors SLA compliance.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

# Ordered pipeline stages — candidates move forward only.
STAGE_ORDER = [
    'LONG_LIST',
    'SHORT_LIST',
    'APPROACH',
    'SCREEN',
    'ASSESS',
    'OFFER',
    'CLOSE',
    'ONBOARD',
]

# Default SLA in calendar days per stage.
DEFAULT_SLA = {
    'LONG_LIST': 14,
    'SHORT_LIST': 7,
    'APPROACH': 10,
    'SCREEN': 14,
    'ASSESS': 21,
    'OFFER': 7,
    'CLOSE': 14,
    'ONBOARD': 30,
}


@dataclass
class StageTransition:
    """Records a candidate entering (and optionally exiting) a pipeline stage."""

    candidate_id: str
    stage: str
    entered_at: datetime
    exited_at: Optional[datetime] = None
    user: str = ""
    note: str = ""


@dataclass
class SLAStatus:
    """SLA health check for the current stage of a candidate."""

    stage: str
    days_in_stage: int
    sla_days: int
    is_breach: bool


class ProcessTracker:
    """In-memory tracker for candidate pipeline stage transitions.

    State is keyed by candidate_id → list of StageTransition.
    Suitable for demo/localStorage persistence; production would use Aurora.
    """

    def __init__(self) -> None:
        self._state: dict[str, list[StageTransition]] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def advance_stage(
        self,
        candidate_id: str,
        new_stage: str,
        user: str,
        note: str = "",
    ) -> StageTransition:
        """Move a candidate to *new_stage*.

        Raises ValueError if *new_stage* is not a valid stage or represents
        a backward (or same-stage) move relative to the candidate's current stage.
        """
        if new_stage not in STAGE_ORDER:
            raise ValueError(
                f"Invalid stage '{new_stage}'. Must be one of {STAGE_ORDER}"
            )

        new_index = STAGE_ORDER.index(new_stage)
        transitions = self._state.get(candidate_id, [])

        if transitions:
            current = transitions[-1]
            current_index = STAGE_ORDER.index(current.stage)
            if new_index <= current_index:
                raise ValueError(
                    f"Cannot move backward: current stage is "
                    f"'{current.stage}' (index {current_index}), "
                    f"requested '{new_stage}' (index {new_index})"
                )
            # Close out the previous stage.
            current.exited_at = _now()

        transition = StageTransition(
            candidate_id=candidate_id,
            stage=new_stage,
            entered_at=_now(),
            user=user,
            note=note,
        )

        if candidate_id not in self._state:
            self._state[candidate_id] = []
        self._state[candidate_id].append(transition)

        return transition

    def get_current_stage(self, candidate_id: str) -> Optional[StageTransition]:
        """Return the most recent transition for *candidate_id*, or None."""
        transitions = self._state.get(candidate_id, [])
        return transitions[-1] if transitions else None

    def check_sla(self, candidate_id: str) -> SLAStatus:
        """Compute SLA status for the candidate's current stage.

        Raises ValueError if the candidate has no recorded transitions.
        """
        current = self.get_current_stage(candidate_id)
        if current is None:
            raise ValueError(
                f"No transitions recorded for candidate '{candidate_id}'"
            )

        days_in_stage = (_now() - current.entered_at).days
        sla_days = DEFAULT_SLA[current.stage]
        is_breach = days_in_stage > sla_days

        return SLAStatus(
            stage=current.stage,
            days_in_stage=days_in_stage,
            sla_days=sla_days,
            is_breach=is_breach,
        )

    def get_timeline(self, transaction_id: str = None) -> list[StageTransition]:
        """Return all transitions across all candidates, sorted by entered_at.

        If *transaction_id* is provided it is reserved for future filtering
        (currently returns the full timeline regardless).
        """
        all_transitions: list[StageTransition] = []
        for transitions in self._state.values():
            all_transitions.extend(transitions)

        all_transitions.sort(key=lambda t: t.entered_at)
        return all_transitions


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------

def _now() -> datetime:
    """UTC-aware current timestamp."""
    return datetime.now(timezone.utc)
