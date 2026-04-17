"""AI-First Analysis Engine — orchestrates auto-analysis on case load.

Coordinates ElementAssessmentService, CaseWeaknessService, and
DecisionWorkflowService to produce a complete AI-first analysis with
all recommendations tracked through the decision workflow.

Bedrock fallback: falls back to deterministic-only analysis (no statute
recommendations, no charging drafts), returning partial results with
warnings.
"""

import logging
from typing import Optional

from models.prosecutor import (
    CaseAnalysisResult,
    ChargingRecommendation,
    ConfidenceLevel,
    ElementMapping,
    StatuteRecommendation,
)

logger = logging.getLogger(__name__)


class AIFirstAnalysisEngine:
    """Orchestrates automatic case analysis on load."""

    def __init__(
        self,
        element_assessment_svc,
        case_weakness_svc,
        decision_workflow_svc,
        bedrock_client,
    ):
        self._element_svc = element_assessment_svc
        self._weakness_svc = case_weakness_svc
        self._decision_svc = decision_workflow_svc
        self._bedrock = bedrock_client

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def auto_analyze(self, case_id: str) -> CaseAnalysisResult:
        """Full auto-analysis on case load.

        1. Recommend applicable statutes (ranked by evidence match)
        2. Auto-map evidence to elements for top statutes
        3. Run weakness analysis
        4. Draft charging recommendation if sufficient evidence
        Each recommendation is created as an AI_Proposed decision.

        When Bedrock is unavailable, falls back to deterministic-only
        analysis — no statute recommendations, no charging drafts —
        returning partial results with warnings.
        """
        warnings: list[str] = []
        statute_recommendations: list[StatuteRecommendation] = []
        all_mappings: list[ElementMapping] = []
        decisions_created: list[str] = []
        charging_rec: Optional[ChargingRecommendation] = None

        # Step 1: Recommend statutes (requires Bedrock)
        if self._bedrock:
            try:
                statute_recommendations = self._element_svc.recommend_statutes(case_id)
                # Create AI_Proposed decision for each recommendation
                for rec in statute_recommendations:
                    decision = self._decision_svc.create_decision(
                        case_id=case_id,
                        decision_type="statute_recommendation",
                        recommendation_text=f"Recommend {rec.citation}: {rec.title}",
                        legal_reasoning=rec.justification,
                        confidence=rec.confidence.value,
                        source_service="ai_first_analysis_engine",
                    )
                    decisions_created.append(decision.decision_id)
            except Exception as e:
                logger.warning("Statute recommendation failed: %s", e)
                warnings.append(f"Statute recommendation unavailable: {e}")
        else:
            warnings.append(
                "Bedrock unavailable — statute recommendations skipped"
            )

        # Step 2: Assess elements for each top recommended statute
        for rec in statute_recommendations:
            try:
                matrix = self._element_svc.assess_elements(case_id, rec.statute_id)
                # Collect element mappings from the matrix ratings
                for rating in matrix.ratings:
                    mapping = ElementMapping(
                        evidence_id=rating.evidence_id,
                        element_id=rating.element_id,
                        justification=rating.reasoning or rating.legal_justification,
                        confidence=self._score_to_confidence(rating.confidence),
                        decision_id=rating.decision_id,
                    )
                    all_mappings.append(mapping)

                # Step 4: Draft charging recommendation if readiness >= 70%
                if matrix.readiness_score >= 70 and self._bedrock:
                    try:
                        charging_rec = self._element_svc.draft_charging_recommendation(
                            case_id, rec.statute_id
                        )
                        if charging_rec and charging_rec.decision_id:
                            decisions_created.append(charging_rec.decision_id)
                    except Exception as e:
                        logger.warning("Charging recommendation failed: %s", e)
                        warnings.append(f"Charging recommendation failed: {e}")
            except Exception as e:
                logger.warning("Element assessment failed for %s: %s", rec.statute_id, e)
                warnings.append(f"Element assessment failed for {rec.citation}: {e}")

        # Step 3: Weakness analysis (partially deterministic)
        weaknesses = []
        try:
            # Pass first statute_id if available for corroboration checks
            statute_id = statute_recommendations[0].statute_id if statute_recommendations else None
            weaknesses = self._weakness_svc.analyze_weaknesses(case_id, statute_id)
        except Exception as e:
            logger.warning("Weakness analysis failed: %s", e)
            warnings.append(f"Weakness analysis failed: {e}")

        return CaseAnalysisResult(
            case_id=case_id,
            statute_recommendations=statute_recommendations,
            element_mappings=all_mappings,
            weaknesses=weaknesses,
            charging_recommendation=charging_rec,
            decisions_created=decisions_created,
            warnings=warnings,
        )

    def on_evidence_added(
        self, case_id: str, evidence_id: str
    ) -> list[ElementMapping]:
        """Auto-categorize new evidence against selected statutes.

        Creates AI_Proposed decisions for each new mapping.
        Returns empty list when Bedrock is unavailable.
        """
        if not self._bedrock:
            return []

        mappings: list[ElementMapping] = []

        # Get statutes currently selected for this case
        selected_statutes = self._get_case_statutes(case_id)

        for statute_id in selected_statutes:
            try:
                new_mappings = self._element_svc.auto_categorize_evidence(
                    case_id, evidence_id, statute_id
                )
                for mapping in new_mappings:
                    # Create AI_Proposed decision for each mapping
                    if not mapping.decision_id:
                        decision = self._decision_svc.create_decision(
                            case_id=case_id,
                            decision_type="evidence_mapping",
                            recommendation_text=(
                                f"Map evidence {evidence_id} to element {mapping.element_id}"
                            ),
                            legal_reasoning=mapping.justification,
                            confidence=mapping.confidence.value,
                            source_service="ai_first_analysis_engine",
                        )
                        mapping.decision_id = decision.decision_id
                    mappings.append(mapping)
            except Exception as e:
                logger.warning(
                    "Evidence categorization failed for statute %s: %s",
                    statute_id, e,
                )

        return mappings

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_case_statutes(self, case_id: str) -> list[str]:
        """Get statute IDs currently selected for a case.

        Falls back to statute recommendations if no explicit selections.
        """
        # Try to get from element_assessment_svc's recommendations
        try:
            recommendations = self._element_svc.recommend_statutes(case_id)
            return [r.statute_id for r in recommendations]
        except Exception:
            return []

    @staticmethod
    def _score_to_confidence(score: int) -> ConfidenceLevel:
        """Map a numeric confidence score to ConfidenceLevel."""
        if score >= 75:
            return ConfidenceLevel.HIGH
        if score >= 40:
            return ConfidenceLevel.MEDIUM
        return ConfidenceLevel.LOW

