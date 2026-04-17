"""Unit tests for EntityExtractionService."""

import io
import json
from unittest.mock import MagicMock

import pytest

from src.models.entity import (
    EntityType,
    ExtractedEntity,
    ExtractedRelationship,
    RelationshipType,
)
from src.services.entity_extraction_service import EntityExtractionService


def _make_bedrock_response(payload: list[dict]) -> dict:
    """Build a mock Bedrock invoke_model response wrapping a JSON array."""
    body_content = json.dumps({
        "content": [{"text": json.dumps(payload)}],
    })
    return {"body": io.BytesIO(body_content.encode())}


def _make_bedrock_response_raw(text: str) -> dict:
    """Build a mock Bedrock response with arbitrary text content."""
    body_content = json.dumps({"content": [{"text": text}]})
    return {"body": io.BytesIO(body_content.encode())}


@pytest.fixture
def bedrock_client():
    return MagicMock()


@pytest.fixture
def service(bedrock_client):
    return EntityExtractionService(bedrock_client)


# ---------------------------------------------------------------------------
# extract_entities — Requirement 2.2, 9.1, 9.2
# ---------------------------------------------------------------------------

class TestExtractEntities:
    """Tests for extract_entities() — Requirements 2.2, 9.1, 9.2."""

    def test_extracts_entities_from_bedrock_response(self, bedrock_client, service):
        bedrock_client.invoke_model.return_value = _make_bedrock_response([
            {"entity_type": "person", "canonical_name": "Erich von Däniken", "confidence": 0.95, "occurrences": 3},
            {"entity_type": "location", "canonical_name": "Nazca Lines", "confidence": 0.88, "occurrences": 2},
        ])

        entities = service.extract_entities("Some text about ancient aliens.", "doc-1")

        assert len(entities) == 2
        assert entities[0].entity_type == EntityType.PERSON
        assert entities[0].canonical_name == "Erich von Däniken"
        assert entities[0].confidence == 0.95
        assert entities[0].occurrences == 3
        assert entities[0].source_document_refs == ["doc-1"]

    def test_sets_source_document_ref(self, bedrock_client, service):
        bedrock_client.invoke_model.return_value = _make_bedrock_response([
            {"entity_type": "event", "canonical_name": "Roswell Incident", "confidence": 0.9, "occurrences": 1},
        ])

        entities = service.extract_entities("text", "my-doc-42")
        assert entities[0].source_document_refs == ["my-doc-42"]

    def test_filters_invalid_entity_types(self, bedrock_client, service):
        bedrock_client.invoke_model.return_value = _make_bedrock_response([
            {"entity_type": "person", "canonical_name": "Valid", "confidence": 0.9, "occurrences": 1},
            {"entity_type": "spaceship", "canonical_name": "Invalid", "confidence": 0.9, "occurrences": 1},
        ])

        entities = service.extract_entities("text", "doc-1")
        assert len(entities) == 1
        assert entities[0].canonical_name == "Valid"

    def test_clamps_confidence_to_valid_range(self, bedrock_client, service):
        bedrock_client.invoke_model.return_value = _make_bedrock_response([
            {"entity_type": "person", "canonical_name": "A", "confidence": 1.5, "occurrences": 1},
            {"entity_type": "person", "canonical_name": "B", "confidence": -0.3, "occurrences": 1},
        ])

        entities = service.extract_entities("text", "doc-1")
        assert entities[0].confidence == 1.0
        assert entities[1].confidence == 0.0

    def test_minimum_occurrence_is_one(self, bedrock_client, service):
        bedrock_client.invoke_model.return_value = _make_bedrock_response([
            {"entity_type": "location", "canonical_name": "Giza", "confidence": 0.8, "occurrences": 0},
        ])

        entities = service.extract_entities("text", "doc-1")
        assert entities[0].occurrences == 1

    def test_handles_empty_response(self, bedrock_client, service):
        bedrock_client.invoke_model.return_value = _make_bedrock_response([])

        entities = service.extract_entities("text", "doc-1")
        assert entities == []

    def test_all_valid_entity_types_accepted(self, bedrock_client, service):
        all_types = [
            {"entity_type": t.value, "canonical_name": f"Entity_{t.value}", "confidence": 0.8, "occurrences": 1}
            for t in EntityType
        ]
        bedrock_client.invoke_model.return_value = _make_bedrock_response(all_types)

        entities = service.extract_entities("text", "doc-1")
        assert len(entities) == len(EntityType)
        extracted_types = {e.entity_type for e in entities}
        assert extracted_types == set(EntityType)

    def test_handles_code_fenced_response(self, bedrock_client, service):
        fenced = '```json\n[{"entity_type": "person", "canonical_name": "Tesla", "confidence": 0.9, "occurrences": 2}]\n```'
        bedrock_client.invoke_model.return_value = _make_bedrock_response_raw(fenced)

        entities = service.extract_entities("text", "doc-1")
        assert len(entities) == 1
        assert entities[0].canonical_name == "Tesla"

    def test_calls_bedrock_invoke_model(self, bedrock_client, service):
        bedrock_client.invoke_model.return_value = _make_bedrock_response([])
        service.extract_entities("some text", "doc-1")

        bedrock_client.invoke_model.assert_called_once()
        call_kwargs = bedrock_client.invoke_model.call_args
        assert call_kwargs.kwargs["modelId"] == "anthropic.claude-3-haiku-20240307-v1:0"


# ---------------------------------------------------------------------------
# extract_relationships — Requirement 9.4
# ---------------------------------------------------------------------------

class TestExtractRelationships:
    """Tests for extract_relationships() — Requirements 9.4."""

    def test_extracts_relationships(self, bedrock_client, service):
        entities = [
            ExtractedEntity(entity_type=EntityType.PERSON, canonical_name="Däniken", confidence=0.9, occurrences=1, source_document_refs=["doc-1"]),
            ExtractedEntity(entity_type=EntityType.LOCATION, canonical_name="Nazca", confidence=0.85, occurrences=1, source_document_refs=["doc-1"]),
        ]
        bedrock_client.invoke_model.return_value = _make_bedrock_response([
            {"source_entity": "Däniken", "target_entity": "Nazca", "relationship_type": "thematic", "confidence": 0.8},
        ])

        rels = service.extract_relationships("text", entities, "doc-1")

        assert len(rels) == 1
        assert rels[0].source_entity == "Däniken"
        assert rels[0].target_entity == "Nazca"
        assert rels[0].relationship_type == RelationshipType.THEMATIC
        assert rels[0].confidence == 0.8
        assert rels[0].source_document_ref == "doc-1"

    def test_filters_invalid_relationship_types(self, bedrock_client, service):
        entities = [
            ExtractedEntity(entity_type=EntityType.PERSON, canonical_name="A", confidence=0.9, occurrences=1, source_document_refs=["doc-1"]),
        ]
        bedrock_client.invoke_model.return_value = _make_bedrock_response([
            {"source_entity": "A", "target_entity": "B", "relationship_type": "causal", "confidence": 0.7},
            {"source_entity": "A", "target_entity": "C", "relationship_type": "magical", "confidence": 0.6},
        ])

        rels = service.extract_relationships("text", entities, "doc-1")
        assert len(rels) == 1
        assert rels[0].relationship_type == RelationshipType.CAUSAL

    def test_all_valid_relationship_types_accepted(self, bedrock_client, service):
        entities = [
            ExtractedEntity(entity_type=EntityType.PERSON, canonical_name="X", confidence=0.9, occurrences=1, source_document_refs=["doc-1"]),
        ]
        all_rels = [
            {"source_entity": "X", "target_entity": "Y", "relationship_type": rt.value, "confidence": 0.7}
            for rt in RelationshipType
        ]
        bedrock_client.invoke_model.return_value = _make_bedrock_response(all_rels)

        rels = service.extract_relationships("text", entities, "doc-1")
        assert len(rels) == len(RelationshipType)
        extracted_types = {r.relationship_type for r in rels}
        assert extracted_types == set(RelationshipType)

    def test_handles_empty_relationships(self, bedrock_client, service):
        bedrock_client.invoke_model.return_value = _make_bedrock_response([])
        rels = service.extract_relationships("text", [], "doc-1")
        assert rels == []

    def test_clamps_relationship_confidence(self, bedrock_client, service):
        entities = [
            ExtractedEntity(entity_type=EntityType.PERSON, canonical_name="A", confidence=0.9, occurrences=1, source_document_refs=["doc-1"]),
        ]
        bedrock_client.invoke_model.return_value = _make_bedrock_response([
            {"source_entity": "A", "target_entity": "B", "relationship_type": "temporal", "confidence": 2.0},
        ])

        rels = service.extract_relationships("text", entities, "doc-1")
        assert rels[0].confidence == 1.0


# ---------------------------------------------------------------------------
# merge_entities — Requirement 9.3
# ---------------------------------------------------------------------------

class TestMergeEntities:
    """Tests for merge_entities() — Requirement 9.3."""

    def test_merge_no_duplicates(self):
        existing = [
            ExtractedEntity(entity_type=EntityType.PERSON, canonical_name="Alice", confidence=0.9, occurrences=2, source_document_refs=["doc-1"]),
        ]
        new = [
            ExtractedEntity(entity_type=EntityType.LOCATION, canonical_name="Cairo", confidence=0.8, occurrences=1, source_document_refs=["doc-2"]),
        ]

        merged = EntityExtractionService.merge_entities(existing, new)
        assert len(merged) == 2

    def test_merge_duplicates_sums_occurrences(self):
        existing = [
            ExtractedEntity(entity_type=EntityType.PERSON, canonical_name="Alice", confidence=0.9, occurrences=3, source_document_refs=["doc-1"]),
        ]
        new = [
            ExtractedEntity(entity_type=EntityType.PERSON, canonical_name="Alice", confidence=0.85, occurrences=5, source_document_refs=["doc-2"]),
        ]

        merged = EntityExtractionService.merge_entities(existing, new)
        assert len(merged) == 1
        assert merged[0].occurrences == 8

    def test_merge_duplicates_unions_source_refs(self):
        existing = [
            ExtractedEntity(entity_type=EntityType.PERSON, canonical_name="Alice", confidence=0.9, occurrences=1, source_document_refs=["doc-1"]),
        ]
        new = [
            ExtractedEntity(entity_type=EntityType.PERSON, canonical_name="Alice", confidence=0.85, occurrences=1, source_document_refs=["doc-2"]),
        ]

        merged = EntityExtractionService.merge_entities(existing, new)
        assert set(merged[0].source_document_refs) == {"doc-1", "doc-2"}

    def test_merge_duplicates_no_duplicate_refs(self):
        existing = [
            ExtractedEntity(entity_type=EntityType.PERSON, canonical_name="Alice", confidence=0.9, occurrences=2, source_document_refs=["doc-1", "doc-2"]),
        ]
        new = [
            ExtractedEntity(entity_type=EntityType.PERSON, canonical_name="Alice", confidence=0.85, occurrences=3, source_document_refs=["doc-2", "doc-3"]),
        ]

        merged = EntityExtractionService.merge_entities(existing, new)
        assert merged[0].source_document_refs == ["doc-1", "doc-2", "doc-3"]

    def test_merge_keeps_higher_confidence(self):
        existing = [
            ExtractedEntity(entity_type=EntityType.PERSON, canonical_name="Alice", confidence=0.7, occurrences=1, source_document_refs=["doc-1"]),
        ]
        new = [
            ExtractedEntity(entity_type=EntityType.PERSON, canonical_name="Alice", confidence=0.95, occurrences=1, source_document_refs=["doc-2"]),
        ]

        merged = EntityExtractionService.merge_entities(existing, new)
        assert merged[0].confidence == 0.95

    def test_merge_same_name_different_type_not_merged(self):
        existing = [
            ExtractedEntity(entity_type=EntityType.PERSON, canonical_name="Mercury", confidence=0.9, occurrences=1, source_document_refs=["doc-1"]),
        ]
        new = [
            ExtractedEntity(entity_type=EntityType.LOCATION, canonical_name="Mercury", confidence=0.8, occurrences=1, source_document_refs=["doc-2"]),
        ]

        merged = EntityExtractionService.merge_entities(existing, new)
        assert len(merged) == 2

    def test_merge_empty_lists(self):
        merged = EntityExtractionService.merge_entities([], [])
        assert merged == []

    def test_merge_existing_only(self):
        existing = [
            ExtractedEntity(entity_type=EntityType.PERSON, canonical_name="Alice", confidence=0.9, occurrences=1, source_document_refs=["doc-1"]),
        ]
        merged = EntityExtractionService.merge_entities(existing, [])
        assert len(merged) == 1
        assert merged[0].canonical_name == "Alice"

    def test_merge_new_only(self):
        new = [
            ExtractedEntity(entity_type=EntityType.PERSON, canonical_name="Bob", confidence=0.8, occurrences=2, source_document_refs=["doc-2"]),
        ]
        merged = EntityExtractionService.merge_entities([], new)
        assert len(merged) == 1
        assert merged[0].canonical_name == "Bob"

    def test_merge_multiple_duplicates_across_lists(self):
        existing = [
            ExtractedEntity(entity_type=EntityType.PERSON, canonical_name="Alice", confidence=0.9, occurrences=2, source_document_refs=["doc-1"]),
            ExtractedEntity(entity_type=EntityType.LOCATION, canonical_name="Cairo", confidence=0.8, occurrences=1, source_document_refs=["doc-1"]),
        ]
        new = [
            ExtractedEntity(entity_type=EntityType.PERSON, canonical_name="Alice", confidence=0.7, occurrences=3, source_document_refs=["doc-2"]),
            ExtractedEntity(entity_type=EntityType.LOCATION, canonical_name="Cairo", confidence=0.85, occurrences=4, source_document_refs=["doc-2"]),
            ExtractedEntity(entity_type=EntityType.EVENT, canonical_name="Roswell", confidence=0.75, occurrences=1, source_document_refs=["doc-2"]),
        ]

        merged = EntityExtractionService.merge_entities(existing, new)
        assert len(merged) == 3

        by_name = {e.canonical_name: e for e in merged}
        assert by_name["Alice"].occurrences == 5
        assert by_name["Cairo"].occurrences == 5
        assert by_name["Cairo"].confidence == 0.85
        assert by_name["Roswell"].occurrences == 1


# ---------------------------------------------------------------------------
# normalize_dates — Date normalization post-processing
# ---------------------------------------------------------------------------

class TestNormalizeDates:
    """Tests for normalize_dates() — date normalization to ISO format."""

    def _make_date_entity(self, canonical_name: str) -> ExtractedEntity:
        return ExtractedEntity(
            entity_type=EntityType.DATE,
            canonical_name=canonical_name,
            confidence=0.9,
            occurrences=1,
            source_document_refs=["doc-1"],
        )

    def test_normalizes_mm_dd_yyyy(self):
        entities = [self._make_date_entity("10/28/2009")]
        result = EntityExtractionService.normalize_dates(entities)
        assert result[0].canonical_name == "2009-10-28 (10/28/2009)"

    def test_normalizes_mm_dd_yy(self):
        entities = [self._make_date_entity("10/28/09")]
        result = EntityExtractionService.normalize_dates(entities)
        assert result[0].canonical_name == "2009-10-28 (10/28/09)"

    def test_normalizes_month_dd_yyyy(self):
        entities = [self._make_date_entity("January 5, 2009")]
        result = EntityExtractionService.normalize_dates(entities)
        assert result[0].canonical_name == "2009-01-05 (January 5, 2009)"

    def test_normalizes_abbreviated_month(self):
        entities = [self._make_date_entity("Jan 5, 2009")]
        result = EntityExtractionService.normalize_dates(entities)
        assert result[0].canonical_name == "2009-01-05 (Jan 5, 2009)"

    def test_normalizes_dd_mon_yy(self):
        entities = [self._make_date_entity("28-Oct-09")]
        result = EntityExtractionService.normalize_dates(entities)
        assert result[0].canonical_name == "2009-10-28 (28-Oct-09)"

    def test_normalizes_dd_mon_yyyy(self):
        entities = [self._make_date_entity("28-Oct-2009")]
        result = EntityExtractionService.normalize_dates(entities)
        assert result[0].canonical_name == "2009-10-28 (28-Oct-2009)"

    def test_already_iso_format_unchanged(self):
        """Pure ISO date is recognized and left as-is (no redundant wrapping)."""
        entities = [self._make_date_entity("2009-10-28")]
        result = EntityExtractionService.normalize_dates(entities)
        assert result[0].canonical_name == "2009-10-28"

    def test_unparseable_date_left_unchanged(self):
        entities = [self._make_date_entity("sometime in the 1990s")]
        result = EntityExtractionService.normalize_dates(entities)
        assert result[0].canonical_name == "sometime in the 1990s"

    def test_non_date_entities_unchanged(self):
        person = ExtractedEntity(
            entity_type=EntityType.PERSON,
            canonical_name="Alice",
            confidence=0.9,
            occurrences=1,
            source_document_refs=["doc-1"],
        )
        entities = [person, self._make_date_entity("10/28/2009")]
        result = EntityExtractionService.normalize_dates(entities)
        assert result[0].canonical_name == "Alice"
        assert result[1].canonical_name == "2009-10-28 (10/28/2009)"

    def test_empty_list(self):
        result = EntityExtractionService.normalize_dates([])
        assert result == []

    def test_mixed_parseable_and_unparseable(self):
        entities = [
            self._make_date_entity("10/28/2009"),
            self._make_date_entity("circa 2000 BCE"),
            self._make_date_entity("March 15, 2020"),
        ]
        result = EntityExtractionService.normalize_dates(entities)
        assert result[0].canonical_name == "2009-10-28 (10/28/2009)"
        assert result[1].canonical_name == "circa 2000 BCE"
        assert result[2].canonical_name == "2020-03-15 (March 15, 2020)"

    def test_mm_dd_yy_century_boundary(self):
        """YY < 70 maps to 2000s, YY >= 70 maps to 1900s."""
        entities = [
            self._make_date_entity("01/15/69"),
            self._make_date_entity("01/15/70"),
        ]
        result = EntityExtractionService.normalize_dates(entities)
        assert result[0].canonical_name.startswith("2069-01-15")
        assert result[1].canonical_name.startswith("1970-01-15")

    def test_normalizes_with_dashes_instead_of_slashes(self):
        entities = [self._make_date_entity("10-28-2009")]
        result = EntityExtractionService.normalize_dates(entities)
        assert result[0].canonical_name == "2009-10-28 (10-28-2009)"

    def test_does_not_double_normalize(self):
        """If canonical_name already starts with ISO date, leave it alone."""
        entities = [self._make_date_entity("2009-10-28 (10/28/09)")]
        result = EntityExtractionService.normalize_dates(entities)
        assert result[0].canonical_name == "2009-10-28 (10/28/09)"
