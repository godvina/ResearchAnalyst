"""Backlog Scoring Service — Computes prioritized case backlog rankings.

Implements a transparent, weighted scoring algorithm that produces a 0–100
composite score for pre-case leads. Factors include pre-assessment score,
priority level, classification confidence, estimated harm, policy alignment,
OSINT sources count, and urgency decay.

Uses Protocol/constructor-injection pattern consistent with project conventions.
"""

from __future__ import annotations

import json
import logging
import math
from datetime import datetime, timezone
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class PolicyPriorityProvider(Protocol):
    """Protocol for policy priority data access."""

    def get_active_policies(self) -> list[dict]:
        ...


class BacklogScoringService:
    """Computes the 0–100 Backlog_Score for pre-case leads.

    Scoring algorithm uses 7 weighted factors summing to 1.00.
    All normalization functions produce values in [0, 100].
    """

    WEIGHTS = {
        "pre_assessment_score": 0.25,
        "priority": 0.20,
        "classification_confidence": 0.15,
        "estimated_harm": 0.15,
        "policy_alignment": 0.10,
        "osint_sources": 0.10,
        "urgency_decay": 0.05,
    }

    ALGORITHM_VERSION = "1.0.0"

    PRIORITY_MAP = {"critical": 100, "high": 75, "medium": 50, "low": 25}

    def __init__(self, aurora_cm: Any, policy_provider: PolicyPriorityProvider = None):
        self.aurora_cm = aurora_cm
        self.policy_provider = policy_provider

    def compute_score(self, lead: dict, policies: list[dict] = None) -> float:
        """Compute composite backlog score for a single lead.

        Args:
            lead: Dict with priority, classification_confidence, pre_assessment_score,
                  osint_sources_count, estimated_harm, case_type, created_at, etc.
            policies: Active policy directives (fetched once for batch).

        Returns:
            Float 0–100 (rounded to 1 decimal).
        """
        pre_assessment = float(lead.get("pre_assessment_score") or 0)
        priority_norm = self._normalize_priority(lead.get("priority", "medium"))
        confidence = float(lead.get("classification_confidence") or 0)
        harm_norm = self._normalize_harm(float(lead.get("estimated_harm") or 0))
        policy_norm = self._normalize_policy_alignment(lead, policies or [])
        osint_norm = self._normalize_osint_sources(int(lead.get("osint_sources_count") or 0))
        urgency_norm = self._normalize_urgency(int(lead.get("days_since_submission") or 0))

        score = (
            pre_assessment * self.WEIGHTS["pre_assessment_score"]
            + priority_norm * self.WEIGHTS["priority"]
            + confidence * self.WEIGHTS["classification_confidence"]
            + harm_norm * self.WEIGHTS["estimated_harm"]
            + policy_norm * self.WEIGHTS["policy_alignment"]
            + osint_norm * self.WEIGHTS["osint_sources"]
            + urgency_norm * self.WEIGHTS["urgency_decay"]
        )

        return round(min(100.0, max(0.0, score)), 1)

    def get_ranked_backlog(
        self,
        filters: dict = None,
        page: int = 1,
        page_size: int = 25,
    ) -> dict:
        """Return paginated, ranked list of leads with computed scores.

        Args:
            filters: Optional dict with case_type, priority, min_score.
            page: Page number (1-indexed).
            page_size: Items per page.

        Returns:
            {leads: [...], total_count, page, page_size, algorithm_version}
        """
        filters = filters or {}

        # Fetch policies once for the batch
        policies = []
        if self.policy_provider:
            try:
                policies = self.policy_provider.get_active_policies()
            except Exception as e:
                logger.warning(f"Failed to fetch policies for scoring: {e}")

        # Query leads with OSINT source counts
        try:
            with self.aurora_cm.cursor() as cur:
                where_clauses = []
                params = []

                if filters.get("case_type"):
                    where_clauses.append("l.case_type = %s")
                    params.append(filters["case_type"])
                if filters.get("priority"):
                    where_clauses.append("l.priority = %s")
                    params.append(filters["priority"])

                where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

                cur.execute(
                    f"""
                    SELECT l.lead_id, l.title, l.case_type, l.priority,
                           l.classification_confidence, l.pre_assessment_score,
                           l.status, l.created_at,
                           COUNT(DISTINCT o.source_name) as osint_sources_count
                    FROM pre_case_leads l
                    LEFT JOIN pre_case_osint_data o ON o.lead_id = l.lead_id
                    WHERE {where_sql}
                    GROUP BY l.lead_id, l.title, l.case_type, l.priority,
                             l.classification_confidence, l.pre_assessment_score,
                             l.status, l.created_at
                    """,
                    params,
                )
                rows = cur.fetchall()
        except Exception as e:
            logger.error(f"Failed to query leads for backlog: {e}")
            return {
                "leads": [],
                "total_count": 0,
                "page": page,
                "page_size": page_size,
                "algorithm_version": self.ALGORITHM_VERSION,
            }

        # Compute scores for all leads
        scored_leads = []
        now = datetime.now(timezone.utc)
        for row in rows:
            created_at = row[7]
            if created_at:
                if hasattr(created_at, "tzinfo") and created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)
                days = (now - created_at).days
            else:
                days = 0

            lead_data = {
                "lead_id": str(row[0]),
                "title": row[1],
                "case_type": row[2],
                "priority": row[3] or "medium",
                "classification_confidence": row[4] or 0,
                "pre_assessment_score": row[5] or 0,
                "status": row[6],
                "created_at": created_at.isoformat() if created_at else None,
                "osint_sources_count": row[8] or 0,
                "estimated_harm": 0,
                "days_since_submission": days,
            }

            score = self.compute_score(lead_data, policies)
            lead_data["backlog_score"] = score
            lead_data["days_since_submission"] = days
            scored_leads.append(lead_data)

        # Apply min_score filter after scoring
        min_score = filters.get("min_score")
        if min_score is not None:
            scored_leads = [l for l in scored_leads if l["backlog_score"] >= float(min_score)]

        # Sort descending by score
        scored_leads.sort(key=lambda x: x["backlog_score"], reverse=True)

        total_count = len(scored_leads)

        # Paginate
        offset = (page - 1) * page_size
        paginated = scored_leads[offset:offset + page_size]

        return {
            "leads": paginated,
            "total_count": total_count,
            "page": page,
            "page_size": page_size,
            "algorithm_version": self.ALGORITHM_VERSION,
        }

    # --- Normalization helpers ---

    def _normalize_priority(self, priority: str) -> float:
        """Normalize priority to 0-100 scale.

        critical=100, high=75, medium=50, low=25.
        """
        return float(self.PRIORITY_MAP.get(priority, 50))

    def _normalize_osint_sources(self, count: int) -> float:
        """Normalize OSINT sources count to 0-100 scale.

        Linear: 0→0, 7+→100. Formula: min(100, count * 100 / 7).
        """
        if count <= 0:
            return 0.0
        return min(100.0, count * 100.0 / 7.0)

    def _normalize_harm(self, amount: float) -> float:
        """Normalize estimated harm to 0-100 scale using logarithmic scaling.

        $0=0, $1M≈50, $100M≈75, $1B+=100. Monotonically non-decreasing.
        """
        if amount <= 0:
            return 0.0
        if amount >= 1_000_000_000:
            return 100.0
        # Log scale: log10(amount) mapped to 0-100
        # log10(1M) = 6, log10(100M) = 8, log10(1B) = 9
        log_val = math.log10(max(1, amount))
        if log_val <= 6:
            return (log_val / 6.0) * 50.0
        elif log_val <= 8:
            return 50.0 + ((log_val - 6.0) / 2.0) * 25.0
        else:
            return 75.0 + ((log_val - 8.0) / 1.0) * 25.0

    def _normalize_urgency(self, days: int) -> float:
        """Normalize urgency/age decay to 0-100 scale.

        Formula: min(100, days * 2). Caps at 50 days.
        """
        return min(100.0, float(days) * 2.0)

    def _normalize_policy_alignment(self, lead: dict, policies: list[dict]) -> float:
        """Normalize policy alignment to 0-100 scale.

        0 if no match, 50 if multiplier 1.0–1.3, 75 if 1.3–1.6, 100 if 1.6–2.0.
        Uses maximum matching multiplier (not cumulative).
        """
        if not policies:
            return 0.0

        case_type = lead.get("case_type", "")
        industry = lead.get("industry", "")

        max_multiplier = 0.0

        for policy in policies:
            target_case_types = policy.get("target_case_types", [])
            target_industries = policy.get("target_industries", [])
            multiplier = float(policy.get("boost_multiplier", 1.0))

            matched = False
            if case_type and target_case_types:
                if case_type in target_case_types or "all" in target_case_types:
                    matched = True
            if industry and target_industries:
                if industry in target_industries or "all" in target_industries:
                    matched = True

            if matched and multiplier > max_multiplier:
                max_multiplier = multiplier

        if max_multiplier <= 0:
            return 0.0
        elif max_multiplier < 1.3:
            return 50.0
        elif max_multiplier < 1.6:
            return 75.0
        else:
            return 100.0
