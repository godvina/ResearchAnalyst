"""Prosecution Readiness Assessment — Pre-case evidence evaluation and scoring.

Evaluates gathered OSINT evidence against elements of offense for the classified
antitrust case type. Produces a composite Pre_Assessment_Score (0-100) with a
recommendation (open_investigation, need_more_evidence, insufficient_basis),
evidence matrix, evidence gaps, and legal reasoning.

Uses Amazon Nova Pro with the Antitrust_Legal_Persona for legal reasoning and
evidence evaluation. Each assessment is stored as an AI_Proposed decision in
Aurora for the Decision_Workflow.

Usage:
    assessment = ProsecutionReadinessAssessment(
        bedrock_client=bedrock_runtime,
        aurora_cm=connection_manager,
    )
    result = assessment.assess("lead-uuid", evidence_list, "procurement_collusion")
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Amazon Nova Pro — GovCloud-available, platform standard
MODEL_ID = "amazon.nova-pro-v1:0"


@dataclass
class AssessmentResult:
    """Output of the ProsecutionReadinessAssessment.

    Attributes:
        assessment_id: UUID for this assessment record.
        lead_id: UUID of the assessed lead.
        score: Composite Pre_Assessment_Score in [0, 100].
        recommendation: One of open_investigation, need_more_evidence, insufficient_basis.
        evidence_matrix: Mapping of evidence items to elements of offense they support.
        evidence_gaps: List of unsupported elements with recommended actions.
        legal_reasoning: AI-generated legal analysis citing statutes.
        statutes_cited: List of relevant statutes referenced.
        scoring_framework: Framework applied based on case_type.
    """

    assessment_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    lead_id: str = ""
    score: int = 0
    recommendation: str = "insufficient_basis"
    evidence_matrix: dict = field(default_factory=dict)
    evidence_gaps: list = field(default_factory=list)
    legal_reasoning: str = ""
    statutes_cited: list = field(default_factory=list)
    scoring_framework: str = ""


# ─── Elements of offense per case type ────────────────────────────────────────

ELEMENTS_OF_OFFENSE = {
    "procurement_collusion": [
        "agreement_or_conspiracy",
        "bid_rigging_or_complementary_bidding",
        "market_allocation_among_conspirators",
        "price_fixing_or_bid_suppression",
        "interstate_commerce_nexus",
        "damages_to_government_or_taxpayers",
    ],
    "price_fixing": [
        "agreement_among_competitors",
        "fixing_or_stabilizing_prices",
        "horizontal_relationship",
        "interstate_commerce_nexus",
        "per_se_violation_applicability",
    ],
    "market_allocation": [
        "agreement_among_competitors",
        "geographic_or_customer_division",
        "horizontal_relationship",
        "interstate_commerce_nexus",
        "per_se_violation_applicability",
    ],
    "merger_review": [
        "substantially_lessen_competition",
        "relevant_market_definition",
        "market_concentration_increase",
        "barriers_to_entry",
        "elimination_of_competition",
        "hhi_threshold_exceeded",
    ],
    "monopolization": [
        "monopoly_power_in_relevant_market",
        "willful_acquisition_or_maintenance",
        "anticompetitive_conduct",
        "relevant_market_definition",
        "harm_to_competition",
    ],
    "criminal_cartel": [
        "agreement_or_conspiracy",
        "per_se_illegal_conduct",
        "knowing_and_willful_participation",
        "interstate_commerce_nexus",
        "identifiable_victims",
        "quantifiable_damages",
    ],
}

# ─── Statutes per case type ───────────────────────────────────────────────────

STATUTES_BY_CASE_TYPE = {
    "procurement_collusion": [
        "Sherman Act Section 1 (15 U.S.C. § 1)",
        "18 U.S.C. § 1341 (Mail Fraud)",
        "18 U.S.C. § 1343 (Wire Fraud)",
        "18 U.S.C. § 371 (Conspiracy to Defraud the United States)",
    ],
    "price_fixing": [
        "Sherman Act Section 1 (15 U.S.C. § 1)",
        "Per se rule — horizontal price-fixing",
    ],
    "market_allocation": [
        "Sherman Act Section 1 (15 U.S.C. § 1)",
        "Per se rule — horizontal market allocation",
    ],
    "merger_review": [
        "Clayton Act Section 7 (15 U.S.C. § 18)",
        "Hart-Scott-Rodino Act (15 U.S.C. § 18a)",
        "FTC Act Section 5 (15 U.S.C. § 45)",
    ],
    "monopolization": [
        "Sherman Act Section 2 (15 U.S.C. § 2)",
        "Rule of reason analysis",
    ],
    "criminal_cartel": [
        "Sherman Act Section 1 (15 U.S.C. § 1) — criminal penalty",
        "18 U.S.C. § 1341 (Mail Fraud)",
        "18 U.S.C. § 1343 (Wire Fraud)",
        "Federal Sentencing Guidelines § 2R1.1",
    ],
}


class ProsecutionReadinessAssessment:
    """Evaluates prosecution readiness for pre-case leads.

    Computes a composite Pre_Assessment_Score using weighted components,
    generates recommendations, builds evidence matrices, and identifies gaps.
    Uses Amazon Nova Pro for legal reasoning. Follows Protocol/constructor-injection
    pattern for testability.
    """

    SCORING_WEIGHTS = {
        "elements_satisfied": 0.40,
        "evidence_quality": 0.25,
        "corroboration": 0.20,
        "pattern_strength": 0.15,
    }

    FRAMEWORKS = {
        "procurement_collusion": "pcsf",
        "price_fixing": "horizontal_agreement",
        "market_allocation": "horizontal_agreement",
        "merger_review": "hart_scott_rodino",
        "monopolization": "section_2",
        "criminal_cartel": "criminal_cartel",
    }

    def __init__(self, bedrock_client: Any, aurora_cm: Any) -> None:
        """Initialize assessment service with dependencies.

        Args:
            bedrock_client: boto3 Bedrock Runtime client for invoke_model.
            aurora_cm: Aurora PostgreSQL connection manager with cursor() context manager.
        """
        self.bedrock_client = bedrock_client
        self.aurora_cm = aurora_cm
        self.model_id = MODEL_ID

    # ─── Public API ───────────────────────────────────────────────────────────

    def assess(
        self, lead_id: str, evidence: list, case_type: str
    ) -> AssessmentResult:
        """Assess prosecution readiness for a pre-case lead.

        Evaluates gathered evidence against elements of offense for the given
        case_type, computes a composite score, generates a recommendation,
        and identifies evidence gaps.

        Args:
            lead_id: UUID of the lead being assessed.
            evidence: List of evidence dicts from OSINT gathering.
            case_type: Classified antitrust case type.

        Returns:
            AssessmentResult with score, recommendation, matrix, gaps, reasoning.
        """
        framework = self.FRAMEWORKS.get(case_type, "pcsf")
        elements = self._get_elements_of_offense(case_type)

        # Build evidence matrix mapping evidence to elements
        evidence_matrix = self._build_evidence_matrix(evidence, case_type)

        # Identify gaps — elements not supported by evidence
        evidence_gaps = self._identify_evidence_gaps(evidence_matrix, case_type)

        # Get AI legal reasoning and component scores from Bedrock
        ai_analysis = self._invoke_legal_analysis(
            lead_id, evidence, case_type, elements, evidence_matrix
        )

        # Compute composite score from component scores
        components = ai_analysis.get("components", {})
        score = self._compute_score(components)

        # Generate recommendation based on score
        recommendation = self._generate_recommendation(score)

        # Build result
        result = AssessmentResult(
            lead_id=lead_id,
            score=score,
            recommendation=recommendation,
            evidence_matrix=evidence_matrix,
            evidence_gaps=evidence_gaps,
            legal_reasoning=ai_analysis.get("legal_reasoning", ""),
            statutes_cited=STATUTES_BY_CASE_TYPE.get(case_type, []),
            scoring_framework=framework,
        )

        # Store assessment in Aurora as AI_Proposed decision
        self._store_assessment(result)

        return result

    # ─── Scoring ──────────────────────────────────────────────────────────────

    def _compute_score(self, components: dict) -> int:
        """Compute weighted composite Pre_Assessment_Score.

        Formula: round(0.40*elements_satisfied + 0.25*evidence_quality
                       + 0.20*corroboration + 0.15*pattern_strength)

        Each component is expected in [0, 100]. The result is clamped to [0, 100].

        Args:
            components: Dict with keys matching SCORING_WEIGHTS.

        Returns:
            Integer score in [0, 100].
        """
        weighted_sum = 0.0
        for key, weight in self.SCORING_WEIGHTS.items():
            value = components.get(key, 0)
            # Clamp individual components to [0, 100]
            value = max(0, min(100, int(value)))
            weighted_sum += weight * value

        score = round(weighted_sum)
        # Clamp final result to [0, 100]
        return max(0, min(100, score))

    def _generate_recommendation(self, score: int) -> str:
        """Generate recommendation based on Pre_Assessment_Score thresholds.

        Thresholds:
            > 70  → open_investigation
            40-70 → need_more_evidence
            < 40  → insufficient_basis

        Args:
            score: Pre_Assessment_Score in [0, 100].

        Returns:
            Recommendation string.
        """
        if score > 70:
            return "open_investigation"
        elif score >= 40:
            return "need_more_evidence"
        else:
            return "insufficient_basis"

    # ─── Elements of Offense ──────────────────────────────────────────────────

    def _get_elements_of_offense(self, case_type: str) -> list:
        """Return legal elements of offense for the given case type.

        Args:
            case_type: One of the six valid antitrust case types.

        Returns:
            List of element strings for the case type.
        """
        return ELEMENTS_OF_OFFENSE.get(case_type, ELEMENTS_OF_OFFENSE["procurement_collusion"])

    # ─── Evidence Matrix ──────────────────────────────────────────────────────

    def _build_evidence_matrix(self, evidence: list, case_type: str) -> dict:
        """Map evidence items to elements of offense they support.

        Each element of offense becomes a key in the matrix. The value is a list
        of evidence items that support that element.

        Args:
            evidence: List of evidence dicts (each should have 'description',
                      'source', 'relevance', and optionally 'supports_elements').
            case_type: The classified case type.

        Returns:
            Dict mapping element names to lists of supporting evidence items.
        """
        elements = self._get_elements_of_offense(case_type)
        matrix = {element: [] for element in elements}

        for item in evidence:
            # Evidence items may declare which elements they support
            supported = item.get("supports_elements", [])

            if supported:
                for element in supported:
                    if element in matrix:
                        matrix[element].append(item)
            else:
                # If no explicit mapping, use keyword matching as fallback
                description = (item.get("description", "") or "").lower()
                source = (item.get("source", "") or "").lower()
                combined_text = f"{description} {source}"

                for element in elements:
                    # Simple keyword matching — element names use underscores
                    element_words = element.replace("_", " ").split()
                    if any(word in combined_text for word in element_words):
                        matrix[element].append(item)

        return matrix

    def _identify_evidence_gaps(self, evidence_matrix: dict, case_type: str) -> list:
        """Identify elements of offense not supported by evidence.

        For each unsupported element, generates a recommended action to fill
        the gap (subpoena, document request, witness interview, additional OSINT).

        Args:
            evidence_matrix: Output of _build_evidence_matrix.
            case_type: The classified case type.

        Returns:
            List of gap dicts with element, description, and recommended_action.
        """
        gaps = []
        elements = self._get_elements_of_offense(case_type)

        # Recommended actions per element type
        gap_actions = {
            "agreement_or_conspiracy": "Seek witness testimony or communications evidence (subpoena email/phone records)",
            "bid_rigging_or_complementary_bidding": "Obtain bid tabulation records from awarding agency (document request)",
            "market_allocation_among_conspirators": "Analyze geographic bid patterns in Redshift cross-case queries",
            "price_fixing_or_bid_suppression": "Obtain historical pricing data and bid submissions (document request)",
            "interstate_commerce_nexus": "Verify federal funding or interstate commerce connection (OSINT: USASpending.gov)",
            "damages_to_government_or_taxpayers": "Calculate overcharge estimates from competitive benchmark analysis",
            "agreement_among_competitors": "Seek direct evidence of communications or meetings between competitors",
            "fixing_or_stabilizing_prices": "Analyze price movement correlation across competitors (Redshift analytics)",
            "horizontal_relationship": "Verify competitive relationship through market analysis (OSINT: SAM.gov NAICS codes)",
            "per_se_violation_applicability": "Confirm conduct falls within per se category (legal analysis)",
            "geographic_or_customer_division": "Map geographic bid patterns to identify exclusivity (Redshift analytics)",
            "substantially_lessen_competition": "Conduct market concentration analysis (HHI calculation)",
            "relevant_market_definition": "Define product and geographic market boundaries (economic analysis)",
            "market_concentration_increase": "Calculate pre/post-merger HHI from market share data",
            "barriers_to_entry": "Identify regulatory, capital, or technological barriers (industry analysis)",
            "elimination_of_competition": "Document competitive overlap between merging parties",
            "hhi_threshold_exceeded": "Calculate HHI using market share data (Redshift analytics)",
            "monopoly_power_in_relevant_market": "Establish market share above 70% in defined relevant market",
            "willful_acquisition_or_maintenance": "Document exclusionary conduct pattern (OSINT: court records, contracts)",
            "anticompetitive_conduct": "Identify specific exclusionary acts (tying, exclusive dealing, predatory pricing)",
            "harm_to_competition": "Document impact on competitors and consumer welfare",
            "per_se_illegal_conduct": "Confirm conduct type (price-fixing, bid-rigging, market allocation)",
            "knowing_and_willful_participation": "Seek evidence of intent (communications, meeting records)",
            "identifiable_victims": "Identify affected government agencies or purchasers",
            "quantifiable_damages": "Calculate overcharge or damages amount from bid/price data",
        }

        for element in elements:
            supporting_evidence = evidence_matrix.get(element, [])
            if not supporting_evidence:
                gaps.append({
                    "element": element,
                    "description": f"No evidence currently supports: {element.replace('_', ' ')}",
                    "recommended_action": gap_actions.get(
                        element,
                        "Conduct additional OSINT research targeting this element",
                    ),
                })

        return gaps

    # ─── AI Legal Analysis ────────────────────────────────────────────────────

    def _invoke_legal_analysis(
        self,
        lead_id: str,
        evidence: list,
        case_type: str,
        elements: list,
        evidence_matrix: dict,
    ) -> dict:
        """Invoke Amazon Nova Pro for legal reasoning and component scoring.

        Args:
            lead_id: UUID of the lead.
            evidence: List of evidence items.
            case_type: Classified case type.
            elements: Elements of offense for this case type.
            evidence_matrix: Current evidence-to-element mapping.

        Returns:
            Dict with 'components' (scoring components) and 'legal_reasoning'.
        """
        prompt = self._build_assessment_prompt(
            evidence, case_type, elements, evidence_matrix
        )

        try:
            body = json.dumps({
                "messages": [
                    {
                        "role": "user",
                        "content": [{"text": prompt}],
                    }
                ],
                "system": [
                    {
                        "text": (
                            "You are a senior DOJ Antitrust Division prosecutor with "
                            "expertise in Sherman Act, Clayton Act, FTC Act, and federal "
                            "sentencing guidelines. Evaluate the evidence presented and "
                            "provide component scores and legal reasoning. Respond ONLY "
                            "with valid JSON."
                        )
                    }
                ],
                "inferenceConfig": {
                    "maxTokens": 4096,
                    "temperature": 0.2,
                },
            })

            response = self.bedrock_client.invoke_model(
                modelId=self.model_id,
                contentType="application/json",
                accept="application/json",
                body=body,
            )

            response_body = json.loads(response["body"].read())
            output_text = (
                response_body.get("output", {})
                .get("message", {})
                .get("content", [{}])[0]
                .get("text", "{}")
            )

            parsed = self._extract_json(output_text)
            return self._validate_analysis(parsed)

        except Exception as e:
            logger.error(f"Bedrock legal analysis failed for lead {lead_id}: {e}")
            # Return default component scores based on evidence coverage
            return self._fallback_analysis(evidence_matrix, elements)

    def _build_assessment_prompt(
        self,
        evidence: list,
        case_type: str,
        elements: list,
        evidence_matrix: dict,
    ) -> str:
        """Build the assessment prompt for Nova Pro.

        Args:
            evidence: List of evidence items.
            case_type: Classified case type.
            elements: Elements of offense.
            evidence_matrix: Evidence-to-element mapping.

        Returns:
            Formatted prompt string.
        """
        framework = self.FRAMEWORKS.get(case_type, "pcsf")
        supported_count = sum(
            1 for el in elements if evidence_matrix.get(el)
        )

        evidence_summary = json.dumps(evidence[:20], indent=2, default=str)
        elements_str = "\n".join(f"  - {el}" for el in elements)
        coverage_str = f"{supported_count}/{len(elements)} elements have supporting evidence"

        return f"""Evaluate the following pre-case evidence for a {case_type} investigation
using the {framework} scoring framework.

ELEMENTS OF OFFENSE:
{elements_str}

EVIDENCE COVERAGE: {coverage_str}

EVIDENCE ITEMS:
{evidence_summary}

Provide your analysis as JSON with this exact structure:
{{
    "components": {{
        "elements_satisfied": <0-100 score based on how many elements have supporting evidence>,
        "evidence_quality": <0-100 score based on admissibility and reliability of evidence>,
        "corroboration": <0-100 score based on independent source corroboration>,
        "pattern_strength": <0-100 score based on strength of identified patterns>
    }},
    "legal_reasoning": "<detailed legal analysis citing relevant statutes and explaining the assessment>"
}}

Score each component from 0 to 100. Be rigorous — pre-case evidence from OSINT
sources alone rarely exceeds 70 for evidence_quality without formal discovery."""

    def _validate_analysis(self, parsed: dict) -> dict:
        """Validate and normalize the AI analysis response.

        Ensures components are present and within valid ranges.

        Args:
            parsed: Parsed JSON from Bedrock response.

        Returns:
            Validated analysis dict.
        """
        components = parsed.get("components", {})
        validated_components = {}

        for key in self.SCORING_WEIGHTS:
            value = components.get(key, 0)
            try:
                value = int(value)
            except (TypeError, ValueError):
                value = 0
            validated_components[key] = max(0, min(100, value))

        return {
            "components": validated_components,
            "legal_reasoning": parsed.get("legal_reasoning", ""),
        }

    def _fallback_analysis(self, evidence_matrix: dict, elements: list) -> dict:
        """Generate fallback component scores when Bedrock is unavailable.

        Uses evidence coverage ratio as a heuristic for scoring.

        Args:
            evidence_matrix: Evidence-to-element mapping.
            elements: Elements of offense.

        Returns:
            Fallback analysis dict with components and reasoning.
        """
        supported_count = sum(
            1 for el in elements if evidence_matrix.get(el)
        )
        coverage_ratio = supported_count / max(len(elements), 1)

        # Heuristic scoring based on coverage
        elements_score = round(coverage_ratio * 100)
        # Without AI analysis, quality and corroboration are conservative
        quality_score = round(coverage_ratio * 50)
        corroboration_score = round(coverage_ratio * 40)
        pattern_score = round(coverage_ratio * 30)

        return {
            "components": {
                "elements_satisfied": elements_score,
                "evidence_quality": quality_score,
                "corroboration": corroboration_score,
                "pattern_strength": pattern_score,
            },
            "legal_reasoning": (
                f"Automated fallback assessment: {supported_count}/{len(elements)} "
                f"elements of offense have supporting evidence. AI legal analysis "
                f"unavailable — manual review recommended."
            ),
        }

    def _extract_json(self, text: str) -> dict:
        """Extract JSON from model response text.

        Handles responses that may include markdown code fences or extra text.

        Args:
            text: Raw text from Bedrock response.

        Returns:
            Parsed dict, or empty dict on failure.
        """
        # Try direct parse first
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            pass

        # Try extracting from markdown code fence
        if "```" in text:
            try:
                start = text.index("```") + 3
                # Skip optional language identifier
                if text[start:start + 4] == "json":
                    start += 4
                start = text.index("\n", start) + 1
                end = text.index("```", start)
                return json.loads(text[start:end])
            except (ValueError, json.JSONDecodeError):
                pass

        # Try finding JSON object boundaries
        try:
            start = text.index("{")
            # Find matching closing brace
            depth = 0
            for i, ch in enumerate(text[start:], start):
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        return json.loads(text[start:i + 1])
        except (ValueError, json.JSONDecodeError):
            pass

        logger.warning("Failed to extract JSON from model response")
        return {}

    # ─── Aurora Storage ───────────────────────────────────────────────────────

    def _store_assessment(self, result: AssessmentResult) -> None:
        """Store assessment result in Aurora pre_case_assessments table.

        Creates an AI_Proposed decision record.

        Args:
            result: The AssessmentResult to store.
        """
        try:
            with self.aurora_cm.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO pre_case_assessments
                        (assessment_id, lead_id, score, recommendation,
                         evidence_matrix, evidence_gaps, legal_reasoning,
                         statutes_cited, scoring_framework, model_version,
                         decision_status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        result.assessment_id,
                        result.lead_id,
                        result.score,
                        result.recommendation,
                        json.dumps(result.evidence_matrix, default=str),
                        json.dumps(result.evidence_gaps, default=str),
                        result.legal_reasoning,
                        json.dumps(result.statutes_cited),
                        result.scoring_framework,
                        self.model_id,
                        "ai_proposed",
                    ),
                )

                # Also update the lead's pre_assessment_score
                cur.execute(
                    """
                    UPDATE pre_case_leads
                    SET pre_assessment_score = %s, updated_at = NOW()
                    WHERE lead_id = %s
                    """,
                    (result.score, result.lead_id),
                )

        except Exception as e:
            logger.error(
                f"Failed to store assessment for lead {result.lead_id}: {e}"
            )
