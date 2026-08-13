#!/usr/bin/env python3
"""
Executive Succession Planning — Compensation & Risk HTTP API Server

Exposes all succession analytics engines (compensation, risk, readiness, process)
via a JSON HTTP API on port 8090 with full CORS support.

Usage:
    python scripts/succession_comp_risk_server.py

Endpoints:
    POST /analyze-all         — Full candidate analysis pipeline
    POST /comp/estimate       — Single candidate comp estimate
    POST /comp/market-range   — Market range for a role
    POST /comp/gap            — Comp gap calculation
    POST /risk/flight         — Flight risk for one candidate
    POST /risk/poachability   — Poachability for one candidate
    POST /risk/cultural       — Cultural risk between two countries
    POST /risk/compliance     — Compliance check
    POST /risk/notice         — Notice period estimate
    POST /readiness/gap       — Gap heatmap for one candidate
    POST /readiness/ttr       — Time-to-readiness
    POST /readiness/cost      — Development cost + ROI
    POST /process/advance     — Advance a candidate's stage
    GET  /process/timeline    — Get stage timeline
"""

import json
import logging
import os
import sys
from dataclasses import asdict
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from succession.compensation_engine import CompensationEngine
from succession.risk_analyzer import RiskAnalyzer
from succession.readiness_analyzer import ReadinessAnalyzer
from succession.process_tracker import ProcessTracker

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


# =============================================================================
# HOFSTEDE PROFILES — Cultural dimension scores by country
# =============================================================================
HOFSTEDE_PROFILES = {
    "US": {"power_distance": 40, "individualism": 91, "masculinity": 62, "uncertainty_avoidance": 46, "long_term_orientation": 26, "indulgence": 68},
    "GB": {"power_distance": 35, "individualism": 89, "masculinity": 66, "uncertainty_avoidance": 35, "long_term_orientation": 51, "indulgence": 69},
    "IR": {"power_distance": 58, "individualism": 41, "masculinity": 43, "uncertainty_avoidance": 59, "long_term_orientation": 14, "indulgence": 40},
    "AE": {"power_distance": 90, "individualism": 25, "masculinity": 50, "uncertainty_avoidance": 80, "long_term_orientation": 23, "indulgence": 26},
    "SA": {"power_distance": 95, "individualism": 25, "masculinity": 60, "uncertainty_avoidance": 80, "long_term_orientation": 36, "indulgence": 52},
    "SG": {"power_distance": 74, "individualism": 20, "masculinity": 48, "uncertainty_avoidance": 8, "long_term_orientation": 72, "indulgence": 46},
    "CN": {"power_distance": 80, "individualism": 20, "masculinity": 66, "uncertainty_avoidance": 30, "long_term_orientation": 87, "indulgence": 24},
    "DE": {"power_distance": 35, "individualism": 67, "masculinity": 66, "uncertainty_avoidance": 65, "long_term_orientation": 83, "indulgence": 40},
    "BR": {"power_distance": 69, "individualism": 38, "masculinity": 49, "uncertainty_avoidance": 76, "long_term_orientation": 44, "indulgence": 59},
    "FR": {"power_distance": 68, "individualism": 71, "masculinity": 43, "uncertainty_avoidance": 86, "long_term_orientation": 63, "indulgence": 48},
    "JP": {"power_distance": 54, "individualism": 46, "masculinity": 95, "uncertainty_avoidance": 92, "long_term_orientation": 88, "indulgence": 42},
    "IN": {"power_distance": 77, "individualism": 48, "masculinity": 56, "uncertainty_avoidance": 40, "long_term_orientation": 51, "indulgence": 26},
}


# =============================================================================
# NOTICE PERIODS — Months by country and seniority
# =============================================================================
NOTICE_PERIODS = {
    "US": {"VP": 0, "C_SUITE": 0, "DIRECTOR": 0},
    "GB": {"VP": 6, "C_SUITE": 12, "DIRECTOR": 3},
    "IR": {"VP": 3, "C_SUITE": 6, "DIRECTOR": 2},
    "AE": {"VP": 3, "C_SUITE": 6, "DIRECTOR": 2},
    "SA": {"VP": 3, "C_SUITE": 6, "DIRECTOR": 2},
    "SG": {"VP": 3, "C_SUITE": 6, "DIRECTOR": 2},
    "CN": {"VP": 1, "C_SUITE": 3, "DIRECTOR": 1},
    "JP": {"VP": 3, "C_SUITE": 6, "DIRECTOR": 2},
    "DE": {"VP": 6, "C_SUITE": 12, "DIRECTOR": 3},
    "FR": {"VP": 3, "C_SUITE": 6, "DIRECTOR": 3},
    "BR": {"VP": 1, "C_SUITE": 3, "DIRECTOR": 1},
    "IN": {"VP": 3, "C_SUITE": 6, "DIRECTOR": 2},
}

# =============================================================================
# NON-COMPETE ENFORCEABILITY — By country
# =============================================================================
NON_COMPETE_ENFORCEABILITY = {
    "US": "limited",
    "GB": "enforceable",
    "IR": "limited",
    "AE": "enforceable",
    "SA": "enforceable",
    "SG": "enforceable",
    "CN": "enforceable",
    "JP": "limited",
    "DE": "enforceable",
    "FR": "enforceable",
    "BR": "limited",
    "IN": "limited",
}


# =============================================================================
# COMP_LOOKUP — Primary compensation benchmarks (PRIVATE sector, key countries)
# =============================================================================
COMP_LOOKUP = {
    "PRIVATE_US_VP": {
        "base": {"p25": 280000, "p50": 360000, "p75": 450000},
        "bonus_pct": {"p25": 30, "p50": 50, "p75": 80},
        "equity": {"p25": 300000, "p50": 650000, "p75": 1200000},
        "benefits": 45000,
        "allowances": {},
        "total": {"p25": 689000, "p50": 1175000, "p75": 2005000},
    },
    "PRIVATE_US_C_SUITE": {
        "base": {"p25": 400000, "p50": 550000, "p75": 700000},
        "bonus_pct": {"p25": 50, "p50": 100, "p75": 150},
        "equity": {"p25": 1000000, "p50": 2500000, "p75": 5000000},
        "benefits": 65000,
        "allowances": {},
        "total": {"p25": 1665000, "p50": 3665000, "p75": 6815000},
    },
    "PRIVATE_US_DIRECTOR": {
        "base": {"p25": 180000, "p50": 230000, "p75": 300000},
        "bonus_pct": {"p25": 20, "p50": 35, "p75": 55},
        "equity": {"p25": 100000, "p50": 250000, "p75": 500000},
        "benefits": 38000,
        "allowances": {},
        "total": {"p25": 354000, "p50": 600500, "p75": 1003000},
    },
    "PRIVATE_IR_VP": {
        "base": {"p25": 180000, "p50": 260000, "p75": 350000},
        "bonus_pct": {"p25": 20, "p50": 35, "p75": 50},
        "equity": {"p25": 0, "p50": 25000, "p75": 80000},
        "benefits": 30000,
        "allowances": {"hardship": 45000, "housing": 65000, "schooling": 35000, "security": 25000},
        "total": {"p25": 416000, "p50": 576000, "p75": 780000},
    },
    "PRIVATE_IR_C_SUITE": {
        "base": {"p25": 280000, "p50": 380000, "p75": 500000},
        "bonus_pct": {"p25": 30, "p50": 50, "p75": 80},
        "equity": {"p25": 0, "p50": 50000, "p75": 150000},
        "benefits": 45000,
        "allowances": {"hardship": 65000, "housing": 90000, "schooling": 50000, "security": 40000},
        "total": {"p25": 589000, "p50": 865000, "p75": 1275000},
    },
    "PRIVATE_IR_DIRECTOR": {
        "base": {"p25": 120000, "p50": 175000, "p75": 240000},
        "bonus_pct": {"p25": 15, "p50": 25, "p75": 40},
        "equity": {"p25": 0, "p50": 10000, "p75": 40000},
        "benefits": 22000,
        "allowances": {"hardship": 35000, "housing": 50000, "schooling": 28000, "security": 18000},
        "total": {"p25": 283000, "p50": 398750, "p75": 554000},
    },
    "PRIVATE_AE_VP": {
        "base": {"p25": 250000, "p50": 330000, "p75": 400000},
        "bonus_pct": {"p25": 30, "p50": 45, "p75": 60},
        "equity": {"p25": 50000, "p50": 150000, "p75": 350000},
        "benefits": 35000,
        "allowances": {"hardship": 15000, "housing": 65000, "schooling": 40000, "security": 10000},
        "total": {"p25": 540000, "p50": 783500, "p75": 1040000},
    },
    "PRIVATE_AE_C_SUITE": {
        "base": {"p25": 380000, "p50": 500000, "p75": 650000},
        "bonus_pct": {"p25": 40, "p50": 70, "p75": 100},
        "equity": {"p25": 200000, "p50": 500000, "p75": 1200000},
        "benefits": 50000,
        "allowances": {"hardship": 20000, "housing": 95000, "schooling": 55000, "security": 15000},
        "total": {"p25": 877000, "p50": 1565000, "p75": 2665000},
    },
    "PRIVATE_AE_DIRECTOR": {
        "base": {"p25": 160000, "p50": 220000, "p75": 290000},
        "bonus_pct": {"p25": 20, "p50": 35, "p75": 50},
        "equity": {"p25": 20000, "p50": 80000, "p75": 180000},
        "benefits": 28000,
        "allowances": {"hardship": 10000, "housing": 50000, "schooling": 32000, "security": 8000},
        "total": {"p25": 320000, "p50": 497000, "p75": 733000},
    },
    "PRIVATE_GB_VP": {
        "base": {"p25": 220000, "p50": 290000, "p75": 370000},
        "bonus_pct": {"p25": 25, "p50": 45, "p75": 70},
        "equity": {"p25": 150000, "p50": 350000, "p75": 700000},
        "benefits": 40000,
        "allowances": {},
        "total": {"p25": 465000, "p50": 810500, "p75": 1329000},
    },
    "PRIVATE_GB_C_SUITE": {
        "base": {"p25": 350000, "p50": 480000, "p75": 620000},
        "bonus_pct": {"p25": 40, "p50": 80, "p75": 130},
        "equity": {"p25": 600000, "p50": 1500000, "p75": 3500000},
        "benefits": 55000,
        "allowances": {},
        "total": {"p25": 1145000, "p50": 2439000, "p75": 4961000},
    },
    "PRIVATE_GB_DIRECTOR": {
        "base": {"p25": 150000, "p50": 195000, "p75": 260000},
        "bonus_pct": {"p25": 18, "p50": 30, "p75": 50},
        "equity": {"p25": 60000, "p50": 150000, "p75": 350000},
        "benefits": 32000,
        "allowances": {},
        "total": {"p25": 269000, "p50": 435500, "p75": 772000},
    },
    "PRIVATE_SG_VP": {
        "base": {"p25": 230000, "p50": 310000, "p75": 400000},
        "bonus_pct": {"p25": 25, "p50": 40, "p75": 60},
        "equity": {"p25": 100000, "p50": 280000, "p75": 600000},
        "benefits": 32000,
        "allowances": {},
        "total": {"p25": 419500, "p50": 746000, "p75": 1272000},
    },
    "PRIVATE_SG_C_SUITE": {
        "base": {"p25": 370000, "p50": 490000, "p75": 630000},
        "bonus_pct": {"p25": 40, "p50": 70, "p75": 110},
        "equity": {"p25": 400000, "p50": 1000000, "p75": 2500000},
        "benefits": 48000,
        "allowances": {},
        "total": {"p25": 966000, "p50": 1881000, "p75": 3841000},
    },
    "PRIVATE_SG_DIRECTOR": {
        "base": {"p25": 150000, "p50": 200000, "p75": 270000},
        "bonus_pct": {"p25": 18, "p50": 30, "p75": 45},
        "equity": {"p25": 40000, "p50": 120000, "p75": 280000},
        "benefits": 26000,
        "allowances": {},
        "total": {"p25": 243000, "p50": 406000, "p75": 697500},
    },
    "PRIVATE_DE_VP": {
        "base": {"p25": 215000, "p50": 285000, "p75": 375000},
        "bonus_pct": {"p25": 20, "p50": 35, "p75": 50},
        "equity": {"p25": 50000, "p50": 150000, "p75": 350000},
        "benefits": 38000,
        "allowances": {},
        "total": {"p25": 346000, "p50": 572750, "p75": 950500},
    },
    "PRIVATE_DE_C_SUITE": {
        "base": {"p25": 340000, "p50": 460000, "p75": 600000},
        "bonus_pct": {"p25": 30, "p50": 55, "p75": 80},
        "equity": {"p25": 200000, "p50": 550000, "p75": 1400000},
        "benefits": 52000,
        "allowances": {},
        "total": {"p25": 694000, "p50": 1315000, "p75": 2532000},
    },
    "PRIVATE_DE_DIRECTOR": {
        "base": {"p25": 140000, "p50": 190000, "p75": 260000},
        "bonus_pct": {"p25": 15, "p50": 25, "p75": 38},
        "equity": {"p25": 20000, "p50": 70000, "p75": 180000},
        "benefits": 32000,
        "allowances": {},
        "total": {"p25": 213000, "p50": 339500, "p75": 570800},
    },
    "GOVERNMENT_US_VP": {
        "base": {"p25": 160000, "p50": 195000, "p75": 225000},
        "bonus_pct": {"p25": 5, "p50": 10, "p75": 15},
        "equity": {"p25": 0, "p50": 0, "p75": 0},
        "benefits": 55000,
        "allowances": {},
        "total": {"p25": 223000, "p50": 269500, "p75": 313750},
    },
    "GOVERNMENT_US_C_SUITE": {
        "base": {"p25": 195000, "p50": 240000, "p75": 285000},
        "bonus_pct": {"p25": 8, "p50": 15, "p75": 22},
        "equity": {"p25": 0, "p50": 0, "p75": 0},
        "benefits": 65000,
        "allowances": {},
        "total": {"p25": 275600, "p50": 341000, "p75": 412700},
    },
    "GOVERNMENT_US_DIRECTOR": {
        "base": {"p25": 130000, "p50": 160000, "p75": 190000},
        "bonus_pct": {"p25": 3, "p50": 8, "p75": 12},
        "equity": {"p25": 0, "p50": 0, "p75": 0},
        "benefits": 48000,
        "allowances": {},
        "total": {"p25": 181900, "p50": 220800, "p75": 260800},
    },
}


# =============================================================================
# Engine Instances
# =============================================================================
comp_engine = CompensationEngine()
risk_analyzer = RiskAnalyzer()
readiness_analyzer = ReadinessAnalyzer()
process_tracker = ProcessTracker()


# =============================================================================
# Helper — serialize dataclass results to JSON-safe dicts
# =============================================================================
def _serialize(obj):
    """Convert dataclass or list of dataclasses to JSON-safe dict/list."""
    if hasattr(obj, "__dataclass_fields__"):
        return asdict(obj)
    if isinstance(obj, list):
        return [_serialize(item) for item in obj]
    return obj


# =============================================================================
# HTTP Handler
# =============================================================================
class SuccessionAPIHandler(BaseHTTPRequestHandler):
    """HTTP request handler for succession planning API."""

    def _set_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def _send_json(self, data, status=200):
        body = json.dumps(data, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self._set_cors_headers()
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, message, status=400):
        self._send_json({"error": message}, status=status)

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        return json.loads(raw)

    # ----- OPTIONS (CORS Preflight) -----
    def do_OPTIONS(self):
        self.send_response(204)
        self._set_cors_headers()
        self.end_headers()

    # ----- GET -----
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        if path == "/process/timeline":
            txn_id = params.get("txn_id", [None])[0]
            timeline = process_tracker.get_timeline(transaction_id=txn_id)
            self._send_json([_serialize(t) for t in timeline])
        elif path == "/health":
            self._send_json({"status": "ok", "service": "succession-comp-risk-api"})
        else:
            self._send_error("Not found", 404)

    # ----- POST -----
    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        try:
            body = self._read_body()
        except Exception as e:
            self._send_error(f"Invalid JSON: {e}")
            return

        try:
            if path == "/analyze-all":
                self._handle_analyze_all(body)
            elif path == "/comp/estimate":
                self._handle_comp_estimate(body)
            elif path == "/comp/market-range":
                self._handle_market_range(body)
            elif path == "/comp/gap":
                self._handle_comp_gap(body)
            elif path == "/risk/flight":
                self._handle_flight_risk(body)
            elif path == "/risk/poachability":
                self._handle_poachability(body)
            elif path == "/risk/cultural":
                self._handle_cultural_risk(body)
            elif path == "/risk/compliance":
                self._handle_compliance_risk(body)
            elif path == "/risk/notice":
                self._handle_notice_period(body)
            elif path == "/readiness/gap":
                self._handle_readiness_gap(body)
            elif path == "/readiness/ttr":
                self._handle_ttr(body)
            elif path == "/readiness/cost":
                self._handle_dev_cost(body)
            elif path == "/process/advance":
                self._handle_advance_stage(body)
            else:
                self._send_error("Not found", 404)
        except Exception as e:
            logger.exception("Handler error")
            self._send_error(str(e), 500)

    # =========================================================================
    # /analyze-all — Full pipeline for multiple candidates
    # =========================================================================
    def _handle_analyze_all(self, body):
        candidates = body.get("candidates", [])
        target_role = body.get("target_role", {})
        transaction_id = body.get("transaction_id", "txn-unknown")

        results = []
        for cand in candidates:
            result = self._analyze_single_candidate(cand, target_role, transaction_id)
            results.append(result)

        self._send_json({"results": results, "transaction_id": transaction_id})

    def _analyze_single_candidate(self, cand, target_role, transaction_id="txn-unknown"):
        """Run full analysis pipeline on a single candidate."""
        candidate_id = cand.get("id", cand.get("name", "unknown"))

        # Candidate comp profile for lookup
        cand_profile = {
            "sector": cand.get("sector", target_role.get("sector", "PRIVATE")),
            "country": cand.get("country", "US"),
            "seniority": cand.get("seniority", "VP"),
        }

        # 1. Total compensation
        comp_est = comp_engine.compute_total_comp(cand_profile, COMP_LOOKUP)

        # 2. Market range for target role
        market_range = comp_engine.compute_market_range(target_role, COMP_LOOKUP)

        # 3. Comp gap
        comp_gap = comp_engine.compute_comp_gap(comp_est.total, market_range.p50)

        # 4. Flight risk
        flight_risk = risk_analyzer.compute_flight_risk(cand)

        # 5. Poachability
        poachability = risk_analyzer.compute_poachability(cand, comp_gap.percentage)

        # 6. Cultural risk
        origin_country = cand.get("country", "US")
        target_country = target_role.get("country", "US")
        cultural_risk = risk_analyzer.compute_cultural_risk(
            origin_country, target_country, HOFSTEDE_PROFILES
        )

        # 7. Compliance risk
        signals = cand.get("compliance_signals", [])
        compliance_risk = risk_analyzer.compute_compliance_risk(cand, signals)

        # 8. Notice period
        notice = risk_analyzer.estimate_notice_period(
            origin_country,
            cand_profile["seniority"],
            NOTICE_PERIODS,
            NON_COMPETE_ENFORCEABILITY,
        )

        # 9. Gap heatmap + fit percentage
        candidate_scores = cand.get("scores", {})
        role_requirements = cand.get("role_requirements", {})
        if not role_requirements:
            from succession.readiness_analyzer import CRITERIA_25
            role_requirements = {c: 7 for c in CRITERIA_25}

        gaps = readiness_analyzer.compute_gap_heatmap(candidate_scores, role_requirements)
        fit_pct = readiness_analyzer.compute_fit_percentage(gaps)

        # 10. Time-to-readiness
        ttr = readiness_analyzer.compute_time_to_readiness(gaps)

        # 11. Development cost
        dev_cost = readiness_analyzer.compute_development_cost(gaps, ttr.months)

        # 12. Process — advance to LONG_LIST for tracking
        try:
            current_stage = process_tracker.get_current_stage(candidate_id)
            process_info = _serialize(current_stage) if current_stage else {"stage": "NOT_STARTED"}
        except Exception:
            process_info = {"stage": "NOT_STARTED"}

        return {
            "candidate_id": candidate_id,
            "compensation": {
                "total_comp": _serialize(comp_est),
                "market_range": _serialize(market_range),
                "comp_gap": _serialize(comp_gap),
            },
            "risk": {
                "flight": _serialize(flight_risk),
                "poachability": _serialize(poachability),
                "cultural": _serialize(cultural_risk),
                "compliance": _serialize(compliance_risk),
                "notice_period": _serialize(notice),
            },
            "readiness": {
                "gap_heatmap": _serialize(gaps),
                "fit_percentage": fit_pct,
                "time_to_readiness": _serialize(ttr),
                "development_cost": dev_cost,
            },
            "process": process_info,
        }

    # =========================================================================
    # Individual Endpoints
    # =========================================================================

    def _handle_comp_estimate(self, body):
        candidate = body.get("candidate", body)
        result = comp_engine.compute_total_comp(candidate, COMP_LOOKUP)
        self._send_json(_serialize(result))

    def _handle_market_range(self, body):
        role = body.get("role", body)
        result = comp_engine.compute_market_range(role, COMP_LOOKUP)
        self._send_json(_serialize(result))

    def _handle_comp_gap(self, body):
        candidate_comp = body.get("candidate_comp", 0)
        role_p50 = body.get("role_p50", 0)
        result = comp_engine.compute_comp_gap(candidate_comp, role_p50)
        self._send_json(_serialize(result))

    def _handle_flight_risk(self, body):
        candidate = body.get("candidate", body)
        result = risk_analyzer.compute_flight_risk(candidate)
        self._send_json(_serialize(result))

    def _handle_poachability(self, body):
        candidate = body.get("candidate", body)
        comp_gap_pct = body.get("comp_gap_pct", 0)
        result = risk_analyzer.compute_poachability(candidate, comp_gap_pct)
        self._send_json(_serialize(result))

    def _handle_cultural_risk(self, body):
        origin = body.get("origin_country", "US")
        target = body.get("target_country", "US")
        result = risk_analyzer.compute_cultural_risk(origin, target, HOFSTEDE_PROFILES)
        self._send_json(_serialize(result))

    def _handle_compliance_risk(self, body):
        candidate = body.get("candidate", body)
        signals = body.get("signals", [])
        result = risk_analyzer.compute_compliance_risk(candidate, signals)
        self._send_json(_serialize(result))

    def _handle_notice_period(self, body):
        country = body.get("country", "US")
        seniority = body.get("seniority", "VP")
        result = risk_analyzer.estimate_notice_period(
            country, seniority, NOTICE_PERIODS, NON_COMPETE_ENFORCEABILITY
        )
        self._send_json(_serialize(result))

    def _handle_readiness_gap(self, body):
        candidate_scores = body.get("candidate_scores", {})
        role_requirements = body.get("role_requirements", {})
        if not role_requirements:
            from succession.readiness_analyzer import CRITERIA_25
            role_requirements = {c: 7 for c in CRITERIA_25}
        gaps = readiness_analyzer.compute_gap_heatmap(candidate_scores, role_requirements)
        fit_pct = readiness_analyzer.compute_fit_percentage(gaps)
        self._send_json({
            "gaps": _serialize(gaps),
            "fit_percentage": fit_pct,
        })

    def _handle_ttr(self, body):
        candidate_scores = body.get("candidate_scores", {})
        role_requirements = body.get("role_requirements", {})
        if not role_requirements:
            from succession.readiness_analyzer import CRITERIA_25
            role_requirements = {c: 7 for c in CRITERIA_25}
        gaps = readiness_analyzer.compute_gap_heatmap(candidate_scores, role_requirements)
        ttr = readiness_analyzer.compute_time_to_readiness(gaps)
        self._send_json(_serialize(ttr))

    def _handle_dev_cost(self, body):
        candidate_scores = body.get("candidate_scores", {})
        role_requirements = body.get("role_requirements", {})
        role_annual_value = body.get("role_annual_value", 2000000)
        acquisition_cost = body.get("acquisition_cost", 500000)
        if not role_requirements:
            from succession.readiness_analyzer import CRITERIA_25
            role_requirements = {c: 7 for c in CRITERIA_25}
        gaps = readiness_analyzer.compute_gap_heatmap(candidate_scores, role_requirements)
        ttr = readiness_analyzer.compute_time_to_readiness(gaps)
        dev_cost = readiness_analyzer.compute_development_cost(gaps, ttr.months)
        roi = readiness_analyzer.compute_roi(role_annual_value, acquisition_cost, dev_cost)
        self._send_json({
            "development_cost": dev_cost,
            "time_to_readiness": _serialize(ttr),
            "roi": _serialize(roi),
        })

    def _handle_advance_stage(self, body):
        candidate_id = body.get("candidate_id", "unknown")
        new_stage = body.get("stage", "LONG_LIST")
        user = body.get("user", "api")
        note = body.get("note", "")
        transition = process_tracker.advance_stage(candidate_id, new_stage, user, note)
        self._send_json(_serialize(transition))

    # Suppress default access log noise
    def log_message(self, format, *args):
        logger.info(f"{self.client_address[0]} - {format % args}")


# =============================================================================
# Main — Start Server
# =============================================================================
def main():
    port = 8090
    server = HTTPServer(("0.0.0.0", port), SuccessionAPIHandler)
    logger.info(f"Compensation & Risk API running on http://localhost:{port}")
    logger.info("Endpoints: /analyze-all, /comp/*, /risk/*, /readiness/*, /process/*")
    logger.info("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down.")
        server.shutdown()


if __name__ == "__main__":
    main()
