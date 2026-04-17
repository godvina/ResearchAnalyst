"""Unit tests for core data model classes and enums."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from src.models.case_file import CaseFile, CaseFileStatus, CrossCaseGraph
from src.models.document import BatchResult, ExtractionResult, ParsedDocument
from src.models.entity import (
    EntityType,
    ExtractedEntity,
    ExtractedRelationship,
    RelationshipType,
)
from src.models.pattern import (
    CrossCaseMatch,
    CrossReferenceReport,
    Pattern,
    PatternReport,
)
from src.models.search import AnalysisSummary, SearchResult


class TestCaseFileStatus:
    def test_all_statuses_exist(self):
        expected = {"created", "ingesting", "indexed", "investigating", "archived", "error"}
        assert {s.value for s in CaseFileStatus} == expected

    def test_status_is_str_enum(self):
        assert CaseFileStatus.CREATED == "created"


class TestCaseFile:
    def test_create_minimal(self):
        cf = CaseFile(
            case_id="abc-123",
            topic_name="Ancient Aliens",
            description="Research topic",
            created_at=datetime.now(timezone.utc),
            s3_prefix="cases/abc-123/",
            neptune_subgraph_label="Entity_abc-123",
        )
        assert cf.status == CaseFileStatus.CREATED
        assert cf.document_count == 0
        assert cf.findings == []
        assert cf.parent_case_id is None

    def test_create_sub_case(self):
        cf = CaseFile(
            case_id="child-1",
            topic_name="Sub topic",
            description="Drill-down",
            created_at=datetime.now(timezone.utc),
            s3_prefix="cases/child-1/",
            neptune_subgraph_label="Entity_child-1",
            parent_case_id="parent-1",
        )
        assert cf.parent_case_id == "parent-1"

    def test_negative_document_count_rejected(self):
        with pytest.raises(ValidationError):
            CaseFile(
                case_id="x",
                topic_name="t",
                description="d",
                created_at=datetime.now(timezone.utc),
                s3_prefix="s",
                neptune_subgraph_label="n",
                document_count=-1,
            )

    def test_invalid_status_rejected(self):
        with pytest.raises(ValidationError):
            CaseFile(
                case_id="x",
                topic_name="t",
                description="d",
                status="bogus",
                created_at=datetime.now(timezone.utc),
                s3_prefix="s",
                neptune_subgraph_label="n",
            )


class TestCrossCaseGraph:
    def test_create(self):
        g = CrossCaseGraph(
            graph_id="g-1",
            name="Cross investigation",
            linked_case_ids=["c-1", "c-2"],
            created_at=datetime.now(timezone.utc),
            neptune_subgraph_label="CrossCase_g-1",
        )
        assert g.status == "active"
        assert g.analyst_notes == ""
        assert len(g.linked_case_ids) == 2


class TestEntityEnums:
    def test_entity_types(self):
        expected = {"person", "location", "date", "artifact", "civilization", "theme", "event"}
        assert {e.value for e in EntityType} == expected

    def test_relationship_types(self):
        expected = {"co-occurrence", "causal", "temporal", "geographic", "thematic"}
        assert {r.value for r in RelationshipType} == expected


class TestExtractedEntity:
    def test_valid_entity(self):
        e = ExtractedEntity(
            entity_type=EntityType.PERSON,
            canonical_name="Erich von Däniken",
            confidence=0.95,
            occurrences=3,
            source_document_refs=["doc-1"],
        )
        assert e.entity_type == EntityType.PERSON

    def test_confidence_out_of_range(self):
        with pytest.raises(ValidationError):
            ExtractedEntity(
                entity_type=EntityType.PERSON,
                canonical_name="Test",
                confidence=1.5,
                occurrences=1,
                source_document_refs=["doc-1"],
            )

    def test_zero_occurrences_rejected(self):
        with pytest.raises(ValidationError):
            ExtractedEntity(
                entity_type=EntityType.PERSON,
                canonical_name="Test",
                confidence=0.5,
                occurrences=0,
                source_document_refs=["doc-1"],
            )

    def test_empty_source_refs_rejected(self):
        with pytest.raises(ValidationError):
            ExtractedEntity(
                entity_type=EntityType.PERSON,
                canonical_name="Test",
                confidence=0.5,
                occurrences=1,
                source_document_refs=[],
            )


class TestExtractedRelationship:
    def test_valid_relationship(self):
        r = ExtractedRelationship(
            source_entity="Entity A",
            target_entity="Entity B",
            relationship_type=RelationshipType.CAUSAL,
            confidence=0.8,
            source_document_ref="doc-1",
        )
        assert r.relationship_type == RelationshipType.CAUSAL


class TestParsedDocument:
    def test_defaults(self):
        doc = ParsedDocument(
            document_id="d-1",
            case_file_id="c-1",
            source_metadata={"filename": "test.txt"},
            raw_text="Hello world",
        )
        assert doc.sections == []
        assert doc.parse_errors == []


class TestExtractionResult:
    def test_defaults(self):
        er = ExtractionResult(document_id="d-1")
        assert er.entities == []
        assert er.relationships == []


class TestBatchResult:
    def test_valid(self):
        br = BatchResult(
            case_file_id="c-1",
            total_documents=10,
            successful=8,
            failed=2,
            document_count=8,
            entity_count=50,
            relationship_count=30,
            failures=[{"document_id": "d-3", "error": "parse failure"}],
        )
        assert br.failed == 2

    def test_negative_counts_rejected(self):
        with pytest.raises(ValidationError):
            BatchResult(
                case_file_id="c-1",
                total_documents=-1,
                successful=0,
                failed=0,
                document_count=0,
                entity_count=0,
                relationship_count=0,
            )


class TestPattern:
    def test_valid(self):
        p = Pattern(
            pattern_id="p-1",
            entities_involved=[{"entity_id": "e-1", "name": "X", "type": "person"}],
            connection_type="graph-based",
            explanation="Found via centrality",
            confidence_score=0.9,
            novelty_score=0.7,
        )
        assert p.source_documents == []

    def test_confidence_bounds(self):
        with pytest.raises(ValidationError):
            Pattern(
                pattern_id="p-1",
                entities_involved=[],
                connection_type="graph-based",
                explanation="test",
                confidence_score=-0.1,
                novelty_score=0.5,
            )


class TestPatternReport:
    def test_defaults(self):
        pr = PatternReport(report_id="r-1", case_file_id="c-1")
        assert pr.patterns == []
        assert pr.graph_patterns_count == 0


class TestCrossCaseMatch:
    def test_valid(self):
        m = CrossCaseMatch(
            entity_a={"entity_id": "e-1", "name": "X", "type": "person", "case_id": "c-1"},
            entity_b={"entity_id": "e-2", "name": "X", "type": "person", "case_id": "c-2"},
            similarity_score=0.85,
            ai_explanation="Same person referenced in both cases",
        )
        assert m.similarity_score == 0.85


class TestCrossReferenceReport:
    def test_defaults(self):
        r = CrossReferenceReport(report_id="r-1", case_ids=["c-1", "c-2"])
        assert r.shared_entities == []
        assert r.ai_analysis == ""


class TestSearchResult:
    def test_valid(self):
        sr = SearchResult(
            document_id="d-1",
            passage="relevant text here",
            relevance_score=0.92,
            source_document_ref="doc-1",
            surrounding_context="...before relevant text here after...",
        )
        assert sr.relevance_score == 0.92

    def test_relevance_bounds(self):
        with pytest.raises(ValidationError):
            SearchResult(
                document_id="d-1",
                passage="text",
                relevance_score=2.0,
                source_document_ref="doc-1",
            )


class TestAnalysisSummary:
    def test_valid(self):
        a = AnalysisSummary(
            subject="Erich von Däniken",
            summary="Key figure in ancient astronaut theory",
            confidence=0.88,
        )
        assert a.supporting_passages == []
