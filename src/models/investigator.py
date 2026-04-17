"""Investigator AI-First data models."""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class DocumentTypeClassification(str, Enum):
    EMAIL = "email"
    FINANCIAL_RECORD = "financial_record"
    LEGAL_FILING = "legal_filing"
    TESTIMONY = "testimony"
    REPORT = "report"
    CORRESPONDENCE = "correspondence"
    OTHER = "other"


class ConfidenceLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ProsecutionReadinessImpact(str, Enum):
    STRENGTHENS = "strengthens"
    WEAKENS = "weakens"
    NEUTRAL = "neutral"


class DecisionState(str, Enum):
    AI_PROPOSED = "ai_proposed"
    HUMAN_CONFIRMED = "human_confirmed"
    HUMAN_OVERRIDDEN = "human_overridden"


class InvestigativeLead(BaseModel):
    lead_id: str
    case_id: str
    entity_name: str
    entity_type: str
    lead_priority_score: int = Field(ge=0, le=100)
    evidence_strength: float = Field(ge=0.0, le=1.0, default=0.0)
    connection_density: float = Field(ge=0.0, le=1.0, default=0.0)
    novelty: float = Field(ge=0.0, le=1.0, default=0.0)
    prosecution_readiness: float = Field(ge=0.0, le=1.0, default=0.0)
    ai_justification: str = ""
    recommended_actions: list[str] = []
    decision_id: Optional[str] = None
    decision_state: Optional[str] = None


class EvidenceTriageResult(BaseModel):
    triage_id: str
    case_id: str
    document_id: str
    doc_type_classification: DocumentTypeClassification
    identified_entities: list[dict] = []
    high_priority_findings: list[dict] = []
    linked_leads: list[str] = []
    prosecution_readiness_impact: ProsecutionReadinessImpact = ProsecutionReadinessImpact.NEUTRAL
    decision_id: Optional[str] = None
    decision_state: Optional[str] = None


class InvestigativeHypothesis(BaseModel):
    hypothesis_id: str
    case_id: str
    hypothesis_text: str
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM
    supporting_evidence: list[dict] = []
    recommended_actions: list[str] = []
    decision_id: Optional[str] = None
    decision_state: Optional[str] = None


class SubpoenaRecommendation(BaseModel):
    recommendation_id: str
    case_id: str
    target: str
    custodian: str = ""
    legal_basis: str = ""
    expected_evidentiary_value: ConfidenceLevel = ConfidenceLevel.MEDIUM
    priority_rank: int = Field(ge=1)
    decision_id: Optional[str] = None
    decision_state: Optional[str] = None


class CaseBriefing(BaseModel):
    narrative: str = ""
    key_findings: list[dict] = []
    statistics: dict = {}
    evidence_coverage: dict = {}
    recommended_next_steps: list[str] = []
    warnings: list[str] = []


class SessionBriefing(BaseModel):
    new_documents: int = 0
    new_entities: int = 0
    updated_leads: int = 0
    new_findings: int = 0
    narrative: str = ""
    recommended_actions: list[str] = []


class CaseAnalysisResult(BaseModel):
    case_id: str
    status: str = "completed"
    briefing: CaseBriefing = CaseBriefing()
    leads: list[InvestigativeLead] = []
    hypotheses: list[InvestigativeHypothesis] = []
    subpoena_recommendations: list[SubpoenaRecommendation] = []
    triage_results: list[EvidenceTriageResult] = []
    created_at: str = ""
