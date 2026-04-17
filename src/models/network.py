"""Conspiracy Network Discovery data models."""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class RiskLevel(str, Enum):
    """Risk classification for a person of interest."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class PatternType(str, Enum):
    """Types of hidden patterns detected in case evidence."""

    FINANCIAL = "financial"
    COMMUNICATION = "communication"
    GEOGRAPHIC = "geographic"
    TEMPORAL = "temporal"


class AnalysisStatus(str, Enum):
    """Status of a network analysis run."""

    PROCESSING = "processing"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"


class InvolvementScore(BaseModel):
    """Composite involvement score with per-factor breakdown."""

    total: int = Field(ge=0, le=100)
    connections: int = Field(ge=0, le=100)
    co_occurrence: int = Field(ge=0, le=100)
    financial: int = Field(ge=0, le=100)
    communication: int = Field(ge=0, le=100)
    geographic: int = Field(ge=0, le=100)


class CentralityScores(BaseModel):
    """Centrality measures for a single entity."""

    betweenness: float = Field(ge=0.0)
    degree: int = Field(ge=0)
    pagerank: float = Field(ge=0.0)


class CommunityCluster(BaseModel):
    """A cluster of tightly connected entities from community detection."""

    cluster_id: str
    entity_names: list[str]
    entity_count: int
    avg_internal_degree: float = 0.0


class EvidenceReference(BaseModel):
    """Reference to a document mentioning a person of interest."""

    document_id: str
    document_name: str
    mention_context: str = ""
    page_number: Optional[int] = None


class RelationshipEntry(BaseModel):
    """A single relationship in a co-conspirator's relationship map."""

    entity_name: str
    relationship_type: str
    edge_weight: float = 0.0


class CoConspiratorProfile(BaseModel):
    """Full dossier for an identified person of interest."""

    profile_id: str
    case_id: str
    entity_name: str
    entity_type: str
    aliases: list[str] = []
    involvement_score: InvolvementScore
    connection_strength: int = Field(ge=0, le=100)
    risk_level: RiskLevel
    evidence_summary: list[EvidenceReference] = []
    relationship_map: list[RelationshipEntry] = []
    document_type_count: int = 0
    potential_charges: list[dict] = []
    ai_legal_reasoning: str = ""
    decision_id: Optional[str] = None
    decision_state: Optional[str] = None


class NetworkPattern(BaseModel):
    """A detected hidden pattern in case evidence."""

    pattern_id: str
    case_id: str
    pattern_type: PatternType
    description: str
    confidence_score: int = Field(ge=0, le=100)
    entities_involved: list[dict] = []
    evidence_documents: list[dict] = []
    ai_reasoning: str = ""
    decision_id: Optional[str] = None
    decision_state: Optional[str] = None


class CaseInitiationBrief(BaseModel):
    """AI-generated brief for a proposed sub-case."""

    proposed_charges: list[dict] = []
    evidence_summary: str = ""
    investigative_steps: list[dict] = []
    full_brief: str = ""


class SubCaseProposal(BaseModel):
    """A proposal to create a sub-case for a co-conspirator."""

    proposal_id: str
    parent_case_id: str
    profile_id: str
    sub_case_id: Optional[str] = None
    brief: CaseInitiationBrief
    decision_id: Optional[str] = None
    status: str = "proposed"


class NetworkAnalysisResult(BaseModel):
    """Complete result of a network analysis run."""

    analysis_id: str
    case_id: str
    analysis_status: AnalysisStatus
    primary_subject: Optional[str] = None
    total_entities_analyzed: int = 0
    persons_of_interest: list[CoConspiratorProfile] = []
    patterns: list[NetworkPattern] = []
    sub_case_proposals: list[SubCaseProposal] = []
    communities: list[CommunityCluster] = []
    created_at: str = ""
    completed_at: Optional[str] = None
