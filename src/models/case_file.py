"""Case file and cross-case graph data models."""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class CaseFileStatus(str, Enum):
    """Valid statuses for a case file lifecycle."""

    CREATED = "created"
    INGESTING = "ingesting"
    INDEXED = "indexed"
    INVESTIGATING = "investigating"
    ARCHIVED = "archived"
    ERROR = "error"


class SearchTier(str, Enum):
    """Search backend tier for a case file."""

    STANDARD = "standard"
    ENTERPRISE = "enterprise"


class CaseFile(BaseModel):
    """Represents a research case file — the core investigative container."""

    case_id: str
    topic_name: str
    description: str
    status: CaseFileStatus = CaseFileStatus.CREATED
    created_at: datetime
    parent_case_id: Optional[str] = None
    s3_prefix: str
    neptune_subgraph_label: str
    document_count: int = Field(default=0, ge=0)
    entity_count: int = Field(default=0, ge=0)
    relationship_count: int = Field(default=0, ge=0)
    findings: list = Field(default_factory=list)
    last_activity: Optional[datetime] = None
    error_details: Optional[str] = None
    search_tier: SearchTier = SearchTier.STANDARD


class CrossCaseGraph(BaseModel):
    """A persisted Neptune subgraph linking entities across multiple case files."""

    graph_id: str
    name: str
    linked_case_ids: list[str]
    created_at: datetime
    neptune_subgraph_label: str
    analyst_notes: str = ""
    status: str = "active"
