"""Matter-Collection hierarchy data models for multi-tenant support.

Replaces the flat case_files model with Organization > Matter > Collection > Document.
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Organization(BaseModel):
    """A tenant/customer — all data is scoped to an organization."""

    org_id: str
    org_name: str
    settings: dict = Field(default_factory=dict)
    created_at: datetime


class MatterStatus(str, Enum):
    """Valid statuses for a matter lifecycle."""

    CREATED = "created"
    INGESTING = "ingesting"
    INDEXED = "indexed"
    INVESTIGATING = "investigating"
    ARCHIVED = "archived"
    ERROR = "error"


class Matter(BaseModel):
    """The primary analysis unit — an investigation, case, or audit. Replaces CaseFile."""

    matter_id: str
    org_id: str
    matter_name: str
    description: str
    status: MatterStatus = MatterStatus.CREATED
    matter_type: str = "investigation"
    created_by: str = ""
    created_at: datetime
    last_activity: Optional[datetime] = None
    s3_prefix: str
    neptune_subgraph_label: str
    total_documents: int = Field(default=0, ge=0)
    total_entities: int = Field(default=0, ge=0)
    total_relationships: int = Field(default=0, ge=0)
    search_tier: str = "standard"
    error_details: Optional[str] = None


class CollectionStatus(str, Enum):
    """Valid statuses for a collection lifecycle."""

    STAGING = "staging"
    PROCESSING = "processing"
    QA_REVIEW = "qa_review"
    PROMOTED = "promoted"
    REJECTED = "rejected"
    ARCHIVED = "archived"


class Collection(BaseModel):
    """A batch of documents from a specific source — tracks provenance and supports QA."""

    collection_id: str
    matter_id: str
    org_id: str
    collection_name: str
    source_description: str = ""
    status: CollectionStatus = CollectionStatus.STAGING
    document_count: int = Field(default=0, ge=0)
    entity_count: int = Field(default=0, ge=0)
    relationship_count: int = Field(default=0, ge=0)
    uploaded_by: str = ""
    uploaded_at: datetime
    promoted_at: Optional[datetime] = None
    chain_of_custody: list[dict] = Field(default_factory=list)
    s3_prefix: str


class PromotionSnapshot(BaseModel):
    """Records the result of promoting a Collection into a Matter's graph."""

    snapshot_id: str
    collection_id: str
    matter_id: str
    entities_added: int = 0
    relationships_added: int = 0
    promoted_at: datetime
    promoted_by: str = ""
