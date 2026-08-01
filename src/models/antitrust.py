"""Antitrust analysis data models.

Defines enums, dataclasses, and Pydantic models for the procurement collusion
detection module and the shared antitrust analysis framework. Designed to be
extensible for future case types (merger review, price fixing, etc.).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# =============================================================================
# Enums
# =============================================================================


class CaseType(str, Enum):
    """Supported antitrust case types. New modules register here."""

    PROCUREMENT_COLLUSION = "procurement_collusion"
    MERGER_REVIEW = "merger_review"
    PRICE_FIXING = "price_fixing"
    MARKET_ALLOCATION = "market_allocation"
    MONOPOLIZATION = "monopolization"
    CRIMINAL_CARTEL = "criminal_cartel"


class BidRiggingType(str, Enum):
    """Classification of bid-rigging pattern types."""

    COMPLEMENTARY_BIDDING = "complementary_bidding"
    BID_ROTATION = "bid_rotation"
    MARKET_ALLOCATION = "market_allocation"
    BID_SUPPRESSION = "bid_suppression"


class RedFlagSeverity(str, Enum):
    """Severity classification for antitrust red flags."""

    CRITICAL = "Critical"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class RedFlagCategory(str, Enum):
    """Categories of antitrust red flags aligned with PCSF taxonomy."""

    BID_RIGGING = "bid_rigging"
    PRICING = "pricing"
    COMMUNICATION = "communication"
    FINANCIAL = "financial"
    MARKET_ALLOCATION = "market_allocation"
    BID_SUPPRESSION = "bid_suppression"
    BEHAVIORAL = "behavioral"


class AnalysisStatus(str, Enum):
    """Status of a collusion analysis run."""

    PROCESSING = "processing"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"


class AwardStatus(str, Enum):
    """Bid award status."""

    WON = "won"
    LOST = "lost"
    WITHDRAWN = "withdrawn"


class SchemeType(str, Enum):
    """Type of collusion scheme identified for a ring."""

    COMPLEMENTARY_BIDDING = "complementary_bidding"
    BID_ROTATION = "bid_rotation"
    MARKET_ALLOCATION = "market_allocation"
    BID_SUPPRESSION = "bid_suppression"
    MIXED = "mixed"


# =============================================================================
# Shared Scoring Dataclasses (used by all antitrust modules)
# =============================================================================


@dataclass
class ScoringFactor:
    """A single weighted factor in the antitrust scoring framework."""

    name: str
    weight: float
    score: float  # 0-100
    evidence_refs: list[str] = field(default_factory=list)
    description: str = ""


@dataclass
class ScoringResult:
    """Result of a composite antitrust score computation."""

    overall_score: float  # 0-100
    factors: list[ScoringFactor] = field(default_factory=list)
    severity: str = "Low"  # Critical, High, Medium, Low
    confidence: float = 0.0  # 0-1


@dataclass
class AnalysisResult:
    """Base result returned by any antitrust analysis module."""

    case_id: str
    case_type: CaseType
    status: str  # "completed", "processing", "partial", "failed"
    overall_score: float  # 0-100
    red_flags: list[dict] = field(default_factory=list)
    patterns: list[dict] = field(default_factory=list)
    subjects: list[dict] = field(default_factory=list)
    evidence_summary: dict = field(default_factory=dict)
    legal_reasoning: Optional[str] = None
    metadata: dict = field(default_factory=dict)


# =============================================================================
# Pydantic Models (API request/response validation)
# =============================================================================


class ProcurementRecord(BaseModel):
    """A single bid submission record."""

    record_id: str = ""
    vendor_id: str
    vendor_name: str
    contract_id: str
    bid_amount: float = Field(gt=0, description="Bid amount must be positive")
    submission_timestamp: Optional[datetime] = None
    specifications_met: bool = True
    award_status: AwardStatus
    government_estimate: Optional[float] = Field(default=None, gt=0)
    naics_codes: list[str] = Field(default_factory=list)
    geographic_region: Optional[str] = None
    raw_data: dict = Field(default_factory=dict)


class BidRiggingPattern(BaseModel):
    """A detected bid-rigging pattern with confidence and evidence."""

    pattern_id: str
    pattern_type: BidRiggingType
    confidence: float = Field(ge=0, le=100)
    involved_vendors: list[str] = Field(default_factory=list)
    involved_contracts: list[str] = Field(default_factory=list)
    evidence_summary: str = ""
    legal_reasoning: Optional[str] = None
    decision_id: Optional[str] = None


class PriceAnomaly(BaseModel):
    """A detected statistical anomaly in bid pricing."""

    anomaly_id: str
    test_type: str  # "bid_spread", "round_number", "price_to_estimate", "time_series"
    severity: RedFlagSeverity
    test_statistic: float
    p_value: Optional[float] = Field(default=None, ge=0, le=1)
    involved_vendors: list[str] = Field(default_factory=list)
    involved_contracts: list[str] = Field(default_factory=list)
    interpretation: str = ""


class CollusionRingMember(BaseModel):
    """A member of an identified collusion ring with their role."""

    vendor_id: str
    vendor_name: str
    role: str  # "ring_leader", "complementary_bidder", "designated_winner", "subcontractor_recipient"


class CollusionRing(BaseModel):
    """An identified group of vendors participating in a coordinated scheme."""

    ring_id: str
    ring_name: str = ""
    member_vendors: list[CollusionRingMember] = Field(default_factory=list)
    scheme_type: SchemeType
    pcsf_score: float = Field(ge=0, le=100)
    affected_contracts: list[str] = Field(default_factory=list)
    timeline: list[dict] = Field(default_factory=list)
    evidence_summary: dict = Field(default_factory=dict)
    legal_reasoning: Optional[str] = None
    decision_id: Optional[str] = None


class RedFlag(BaseModel):
    """A PCSF-aligned red flag indicator."""

    flag_id: str
    category: RedFlagCategory
    severity: RedFlagSeverity
    title: str
    description: str = ""
    evidence_refs: list[str] = Field(default_factory=list)
    involved_vendors: list[str] = Field(default_factory=list)
    involved_contracts: list[str] = Field(default_factory=list)
    pcsf_taxonomy_code: Optional[str] = None
    ai_legal_reasoning: Optional[str] = None
    decision_id: Optional[str] = None


class PCSFBreakdown(BaseModel):
    """Breakdown of PCSF composite score by component."""

    bid_rigging_score: float = Field(ge=0, le=100, default=0)
    pricing_score: float = Field(ge=0, le=100, default=0)
    communication_score: float = Field(ge=0, le=100, default=0)
    financial_score: float = Field(ge=0, le=100, default=0)
    behavioral_score: float = Field(ge=0, le=100, default=0)


class CollusionAnalysisResult(BaseModel):
    """Complete result of a collusion analysis run for an investigation."""

    analysis_id: str
    case_id: str
    status: AnalysisStatus
    pcsf_score: float = Field(ge=0, le=100)
    pcsf_breakdown: PCSFBreakdown = Field(default_factory=PCSFBreakdown)
    total_contracts_analyzed: int = 0
    total_bids_analyzed: int = 0
    total_vendors_analyzed: int = 0
    bid_rigging_patterns: list[BidRiggingPattern] = Field(default_factory=list)
    price_anomalies: list[PriceAnomaly] = Field(default_factory=list)
    communication_patterns: list[dict] = Field(default_factory=list)
    financial_flow_patterns: list[dict] = Field(default_factory=list)
    collusion_rings: list[CollusionRing] = Field(default_factory=list)
    red_flags: list[RedFlag] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)


# =============================================================================
# API Request Models
# =============================================================================


class TriggerAnalysisRequest(BaseModel):
    """Request body for POST /case-files/{id}/collusion-analysis."""

    force_recompute: bool = False
    contract_ids: Optional[list[str]] = None  # None = analyze all


class IngestProcurementRequest(BaseModel):
    """Request body for POST /case-files/{id}/procurement-records."""

    records: list[ProcurementRecord] = Field(min_length=1)
    source_file: Optional[str] = None
