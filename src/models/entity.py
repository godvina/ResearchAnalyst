"""Entity and relationship extraction data models."""

from enum import Enum

from pydantic import BaseModel, Field


class EntityType(str, Enum):
    """Supported entity types for extraction."""

    PERSON = "person"
    LOCATION = "location"
    DATE = "date"
    ARTIFACT = "artifact"
    CIVILIZATION = "civilization"
    THEME = "theme"
    EVENT = "event"
    ORGANIZATION = "organization"
    PHONE_NUMBER = "phone_number"
    EMAIL = "email"
    ADDRESS = "address"
    ACCOUNT_NUMBER = "account_number"
    VEHICLE = "vehicle"
    FINANCIAL_AMOUNT = "financial_amount"


class RelationshipType(str, Enum):
    """Supported relationship types between entities."""

    CO_OCCURRENCE = "co-occurrence"
    CAUSAL = "causal"
    TEMPORAL = "temporal"
    GEOGRAPHIC = "geographic"
    THEMATIC = "thematic"


class ExtractedEntity(BaseModel):
    """An entity extracted from document text via Bedrock."""

    entity_type: EntityType
    canonical_name: str
    confidence: float = Field(ge=0.0, le=1.0)
    occurrences: int = Field(ge=1)
    source_document_refs: list[str] = Field(min_length=1)


class ExtractedRelationship(BaseModel):
    """A relationship between two entities extracted from document text."""

    source_entity: str
    target_entity: str
    relationship_type: RelationshipType
    confidence: float = Field(ge=0.0, le=1.0)
    source_document_ref: str
