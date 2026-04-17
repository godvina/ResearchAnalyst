"""Document parsing and ingestion result data models."""

from typing import Optional

from pydantic import BaseModel, Field


class ParsedDocument(BaseModel):
    """Structured representation of a parsed raw document."""

    document_id: str
    case_file_id: str
    source_metadata: dict
    raw_text: str
    sections: list[dict] = Field(default_factory=list)
    parse_errors: list[str] = Field(default_factory=list)
    page_count: int = 0
    file_size_bytes: int = 0
    extracted_images: list[dict] = Field(default_factory=list)
    image_extraction_summary: dict = Field(default_factory=dict)


class ExtractionResult(BaseModel):
    """Result of entity and relationship extraction for a single document."""

    document_id: str
    entities: list[dict] = Field(default_factory=list)
    relationships: list[dict] = Field(default_factory=list)


class BatchResult(BaseModel):
    """Summary of a batch ingestion run across multiple documents."""

    case_file_id: str
    total_documents: int = Field(ge=0)
    successful: int = Field(ge=0)
    failed: int = Field(ge=0)
    document_count: int = Field(ge=0)
    entity_count: int = Field(ge=0)
    relationship_count: int = Field(ge=0)
    failures: list[dict] = Field(default_factory=list)
