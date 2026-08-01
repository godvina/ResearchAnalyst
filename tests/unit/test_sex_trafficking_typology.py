"""Unit tests for Sex Trafficking Crime Typology engine."""
import pytest
from services.sex_trafficking_typology import (
    SexTraffickingTypologyEngine,
    TYPOLOGY_CATEGORIES,
    TypologyReport,
)


class TestTypologyCategories:
    """Verify the 6 typology categories are properly defined."""

    def test_has_six_categories(self):
        assert len(TYPOLOGY_CATEGORIES) == 6

    def test_category_ids(self):
        ids = [c.id for c in TYPOLOGY_CATEGORIES]
        assert "recruitment_grooming" in ids
        assert "transportation_movement" in ids
        assert "financial_control" in ids
        assert "communication_networks" in ids
        assert "venue_infrastructure" in ids
        assert "power_control" in ids

    def test_each_category_has_flags(self):
        for cat in TYPOLOGY_CATEGORIES:
            assert len(cat.flags) >= 4, f"{cat.id} has too few flags"
            total_weight = sum(f.weight for f in cat.flags)
            assert abs(total_weight - 1.0) < 0.01, f"{cat.id} flag weights don't sum to 1.0"

    def test_each_category_has_evidence_example(self):
        for cat in TYPOLOGY_CATEGORIES:
            assert len(cat.evidence_examples) >= 1
            assert cat.evidence_examples[0].text


class TestTypologyEngine:
    """Test the scoring engine."""

    def test_empty_entities_returns_zero_scores(self):
        engine = SexTraffickingTypologyEngine()
        report = engine.analyze_case("test-case-id", entities=[], relationships=[])
        assert isinstance(report, TypologyReport)
        assert report.overall_score == 0.0
        assert report.flags_triggered == 0

    def test_person_and_victim_entities_trigger_recruitment(self):
        engine = SexTraffickingTypologyEngine()
        entities = [
            {"entity_id": "1", "canonical_name": "Subject A", "entity_type": "person", "document_count": 10},
            {"entity_id": "2", "canonical_name": "Victim B", "entity_type": "victim", "document_count": 5},
            {"entity_id": "3", "canonical_name": "Victim C", "entity_type": "minor", "document_count": 3},
        ]
        report = engine.analyze_case("test-case-id", entities=entities, relationships=[])
        
        recruitment_score = next(s for s in report.scores if s.category_id == "recruitment_grooming")
        assert recruitment_score.score > 0
        assert len(recruitment_score.matched_flags) >= 1

    def test_location_entities_trigger_transportation(self):
        engine = SexTraffickingTypologyEngine()
        entities = [
            {"entity_id": "1", "canonical_name": "Miami", "entity_type": "location", "document_count": 8},
            {"entity_id": "2", "canonical_name": "Atlanta", "entity_type": "location", "document_count": 6},
            {"entity_id": "3", "canonical_name": "Charlotte", "entity_type": "location", "document_count": 4},
            {"entity_id": "4", "canonical_name": "Hotel Marriott", "entity_type": "hotel", "document_count": 3},
        ]
        report = engine.analyze_case("test-case-id", entities=entities, relationships=[])
        
        transport_score = next(s for s in report.scores if s.category_id == "transportation_movement")
        assert transport_score.score > 0

    def test_financial_entities_trigger_financial_control(self):
        engine = SexTraffickingTypologyEngine()
        entities = [
            {"entity_id": "1", "canonical_name": "$9,500", "entity_type": "financial_amount", "document_count": 12},
            {"entity_id": "2", "canonical_name": "Wells Fargo #4421", "entity_type": "account_number", "document_count": 5},
            {"entity_id": "3", "canonical_name": "$8,900", "entity_type": "financial_amount", "document_count": 8},
        ]
        report = engine.analyze_case("test-case-id", entities=entities, relationships=[])
        
        financial_score = next(s for s in report.scores if s.category_id == "financial_control")
        assert financial_score.score > 0
        assert len(financial_score.matched_flags) >= 1

    def test_frontend_payload_format(self):
        engine = SexTraffickingTypologyEngine()
        report = engine.analyze_case("test-id", entities=[], relationships=[])
        report.case_name = "Test Case"
        payload = engine.to_frontend_payload(report)

        assert payload["case_id"] == "test-id"
        assert payload["case_name"] == "Test Case"
        assert len(payload["categories"]) == 6
        assert "overall_score" in payload
        assert "flags_triggered" in payload
        assert "recommendations" in payload

    def test_combinatorial_bonus(self):
        """Multiple flags firing gives bonus score."""
        engine = SexTraffickingTypologyEngine()
        # Lots of comms entities to trigger multiple flags
        entities = [
            {"entity_id": str(i), "canonical_name": f"Phone {i}", "entity_type": "phone_number", "document_count": 5}
            for i in range(10)
        ] + [
            {"entity_id": "e1", "canonical_name": "user@email.com", "entity_type": "email", "document_count": 3},
            {"entity_id": "e2", "canonical_name": "@handle", "entity_type": "social_media_handle", "document_count": 4},
        ]
        report = engine.analyze_case("test-case-id", entities=entities, relationships=[])
        
        comms_score = next(s for s in report.scores if s.category_id == "communication_networks")
        # Should have multiple flags and bonus
        assert comms_score.score > 30
