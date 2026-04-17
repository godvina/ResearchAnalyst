"""Element Assessment Service — AI evidence-element analysis engine.

Reuses the claim decomposition pattern from hypothesis_testing_service.py,
treating each statutory element as a testable claim evaluated against case
evidence via Amazon Bedrock with the Senior Legal Analyst Persona.

Every AI rating flows through the three-state Decision Workflow
(AI_Proposed → Human_Confirmed / Human_Overridden).
"""

import json
import logging
import uuid
from typing import Optional, Callable

from models.prosecutor import (
    AlternativeCharge,
    ChargingRecommendation,
    ConfidenceLevel,
    DecisionState,
    ElementMapping,
    ElementRating,
    EvidenceMatrix,
    ReadinessScore,
    StatuteRecommendation,
    StatutoryElement,
    SupportRating,
)

logger = logging.getLogger(__name__)

# Bedrock model used for all AI analysis
_MODEL_ID = "anthropic.claude-3-haiku-20240307-v1:0"


class ElementAssessmentService:
    """AI-powered evidence-element analysis engine for prosecutors."""

    SENIOR_LEGAL_ANALYST_PERSONA = (
        "You are a senior federal prosecutor (AUSA) with 20+ years of experience. "
        "Reason using proper legal terminology. Cite case law patterns and reference "
        "federal sentencing guidelines (USSG) where applicable. Provide thorough legal "
        "justifications for every recommendation."
    )

    def __init__(
        self,
        aurora_cm,
        neptune_cm,
        bedrock_client,
        search_fn: Optional[Callable] = None,
        decision_workflow_svc=None,
    ):
        self._db = aurora_cm
        self._neptune = neptune_cm
        self._bedrock = bedrock_client
        self._search = search_fn
        self._decision_svc = decision_workflow_svc

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def assess_elements(self, case_id: str, statute_id: str) -> EvidenceMatrix:
        """Assess all evidence against all elements for a statute.

        Fetches statutory elements from Aurora, case evidence from
        Aurora + Neptune, then calls Bedrock with the Senior Legal Analyst
        Persona for each element-evidence pair.  Each rating includes a
        legal_justification and starts as AI_Proposed via DecisionWorkflowService.
        """
        elements = self._fetch_elements(statute_id)
        evidence_items = self._fetch_evidence(case_id)

        ratings: list[ElementRating] = []
        for elem in elements:
            for ev in evidence_items:
                rating = self._rate_pair(case_id, elem, ev)
                ratings.append(rating)

        # Compute readiness inline
        total = len(elements) or 1
        covered = self._count_covered_elements(elements, ratings)
        score = round(covered / total * 100)

        return EvidenceMatrix(
            case_id=case_id,
            statute_id=statute_id,
            elements=elements,
            evidence_items=evidence_items,
            ratings=ratings,
            readiness_score=score,
        )

    def assess_single(
        self, case_id: str, element_id: str, evidence_id: str
    ) -> ElementRating:
        """Assess a single evidence-element pair with legal reasoning."""
        element = self._fetch_element_by_id(element_id)
        ev = {"evidence_id": evidence_id, "title": evidence_id, "type": "document"}
        return self._rate_pair(case_id, element, ev)

    def compute_readiness_score(
        self, case_id: str, statute_id: str
    ) -> ReadinessScore:
        """Compute prosecution readiness: round((green+yellow)/total * 100)."""
        elements = self._fetch_elements(statute_id)
        citation = self._fetch_citation(statute_id)
        evidence_items = self._fetch_evidence(case_id)

        ratings: list[ElementRating] = []
        for elem in elements:
            for ev in evidence_items:
                rating = self._rate_pair(case_id, elem, ev)
                ratings.append(rating)

        total = len(elements)
        if total == 0:
            return ReadinessScore(
                case_id=case_id,
                statute_id=statute_id,
                citation=citation,
                score=0,
                total_elements=0,
                covered_elements=0,
                missing_elements=[],
            )

        covered_set, missing_names = self._partition_elements(elements, ratings)
        covered = len(covered_set)
        score = round(covered / total * 100)

        return ReadinessScore(
            case_id=case_id,
            statute_id=statute_id,
            citation=citation,
            score=score,
            total_elements=total,
            covered_elements=covered,
            missing_elements=missing_names,
        )

    def suggest_alternative_charges(
        self, case_id: str, statute_id: str
    ) -> list[AlternativeCharge]:
        """When primary charge has red elements, suggest up to 5 alternatives
        sorted by estimated_conviction_likelihood descending."""
        elements = self._fetch_elements(statute_id)
        evidence_items = self._fetch_evidence(case_id)

        # Gather red element descriptions for context
        red_descriptions: list[str] = []
        for elem in elements:
            best = SupportRating.RED
            for ev in evidence_items:
                r = self._rate_pair(case_id, elem, ev)
                if r.rating == SupportRating.GREEN:
                    best = SupportRating.GREEN
                    break
                if r.rating == SupportRating.YELLOW:
                    best = SupportRating.YELLOW
            if best == SupportRating.RED:
                red_descriptions.append(elem.display_name)

        if not red_descriptions:
            return []

        return self._bedrock_suggest_alternatives(case_id, statute_id, red_descriptions)

    def recommend_statutes(self, case_id: str) -> list[StatuteRecommendation]:
        """Auto-recommend applicable statutes ranked by evidence match strength.

        Returns justification for each recommendation and explains why
        alternative statutes were considered and rejected.
        """
        evidence_items = self._fetch_evidence(case_id)
        if not evidence_items:
            return []

        return self._bedrock_recommend_statutes(case_id, evidence_items)

    def auto_categorize_evidence(
        self, case_id: str, evidence_id: str, statute_id: str
    ) -> list[ElementMapping]:
        """Auto-map new evidence to the most relevant statutory elements."""
        elements = self._fetch_elements(statute_id)
        if not elements:
            return []

        return self._bedrock_categorize_evidence(case_id, evidence_id, elements)

    def draft_charging_recommendation(
        self, case_id: str, statute_id: str
    ) -> ChargingRecommendation:
        """Draft initial charging recommendation when readiness >= 70%."""
        readiness = self.compute_readiness_score(case_id, statute_id)
        if readiness.score < 70:
            return ChargingRecommendation(
                case_id=case_id,
                statute_id=statute_id,
                recommendation_text="Insufficient evidence for charging recommendation.",
                legal_reasoning="Readiness score below 70% threshold.",
                sentencing_guideline_refs=[],
                confidence=ConfidenceLevel.LOW,
            )

        return self._bedrock_draft_recommendation(case_id, statute_id, readiness)

    # ------------------------------------------------------------------
    # Bedrock interaction helpers
    # ------------------------------------------------------------------

    def _rate_pair(
        self, case_id: str, element: StatutoryElement, evidence: dict
    ) -> ElementRating:
        """Rate a single element-evidence pair via Bedrock."""
        if not self._bedrock:
            return self._fallback_rating(element.element_id, evidence["evidence_id"])

        prompt = (
            f"Evaluate whether this evidence supports the following statutory element.\n\n"
            f"Statutory Element: {element.display_name}\n"
            f"Element Description: {element.description}\n"
            f"Evidence ID: {evidence.get('evidence_id', 'unknown')}\n"
            f"Evidence Title: {evidence.get('title', 'unknown')}\n"
            f"Evidence Type: {evidence.get('type', 'unknown')}\n\n"
            f"Return JSON: {{\"rating\": \"green\"|\"yellow\"|\"red\", "
            f"\"confidence\": 0-100, \"reasoning\": \"...\", "
            f"\"legal_justification\": \"...\"}}\n"
            f"Return ONLY JSON."
        )

        try:
            result = self._invoke_bedrock(prompt)
            rating_val = result.get("rating", "yellow")
            if rating_val not in ("green", "yellow", "red"):
                rating_val = "yellow"
            confidence = max(0, min(100, int(result.get("confidence", 50))))
            reasoning = result.get("reasoning", "")
            legal_just = result.get("legal_justification", "")

            er = ElementRating(
                element_id=element.element_id,
                evidence_id=evidence["evidence_id"],
                rating=SupportRating(rating_val),
                confidence=confidence,
                reasoning=reasoning,
                legal_justification=legal_just,
                decision_state=DecisionState.AI_PROPOSED,
            )

            # Create AI_Proposed decision if workflow service available
            if self._decision_svc:
                decision = self._decision_svc.create_decision(
                    case_id=case_id,
                    decision_type="element_rating",
                    recommendation_text=f"Rate {element.display_name} as {rating_val}",
                    legal_reasoning=legal_just,
                    confidence=self._map_confidence(confidence),
                    source_service="element_assessment",
                )
                er.decision_id = decision.decision_id

            return er
        except Exception as e:
            logger.warning("Bedrock rating failed: %s", e)
            return self._fallback_rating(element.element_id, evidence["evidence_id"])

    def _bedrock_suggest_alternatives(
        self, case_id: str, statute_id: str, red_elements: list[str]
    ) -> list[AlternativeCharge]:
        """Use Bedrock to suggest alternative charges."""
        if not self._bedrock:
            return []

        prompt = (
            f"The primary charge (statute {statute_id}) has unsupported elements: "
            f"{', '.join(red_elements)}.\n\n"
            f"Suggest up to 5 alternative federal charges that may be easier to prove "
            f"given the available evidence. For each, provide:\n"
            f"- statute_id, citation, title\n"
            f"- estimated_conviction_likelihood (0-100)\n"
            f"- reasoning\n\n"
            f"Return a JSON array sorted by estimated_conviction_likelihood descending.\n"
            f"Return ONLY the JSON array."
        )

        try:
            results = self._invoke_bedrock_list(prompt)
            alternatives = []
            for item in results[:5]:
                alternatives.append(
                    AlternativeCharge(
                        statute_id=item.get("statute_id", str(uuid.uuid4())),
                        citation=item.get("citation", "Unknown"),
                        title=item.get("title", "Unknown"),
                        estimated_conviction_likelihood=max(
                            0, min(100, int(item.get("estimated_conviction_likelihood", 50)))
                        ),
                        reasoning=item.get("reasoning", ""),
                    )
                )
            # Ensure sorted descending by likelihood
            alternatives.sort(
                key=lambda x: x.estimated_conviction_likelihood, reverse=True
            )
            return alternatives[:5]
        except Exception as e:
            logger.warning("Bedrock alternative charges failed: %s", e)
            return []

    def _bedrock_recommend_statutes(
        self, case_id: str, evidence_items: list[dict]
    ) -> list[StatuteRecommendation]:
        """Use Bedrock to recommend applicable statutes."""
        if not self._bedrock:
            return []

        evidence_summary = "\n".join(
            f"- {ev.get('title', 'unknown')} ({ev.get('type', 'unknown')})"
            for ev in evidence_items[:20]
        )

        prompt = (
            f"Based on the following case evidence, recommend the most applicable "
            f"federal statutes ranked by evidence match strength.\n\n"
            f"Evidence:\n{evidence_summary}\n\n"
            f"For each recommended statute, provide:\n"
            f"- statute_id, citation, title\n"
            f"- match_strength (0-100)\n"
            f"- justification (legal reasoning)\n"
            f"- confidence (high/medium/low)\n"
            f"- rejected_alternatives: list of {{citation, reason_rejected}}\n\n"
            f"Return a JSON array sorted by match_strength descending.\n"
            f"Return ONLY the JSON array."
        )

        try:
            results = self._invoke_bedrock_list(prompt)
            recommendations = []
            for item in results:
                rejected = item.get("rejected_alternatives", [])
                if not isinstance(rejected, list):
                    rejected = []
                recommendations.append(
                    StatuteRecommendation(
                        statute_id=item.get("statute_id", str(uuid.uuid4())),
                        citation=item.get("citation", "Unknown"),
                        title=item.get("title", "Unknown"),
                        match_strength=max(
                            0, min(100, int(item.get("match_strength", 50)))
                        ),
                        justification=item.get("justification", "AI-generated recommendation"),
                        confidence=ConfidenceLevel(
                            item.get("confidence", "medium")
                        ),
                        rejected_alternatives=rejected,
                    )
                )
            recommendations.sort(key=lambda x: x.match_strength, reverse=True)
            return recommendations
        except Exception as e:
            logger.warning("Bedrock statute recommendation failed: %s", e)
            return []

    def _bedrock_categorize_evidence(
        self, case_id: str, evidence_id: str, elements: list[StatutoryElement]
    ) -> list[ElementMapping]:
        """Use Bedrock to auto-map evidence to statutory elements."""
        if not self._bedrock:
            return []

        element_desc = "\n".join(
            f"- {e.element_id}: {e.display_name} — {e.description}"
            for e in elements
        )

        prompt = (
            f"Map evidence item '{evidence_id}' to the most relevant statutory elements.\n\n"
            f"Statutory Elements:\n{element_desc}\n\n"
            f"For each mapping, provide:\n"
            f"- element_id\n"
            f"- justification (cite specific evidentiary basis)\n"
            f"- confidence (high/medium/low)\n\n"
            f"Return a JSON array.\nReturn ONLY the JSON array."
        )

        try:
            results = self._invoke_bedrock_list(prompt)
            mappings = []
            valid_ids = {e.element_id for e in elements}
            for item in results:
                eid = item.get("element_id", "")
                if eid not in valid_ids:
                    continue
                mapping = ElementMapping(
                    evidence_id=evidence_id,
                    element_id=eid,
                    justification=item.get("justification", "AI-generated mapping"),
                    confidence=ConfidenceLevel(item.get("confidence", "medium")),
                )
                if self._decision_svc:
                    decision = self._decision_svc.create_decision(
                        case_id=case_id,
                        decision_type="evidence_mapping",
                        recommendation_text=f"Map {evidence_id} to element {eid}",
                        legal_reasoning=mapping.justification,
                        confidence=mapping.confidence.value,
                        source_service="element_assessment",
                    )
                    mapping.decision_id = decision.decision_id
                mappings.append(mapping)
            return mappings
        except Exception as e:
            logger.warning("Bedrock evidence categorization failed: %s", e)
            return []

    def _bedrock_draft_recommendation(
        self, case_id: str, statute_id: str, readiness: ReadinessScore
    ) -> ChargingRecommendation:
        """Use Bedrock to draft a charging recommendation."""
        if not self._bedrock:
            return ChargingRecommendation(
                case_id=case_id,
                statute_id=statute_id,
                recommendation_text="AI analysis unavailable",
                legal_reasoning="AI analysis unavailable",
                sentencing_guideline_refs=[],
                confidence=ConfidenceLevel.LOW,
            )

        prompt = (
            f"Draft a charging recommendation for case {case_id} under statute "
            f"{readiness.citation} (statute_id: {statute_id}).\n\n"
            f"Readiness: {readiness.score}% ({readiness.covered_elements}/{readiness.total_elements} elements covered)\n"
            f"Missing elements: {', '.join(readiness.missing_elements) if readiness.missing_elements else 'None'}\n\n"
            f"Provide:\n"
            f"- recommendation_text: full charging recommendation\n"
            f"- legal_reasoning: cite precedent patterns and sentencing guidelines\n"
            f"- sentencing_guideline_refs: list of applicable USSG sections\n"
            f"- confidence: high/medium/low\n\n"
            f"Return JSON object.\nReturn ONLY JSON."
        )

        try:
            result = self._invoke_bedrock(prompt)
            refs = result.get("sentencing_guideline_refs", [])
            if not isinstance(refs, list):
                refs = [str(refs)]
            if not refs:
                refs = ["USSG §2B1.1"]

            rec = ChargingRecommendation(
                case_id=case_id,
                statute_id=statute_id,
                recommendation_text=result.get(
                    "recommendation_text", "Charging recommended based on evidence."
                ),
                legal_reasoning=result.get(
                    "legal_reasoning", "Sufficient evidence mapped to statutory elements."
                ),
                sentencing_guideline_refs=refs,
                confidence=ConfidenceLevel(result.get("confidence", "medium")),
            )

            if self._decision_svc:
                decision = self._decision_svc.create_decision(
                    case_id=case_id,
                    decision_type="charging_recommendation",
                    recommendation_text=rec.recommendation_text,
                    legal_reasoning=rec.legal_reasoning,
                    confidence=rec.confidence.value,
                    source_service="element_assessment",
                )
                rec.decision_id = decision.decision_id

            return rec
        except Exception as e:
            logger.warning("Bedrock charging recommendation failed: %s", e)
            return ChargingRecommendation(
                case_id=case_id,
                statute_id=statute_id,
                recommendation_text="AI analysis unavailable",
                legal_reasoning="AI analysis unavailable",
                sentencing_guideline_refs=[],
                confidence=ConfidenceLevel.LOW,
            )

    # ------------------------------------------------------------------
    # Bedrock invocation
    # ------------------------------------------------------------------

    def _invoke_bedrock(self, prompt: str) -> dict:
        """Invoke Bedrock and parse a JSON object response."""
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 2048,
            "system": self.SENIOR_LEGAL_ANALYST_PERSONA,
            "messages": [{"role": "user", "content": prompt}],
        })
        resp = self._bedrock.invoke_model(
            modelId=_MODEL_ID, body=body
        )
        text = json.loads(resp["body"].read()).get("content", [{}])[0].get("text", "{}")
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
        return {}

    def _invoke_bedrock_list(self, prompt: str) -> list[dict]:
        """Invoke Bedrock and parse a JSON array response."""
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 4096,
            "system": self.SENIOR_LEGAL_ANALYST_PERSONA,
            "messages": [{"role": "user", "content": prompt}],
        })
        resp = self._bedrock.invoke_model(
            modelId=_MODEL_ID, body=body
        )
        text = json.loads(resp["body"].read()).get("content", [{}])[0].get("text", "[]")
        start = text.find("[")
        end = text.rfind("]") + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
        return []

    # ------------------------------------------------------------------
    # Data access helpers
    # ------------------------------------------------------------------

    def _fetch_elements(self, statute_id: str) -> list[StatutoryElement]:
        """Fetch statutory elements for a statute from Aurora."""
        if not self._db:
            return []
        try:
            with self._db.cursor() as cur:
                cur.execute(
                    "SELECT element_id, statute_id, display_name, description, element_order "
                    "FROM statutory_elements WHERE statute_id = %s ORDER BY element_order",
                    (statute_id,),
                )
                rows = cur.fetchall()
                return [
                    StatutoryElement(
                        element_id=str(r[0]),
                        statute_id=str(r[1]),
                        display_name=r[2],
                        description=r[3],
                        element_order=r[4],
                    )
                    for r in rows
                ]
        except Exception as e:
            logger.warning("Failed to fetch elements: %s", e)
            return []

    def _fetch_element_by_id(self, element_id: str) -> StatutoryElement:
        """Fetch a single statutory element by ID."""
        if self._db:
            try:
                with self._db.cursor() as cur:
                    cur.execute(
                        "SELECT element_id, statute_id, display_name, description, element_order "
                        "FROM statutory_elements WHERE element_id = %s",
                        (element_id,),
                    )
                    r = cur.fetchone()
                    if r:
                        return StatutoryElement(
                            element_id=str(r[0]),
                            statute_id=str(r[1]),
                            display_name=r[2],
                            description=r[3],
                            element_order=r[4],
                        )
            except Exception as e:
                logger.warning("Failed to fetch element: %s", e)

        # Fallback placeholder
        return StatutoryElement(
            element_id=element_id,
            statute_id="unknown",
            display_name=element_id,
            description="Unknown element",
            element_order=0,
        )

    def _fetch_evidence(self, case_id: str) -> list[dict]:
        """Fetch case evidence from Aurora + Neptune."""
        items: list[dict] = []

        # Aurora documents
        if self._db:
            try:
                with self._db.cursor() as cur:
                    cur.execute(
                        "SELECT document_id, filename, doc_type FROM case_documents "
                        "WHERE case_id = %s",
                        (case_id,),
                    )
                    for r in cur.fetchall():
                        items.append({
                            "evidence_id": str(r[0]),
                            "title": r[1],
                            "type": r[2] or "document",
                        })
            except Exception as e:
                logger.warning("Failed to fetch Aurora evidence: %s", e)

        # Neptune entities
        if self._neptune:
            try:
                with self._neptune.cursor() as cur:
                    cur.execute(
                        "g.V().has('case_id', case_id).valueMap(true)",
                        {"case_id": case_id},
                    )
                    for r in cur.fetchall():
                        eid = str(r.get("id", r.get("entity_id", uuid.uuid4())))
                        items.append({
                            "evidence_id": eid,
                            "title": r.get("name", [eid])[0] if isinstance(r.get("name"), list) else r.get("name", eid),
                            "type": "entity",
                        })
            except Exception as e:
                logger.warning("Failed to fetch Neptune evidence: %s", e)

        # Search-based evidence
        if self._search:
            try:
                search_results = self._search(case_id, "case evidence")
                for sr in (search_results or []):
                    items.append({
                        "evidence_id": sr.get("id", str(uuid.uuid4())),
                        "title": sr.get("title", sr.get("filename", "search result")),
                        "type": "search",
                    })
            except Exception as e:
                logger.warning("Failed to fetch search evidence: %s", e)

        return items

    def _fetch_citation(self, statute_id: str) -> str:
        """Fetch the citation string for a statute."""
        if not self._db:
            return statute_id
        try:
            with self._db.cursor() as cur:
                cur.execute(
                    "SELECT citation FROM statutes WHERE statute_id = %s",
                    (statute_id,),
                )
                row = cur.fetchone()
                return row[0] if row else statute_id
        except Exception as e:
            logger.warning("Failed to fetch citation: %s", e)
            return statute_id

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _fallback_rating(element_id: str, evidence_id: str) -> ElementRating:
        """Bedrock fallback: yellow / 0 / unavailable."""
        return ElementRating(
            element_id=element_id,
            evidence_id=evidence_id,
            rating=SupportRating.YELLOW,
            confidence=0,
            reasoning="AI analysis unavailable",
            legal_justification="",
            decision_state=DecisionState.AI_PROPOSED,
        )

    @staticmethod
    def _count_covered_elements(
        elements: list[StatutoryElement], ratings: list[ElementRating]
    ) -> int:
        """Count elements that have at least one green or yellow rating."""
        covered = set()
        for r in ratings:
            if r.rating in (SupportRating.GREEN, SupportRating.YELLOW):
                covered.add(r.element_id)
        return len(covered)

    @staticmethod
    def _partition_elements(
        elements: list[StatutoryElement], ratings: list[ElementRating]
    ) -> tuple[set[str], list[str]]:
        """Partition elements into covered (green/yellow) and missing (red-only)."""
        covered = set()
        for r in ratings:
            if r.rating in (SupportRating.GREEN, SupportRating.YELLOW):
                covered.add(r.element_id)
        missing = [e.display_name for e in elements if e.element_id not in covered]
        return covered, missing

    @staticmethod
    def _map_confidence(score: int) -> str:
        """Map a numeric confidence score to high/medium/low."""
        if score >= 75:
            return "high"
        if score >= 40:
            return "medium"
        return "low"

