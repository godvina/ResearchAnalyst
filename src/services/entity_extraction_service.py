"""Entity extraction service using Bedrock LLM.

Extracts entities and relationships from document text using a chunking
strategy for large documents. Each chunk is processed independently and
results are merged using deduplication by canonical_name + entity_type.
"""

import json
import logging
import re
from datetime import datetime
from typing import Any

from models.entity import (
    EntityType,
    ExtractedEntity,
    ExtractedRelationship,
    RelationshipType,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

VALID_ENTITY_TYPES = {e.value for e in EntityType}
VALID_RELATIONSHIP_TYPES = {r.value for r in RelationshipType}

ENTITY_EXTRACTION_PROMPT = """\
You are an investigative analyst extracting key entities from case file documents.

FIRST, classify this document. Based on the content, determine the document_type as one of:
email, court_filing, deposition, financial_record, law_enforcement_report, correspondence, contract, photo_description, news_article, transcript, miscellaneous

Extract ONLY meaningful, investigatively relevant entities. Focus on:
- People (full names, aliases, nicknames — NOT generic titles like "Mr." alone)
- Organizations (companies, agencies, law firms, banks — NOT generic terms)
- Phone numbers (any format, normalize to digits with dashes)
- Email addresses
- Physical addresses (street addresses, NOT just "2nd floor" or room numbers)
- Account numbers (bank accounts, routing numbers, case reference numbers)
- Vehicles (license plates, VIN numbers, vehicle descriptions with identifying info)
- Financial amounts (specific dollar amounts tied to transactions)
- Dates (specific dates tied to events, NOT generic references)
- Locations (cities, countries, named places — NOT generic descriptions)
- Events (specific named events, meetings, transactions)

DO NOT extract:
- Generic labels (e.g., "Emergency Listings", "2nd Floor", "Page 1")
- Document metadata (file names, form field labels, headers/footers)
- Single common words or abbreviations without context
- Entities with confidence below 0.5

For each entity provide:
- entity_type: one of {entity_types}
- canonical_name: normalized form (e.g., "(555) 012-3456" → "555-012-3456", "J. Smith" → "J. Smith")
- confidence: float 0.0-1.0 (how certain this is a real entity, not noise)
- occurrences: count in this text

Return a JSON object with two fields:
1. "document_type": one of the types listed above
2. "entities": array of entity objects

Example:
{{
  "document_type": "email",
  "entities": [
    {{"entity_type": "person", "canonical_name": "Jeffrey Epstein", "confidence": 0.98, "occurrences": 5}},
    {{"entity_type": "phone_number", "canonical_name": "212-555-0142", "confidence": 0.95, "occurrences": 1}},
    {{"entity_type": "organization", "canonical_name": "JP Morgan Chase", "confidence": 0.90, "occurrences": 2}}
  ]
}}

Document text:
{text}
"""

RELATIONSHIP_EXTRACTION_PROMPT = """\
Given the following document text and a list of extracted entities, identify relationships between them.
For each relationship, provide:
- source_entity: canonical name of the source entity
- target_entity: canonical name of the target entity
- relationship_type: one of {relationship_types}
- confidence: a float between 0.0 and 1.0

Return ONLY a JSON array of objects. Example:
[
  {{"source_entity": "Erich von Däniken", "target_entity": "Nazca Lines", "relationship_type": "thematic", "confidence": 0.85}}
]

Entities:
{entities}

Document text:
{text}
"""

# Chunking configuration
CHUNK_SIZE = 10_000       # chars per chunk sent to Bedrock
CHUNK_OVERLAP = 500       # overlap between chunks to catch boundary entities


class EntityExtractionService:
    """Uses Bedrock LLM to extract entities and relationships from text.

    For documents larger than CHUNK_SIZE, the text is split into overlapping
    chunks. Entities and relationships are extracted from each chunk and then
    merged/deduplicated so nothing is lost.
    """

    def __init__(self, bedrock_client: Any, model_id: str = "anthropic.claude-3-haiku-20240307-v1:0"):
        self._client = bedrock_client
        self._model_id = model_id
        self._last_document_type = "miscellaneous"

    # ------------------------------------------------------------------
    # Bedrock helpers
    # ------------------------------------------------------------------

    def _invoke_model(self, prompt: str) -> str:
        """Invoke the Bedrock model and return the text response."""
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}],
        })
        logger.info("Invoking Bedrock model %s (prompt length: %d chars)", self._model_id, len(prompt))
        response = self._client.invoke_model(
            modelId=self._model_id,
            contentType="application/json",
            accept="application/json",
            body=body,
        )
        response_body = json.loads(response["body"].read())
        logger.info("Bedrock response received")
        return response_body["content"][0]["text"]

    def _parse_json_response(self, text: str) -> list[dict]:
        """Extract a JSON array from the model response text."""
        cleaned = text.strip()
        if cleaned.startswith("```"):
            first_newline = cleaned.index("\n")
            cleaned = cleaned[first_newline + 1:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()
        # Try to find JSON array in the response if direct parse fails
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            # Look for [ ... ] pattern in the text
            start = cleaned.find("[")
            end = cleaned.rfind("]")
            if start != -1 and end != -1 and end > start:
                try:
                    return json.loads(cleaned[start:end + 1])
                except json.JSONDecodeError:
                    pass
            logger.warning("Could not parse JSON from response (first 200 chars): %s", cleaned[:200])
            return []

    # ------------------------------------------------------------------
    # Chunking
    # ------------------------------------------------------------------

    @staticmethod
    def chunk_text(text: str, chunk_size: int = CHUNK_SIZE,
                   overlap: int = CHUNK_OVERLAP) -> list[str]:
        """Split text into overlapping chunks.

        Returns a list of text chunks. Short documents (≤ chunk_size) are
        returned as a single-element list.
        """
        if len(text) <= chunk_size:
            return [text]
        chunks: list[str] = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunks.append(text[start:end])
            start = end - overlap
        return chunks

    # ------------------------------------------------------------------
    # Entity extraction (with chunking)
    # ------------------------------------------------------------------

    def _extract_entities_single(self, text: str, document_id: str) -> list[ExtractedEntity]:
        """Extract entities from a single text chunk. Also captures document_type."""
        prompt = ENTITY_EXTRACTION_PROMPT.format(
            entity_types=", ".join(sorted(VALID_ENTITY_TYPES)),
            text=text,
        )
        raw_response = self._invoke_model(prompt)

        # Parse response — new format is {"document_type": "...", "entities": [...]}
        # but we also handle the old format (plain array) for backward compat
        parsed = None
        try:
            # Try to find JSON object first
            text_resp = raw_response.strip()
            obj_start = text_resp.find("{")
            arr_start = text_resp.find("[")

            if obj_start >= 0 and (arr_start < 0 or obj_start < arr_start):
                # New format: JSON object with document_type and entities
                obj_end = text_resp.rfind("}") + 1
                if obj_end > obj_start:
                    parsed = json.loads(text_resp[obj_start:obj_end])
            if parsed and isinstance(parsed, dict):
                # Store document_type for the caller to pick up
                self._last_document_type = parsed.get("document_type", "miscellaneous")
                raw_entities = parsed.get("entities", [])
            else:
                # Fall back to old format (plain array)
                raw_entities = self._parse_json_response(raw_response)
                self._last_document_type = "miscellaneous"
        except (json.JSONDecodeError, Exception):
            raw_entities = self._parse_json_response(raw_response)
            self._last_document_type = "miscellaneous"

        entities: list[ExtractedEntity] = []
        for item in raw_entities:
            entity_type_str = item.get("entity_type", "").lower()
            if entity_type_str not in VALID_ENTITY_TYPES:
                continue
            confidence = max(0.0, min(1.0, float(item.get("confidence", 0.0))))
            if confidence < 0.5:
                continue  # Skip low-confidence noise
            occurrences = max(1, int(item.get("occurrences", 1)))
            canonical = item.get("canonical_name", "").strip()
            if not canonical or len(canonical) < 2:
                continue  # Skip empty or single-char entities
            entities.append(ExtractedEntity(
                entity_type=EntityType(entity_type_str),
                canonical_name=canonical,
                confidence=confidence,
                occurrences=occurrences,
                source_document_refs=[document_id],
            ))
        return entities

    def extract_entities(self, text: str, document_id: str) -> list[ExtractedEntity]:
        """Extract entities from document text, chunking if needed."""
        chunks = self.chunk_text(text)
        logger.info("Extracting entities from %d chunk(s) for doc %s", len(chunks), document_id)

        all_entities: list[ExtractedEntity] = []
        for i, chunk in enumerate(chunks):
            try:
                chunk_entities = self._extract_entities_single(chunk, document_id)
                logger.info("Chunk %d/%d: %d entities", i + 1, len(chunks), len(chunk_entities))
                all_entities = self.merge_entities(all_entities, chunk_entities)
            except Exception as exc:
                logger.warning("Entity extraction failed on chunk %d/%d: %s",
                               i + 1, len(chunks), str(exc)[:200])
        all_entities = self.normalize_dates(all_entities)
        return all_entities

    # ------------------------------------------------------------------
    # Date normalization
    # ------------------------------------------------------------------

    # Common date patterns for regex-based parsing (US-centric, dayfirst=False)
    _DATE_PATTERNS: list[tuple[re.Pattern, str]] = [
        # MM/DD/YYYY or MM-DD-YYYY
        (re.compile(r"^(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})$"), "MDY4"),
        # MM/DD/YY or MM-DD-YY
        (re.compile(r"^(\d{1,2})[/\-](\d{1,2})[/\-](\d{2})$"), "MDY2"),
        # Month DD, YYYY  (e.g. "January 5, 2009" or "Jan 5, 2009")
        (re.compile(
            r"^(January|February|March|April|May|June|July|August|September|October|November|December|"
            r"Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.?\s+(\d{1,2}),?\s+(\d{4})$",
            re.IGNORECASE,
        ), "MONTH_DD_YYYY"),
        # DD-Mon-YY or DD-Mon-YYYY  (e.g. "28-Oct-09", "28-Oct-2009")
        (re.compile(
            r"^(\d{1,2})[/\-](Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[/\-](\d{2,4})$",
            re.IGNORECASE,
        ), "DD_MON_YY"),
        # YYYY-MM-DD (already ISO)
        (re.compile(r"^(\d{4})-(\d{2})-(\d{2})$"), "ISO"),
    ]

    _MONTH_MAP: dict[str, int] = {
        "jan": 1, "january": 1, "feb": 2, "february": 2,
        "mar": 3, "march": 3, "apr": 4, "april": 4,
        "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
        "aug": 8, "august": 8, "sep": 9, "september": 9,
        "oct": 10, "october": 10, "nov": 11, "november": 11,
        "dec": 12, "december": 12,
    }

    @staticmethod
    def _parse_date_to_iso(text: str) -> str | None:
        """Try to parse a date string into ISO format (YYYY-MM-DD).

        Uses regex patterns for common formats. Returns None if parsing fails.
        US date convention: dayfirst=False (MM/DD/YY).
        """
        cleaned = text.strip()
        for pattern, fmt in EntityExtractionService._DATE_PATTERNS:
            m = pattern.match(cleaned)
            if not m:
                continue
            try:
                if fmt == "MDY4":
                    month, day, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
                elif fmt == "MDY2":
                    month, day = int(m.group(1)), int(m.group(2))
                    yr2 = int(m.group(3))
                    year = 2000 + yr2 if yr2 < 70 else 1900 + yr2
                elif fmt == "MONTH_DD_YYYY":
                    month = EntityExtractionService._MONTH_MAP[m.group(1).lower().rstrip(".")]
                    day, year = int(m.group(2)), int(m.group(3))
                elif fmt == "DD_MON_YY":
                    day = int(m.group(1))
                    month = EntityExtractionService._MONTH_MAP[m.group(2).lower()]
                    yr_raw = int(m.group(3))
                    year = yr_raw if yr_raw >= 100 else (2000 + yr_raw if yr_raw < 70 else 1900 + yr_raw)
                elif fmt == "ISO":
                    year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
                else:
                    continue
                # Validate via datetime constructor
                dt = datetime(year, month, day)
                return dt.strftime("%Y-%m-%d")
            except (ValueError, KeyError):
                continue
        return None

    @staticmethod
    def normalize_dates(entities: list[ExtractedEntity]) -> list[ExtractedEntity]:
        """Normalize date entities to ISO format (YYYY-MM-DD) where possible.

        Handles common formats: MM/DD/YY, MM/DD/YYYY, Month DD, YYYY, DD-Mon-YY, etc.
        If normalization succeeds, prepends the ISO date to canonical_name like:
        "2009-10-28 (10/28/09)" so both forms are searchable.
        If normalization fails, leaves the entity unchanged.

        This is a best-effort operation — never raises exceptions.
        """
        result: list[ExtractedEntity] = []
        for entity in entities:
            if entity.entity_type != EntityType.DATE:
                result.append(entity)
                continue
            try:
                iso = EntityExtractionService._parse_date_to_iso(entity.canonical_name)
                if iso is not None:
                    # Don't double-normalize if already in "YYYY-MM-DD (original)" form
                    if entity.canonical_name.startswith(iso):
                        result.append(entity)
                    else:
                        normalized_name = f"{iso} ({entity.canonical_name})"
                        result.append(entity.model_copy(update={"canonical_name": normalized_name}))
                else:
                    result.append(entity)
            except Exception:
                # Best-effort: never fail the pipeline
                result.append(entity)
        return result

    # ------------------------------------------------------------------
    # Relationship extraction (with chunking)
    # ------------------------------------------------------------------

    def _extract_relationships_single(
        self, text: str, entities: list[ExtractedEntity], document_id: str,
    ) -> list[ExtractedRelationship]:
        """Extract relationships from a single text chunk."""
        entity_names = [f"{e.canonical_name} ({e.entity_type.value})" for e in entities]
        prompt = RELATIONSHIP_EXTRACTION_PROMPT.format(
            relationship_types=", ".join(sorted(VALID_RELATIONSHIP_TYPES)),
            entities="\n".join(f"- {name}" for name in entity_names),
            text=text,
        )
        raw_response = self._invoke_model(prompt)
        raw_relationships = self._parse_json_response(raw_response)

        relationships: list[ExtractedRelationship] = []
        for item in raw_relationships:
            rel_type_str = item.get("relationship_type", "").lower()
            if rel_type_str not in VALID_RELATIONSHIP_TYPES:
                continue
            confidence = max(0.0, min(1.0, float(item.get("confidence", 0.0))))
            relationships.append(ExtractedRelationship(
                source_entity=item.get("source_entity", "").strip(),
                target_entity=item.get("target_entity", "").strip(),
                relationship_type=RelationshipType(rel_type_str),
                confidence=confidence,
                source_document_ref=document_id,
            ))
        return relationships

    def extract_relationships(
        self, text: str, entities: list[ExtractedEntity], document_id: str,
    ) -> list[ExtractedRelationship]:
        """Extract relationships from document text, chunking if needed.

        The full merged entity list is passed to each chunk so the model
        can identify cross-chunk relationships.
        """
        chunks = self.chunk_text(text)
        logger.info("Extracting relationships from %d chunk(s) for doc %s", len(chunks), document_id)

        all_rels: list[ExtractedRelationship] = []
        seen: set[tuple[str, str, str]] = set()
        for i, chunk in enumerate(chunks):
            try:
                chunk_rels = self._extract_relationships_single(chunk, entities, document_id)
                # Deduplicate relationships across chunks
                for rel in chunk_rels:
                    key = (rel.source_entity, rel.target_entity, rel.relationship_type.value)
                    if key not in seen:
                        seen.add(key)
                        all_rels.append(rel)
                logger.info("Chunk %d/%d: %d relationships (total unique: %d)",
                            i + 1, len(chunks), len(chunk_rels), len(all_rels))
            except Exception as exc:
                logger.warning("Relationship extraction failed on chunk %d/%d: %s",
                               i + 1, len(chunks), str(exc)[:200])
        return all_rels

    @staticmethod
    def merge_entities(
        existing: list[ExtractedEntity],
        new: list[ExtractedEntity],
    ) -> list[ExtractedEntity]:
        """Merge duplicate entities by canonical_name + entity_type.

        Entities with the same canonical name and type are merged:
        - occurrence counts are summed
        - source_document_refs are unioned (preserving order, no duplicates)
        - the higher confidence score is kept

        Args:
            existing: The current list of entities.
            new: New entities to merge in.

        Returns:
            A merged list of ExtractedEntity objects.
        """
        merged: dict[tuple[str, EntityType], ExtractedEntity] = {}

        for entity in [*existing, *new]:
            key = (entity.canonical_name, entity.entity_type)
            if key in merged:
                current = merged[key]
                # Sum occurrences
                combined_occurrences = current.occurrences + entity.occurrences
                # Union source refs preserving order
                seen = set(current.source_document_refs)
                combined_refs = list(current.source_document_refs)
                for ref in entity.source_document_refs:
                    if ref not in seen:
                        combined_refs.append(ref)
                        seen.add(ref)
                # Keep higher confidence
                combined_confidence = max(current.confidence, entity.confidence)

                merged[key] = ExtractedEntity(
                    entity_type=entity.entity_type,
                    canonical_name=entity.canonical_name,
                    confidence=combined_confidence,
                    occurrences=combined_occurrences,
                    source_document_refs=combined_refs,
                )
            else:
                merged[key] = entity

        return list(merged.values())
