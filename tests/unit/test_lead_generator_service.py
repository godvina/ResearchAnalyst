"""Unit tests for LeadGeneratorService.generate_leads."""

import io
import json
import uuid
from unittest.mock import MagicMock, patch

import pytest

from services.lead_generator_service import (
    InvestigationLead,
    LeadGeneratorService,
    VALID_LEAD_TYPES,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_bedrock_response(leads_json: list) -> MagicMock:
    """Build a mock Bedrock invoke_model response."""
    body_bytes = json.dumps({
        "content": [{"text": json.dumps(leads_json)}],
    }).encode("utf-8")
    resp = MagicMock()
    resp.__getitem__ = lambda self, k: {"body": io.BytesIO(body_bytes)}[k]
    return resp


def _make_aurora_cm(doc_rows=None, entity_rows=None):
    """Build a mock Aurora connection manager with cursor context manager."""
    cur = MagicMock()
    call_count = {"n": 0}

    def _execute(sql, params=None):
        pass

    def _fetchall():
        call_count["n"] += 1
        if call_count["n"] == 1:
            return doc_rows or []
        return entity_rows or []

    cur.execute = _execute
    cur.fetchall = _fetchall
    cm = MagicMock()
    cm.cursor.return_value.__enter__ = MagicMock(return_value=cur)
    cm.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return cm


SAMPLE_LEADS_JSON = [
    {
        "narrative": "Von Braun appears in 14 documents spanning 1945-1969 with unexplained gaps.",
        "lead_type": "temporal_gap",
        "confidence": 0.87,
        "supporting_entity_names": ["NASA", "Operation Paperclip"],
        "document_count": 14,
        "date_range": "1945-1969",
    },
    {
        "narrative": "Entity cluster of 8 German scientists appear together across 12 episodes.",
        "lead_type": "entity_cluster",
        "confidence": 0.75,
        "supporting_entity_names": ["Von Braun", "V-2 Rocket"],
        "document_count": 12,
        "date_range": "1942-1960",
    },
    {
        "narrative": "Geographic convergence: Egypt, Peru, Cambodia mentioned in same context 23 times.",
        "lead_type": "geographic_convergence",
        "confidence": 0.65,
        "supporting_entity_names": ["Egypt", "Peru", "Cambodia"],
        "document_count": 23,
        "date_range": None,
    },
]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestGenerateLeads:
    """Tests for LeadGeneratorService.generate_leads."""

    def test_returns_leads_from_bedrock(self):
        """Bedrock returns valid leads — should parse and return them."""
        aurora = _make_aurora_cm(
            doc_rows=[("doc1", "file1.txt", "Von Braun was a rocket scientist")],
        )
        bedrock = MagicMock()
        bedrock.invoke_model.return_value = _make_bedrock_response(SAMPLE_LEADS_JSON)

        svc = LeadGeneratorService(aurora, bedrock)
        leads = svc.generate_leads("case-1", "Von Braun", "person")

        assert 3 <= len(leads) <= 7
        assert all(isinstance(l, InvestigationLead) for l in leads)

    def test_leads_sorted_by_confidence_descending(self):
        """Leads should be sorted by confidence descending."""
        aurora = _make_aurora_cm()
        bedrock = MagicMock()
        bedrock.invoke_model.return_value = _make_bedrock_response(SAMPLE_LEADS_JSON)

        svc = LeadGeneratorService(aurora, bedrock)
        leads = svc.generate_leads("case-1", "Von Braun", "person")

        for i in range(len(leads) - 1):
            assert leads[i].confidence >= leads[i + 1].confidence

    def test_lead_type_validated(self):
        """Invalid lead_type should be replaced with 'document_pattern'."""
        bad_leads = [
            {
                "narrative": "Some finding about Von Braun.",
                "lead_type": "INVALID_TYPE",
                "confidence": 0.9,
                "supporting_entity_names": ["Von Braun"],
                "document_count": 5,
                "date_range": None,
            },
            {
                "narrative": "Another finding about Von Braun.",
                "lead_type": "temporal_gap",
                "confidence": 0.8,
                "supporting_entity_names": ["Von Braun"],
                "document_count": 3,
                "date_range": None,
            },
            {
                "narrative": "Third finding about Von Braun.",
                "lead_type": "entity_cluster",
                "confidence": 0.7,
                "supporting_entity_names": ["Von Braun"],
                "document_count": 2,
                "date_range": None,
            },
        ]
        aurora = _make_aurora_cm()
        bedrock = MagicMock()
        bedrock.invoke_model.return_value = _make_bedrock_response(bad_leads)

        svc = LeadGeneratorService(aurora, bedrock)
        leads = svc.generate_leads("case-1", "Von Braun", "person")

        for lead in leads:
            assert lead.lead_type in VALID_LEAD_TYPES

    def test_confidence_clamped(self):
        """Confidence values outside [0, 1] should be clamped."""
        out_of_range = [
            {
                "narrative": f"Finding {i} about Von Braun.",
                "lead_type": "temporal_gap",
                "confidence": c,
                "supporting_entity_names": ["Von Braun"],
                "document_count": 1,
                "date_range": None,
            }
            for i, c in enumerate([1.5, -0.3, 0.5])
        ]
        aurora = _make_aurora_cm()
        bedrock = MagicMock()
        bedrock.invoke_model.return_value = _make_bedrock_response(out_of_range)

        svc = LeadGeneratorService(aurora, bedrock)
        leads = svc.generate_leads("case-1", "Von Braun", "person")

        for lead in leads:
            assert 0.0 <= lead.confidence <= 1.0

    def test_pads_to_minimum_3(self):
        """If Bedrock returns fewer than 3 leads, pad with fallback."""
        one_lead = [SAMPLE_LEADS_JSON[0]]
        aurora = _make_aurora_cm()
        bedrock = MagicMock()
        bedrock.invoke_model.return_value = _make_bedrock_response(one_lead)

        svc = LeadGeneratorService(aurora, bedrock)
        leads = svc.generate_leads("case-1", "Von Braun", "person")

        assert len(leads) >= 3

    def test_truncates_to_maximum_7(self):
        """If Bedrock returns more than 7 leads, truncate to 7."""
        many_leads = [
            {
                "narrative": f"Finding {i} about Von Braun.",
                "lead_type": "temporal_gap",
                "confidence": 0.9 - i * 0.05,
                "supporting_entity_names": ["Von Braun"],
                "document_count": i + 1,
                "date_range": None,
            }
            for i in range(10)
        ]
        aurora = _make_aurora_cm()
        bedrock = MagicMock()
        bedrock.invoke_model.return_value = _make_bedrock_response(many_leads)

        svc = LeadGeneratorService(aurora, bedrock)
        leads = svc.generate_leads("case-1", "Von Braun", "person")

        assert len(leads) <= 7

    def test_bedrock_failure_returns_fallback(self):
        """When Bedrock raises, should return fallback leads (padded to 3)."""
        aurora = _make_aurora_cm()
        bedrock = MagicMock()
        bedrock.invoke_model.side_effect = Exception("Bedrock timeout")

        svc = LeadGeneratorService(aurora, bedrock)
        leads = svc.generate_leads("case-1", "Von Braun", "person")

        # _generate_fallback_leads is a placeholder returning [], so padding kicks in
        assert len(leads) >= 3
        for lead in leads:
            assert lead.lead_type in VALID_LEAD_TYPES
            assert 0.0 <= lead.confidence <= 1.0

    def test_pattern_svc_integration(self):
        """When pattern_svc is provided, it should be queried."""
        aurora = _make_aurora_cm()
        bedrock = MagicMock()
        bedrock.invoke_model.return_value = _make_bedrock_response(SAMPLE_LEADS_JSON)

        pattern_svc = MagicMock()
        pattern_svc.discover_top_patterns.return_value = {
            "patterns": [
                {"entities": [{"name": "Von Braun"}], "question": "Why does Von Braun appear?"},
            ],
        }

        svc = LeadGeneratorService(aurora, bedrock, pattern_svc=pattern_svc)
        leads = svc.generate_leads("case-1", "Von Braun", "person")

        pattern_svc.discover_top_patterns.assert_called_once_with("case-1")
        assert len(leads) >= 3

    def test_to_dict_serialization(self):
        """InvestigationLead.to_dict should produce a JSON-serializable dict."""
        lead = InvestigationLead(
            lead_id=str(uuid.uuid4()),
            narrative="Test narrative",
            lead_type="temporal_gap",
            confidence=0.85,
            supporting_entity_names=["A", "B"],
            document_count=5,
            date_range="2020-2023",
        )
        d = lead.to_dict()
        assert d["narrative"] == "Test narrative"
        assert d["lead_type"] == "temporal_gap"
        assert d["confidence"] == 0.85
        assert json.dumps(d)  # should not raise


class TestGenerateFallbackLeads:
    """Tests for LeadGeneratorService._generate_fallback_leads (Req 5.4)."""

    def _make_svc(self):
        return LeadGeneratorService(_make_aurora_cm(), MagicMock())

    def test_returns_at_least_2_leads_with_neighbors_and_docs(self):
        """With neighbors and doc_count, should return at least 2 leads."""
        svc = self._make_svc()
        neighbors = [{"name": "NASA", "type": "organization"}, {"name": "V-2 Rocket", "type": "object"}]
        leads = svc._generate_fallback_leads("Von Braun", "person", neighbors, 14)

        assert len(leads) >= 2
        for lead in leads:
            assert isinstance(lead, InvestigationLead)

    def test_returns_at_least_2_leads_with_empty_neighbors(self):
        """With no neighbors, should still return at least 2 leads."""
        svc = self._make_svc()
        leads = svc._generate_fallback_leads("Von Braun", "person", [], 5)

        assert len(leads) >= 2

    def test_returns_at_least_2_leads_with_zero_docs(self):
        """With zero doc_count, should still return at least 2 leads."""
        svc = self._make_svc()
        neighbors = [{"name": "NASA", "type": "organization"}]
        leads = svc._generate_fallback_leads("Von Braun", "person", neighbors, 0)

        assert len(leads) >= 2

    def test_returns_at_least_2_leads_with_nothing(self):
        """With no neighbors and no docs, should still return at least 2 leads."""
        svc = self._make_svc()
        leads = svc._generate_fallback_leads("Von Braun", "person", [], 0)

        assert len(leads) >= 2

    def test_all_leads_have_valid_lead_type(self):
        """Every fallback lead must have a lead_type from VALID_LEAD_TYPES."""
        svc = self._make_svc()
        neighbors = [{"name": f"Entity_{i}", "type": "person"} for i in range(10)]
        leads = svc._generate_fallback_leads("Von Braun", "person", neighbors, 14)

        for lead in leads:
            assert lead.lead_type in VALID_LEAD_TYPES, f"Invalid lead_type: {lead.lead_type}"

    def test_all_leads_have_valid_confidence(self):
        """Every fallback lead must have confidence in [0.0, 1.0]."""
        svc = self._make_svc()
        neighbors = [{"name": f"Entity_{i}", "type": "person"} for i in range(50)]
        leads = svc._generate_fallback_leads("Von Braun", "person", neighbors, 100)

        for lead in leads:
            assert 0.0 <= lead.confidence <= 1.0, f"Confidence out of range: {lead.confidence}"

    def test_narratives_contain_entity_name(self):
        """Fallback lead narratives should reference the entity name."""
        svc = self._make_svc()
        leads = svc._generate_fallback_leads("Von Braun", "person", [{"name": "NASA", "type": "org"}], 14)

        for lead in leads:
            assert "Von Braun" in lead.narrative

    def test_narratives_are_not_raw_metrics(self):
        """Narratives should contain investigative framing, not just numbers."""
        svc = self._make_svc()
        neighbors = [{"name": "NASA", "type": "organization"}, {"name": "Operation Paperclip", "type": "event"}]
        leads = svc._generate_fallback_leads("Von Braun", "person", neighbors, 14)

        for lead in leads:
            assert len(lead.narrative) > 50, "Narrative too short to be meaningful"
            # Should contain investigative language
            assert any(word in lead.narrative.lower() for word in [
                "investigation", "analysis", "pattern", "anomaly", "warrants",
                "reveal", "surface", "suggest", "cluster", "cross-referencing",
            ]), f"Narrative lacks investigative framing: {lead.narrative}"

    def test_neighbor_names_appear_in_cluster_lead(self):
        """When neighbors exist, the cluster lead should mention some of them."""
        svc = self._make_svc()
        neighbors = [{"name": "NASA", "type": "organization"}, {"name": "Operation Paperclip", "type": "event"}]
        leads = svc._generate_fallback_leads("Von Braun", "person", neighbors, 14)

        cluster_leads = [l for l in leads if l.lead_type == "entity_cluster"]
        assert len(cluster_leads) >= 1
        narrative = cluster_leads[0].narrative
        assert any(n["name"] in narrative for n in neighbors)

    def test_three_leads_when_both_neighbors_and_docs(self):
        """When both neighbors and docs exist, should produce 3 leads (bonus cross-ref)."""
        svc = self._make_svc()
        neighbors = [{"name": "NASA", "type": "organization"}]
        leads = svc._generate_fallback_leads("Von Braun", "person", neighbors, 5)

        assert len(leads) >= 3
