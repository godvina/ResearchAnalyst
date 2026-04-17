"""Data models for AI Investigative Search.

Defines request/response schemas, assessment structures, and findings
persistence models. Uses Optional[type] for Python 3.10 Lambda compatibility.
"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ConfidenceLevel(str, Enum):
    STRONG_CASE = "strong_case"
    NEEDS_MORE_EVIDENCE = "needs_more_evidence"
    INSUFFICIENT = "insufficient"


class CaseViability(str, Enum):
    VIABLE = "viable"
    PROMISING = "promising"
    INSUFFICIENT = "insufficient"


class FindingType(str, Enum):
    SEARCH_RESULT = "search_result"
    ENTITY_LIST = "entity_list"
    LEAD_ASSESSMENT = "lead_assessment"
    MANUAL_NOTE = "manual_note"


# ---------------------------------------------------------------------------
# Assessment sub-models
# ---------------------------------------------------------------------------


class EvidenceCitation(BaseModel):
    document_id: str
    source_filename: str
    page_number: Optional[int] = None
    chunk_index: Optional[int] = None
    text_excerpt: str
    relevance_score: float


class GraphConnection(BaseModel):
    source_entity: str
    target_entity: str
    relationship_type: str
    properties: dict = Field(default_factory=dict)
    source_documents: list = Field(default_factory=list)


class EvidenceGap(BaseModel):
    area: str
    suggestion: str


class NextStep(BaseModel):
    action: str
    priority: int  # 1 = highest
    rationale: str


class CrossReferenceEntry(BaseModel):
    finding: str
    category: str  # confirmed_internally | external_only | needs_research
    internal_evidence: list = Field(default_factory=list)
    external_source: Optional[str] = None


class ExtractedQueryEntity(BaseModel):
    name: str
    type: str  # person | organization | location | event
    aliases: list = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Main assessment response
# ---------------------------------------------------------------------------


class InvestigativeAssessment(BaseModel):
    query: str
    case_id: str
    search_scope: str = "internal"
    confidence_level: ConfidenceLevel = ConfidenceLevel.INSUFFICIENT
    executive_summary: str = ""
    internal_evidence: list = Field(default_factory=list)
    graph_connections: list = Field(default_factory=list)
    ai_analysis: str = ""
    evidence_gaps: list = Field(default_factory=list)
    recommended_next_steps: list = Field(default_factory=list)
    cross_reference_report: Optional[list] = None
    raw_search_results: list = Field(default_factory=list)
    entities_extracted: list = Field(default_factory=list)
    synthesis_error: Optional[str] = None


class LeadAssessmentResponse(BaseModel):
    lead_id: str
    case_id: str
    case_viability: CaseViability = CaseViability.INSUFFICIENT
    subjects_assessed: int = 0
    subject_assessments: list = Field(default_factory=list)
    cross_subject_connections: list = Field(default_factory=list)
    consolidated_summary: str = ""
    job_id: Optional[str] = None
    status: str = "complete"  # complete | processing | failed


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class InvestigativeSearchRequest(BaseModel):
    query: str = Field(min_length=1)
    search_scope: str = Field(default="internal")
    top_k: int = Field(default=10, ge=1, le=50)
    output_format: str = Field(default="full")


class LeadAssessmentRequest(BaseModel):
    lead_id: str = Field(min_length=1)
    subjects: list = Field(min_length=1)
    osint_directives: list = Field(default_factory=list)
    evidence_hints: list = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Findings persistence models
# ---------------------------------------------------------------------------


class SaveFindingRequest(BaseModel):
    query: Optional[str] = None
    finding_type: str = "search_result"
    title: str = Field(min_length=1, max_length=500)
    summary: Optional[str] = None
    full_assessment: Optional[dict] = None
    source_citations: list = Field(default_factory=list)
    entity_names: list = Field(default_factory=list)
    tags: list = Field(default_factory=list)
    investigator_notes: Optional[str] = None
    confidence_level: Optional[str] = None


class UpdateFindingRequest(BaseModel):
    investigator_notes: Optional[str] = None
    tags: Optional[list] = None
    is_key_evidence: Optional[bool] = None
    needs_follow_up: Optional[bool] = None


class FindingResponse(BaseModel):
    finding_id: str
    case_id: str
    user_id: str
    query: Optional[str] = None
    finding_type: str
    title: str
    summary: Optional[str] = None
    source_citations: list = Field(default_factory=list)
    entity_names: list = Field(default_factory=list)
    tags: list = Field(default_factory=list)
    investigator_notes: Optional[str] = None
    confidence_level: Optional[str] = None
    is_key_evidence: bool = False
    needs_follow_up: bool = False
    created_at: str = ""
    updated_at: str = ""
