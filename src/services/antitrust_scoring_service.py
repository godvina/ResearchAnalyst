"""Antitrust scoring framework — shared across all case type modules.

Provides a generic weighted-factor scoring engine that each antitrust module
configures with its own factors and weights. Computes composite scores,
classifies severity, and caches results in Aurora.

Usage:
    scoring_svc = AntitrustScoringService(aurora_cm)
    factors = [
        ScoringFactor(name="bid_rigging", weight=0.30, score=85.0),
        ScoringFactor(name="pricing", weight=0.25, score=60.0),
        ...
    ]
    result = scoring_svc.compute_score(factors)
    # result.overall_score = weighted composite
    # result.severity = "Critical" | "High" | "Medium" | "Low"
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Optional

logger = logging.getLogger(__name__)


# Import from models if available, otherwise define locally for standalone use
try:
    from models.antitrust import ScoringFactor, ScoringResult
except ImportError:
    from dataclasses import dataclass, field

    @dataclass
    class ScoringFactor:
        name: str
        weight: float
        score: float
        evidence_refs: list[str] = field(default_factory=list)
        description: str = ""

    @dataclass
    class ScoringResult:
        overall_score: float
        factors: list[ScoringFactor] = field(default_factory=list)
        severity: str = "Low"
        confidence: float = 0.0


# Severity thresholds
SEVERITY_CRITICAL = 75.0
SEVERITY_HIGH = 50.0
SEVERITY_MEDIUM = 25.0


class AntitrustScoringService:
    """Generic weighted-factor scoring framework for antitrust analysis.

    Shared across all case types. Each module provides its own factors and
    weights via get_scoring_factors(). This service computes the composite
    score and classifies severity.
    """

    def __init__(self, aurora_cm=None) -> None:
        """Initialize scoring service.

        Args:
            aurora_cm: Aurora ConnectionManager for caching scores.
                If None, caching is disabled (useful for testing).
        """
        self.aurora_cm = aurora_cm

    def compute_score(self, factors: list[ScoringFactor]) -> ScoringResult:
        """Compute weighted composite score from factors.

        Args:
            factors: List of ScoringFactor with name, weight, and score.
                Weights must sum to 1.0 (tolerance: 0.001).

        Returns:
            ScoringResult with overall_score, severity, and confidence.

        Raises:
            ValueError: If weights do not sum to 1.0 (within tolerance).
        """
        if not factors:
            return ScoringResult(overall_score=0.0, factors=[], severity="Low", confidence=0.0)

        # Validate weights sum to 1.0
        total_weight = sum(f.weight for f in factors)
        if abs(total_weight - 1.0) > 0.001:
            raise ValueError(
                f"Factor weights must sum to 1.0, got {total_weight:.4f}. "
                f"Factors: {[(f.name, f.weight) for f in factors]}"
            )

        # Compute weighted composite
        overall_score = sum(f.weight * f.score for f in factors)

        # Clamp to [0, 100]
        overall_score = max(0.0, min(100.0, overall_score))

        # Classify severity
        severity = self.classify_severity(overall_score)

        # Compute confidence based on factor coverage
        non_zero_factors = sum(1 for f in factors if f.score > 0)
        confidence = non_zero_factors / len(factors) if factors else 0.0

        return ScoringResult(
            overall_score=round(overall_score, 2),
            factors=factors,
            severity=severity,
            confidence=round(confidence, 2),
        )

    def classify_severity(self, score: float) -> str:
        """Map a score to severity classification.

        Args:
            score: Numeric score in [0, 100].

        Returns:
            Severity string: "Critical", "High", "Medium", or "Low".
        """
        if score >= SEVERITY_CRITICAL:
            return "Critical"
        elif score >= SEVERITY_HIGH:
            return "High"
        elif score >= SEVERITY_MEDIUM:
            return "Medium"
        else:
            return "Low"

    def store_score(
        self,
        case_id: str,
        entity_id: str,
        result: ScoringResult,
        score_type: str = "pcsf",
    ) -> Optional[str]:
        """Persist scoring result to Aurora for caching.

        Args:
            case_id: Investigation identifier.
            entity_id: Entity being scored (contract cluster, vendor, ring).
            result: The computed ScoringResult.
            score_type: Type of score (e.g., "pcsf", "merger_hhi").

        Returns:
            The score_id if stored successfully, None otherwise.
        """
        if not self.aurora_cm:
            logger.debug("No Aurora connection — skipping score cache")
            return None

        score_id = str(uuid.uuid4())
        try:
            with self.aurora_cm.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO collusion_analyses (analysis_id, case_id, pcsf_score, pcsf_breakdown, analysis_status)
                        VALUES (%s, %s, %s, %s, 'completed')
                        ON CONFLICT (analysis_id) DO UPDATE SET
                            pcsf_score = EXCLUDED.pcsf_score,
                            pcsf_breakdown = EXCLUDED.pcsf_breakdown,
                            updated_at = NOW()
                        """,
                        (
                            score_id,
                            case_id,
                            result.overall_score,
                            json.dumps({
                                "factors": [
                                    {"name": f.name, "weight": f.weight, "score": f.score}
                                    for f in result.factors
                                ],
                                "severity": result.severity,
                                "confidence": result.confidence,
                                "entity_id": entity_id,
                                "score_type": score_type,
                            }),
                        ),
                    )
                conn.commit()
            logger.info(f"Stored score {score_id} for case={case_id} entity={entity_id}")
            return score_id
        except Exception as e:
            logger.error(f"Failed to store score: {e}")
            return None

    def get_cached_score(
        self,
        case_id: str,
        entity_id: str,
        max_age_minutes: int = 60,
    ) -> Optional[ScoringResult]:
        """Retrieve cached score if available and not stale.

        Args:
            case_id: Investigation identifier.
            entity_id: Entity that was scored.
            max_age_minutes: Maximum age of cached score in minutes.

        Returns:
            ScoringResult if found and fresh, None otherwise.
        """
        if not self.aurora_cm:
            return None

        try:
            with self.aurora_cm.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT pcsf_score, pcsf_breakdown, updated_at
                        FROM collusion_analyses
                        WHERE case_id = %s
                          AND pcsf_breakdown->>'entity_id' = %s
                          AND updated_at > NOW() - INTERVAL '%s minutes'
                        ORDER BY updated_at DESC
                        LIMIT 1
                        """,
                        (case_id, entity_id, max_age_minutes),
                    )
                    row = cur.fetchone()
                    if not row:
                        return None

                    score, breakdown, _ = row
                    if isinstance(breakdown, str):
                        breakdown = json.loads(breakdown)

                    factors = [
                        ScoringFactor(
                            name=f["name"],
                            weight=f["weight"],
                            score=f["score"],
                        )
                        for f in breakdown.get("factors", [])
                    ]

                    return ScoringResult(
                        overall_score=float(score),
                        factors=factors,
                        severity=breakdown.get("severity", "Low"),
                        confidence=breakdown.get("confidence", 0.0),
                    )
        except Exception as e:
            logger.error(f"Failed to retrieve cached score: {e}")
            return None
