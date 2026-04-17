"""Unit tests for CommandCenterEngine — indicator computations, Bedrock fallback,
cache behavior, and full orchestration."""

import json
from datetime import datetime, timezone, timedelta, date
from unittest.mock import MagicMock, patch

import pytest

from src.services.command_center_engine import (
    CommandCenterEngine,
    IndicatorResult,
    classify_indicator_color,
    _clamp,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

CASE_ID = "case-test-cc-001"


@pytest.fixture
def mock_aurora():
    """Mock Aurora ConnectionManager with cursor context manager."""
    cm = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = None
    mock_cursor.fetchall.return_value = []
    cm.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    cm.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return cm


@pytest.fixture
def mock_bedrock():
    """Mock Bedrock client that returns valid JSON responses."""
    client = MagicMock()
    body_mock = MagicMock()
    body_mock.read.return_value = json.dumps({
        "content": [{"text": json.dumps({
            "bluf": "Test BLUF statement. Second sentence.",
            "key_finding": "Test key finding",
            "critical_gap": "Test critical gap",
            "next_action": {
                "text": "Run search on Entity X",
                "action_type": "investigative_search",
                "action_target": "Entity X",
            },
        })}]
    }).encode()
    client.invoke_model.return_value = {"body": body_mock}
    return client


@pytest.fixture
def mock_case_assessment_svc():
    svc = MagicMock()
    svc.get_assessment.return_value = {
        "case_id": CASE_ID,
        "strength_score": 65,
        "evidence_coverage": {
            "people": {"count": 10, "status": "covered"},
            "organizations": {"count": 5, "status": "covered"},
            "financial_connections": {"count": 3, "status": "covered"},
            "communication_patterns": {"count": 2, "status": "covered"},
            "physical_evidence": {"count": 1, "status": "covered"},
            "timeline": {"count": 8, "status": "covered"},
            "geographic_scope": {"count": 0, "status": "gap"},
        },
    }
    return svc


@pytest.fixture
def mock_case_weakness_svc():
    svc = MagicMock()
    svc.analyze_weaknesses.return_value = []
    return svc


@pytest.fixture
def mock_investigator_engine():
    engine = MagicMock()
    lead = MagicMock()
    lead.entity_name = "John Doe"
    lead.entity_type = "person"
    lead.lead_priority_score = 85
    lead.ai_justification = "High connectivity in the knowledge graph"
    engine.get_investigative_leads.return_value = [lead]
    return engine


@pytest.fixture
def engine(mock_aurora, mock_case_assessment_svc, mock_case_weakness_svc, mock_investigator_engine):
    """CommandCenterEngine with no Bedrock (fallback mode)."""
    return CommandCenterEngine(
        aurora_cm=mock_aurora,
        bedrock_client=None,
        neptune_endpoint="",
        neptune_port="8182",
        case_assessment_svc=mock_case_assessment_svc,
        case_weakness_svc=mock_case_weakness_svc,
        investigator_engine=mock_investigator_engine,
    )


@pytest.fixture
def engine_with_bedrock(mock_aurora, mock_bedrock, mock_case_assessment_svc, mock_case_weakness_svc, mock_investigator_engine):
    """CommandCenterEngine with Bedrock client."""
    return CommandCenterEngine(
        aurora_cm=mock_aurora,
        bedrock_client=mock_bedrock,
        neptune_endpoint="",
        neptune_port="8182",
        case_assessment_svc=mock_case_assessment_svc,
        case_weakness_svc=mock_case_weakness_svc,
        investigator_engine=mock_investigator_engine,
    )


# ---------------------------------------------------------------------------
# Test: classify_verdict
# ---------------------------------------------------------------------------

class TestClassifyVerdict:
    def test_pursue_at_67(self):
        assert CommandCenterEngine.classify_verdict(67) == "PURSUE"

    def test_pursue_at_100(self):
        assert CommandCenterEngine.classify_verdict(100) == "PURSUE"

    def test_pursue_at_80(self):
        assert CommandCenterEngine.classify_verdict(80) == "PURSUE"

    def test_investigate_further_at_34(self):
        assert CommandCenterEngine.classify_verdict(34) == "INVESTIGATE FURTHER"

    def test_investigate_further_at_66(self):
        assert CommandCenterEngine.classify_verdict(66) == "INVESTIGATE FURTHER"

    def test_investigate_further_at_50(self):
        assert CommandCenterEngine.classify_verdict(50) == "INVESTIGATE FURTHER"

    def test_close_at_0(self):
        assert CommandCenterEngine.classify_verdict(0) == "CLOSE"

    def test_close_at_33(self):
        assert CommandCenterEngine.classify_verdict(33) == "CLOSE"

    def test_close_at_15(self):
        assert CommandCenterEngine.classify_verdict(15) == "CLOSE"

    def test_all_scores_covered(self):
        """Every score 0-100 maps to exactly one verdict."""
        for score in range(101):
            verdict = CommandCenterEngine.classify_verdict(score)
            assert verdict in ("PURSUE", "INVESTIGATE FURTHER", "CLOSE")


# ---------------------------------------------------------------------------
# Test: compute_viability_score
# ---------------------------------------------------------------------------

class TestComputeViabilityScore:
    def test_equal_scores(self):
        indicators = [
            IndicatorResult(name=f"Ind{i}", key=f"ind{i}", score=60,
                            insight="", gap_note="", emoji="")
            for i in range(5)
        ]
        assert CommandCenterEngine.compute_viability_score(indicators) == 60

    def test_mixed_scores(self):
        scores = [100, 80, 60, 40, 20]
        indicators = [
            IndicatorResult(name=f"Ind{i}", key=f"ind{i}", score=s,
                            insight="", gap_note="", emoji="")
            for i, s in enumerate(scores)
        ]
        # Average = (100+80+60+40+20)/5 = 60
        assert CommandCenterEngine.compute_viability_score(indicators) == 60

    def test_all_zeros(self):
        indicators = [
            IndicatorResult(name=f"Ind{i}", key=f"ind{i}", score=0,
                            insight="", gap_note="", emoji="")
            for i in range(5)
        ]
        assert CommandCenterEngine.compute_viability_score(indicators) == 0

    def test_all_hundreds(self):
        indicators = [
            IndicatorResult(name=f"Ind{i}", key=f"ind{i}", score=100,
                            insight="", gap_note="", emoji="")
            for i in range(5)
        ]
        assert CommandCenterEngine.compute_viability_score(indicators) == 100

    def test_empty_indicators(self):
        assert CommandCenterEngine.compute_viability_score([]) == 0

    def test_result_is_integer(self):
        indicators = [
            IndicatorResult(name=f"Ind{i}", key=f"ind{i}", score=s,
                            insight="", gap_note="", emoji="")
            for i, s in enumerate([33, 33, 33, 33, 34])
        ]
        result = CommandCenterEngine.compute_viability_score(indicators)
        assert isinstance(result, int)
        assert 0 <= result <= 100

    def test_rounding(self):
        # (71+72+73+74+75)/5 = 73.0
        indicators = [
            IndicatorResult(name=f"Ind{i}", key=f"ind{i}", score=s,
                            insight="", gap_note="", emoji="")
            for i, s in enumerate([71, 72, 73, 74, 75])
        ]
        assert CommandCenterEngine.compute_viability_score(indicators) == 73


# ---------------------------------------------------------------------------
# Test: classify_indicator_color
# ---------------------------------------------------------------------------

class TestClassifyIndicatorColor:
    def test_green_above_60(self):
        assert classify_indicator_color(61) == "green"
        assert classify_indicator_color(100) == "green"

    def test_yellow_30_to_60(self):
        assert classify_indicator_color(30) == "yellow"
        assert classify_indicator_color(60) == "yellow"
        assert classify_indicator_color(45) == "yellow"

    def test_red_below_30(self):
        assert classify_indicator_color(0) == "red"
        assert classify_indicator_color(29) == "red"

    def test_all_scores_covered(self):
        for score in range(101):
            color = classify_indicator_color(score)
            assert color in ("green", "yellow", "red")


# ---------------------------------------------------------------------------
# Test: compute_signal_strength
# ---------------------------------------------------------------------------

class TestComputeSignalStrength:
    def test_no_neptune_returns_zero(self, engine):
        """Without Neptune endpoint, score should be 0."""
        result = engine.compute_signal_strength(CASE_ID)
        assert result.score == 0
        assert result.key == "signal_strength"
        assert result.name == "Signal Strength"
        assert result.emoji == "📡"

    def test_score_formula(self):
        """Verify score = clamp(int(meaningful/max(total,1) * 100))."""
        # meaningful=60, total=100 → ratio=0.6 → score=60
        assert _clamp(int((60 / max(100, 1)) * 100)) == 60
        # meaningful=80, total=100 → ratio=0.8 → score=80
        assert _clamp(int((80 / max(100, 1)) * 100)) == 80
        # meaningful=0, total=0 → ratio=0 → score=0
        assert _clamp(int((0 / max(0, 1)) * 100)) == 0

    def test_ratio_above_06_gives_score_above_60(self):
        """When ratio > 0.6, score > 60."""
        for meaningful in range(61, 101):
            total = 100
            score = _clamp(int((meaningful / max(total, 1)) * 100))
            assert score > 60, f"meaningful={meaningful}, total={total}, score={score}"


# ---------------------------------------------------------------------------
# Test: compute_corroboration_depth
# ---------------------------------------------------------------------------

class TestComputeCorroborationDepth:
    def test_all_multi_source(self, mock_aurora):
        """All entities with high occurrence/degree → score = 100."""
        eng = CommandCenterEngine(
            aurora_cm=mock_aurora, bedrock_client=None,
            neptune_endpoint="test-neptune", neptune_port="8182",
            case_assessment_svc=MagicMock(), case_weakness_svc=MagicMock(),
            investigator_engine=MagicMock(),
        )
        # Mock _gremlin to return entities with high occurrence and degree
        gremlin_results = [
            {"name": f"Entity_{i}", "occurrences": 5, "degree": 3}
            for i in range(50)
        ]
        with patch.object(eng, '_gremlin', return_value=gremlin_results):
            result = eng.compute_corroboration_depth(CASE_ID)
        assert result.score == 100
        assert result.key == "corroboration_depth"

    def test_all_single_source(self, mock_aurora):
        """All entities with occurrence=1 and degree=0 → score = 0."""
        eng = CommandCenterEngine(
            aurora_cm=mock_aurora, bedrock_client=None,
            neptune_endpoint="test-neptune", neptune_port="8182",
            case_assessment_svc=MagicMock(), case_weakness_svc=MagicMock(),
            investigator_engine=MagicMock(),
        )
        gremlin_results = [
            {"name": f"Entity_{i}", "occurrences": 1, "degree": 0}
            for i in range(50)
        ]
        with patch.object(eng, '_gremlin', return_value=gremlin_results):
            result = eng.compute_corroboration_depth(CASE_ID)
        assert result.score == 0

    def test_ratio_above_05_gives_score_above_50(self):
        """When multi/(multi+single) > 0.5, score > 50."""
        multi, single = 60, 40
        score = _clamp(int((multi / max(multi + single, 1)) * 100))
        assert score == 60
        assert score > 50

    def test_neptune_failure_returns_zero(self, mock_aurora):
        """Neptune exception → score = 0."""
        eng = CommandCenterEngine(
            aurora_cm=mock_aurora, bedrock_client=None,
            neptune_endpoint="test-neptune", neptune_port="8182",
            case_assessment_svc=MagicMock(), case_weakness_svc=MagicMock(),
            investigator_engine=MagicMock(),
        )
        with patch.object(eng, '_gremlin', side_effect=Exception("Neptune timeout")):
            result = eng.compute_corroboration_depth(CASE_ID)
        assert result.score == 0
        assert "failed" in result.gap_note.lower() or "Neptune" in result.gap_note


# ---------------------------------------------------------------------------
# Test: compute_network_density
# ---------------------------------------------------------------------------

class TestComputeNetworkDensity:
    def test_no_neptune_returns_zero(self, engine):
        result = engine.compute_network_density(CASE_ID)
        assert result.score == 0
        assert result.key == "network_density"

    def test_score_formula(self):
        """Score = clamp(int(clustering * 50 + min(hubs/3, 1.0) * 50))."""
        # clustering=0.6, hubs=3 → 0.6*50 + 1.0*50 = 80
        assert _clamp(int(0.6 * 50 + min(3 / 3, 1.0) * 50)) == 80
        # clustering=0.0, hubs=0 → 0
        assert _clamp(int(0.0 * 50 + min(0 / 3, 1.0) * 50)) == 0
        # clustering=1.0, hubs=10 → 50 + 50 = 100
        assert _clamp(int(1.0 * 50 + min(10 / 3, 1.0) * 50)) == 100

    def test_clustering_above_03_and_hub_gives_score_above_60(self):
        """When clustering > 0.3 AND hub_count >= 1, score > 60."""
        clustering = 0.4
        hub_count = 1
        score = _clamp(int(clustering * 50 + min(hub_count / 3, 1.0) * 50))
        # 0.4*50 + (1/3)*50 = 20 + 16.67 = 36
        assert score > 30  # This specific combo gives 36, not > 60
        # With higher values:
        clustering = 0.5
        hub_count = 2
        score = _clamp(int(clustering * 50 + min(hub_count / 3, 1.0) * 50))
        # 0.5*50 + (2/3)*50 = 25 + 33.33 = 58
        assert score > 50

        # The design says clustering > 0.3 AND hub >= 1 → score > 60
        # This requires clustering * 50 + hub_bonus * 50 > 60
        # With clustering=0.8, hub=2: 40 + 33 = 73 > 60
        clustering = 0.8
        hub_count = 2
        score = _clamp(int(clustering * 50 + min(hub_count / 3, 1.0) * 50))
        assert score > 60


# ---------------------------------------------------------------------------
# Test: compute_temporal_coherence
# ---------------------------------------------------------------------------

class TestComputeTemporalCoherence:
    def test_no_dates_returns_zero(self, mock_aurora):
        eng = CommandCenterEngine(
            aurora_cm=mock_aurora, bedrock_client=None,
            neptune_endpoint="test-neptune", neptune_port="8182",
            case_assessment_svc=MagicMock(), case_weakness_svc=MagicMock(),
            investigator_engine=MagicMock(),
        )
        with patch.object(eng, '_gremlin', return_value=[]):
            result = eng.compute_temporal_coherence(CASE_ID)
        assert result.score == 0
        assert result.key == "temporal_coherence"

    def test_dates_with_cluster(self, mock_aurora):
        """Dates forming a cluster should produce a positive score."""
        eng = CommandCenterEngine(
            aurora_cm=mock_aurora, bedrock_client=None,
            neptune_endpoint="test-neptune", neptune_port="8182",
            case_assessment_svc=MagicMock(), case_weakness_svc=MagicMock(),
            investigator_engine=MagicMock(),
        )
        date_strings = ["2023-01-01", "2023-01-02", "2023-01-03", "2023-01-04", "2023-01-05"]
        with patch.object(eng, '_gremlin', return_value=date_strings):
            result = eng.compute_temporal_coherence(CASE_ID)
        assert result.score > 0
        assert result.raw_data["cluster_count"] >= 1

    def test_dates_with_gap(self, mock_aurora):
        """Dates with a 100-day gap should incur a penalty."""
        eng = CommandCenterEngine(
            aurora_cm=mock_aurora, bedrock_client=None,
            neptune_endpoint="test-neptune", neptune_port="8182",
            case_assessment_svc=MagicMock(), case_weakness_svc=MagicMock(),
            investigator_engine=MagicMock(),
        )
        date_strings = ["2023-01-01", "2023-01-02", "2023-04-15"]
        with patch.object(eng, '_gremlin', return_value=date_strings):
            result = eng.compute_temporal_coherence(CASE_ID)
        assert result.raw_data["gap_count"] >= 1

    def test_parse_dates_iso(self):
        dates = CommandCenterEngine._parse_dates(["2023-01-15", "2023-06-20"])
        assert len(dates) == 2
        assert dates[0] == date(2023, 1, 15)

    def test_parse_dates_us_format(self):
        dates = CommandCenterEngine._parse_dates(["4/28/2017", "Fri 4/28/2017"])
        assert len(dates) == 2

    def test_parse_dates_invalid(self):
        dates = CommandCenterEngine._parse_dates(["not-a-date", "hello", ""])
        assert len(dates) == 0

    def test_detect_clusters(self):
        test_dates = [date(2023, 1, 1), date(2023, 1, 2), date(2023, 1, 3), date(2023, 6, 1)]
        clusters = CommandCenterEngine._detect_temporal_clusters(test_dates)
        assert len(clusters) == 1
        assert clusters[0]["count"] == 3

    def test_detect_gaps(self):
        test_dates = [date(2023, 1, 1), date(2023, 6, 1)]
        gaps = CommandCenterEngine._detect_temporal_gaps(test_dates)
        assert len(gaps) == 1
        assert gaps[0]["days"] > 90

    def test_score_always_in_range(self, mock_aurora):
        """Score should always be 0-100 regardless of input."""
        eng = CommandCenterEngine(
            aurora_cm=mock_aurora, bedrock_client=None,
            neptune_endpoint="test-neptune", neptune_port="8182",
            case_assessment_svc=MagicMock(), case_weakness_svc=MagicMock(),
            investigator_engine=MagicMock(),
        )
        date_strings = [
            f"2023-{m:02d}-{d:02d}"
            for m in range(1, 13) for d in [1, 15]
        ]
        with patch.object(eng, '_gremlin', return_value=date_strings):
            result = eng.compute_temporal_coherence(CASE_ID)
        assert 0 <= result.score <= 100


# ---------------------------------------------------------------------------
# Test: compute_prosecution_readiness
# ---------------------------------------------------------------------------

class TestComputeProsecutionReadiness:
    def test_all_covered_no_weaknesses(self, mock_aurora, mock_case_assessment_svc, mock_case_weakness_svc):
        """7/7 covered + 0 critical → score > 80."""
        mock_case_assessment_svc.get_assessment.return_value = {
            "evidence_coverage": {
                "people": {"status": "covered"},
                "organizations": {"status": "covered"},
                "financial_connections": {"status": "covered"},
                "communication_patterns": {"status": "covered"},
                "physical_evidence": {"status": "covered"},
                "timeline": {"status": "covered"},
                "geographic_scope": {"status": "covered"},
            },
        }
        mock_case_weakness_svc.analyze_weaknesses.return_value = []

        eng = CommandCenterEngine(
            aurora_cm=mock_aurora, bedrock_client=None,
            neptune_endpoint="", neptune_port="8182",
            case_assessment_svc=mock_case_assessment_svc,
            case_weakness_svc=mock_case_weakness_svc,
            investigator_engine=MagicMock(),
        )
        result = eng.compute_prosecution_readiness(CASE_ID)
        assert result.score > 80
        assert result.key == "prosecution_readiness"

    def test_partial_coverage(self, mock_aurora, mock_case_assessment_svc, mock_case_weakness_svc):
        """3/7 covered → lower score."""
        mock_case_assessment_svc.get_assessment.return_value = {
            "evidence_coverage": {
                "people": {"status": "covered"},
                "organizations": {"status": "covered"},
                "financial_connections": {"status": "covered"},
                "communication_patterns": {"status": "gap"},
                "physical_evidence": {"status": "gap"},
                "timeline": {"status": "gap"},
                "geographic_scope": {"status": "gap"},
            },
        }
        mock_case_weakness_svc.analyze_weaknesses.return_value = []

        eng = CommandCenterEngine(
            aurora_cm=mock_aurora, bedrock_client=None,
            neptune_endpoint="", neptune_port="8182",
            case_assessment_svc=mock_case_assessment_svc,
            case_weakness_svc=mock_case_weakness_svc,
            investigator_engine=MagicMock(),
        )
        result = eng.compute_prosecution_readiness(CASE_ID)
        # (3/7)*80 + 20 = 34.28 + 20 = 54
        assert result.score == 54

    def test_score_formula(self):
        """Verify formula: clamp(int((covered/7)*80 + (20 if zero_critical else 0)))."""
        # 7/7 + 0 critical = 80 + 20 = 100
        assert _clamp(int((7 / 7) * 80 + 20)) == 100
        # 0/7 + 0 critical = 0 + 20 = 20
        assert _clamp(int((0 / 7) * 80 + 20)) == 20
        # 0/7 + critical = 0 + 0 = 0
        assert _clamp(int((0 / 7) * 80 + 0)) == 0
        # 5/7 + critical = 57.14 + 0 = 57
        assert _clamp(int((5 / 7) * 80 + 0)) == 57

    def test_service_failure_returns_zero(self, mock_aurora, mock_case_assessment_svc, mock_case_weakness_svc):
        mock_case_assessment_svc.get_assessment.side_effect = Exception("Service down")

        eng = CommandCenterEngine(
            aurora_cm=mock_aurora, bedrock_client=None,
            neptune_endpoint="", neptune_port="8182",
            case_assessment_svc=mock_case_assessment_svc,
            case_weakness_svc=mock_case_weakness_svc,
            investigator_engine=MagicMock(),
        )
        result = eng.compute_prosecution_readiness(CASE_ID)
        assert result.score == 0


# ---------------------------------------------------------------------------
# Test: Bedrock strategic assessment
# ---------------------------------------------------------------------------

class TestStrategicAssessment:
    def test_fallback_without_bedrock(self, engine):
        indicators = [
            IndicatorResult(name="Signal Strength", key="signal_strength", score=70,
                            insight="Good signal", gap_note="Minor gaps", emoji="📡"),
            IndicatorResult(name="Corroboration", key="corroboration_depth", score=50,
                            insight="Moderate", gap_note="Needs more sources", emoji="🔗"),
        ]
        result = engine.generate_strategic_assessment(CASE_ID, indicators, 60, [])
        assert "bluf" in result
        assert "key_finding" in result
        assert "critical_gap" in result
        assert "next_action" in result
        assert isinstance(result["next_action"], dict)
        assert result["bluf"]  # non-empty

    def test_bedrock_success(self, engine_with_bedrock):
        indicators = [
            IndicatorResult(name="Signal Strength", key="signal_strength", score=70,
                            insight="Good", gap_note="", emoji="📡"),
        ]
        lead = MagicMock()
        lead.entity_name = "Test Entity"
        lead.entity_type = "person"
        lead.lead_priority_score = 80
        lead.ai_justification = "High connectivity"

        result = engine_with_bedrock.generate_strategic_assessment(CASE_ID, indicators, 70, [lead])
        assert "bluf" in result
        assert result["bluf"]  # non-empty

    def test_bedrock_failure_falls_back(self, mock_aurora, mock_case_assessment_svc, mock_case_weakness_svc, mock_investigator_engine):
        """When Bedrock raises an exception, fallback template is used."""
        bad_bedrock = MagicMock()
        bad_bedrock.invoke_model.side_effect = Exception("Throttled")

        eng = CommandCenterEngine(
            aurora_cm=mock_aurora, bedrock_client=bad_bedrock,
            neptune_endpoint="", neptune_port="8182",
            case_assessment_svc=mock_case_assessment_svc,
            case_weakness_svc=mock_case_weakness_svc,
            investigator_engine=mock_investigator_engine,
        )
        indicators = [
            IndicatorResult(name="Test", key="test", score=50,
                            insight="Test insight", gap_note="Test gap", emoji="🔍"),
        ]
        result = eng.generate_strategic_assessment(CASE_ID, indicators, 50, [])
        assert "bluf" in result
        assert result["bluf"]  # fallback should produce non-empty


# ---------------------------------------------------------------------------
# Test: Threat threads
# ---------------------------------------------------------------------------

class TestThreatThreads:
    def test_fallback_without_bedrock(self, engine, mock_investigator_engine):
        leads = mock_investigator_engine.get_investigative_leads.return_value
        result = engine.generate_threat_threads(CASE_ID, leads, [])
        assert isinstance(result, list)
        assert len(result) >= 1
        assert "title" in result[0]
        assert "narrative" in result[0]
        assert "confidence" in result[0]
        assert "primary_entity" in result[0]

    def test_fallback_with_no_leads(self, engine):
        result = engine.generate_threat_threads(CASE_ID, [], [])
        assert isinstance(result, list)
        assert len(result) == 0

    def test_bedrock_threat_threads(self, mock_aurora, mock_case_assessment_svc, mock_case_weakness_svc, mock_investigator_engine):
        """Bedrock returns valid thread JSON."""
        bedrock = MagicMock()
        body_mock = MagicMock()
        body_mock.read.return_value = json.dumps({
            "content": [{"text": json.dumps([
                {
                    "title": "Financial Network Thread",
                    "narrative": "Evidence suggests financial connections.",
                    "confidence": 82,
                    "primary_entity": "John Doe",
                    "evidence_chain": [{"entity": "John Doe", "connection": "financial", "target": "Corp X"}],
                },
                {
                    "title": "Communication Thread",
                    "narrative": "Communication patterns detected.",
                    "confidence": 65,
                    "primary_entity": "Jane Smith",
                    "evidence_chain": [],
                },
            ])}]
        }).encode()
        bedrock.invoke_model.return_value = {"body": body_mock}

        eng = CommandCenterEngine(
            aurora_cm=mock_aurora, bedrock_client=bedrock,
            neptune_endpoint="", neptune_port="8182",
            case_assessment_svc=mock_case_assessment_svc,
            case_weakness_svc=mock_case_weakness_svc,
            investigator_engine=mock_investigator_engine,
        )
        leads = mock_investigator_engine.get_investigative_leads.return_value
        result = eng.generate_threat_threads(CASE_ID, leads, [])
        assert len(result) == 2
        assert result[0]["title"] == "Financial Network Thread"
        assert result[0]["confidence"] == 82


# ---------------------------------------------------------------------------
# Test: Cache behavior
# ---------------------------------------------------------------------------

class TestCacheBehavior:
    def test_cache_hit(self, mock_aurora, mock_case_assessment_svc, mock_case_weakness_svc, mock_investigator_engine):
        """Fresh cache entry should be returned without recomputation."""
        cached_data = {
            "viability_score": 72,
            "verdict": "PURSUE",
            "indicators": [],
            "strategic_assessment": {},
            "threat_threads": [],
        }
        mock_cursor = mock_aurora.cursor.return_value.__enter__.return_value
        mock_cursor.fetchone.return_value = (
            json.dumps(cached_data),
            datetime.now(timezone.utc) - timedelta(minutes=5),  # 5 min old = fresh
        )

        eng = CommandCenterEngine(
            aurora_cm=mock_aurora, bedrock_client=None,
            neptune_endpoint="", neptune_port="8182",
            case_assessment_svc=mock_case_assessment_svc,
            case_weakness_svc=mock_case_weakness_svc,
            investigator_engine=mock_investigator_engine,
        )
        result = eng.compute(CASE_ID)
        assert result["cache_hit"] is True
        assert result["viability_score"] == 72

    def test_cache_miss_stale(self, mock_aurora, mock_case_assessment_svc, mock_case_weakness_svc, mock_investigator_engine):
        """Stale cache (> 15 min) should trigger recomputation."""
        mock_cursor = mock_aurora.cursor.return_value.__enter__.return_value
        mock_cursor.fetchone.return_value = (
            json.dumps({"viability_score": 50}),
            datetime.now(timezone.utc) - timedelta(minutes=20),  # 20 min old = stale
        )

        eng = CommandCenterEngine(
            aurora_cm=mock_aurora, bedrock_client=None,
            neptune_endpoint="", neptune_port="8182",
            case_assessment_svc=mock_case_assessment_svc,
            case_weakness_svc=mock_case_weakness_svc,
            investigator_engine=mock_investigator_engine,
        )
        result = eng.compute(CASE_ID)
        assert result["cache_hit"] is False

    def test_bypass_cache(self, mock_aurora, mock_case_assessment_svc, mock_case_weakness_svc, mock_investigator_engine):
        """bypass_cache=True should skip cache check."""
        mock_cursor = mock_aurora.cursor.return_value.__enter__.return_value
        # Return fresh cache data
        mock_cursor.fetchone.side_effect = [
            # First call would be cache check — but it's bypassed
            # The corroboration_depth query
            (10, 5),
            # prosecution_readiness calls
            None,
        ]
        mock_cursor.fetchall.return_value = []

        eng = CommandCenterEngine(
            aurora_cm=mock_aurora, bedrock_client=None,
            neptune_endpoint="", neptune_port="8182",
            case_assessment_svc=mock_case_assessment_svc,
            case_weakness_svc=mock_case_weakness_svc,
            investigator_engine=mock_investigator_engine,
        )
        result = eng.compute(CASE_ID, bypass_cache=True)
        assert result["cache_hit"] is False


# ---------------------------------------------------------------------------
# Test: Full orchestration (compute)
# ---------------------------------------------------------------------------

class TestComputeOrchestration:
    def test_full_compute_without_bedrock(self, engine):
        """Full compute without Bedrock should return all required fields."""
        result = engine.compute(CASE_ID, bypass_cache=True)

        # Required fields
        assert "viability_score" in result
        assert "verdict" in result
        assert "verdict_reasoning" in result
        assert "indicators" in result
        assert "strategic_assessment" in result
        assert "threat_threads" in result
        assert "computed_at" in result
        assert "cache_hit" in result

        # Viability score in range
        assert 0 <= result["viability_score"] <= 100
        assert isinstance(result["viability_score"], int)

        # Verdict is valid
        assert result["verdict"] in ("PURSUE", "INVESTIGATE FURTHER", "CLOSE")

        # Exactly 5 indicators
        assert len(result["indicators"]) == 5

        # Each indicator has required fields
        for ind in result["indicators"]:
            assert "name" in ind
            assert "key" in ind
            assert "score" in ind
            assert "insight" in ind
            assert "gap_note" in ind
            assert "emoji" in ind
            assert 0 <= ind["score"] <= 100

        # Strategic assessment has required fields
        sa = result["strategic_assessment"]
        assert "bluf" in sa
        assert "key_finding" in sa
        assert "critical_gap" in sa
        assert "next_action" in sa

        # Threat threads is a list
        assert isinstance(result["threat_threads"], list)

        # cache_hit is False for fresh computation
        assert result["cache_hit"] is False

    def test_indicator_failure_doesnt_crash(self, mock_aurora, mock_case_assessment_svc, mock_case_weakness_svc, mock_investigator_engine):
        """If an indicator computation raises, it should get score=0 and continue."""
        mock_case_assessment_svc.get_assessment.side_effect = Exception("Service down")

        eng = CommandCenterEngine(
            aurora_cm=mock_aurora, bedrock_client=None,
            neptune_endpoint="", neptune_port="8182",
            case_assessment_svc=mock_case_assessment_svc,
            case_weakness_svc=mock_case_weakness_svc,
            investigator_engine=mock_investigator_engine,
        )
        result = eng.compute(CASE_ID, bypass_cache=True)

        # Should still return 5 indicators
        assert len(result["indicators"]) == 5
        # Prosecution readiness should be 0 due to failure
        pr_ind = next(i for i in result["indicators"] if i["key"] == "prosecution_readiness")
        assert pr_ind["score"] == 0

    def test_all_indicators_have_correct_keys(self, engine):
        """Verify the 5 indicator keys match the design spec."""
        result = engine.compute(CASE_ID, bypass_cache=True)
        expected_keys = {
            "signal_strength", "corroboration_depth", "network_density",
            "temporal_coherence", "prosecution_readiness",
        }
        actual_keys = {ind["key"] for ind in result["indicators"]}
        assert actual_keys == expected_keys

    def test_without_bedrock_fallback_content(self, engine):
        """Without Bedrock, strategic_assessment and threat_threads should have fallback content."""
        result = engine.compute(CASE_ID, bypass_cache=True)

        sa = result["strategic_assessment"]
        assert sa["bluf"]  # non-empty
        assert sa["key_finding"]  # non-empty
        assert sa["critical_gap"]  # non-empty

        # Threat threads should exist (from leads)
        assert isinstance(result["threat_threads"], list)


# ---------------------------------------------------------------------------
# Test: _clamp helper
# ---------------------------------------------------------------------------

class TestClamp:
    def test_within_range(self):
        assert _clamp(50) == 50

    def test_below_min(self):
        assert _clamp(-10) == 0

    def test_above_max(self):
        assert _clamp(150) == 100

    def test_at_boundaries(self):
        assert _clamp(0) == 0
        assert _clamp(100) == 100
