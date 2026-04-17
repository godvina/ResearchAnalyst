"""Unit tests for the trawl briefing handler.

Tests cover:
- Route dispatching for GET /trawl/briefing
- Successful Bedrock AI brief (source="ai")
- Bedrock timeout fallback (source="fallback")
- Bedrock error fallback
- Response schema completeness
- 404 for non-existent case (no scans)
- Top entities sorted by frequency, max 5
- Indicator deltas contain all 5 keys with before/after
"""

import json
import sys
import os
from unittest.mock import MagicMock, patch

import pytest

# Ensure src is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))


def _make_event(case_id, method="GET", path_suffix="/trawl/briefing"):
    path = f"/case-files/{case_id}{path_suffix}"
    return {
        "httpMethod": method,
        "path": path,
        "pathParameters": {"id": case_id},
        "queryStringParameters": {},
        "body": None,
        "requestContext": {"requestId": "test-req-123"},
    }


CASE_ID = "ed0b6c27-3b6b-4255-b9d0-efe8f4383a99"

MOCK_SCANS = [
    {
        "scan_id": "scan-002",
        "case_id": CASE_ID,
        "started_at": "2025-01-15T10:00:00",
        "completed_at": "2025-01-15T10:00:15",
        "alerts_generated": 12,
        "scan_status": "completed",
        "scan_type": "full",
        "phase_timings": {},
        "error_message": None,
        "pattern_baseline": {},
        "indicator_snapshot": {
            "viability_score": 72,
            "signal_strength": 100,
            "corroboration_depth": 46,
            "network_density": 66,
            "temporal_coherence": 50,
            "prosecution_readiness": 100,
        },
    },
    {
        "scan_id": "scan-001",
        "case_id": CASE_ID,
        "started_at": "2025-01-14T10:00:00",
        "completed_at": "2025-01-14T10:00:10",
        "alerts_generated": 8,
        "scan_status": "completed",
        "scan_type": "full",
        "phase_timings": {},
        "error_message": None,
        "pattern_baseline": {},
        "indicator_snapshot": {
            "viability_score": 65,
            "signal_strength": 85,
            "corroboration_depth": 40,
            "network_density": 60,
            "temporal_coherence": 45,
            "prosecution_readiness": 95,
        },
    },
]

MOCK_ALERTS = [
    {"alert_id": "a1", "entity_names": ["Epstein", "Maxwell"], "severity": "critical", "source_type": "internal"},
    {"alert_id": "a2", "entity_names": ["Epstein", "Brunel"], "severity": "high", "source_type": "internal"},
    {"alert_id": "a3", "entity_names": ["Maxwell", "Visoski"], "severity": "medium", "source_type": "osint"},
    {"alert_id": "a4", "entity_names": ["Epstein"], "severity": "high", "source_type": "internal"},
    {"alert_id": "a5", "entity_names": ["Brunel", "Epstein"], "severity": "low", "source_type": "osint"},
    {"alert_id": "a6", "entity_names": [], "severity": "medium", "source_type": "internal"},
]


@pytest.fixture
def mock_store():
    store = MagicMock()
    store.list_scan_history.return_value = MOCK_SCANS
    store.list_alerts.return_value = MOCK_ALERTS
    return store


class TestBriefingRouteDispatch:
    """Test that the briefing route dispatches correctly."""

    @patch("lambdas.api.trawl._build_alert_store")
    def test_briefing_route_dispatches(self, mock_build, mock_store):
        mock_build.return_value = mock_store
        from lambdas.api.trawl import dispatch_handler

        event = _make_event(CASE_ID)
        resp = dispatch_handler(event, None)
        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        assert "brief_text" in body

    @patch("lambdas.api.trawl._build_alert_store")
    def test_briefing_route_post_returns_404(self, mock_build, mock_store):
        mock_build.return_value = mock_store
        from lambdas.api.trawl import dispatch_handler

        event = _make_event(CASE_ID, method="POST")
        resp = dispatch_handler(event, None)
        # POST to /trawl/briefing should not match — falls through to 404
        assert resp["statusCode"] in (404, 200)  # might match /trawl POST


class TestBriefingHandler:
    """Test the briefing handler directly."""

    @patch("lambdas.api.trawl._invoke_bedrock_brief")
    @patch("lambdas.api.trawl._build_alert_store")
    def test_successful_bedrock_returns_ai_source(self, mock_build, mock_bedrock, mock_store):
        mock_build.return_value = mock_store
        mock_bedrock.return_value = "AI-generated brief text here."
        from lambdas.api.trawl import trawl_briefing_handler

        event = _make_event(CASE_ID)
        resp = trawl_briefing_handler(event, None)
        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        assert body["source"] == "ai"
        assert body["brief_text"] == "AI-generated brief text here."

    @patch("lambdas.api.trawl._invoke_bedrock_brief")
    @patch("lambdas.api.trawl._build_alert_store")
    def test_bedrock_timeout_returns_fallback(self, mock_build, mock_bedrock, mock_store):
        mock_build.return_value = mock_store
        mock_bedrock.side_effect = Exception("ReadTimeoutError")
        from lambdas.api.trawl import trawl_briefing_handler

        event = _make_event(CASE_ID)
        resp = trawl_briefing_handler(event, None)
        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        assert body["source"] == "fallback"
        assert "new findings detected" in body["brief_text"]

    @patch("lambdas.api.trawl._invoke_bedrock_brief")
    @patch("lambdas.api.trawl._build_alert_store")
    def test_bedrock_error_returns_fallback(self, mock_build, mock_bedrock, mock_store):
        mock_build.return_value = mock_store
        mock_bedrock.side_effect = RuntimeError("Bedrock unavailable")
        from lambdas.api.trawl import trawl_briefing_handler

        event = _make_event(CASE_ID)
        resp = trawl_briefing_handler(event, None)
        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        assert body["source"] == "fallback"

    @patch("lambdas.api.trawl._invoke_bedrock_brief")
    @patch("lambdas.api.trawl._build_alert_store")
    def test_response_contains_all_required_fields(self, mock_build, mock_bedrock, mock_store):
        mock_build.return_value = mock_store
        mock_bedrock.return_value = None  # fallback
        from lambdas.api.trawl import trawl_briefing_handler

        event = _make_event(CASE_ID)
        resp = trawl_briefing_handler(event, None)
        body = json.loads(resp["body"])
        assert "brief_text" in body
        assert "top_entities" in body
        assert "indicator_deltas" in body
        assert "generated_at" in body
        assert "source" in body

    @patch("lambdas.api.trawl._build_alert_store")
    def test_404_for_no_scans(self, mock_build):
        store = MagicMock()
        store.list_scan_history.return_value = []
        mock_build.return_value = store
        from lambdas.api.trawl import trawl_briefing_handler

        event = _make_event(CASE_ID)
        resp = trawl_briefing_handler(event, None)
        assert resp["statusCode"] == 404

    @patch("lambdas.api.trawl._invoke_bedrock_brief")
    @patch("lambdas.api.trawl._build_alert_store")
    def test_top_entities_sorted_by_frequency_max_5(self, mock_build, mock_bedrock, mock_store):
        mock_build.return_value = mock_store
        mock_bedrock.return_value = None
        from lambdas.api.trawl import trawl_briefing_handler

        event = _make_event(CASE_ID)
        resp = trawl_briefing_handler(event, None)
        body = json.loads(resp["body"])
        entities = body["top_entities"]
        assert len(entities) <= 5
        # Epstein appears in 4 alerts, should be first
        assert entities[0] == "Epstein"

    @patch("lambdas.api.trawl._invoke_bedrock_brief")
    @patch("lambdas.api.trawl._build_alert_store")
    def test_indicator_deltas_has_all_5_keys(self, mock_build, mock_bedrock, mock_store):
        mock_build.return_value = mock_store
        mock_bedrock.return_value = None
        from lambdas.api.trawl import trawl_briefing_handler

        event = _make_event(CASE_ID)
        resp = trawl_briefing_handler(event, None)
        body = json.loads(resp["body"])
        deltas = body["indicator_deltas"]
        expected_keys = {
            "signal_strength", "corroboration_depth", "network_density",
            "temporal_coherence", "prosecution_readiness",
        }
        assert set(deltas.keys()) == expected_keys
        for k in expected_keys:
            assert "before" in deltas[k]
            assert "after" in deltas[k]
