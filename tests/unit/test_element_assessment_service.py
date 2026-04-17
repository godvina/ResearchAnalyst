"""Unit tests for ElementAssessmentService.

Covers:
- Bedrock fallback returns yellow/0/unavailable
- compute_readiness_score formula: round((green+yellow)/total * 100)
- suggest_alternative_charges returns at most 5, sorted by likelihood descending
- recommend_statutes returns non-empty list sorted by match_strength descending
- Senior Legal Analyst Persona system prompt is included in Bedrock calls
"""

import io
import json
from contextlib import contextmanager
from unittest.mock import MagicMock, patch, call

import pytest

from src.models.prosecutor import (
    ConfidenceLevel,
    DecisionState,
    SupportRating,
)
from src.services.element_assessment_service import ElementAssessmentService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _FreshBytesIO:
    """A wrapper that returns a fresh BytesIO on each .read() call,
    so the same mock return_value works across multiple invocations."""

    def __init__(self, data: bytes):
        self._data = data

    def read(self):
        return self._data


def _bedrock_response(payload: dict | list) -> dict:
    """Build a mock Bedrock invoke_model response."""
    body_text = json.dumps(payload)
    content = json.dumps({"content": [{"text": body_text}]})
    return {"body": _FreshBytesIO(content.encode())}


def _make_mock_db(
    elements=None,
    evidence=None,
    citation="18 U.S.C. § 1591",
):
    """Build a mock Aurora connection manager.

    `elements` — list of tuples (element_id, statute_id, display_name, description, order)
    `evidence`  — list of tuples (document_id, filename, doc_type)
    """
    if elements is None:
        elements = []
    if evidence is None:
        evidence = []

    cursor = MagicMock()
    call_count = {"n": 0}

    def _execute(sql, params=None):
        call_count["n"] += 1
        sql_lower = sql.strip().lower()
        if "statutory_elements" in sql_lower:
            cursor.fetchall.return_value = elements
            cursor.fetchone.return_value = elements[0] if elements else None
        elif "case_documents" in sql_lower:
            cursor.fetchall.return_value = evidence
        elif "citation" in sql_lower or "statutes" in sql_lower:
            cursor.fetchone.return_value = (citation,)
        else:
            cursor.fetchall.return_value = []
            cursor.fetchone.return_value = None

    cursor.execute = _execute

    db = MagicMock()

    @contextmanager
    def _cursor_ctx():
        yield cursor

    db.cursor = _cursor_ctx
    return db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_ELEMENTS = [
    ("elem-1", "stat-1", "Interstate Commerce", "Prove interstate nexus", 1),
    ("elem-2", "stat-1", "Force or Coercion", "Prove use of force", 2),
    ("elem-3", "stat-1", "Commercial Sex Act", "Prove commercial sex act", 3),
]

SAMPLE_EVIDENCE = [
    ("doc-1", "financial_records.pdf", "document"),
    ("doc-2", "witness_statement.pdf", "document"),
]


@pytest.fixture()
def mock_db():
    return _make_mock_db(elements=SAMPLE_ELEMENTS, evidence=SAMPLE_EVIDENCE)


@pytest.fixture()
def mock_neptune():
    cursor = MagicMock()
    cursor.fetchall.return_value = []
    cm = MagicMock()

    @contextmanager
    def _cursor_ctx():
        yield cursor

    cm.cursor = _cursor_ctx
    return cm


@pytest.fixture()
def mock_decision_svc():
    svc = MagicMock()
    decision = MagicMock()
    decision.decision_id = "decision-001"
    svc.create_decision.return_value = decision
    return svc


# ---------------------------------------------------------------------------
# Tests: Bedrock fallback
# ---------------------------------------------------------------------------

class TestBedrockFallback:
    """When Bedrock is unavailable (None), ratings should be yellow/0/unavailable."""

    def test_assess_single_returns_yellow_zero_unavailable(self, mock_db, mock_neptune):
        svc = ElementAssessmentService(
            aurora_cm=mock_db,
            neptune_cm=mock_neptune,
            bedrock_client=None,  # Bedrock unavailable
        )

        rating = svc.assess_single("case-1", "elem-1", "doc-1")

        assert rating.rating == SupportRating.YELLOW
        assert rating.confidence == 0
        assert "unavailable" in rating.reasoning.lower()

    def test_assess_elements_all_yellow_when_bedrock_down(self, mock_db, mock_neptune):
        svc = ElementAssessmentService(
            aurora_cm=mock_db,
            neptune_cm=mock_neptune,
            bedrock_client=None,
        )

        matrix = svc.assess_elements("case-1", "stat-1")

        for r in matrix.ratings:
            assert r.rating == SupportRating.YELLOW
            assert r.confidence == 0
            assert "unavailable" in r.reasoning.lower()

    def test_bedrock_exception_triggers_fallback(self, mock_db, mock_neptune):
        bedrock = MagicMock()
        bedrock.invoke_model.side_effect = Exception("Service unavailable")

        svc = ElementAssessmentService(
            aurora_cm=mock_db,
            neptune_cm=mock_neptune,
            bedrock_client=bedrock,
        )

        rating = svc.assess_single("case-1", "elem-1", "doc-1")

        assert rating.rating == SupportRating.YELLOW
        assert rating.confidence == 0
        assert "unavailable" in rating.reasoning.lower()


# ---------------------------------------------------------------------------
# Tests: compute_readiness_score formula
# ---------------------------------------------------------------------------

class TestReadinessScore:
    """Readiness = round((green + yellow) / total * 100)."""

    def test_all_green_yields_100(self, mock_neptune):
        """3 elements, all green → 100%."""
        bedrock = MagicMock()
        bedrock.invoke_model.return_value = _bedrock_response({
            "rating": "green", "confidence": 90,
            "reasoning": "Strong", "legal_justification": "Solid evidence",
        })

        db = _make_mock_db(elements=SAMPLE_ELEMENTS, evidence=SAMPLE_EVIDENCE)
        svc = ElementAssessmentService(
            aurora_cm=db, neptune_cm=mock_neptune, bedrock_client=bedrock,
        )

        score = svc.compute_readiness_score("case-1", "stat-1")

        assert score.score == 100
        assert score.covered_elements == 3
        assert score.total_elements == 3
        assert score.missing_elements == []

    def test_all_red_yields_0(self, mock_neptune):
        """3 elements, all red → 0%."""
        bedrock = MagicMock()
        bedrock.invoke_model.return_value = _bedrock_response({
            "rating": "red", "confidence": 10,
            "reasoning": "No support", "legal_justification": "Insufficient",
        })

        db = _make_mock_db(elements=SAMPLE_ELEMENTS, evidence=SAMPLE_EVIDENCE)
        svc = ElementAssessmentService(
            aurora_cm=db, neptune_cm=mock_neptune, bedrock_client=bedrock,
        )

        score = svc.compute_readiness_score("case-1", "stat-1")

        assert score.score == 0
        assert score.covered_elements == 0
        assert score.total_elements == 3
        assert len(score.missing_elements) == 3

    def test_mixed_ratings_formula(self, mock_neptune):
        """2 elements covered (green/yellow), 1 red → round(2/3*100) = 67%."""
        call_idx = {"n": 0}

        def _invoke_model(**kwargs):
            call_idx["n"] += 1
            body = json.loads(kwargs.get("body", "{}"))
            prompt = body.get("messages", [{}])[0].get("content", "")

            # First element gets green, second gets yellow, third gets red
            # Each element is rated against 2 evidence items
            # elem-1 (calls 1-2): green
            # elem-2 (calls 3-4): yellow
            # elem-3 (calls 5-6): red
            idx = call_idx["n"]
            if idx <= 2:
                rating = "green"
            elif idx <= 4:
                rating = "yellow"
            else:
                rating = "red"

            return _bedrock_response({
                "rating": rating, "confidence": 70,
                "reasoning": "Test", "legal_justification": "Test",
            })

        bedrock = MagicMock()
        bedrock.invoke_model.side_effect = _invoke_model

        db = _make_mock_db(elements=SAMPLE_ELEMENTS, evidence=SAMPLE_EVIDENCE)
        svc = ElementAssessmentService(
            aurora_cm=db, neptune_cm=mock_neptune, bedrock_client=bedrock,
        )

        score = svc.compute_readiness_score("case-1", "stat-1")

        # 2 covered out of 3 → round(2/3 * 100) = 67
        assert score.score == 67
        assert score.covered_elements == 2
        assert score.total_elements == 3
        assert len(score.missing_elements) == 1

    def test_no_elements_yields_0(self, mock_neptune):
        """0 elements → score 0."""
        db = _make_mock_db(elements=[], evidence=SAMPLE_EVIDENCE)
        svc = ElementAssessmentService(
            aurora_cm=db, neptune_cm=mock_neptune, bedrock_client=None,
        )

        score = svc.compute_readiness_score("case-1", "stat-1")

        assert score.score == 0
        assert score.total_elements == 0


# ---------------------------------------------------------------------------
# Tests: suggest_alternative_charges
# ---------------------------------------------------------------------------

class TestAlternativeCharges:
    """At most 5 alternatives, sorted by likelihood descending."""

    def test_returns_at_most_5(self, mock_db, mock_neptune):
        """Even if Bedrock returns 7, we cap at 5."""
        seven_alts = [
            {"statute_id": f"s-{i}", "citation": f"§ {i}", "title": f"Charge {i}",
             "estimated_conviction_likelihood": 90 - i * 5, "reasoning": f"Reason {i}"}
            for i in range(7)
        ]

        bedrock = MagicMock()
        # First calls are for rating pairs (all red to trigger alternatives)
        rating_resp = _bedrock_response({
            "rating": "red", "confidence": 10,
            "reasoning": "No support", "legal_justification": "Insufficient",
        })
        alt_resp = _bedrock_response(seven_alts)

        call_count = {"n": 0}

        def _invoke(**kwargs):
            call_count["n"] += 1
            body = json.loads(kwargs.get("body", "{}"))
            prompt = body.get("messages", [{}])[0].get("content", "")
            if "alternative" in prompt.lower() or "suggest" in prompt.lower():
                return alt_resp
            return rating_resp

        bedrock.invoke_model.side_effect = _invoke

        svc = ElementAssessmentService(
            aurora_cm=mock_db, neptune_cm=mock_neptune, bedrock_client=bedrock,
        )

        alts = svc.suggest_alternative_charges("case-1", "stat-1")

        assert len(alts) <= 5

    def test_sorted_by_likelihood_descending(self, mock_db, mock_neptune):
        """Alternatives must be sorted by estimated_conviction_likelihood desc."""
        alts_data = [
            {"statute_id": "s-1", "citation": "§ 1", "title": "C1",
             "estimated_conviction_likelihood": 60, "reasoning": "R1"},
            {"statute_id": "s-2", "citation": "§ 2", "title": "C2",
             "estimated_conviction_likelihood": 90, "reasoning": "R2"},
            {"statute_id": "s-3", "citation": "§ 3", "title": "C3",
             "estimated_conviction_likelihood": 75, "reasoning": "R3"},
        ]

        bedrock = MagicMock()
        rating_resp = _bedrock_response({
            "rating": "red", "confidence": 10,
            "reasoning": "No support", "legal_justification": "Insufficient",
        })
        alt_resp = _bedrock_response(alts_data)

        def _invoke(**kwargs):
            body = json.loads(kwargs.get("body", "{}"))
            prompt = body.get("messages", [{}])[0].get("content", "")
            if "alternative" in prompt.lower() or "suggest" in prompt.lower():
                return alt_resp
            return rating_resp

        bedrock.invoke_model.side_effect = _invoke

        svc = ElementAssessmentService(
            aurora_cm=mock_db, neptune_cm=mock_neptune, bedrock_client=bedrock,
        )

        alts = svc.suggest_alternative_charges("case-1", "stat-1")

        likelihoods = [a.estimated_conviction_likelihood for a in alts]
        assert likelihoods == sorted(likelihoods, reverse=True)

    def test_no_red_elements_returns_empty(self, mock_db, mock_neptune):
        """If no elements are red, no alternatives needed."""
        bedrock = MagicMock()
        bedrock.invoke_model.return_value = _bedrock_response({
            "rating": "green", "confidence": 90,
            "reasoning": "Strong", "legal_justification": "Solid",
        })

        svc = ElementAssessmentService(
            aurora_cm=mock_db, neptune_cm=mock_neptune, bedrock_client=bedrock,
        )

        alts = svc.suggest_alternative_charges("case-1", "stat-1")

        assert alts == []


# ---------------------------------------------------------------------------
# Tests: recommend_statutes
# ---------------------------------------------------------------------------

class TestRecommendStatutes:
    """Non-empty list sorted by match_strength descending."""

    def test_returns_sorted_by_match_strength(self, mock_db, mock_neptune):
        recs = [
            {"statute_id": "s-1", "citation": "§ 1591", "title": "Sex Trafficking",
             "match_strength": 85, "justification": "Strong evidence",
             "confidence": "high", "rejected_alternatives": [{"citation": "§ 1341", "reason_rejected": "No mail fraud"}]},
            {"statute_id": "s-2", "citation": "§ 1343", "title": "Wire Fraud",
             "match_strength": 60, "justification": "Some evidence",
             "confidence": "medium", "rejected_alternatives": []},
        ]

        bedrock = MagicMock()
        bedrock.invoke_model.return_value = _bedrock_response(recs)

        svc = ElementAssessmentService(
            aurora_cm=mock_db, neptune_cm=mock_neptune, bedrock_client=bedrock,
        )

        results = svc.recommend_statutes("case-1")

        assert len(results) >= 1
        strengths = [r.match_strength for r in results]
        assert strengths == sorted(strengths, reverse=True)

    def test_each_has_justification_and_confidence(self, mock_db, mock_neptune):
        recs = [
            {"statute_id": "s-1", "citation": "§ 1591", "title": "Sex Trafficking",
             "match_strength": 85, "justification": "Strong evidence of trafficking",
             "confidence": "high", "rejected_alternatives": [{"citation": "§ 1341", "reason_rejected": "No mail"}]},
        ]

        bedrock = MagicMock()
        bedrock.invoke_model.return_value = _bedrock_response(recs)

        svc = ElementAssessmentService(
            aurora_cm=mock_db, neptune_cm=mock_neptune, bedrock_client=bedrock,
        )

        results = svc.recommend_statutes("case-1")

        for r in results:
            assert r.justification
            assert r.confidence in (ConfidenceLevel.HIGH, ConfidenceLevel.MEDIUM, ConfidenceLevel.LOW)

    def test_no_evidence_returns_empty(self, mock_neptune):
        db = _make_mock_db(elements=[], evidence=[])
        svc = ElementAssessmentService(
            aurora_cm=db, neptune_cm=mock_neptune, bedrock_client=MagicMock(),
        )

        results = svc.recommend_statutes("case-1")

        assert results == []


# ---------------------------------------------------------------------------
# Tests: Senior Legal Analyst Persona in Bedrock calls
# ---------------------------------------------------------------------------

class TestSeniorLegalAnalystPersona:
    """Verify the AUSA system prompt is included in all Bedrock calls."""

    def test_persona_in_assess_single(self, mock_db, mock_neptune):
        bedrock = MagicMock()
        bedrock.invoke_model.return_value = _bedrock_response({
            "rating": "green", "confidence": 80,
            "reasoning": "Strong", "legal_justification": "Solid",
        })

        svc = ElementAssessmentService(
            aurora_cm=mock_db, neptune_cm=mock_neptune, bedrock_client=bedrock,
        )

        svc.assess_single("case-1", "elem-1", "doc-1")

        # Check the body sent to Bedrock includes the system prompt
        call_args = bedrock.invoke_model.call_args
        body = json.loads(call_args[1]["body"] if "body" in call_args[1] else call_args[0][0])
        assert body["system"] == ElementAssessmentService.SENIOR_LEGAL_ANALYST_PERSONA

    def test_persona_in_recommend_statutes(self, mock_db, mock_neptune):
        recs = [
            {"statute_id": "s-1", "citation": "§ 1591", "title": "T",
             "match_strength": 80, "justification": "J",
             "confidence": "high", "rejected_alternatives": []},
        ]
        bedrock = MagicMock()
        bedrock.invoke_model.return_value = _bedrock_response(recs)

        svc = ElementAssessmentService(
            aurora_cm=mock_db, neptune_cm=mock_neptune, bedrock_client=bedrock,
        )

        svc.recommend_statutes("case-1")

        call_args = bedrock.invoke_model.call_args
        body = json.loads(call_args[1]["body"] if "body" in call_args[1] else call_args[0][0])
        assert body["system"] == ElementAssessmentService.SENIOR_LEGAL_ANALYST_PERSONA

    def test_persona_constant_matches_design(self):
        """The persona constant should mention AUSA and legal terminology."""
        persona = ElementAssessmentService.SENIOR_LEGAL_ANALYST_PERSONA
        assert "AUSA" in persona
        assert "legal terminology" in persona.lower() or "legal" in persona.lower()
        assert "sentencing guidelines" in persona.lower() or "USSG" in persona


# ---------------------------------------------------------------------------
# Tests: Decision workflow integration
# ---------------------------------------------------------------------------

class TestDecisionWorkflowIntegration:
    """Ratings create AI_Proposed decisions via DecisionWorkflowService."""

    def test_assess_single_creates_ai_proposed_decision(
        self, mock_db, mock_neptune, mock_decision_svc
    ):
        bedrock = MagicMock()
        bedrock.invoke_model.return_value = _bedrock_response({
            "rating": "green", "confidence": 85,
            "reasoning": "Strong evidence", "legal_justification": "Direct proof",
        })

        svc = ElementAssessmentService(
            aurora_cm=mock_db,
            neptune_cm=mock_neptune,
            bedrock_client=bedrock,
            decision_workflow_svc=mock_decision_svc,
        )

        rating = svc.assess_single("case-1", "elem-1", "doc-1")

        mock_decision_svc.create_decision.assert_called_once()
        call_kwargs = mock_decision_svc.create_decision.call_args
        assert call_kwargs[1]["decision_type"] == "element_rating"
        assert call_kwargs[1]["source_service"] == "element_assessment"
        assert rating.decision_id == "decision-001"

    def test_rating_starts_as_ai_proposed(self, mock_db, mock_neptune):
        bedrock = MagicMock()
        bedrock.invoke_model.return_value = _bedrock_response({
            "rating": "green", "confidence": 85,
            "reasoning": "Strong", "legal_justification": "Solid",
        })

        svc = ElementAssessmentService(
            aurora_cm=mock_db, neptune_cm=mock_neptune, bedrock_client=bedrock,
        )

        rating = svc.assess_single("case-1", "elem-1", "doc-1")

        assert rating.decision_state == DecisionState.AI_PROPOSED


# ---------------------------------------------------------------------------
# Tests: draft_charging_recommendation
# ---------------------------------------------------------------------------

class TestChargingRecommendation:
    """Charging recommendation requires readiness >= 70%."""

    def test_below_threshold_returns_insufficient(self, mock_neptune):
        """Readiness < 70% → insufficient evidence message."""

        def _invoke(**kwargs):
            body = json.loads(kwargs.get("body", "{}"))
            prompt = body.get("messages", [{}])[0].get("content", "")
            # All rating calls return red
            return _bedrock_response({
                "rating": "red", "confidence": 10,
                "reasoning": "No support", "legal_justification": "Insufficient",
            })

        bedrock = MagicMock()
        bedrock.invoke_model.side_effect = _invoke

        db = _make_mock_db(elements=SAMPLE_ELEMENTS, evidence=SAMPLE_EVIDENCE)
        svc = ElementAssessmentService(
            aurora_cm=db, neptune_cm=mock_neptune, bedrock_client=bedrock,
        )

        rec = svc.draft_charging_recommendation("case-1", "stat-1")

        assert "insufficient" in rec.recommendation_text.lower()
        assert rec.confidence == ConfidenceLevel.LOW

    def test_above_threshold_returns_recommendation(self, mock_neptune, mock_decision_svc):
        """Readiness >= 70% → full recommendation with legal reasoning."""
        call_idx = {"n": 0}

        def _invoke(**kwargs):
            call_idx["n"] += 1
            body = json.loads(kwargs.get("body", "{}"))
            prompt = body.get("messages", [{}])[0].get("content", "")

            if "draft" in prompt.lower() or "charging recommendation" in prompt.lower():
                return _bedrock_response({
                    "recommendation_text": "Recommend charging under § 1591",
                    "legal_reasoning": "Evidence strongly supports all elements",
                    "sentencing_guideline_refs": ["USSG §2B1.1"],
                    "confidence": "high",
                })
            # All elements green for readiness
            return _bedrock_response({
                "rating": "green", "confidence": 90,
                "reasoning": "Strong", "legal_justification": "Solid",
            })

        bedrock = MagicMock()
        bedrock.invoke_model.side_effect = _invoke

        db = _make_mock_db(elements=SAMPLE_ELEMENTS, evidence=SAMPLE_EVIDENCE)
        svc = ElementAssessmentService(
            aurora_cm=db,
            neptune_cm=mock_neptune,
            bedrock_client=bedrock,
            decision_workflow_svc=mock_decision_svc,
        )

        rec = svc.draft_charging_recommendation("case-1", "stat-1")

        assert rec.recommendation_text
        assert rec.legal_reasoning
        assert len(rec.sentencing_guideline_refs) >= 1
