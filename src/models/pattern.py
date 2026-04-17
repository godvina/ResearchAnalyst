"""Pattern discovery and cross-case analysis data models."""

from enum import Enum

from pydantic import BaseModel, Field


class Pattern(BaseModel):
    """A discovered connection between entities — graph-based, vector-based, or combined."""

    pattern_id: str
    entities_involved: list[dict]
    connection_type: str
    explanation: str
    confidence_score: float = Field(ge=0.0, le=1.0)
    novelty_score: float = Field(ge=0.0, le=1.0)
    source_documents: list[str] = Field(default_factory=list)


class PatternReport(BaseModel):
    """Aggregated pattern discovery results for a case file."""

    report_id: str
    case_file_id: str
    patterns: list[Pattern] = Field(default_factory=list)
    graph_patterns_count: int = Field(default=0, ge=0)
    vector_patterns_count: int = Field(default=0, ge=0)
    combined_count: int = Field(default=0, ge=0)


class CrossCaseMatch(BaseModel):
    """A matched entity pair across two different case files."""

    entity_a: dict
    entity_b: dict
    similarity_score: float = Field(ge=0.0, le=1.0)
    ai_explanation: str = ""


class CrossReferenceReport(BaseModel):
    """Full cross-case analysis report with shared entities and AI analysis."""

    report_id: str
    case_ids: list[str]
    shared_entities: list[CrossCaseMatch] = Field(default_factory=list)
    parallel_patterns: list[dict] = Field(default_factory=list)
    ai_analysis: str = ""


# ---------------------------------------------------------------------------
# Top 5 Investigative Patterns — multi-modal evidence models
# ---------------------------------------------------------------------------


class EvidenceModality(str, Enum):
    """Evidence modality types for multi-modal pattern discovery."""

    TEXT = "text"
    VISUAL = "visual"
    FACE = "face"
    COOCCURRENCE = "cooccurrence"


class RawPattern(BaseModel):
    """Intermediate pattern before AI synthesis."""

    entities: list[dict] = Field(default_factory=list)  # [{name, type, role}]
    modalities: list[EvidenceModality] = Field(default_factory=list)
    source_documents: list[str] = Field(default_factory=list)
    source_images: list[str] = Field(default_factory=list)
    face_crops: list[dict] = Field(default_factory=list)  # [{crop_s3_key, entity_name, similarity}]
    evidence_strength: float = 0.0  # normalized supporting source count
    cross_modal_score: float = 0.0  # 0-1 based on modality count
    novelty_score: float = 0.0  # 0-1 based on unexpected connections
    composite_score: float = 0.0  # computed: strength × cross_modal × novelty


class PatternQuestion(BaseModel):
    """A single investigative question with summary data."""

    index: int  # 1-5 priority rank
    question: str  # natural language investigative question
    confidence: int = Field(ge=0, le=100)  # percentage
    modalities: list[EvidenceModality] = Field(default_factory=list)
    summary: str = ""  # 2-3 sentence AI explanation
    document_count: int = 0
    image_count: int = 0
    raw_pattern: RawPattern = Field(default_factory=RawPattern)


class EvidenceBundle(BaseModel):
    """Detailed evidence for a single pattern (fetched on second click)."""

    documents: list[dict] = Field(default_factory=list)  # [{document_id, filename, excerpt, download_url}]
    images: list[dict] = Field(default_factory=list)  # [{s3_key, presigned_url, visual_labels}]
    face_crops: list[dict] = Field(default_factory=list)  # [{presigned_url, entity_name, similarity}]
    entity_paths: list[dict] = Field(default_factory=list)  # [{from_entity, to_entity, path_nodes}]
    cooccurring_labels: list[str] = Field(default_factory=list)


class TopPatternReport(BaseModel):
    """Top 5 investigative patterns response."""

    case_file_id: str
    patterns: list[PatternQuestion] = Field(default_factory=list)  # up to 5
    generated_at: str = ""  # ISO timestamp
    fewer_patterns_explanation: str = ""  # set if < 5 patterns found
