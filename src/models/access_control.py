"""Access control data models for document security labeling."""

from datetime import datetime
from enum import IntEnum
from typing import Optional

from pydantic import BaseModel, Field


class SecurityLabel(IntEnum):
    """Hierarchical security labels with integer ranks for comparison.

    Higher rank indicates higher sensitivity:
    PUBLIC(0) < RESTRICTED(1) < CONFIDENTIAL(2) < TOP_SECRET(3)
    """

    PUBLIC = 0
    RESTRICTED = 1
    CONFIDENTIAL = 2
    TOP_SECRET = 3


class AccessDecision(BaseModel):
    """Result of an access policy check."""

    allowed: bool
    reason: str


class UserContext(BaseModel):
    """Resolved caller identity and clearance."""

    user_id: str
    username: str
    clearance_level: SecurityLabel
    role: str
    groups: list[str] = Field(default_factory=list)


class ResourceContext(BaseModel):
    """Document-level context for access decisions."""

    document_id: str
    case_id: str
    effective_label: SecurityLabel
    security_label_override: Optional[SecurityLabel] = None


class PlatformUser(BaseModel):
    """Platform user record with clearance level."""

    user_id: str
    username: str
    display_name: str
    role: str
    clearance_level: SecurityLabel
    created_at: datetime
    updated_at: datetime


class LabelAuditEntry(BaseModel):
    """Immutable audit log entry for label changes."""

    audit_id: str
    entity_type: str  # "matter", "document", "user", "access_denied"
    entity_id: str
    previous_label: Optional[str] = None
    new_label: Optional[str] = None
    changed_by: str
    changed_at: datetime
    change_reason: Optional[str] = None
