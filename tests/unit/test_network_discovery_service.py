"""Unit tests for NetworkDiscoveryService.

Covers:
- Involvement score formula (weighted composite)
- Risk level classification rules
- Persons of interest sorted by involvement score descending
- analyze_network creates AI_Proposed decisions
- Large subgraph (>50K) returns processing status
- Filtering by risk_level and min_score works correctly
"""

from contextlib import contextmanager
from io import BytesIO
from unittest.mock import MagicMock, patch
import json

import pytest

from src.models.network import (
    AnalysisStatus,
    CentralityScores,
    CoConspiratorProfile,
    InvolvementScore,
    NetworkAnalysisResult,
    RiskLevel,
)
from src.models.prosecutor import (
    AIDecision,
    ConfidenceLevel,
    DecisionState,
)
from src.services.network_discovery_service import (
    LARGE_SUBGRAPH_THRESHOLD,
    NetworkDiscoveryService,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_mock_cursor():
    cursor = MagicMock()
    cursor.fetchone.return_value = None
    cursor.fetchall.return_value = []
    return cursor


def _make_mock_db(cursor=None):
    db = MagicMock()
    cur = cursor or _make_mock_cursor()

    @contextmanager
    def _cursor_ctx():
        yield cur

    db.cursor = _cursor_ctx
    return db, cur


def _make_bedrock_response(text: str = "Legal reasoning text"):
    """Create a mock Bedrock response."""
    body_bytes = json.dumps({
        "content": [{"text": text}],
    }).encode()
    response = {"body": BytesIO(body_bytes)}
    return response


def _make_decision(
    decision_id="dec-001",
    case_id="case-001",
    decision_type="person_of_interest",
    state=DecisionState.AI_PROPOSED,
):
    return AIDecision(
        decision_id=decision_id,
        case_id=case_id,
        decision_type=decision_type,
        state=state,
        recommendation_text="Test recommendation",
        legal_reasoning="Test reasoning",
        confidence=ConfidenceLevel.HIGH,
        source_service="network_discovery",
        created_at="2024-01-01T00:00:00+00:00",
        updated_at="2024-01-01T00:00:00+00:00",
    )


@pytest.fixture()
def mock_deps():
    """Create all mock dependencies for NetworkDiscoveryService."""
    db, cursor = _make_mock_db()
    bedrock = MagicMock()
    bedrock.invoke_model.return_value = _make_bedrock_response()

    decision_svc = MagicMock()
    decision_svc.create_decision.return_value = _make_decision()

    cross_case_svc = MagicMock()
    pattern_svc = MagicMock()

    return {
        "neptune_endpoint": "localhost",
        "neptune_port": "8182",
        "aurora_cm": db,
        "bedrock_client": bedrock,
        "opensearch_endpoint": "localhost:9200",
        "decision_workflow_svc": decision_svc,
        "cross_case_svc": cross_case_svc,
        "pattern_discovery_svc": pattern_svc,
        "cursor": cursor,
    }


@pytest.fixture()
def service(mock_deps):
    return NetworkDiscoveryService(
        neptune_endpoint=mock_deps["neptune_endpoint"],
        neptune_port=mock_deps["neptune_port"],
        aurora_cm=mock_deps["aurora_cm"],
        bedrock_client=mock_deps["bedrock_client"],
        opensearch_endpoint=mock_deps["opensearch_endpoint"],
        decision_workflow_svc=mock_deps["decision_workflow_svc"],
        cross_case_svc=mock_deps["cross_case_svc"],
        pattern_discovery_svc=mock_deps["pattern_discovery_svc"],
    )


@pytest.fixture(autouse=True)
def _enable_neptune():
    """Enable Neptune feature flag for all tests in this module."""
    import src.services.network_discovery_service as nds_mod
    original = nds_mod._NEPTUNE_ENABLED
    nds_mod._NEPTUNE_ENABLED = True
    yield
    nds_mod._NEPTUNE_ENABLED = original


# ---------------------------------------------------------------------------
# Tests: Constructor and Constants (Task 3.1)
# ---------------------------------------------------------------------------

class TestConstructorAndConstants:
    def test_constructor_stores_all_dependencies(self, service, mock_deps):
        assert service._neptune_endpoint == "localhost"
        assert service._neptune_port == "8182"
        assert service._opensearch_endpoint == "localhost:9200"
        assert service._aurora is mock_deps["aurora_cm"]
        assert service._bedrock is mock_deps["bedrock_client"]
        assert service._decision_workflow_svc is mock_deps["decision_workflow_svc"]
        assert service._cross_case_svc is mock_deps["cross_case_svc"]
        assert service._pattern_discovery_svc is mock_deps["pattern_discovery_svc"]

    def test_senior_legal_analyst_persona_defined(self, service):
        assert "senior federal prosecutor" in service.SENIOR_LEGAL_ANALYST_PERSONA
        assert "AUSA" in service.SENIOR_LEGAL_ANALYST_PERSONA
        assert "USSG" in service.SENIOR_LEGAL_ANALYST_PERSONA

    def test_involvement_weights_sum_to_one(self, service):
        total = sum(service.INVOLVEMENT_WEIGHTS.values())
        assert abs(total - 1.0) < 1e-9

    def test_involvement_weights_correct_values(self, service):
        w = service.INVOLVEMENT_WEIGHTS
        assert w["connections"] == 0.25
        assert w["co_occurrence"] == 0.25
        assert w["financial"] == 0.20
        assert w["communication"] == 0.15
        assert w["geographic"] == 0.15


# ---------------------------------------------------------------------------
# Tests: Involvement Score Formula (Task 3.4)
# ---------------------------------------------------------------------------

class TestInvolvementScore:
    def test_weighted_formula_basic(self, service):
        """Verify the weighted composite formula produces correct total."""
        # Mock all scoring methods to return known values
        with patch.object(service, '_score_connections', return_value=80), \
             patch.object(service, '_score_co_occurrence', return_value=60), \
             patch.object(service, '_score_financial', return_value=40), \
             patch.object(service, '_score_communication', return_value=20), \
             patch.object(service, '_score_geographic', return_value=10):

            score = service._compute_involvement_score("case-1", "John", "Subject")

            expected = round(80 * 0.25 + 60 * 0.25 + 40 * 0.20 + 20 * 0.15 + 10 * 0.15)
            assert score.total == expected
            assert score.connections == 80
            assert score.co_occurrence == 60
            assert score.financial == 40
            assert score.communication == 20
            assert score.geographic == 10

    def test_weighted_formula_all_zeros(self, service):
        with patch.object(service, '_score_connections', return_value=0), \
             patch.object(service, '_score_co_occurrence', return_value=0), \
             patch.object(service, '_score_financial', return_value=0), \
             patch.object(service, '_score_communication', return_value=0), \
             patch.object(service, '_score_geographic', return_value=0):

            score = service._compute_involvement_score("case-1", "John", "Subject")
            assert score.total == 0

    def test_weighted_formula_all_max(self, service):
        with patch.object(service, '_score_connections', return_value=100), \
             patch.object(service, '_score_co_occurrence', return_value=100), \
             patch.object(service, '_score_financial', return_value=100), \
             patch.object(service, '_score_communication', return_value=100), \
             patch.object(service, '_score_geographic', return_value=100):

            score = service._compute_involvement_score("case-1", "John", "Subject")
            assert score.total == 100

    def test_total_clamped_to_0_100(self, service):
        """Total should never exceed 100 or go below 0."""
        with patch.object(service, '_score_connections', return_value=100), \
             patch.object(service, '_score_co_occurrence', return_value=100), \
             patch.object(service, '_score_financial', return_value=100), \
             patch.object(service, '_score_communication', return_value=100), \
             patch.object(service, '_score_geographic', return_value=100):

            score = service._compute_involvement_score("case-1", "John", "Subject")
            assert 0 <= score.total <= 100


# ---------------------------------------------------------------------------
# Tests: Risk Level Classification (Task 3.4)
# ---------------------------------------------------------------------------

class TestRiskClassification:
    def _make_profile(self, doc_type_count: int, connection_strength: int):
        return CoConspiratorProfile(
            profile_id="p-1",
            case_id="case-1",
            entity_name="Test Person",
            entity_type="PERSON",
            involvement_score=InvolvementScore(
                total=50, connections=50, co_occurrence=50,
                financial=50, communication=50, geographic=50,
            ),
            connection_strength=connection_strength,
            risk_level=RiskLevel.LOW,
            document_type_count=doc_type_count,
        )

    def test_high_risk_3_doc_types_and_strength_above_70(self, service):
        profile = self._make_profile(doc_type_count=3, connection_strength=80)
        assert service._classify_risk_level(profile) == RiskLevel.HIGH

    def test_high_risk_5_doc_types_and_strength_90(self, service):
        profile = self._make_profile(doc_type_count=5, connection_strength=90)
        assert service._classify_risk_level(profile) == RiskLevel.HIGH

    def test_medium_risk_2_doc_types(self, service):
        profile = self._make_profile(doc_type_count=2, connection_strength=30)
        assert service._classify_risk_level(profile) == RiskLevel.MEDIUM

    def test_medium_risk_strength_between_40_and_70(self, service):
        profile = self._make_profile(doc_type_count=1, connection_strength=50)
        assert service._classify_risk_level(profile) == RiskLevel.MEDIUM

    def test_medium_risk_strength_exactly_40(self, service):
        profile = self._make_profile(doc_type_count=1, connection_strength=40)
        assert service._classify_risk_level(profile) == RiskLevel.MEDIUM

    def test_medium_risk_strength_exactly_70(self, service):
        profile = self._make_profile(doc_type_count=1, connection_strength=70)
        assert service._classify_risk_level(profile) == RiskLevel.MEDIUM

    def test_low_risk_1_doc_type_and_strength_below_40(self, service):
        profile = self._make_profile(doc_type_count=1, connection_strength=20)
        assert service._classify_risk_level(profile) == RiskLevel.LOW

    def test_low_risk_0_doc_types_and_strength_0(self, service):
        profile = self._make_profile(doc_type_count=0, connection_strength=10)
        assert service._classify_risk_level(profile) == RiskLevel.LOW

    def test_not_high_when_3_doc_types_but_strength_70(self, service):
        """3 doc types but connection_strength == 70 (not > 70) → medium."""
        profile = self._make_profile(doc_type_count=3, connection_strength=70)
        assert service._classify_risk_level(profile) == RiskLevel.MEDIUM

    def test_not_low_when_1_doc_type_but_strength_40(self, service):
        """1 doc type but connection_strength == 40 (not < 40) → medium."""
        profile = self._make_profile(doc_type_count=1, connection_strength=40)
        assert service._classify_risk_level(profile) == RiskLevel.MEDIUM


# ---------------------------------------------------------------------------
# Tests: Anomaly Detection (Task 3.2)
# ---------------------------------------------------------------------------

class TestAnomalyDetection:
    def test_flags_entities_above_2_std_dev(self, service):
        # Degrees: [5, 5, 5, 5, 5, 5, 5, 5, 5, 100]
        # mean=14.5, stdev~28.4, threshold~71.3 → 100 > 71.3
        centrality = {
            f"Normal{i}": CentralityScores(betweenness=0.1, degree=5, pagerank=0.1)
            for i in range(9)
        }
        centrality["Outlier"] = CentralityScores(betweenness=0.5, degree=100, pagerank=0.5)
        anomalies = service._run_anomaly_detection("case-1", centrality)
        assert "Outlier" in anomalies

    def test_no_anomalies_when_uniform(self, service):
        centrality = {
            "A": CentralityScores(betweenness=0.1, degree=5, pagerank=0.1),
            "B": CentralityScores(betweenness=0.1, degree=5, pagerank=0.1),
            "C": CentralityScores(betweenness=0.1, degree=5, pagerank=0.1),
        }
        anomalies = service._run_anomaly_detection("case-1", centrality)
        assert anomalies == []

    def test_empty_centrality_returns_empty(self, service):
        assert service._run_anomaly_detection("case-1", {}) == []

    def test_single_entity_returns_empty(self, service):
        centrality = {
            "A": CentralityScores(betweenness=0.1, degree=5, pagerank=0.1),
        }
        assert service._run_anomaly_detection("case-1", centrality) == []


# ---------------------------------------------------------------------------
# Tests: analyze_network Orchestration (Task 3.7)
# ---------------------------------------------------------------------------

class TestAnalyzeNetwork:
    def test_large_subgraph_returns_processing_status(self, service, mock_deps):
        """Subgraph >50K nodes should return processing status."""
        with patch.object(service, '_gremlin_query') as mock_gremlin:
            mock_gremlin.return_value = [LARGE_SUBGRAPH_THRESHOLD + 1]

            result = service.analyze_network("case-large")

            assert result.analysis_status == AnalysisStatus.PROCESSING
            assert result.total_entities_analyzed == LARGE_SUBGRAPH_THRESHOLD + 1

    def test_small_subgraph_returns_completed(self, service, mock_deps):
        """Subgraph <=50K nodes should complete synchronously."""
        with patch.object(service, '_gremlin_query', return_value=[10]), \
             patch.object(service, '_identify_primary_subject', return_value="Subject"), \
             patch.object(service, '_run_community_detection', return_value=[]), \
             patch.object(service, '_run_centrality_scoring', return_value={}), \
             patch.object(service, '_run_anomaly_detection', return_value=[]), \
             patch.object(service, '_select_candidates', return_value=[]), \
             patch.object(service, '_cache_analysis'):

            result = service.analyze_network("case-small")

            assert result.analysis_status == AnalysisStatus.COMPLETED
            assert result.case_id == "case-small"

    def test_creates_ai_proposed_decisions_for_each_poi(self, service, mock_deps):
        """Each person of interest should get an AI_Proposed decision."""
        mock_score = InvolvementScore(
            total=50, connections=50, co_occurrence=50,
            financial=50, communication=50, geographic=50,
        )

        with patch.object(service, '_gremlin_query', return_value=[5]), \
             patch.object(service, '_identify_primary_subject', return_value="Subject"), \
             patch.object(service, '_run_community_detection', return_value=[]), \
             patch.object(service, '_run_centrality_scoring', return_value={
                 "Alice": CentralityScores(betweenness=0.5, degree=10, pagerank=0.3),
                 "Bob": CentralityScores(betweenness=0.3, degree=8, pagerank=0.2),
             }), \
             patch.object(service, '_run_anomaly_detection', return_value=[]), \
             patch.object(service, '_select_candidates', return_value=["Alice", "Bob"]), \
             patch.object(service, '_compute_involvement_score', return_value=mock_score), \
             patch.object(service, '_get_evidence_for_entity', return_value=[]), \
             patch.object(service, '_get_relationships', return_value=[]), \
             patch.object(service, '_generate_legal_reasoning', return_value="Legal text"), \
             patch.object(service, '_cache_analysis'):

            result = service.analyze_network("case-1")

            # Decision service should be called once per POI
            assert mock_deps["decision_workflow_svc"].create_decision.call_count == 2
            for person in result.persons_of_interest:
                assert person.decision_id is not None
                assert person.decision_state == "ai_proposed"

    def test_persons_sorted_by_involvement_score_descending(self, service, mock_deps):
        """Persons of interest should be sorted by involvement score descending."""
        call_count = [0]
        scores = [30, 80, 50]

        def mock_score(*args, **kwargs):
            idx = call_count[0]
            call_count[0] += 1
            s = scores[idx]
            return InvolvementScore(
                total=s, connections=s, co_occurrence=s,
                financial=s, communication=s, geographic=s,
            )

        with patch.object(service, '_gremlin_query', return_value=[5]), \
             patch.object(service, '_identify_primary_subject', return_value="Subject"), \
             patch.object(service, '_run_community_detection', return_value=[]), \
             patch.object(service, '_run_centrality_scoring', return_value={
                 "A": CentralityScores(betweenness=0.1, degree=3, pagerank=0.1),
                 "B": CentralityScores(betweenness=0.5, degree=10, pagerank=0.3),
                 "C": CentralityScores(betweenness=0.3, degree=5, pagerank=0.2),
             }), \
             patch.object(service, '_run_anomaly_detection', return_value=[]), \
             patch.object(service, '_select_candidates', return_value=["A", "B", "C"]), \
             patch.object(service, '_compute_involvement_score', side_effect=mock_score), \
             patch.object(service, '_get_evidence_for_entity', return_value=[]), \
             patch.object(service, '_get_relationships', return_value=[]), \
             patch.object(service, '_generate_legal_reasoning', return_value="Legal text"), \
             patch.object(service, '_cache_analysis'):

            result = service.analyze_network("case-1")

            totals = [p.involvement_score.total for p in result.persons_of_interest]
            assert totals == sorted(totals, reverse=True)


# ---------------------------------------------------------------------------
# Tests: Filtering (Task 3.9)
# ---------------------------------------------------------------------------

class TestFiltering:
    def _make_analysis_with_persons(self):
        """Create a mock analysis result with varied profiles."""
        persons = [
            CoConspiratorProfile(
                profile_id="p-1", case_id="case-1",
                entity_name="High Risk Person", entity_type="PERSON",
                involvement_score=InvolvementScore(
                    total=90, connections=90, co_occurrence=90,
                    financial=90, communication=90, geographic=90,
                ),
                connection_strength=85, risk_level=RiskLevel.HIGH,
                document_type_count=4,
            ),
            CoConspiratorProfile(
                profile_id="p-2", case_id="case-1",
                entity_name="Medium Risk Person", entity_type="PERSON",
                involvement_score=InvolvementScore(
                    total=50, connections=50, co_occurrence=50,
                    financial=50, communication=50, geographic=50,
                ),
                connection_strength=55, risk_level=RiskLevel.MEDIUM,
                document_type_count=2,
            ),
            CoConspiratorProfile(
                profile_id="p-3", case_id="case-1",
                entity_name="Low Risk Person", entity_type="PERSON",
                involvement_score=InvolvementScore(
                    total=20, connections=20, co_occurrence=20,
                    financial=20, communication=20, geographic=20,
                ),
                connection_strength=15, risk_level=RiskLevel.LOW,
                document_type_count=1,
            ),
        ]
        return NetworkAnalysisResult(
            analysis_id="a-1", case_id="case-1",
            analysis_status=AnalysisStatus.COMPLETED,
            persons_of_interest=persons,
        )

    def test_filter_by_risk_level_high(self, service):
        analysis = self._make_analysis_with_persons()
        with patch.object(service, 'get_analysis', return_value=analysis):
            result = service.get_persons_of_interest("case-1", risk_level=RiskLevel.HIGH)
            assert len(result) == 1
            assert result[0].risk_level == RiskLevel.HIGH

    def test_filter_by_risk_level_medium(self, service):
        analysis = self._make_analysis_with_persons()
        with patch.object(service, 'get_analysis', return_value=analysis):
            result = service.get_persons_of_interest("case-1", risk_level=RiskLevel.MEDIUM)
            assert len(result) == 1
            assert result[0].risk_level == RiskLevel.MEDIUM

    def test_filter_by_risk_level_low(self, service):
        analysis = self._make_analysis_with_persons()
        with patch.object(service, 'get_analysis', return_value=analysis):
            result = service.get_persons_of_interest("case-1", risk_level=RiskLevel.LOW)
            assert len(result) == 1
            assert result[0].risk_level == RiskLevel.LOW

    def test_filter_by_min_score(self, service):
        analysis = self._make_analysis_with_persons()
        with patch.object(service, 'get_analysis', return_value=analysis):
            result = service.get_persons_of_interest("case-1", min_score=50)
            assert len(result) == 2
            assert all(p.involvement_score.total >= 50 for p in result)

    def test_filter_by_both_risk_and_score(self, service):
        analysis = self._make_analysis_with_persons()
        with patch.object(service, 'get_analysis', return_value=analysis):
            result = service.get_persons_of_interest(
                "case-1", risk_level=RiskLevel.HIGH, min_score=80,
            )
            assert len(result) == 1
            assert result[0].entity_name == "High Risk Person"

    def test_no_analysis_returns_empty(self, service):
        with patch.object(service, 'get_analysis', return_value=None):
            result = service.get_persons_of_interest("case-1")
            assert result == []

    def test_results_sorted_descending(self, service):
        analysis = self._make_analysis_with_persons()
        with patch.object(service, 'get_analysis', return_value=analysis):
            result = service.get_persons_of_interest("case-1")
            totals = [p.involvement_score.total for p in result]
            assert totals == sorted(totals, reverse=True)


# ---------------------------------------------------------------------------
# Tests: spawn_sub_case (Task 3.11)
# ---------------------------------------------------------------------------

class TestSpawnSubCase:
    def test_creates_sub_case_proposal_with_decision(self, service, mock_deps):
        """spawn_sub_case should create a proposal with an AI_Proposed decision."""
        profile = CoConspiratorProfile(
            profile_id="p-1", case_id="case-1",
            entity_name="Target Person", entity_type="PERSON",
            involvement_score=InvolvementScore(
                total=85, connections=90, co_occurrence=80,
                financial=70, communication=60, geographic=50,
            ),
            connection_strength=85, risk_level=RiskLevel.HIGH,
            document_type_count=4,
        )

        with patch.object(service, 'get_person_profile', return_value=profile), \
             patch.object(service, '_cache_sub_case_proposal'):

            # Reset bedrock mock for fresh response
            mock_deps["bedrock_client"].invoke_model.return_value = _make_bedrock_response(
                "Case initiation brief for Target Person"
            )

            result = service.spawn_sub_case("case-1", "p-1")

            assert result.parent_case_id == "case-1"
            assert result.profile_id == "p-1"
            assert result.decision_id is not None
            assert result.status == "proposed"
            assert result.brief.evidence_summary != ""
            assert len(result.brief.proposed_charges) > 0
            assert len(result.brief.investigative_steps) > 0

    def test_creates_decision_with_sub_case_proposal_type(self, service, mock_deps):
        profile = CoConspiratorProfile(
            profile_id="p-1", case_id="case-1",
            entity_name="Target", entity_type="PERSON",
            involvement_score=InvolvementScore(
                total=85, connections=90, co_occurrence=80,
                financial=70, communication=60, geographic=50,
            ),
            connection_strength=85, risk_level=RiskLevel.HIGH,
            document_type_count=4,
        )

        with patch.object(service, 'get_person_profile', return_value=profile), \
             patch.object(service, '_cache_sub_case_proposal'):

            service.spawn_sub_case("case-1", "p-1")

            call_args = mock_deps["decision_workflow_svc"].create_decision.call_args
            assert call_args.kwargs["decision_type"] == "sub_case_proposal"
            assert call_args.kwargs["source_service"] == "network_discovery"


# ---------------------------------------------------------------------------
# Tests: Legal Reasoning (Task 3.6)
# ---------------------------------------------------------------------------

class TestLegalReasoning:
    def test_uses_senior_legal_analyst_persona(self, service, mock_deps):
        profile = CoConspiratorProfile(
            profile_id="p-1", case_id="case-1",
            entity_name="Test", entity_type="PERSON",
            involvement_score=InvolvementScore(
                total=50, connections=50, co_occurrence=50,
                financial=50, communication=50, geographic=50,
            ),
            connection_strength=50, risk_level=RiskLevel.MEDIUM,
        )

        service._generate_legal_reasoning(profile)

        call_args = mock_deps["bedrock_client"].invoke_model.call_args
        body = json.loads(call_args.kwargs["body"])
        assert body["system"] == service.SENIOR_LEGAL_ANALYST_PERSONA

    def test_fallback_on_bedrock_failure(self, service, mock_deps):
        mock_deps["bedrock_client"].invoke_model.side_effect = Exception("Bedrock down")

        profile = CoConspiratorProfile(
            profile_id="p-1", case_id="case-1",
            entity_name="Test Person", entity_type="PERSON",
            involvement_score=InvolvementScore(
                total=50, connections=50, co_occurrence=50,
                financial=50, communication=50, geographic=50,
            ),
            connection_strength=50, risk_level=RiskLevel.MEDIUM,
        )

        result = service._generate_legal_reasoning(profile)

        assert "AI analysis unavailable" in result
        assert "Test Person" in result


# ---------------------------------------------------------------------------
# Tests: get_person_profile (Task 3.9)
# ---------------------------------------------------------------------------

class TestGetPersonProfile:
    def test_raises_key_error_for_missing_analysis(self, service):
        with patch.object(service, 'get_analysis', return_value=None):
            with pytest.raises(KeyError, match="No analysis found"):
                service.get_person_profile("case-1", "p-999")

    def test_raises_key_error_for_missing_person(self, service):
        analysis = NetworkAnalysisResult(
            analysis_id="a-1", case_id="case-1",
            analysis_status=AnalysisStatus.COMPLETED,
            persons_of_interest=[
                CoConspiratorProfile(
                    profile_id="p-1", case_id="case-1",
                    entity_name="Existing", entity_type="PERSON",
                    involvement_score=InvolvementScore(
                        total=50, connections=50, co_occurrence=50,
                        financial=50, communication=50, geographic=50,
                    ),
                    connection_strength=50, risk_level=RiskLevel.MEDIUM,
                ),
            ],
        )
        with patch.object(service, 'get_analysis', return_value=analysis):
            with pytest.raises(KeyError, match="not found"):
                service.get_person_profile("case-1", "p-999")

    def test_returns_matching_profile(self, service):
        profile = CoConspiratorProfile(
            profile_id="p-1", case_id="case-1",
            entity_name="Found Person", entity_type="PERSON",
            involvement_score=InvolvementScore(
                total=75, connections=80, co_occurrence=70,
                financial=60, communication=50, geographic=40,
            ),
            connection_strength=65, risk_level=RiskLevel.MEDIUM,
        )
        analysis = NetworkAnalysisResult(
            analysis_id="a-1", case_id="case-1",
            analysis_status=AnalysisStatus.COMPLETED,
            persons_of_interest=[profile],
        )
        with patch.object(service, 'get_analysis', return_value=analysis):
            result = service.get_person_profile("case-1", "p-1")
            assert result.entity_name == "Found Person"
            assert result.profile_id == "p-1"
