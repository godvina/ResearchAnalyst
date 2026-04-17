"""Lead ingestion data models for the Lead-to-Investigation feature.

Defines the structured JSON schema that external lead-finding applications
submit to ``POST /leads/ingest``.  Pydantic validates required fields,
subject types, confidence ranges, and connection reference integrity.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class LeadSubject(BaseModel):
    """A person or organization identified in the lead."""

    name: str = Field(min_length=1)
    type: Literal["person", "organization"]
    role: str = ""
    aliases: list[str] = Field(default_factory=list)
    identifiers: dict[str, str] = Field(default_factory=dict)


class LeadConnection(BaseModel):
    """A known relationship between two subjects."""

    from_subject: str = Field(alias="from")
    to_subject: str = Field(alias="to")
    relationship: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0, default=0.8)
    source: str = ""

    model_config = {"populate_by_name": True}


class EvidenceHint(BaseModel):
    """A reference to a public document relevant to the lead."""

    description: str = Field(min_length=1)
    url: str = ""
    document_type: str = ""
    relevant_subjects: list[str] = Field(default_factory=list)


class LeadJSON(BaseModel):
    """Top-level lead payload submitted by the external lead-finding app."""

    lead_id: str = Field(min_length=1)
    classification: str = Field(min_length=1)
    subcategory: str = ""
    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    source_app: str = ""
    priority: str = "medium"
    subjects: list[LeadSubject] = Field(min_length=1)
    connections: list[LeadConnection] = Field(default_factory=list)
    evidence_hints: list[EvidenceHint] = Field(default_factory=list)
    osint_directives: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    statutes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_connection_refs(self) -> "LeadJSON":
        """Ensure every connection references subjects that exist."""
        names = {s.name for s in self.subjects}
        for i, conn in enumerate(self.connections):
            if conn.from_subject not in names:
                raise ValueError(
                    f"connections[{i}].from references unknown subject '{conn.from_subject}'"
                )
            if conn.to_subject not in names:
                raise ValueError(
                    f"connections[{i}].to references unknown subject '{conn.to_subject}'"
                )
        return self

    def lead_metadata_subset(self) -> dict:
        """Return the subset stored as JSONB on the matter row."""
        return {
            "lead_id": self.lead_id,
            "classification": self.classification,
            "subcategory": self.subcategory,
            "priority": self.priority,
            "tags": self.tags,
            "statutes": self.statutes,
        }
