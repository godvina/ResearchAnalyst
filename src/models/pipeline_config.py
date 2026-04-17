"""Pipeline configuration and monitoring data models."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


# --- Pipeline step config section models ---


class ParseConfig(BaseModel):
    """Configuration for the Parse pipeline step."""

    pdf_method: str = "text"  # "text", "ocr", "hybrid"
    ocr_enabled: bool = False
    table_extraction_enabled: bool = False


class ExtractConfig(BaseModel):
    """Configuration for the Extract pipeline step."""

    prompt_template: str = "default_investigative_v1"
    entity_types: list[str] = Field(default_factory=lambda: [
        "person", "organization", "location", "date", "event",
        "phone_number", "email", "address", "account_number",
        "vehicle", "financial_amount",
    ])
    llm_model_id: str = "anthropic.claude-3-sonnet-20240229-v1:0"
    chunk_size_chars: int = 8000
    confidence_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    relationship_inference_enabled: bool = True


class OpenSearchSettings(BaseModel):
    """Nested OpenSearch settings within EmbedConfig."""

    index_refresh_interval: str = "30s"
    number_of_replicas: int = 1


class EmbedConfig(BaseModel):
    """Configuration for the Embed pipeline step."""

    embedding_model_id: str = "amazon.titan-embed-text-v1"
    search_tier: str = "standard"
    opensearch_settings: OpenSearchSettings = Field(default_factory=OpenSearchSettings)


class NormalizationRules(BaseModel):
    """Normalization rules for graph loading."""

    case_folding: bool = True
    trim_whitespace: bool = True
    alias_merging: bool = False
    abbreviation_expansion: bool = False


class GraphLoadConfig(BaseModel):
    """Configuration for the Graph Load pipeline step."""

    load_strategy: str = "bulk_csv"  # "bulk_csv" or "gremlin"
    batch_size: int = 500
    normalization_rules: NormalizationRules = Field(default_factory=NormalizationRules)


class StoreArtifactConfig(BaseModel):
    """Configuration for the Store Artifact pipeline step."""

    artifact_format: str = "json"  # "json" or "jsonl"
    include_raw_text: bool = False


class RekognitionConfig(BaseModel):
    """Configuration for the optional Rekognition pipeline step."""

    enabled: bool = False
    watchlist_collection_id: Optional[str] = None
    min_face_confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    min_object_confidence: float = Field(default=0.7, ge=0.0, le=1.0)
    detect_text: bool = True
    detect_moderation_labels: bool = False
    video_processing_mode: str = "skip"  # "skip", "faces_only", "targeted", "full"
    video_segment_length_seconds: int = 60


# --- Core pipeline config models ---


class PipelineConfig(BaseModel):
    """A pipeline configuration record stored in Aurora."""

    config_id: UUID
    case_id: UUID
    version: int
    config_json: dict
    created_at: datetime
    created_by: str
    is_active: bool


class ConfigVersion(BaseModel):
    """An immutable snapshot of a pipeline config at a point in time."""

    config_id: UUID
    case_id: UUID
    version: int
    config_json: dict
    created_at: datetime
    created_by: str


class EffectiveConfig(BaseModel):
    """The result of deep-merging system defaults with case overrides."""

    case_id: UUID
    config_version: Optional[int] = None  # None if using only system defaults
    effective_json: dict
    origins: dict  # e.g. {"parse.pdf_method": "system_default", ...}


class SampleRun(BaseModel):
    """A pipeline execution against a small subset of documents."""

    run_id: UUID
    case_id: UUID
    config_version: int
    document_ids: list[str]
    status: str  # pending, running, completed, failed
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_by: str


class QualityScore(BaseModel):
    """Pipeline quality score with weighted breakdown."""

    overall: float = Field(ge=0.0, le=100.0)
    confidence_avg: float = Field(ge=0.0, le=100.0)
    type_diversity: float = Field(ge=0.0, le=100.0)
    relationship_density: float = Field(ge=0.0, le=100.0)
    noise_ratio_score: float = Field(ge=0.0, le=100.0)


class SampleRunSnapshot(BaseModel):
    """Snapshot of a sample run's results for comparison."""

    snapshot_id: UUID
    run_id: UUID
    case_id: UUID
    config_version: int
    snapshot_name: Optional[str] = None
    entities: list[dict] = Field(default_factory=list)
    relationships: list[dict] = Field(default_factory=list)
    quality_metrics: dict = Field(default_factory=dict)
    created_at: datetime


class SampleRunComparison(BaseModel):
    """Comparison between two sample run snapshots."""

    run_a: SampleRunSnapshot
    run_b: SampleRunSnapshot
    entities_added: list[dict] = Field(default_factory=list)
    entities_removed: list[dict] = Field(default_factory=list)
    entities_changed: list[dict] = Field(default_factory=list)
    relationship_changes: list[dict] = Field(default_factory=list)
    quality_a: QualityScore
    quality_b: QualityScore
    quality_delta: dict = Field(default_factory=dict)


class ValidationError(BaseModel):
    """A single config validation error."""

    field_path: str  # e.g. "extract.confidence_threshold"
    reason: str      # e.g. "Must be between 0.0 and 1.0"


class StepDetail(BaseModel):
    """Detailed metrics and config for a single pipeline step."""

    step_name: str
    service_status: str  # Active/Inactive
    item_count: int = 0
    metrics: dict = Field(default_factory=dict)
    config_values: dict = Field(default_factory=dict)
    config_origins: dict = Field(default_factory=dict)
    recent_runs: list[dict] = Field(default_factory=list)
    recent_errors: list[dict] = Field(default_factory=list)


class PipelineRunSummary(BaseModel):
    """Summary of a pipeline run for listing."""

    run_id: UUID
    case_id: UUID
    config_version: int
    is_sample_run: bool = False
    document_count: int = 0
    status: str  # pending, running, completed, failed
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    quality_score: Optional[float] = None


class PipelineRunMetrics(BaseModel):
    """Detailed metrics for a pipeline run."""

    run_id: UUID
    total_entities: Optional[int] = None
    total_relationships: Optional[int] = None
    entity_type_counts: Optional[dict] = None
    avg_confidence: Optional[float] = None
    noise_ratio: Optional[float] = None
    docs_per_minute: Optional[float] = None
    avg_entities_per_doc: Optional[float] = None
    failed_doc_count: int = 0
    failure_rate: Optional[float] = None
    estimated_cost_usd: Optional[float] = None
    total_input_tokens: Optional[int] = None
    total_output_tokens: Optional[int] = None
    quality_score: Optional[float] = None
    quality_breakdown: Optional[dict] = None


class PipelineStatus(BaseModel):
    """Current pipeline execution status for a case."""

    case_id: UUID
    current_step: Optional[str] = None
    docs_processed: int = 0
    docs_remaining: int = 0
    elapsed_seconds: Optional[float] = None
    status: str = "idle"  # idle, running, completed, failed
    step_statuses: dict = Field(default_factory=dict)


# --- Models for Req 13-19 ---


class CostEstimate(BaseModel):
    """Cost estimate from the pipeline wizard."""

    one_time: dict = Field(default_factory=dict)
    monthly: dict = Field(default_factory=dict)
    optimizations: list[str] = Field(default_factory=list)
    tiers: dict = Field(default_factory=dict)  # economy, recommended, premium


class CaseAssessment(BaseModel):
    """Case assessment dashboard data."""

    case_id: UUID
    strength_score: int = Field(default=0, ge=0, le=100)
    evidence_coverage: dict = Field(default_factory=dict)
    key_subjects: list[dict] = Field(default_factory=list)
    critical_leads: list[dict] = Field(default_factory=list)
    resource_recommendations: list[str] = Field(default_factory=list)
    timeline: list[dict] = Field(default_factory=list)


class ChatMessage(BaseModel):
    """A single message in a chat conversation."""

    role: str  # "user" or "assistant"
    content: str
    citations: list[dict] = Field(default_factory=list)
    timestamp: datetime
    conversation_id: Optional[UUID] = None


class Finding(BaseModel):
    """An investigator finding or note attached to a case."""

    finding_id: UUID
    case_id: UUID
    user_id: str
    finding_type: str = "note"  # note, suspicious, lead, evidence_gap, recommendation
    title: str
    content: str
    entity_refs: list[str] = Field(default_factory=list)
    document_refs: list[str] = Field(default_factory=list)
    created_at: datetime


class WorkbenchCase(BaseModel):
    """A case as displayed in the investigator workbench."""

    case_id: UUID
    topic_name: str
    status: str
    priority: str = "medium"  # critical, high, medium, low
    assigned_to: Optional[str] = None
    strength_score: Optional[int] = None
    document_count: int = 0
    entity_count: int = 0
    last_activity_at: Optional[datetime] = None
    swim_lane: Optional[str] = None  # needs_action, active, awaiting, review_close


# --- Models for Req 23: AI-Powered Document Classification and Case Routing ---


class ClassificationConfig(BaseModel):
    """Configuration for the optional Document Classification step."""

    routing_mode: str = "folder_based"  # "folder_based", "metadata_routing", "ai_classification"
    case_number_pattern: str = r"\d{4}-[A-Z]{2}-\d{5}"
    ai_model_id: str = "anthropic.claude-3-haiku-20240307-v1:0"
    confidence_threshold: float = Field(default=0.8, ge=0.0, le=1.0)
    max_preview_chars: int = Field(default=5000, ge=100, le=50000)
    classify_sample_size: int = Field(default=100, ge=1, le=10000)


class ClassificationResult(BaseModel):
    """Result of classifying a single document."""

    document_id: str
    matched_case_id: Optional[str] = None
    case_number: Optional[str] = None
    case_category: Optional[str] = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    routing_reason: str = ""
    routing_mode: str = "folder_based"


class RoutingOutcome(BaseModel):
    """Outcome of routing a classified document."""

    action: str  # "assigned", "triage", "skipped"
    case_id: Optional[str] = None
    triage_reason: Optional[str] = None


class TriageQueueItem(BaseModel):
    """A document in the triage queue awaiting manual assignment."""

    triage_id: UUID
    document_id: str
    filename: str
    classification_result: dict = Field(default_factory=dict)
    suggested_case_id: Optional[str] = None
    suggested_case_name: Optional[str] = None
    confidence: float = 0.0
    status: str = "pending"  # "pending", "assigned", "new_case"
    assigned_case_id: Optional[str] = None
    assigned_by: Optional[str] = None
    assigned_at: Optional[datetime] = None
    created_at: datetime
