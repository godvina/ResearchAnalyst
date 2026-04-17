"""Prosecutor Case Review data models.

Pydantic models for element-by-element evidence mapping, charging decisions,
case weakness analysis, precedent matching, AI-first analysis, and the
three-state human-in-the-loop decision workflow.
"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# --- Enums ---


class SupportRating(str, Enum):
    """Evidence support rating for an element-evidence pair."""

    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"


class ConfidenceLevel(str, Enum):
    """AI recommendation confidence level."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class DecisionState(str, Enum):
    """Three-state human-in-the-loop decision workflow."""

    AI_PROPOSED = "ai_proposed"
    HUMAN_CONFIRMED = "human_confirmed"
    HUMAN_OVERRIDDEN = "human_overridden"


class WeaknessSeverity(str, Enum):
    """Severity classification for case weaknesses."""

    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


class WeaknessType(str, Enum):
    """Types of case weaknesses detected by the analyzer."""

    CONFLICTING_STATEMENTS = "conflicting_statements"
    MISSING_CORROBORATION = "missing_corroboration"
    SUPPRESSION_RISK = "suppression_risk"
    BRADY_MATERIAL = "brady_material"


class RulingOutcome(str, Enum):
    """Possible ruling outcomes for precedent cases."""

    GUILTY = "guilty"
    NOT_GUILTY = "not_guilty"
    PLEA_DEAL = "plea_deal"
    DISMISSED = "dismissed"
    SETTLED = "settled"


# --- Models ---


class StatutoryElement(BaseModel):
    """A discrete legal requirement that must be proven for conviction."""

    element_id: str
    statute_id: str
    display_name: str
    description: str
    element_order: int


class Statute(BaseModel):
    """A federal statute with its required elements."""

    statute_id: str
    citation: str
    title: str
    description: Optional[str] = None
    elements: list[StatutoryElement] = []


class ElementRating(BaseModel):
    """AI-assessed support rating for a single evidence-element pair."""

    element_id: str
    evidence_id: str
    rating: SupportRating
    confidence: int = Field(ge=0, le=100)
    reasoning: str = ""
    legal_justification: str = ""
    decision_id: Optional[str] = None
    decision_state: DecisionState = DecisionState.AI_PROPOSED


class EvidenceMatrix(BaseModel):
    """Grid mapping evidence items to statutory elements with ratings."""

    case_id: str
    statute_id: str
    elements: list[StatutoryElement]
    evidence_items: list[dict]  # [{evidence_id, title, type}]
    ratings: list[ElementRating]
    readiness_score: int = Field(ge=0, le=100)


class ReadinessScore(BaseModel):
    """Prosecution readiness score for a case-statute pair."""

    case_id: str
    statute_id: str
    citation: str
    score: int = Field(ge=0, le=100)
    total_elements: int
    covered_elements: int  # green + yellow
    missing_elements: list[str]  # element display names


class CaseWeakness(BaseModel):
    """A flagged weakness in the case with legal reasoning."""

    weakness_id: str
    case_id: str
    weakness_type: WeaknessType
    severity: WeaknessSeverity
    description: str
    legal_reasoning: str = ""
    affected_elements: list[str] = []
    affected_evidence: list[str] = []
    remediation: Optional[str] = None


class PrecedentMatch(BaseModel):
    """A historically similar case matched by the precedent analyzer."""

    precedent_id: str
    case_reference: str
    charge_type: str
    ruling: RulingOutcome
    sentence: Optional[str] = None
    similarity_score: int = Field(ge=0, le=100)
    key_factors: list[str] = []
    judge: Optional[str] = None
    jurisdiction: Optional[str] = None


class RulingDistribution(BaseModel):
    """Outcome percentages across matched precedent cases."""

    guilty_pct: float
    not_guilty_pct: float
    plea_deal_pct: float
    dismissed_pct: float
    settled_pct: float
    total_cases: int


class SentencingAdvisory(BaseModel):
    """AI-generated sentencing advisory citing precedent and guidelines."""

    likely_sentence: str
    fine_or_penalty: str
    supervised_release: str
    precedent_match_pct: int
    disclaimer: Optional[str] = None


class AlternativeCharge(BaseModel):
    """An alternative charge suggestion when primary charge has red elements."""

    statute_id: str
    citation: str
    title: str
    estimated_conviction_likelihood: int = Field(ge=0, le=100)
    reasoning: str


class ChargingMemo(BaseModel):
    """Exportable charging memo document."""

    case_id: str
    case_summary: str
    selected_charges: list[dict]
    evidence_mapping_summary: str
    risk_assessment: str
    rationale: str
    approving_attorney: str
    generated_at: str


class StatuteRecommendation(BaseModel):
    """AI-recommended statute ranked by evidence match strength."""

    statute_id: str
    citation: str
    title: str
    match_strength: int = Field(ge=0, le=100)
    justification: str
    confidence: ConfidenceLevel
    rejected_alternatives: list[dict] = []  # [{citation, reason_rejected}]


class ElementMapping(BaseModel):
    """Auto-mapping of evidence to a statutory element."""

    evidence_id: str
    element_id: str
    justification: str
    confidence: ConfidenceLevel
    decision_id: Optional[str] = None


class ChargingRecommendation(BaseModel):
    """AI-drafted charging recommendation with legal reasoning."""

    case_id: str
    statute_id: str
    recommendation_text: str
    legal_reasoning: str
    sentencing_guideline_refs: list[str] = []
    confidence: ConfidenceLevel
    decision_id: Optional[str] = None


class AIDecision(BaseModel):
    """An AI recommendation tracked through the three-state decision workflow."""

    decision_id: str
    case_id: str
    decision_type: str
    state: DecisionState
    recommendation_text: str
    legal_reasoning: Optional[str] = None
    confidence: ConfidenceLevel
    source_service: Optional[str] = None
    related_entity_id: Optional[str] = None
    related_entity_type: Optional[str] = None
    confirmed_at: Optional[str] = None
    confirmed_by: Optional[str] = None
    overridden_at: Optional[str] = None
    overridden_by: Optional[str] = None
    override_rationale: Optional[str] = None
    created_at: str
    updated_at: str


class DecisionAuditEntry(BaseModel):
    """A single entry in the decision audit trail."""

    audit_id: str
    decision_id: str
    previous_state: Optional[str] = None
    new_state: str
    actor: str
    rationale: Optional[str] = None
    created_at: str


class CaseAnalysisResult(BaseModel):
    """Complete result of AI-first auto-analysis on case load."""

    case_id: str
    statute_recommendations: list[StatuteRecommendation] = []
    element_mappings: list[ElementMapping] = []
    weaknesses: list[CaseWeakness] = []
    charging_recommendation: Optional[ChargingRecommendation] = None
    decisions_created: list[str] = []
    warnings: list[str] = []
