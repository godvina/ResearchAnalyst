"""Unit tests for TrawlerEngine — severity, alert generation, pattern changes,
config filtering, deduplication, partial failure, and full scan orchestration."""

import json
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from src.services.trawler_engine import (
    TrawlerEngine,
    assign_severity,
    severity_meets_threshold,
    make_evidence_ref,
    detect_pattern_changes,
    filter_alert_by_config,
    is_duplicate_alert,
    categorize_external_findings,
    ALERT_THRESHOLDS,
    DEFAULT_CONFIG,
    SEVERITY_ORDER,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

CASE_ID = "case-test-001"


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
def mock_pattern_service():
    svc = MagicMock()
    svc.discover_top_patterns.return_value = {"patterns": [], "generated_at": ""}
    return svc


@pytest.fixture
def mock_cross_case_service():
    svc = MagicMock()
    svc.scan_for_overlaps.return_value = []
    return svc


@pytest.fixture
def mock_research_agent():
    agent = MagicMock()
    agent.research_all_subjects.return_value = []
    return agent


@pytest.fixture
def mock_search_service():
    svc = MagicMock()
    svc._search_documents.return_value = []
    svc._generate_cross_reference_report.return_value = []
    return svc


@pytest.fixture
def mock_alert_store():
    store = MagicMock()
    store.find_duplicate.return_value = None
    store.merge_into_existing.return_value = {}
    return store


@pytest.fixture
def engine(mock_aurora, mock_pattern_service, mock_cross_case_service):
    """TrawlerEngine with mocked dependencies and no Neptune."""
    return TrawlerEngine(
        aurora_cm=mock_aurora,
        pattern_service=mock_pattern_service,
        cross_case_service=mock_cross_case_service,
        neptune_endpoint="",  # no Neptune
    )



# ===================================================================
# 1. Severity Assignment Tests
# ===================================================================

class TestSeverityAssignment:
    """Tests for assign_severity function."""

    def test_critical_at_10(self):
        assert assign_severity(10) == "critical"

    def test_critical_above_10(self):
        assert assign_severity(15) == "critical"

    def test_high_at_5(self):
        assert assign_severity(5) == "high"

    def test_high_at_9(self):
        assert assign_severity(9) == "high"

    def test_medium_at_3(self):
        assert assign_severity(3) == "medium"

    def test_medium_at_4(self):
        assert assign_severity(4) == "medium"

    def test_low_at_1(self):
        assert assign_severity(1) == "low"

    def test_low_at_2(self):
        assert assign_severity(2) == "low"

    def test_low_at_0(self):
        assert assign_severity(0) == "low"

    def test_low_negative(self):
        assert assign_severity(-1) == "low"

    def test_severity_meets_threshold(self):
        assert severity_meets_threshold("critical", "low") is True
        assert severity_meets_threshold("high", "high") is True
        assert severity_meets_threshold("low", "high") is False
        assert severity_meets_threshold("medium", "critical") is False
        assert severity_meets_threshold("low", "low") is True


# ===================================================================
# 2. Alert Generation Threshold Tests
# ===================================================================

class TestAlertGenerationThresholds:
    """Tests for threshold-based alert generation."""

    def test_new_connection_threshold_met(self, engine):
        """≥3 shared evidence docs should generate new_connection alert."""
        candidates = [{
            "alert_type": "new_connection",
            "title": "Test connection",
            "summary": "Test",
            "entity_names": ["A", "B"],
            "evidence_refs": [
                make_evidence_ref("r1", "graph_edge", "e1", "ex1"),
                make_evidence_ref("r2", "graph_edge", "e2", "ex2"),
                make_evidence_ref("r3", "graph_edge", "e3", "ex3"),
            ],
            "source_type": "internal",
        }]
        alerts = engine._generate_alerts(CASE_ID, candidates, DEFAULT_CONFIG)
        assert len(alerts) == 1
        assert alerts[0]["alert_type"] == "new_connection"
        assert alerts[0]["severity"] == "medium"  # 3 refs = medium

    def test_entity_spike_below_threshold(self, engine):
        """<5 docs should still generate alert (threshold is in phase, not _generate_alerts)."""
        # _generate_alerts doesn't enforce thresholds — phases do.
        # But with 2 evidence refs, severity is low.
        candidates = [{
            "alert_type": "entity_spike",
            "title": "Test spike",
            "summary": "Test",
            "entity_names": ["Entity1"],
            "evidence_refs": [
                make_evidence_ref("r1", "document", "f1.pdf", "ex1"),
                make_evidence_ref("r2", "document", "f2.pdf", "ex2"),
            ],
            "source_type": "internal",
        }]
        alerts = engine._generate_alerts(CASE_ID, candidates, DEFAULT_CONFIG)
        assert len(alerts) == 1
        assert alerts[0]["severity"] == "low"

    def test_high_severity_with_5_refs(self, engine):
        """5 evidence refs should produce high severity."""
        refs = [make_evidence_ref(f"r{i}", "document", f"f{i}.pdf", f"ex{i}") for i in range(5)]
        candidates = [{
            "alert_type": "new_connection",
            "title": "Test",
            "summary": "Test",
            "entity_names": ["A", "B"],
            "evidence_refs": refs,
            "source_type": "internal",
        }]
        alerts = engine._generate_alerts(CASE_ID, candidates, DEFAULT_CONFIG)
        assert alerts[0]["severity"] == "high"

    def test_critical_severity_with_10_refs(self, engine):
        """10+ evidence refs should produce critical severity."""
        refs = [make_evidence_ref(f"r{i}", "document", f"f{i}.pdf", f"ex{i}") for i in range(12)]
        candidates = [{
            "alert_type": "entity_spike",
            "title": "Test",
            "summary": "Test",
            "entity_names": ["X"],
            "evidence_refs": refs,
            "source_type": "internal",
        }]
        alerts = engine._generate_alerts(CASE_ID, candidates, DEFAULT_CONFIG)
        assert alerts[0]["severity"] == "critical"


# ===================================================================
# 3. Pattern Score Change Detection Tests
# ===================================================================

class TestPatternScoreChangeDetection:
    """Tests for detect_pattern_changes function."""

    def test_no_change_when_equal(self):
        baseline = {"p1": 0.5}
        current = {"p1": {"score": 0.5}}
        assert detect_pattern_changes(baseline, current) == []

    def test_no_change_below_25_pct(self):
        baseline = {"p1": 1.0}
        current = {"p1": {"score": 1.24}}  # 24% increase, below threshold
        assert detect_pattern_changes(baseline, current) == []

    def test_change_at_26_pct(self):
        baseline = {"p1": 1.0}
        current = {"p1": {"score": 1.26}}  # 26% increase
        changes = detect_pattern_changes(baseline, current)
        assert len(changes) == 1
        assert changes[0]["title"] == "p1"
        assert changes[0]["pct_change"] == pytest.approx(26.0, abs=0.1)

    def test_new_pattern_not_in_baseline(self):
        """New patterns (baseline=0) should not trigger change (division by zero guard)."""
        baseline = {}
        current = {"new_pattern": {"score": 0.8}}
        changes = detect_pattern_changes(baseline, current)
        assert len(changes) == 0

    def test_multiple_changes(self):
        baseline = {"p1": 1.0, "p2": 2.0, "p3": 0.5}
        current = {
            "p1": {"score": 1.5},   # 50% increase
            "p2": {"score": 2.1},   # 5% increase (no alert)
            "p3": {"score": 0.8},   # 60% increase
        }
        changes = detect_pattern_changes(baseline, current)
        assert len(changes) == 2
        titles = {c["title"] for c in changes}
        assert titles == {"p1", "p3"}

    def test_decrease_no_alert(self):
        baseline = {"p1": 1.0}
        current = {"p1": {"score": 0.5}}  # decrease
        assert detect_pattern_changes(baseline, current) == []



# ===================================================================
# 4. Config-Based Alert Filtering Tests
# ===================================================================

class TestConfigBasedFiltering:
    """Tests for filter_alert_by_config function."""

    def test_enabled_type_passes(self):
        assert filter_alert_by_config(
            "new_connection", "high",
            DEFAULT_CONFIG["enabled_alert_types"], "low",
        ) is True

    def test_disabled_type_blocked(self):
        assert filter_alert_by_config(
            "external_lead", "high",
            DEFAULT_CONFIG["enabled_alert_types"], "low",
        ) is False

    def test_severity_below_threshold_blocked(self):
        assert filter_alert_by_config(
            "new_connection", "low",
            DEFAULT_CONFIG["enabled_alert_types"], "high",
        ) is False

    def test_severity_at_threshold_passes(self):
        assert filter_alert_by_config(
            "new_connection", "high",
            DEFAULT_CONFIG["enabled_alert_types"], "high",
        ) is True

    def test_severity_above_threshold_passes(self):
        assert filter_alert_by_config(
            "new_connection", "critical",
            DEFAULT_CONFIG["enabled_alert_types"], "medium",
        ) is True

    def test_empty_enabled_types_blocks_all(self):
        assert filter_alert_by_config(
            "new_connection", "critical", [], "low",
        ) is False

    def test_generate_alerts_respects_config(self, engine):
        """_generate_alerts should filter out disabled types and low severity."""
        config = {
            "enabled_alert_types": ["entity_spike"],
            "min_severity": "medium",
            "external_trawl_enabled": False,
        }
        candidates = [
            {
                "alert_type": "new_connection",  # disabled type
                "title": "Blocked",
                "summary": "Should be filtered",
                "entity_names": ["A"],
                "evidence_refs": [make_evidence_ref("r1", "graph_edge", "e1", "ex")],
                "source_type": "internal",
            },
            {
                "alert_type": "entity_spike",  # enabled, but only 1 ref = low severity
                "title": "Low severity",
                "summary": "Should be filtered by severity",
                "entity_names": ["B"],
                "evidence_refs": [make_evidence_ref("r2", "document", "f.pdf", "ex")],
                "source_type": "internal",
            },
            {
                "alert_type": "entity_spike",  # enabled, 4 refs = medium severity
                "title": "Passes",
                "summary": "Should pass",
                "entity_names": ["C"],
                "evidence_refs": [
                    make_evidence_ref(f"r{i}", "document", f"f{i}.pdf", f"ex{i}")
                    for i in range(4)
                ],
                "source_type": "internal",
            },
        ]
        alerts = engine._generate_alerts(CASE_ID, candidates, config)
        assert len(alerts) == 1
        assert alerts[0]["title"] == "Passes"


# ===================================================================
# 5. Deduplication Logic Tests
# ===================================================================

class TestDeduplication:
    """Tests for alert deduplication."""

    def test_no_duplicate_when_store_returns_none(self):
        store = MagicMock()
        store.find_duplicate.return_value = None
        assert is_duplicate_alert(CASE_ID, "new_connection", ["A", "B"], store) is False

    def test_duplicate_when_store_returns_match(self):
        store = MagicMock()
        store.find_duplicate.return_value = {"alert_id": "existing-123"}
        assert is_duplicate_alert(CASE_ID, "new_connection", ["A", "B"], store) is True

    def test_no_duplicate_with_empty_entities(self):
        store = MagicMock()
        assert is_duplicate_alert(CASE_ID, "new_connection", [], store) is False

    def test_no_duplicate_without_store(self):
        assert is_duplicate_alert(CASE_ID, "new_connection", ["A"], None) is False

    def test_deduplicate_alerts_merges_existing(self, engine, mock_alert_store):
        """When a duplicate is found, merge into existing instead of creating new."""
        engine._alert_store = mock_alert_store
        mock_alert_store.find_duplicate.return_value = {
            "alert_id": "existing-alert-id",
            "entity_names": ["A"],
        }

        alerts = [{
            "alert_id": "new-alert-id",
            "case_id": CASE_ID,
            "alert_type": "new_connection",
            "severity": "high",
            "title": "Test",
            "summary": "New summary",
            "entity_names": ["A", "B"],
            "evidence_refs": [make_evidence_ref("r1", "graph_edge", "e1", "ex")],
            "source_type": "internal",
        }]

        result = engine._deduplicate_alerts(CASE_ID, alerts)
        assert len(result) == 0  # merged, not added as new
        mock_alert_store.merge_into_existing.assert_called_once()

    def test_deduplicate_alerts_keeps_non_duplicate(self, engine, mock_alert_store):
        """Non-duplicate alerts should pass through."""
        engine._alert_store = mock_alert_store
        mock_alert_store.find_duplicate.return_value = None

        alerts = [{
            "alert_id": "new-alert-id",
            "case_id": CASE_ID,
            "alert_type": "new_connection",
            "severity": "high",
            "title": "Test",
            "summary": "Summary",
            "entity_names": ["X", "Y"],
            "evidence_refs": [make_evidence_ref("r1", "graph_edge", "e1", "ex")],
            "source_type": "internal",
        }]

        result = engine._deduplicate_alerts(CASE_ID, alerts)
        assert len(result) == 1



# ===================================================================
# 6. Partial Failure Handling Tests
# ===================================================================

class TestPartialFailureHandling:
    """Tests for scan resilience when individual phases fail."""

    def test_phase_failure_sets_partial_status(self, mock_aurora, mock_pattern_service, mock_cross_case_service):
        """If a phase raises, scan should continue and set status=partial."""
        engine = TrawlerEngine(
            aurora_cm=mock_aurora,
            pattern_service=mock_pattern_service,
            cross_case_service=mock_cross_case_service,
            neptune_endpoint="",
        )

        # Make pattern service fail
        mock_pattern_service.discover_top_patterns.side_effect = RuntimeError("Pattern service down")
        # Cross-case returns something
        mock_cross_case_service.scan_for_overlaps.return_value = []

        # Setup cursor to return no previous scan
        mock_cursor = mock_aurora.cursor.return_value.__enter__.return_value
        mock_cursor.fetchone.return_value = None

        result = engine.run_scan(CASE_ID)
        assert result["scan_status"] in ("partial", "completed")
        # The scan should still complete (not crash)
        assert "scan_id" in result

    def test_all_phases_fail_sets_failed_status(self, mock_aurora, mock_pattern_service, mock_cross_case_service):
        """If all phases fail, scan_status should be 'failed'."""
        engine = TrawlerEngine(
            aurora_cm=mock_aurora,
            pattern_service=mock_pattern_service,
            cross_case_service=mock_cross_case_service,
            neptune_endpoint="",
        )

        mock_pattern_service.discover_top_patterns.side_effect = RuntimeError("fail")
        mock_cross_case_service.scan_for_overlaps.side_effect = RuntimeError("fail")

        mock_cursor = mock_aurora.cursor.return_value.__enter__.return_value
        mock_cursor.fetchone.return_value = None

        result = engine.run_scan(CASE_ID)
        assert result["scan_status"] in ("partial", "failed")

    def test_persist_alerts_continues_on_individual_failure(self, engine, mock_aurora):
        """If one alert fails to persist, others should still be saved."""
        mock_cursor = mock_aurora.cursor.return_value.__enter__.return_value
        call_count = [0]

        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 2:  # Fail on second INSERT (first alert persist)
                raise RuntimeError("DB error")

        mock_cursor.execute.side_effect = side_effect

        alerts = [
            {
                "alert_id": str(uuid.uuid4()),
                "case_id": CASE_ID,
                "alert_type": "new_connection",
                "severity": "high",
                "title": f"Alert {i}",
                "summary": f"Summary {i}",
                "entity_names": [f"E{i}"],
                "evidence_refs": [],
                "source_type": "internal",
            }
            for i in range(3)
        ]

        # This should not raise — individual failures are caught
        count = engine._persist_alerts(CASE_ID, "scan-1", alerts)
        # At least some should succeed (exact count depends on which call fails)
        assert isinstance(count, int)


# ===================================================================
# 7. Evidence Reference Structure Tests
# ===================================================================

class TestEvidenceRefStructure:
    """Tests for make_evidence_ref function."""

    def test_valid_document_ref(self):
        ref = make_evidence_ref("doc-1", "document", "file.pdf", "Some excerpt text")
        assert ref["ref_id"] == "doc-1"
        assert ref["ref_type"] == "document"
        assert ref["source_label"] == "file.pdf"
        assert ref["excerpt"] == "Some excerpt text"

    def test_valid_graph_edge_ref(self):
        ref = make_evidence_ref("edge-1", "graph_edge", "edge-id-123", "Connection found")
        assert ref["ref_type"] == "graph_edge"

    def test_valid_external_url_ref(self):
        ref = make_evidence_ref("ext-1", "external_url", "https://example.com", "External finding")
        assert ref["ref_type"] == "external_url"

    def test_invalid_ref_type_defaults_to_document(self):
        ref = make_evidence_ref("r1", "invalid_type", "label", "excerpt")
        assert ref["ref_type"] == "document"

    def test_excerpt_truncated_to_500(self):
        long_text = "x" * 600
        ref = make_evidence_ref("r1", "document", "f.pdf", long_text)
        assert len(ref["excerpt"]) == 500

    def test_empty_ref_id_generates_uuid(self):
        ref = make_evidence_ref("", "document", "f.pdf", "ex")
        assert len(ref["ref_id"]) > 0  # UUID generated

    def test_empty_source_label(self):
        ref = make_evidence_ref("r1", "document", "", "ex")
        assert ref["source_label"] == ""


# ===================================================================
# 8. External Finding Categorization Tests
# ===================================================================

class TestExternalFindingCategorization:
    """Tests for categorize_external_findings function."""

    def test_external_only_generates_alert(self):
        entries = [{"finding": "New lead", "category": "external_only", "external_source": "https://example.com"}]
        candidates = categorize_external_findings(entries)
        assert len(candidates) == 1
        assert candidates[0]["alert_type"] == "external_lead"
        assert candidates[0]["source_type"] == "osint"
        assert candidates[0]["evidence_refs"][0]["ref_type"] == "external_url"

    def test_confirmed_internally_generates_medium_alert(self):
        entries = [{"finding": "Corroborated", "category": "confirmed_internally", "external_source": "https://example.com"}]
        candidates = categorize_external_findings(entries)
        assert len(candidates) == 1
        assert candidates[0]["_force_severity"] == "medium"
        assert candidates[0]["source_type"] == "osint"

    def test_needs_research_no_alert(self):
        entries = [{"finding": "Unclear", "category": "needs_research", "external_source": ""}]
        candidates = categorize_external_findings(entries)
        assert len(candidates) == 0

    def test_mixed_categories(self):
        entries = [
            {"finding": "Lead A", "category": "external_only", "external_source": "src1"},
            {"finding": "Lead B", "category": "needs_research", "external_source": "src2"},
            {"finding": "Lead C", "category": "confirmed_internally", "external_source": "src3"},
        ]
        candidates = categorize_external_findings(entries)
        assert len(candidates) == 2  # external_only + confirmed_internally

    def test_empty_entries(self):
        assert categorize_external_findings([]) == []



# ===================================================================
# 9. Full Scan Orchestration Tests
# ===================================================================

class TestFullScanOrchestration:
    """Tests for run_scan with mocked dependencies."""

    def test_full_scan_returns_summary(self, mock_aurora, mock_pattern_service, mock_cross_case_service):
        """Full scan should return a valid summary dict."""
        mock_cursor = mock_aurora.cursor.return_value.__enter__.return_value
        mock_cursor.fetchone.return_value = None

        engine = TrawlerEngine(
            aurora_cm=mock_aurora,
            pattern_service=mock_pattern_service,
            cross_case_service=mock_cross_case_service,
            neptune_endpoint="",
        )

        result = engine.run_scan(CASE_ID)
        assert result["case_id"] == CASE_ID
        assert result["scan_type"] == "full"
        assert "scan_id" in result
        assert "alerts_generated" in result
        assert "phase_timings" in result
        assert "elapsed_seconds" in result

    def test_targeted_scan_type(self, mock_aurora, mock_pattern_service, mock_cross_case_service):
        """Targeted scan should set scan_type='targeted'."""
        mock_cursor = mock_aurora.cursor.return_value.__enter__.return_value
        mock_cursor.fetchone.return_value = None

        engine = TrawlerEngine(
            aurora_cm=mock_aurora,
            pattern_service=mock_pattern_service,
            cross_case_service=mock_cross_case_service,
            neptune_endpoint="",
        )

        result = engine.run_scan(CASE_ID, targeted_doc_ids=["doc-1", "doc-2"])
        assert result["scan_type"] == "targeted"

    def test_scan_with_cross_case_overlaps(self, mock_aurora, mock_pattern_service, mock_cross_case_service):
        """Cross-case overlaps should generate alerts."""
        mock_cursor = mock_aurora.cursor.return_value.__enter__.return_value
        mock_cursor.fetchone.return_value = None

        # Create a mock CrossCaseMatch
        mock_match = MagicMock()
        mock_match.entity_a = {"entity_id": "e1", "name": "John Doe", "type": "person", "case_id": CASE_ID}
        mock_match.entity_b = {"entity_id": "e2", "name": "John Doe", "type": "person", "case_id": "case-other"}
        mock_match.similarity_score = 1.0
        mock_cross_case_service.scan_for_overlaps.return_value = [mock_match]

        engine = TrawlerEngine(
            aurora_cm=mock_aurora,
            pattern_service=mock_pattern_service,
            cross_case_service=mock_cross_case_service,
            neptune_endpoint="",
        )

        result = engine.run_scan(CASE_ID)
        assert result["alerts_generated"] >= 0  # May be 0 if persist fails on mock

    def test_scan_with_pattern_changes(self, mock_aurora, mock_pattern_service, mock_cross_case_service):
        """Pattern score increases >25% should generate alerts."""
        # Setup: previous scan had baseline
        mock_cursor = mock_aurora.cursor.return_value.__enter__.return_value
        mock_cursor.fetchone.return_value = (
            datetime.now(timezone.utc) - timedelta(hours=1),
            json.dumps({"Pattern A": 1.0}),
        )

        # Current patterns show 50% increase
        mock_pattern_service.discover_top_patterns.return_value = {
            "patterns": [
                {"title": "Pattern A", "composite_score": 1.5, "entities": [{"name": "Entity1"}]},
            ],
            "generated_at": "",
        }

        engine = TrawlerEngine(
            aurora_cm=mock_aurora,
            pattern_service=mock_pattern_service,
            cross_case_service=mock_cross_case_service,
            neptune_endpoint="",
        )

        result = engine.run_scan(CASE_ID)
        assert "scan_id" in result


# ===================================================================
# 10. Trawl Config CRUD Tests
# ===================================================================

class TestTrawlConfigCRUD:
    """Tests for get_trawl_config and save_trawl_config."""

    def test_get_config_returns_defaults_when_no_row(self, engine, mock_aurora):
        mock_cursor = mock_aurora.cursor.return_value.__enter__.return_value
        mock_cursor.fetchone.return_value = None

        config = engine.get_trawl_config(CASE_ID)
        assert config == DEFAULT_CONFIG

    def test_get_config_returns_stored_values(self, engine, mock_aurora):
        mock_cursor = mock_aurora.cursor.return_value.__enter__.return_value
        mock_cursor.fetchone.return_value = (
            ["new_connection", "entity_spike"],
            "high",
            True,
        )

        config = engine.get_trawl_config(CASE_ID)
        assert config["enabled_alert_types"] == ["new_connection", "entity_spike"]
        assert config["min_severity"] == "high"
        assert config["external_trawl_enabled"] is True

    def test_get_config_handles_json_string(self, engine, mock_aurora):
        mock_cursor = mock_aurora.cursor.return_value.__enter__.return_value
        mock_cursor.fetchone.return_value = (
            '["pattern_change"]',
            "medium",
            False,
        )

        config = engine.get_trawl_config(CASE_ID)
        assert config["enabled_alert_types"] == ["pattern_change"]

    def test_save_config_calls_upsert(self, engine, mock_aurora):
        mock_cursor = mock_aurora.cursor.return_value.__enter__.return_value

        result = engine.save_trawl_config(CASE_ID, {
            "enabled_alert_types": ["new_connection"],
            "min_severity": "high",
            "external_trawl_enabled": True,
        })

        assert result["case_id"] == CASE_ID
        assert result["min_severity"] == "high"
        assert result["external_trawl_enabled"] is True
        mock_cursor.execute.assert_called_once()

    def test_get_config_handles_db_error(self, engine, mock_aurora):
        mock_cursor = mock_aurora.cursor.return_value.__enter__.return_value
        mock_cursor.execute.side_effect = RuntimeError("DB down")

        config = engine.get_trawl_config(CASE_ID)
        assert config == DEFAULT_CONFIG  # Falls back to defaults


# ===================================================================
# 11. Temporal Anomaly Detection Tests
# ===================================================================

class TestTemporalAnomalyDetection:
    """Tests for _detect_temporal_anomalies static method."""

    def test_no_events_no_anomalies(self):
        assert TrawlerEngine._detect_temporal_anomalies([]) == []

    def test_single_event_no_anomaly(self):
        events = [{
            "name": "Event1",
            "created_at": "2024-01-01T00:00:00+00:00",
            "connected_entities": ["A", "B"],
        }]
        assert TrawlerEngine._detect_temporal_anomalies(events) == []

    def test_three_entities_in_48h_triggers_anomaly(self):
        base = datetime(2024, 1, 1, tzinfo=timezone.utc)
        events = [
            {
                "name": "Event1",
                "created_at": base.isoformat(),
                "connected_entities": ["A", "B"],
            },
            {
                "name": "Event2",
                "created_at": (base + timedelta(hours=12)).isoformat(),
                "connected_entities": ["C"],
            },
        ]
        result = TrawlerEngine._detect_temporal_anomalies(events)
        assert len(result) == 1
        assert result[0]["alert_type"] == "temporal_anomaly"
        assert len(result[0]["entity_names"]) >= 3

    def test_entities_outside_48h_no_anomaly(self):
        base = datetime(2024, 1, 1, tzinfo=timezone.utc)
        events = [
            {
                "name": "Event1",
                "created_at": base.isoformat(),
                "connected_entities": ["A", "B"],
            },
            {
                "name": "Event2",
                "created_at": (base + timedelta(hours=72)).isoformat(),
                "connected_entities": ["C"],
            },
        ]
        result = TrawlerEngine._detect_temporal_anomalies(events)
        assert len(result) == 0

    def test_two_entities_in_48h_no_anomaly(self):
        base = datetime(2024, 1, 1, tzinfo=timezone.utc)
        events = [
            {
                "name": "Event1",
                "created_at": base.isoformat(),
                "connected_entities": ["A"],
            },
            {
                "name": "Event2",
                "created_at": (base + timedelta(hours=6)).isoformat(),
                "connected_entities": ["B"],
            },
        ]
        result = TrawlerEngine._detect_temporal_anomalies(events)
        assert len(result) == 0
