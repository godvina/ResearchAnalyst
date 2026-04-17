"""Unit tests for AIFirstAnalysisEngine.

Covers:
- auto_analyze returns CaseAnalysisResult with statute_recommendations,
  element_mappings, weaknesses
- auto_analyze creates AI_Proposed decisions for statute recommendations
- on_evidence_added creates AI_Proposed decisions for new mappings
- Bedrock fallback returns partial results with warnings
- Charging recommendation triggered when readiness >= 70%
"""

from unittest.mock import MagicMock, call, patch

import pytest

from src.models.prosecutor import (
    CaseAnalysisResult,
    CaseWeakness,
    ChargingRecommendation,
    ConfidenceLevel,
    DecisionState,
    ElementMapping,
    ElementRating,
    EvidenceMatrix,
    ReadinessScore,
    StatuteRecommendation,
    StatutoryElement,
    SupportRating,
    WeaknessSeverity,
    WeaknessType,
)
from src.services.ai_first_analysis_engine import AIFirstAnalysisEngine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_ELEMENTS = [
    StatutoryElement(
        element_id="elem-1", statute_id="stat-1",
        display_name="Interstate Commerce", description="Prove interstate nexus",
        element_order=1,
    ),
    StatutoryElement(
        element_id="elem-2", statute_id="stat-1",
        display_name="Force or Coercion", description="Prove use of force",
        element_order=2,
    ),
]

SAMPLE_EVIDENCE = [
    {"evidence_id": "doc-1", "title": "financial_records.pdf", "type": "document"},
    {"evidence_id": "doc-2", "title": "witness_statement.pdf", "type": "document"},
]

SAMPLE_RATINGS = [
    ElementRating(
        element_id="elem-1", evidence_id="doc-1",
        rating=SupportRating.GREEN, confidence=85,
        reasoning="Strong evidence", legal_justification="Direct proof",
        decision_id="dec-rating-1", decision_state=DecisionState.AI_PROPOSED,
    ),
    ElementRating(
        element_id="elem-2", evidence_id="doc-2",
        rating=SupportRating.YELLOW, confidence=55,
        reasoning="Partial support", legal_justification="Circumstantial",
        decision_id="dec-rating-2", decision_state=DecisionState.AI_PROPOSED,
    ),
]


def _make_statute_recommendation(
    statute_id="stat-1",
    citation="18 U.S.C. § 1591",
    title="Sex Trafficking",
    match_strength=85,
):
    return StatuteRecommendation(
        statute_id=statute_id,
        citation=citation,
        title=title,
        match_strength=match_strength,
        justification="Strong evidence of trafficking activity",
        confidence=ConfidenceLevel.HIGH,
        rejected_alternatives=[{"citation": "§ 1341", "reason_rejected": "No mail fraud"}],
    )


def _make_evidence_matrix(readiness_score=80):
    return EvidenceMatrix(
        case_id="case-001",
        statute_id="stat-1",
        elements=SAMPLE_ELEMENTS,
        evidence_items=SAMPLE_EVIDENCE,
        ratings=SAMPLE_RATINGS,
        readiness_score=readiness_score,
    )


def _make_charging_recommendation():
    return ChargingRecommendation(
        case_id="case-001",
        statute_id="stat-1",
        recommendation_text="Recommend charging under § 1591",
        legal_reasoning="Evidence strongly supports all elements",
        sentencing_guideline_refs=["USSG §2B1.1"],
        confidence=ConfidenceLevel.HIGH,
        decision_id="dec-charging-1",
    )


def _make_weakness():
    return CaseWeakness(
        weakness_id="weak-1",
        case_id="case-001",
        weakness_type=WeaknessType.MISSING_CORROBORATION,
        severity=WeaknessSeverity.WARNING,
        description="Element 'Force' supported by only one source",
        legal_reasoning="Single-source elements are vulnerable",
        affected_elements=["elem-2"],
        affected_evidence=["doc-2"],
    )


def _make_decision_mock():
    """Build a mock DecisionWorkflowService."""
    svc = MagicMock()
    call_count = {"n": 0}

    def _create_decision(**kwargs):
        call_count["n"] += 1
        decision = MagicMock()
        decision.decision_id = f"dec-{call_count['n']:03d}"
        return decision

    svc.create_decision.side_effect = _create_decision
    return svc


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_element_svc():
    svc = MagicMock()
    svc.recommend_statutes.return_value = [_make_statute_recommendation()]
    svc.assess_elements.return_value = _make_evidence_matrix(readiness_score=80)
    svc.draft_charging_recommendation.return_value = _make_charging_recommendation()
    svc.auto_categorize_evidence.return_value = [
        ElementMapping(
            evidence_id="doc-new",
            element_id="elem-1",
            justification="Maps to interstate commerce element",
            confidence=ConfidenceLevel.HIGH,
            decision_id=None,
        ),
    ]
    return svc


@pytest.fixture()
def mock_weakness_svc():
    svc = MagicMock()
    svc.analyze_weaknesses.return_value = [_make_weakness()]
    return svc


@pytest.fixture()
def mock_decision_svc():
    return _make_decision_mock()


@pytest.fixture()
def mock_bedrock():
    return MagicMock()


@pytest.fixture()
def engine(mock_element_svc, mock_weakness_svc, mock_decision_svc, mock_bedrock):
    return AIFirstAnalysisEngine(
        element_assessment_svc=mock_element_svc,
        case_weakness_svc=mock_weakness_svc,
        decision_workflow_svc=mock_decision_svc,
        bedrock_client=mock_bedrock,
    )


# ---------------------------------------------------------------------------
# Tests: auto_analyze returns CaseAnalysisResult
# ---------------------------------------------------------------------------

class TestAutoAnalyzeResult:
    """auto_analyze returns CaseAnalysisResult with all expected fields."""

    def test_returns_case_analysis_result(self, engine):
        result = engine.auto_analyze("case-001")

        assert isinstance(result, CaseAnalysisResult)
        assert result.case_id == "case-001"

    def test_contains_statute_recommendations(self, engine):
        result = engine.auto_analyze("case-001")

        assert len(result.statute_recommendations) >= 1
        rec = result.statute_recommendations[0]
        assert rec.citation == "18 U.S.C. § 1591"
        assert rec.match_strength == 85

    def test_contains_element_mappings(self, engine):
        result = engine.auto_analyze("case-001")

        assert len(result.element_mappings) >= 1

    def test_contains_weaknesses(self, engine):
        result = engine.auto_analyze("case-001")

        assert len(result.weaknesses) >= 1
        assert result.weaknesses[0].weakness_type == WeaknessType.MISSING_CORROBORATION

    def test_no_warnings_when_bedrock_available(self, engine):
        result = engine.auto_analyze("case-001")

        assert result.warnings == []


# ---------------------------------------------------------------------------
# Tests: auto_analyze creates AI_Proposed decisions
# ---------------------------------------------------------------------------

class TestAutoAnalyzeDecisions:
    """auto_analyze creates AI_Proposed decisions for statute recommendations."""

    def test_creates_decision_for_each_statute_recommendation(
        self, mock_element_svc, mock_weakness_svc, mock_decision_svc, mock_bedrock
    ):
        mock_element_svc.recommend_statutes.return_value = [
            _make_statute_recommendation("stat-1", "§ 1591", "Sex Trafficking", 85),
            _make_statute_recommendation("stat-2", "§ 1343", "Wire Fraud", 70),
        ]
        mock_element_svc.assess_elements.return_value = _make_evidence_matrix(readiness_score=50)

        engine = AIFirstAnalysisEngine(
            element_assessment_svc=mock_element_svc,
            case_weakness_svc=mock_weakness_svc,
            decision_workflow_svc=mock_decision_svc,
            bedrock_client=mock_bedrock,
        )

        result = engine.auto_analyze("case-001")

        # At least 2 decisions for the 2 statute recommendations
        assert mock_decision_svc.create_decision.call_count >= 2
        # Check decision_type for statute recommendations
        statute_calls = [
            c for c in mock_decision_svc.create_decision.call_args_list
            if c[1].get("decision_type") == "statute_recommendation"
        ]
        assert len(statute_calls) == 2

    def test_decisions_created_list_populated(self, engine):
        result = engine.auto_analyze("case-001")

        assert len(result.decisions_created) >= 1
        # All decision IDs should be non-empty strings
        for did in result.decisions_created:
            assert did and isinstance(did, str)

    def test_decision_source_service_is_engine(
        self, mock_element_svc, mock_weakness_svc, mock_decision_svc, mock_bedrock
    ):
        engine = AIFirstAnalysisEngine(
            element_assessment_svc=mock_element_svc,
            case_weakness_svc=mock_weakness_svc,
            decision_workflow_svc=mock_decision_svc,
            bedrock_client=mock_bedrock,
        )

        engine.auto_analyze("case-001")

        for c in mock_decision_svc.create_decision.call_args_list:
            assert c[1]["source_service"] == "ai_first_analysis_engine"


# ---------------------------------------------------------------------------
# Tests: on_evidence_added creates AI_Proposed decisions
# ---------------------------------------------------------------------------

class TestOnEvidenceAdded:
    """on_evidence_added creates AI_Proposed decisions for new mappings."""

    def test_returns_element_mappings(self, engine, mock_element_svc):
        mappings = engine.on_evidence_added("case-001", "doc-new")

        assert len(mappings) >= 1
        assert mappings[0].evidence_id == "doc-new"
        assert mappings[0].element_id == "elem-1"

    def test_creates_decisions_for_mappings_without_decision_id(
        self, engine, mock_element_svc, mock_decision_svc
    ):
        # auto_categorize_evidence returns mappings without decision_id
        mock_element_svc.auto_categorize_evidence.return_value = [
            ElementMapping(
                evidence_id="doc-new",
                element_id="elem-1",
                justification="Maps to element",
                confidence=ConfidenceLevel.HIGH,
                decision_id=None,
            ),
        ]

        mappings = engine.on_evidence_added("case-001", "doc-new")

        # Decision should have been created for the mapping
        assert mappings[0].decision_id is not None
        assert mock_decision_svc.create_decision.called

    def test_preserves_existing_decision_ids(
        self, engine, mock_element_svc, mock_decision_svc
    ):
        mock_element_svc.auto_categorize_evidence.return_value = [
            ElementMapping(
                evidence_id="doc-new",
                element_id="elem-1",
                justification="Maps to element",
                confidence=ConfidenceLevel.HIGH,
                decision_id="existing-dec-id",
            ),
        ]

        mappings = engine.on_evidence_added("case-001", "doc-new")

        # Should NOT create a new decision since one already exists
        assert mappings[0].decision_id == "existing-dec-id"

    def test_returns_empty_when_bedrock_unavailable(
        self, mock_element_svc, mock_weakness_svc, mock_decision_svc
    ):
        engine = AIFirstAnalysisEngine(
            element_assessment_svc=mock_element_svc,
            case_weakness_svc=mock_weakness_svc,
            decision_workflow_svc=mock_decision_svc,
            bedrock_client=None,
        )

        mappings = engine.on_evidence_added("case-001", "doc-new")

        assert mappings == []


# ---------------------------------------------------------------------------
# Tests: Bedrock fallback returns partial results with warnings
# ---------------------------------------------------------------------------

class TestBedrockFallback:
    """When Bedrock is unavailable, return partial results with warnings."""

    def test_no_bedrock_returns_empty_recommendations(
        self, mock_element_svc, mock_weakness_svc, mock_decision_svc
    ):
        engine = AIFirstAnalysisEngine(
            element_assessment_svc=mock_element_svc,
            case_weakness_svc=mock_weakness_svc,
            decision_workflow_svc=mock_decision_svc,
            bedrock_client=None,
        )

        result = engine.auto_analyze("case-001")

        assert result.statute_recommendations == []
        assert result.element_mappings == []

    def test_no_bedrock_includes_warning(
        self, mock_element_svc, mock_weakness_svc, mock_decision_svc
    ):
        engine = AIFirstAnalysisEngine(
            element_assessment_svc=mock_element_svc,
            case_weakness_svc=mock_weakness_svc,
            decision_workflow_svc=mock_decision_svc,
            bedrock_client=None,
        )

        result = engine.auto_analyze("case-001")

        assert len(result.warnings) >= 1
        assert any("bedrock" in w.lower() or "unavailable" in w.lower() for w in result.warnings)

    def test_no_bedrock_still_runs_weakness_analysis(
        self, mock_element_svc, mock_weakness_svc, mock_decision_svc
    ):
        engine = AIFirstAnalysisEngine(
            element_assessment_svc=mock_element_svc,
            case_weakness_svc=mock_weakness_svc,
            decision_workflow_svc=mock_decision_svc,
            bedrock_client=None,
        )

        result = engine.auto_analyze("case-001")

        mock_weakness_svc.analyze_weaknesses.assert_called_once()
        assert len(result.weaknesses) >= 1

    def test_no_bedrock_skips_charging_recommendation(
        self, mock_element_svc, mock_weakness_svc, mock_decision_svc
    ):
        engine = AIFirstAnalysisEngine(
            element_assessment_svc=mock_element_svc,
            case_weakness_svc=mock_weakness_svc,
            decision_workflow_svc=mock_decision_svc,
            bedrock_client=None,
        )

        result = engine.auto_analyze("case-001")

        assert result.charging_recommendation is None
        mock_element_svc.draft_charging_recommendation.assert_not_called()


# ---------------------------------------------------------------------------
# Tests: Charging recommendation triggered when readiness >= 70%
# ---------------------------------------------------------------------------

class TestChargingRecommendationThreshold:
    """Charging recommendation is drafted when readiness >= 70%."""

    def test_readiness_above_70_triggers_charging_recommendation(
        self, mock_element_svc, mock_weakness_svc, mock_decision_svc, mock_bedrock
    ):
        mock_element_svc.assess_elements.return_value = _make_evidence_matrix(
            readiness_score=80
        )

        engine = AIFirstAnalysisEngine(
            element_assessment_svc=mock_element_svc,
            case_weakness_svc=mock_weakness_svc,
            decision_workflow_svc=mock_decision_svc,
            bedrock_client=mock_bedrock,
        )

        result = engine.auto_analyze("case-001")

        mock_element_svc.draft_charging_recommendation.assert_called_once()
        assert result.charging_recommendation is not None
        assert result.charging_recommendation.recommendation_text

    def test_readiness_exactly_70_triggers_charging_recommendation(
        self, mock_element_svc, mock_weakness_svc, mock_decision_svc, mock_bedrock
    ):
        mock_element_svc.assess_elements.return_value = _make_evidence_matrix(
            readiness_score=70
        )

        engine = AIFirstAnalysisEngine(
            element_assessment_svc=mock_element_svc,
            case_weakness_svc=mock_weakness_svc,
            decision_workflow_svc=mock_decision_svc,
            bedrock_client=mock_bedrock,
        )

        result = engine.auto_analyze("case-001")

        mock_element_svc.draft_charging_recommendation.assert_called_once()

    def test_readiness_below_70_skips_charging_recommendation(
        self, mock_element_svc, mock_weakness_svc, mock_decision_svc, mock_bedrock
    ):
        mock_element_svc.assess_elements.return_value = _make_evidence_matrix(
            readiness_score=50
        )

        engine = AIFirstAnalysisEngine(
            element_assessment_svc=mock_element_svc,
            case_weakness_svc=mock_weakness_svc,
            decision_workflow_svc=mock_decision_svc,
            bedrock_client=mock_bedrock,
        )

        result = engine.auto_analyze("case-001")

        mock_element_svc.draft_charging_recommendation.assert_not_called()
        assert result.charging_recommendation is None

    def test_charging_decision_id_added_to_decisions_created(
        self, mock_element_svc, mock_weakness_svc, mock_decision_svc, mock_bedrock
    ):
        mock_element_svc.assess_elements.return_value = _make_evidence_matrix(
            readiness_score=80
        )

        engine = AIFirstAnalysisEngine(
            element_assessment_svc=mock_element_svc,
            case_weakness_svc=mock_weakness_svc,
            decision_workflow_svc=mock_decision_svc,
            bedrock_client=mock_bedrock,
        )

        result = engine.auto_analyze("case-001")

        # The charging recommendation's decision_id should be in decisions_created
        assert result.charging_recommendation.decision_id in result.decisions_created
