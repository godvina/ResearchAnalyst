"""Semantic search and AI analysis data models."""

from typing import Optional

from pydantic import BaseModel, Field


class SearchResult(BaseModel):
    """A single result from a semantic search query."""

    document_id: str
    passage: str
    relevance_score: float = Field(ge=0.0, le=1.0)
    source_document_ref: str
    surrounding_context: str = ""


class AnalysisSummary(BaseModel):
    """AI-generated analytical summary for an entity or pattern."""

    subject: str
    summary: str
    supporting_passages: list[SearchResult] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)


class FacetedFilter(BaseModel):
    """Filter criteria for enterprise-tier faceted search."""

    date_from: Optional[str] = None
    date_to: Optional[str] = None
    person: Optional[str] = None
    document_type: Optional[str] = None
    entity_type: Optional[str] = None


class SearchRequest(BaseModel):
    """Extended search request supporting multi-mode search."""

    query: str
    search_mode: str = "semantic"
    filters: Optional[FacetedFilter] = None
    top_k: int = Field(default=10, ge=1, le=100)


class SearchResponse(BaseModel):
    """Search response with tier metadata."""

    results: list[SearchResult]
    search_tier: str
    available_modes: list[str]
