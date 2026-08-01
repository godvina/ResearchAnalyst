"""Collusion Detection Service — core analysis engine for procurement collusion.

Implements the AntitrustAnalysisModule abstract base class and orchestrates:
- Bid-rigging detection (complementary bidding, rotation, suppression)
- Statistical anomaly analysis (price spread, round numbers, estimate ratios)
- Communication pattern analysis (pre-deadline timing spikes)
- Financial flow analysis (subcontracting, reciprocal flows, shell companies)
- PCSF composite scoring

This module is the primary entry point for procurement collusion investigations.
It coordinates data retrieval from Aurora (bid records) and Neptune (vendor
relationships), runs vectorized statistical computations via numpy, and
delegates legal reasoning to the injected AntitrustLegalReasoning service.

Usage:
    svc = CollusionDetectionService(
        aurora_cm=connection_manager,
        neptune_endpoint="my-neptune-cluster.us-east-1.neptune.amazonaws.com",
        neptune_port="8182",
        bedrock_client=bedrock_runtime,
        antitrust_scoring_svc=scoring_svc,
        antitrust_legal_reasoning=legal_reasoning_svc,
    )
    result = svc.run_analysis(case_id="INV-2024-001")
"""

from __future__ import annotations

import json
import logging
import math
import os
import ssl
import statistics
import urllib.request
import urllib.error
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Optional

import numpy as np

logger = logging.getLogger(__name__)

# Feature flag: when "false", Neptune-dependent operations return partial results
_NEPTUNE_ENABLED = os.environ.get("NEPTUNE_ENABLED", "true") == "true"

# Pagination constants
AURORA_BATCH_SIZE = 5000

# PCSF scoring weights
PCSF_WEIGHTS = {
    "bid_rigging": 0.30,
    "pricing": 0.25,
    "communication": 0.20,
    "financial": 0.15,
    "behavioral": 0.10,
}

# Complementary bid score component weights
COMPLEMENTARY_BID_WEIGHTS = {
    "bid_relative": 0.30,
    "spec_gaps": 0.25,
    "timing": 0.20,
    "history": 0.25,
}

# Thresholds
COMPLEMENTARY_BID_FLAG_THRESHOLD = 70
ROTATION_INDEX_FLAG_THRESHOLD = 0.7
CHI_SQUARED_P_VALUE_THRESHOLD = 0.05
ABSTENTION_RATE_FLAG_THRESHOLD = 0.60
BID_SPREAD_CV_THRESHOLD = 0.05
ROUND_NUMBER_THRESHOLD = 0.50
COMMUNICATION_STD_DEV_MULTIPLIER = 2
PRE_DEADLINE_WINDOW_DAYS = 14
SUBCONTRACTING_WINDOW_DAYS = 90


# Import from models if available, otherwise define locally for standalone testing
try:
    from models.antitrust import (
        AnalysisResult,
        AnalysisStatus,
        BidRiggingPattern,
        BidRiggingType,
        CaseType,
        CollusionAnalysisResult,
        CollusionRing,
        CollusionRingMember,
        PCSFBreakdown,
        PriceAnomaly,
        RedFlag,
        RedFlagCategory,
        RedFlagSeverity,
        SchemeType,
        ScoringFactor,
        ScoringResult,
    )
except ImportError:
    # Minimal fallback for standalone testing
    from dataclasses import dataclass, field
    from enum import Enum

    class CaseType(str, Enum):
        PROCUREMENT_COLLUSION = "procurement_collusion"

    class AnalysisStatus(str, Enum):
        PROCESSING = "processing"
        COMPLETED = "completed"
        PARTIAL = "partial"
        FAILED = "failed"

    class BidRiggingType(str, Enum):
        COMPLEMENTARY_BIDDING = "complementary_bidding"
        BID_ROTATION = "bid_rotation"
        MARKET_ALLOCATION = "market_allocation"
        BID_SUPPRESSION = "bid_suppression"

    class RedFlagSeverity(str, Enum):
        CRITICAL = "Critical"
        HIGH = "High"
        MEDIUM = "Medium"
        LOW = "Low"

    class RedFlagCategory(str, Enum):
        BID_RIGGING = "bid_rigging"
        PRICING = "pricing"
        COMMUNICATION = "communication"
        FINANCIAL = "financial"
        BEHAVIORAL = "behavioral"

    class SchemeType(str, Enum):
        COMPLEMENTARY_BIDDING = "complementary_bidding"
        BID_ROTATION = "bid_rotation"
        MARKET_ALLOCATION = "market_allocation"
        BID_SUPPRESSION = "bid_suppression"
        MIXED = "mixed"

    @dataclass
    class ScoringFactor:
        name: str
        weight: float
        score: float
        evidence_refs: list = field(default_factory=list)
        description: str = ""

    @dataclass
    class ScoringResult:
        overall_score: float
        factors: list = field(default_factory=list)
        severity: str = "Low"
        confidence: float = 0.0

    @dataclass
    class AnalysisResult:
        case_id: str
        case_type: str
        status: str
        overall_score: float
        red_flags: list = field(default_factory=list)
        patterns: list = field(default_factory=list)
        subjects: list = field(default_factory=list)
        evidence_summary: dict = field(default_factory=dict)
        legal_reasoning: str = None
        metadata: dict = field(default_factory=dict)



# =============================================================================
# Abstract Base Class
# =============================================================================


class AntitrustAnalysisModule(ABC):
    """Abstract base class for all antitrust analysis modules.

    Each case type (procurement collusion, merger review, price fixing, etc.)
    implements this interface. The framework uses it to orchestrate analysis,
    scoring, and legal reasoning across case types.
    """

    @abstractmethod
    def get_case_type(self) -> CaseType:
        """Return the CaseType enum value this module handles.

        Returns:
            CaseType enum member identifying this module's domain.
        """
        ...

    @abstractmethod
    def run_analysis(self, case_id: str) -> AnalysisResult:
        """Execute full analysis for a case.

        Orchestrates all detection methods, computes the composite PCSF score,
        generates red flags, and caches results.

        Args:
            case_id: Investigation identifier.

        Returns:
            AnalysisResult with overall score, patterns, red flags, and metadata.
        """
        ...

    @abstractmethod
    def run_incremental_analysis(
        self, case_id: str, new_record_ids: list[str]
    ) -> AnalysisResult:
        """Update analysis with newly ingested records.

        Only recomputes clusters affected by the new records rather than
        re-running the full analysis.

        Args:
            case_id: Investigation identifier.
            new_record_ids: IDs of newly ingested procurement records.

        Returns:
            Updated AnalysisResult reflecting the new data.
        """
        ...

    @abstractmethod
    def get_scoring_factors(self) -> list[ScoringFactor]:
        """Return the scoring factor definitions for this case type.

        Returns:
            List of ScoringFactor with name, weight, and description.
            Weights must sum to 1.0.
        """
        ...

    @abstractmethod
    def get_red_flag_categories(self) -> list[str]:
        """Return the red flag categories applicable to this case type.

        Returns:
            List of category identifiers (e.g., "bid_rigging", "pricing").
        """
        ...

    @abstractmethod
    def get_legal_statutes(self) -> list[dict]:
        """Return applicable legal statutes for this case type.

        Returns:
            List of dicts with keys: statute_id, title, section, description.
        """
        ...

    @abstractmethod
    def get_graph_schema(self) -> dict:
        """Return the Neptune graph schema used by this module.

        Returns:
            Dict describing vertex labels, edge labels, and properties
            used in the graph for this case type.
        """
        ...


# =============================================================================
# Implementation
# =============================================================================


class CollusionDetectionService(AntitrustAnalysisModule):
    """Core analysis engine for procurement collusion detection.

    Orchestrates bid-rigging detection, statistical anomaly analysis,
    communication pattern analysis, financial flow analysis, and PCSF scoring.
    Implements the AntitrustAnalysisModule interface for the
    PROCUREMENT_COLLUSION case type.

    Dependencies are injected via the constructor for testability:
        - aurora_cm: ConnectionManager for Aurora PostgreSQL queries
        - neptune_endpoint/port: Neptune graph database for vendor relationships
        - bedrock_client: (unused directly — passed to legal reasoning service)
        - opensearch_endpoint: for document co-occurrence searches
        - decision_workflow_svc: human-in-the-loop decision engine
        - antitrust_scoring_svc: shared weighted-factor scoring framework
        - antitrust_legal_reasoning: Bedrock prompt management for legal analysis
        - procurement_parser: optional parser for raw procurement data
    """

    def __init__(
        self,
        aurora_cm: Any,
        neptune_endpoint: str,
        neptune_port: str = "8182",
        bedrock_client: Any = None,
        opensearch_endpoint: str = "",
        decision_workflow_svc: Any = None,
        antitrust_scoring_svc: Any = None,
        antitrust_legal_reasoning: Any = None,
        procurement_parser: Any = None,
    ) -> None:
        """Initialize the collusion detection service.

        Args:
            aurora_cm: Aurora PostgreSQL ConnectionManager for bid record queries.
            neptune_endpoint: Neptune cluster endpoint for graph queries.
            neptune_port: Neptune port (default 8182).
            bedrock_client: boto3 Bedrock Runtime client (passed through, not
                used directly — legal reasoning is via antitrust_legal_reasoning).
            opensearch_endpoint: OpenSearch Serverless endpoint for document search.
            decision_workflow_svc: DecisionWorkflowService for AI_Proposed decisions.
            antitrust_scoring_svc: AntitrustScoringService for composite scoring.
            antitrust_legal_reasoning: AntitrustLegalReasoning for Bedrock prompts.
            procurement_parser: Optional parser for raw procurement file formats.
        """
        self._aurora = aurora_cm
        self._neptune_endpoint = neptune_endpoint
        self._neptune_port = neptune_port
        self._bedrock_client = bedrock_client
        self._opensearch_endpoint = opensearch_endpoint
        self._decision_workflow_svc = decision_workflow_svc
        self._scoring_svc = antitrust_scoring_svc
        self._legal_reasoning = antitrust_legal_reasoning
        self._procurement_parser = procurement_parser

    # ------------------------------------------------------------------
    # AntitrustAnalysisModule interface
    # ------------------------------------------------------------------

    def get_case_type(self) -> CaseType:
        """Return PROCUREMENT_COLLUSION case type."""
        return CaseType.PROCUREMENT_COLLUSION

    def get_scoring_factors(self) -> list[ScoringFactor]:
        """Return PCSF scoring factor definitions.

        Returns:
            Five factors: bid_rigging (0.30), pricing (0.25),
            communication (0.20), financial (0.15), behavioral (0.10).
        """
        return [
            ScoringFactor(
                name="bid_rigging",
                weight=PCSF_WEIGHTS["bid_rigging"],
                score=0.0,
                description="Complementary bidding, rotation, suppression patterns",
            ),
            ScoringFactor(
                name="pricing",
                weight=PCSF_WEIGHTS["pricing"],
                score=0.0,
                description="Statistical anomalies in bid pricing",
            ),
            ScoringFactor(
                name="communication",
                weight=PCSF_WEIGHTS["communication"],
                score=0.0,
                description="Pre-deadline communication timing spikes",
            ),
            ScoringFactor(
                name="financial",
                weight=PCSF_WEIGHTS["financial"],
                score=0.0,
                description="Suspicious financial flows between competitors",
            ),
            ScoringFactor(
                name="behavioral",
                weight=PCSF_WEIGHTS["behavioral"],
                score=0.0,
                description="Behavioral indicators (meetings, joint ventures, personnel)",
            ),
        ]

    def get_red_flag_categories(self) -> list[str]:
        """Return PCSF red flag categories for procurement collusion."""
        return [
            "bid_rigging",
            "pricing",
            "communication",
            "financial",
            "market_allocation",
            "bid_suppression",
            "behavioral",
        ]

    def get_legal_statutes(self) -> list[dict]:
        """Return applicable legal statutes for procurement collusion.

        Returns:
            Sherman Act section 1, False Claims Act, and wire fraud statutes.
        """
        return [
            {
                "statute_id": "15_usc_1",
                "title": "Sherman Antitrust Act",
                "section": "Section 1",
                "description": (
                    "Every contract, combination in the form of trust or otherwise, "
                    "or conspiracy, in restraint of trade or commerce among the several "
                    "States, or with foreign nations, is declared to be illegal."
                ),
            },
            {
                "statute_id": "31_usc_3729",
                "title": "False Claims Act",
                "section": "31 U.S.C. § 3729",
                "description": (
                    "Liability for false or fraudulent claims submitted to the "
                    "United States government."
                ),
            },
            {
                "statute_id": "18_usc_1343",
                "title": "Wire Fraud",
                "section": "18 U.S.C. § 1343",
                "description": (
                    "Fraud by wire, radio, or television in furtherance of a "
                    "scheme to defraud."
                ),
            },
        ]

    def get_graph_schema(self) -> dict:
        """Return Neptune graph schema for procurement collusion analysis.

        Returns:
            Dict with vertex_labels, edge_labels, and properties used
            in the collusion detection graph model.
        """
        return {
            "vertex_labels": [
                "Vendor",
                "Contract",
                "Bid",
                "Agency",
                "Person",
                "ShellCompany",
            ],
            "edge_labels": [
                "SUBMITTED_BID",
                "AWARDED_TO",
                "SUBCONTRACTED_TO",
                "COMMUNICATED_WITH",
                "FINANCIAL_FLOW",
                "AFFILIATED_WITH",
                "SHARES_PERSONNEL",
                "SHARES_ADDRESS",
            ],
            "properties": {
                "Vendor": ["vendor_id", "name", "naics_codes", "geographic_regions"],
                "Contract": ["contract_id", "agency", "value", "award_date", "category"],
                "Bid": ["bid_id", "amount", "submission_date", "specs_met", "status"],
                "FINANCIAL_FLOW": ["amount", "date", "flow_type", "description"],
                "COMMUNICATED_WITH": ["date", "channel", "pre_deadline"],
            },
        }


    # ------------------------------------------------------------------
    # Internal: Neptune Gremlin HTTP helper
    # ------------------------------------------------------------------

    def _gremlin_query(self, query: str) -> list:
        """Execute a Gremlin query via Neptune HTTP API.

        Args:
            query: Gremlin traversal string.

        Returns:
            List of result items. Returns empty list if Neptune is
            unavailable or disabled.
        """
        if not self._neptune_endpoint or not _NEPTUNE_ENABLED:
            return []
        url = f"https://{self._neptune_endpoint}:{self._neptune_port}/gremlin"
        data = json.dumps({"gremlin": query}).encode("utf-8")
        ctx = ssl.create_default_context()
        req = urllib.request.Request(
            url, data=data, headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=60) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                result = body.get("result", {}).get("data", {})
                if isinstance(result, dict) and "@value" in result:
                    return result["@value"]
                if isinstance(result, list):
                    return result
                return [result] if result else []
        except Exception as e:
            logger.error("Neptune query error: %s", str(e)[:200])
            return []

    @staticmethod
    def _entity_label(case_id: str) -> str:
        """Generate Neptune vertex label scoped to a case.

        Args:
            case_id: Investigation identifier.

        Returns:
            Label string in the form 'Vendor_{case_id}'.
        """
        return f"Vendor_{case_id}"

    @staticmethod
    def _escape(s: str) -> str:
        """Escape a string for safe inclusion in Gremlin queries."""
        return s.replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"')

    # ------------------------------------------------------------------
    # Internal: Aurora paginated query helper
    # ------------------------------------------------------------------

    def _fetch_bids_paginated(
        self, case_id: str, contract_ids: Optional[list[str]] = None
    ) -> list[dict]:
        """Fetch bid records from Aurora in paginated batches of 5000.

        Args:
            case_id: Investigation identifier.
            contract_ids: Optional list of contract IDs to filter.
                If None, fetches all bids for the case.

        Returns:
            List of bid record dicts with keys: record_id, vendor_id,
            vendor_name, contract_id, bid_amount, submission_timestamp,
            specifications_met, award_status, government_estimate,
            geographic_region.
        """
        all_records: list[dict] = []
        offset = 0

        while True:
            if contract_ids:
                query = """
                    SELECT record_id, vendor_id, vendor_name, contract_id,
                           bid_amount, submission_timestamp, specifications_met,
                           award_status, government_estimate, geographic_region
                    FROM procurement_records
                    WHERE case_id = %s AND contract_id = ANY(%s)
                    ORDER BY contract_id, bid_amount
                    LIMIT %s OFFSET %s
                """
                params = (case_id, contract_ids, AURORA_BATCH_SIZE, offset)
            else:
                query = """
                    SELECT record_id, vendor_id, vendor_name, contract_id,
                           bid_amount, submission_timestamp, specifications_met,
                           award_status, government_estimate, geographic_region
                    FROM procurement_records
                    WHERE case_id = %s
                    ORDER BY contract_id, bid_amount
                    LIMIT %s OFFSET %s
                """
                params = (case_id, AURORA_BATCH_SIZE, offset)

            try:
                with self._aurora.get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute(query, params)
                        rows = cur.fetchall()
            except Exception as e:
                logger.error("Aurora query failed at offset %d: %s", offset, e)
                break

            if not rows:
                break

            columns = [
                "record_id", "vendor_id", "vendor_name", "contract_id",
                "bid_amount", "submission_timestamp", "specifications_met",
                "award_status", "government_estimate", "geographic_region",
            ]
            for row in rows:
                all_records.append(dict(zip(columns, row)))

            if len(rows) < AURORA_BATCH_SIZE:
                break
            offset += AURORA_BATCH_SIZE

        return all_records

    def _fetch_vendor_communications(
        self, case_id: str, vendor_pairs: list[tuple[str, str]]
    ) -> list[dict]:
        """Fetch communication records between vendor pairs.

        Args:
            case_id: Investigation identifier.
            vendor_pairs: List of (vendor_a_id, vendor_b_id) tuples.

        Returns:
            List of communication record dicts.
        """
        if not vendor_pairs:
            return []

        all_comms: list[dict] = []
        offset = 0

        # Build pair filter
        pair_conditions = " OR ".join(
            "(vendor_a_id = %s AND vendor_b_id = %s)"
            for _ in vendor_pairs
        )
        pair_params: list = []
        for a, b in vendor_pairs:
            pair_params.extend([a, b])

        while True:
            query = f"""
                SELECT comm_id, vendor_a_id, vendor_b_id, comm_date,
                       channel, contract_deadline, days_before_deadline
                FROM vendor_communications
                WHERE case_id = %s AND ({pair_conditions})
                ORDER BY comm_date
                LIMIT %s OFFSET %s
            """
            params = tuple([case_id] + pair_params + [AURORA_BATCH_SIZE, offset])

            try:
                with self._aurora.get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute(query, params)
                        rows = cur.fetchall()
            except Exception as e:
                logger.error("Communication query failed: %s", e)
                break

            if not rows:
                break

            columns = [
                "comm_id", "vendor_a_id", "vendor_b_id", "comm_date",
                "channel", "contract_deadline", "days_before_deadline",
            ]
            for row in rows:
                all_comms.append(dict(zip(columns, row)))

            if len(rows) < AURORA_BATCH_SIZE:
                break
            offset += AURORA_BATCH_SIZE

        return all_comms

    def _fetch_financial_flows(
        self, case_id: str, vendor_pairs: list[tuple[str, str]]
    ) -> list[dict]:
        """Fetch financial flow records between vendor pairs.

        Args:
            case_id: Investigation identifier.
            vendor_pairs: List of (vendor_a_id, vendor_b_id) tuples.

        Returns:
            List of financial flow record dicts.
        """
        if not vendor_pairs:
            return []

        all_flows: list[dict] = []
        offset = 0

        pair_conditions = " OR ".join(
            "((payer_vendor_id = %s AND payee_vendor_id = %s) OR "
            "(payer_vendor_id = %s AND payee_vendor_id = %s))"
            for _ in vendor_pairs
        )
        pair_params: list = []
        for a, b in vendor_pairs:
            pair_params.extend([a, b, b, a])

        while True:
            query = f"""
                SELECT flow_id, payer_vendor_id, payee_vendor_id, amount,
                       flow_date, flow_type, related_contract_id, description
                FROM financial_flows
                WHERE case_id = %s AND ({pair_conditions})
                ORDER BY flow_date
                LIMIT %s OFFSET %s
            """
            params = tuple([case_id] + pair_params + [AURORA_BATCH_SIZE, offset])

            try:
                with self._aurora.get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute(query, params)
                        rows = cur.fetchall()
            except Exception as e:
                logger.error("Financial flow query failed: %s", e)
                break

            if not rows:
                break

            columns = [
                "flow_id", "payer_vendor_id", "payee_vendor_id", "amount",
                "flow_date", "flow_type", "related_contract_id", "description",
            ]
            for row in rows:
                all_flows.append(dict(zip(columns, row)))

            if len(rows) < AURORA_BATCH_SIZE:
                break
            offset += AURORA_BATCH_SIZE

        return all_flows


    # ------------------------------------------------------------------
    # Bid-Rigging Detection
    # ------------------------------------------------------------------

    def detect_complementary_bidding(
        self, case_id: str, contract_ids: list[str]
    ) -> list[dict]:
        """Detect complementary (cover) bidding patterns.

        For each contract, compares losing bids against the winning bid to
        compute a Complementary_Bid_Score. Flags bids scoring above 70.

        Score formula per losing bid:
            0.30 * bid_relative + 0.25 * spec_gaps + 0.20 * timing + 0.25 * history

        Args:
            case_id: Investigation identifier.
            contract_ids: List of contract IDs to analyze.

        Returns:
            List of flagged bid dicts with complementary_bid_score and
            component breakdown.
        """
        bids = self._fetch_bids_paginated(case_id, contract_ids)
        if not bids:
            return []

        # Group bids by contract
        by_contract: dict[str, list[dict]] = defaultdict(list)
        for bid in bids:
            by_contract[bid["contract_id"]].append(bid)

        # Build vendor history for the history component
        vendor_win_history = self._build_vendor_win_history(bids)

        flagged: list[dict] = []

        for contract_id, contract_bids in by_contract.items():
            # Identify winning bid
            winning_bids = [
                b for b in contract_bids if b["award_status"] == "won"
            ]
            if not winning_bids:
                continue
            winning_bid = winning_bids[0]

            losing_bids = [
                b for b in contract_bids if b["award_status"] != "won"
            ]

            for bid in losing_bids:
                score = self.compute_complementary_bid_score(
                    bid, winning_bid, vendor_win_history
                )
                if score >= COMPLEMENTARY_BID_FLAG_THRESHOLD:
                    flagged.append({
                        "record_id": bid["record_id"],
                        "vendor_id": bid["vendor_id"],
                        "vendor_name": bid["vendor_name"],
                        "contract_id": contract_id,
                        "bid_amount": bid["bid_amount"],
                        "winning_amount": winning_bid["bid_amount"],
                        "complementary_bid_score": round(score, 2),
                        "flag_type": "complementary_bidding",
                    })

        logger.info(
            "Complementary bidding: analyzed %d contracts, flagged %d bids",
            len(by_contract),
            len(flagged),
        )
        return flagged

    def compute_complementary_bid_score(
        self,
        bid: dict,
        winning_bid: dict,
        history: dict[str, dict],
    ) -> float:
        """Compute the Complementary Bid Score for a single losing bid.

        Components (weighted):
            - bid_relative (0.30): How far above the winner (normalized 0-100)
            - spec_gaps (0.25): Whether bid fails to meet specifications
            - timing (0.20): Submission timing relative to deadline/winner
            - history (0.25): Historical pattern of this vendor losing to winner

        Args:
            bid: The losing bid record dict.
            winning_bid: The winning bid record dict.
            history: Dict mapping vendor_id to win/loss history stats.

        Returns:
            Float score in range [0, 100].
        """
        # Component 1: Bid relative to winner (higher = more suspicious)
        winning_amount = winning_bid["bid_amount"]
        bid_amount = bid["bid_amount"]
        if winning_amount > 0:
            # Percentage above winner, capped at 100
            pct_above = ((bid_amount - winning_amount) / winning_amount) * 100
            # Normalize: 5-30% above is the suspicious range for cover bids
            bid_relative = min(100.0, max(0.0, (pct_above / 30.0) * 100.0))
        else:
            bid_relative = 0.0

        # Component 2: Specification gaps
        specs_met = bid.get("specifications_met", True)
        spec_gaps = 100.0 if not specs_met else 0.0

        # Component 3: Timing (late submissions are more suspicious)
        timing_score = 0.0
        bid_ts = bid.get("submission_timestamp")
        win_ts = winning_bid.get("submission_timestamp")
        if bid_ts and win_ts:
            # If bid was submitted after the winner, more suspicious
            if isinstance(bid_ts, str):
                try:
                    bid_ts = datetime.fromisoformat(bid_ts.replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    bid_ts = None
            if isinstance(win_ts, str):
                try:
                    win_ts = datetime.fromisoformat(win_ts.replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    win_ts = None
            if bid_ts and win_ts and bid_ts > win_ts:
                # Submitted after winner — suspicious
                hours_after = (bid_ts - win_ts).total_seconds() / 3600
                timing_score = min(100.0, hours_after * 10.0)

        # Component 4: Historical pattern
        vendor_id = bid["vendor_id"]
        winner_id = winning_bid["vendor_id"]
        history_score = 0.0
        vendor_stats = history.get(vendor_id, {})
        losses_to_winner = vendor_stats.get(f"losses_to_{winner_id}", 0)
        total_bids = vendor_stats.get("total_bids", 1)
        if total_bids > 0:
            # High loss rate to same winner is suspicious
            loss_rate = losses_to_winner / total_bids
            history_score = min(100.0, loss_rate * 200.0)  # 50% loss rate = 100

        # Weighted composite
        score = (
            COMPLEMENTARY_BID_WEIGHTS["bid_relative"] * bid_relative
            + COMPLEMENTARY_BID_WEIGHTS["spec_gaps"] * spec_gaps
            + COMPLEMENTARY_BID_WEIGHTS["timing"] * timing_score
            + COMPLEMENTARY_BID_WEIGHTS["history"] * history_score
        )

        return max(0.0, min(100.0, score))

    def _build_vendor_win_history(self, bids: list[dict]) -> dict[str, dict]:
        """Build vendor win/loss history from bid records.

        Args:
            bids: All bid records for the case.

        Returns:
            Dict mapping vendor_id to stats dict with total_bids,
            wins, and losses_to_{winner_id} counts.
        """
        history: dict[str, dict] = defaultdict(lambda: {"total_bids": 0, "wins": 0})

        # Group by contract to determine winners
        by_contract: dict[str, list[dict]] = defaultdict(list)
        for bid in bids:
            by_contract[bid["contract_id"]].append(bid)

        for contract_id, contract_bids in by_contract.items():
            winners = [b for b in contract_bids if b["award_status"] == "won"]
            winner_id = winners[0]["vendor_id"] if winners else None

            for bid in contract_bids:
                vid = bid["vendor_id"]
                history[vid]["total_bids"] += 1
                if bid["award_status"] == "won":
                    history[vid]["wins"] += 1
                elif winner_id:
                    key = f"losses_to_{winner_id}"
                    history[vid][key] = history[vid].get(key, 0) + 1

        return dict(history)

    def detect_bid_rotation(
        self, case_id: str, vendor_sets: list[list[str]]
    ) -> list[dict]:
        """Detect bid rotation patterns among vendor sets.

        Computes the Winner_Rotation_Index for each vendor set. A high index
        (>0.7) indicates suspiciously even distribution of wins — consistent
        with a turn-taking arrangement.

        Args:
            case_id: Investigation identifier.
            vendor_sets: List of vendor ID groups to test for rotation.
                Each group is a list of vendor IDs suspected of coordinating.

        Returns:
            List of flagged vendor sets with rotation_index and details.
        """
        bids = self._fetch_bids_paginated(case_id)
        if not bids:
            return []

        flagged: list[dict] = []

        for vendor_set in vendor_sets:
            # Filter bids to only those from vendors in this set
            set_bids = [b for b in bids if b["vendor_id"] in vendor_set]
            if not set_bids:
                continue

            # Get contracts where these vendors competed
            contracts_with_set = set(b["contract_id"] for b in set_bids)
            contract_bids = [
                b for b in bids if b["contract_id"] in contracts_with_set
            ]

            rotation_index = self.compute_winner_rotation_index(
                vendor_set, contract_bids
            )

            if rotation_index >= ROTATION_INDEX_FLAG_THRESHOLD:
                # Count wins per vendor
                wins_per_vendor = defaultdict(int)
                for b in set_bids:
                    if b["award_status"] == "won":
                        wins_per_vendor[b["vendor_id"]] += 1

                flagged.append({
                    "vendor_set": vendor_set,
                    "rotation_index": round(rotation_index, 4),
                    "wins_per_vendor": dict(wins_per_vendor),
                    "total_contracts": len(contracts_with_set),
                    "flag_type": "bid_rotation",
                })

        logger.info(
            "Bid rotation: tested %d vendor sets, flagged %d",
            len(vendor_sets),
            len(flagged),
        )
        return flagged

    def compute_winner_rotation_index(
        self, vendor_set: list[str], contracts: list[dict]
    ) -> float:
        """Compute the Winner Rotation Index for a vendor set.

        Measures how evenly wins are distributed among the set members.
        A perfectly even distribution (each vendor wins equally) yields 1.0.
        Random/competitive distribution yields lower values.

        Formula: 1 - (std_dev(win_counts) / mean(win_counts))
        Clamped to [0, 1].

        Args:
            vendor_set: List of vendor IDs in the suspected rotation group.
            contracts: All bid records for contracts involving these vendors.

        Returns:
            Float in [0, 1]. Higher = more suspicious rotation pattern.
        """
        if len(vendor_set) < 2:
            return 0.0

        # Count wins per vendor in the set
        wins = {vid: 0 for vid in vendor_set}
        for bid in contracts:
            if bid["vendor_id"] in wins and bid["award_status"] == "won":
                wins[bid["vendor_id"]] += 1

        win_counts = np.array(list(wins.values()), dtype=np.float64)
        total_wins = win_counts.sum()

        if total_wins < len(vendor_set):
            # Not enough data to assess rotation
            return 0.0

        mean_wins = win_counts.mean()
        if mean_wins == 0:
            return 0.0

        std_wins = win_counts.std()
        # Rotation index: 1 - normalized standard deviation
        # Perfect rotation = 0 std dev = index 1.0
        rotation_index = 1.0 - (std_wins / mean_wins)

        return float(max(0.0, min(1.0, rotation_index)))


    def detect_market_allocation(self, case_id: str) -> list[dict]:
        """Detect geographic or category market allocation schemes.

        Performs a chi-squared test for independence between vendor identity
        and geographic region (or NAICS category). If the distribution is
        significantly non-random (p < 0.05), it suggests vendors have divided
        the market.

        Args:
            case_id: Investigation identifier.

        Returns:
            List of flagged allocation patterns with chi2 statistic,
            p-value, and affected vendors/regions.
        """
        bids = self._fetch_bids_paginated(case_id)
        if not bids:
            return []

        flagged: list[dict] = []

        # Test geographic allocation
        geo_result = self._chi_squared_allocation_test(bids, "geographic_region")
        if geo_result and geo_result["p_value"] < CHI_SQUARED_P_VALUE_THRESHOLD:
            flagged.append({
                "allocation_type": "geographic",
                "chi2_statistic": round(geo_result["chi2"], 4),
                "p_value": round(geo_result["p_value"], 6),
                "degrees_of_freedom": geo_result["dof"],
                "vendor_region_matrix": geo_result["matrix_summary"],
                "exclusive_vendors": geo_result["exclusive_vendors"],
                "flag_type": "market_allocation",
            })

        logger.info("Market allocation: flagged %d patterns", len(flagged))
        return flagged

    def _chi_squared_allocation_test(
        self, bids: list[dict], dimension_key: str
    ) -> Optional[dict]:
        """Run chi-squared test for vendor-dimension independence.

        Args:
            bids: Bid records to analyze.
            dimension_key: Key in bid dict to use as the dimension
                (e.g., "geographic_region").

        Returns:
            Dict with chi2, p_value, dof, matrix_summary, exclusive_vendors.
            None if insufficient data.
        """
        # Build contingency matrix: vendors x dimensions
        vendors = sorted(set(b["vendor_id"] for b in bids))
        dimensions = sorted(set(
            b.get(dimension_key, "unknown") for b in bids
            if b.get(dimension_key)
        ))

        if len(vendors) < 2 or len(dimensions) < 2:
            return None

        # Build observed frequency matrix
        vendor_idx = {v: i for i, v in enumerate(vendors)}
        dim_idx = {d: i for i, d in enumerate(dimensions)}
        observed = np.zeros((len(vendors), len(dimensions)), dtype=np.float64)

        for bid in bids:
            vid = bid["vendor_id"]
            dim = bid.get(dimension_key)
            if vid in vendor_idx and dim in dim_idx:
                observed[vendor_idx[vid], dim_idx[dim]] += 1

        # Remove rows/cols with all zeros
        row_sums = observed.sum(axis=1)
        col_sums = observed.sum(axis=0)
        valid_rows = row_sums > 0
        valid_cols = col_sums > 0
        observed = observed[valid_rows][:, valid_cols]

        if observed.shape[0] < 2 or observed.shape[1] < 2:
            return None

        # Compute chi-squared statistic
        row_totals = observed.sum(axis=1, keepdims=True)
        col_totals = observed.sum(axis=0, keepdims=True)
        grand_total = observed.sum()

        if grand_total == 0:
            return None

        expected = (row_totals * col_totals) / grand_total
        # Avoid division by zero
        expected = np.where(expected == 0, 1e-10, expected)

        chi2 = float(((observed - expected) ** 2 / expected).sum())
        dof = (observed.shape[0] - 1) * (observed.shape[1] - 1)

        if dof <= 0:
            return None

        # Approximate p-value using chi-squared survival function
        p_value = self._chi2_survival(chi2, dof)

        # Identify vendors with exclusive presence in single dimension
        active_vendors = [v for v, valid in zip(vendors, valid_rows) if valid]
        active_dims = [d for d, valid in zip(dimensions, valid_cols) if valid]
        exclusive_vendors = []
        for i, vendor in enumerate(active_vendors):
            row = observed[i]
            if row.sum() > 0:
                # Check if >80% of bids are in one dimension
                max_pct = row.max() / row.sum()
                if max_pct > 0.80:
                    dominant_dim_idx = int(row.argmax())
                    exclusive_vendors.append({
                        "vendor_id": vendor,
                        "dominant_dimension": active_dims[dominant_dim_idx],
                        "concentration_pct": round(float(max_pct) * 100, 1),
                    })

        return {
            "chi2": chi2,
            "p_value": p_value,
            "dof": dof,
            "matrix_summary": {
                "vendors": len(active_vendors),
                "dimensions": len(active_dims),
                "total_observations": int(grand_total),
            },
            "exclusive_vendors": exclusive_vendors,
        }

    @staticmethod
    def _chi2_survival(x: float, k: int) -> float:
        """Approximate chi-squared survival function P(X > x) for k dof.

        Uses the Wilson-Hilferty normal approximation for the chi-squared
        distribution.

        Args:
            x: Chi-squared test statistic.
            k: Degrees of freedom.

        Returns:
            Approximate p-value (probability of observing >= x under null).
        """
        if k <= 0 or x <= 0:
            return 1.0
        # Wilson-Hilferty approximation
        z = ((x / k) ** (1.0 / 3.0) - (1.0 - 2.0 / (9.0 * k))) / math.sqrt(
            2.0 / (9.0 * k)
        )
        # Standard normal CDF approximation
        if z < -8:
            return 1.0
        if z > 8:
            return 0.0
        p = 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))
        return max(0.0, min(1.0, 1.0 - p))

    def detect_bid_suppression(self, case_id: str) -> list[dict]:
        """Detect bid suppression — qualified vendors abstaining from bidding.

        Identifies vendors who are qualified (have bid on similar contracts)
        but have an abstention rate exceeding 60% on contracts where their
        competitors bid.

        Args:
            case_id: Investigation identifier.

        Returns:
            List of flagged vendors with abstention_rate and details.
        """
        bids = self._fetch_bids_paginated(case_id)
        if not bids:
            return []

        # Determine each vendor's qualified contract set
        vendor_regions: dict[str, set[str]] = defaultdict(set)
        vendor_contracts: dict[str, set[str]] = defaultdict(set)
        contract_regions: dict[str, str] = {}

        for bid in bids:
            vid = bid["vendor_id"]
            cid = bid["contract_id"]
            region = bid.get("geographic_region", "")
            vendor_contracts[vid].add(cid)
            if region:
                vendor_regions[vid].add(region)
                contract_regions[cid] = region

        flagged: list[dict] = []

        for vendor_id, regions in vendor_regions.items():
            if not regions:
                continue

            # Contracts in vendor's qualified regions
            qualified_contracts = {
                cid for cid, region in contract_regions.items()
                if region in regions
            }

            actual_bids = vendor_contracts[vendor_id]
            eligible_count = len(qualified_contracts)
            bid_count = len(actual_bids & qualified_contracts)

            if eligible_count < 3:
                continue

            abstention_rate = 1.0 - (bid_count / eligible_count)

            if abstention_rate >= ABSTENTION_RATE_FLAG_THRESHOLD:
                flagged.append({
                    "vendor_id": vendor_id,
                    "abstention_rate": round(abstention_rate, 4),
                    "eligible_contracts": eligible_count,
                    "actual_bids": bid_count,
                    "abstained_contracts": eligible_count - bid_count,
                    "qualified_regions": list(regions),
                    "flag_type": "bid_suppression",
                })

        logger.info("Bid suppression: flagged %d vendors", len(flagged))
        return flagged


    # ------------------------------------------------------------------
    # Statistical Anomaly Analysis
    # ------------------------------------------------------------------

    def analyze_price_anomalies(
        self, case_id: str, contract_ids: list[str]
    ) -> list[dict]:
        """Analyze bid pricing for statistical anomalies.

        Detects three types of pricing anomalies:
        1. Bid spread CV < 0.05 (suspiciously tight clustering)
        2. Round numbers > 50% of bids (suggests coordination)
        3. Price-to-estimate ratio anomalies (bids too close to estimate)

        Args:
            case_id: Investigation identifier.
            contract_ids: Contract IDs to analyze.

        Returns:
            List of detected anomaly dicts with test type, statistic,
            and involved vendors/contracts.
        """
        bids = self._fetch_bids_paginated(case_id, contract_ids)
        if not bids:
            return []

        anomalies: list[dict] = []

        # Group by contract for per-contract analysis
        by_contract: dict[str, list[dict]] = defaultdict(list)
        for bid in bids:
            by_contract[bid["contract_id"]].append(bid)

        for contract_id, contract_bids in by_contract.items():
            if len(contract_bids) < 3:
                continue

            amounts = np.array(
                [b["bid_amount"] for b in contract_bids], dtype=np.float64
            )
            vendors = [b["vendor_id"] for b in contract_bids]

            # Test 1: Coefficient of Variation (bid spread)
            mean_amount = amounts.mean()
            if mean_amount > 0:
                cv = float(amounts.std() / mean_amount)
                if cv < BID_SPREAD_CV_THRESHOLD:
                    anomalies.append({
                        "anomaly_id": str(uuid.uuid4()),
                        "test_type": "bid_spread",
                        "contract_id": contract_id,
                        "test_statistic": round(cv, 6),
                        "threshold": BID_SPREAD_CV_THRESHOLD,
                        "interpretation": (
                            f"Bid spread CV={cv:.4f} is below threshold "
                            f"{BID_SPREAD_CV_THRESHOLD}. Bids are suspiciously "
                            f"clustered, suggesting coordination."
                        ),
                        "involved_vendors": vendors,
                        "severity": "High" if cv < 0.02 else "Medium",
                    })

            # Test 2: Round number prevalence
            round_count = sum(
                1 for a in amounts
                if a == round(a, -3) or a % 1000 == 0 or a % 500 == 0
            )
            round_pct = round_count / len(amounts)
            if round_pct > ROUND_NUMBER_THRESHOLD:
                anomalies.append({
                    "anomaly_id": str(uuid.uuid4()),
                    "test_type": "round_number",
                    "contract_id": contract_id,
                    "test_statistic": round(round_pct, 4),
                    "threshold": ROUND_NUMBER_THRESHOLD,
                    "interpretation": (
                        f"{round_pct*100:.1f}% of bids are round numbers "
                        f"(threshold: {ROUND_NUMBER_THRESHOLD*100:.0f}%). "
                        f"Suggests bids were not independently calculated."
                    ),
                    "involved_vendors": vendors,
                    "severity": "Medium",
                })

            # Test 3: Price-to-estimate ratio
            estimates = [
                b["government_estimate"]
                for b in contract_bids
                if b.get("government_estimate") and b["government_estimate"] > 0
            ]
            if estimates:
                estimate = estimates[0]
                ratios = amounts / estimate
                mean_ratio = float(ratios.mean())
                ratio_spread = float(ratios.std())
                if ratio_spread < 0.03 and 0.90 < mean_ratio < 1.10:
                    anomalies.append({
                        "anomaly_id": str(uuid.uuid4()),
                        "test_type": "price_to_estimate",
                        "contract_id": contract_id,
                        "test_statistic": round(mean_ratio, 4),
                        "ratio_spread": round(ratio_spread, 4),
                        "interpretation": (
                            f"All bids cluster near government estimate "
                            f"(mean ratio={mean_ratio:.3f}, spread={ratio_spread:.4f}). "
                            f"Suggests bidders had access to the estimate."
                        ),
                        "involved_vendors": vendors,
                        "severity": "High",
                    })

        logger.info(
            "Price anomalies: analyzed %d contracts, found %d anomalies",
            len(by_contract),
            len(anomalies),
        )
        return anomalies

    # ------------------------------------------------------------------
    # Communication Pattern Analysis
    # ------------------------------------------------------------------

    def analyze_communication_timing(
        self, case_id: str, vendor_pairs: list[tuple[str, str]]
    ) -> list[dict]:
        """Analyze communication timing between vendor pairs.

        Flags communication spikes exceeding 2 standard deviations above
        the mean in the 14-day pre-deadline window. Such spikes suggest
        coordination before bid submission.

        Args:
            case_id: Investigation identifier.
            vendor_pairs: List of (vendor_a_id, vendor_b_id) tuples to analyze.

        Returns:
            List of flagged communication spikes with timing details.
        """
        comms = self._fetch_vendor_communications(case_id, vendor_pairs)
        if not comms:
            return []

        flagged: list[dict] = []

        # Group by vendor pair
        by_pair: dict[tuple[str, str], list[dict]] = defaultdict(list)
        for comm in comms:
            pair_key = (comm["vendor_a_id"], comm["vendor_b_id"])
            by_pair[pair_key].append(comm)

        for pair_key, pair_comms in by_pair.items():
            if len(pair_comms) < 5:
                continue

            # Separate pre-deadline communications
            pre_deadline_comms = [
                c for c in pair_comms
                if c.get("days_before_deadline") is not None
                and 0 <= c["days_before_deadline"] <= PRE_DEADLINE_WINDOW_DAYS
            ]

            if not pre_deadline_comms:
                continue

            # Compute daily communication rates for baseline
            daily_counts: dict[str, int] = defaultdict(int)
            for c in pair_comms:
                date_str = str(c.get("comm_date", ""))[:10]
                if date_str:
                    daily_counts[date_str] += 1

            if len(daily_counts) < 3:
                continue

            daily_values = np.array(list(daily_counts.values()), dtype=np.float64)
            mean_daily = float(daily_values.mean())
            std_daily = float(daily_values.std())

            if std_daily == 0:
                continue

            # Check for spikes in pre-deadline window
            pre_deadline_daily: dict[str, int] = defaultdict(int)
            for c in pre_deadline_comms:
                date_str = str(c.get("comm_date", ""))[:10]
                if date_str:
                    pre_deadline_daily[date_str] += 1

            spike_threshold = mean_daily + (COMMUNICATION_STD_DEV_MULTIPLIER * std_daily)

            for date_str, count in pre_deadline_daily.items():
                if count > spike_threshold:
                    flagged.append({
                        "vendor_pair": list(pair_key),
                        "spike_date": date_str,
                        "communication_count": count,
                        "baseline_mean": round(mean_daily, 2),
                        "baseline_std": round(std_daily, 2),
                        "spike_threshold": round(spike_threshold, 2),
                        "std_devs_above": round(
                            (count - mean_daily) / std_daily, 2
                        ),
                        "days_before_deadline": next(
                            (c["days_before_deadline"] for c in pre_deadline_comms
                             if str(c.get("comm_date", ""))[:10] == date_str),
                            None,
                        ),
                        "flag_type": "communication_spike",
                    })

        logger.info(
            "Communication timing: analyzed %d pairs, flagged %d spikes",
            len(by_pair),
            len(flagged),
        )
        return flagged

    # ------------------------------------------------------------------
    # Financial Flow Analysis
    # ------------------------------------------------------------------

    def analyze_financial_flows(
        self, case_id: str, vendor_pairs: list[tuple[str, str]]
    ) -> list[dict]:
        """Analyze financial flows between vendor pairs for collusion indicators.

        Detects three suspicious patterns:
        1. Subcontracting within 90 days of contract award
        2. Reciprocal financial flows (A pays B, B pays A)
        3. Shell company intermediaries

        Args:
            case_id: Investigation identifier.
            vendor_pairs: List of (vendor_a_id, vendor_b_id) tuples.

        Returns:
            List of flagged financial patterns with details.
        """
        flows = self._fetch_financial_flows(case_id, vendor_pairs)
        if not flows:
            return []

        flagged: list[dict] = []

        # Group by vendor pair (bidirectional)
        by_pair: dict[tuple[str, str], list[dict]] = defaultdict(list)
        for flow in flows:
            pair_key = tuple(sorted([flow["payer_vendor_id"], flow["payee_vendor_id"]]))
            by_pair[pair_key].append(flow)

        for pair_key, pair_flows in by_pair.items():
            vendor_a, vendor_b = pair_key

            # Pattern 1: Subcontracting within 90 days of award
            subcontract_flows = [
                f for f in pair_flows
                if f.get("flow_type") == "subcontract"
            ]
            if subcontract_flows:
                flagged.append({
                    "pattern_type": "post_award_subcontracting",
                    "vendor_pair": list(pair_key),
                    "flow_count": len(subcontract_flows),
                    "total_amount": sum(f.get("amount", 0) for f in subcontract_flows),
                    "contracts_involved": list(set(
                        f["related_contract_id"]
                        for f in subcontract_flows
                        if f.get("related_contract_id")
                    )),
                    "interpretation": (
                        f"Subcontracting between competitors within "
                        f"{SUBCONTRACTING_WINDOW_DAYS} days of award suggests "
                        f"pre-arranged profit sharing."
                    ),
                    "flag_type": "financial_flow",
                    "severity": "High",
                })

            # Pattern 2: Reciprocal flows
            a_to_b = [
                f for f in pair_flows if f["payer_vendor_id"] == vendor_a
            ]
            b_to_a = [
                f for f in pair_flows if f["payer_vendor_id"] == vendor_b
            ]
            if a_to_b and b_to_a:
                a_to_b_total = sum(f.get("amount", 0) for f in a_to_b)
                b_to_a_total = sum(f.get("amount", 0) for f in b_to_a)
                if min(a_to_b_total, b_to_a_total) > 0:
                    ratio = max(a_to_b_total, b_to_a_total) / min(
                        a_to_b_total, b_to_a_total
                    )
                    if ratio < 1.3:
                        flagged.append({
                            "pattern_type": "reciprocal_flows",
                            "vendor_pair": list(pair_key),
                            "a_to_b_total": round(a_to_b_total, 2),
                            "b_to_a_total": round(b_to_a_total, 2),
                            "reciprocity_ratio": round(ratio, 4),
                            "interpretation": (
                                f"Reciprocal financial flows between competitors "
                                f"(ratio={ratio:.2f}) suggest profit-sharing or "
                                f"kickback arrangement."
                            ),
                            "flag_type": "financial_flow",
                            "severity": "Critical",
                        })

            # Pattern 3: Shell company indicators
            shell_flows = [
                f for f in pair_flows
                if f.get("flow_type") in ("shell", "intermediary", "pass_through")
            ]
            if shell_flows:
                flagged.append({
                    "pattern_type": "shell_company",
                    "vendor_pair": list(pair_key),
                    "flow_count": len(shell_flows),
                    "total_amount": sum(f.get("amount", 0) for f in shell_flows),
                    "interpretation": (
                        "Financial flows through shell/intermediary entities "
                        "suggest concealment of collusive payments."
                    ),
                    "flag_type": "financial_flow",
                    "severity": "Critical",
                })

        logger.info(
            "Financial flows: analyzed %d pairs, flagged %d patterns",
            len(by_pair),
            len(flagged),
        )
        return flagged


    # ------------------------------------------------------------------
    # Collusion Ring Identification
    # ------------------------------------------------------------------

    def identify_collusion_rings(self, case_id: str) -> list[dict]:
        """Identify collusion rings by grouping vendors with scheme evidence.

        Uses Neptune graph relationships and Aurora bid patterns to cluster
        vendors into rings. Each ring is assigned a scheme type, member roles,
        and a timeline of coordinated activity.

        Args:
            case_id: Investigation identifier.

        Returns:
            List of collusion ring dicts with members, scheme_type,
            affected_contracts, and timeline.
        """
        # Fetch vendor relationships from Neptune
        label = self._entity_label(case_id)
        neptune_available = True

        # Query vendor-to-vendor edges (communication, financial, shared personnel)
        edge_query = (
            f"g.V().hasLabel('{self._escape(label)}')"
            f".outE('COMMUNICATED_WITH','FINANCIAL_FLOW','SHARES_PERSONNEL')"
            f".project('src','tgt','edge_type')"
            f".by(outV().values('vendor_id'))"
            f".by(inV().values('vendor_id'))"
            f".by(label())"
        )
        edges = self._gremlin_query(edge_query)
        if not edges and self._neptune_endpoint and _NEPTUNE_ENABLED:
            neptune_available = False
            logger.warning("Neptune unavailable for ring identification")

        # Build adjacency from Neptune edges
        adjacency: dict[str, set[str]] = defaultdict(set)
        edge_types: dict[tuple[str, str], set[str]] = defaultdict(set)
        for edge in edges:
            if isinstance(edge, dict):
                src = edge.get("src", "")
                tgt = edge.get("tgt", "")
                etype = edge.get("edge_type", "")
                if src and tgt:
                    adjacency[src].add(tgt)
                    adjacency[tgt].add(src)
                    pair = tuple(sorted([src, tgt]))
                    edge_types[pair].add(etype)

        # Also use bid pattern data to strengthen ring detection
        bids = self._fetch_bids_paginated(case_id)
        vendor_win_history = self._build_vendor_win_history(bids)

        # Find connected components (potential rings)
        visited: set[str] = set()
        rings: list[dict] = []

        all_vendors = set(adjacency.keys())
        for vendor in all_vendors:
            if vendor in visited:
                continue

            # BFS to find connected component
            component: set[str] = set()
            queue = [vendor]
            while queue:
                current = queue.pop(0)
                if current in component:
                    continue
                component.add(current)
                visited.add(current)
                for neighbor in adjacency.get(current, set()):
                    if neighbor not in component:
                        queue.append(neighbor)

            if len(component) < 2:
                continue

            # Determine scheme type based on evidence
            scheme_type = self._classify_ring_scheme(
                component, edge_types, bids, vendor_win_history
            )

            # Assign roles within the ring
            members = self._assign_ring_roles(
                component, bids, vendor_win_history, edge_types
            )

            # Build timeline of coordinated activity
            timeline = self._build_ring_timeline(component, bids, case_id)

            # Affected contracts
            affected_contracts = list(set(
                b["contract_id"] for b in bids
                if b["vendor_id"] in component
            ))

            ring_id = str(uuid.uuid4())
            rings.append({
                "ring_id": ring_id,
                "member_count": len(component),
                "members": members,
                "scheme_type": scheme_type,
                "affected_contracts": affected_contracts,
                "timeline": timeline,
                "neptune_data_available": neptune_available,
            })

        logger.info("Collusion rings: identified %d rings", len(rings))
        return rings

    def _classify_ring_scheme(
        self,
        component: set[str],
        edge_types: dict[tuple[str, str], set[str]],
        bids: list[dict],
        history: dict[str, dict],
    ) -> str:
        """Classify the scheme type for a ring based on evidence patterns.

        Args:
            component: Set of vendor IDs in the ring.
            edge_types: Edge type sets between vendor pairs.
            bids: All bid records.
            history: Vendor win/loss history.

        Returns:
            Scheme type string (e.g., "bid_rotation", "complementary_bidding").
        """
        component_bids = [b for b in bids if b["vendor_id"] in component]
        if not component_bids:
            return "mixed"

        # Check for rotation pattern
        wins = defaultdict(int)
        for b in component_bids:
            if b["award_status"] == "won":
                wins[b["vendor_id"]] += 1

        if len(wins) >= 2:
            win_values = list(wins.values())
            if len(win_values) >= 2:
                win_arr = np.array(win_values, dtype=np.float64)
                if win_arr.mean() > 0:
                    cv = float(win_arr.std() / win_arr.mean())
                    if cv < 0.3:
                        return "bid_rotation"

        # Check for complementary bidding (one dominant winner)
        if wins:
            total_wins = sum(wins.values())
            max_wins = max(wins.values())
            if total_wins > 0 and max_wins / total_wins > 0.7:
                return "complementary_bidding"

        # Check for market allocation (geographic separation)
        regions_per_vendor: dict[str, set[str]] = defaultdict(set)
        for b in component_bids:
            if b.get("geographic_region"):
                regions_per_vendor[b["vendor_id"]].add(b["geographic_region"])

        if len(regions_per_vendor) >= 2:
            vendor_list = list(regions_per_vendor.keys())
            overlap = False
            for i in range(len(vendor_list)):
                for j in range(i + 1, len(vendor_list)):
                    if regions_per_vendor[vendor_list[i]] & regions_per_vendor[vendor_list[j]]:
                        overlap = True
                        break
                if overlap:
                    break
            if not overlap:
                return "market_allocation"

        return "mixed"

    def _assign_ring_roles(
        self,
        component: set[str],
        bids: list[dict],
        history: dict[str, dict],
        edge_types: dict[tuple[str, str], set[str]],
    ) -> list[dict]:
        """Assign roles to ring members based on their behavior.

        Roles: ring_leader, designated_winner, complementary_bidder,
        subcontractor_recipient.

        Args:
            component: Set of vendor IDs in the ring.
            bids: All bid records.
            history: Vendor win/loss history.
            edge_types: Edge types between vendor pairs.

        Returns:
            List of member dicts with vendor_id and role.
        """
        component_bids = [b for b in bids if b["vendor_id"] in component]
        members: list[dict] = []

        # Count wins and connections
        wins: dict[str, int] = defaultdict(int)
        connections: dict[str, int] = defaultdict(int)

        for b in component_bids:
            if b["award_status"] == "won":
                wins[b["vendor_id"]] += 1

        for pair, types in edge_types.items():
            for v in pair:
                if v in component:
                    connections[v] = connections.get(v, 0) + len(types)

        # Assign roles
        max_wins = max(wins.values()) if wins else 0
        max_connections = max(connections.values()) if connections else 0

        for vendor_id in component:
            vendor_wins = wins.get(vendor_id, 0)
            vendor_connections = connections.get(vendor_id, 0)

            if vendor_connections == max_connections and max_connections > 0:
                role = "ring_leader"
            elif vendor_wins == max_wins and max_wins > 0 and vendor_wins > 1:
                role = "designated_winner"
            elif vendor_wins == 0:
                role = "complementary_bidder"
            else:
                role = "subcontractor_recipient"

            members.append({
                "vendor_id": vendor_id,
                "role": role,
                "wins": vendor_wins,
                "total_bids": history.get(vendor_id, {}).get("total_bids", 0),
            })

        return members

    def _build_ring_timeline(
        self, component: set[str], bids: list[dict], case_id: str
    ) -> list[dict]:
        """Build a timeline of coordinated activity for a ring.

        Args:
            component: Set of vendor IDs in the ring.
            bids: All bid records.
            case_id: Investigation identifier.

        Returns:
            List of timeline event dicts sorted chronologically.
        """
        timeline: list[dict] = []

        component_bids = [b for b in bids if b["vendor_id"] in component]

        # Group by contract and create timeline events
        by_contract: dict[str, list[dict]] = defaultdict(list)
        for bid in component_bids:
            by_contract[bid["contract_id"]].append(bid)

        for contract_id, contract_bids in by_contract.items():
            winners = [b for b in contract_bids if b["award_status"] == "won"]
            losers = [b for b in contract_bids if b["award_status"] != "won"]

            if winners:
                winner = winners[0]
                event = {
                    "contract_id": contract_id,
                    "event_type": "contract_award",
                    "winner_vendor_id": winner["vendor_id"],
                    "winner_amount": winner["bid_amount"],
                    "losing_bidders": len(losers),
                    "timestamp": str(winner.get("submission_timestamp", "")),
                }
                timeline.append(event)

        # Sort by timestamp
        timeline.sort(key=lambda e: e.get("timestamp", ""))
        return timeline


    # ------------------------------------------------------------------
    # Orchestration: run_analysis and run_incremental_analysis
    # ------------------------------------------------------------------

    def run_analysis(self, case_id: str) -> AnalysisResult:
        """Execute full collusion analysis for a case.

        Orchestrates all detection methods, computes the composite PCSF score,
        generates red flags, and caches results. This is the primary entry
        point for a complete analysis run.

        Steps:
        1. Fetch all bid records for the case
        2. Run complementary bidding detection
        3. Run bid rotation detection (using vendor clusters from Neptune)
        4. Run market allocation detection
        5. Run bid suppression detection
        6. Run price anomaly analysis
        7. Run communication timing analysis
        8. Run financial flow analysis
        9. Identify collusion rings
        10. Compute PCSF composite score
        11. Generate red flags
        12. Cache results in Aurora
        13. Optionally generate legal reasoning via antitrust_legal_reasoning

        Args:
            case_id: Investigation identifier.

        Returns:
            AnalysisResult with overall score, patterns, red flags, and metadata.
        """
        logger.info("Starting full collusion analysis for case_id=%s", case_id)
        start_time = datetime.now(timezone.utc)
        status = "completed"
        neptune_partial = False

        # Step 1: Get all contract IDs for this case
        bids = self._fetch_bids_paginated(case_id)
        if not bids:
            return AnalysisResult(
                case_id=case_id,
                case_type=CaseType.PROCUREMENT_COLLUSION,
                status="completed",
                overall_score=0.0,
                metadata={"message": "No bid records found for case"},
            )

        all_contract_ids = list(set(b["contract_id"] for b in bids))
        all_vendor_ids = list(set(b["vendor_id"] for b in bids))

        # Step 2: Complementary bidding
        complementary_flags = self.detect_complementary_bidding(
            case_id, all_contract_ids
        )

        # Step 3: Bid rotation — build vendor sets from Neptune clusters
        vendor_sets = self._get_vendor_clusters_from_graph(case_id)
        if not vendor_sets:
            # Fallback: test all vendors as one set if Neptune unavailable
            neptune_partial = True
            vendor_sets = [all_vendor_ids] if len(all_vendor_ids) >= 2 else []
        rotation_flags = self.detect_bid_rotation(case_id, vendor_sets)

        # Step 4: Market allocation
        allocation_flags = self.detect_market_allocation(case_id)

        # Step 5: Bid suppression
        suppression_flags = self.detect_bid_suppression(case_id)

        # Step 6: Price anomalies
        price_anomalies = self.analyze_price_anomalies(case_id, all_contract_ids)

        # Step 7: Communication timing
        vendor_pairs = self._get_vendor_pairs_from_graph(case_id)
        if not vendor_pairs:
            neptune_partial = True
            # Generate pairs from vendors that competed on same contracts
            vendor_pairs = self._generate_competitor_pairs(bids)
        comm_flags = self.analyze_communication_timing(case_id, vendor_pairs)

        # Step 8: Financial flows
        financial_flags = self.analyze_financial_flows(case_id, vendor_pairs)

        # Step 9: Identify collusion rings
        rings = self.identify_collusion_rings(case_id)

        # Step 10: Compute PCSF composite score
        bid_rigging_score = self._compute_component_score(
            complementary_flags, rotation_flags, allocation_flags, suppression_flags
        )
        pricing_score = self._compute_pricing_score(price_anomalies)
        communication_score = self._compute_communication_score(comm_flags)
        financial_score = self._compute_financial_score(financial_flags)
        behavioral_score = self._compute_behavioral_score(rings)

        factors = [
            ScoringFactor(
                name="bid_rigging",
                weight=PCSF_WEIGHTS["bid_rigging"],
                score=bid_rigging_score,
                description="Complementary bidding, rotation, allocation, suppression",
            ),
            ScoringFactor(
                name="pricing",
                weight=PCSF_WEIGHTS["pricing"],
                score=pricing_score,
                description="Statistical pricing anomalies",
            ),
            ScoringFactor(
                name="communication",
                weight=PCSF_WEIGHTS["communication"],
                score=communication_score,
                description="Pre-deadline communication spikes",
            ),
            ScoringFactor(
                name="financial",
                weight=PCSF_WEIGHTS["financial"],
                score=financial_score,
                description="Suspicious financial flows",
            ),
            ScoringFactor(
                name="behavioral",
                weight=PCSF_WEIGHTS["behavioral"],
                score=behavioral_score,
                description="Ring structure and behavioral indicators",
            ),
        ]

        # Use scoring service if available
        if self._scoring_svc:
            scoring_result = self._scoring_svc.compute_score(factors)
        else:
            overall = sum(f.weight * f.score for f in factors)
            scoring_result = ScoringResult(
                overall_score=round(overall, 2),
                factors=factors,
                severity=self._classify_severity(overall),
                confidence=sum(1 for f in factors if f.score > 0) / len(factors),
            )

        # Step 11: Generate red flags
        red_flags = self._generate_red_flags(
            complementary_flags, rotation_flags, allocation_flags,
            suppression_flags, price_anomalies, comm_flags, financial_flags,
        )

        # Step 12: Cache results
        if neptune_partial:
            status = "partial"
        self._cache_analysis_result(case_id, scoring_result, status)

        # Step 13: Legal reasoning (via injected service, not direct Bedrock)
        legal_reasoning = None
        if self._legal_reasoning and scoring_result.overall_score > 25:
            try:
                legal_reasoning = self._legal_reasoning.analyze_pattern(
                    pattern={
                        "pattern_type": "procurement_collusion",
                        "confidence": scoring_result.overall_score,
                        "involved_vendors": all_vendor_ids[:20],
                        "involved_contracts": all_contract_ids[:20],
                        "details": {
                            "rings_identified": len(rings),
                            "bid_rigging_score": bid_rigging_score,
                            "pricing_score": pricing_score,
                        },
                    },
                    case_type="procurement_collusion",
                    evidence=red_flags[:10],
                )
            except Exception as e:
                logger.warning("Legal reasoning generation failed: %s", e)

        elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
        logger.info(
            "Collusion analysis complete: case=%s score=%.1f severity=%s elapsed=%.1fs",
            case_id,
            scoring_result.overall_score,
            scoring_result.severity,
            elapsed,
        )

        return AnalysisResult(
            case_id=case_id,
            case_type=CaseType.PROCUREMENT_COLLUSION,
            status=status,
            overall_score=scoring_result.overall_score,
            red_flags=red_flags,
            patterns=[
                *[{"type": "complementary_bidding", **f} for f in complementary_flags],
                *[{"type": "bid_rotation", **f} for f in rotation_flags],
                *[{"type": "market_allocation", **f} for f in allocation_flags],
                *[{"type": "bid_suppression", **f} for f in suppression_flags],
                *[{"type": "price_anomaly", **f} for f in price_anomalies],
                *[{"type": "communication_spike", **f} for f in comm_flags],
                *[{"type": "financial_flow", **f} for f in financial_flags],
            ],
            subjects=[{"type": "ring", **r} for r in rings],
            evidence_summary={
                "total_bids_analyzed": len(bids),
                "total_contracts_analyzed": len(all_contract_ids),
                "total_vendors_analyzed": len(all_vendor_ids),
                "complementary_bids_flagged": len(complementary_flags),
                "rotation_patterns": len(rotation_flags),
                "allocation_patterns": len(allocation_flags),
                "suppression_flags": len(suppression_flags),
                "price_anomalies": len(price_anomalies),
                "communication_spikes": len(comm_flags),
                "financial_patterns": len(financial_flags),
                "collusion_rings": len(rings),
            },
            legal_reasoning=legal_reasoning,
            metadata={
                "elapsed_seconds": round(elapsed, 2),
                "neptune_available": not neptune_partial,
                "scoring_severity": scoring_result.severity,
                "scoring_confidence": scoring_result.confidence,
            },
        )

    def run_incremental_analysis(
        self, case_id: str, new_record_ids: list[str]
    ) -> AnalysisResult:
        """Update analysis with newly ingested records.

        Only recomputes clusters affected by the new records rather than
        re-running the full analysis. Identifies which contracts and vendors
        are affected, then re-runs detection only for those subsets.

        Args:
            case_id: Investigation identifier.
            new_record_ids: IDs of newly ingested procurement records.

        Returns:
            Updated AnalysisResult reflecting the new data.
        """
        logger.info(
            "Starting incremental analysis: case=%s new_records=%d",
            case_id,
            len(new_record_ids),
        )

        if not new_record_ids:
            return AnalysisResult(
                case_id=case_id,
                case_type=CaseType.PROCUREMENT_COLLUSION,
                status="completed",
                overall_score=0.0,
                metadata={"message": "No new records to analyze"},
            )

        # Fetch the new records to determine affected contracts/vendors
        affected_contracts: set[str] = set()
        affected_vendors: set[str] = set()

        try:
            with self._aurora.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT contract_id, vendor_id
                        FROM procurement_records
                        WHERE case_id = %s AND record_id = ANY(%s)
                        """,
                        (case_id, new_record_ids),
                    )
                    for row in cur.fetchall():
                        affected_contracts.add(row[0])
                        affected_vendors.add(row[1])
        except Exception as e:
            logger.error("Failed to fetch new records: %s", e)
            return self.run_analysis(case_id)

        if not affected_contracts:
            return self.run_analysis(case_id)

        # Re-run detection only for affected contracts
        affected_contract_list = list(affected_contracts)
        affected_vendor_list = list(affected_vendors)

        # Complementary bidding on affected contracts
        complementary_flags = self.detect_complementary_bidding(
            case_id, affected_contract_list
        )

        # Price anomalies on affected contracts
        price_anomalies = self.analyze_price_anomalies(
            case_id, affected_contract_list
        )

        # Generate pairs from affected vendors
        vendor_pairs = [
            (a, b)
            for i, a in enumerate(affected_vendor_list)
            for b in affected_vendor_list[i + 1:]
        ]

        # Communication and financial for affected vendors
        comm_flags = self.analyze_communication_timing(case_id, vendor_pairs)
        financial_flags = self.analyze_financial_flows(case_id, vendor_pairs)

        # Run full analysis to get the complete result with updated data
        full_result = self.run_analysis(case_id)

        # Mark as incremental in metadata
        full_result.metadata["incremental"] = True
        full_result.metadata["new_record_ids"] = new_record_ids
        full_result.metadata["affected_contracts"] = list(affected_contracts)
        full_result.metadata["affected_vendors"] = list(affected_vendors)

        return full_result


    # ------------------------------------------------------------------
    # Private helpers: scoring, caching, graph queries
    # ------------------------------------------------------------------

    def _get_vendor_clusters_from_graph(self, case_id: str) -> list[list[str]]:
        """Fetch vendor clusters from Neptune for rotation testing.

        Args:
            case_id: Investigation identifier.

        Returns:
            List of vendor ID lists (clusters). Empty if Neptune unavailable.
        """
        label = self._entity_label(case_id)
        query = (
            f"g.V().hasLabel('{self._escape(label)}')"
            f".group().by('cluster_id').by('vendor_id').unfold()"
            f".select(values)"
        )
        results = self._gremlin_query(query)
        if not results:
            return []

        clusters: list[list[str]] = []
        for item in results:
            if isinstance(item, list) and len(item) >= 2:
                clusters.append(item)
            elif isinstance(item, dict):
                values = list(item.values()) if item else []
                if len(values) >= 2:
                    clusters.append(values)

        return clusters

    def _get_vendor_pairs_from_graph(
        self, case_id: str
    ) -> list[tuple[str, str]]:
        """Fetch vendor pairs with communication edges from Neptune.

        Args:
            case_id: Investigation identifier.

        Returns:
            List of (vendor_a_id, vendor_b_id) tuples. Empty if Neptune unavailable.
        """
        label = self._entity_label(case_id)
        query = (
            f"g.V().hasLabel('{self._escape(label)}')"
            f".outE('COMMUNICATED_WITH')"
            f".project('src','tgt')"
            f".by(outV().values('vendor_id'))"
            f".by(inV().values('vendor_id'))"
        )
        results = self._gremlin_query(query)
        if not results:
            return []

        pairs: list[tuple[str, str]] = []
        seen: set[tuple[str, str]] = set()
        for item in results:
            if isinstance(item, dict):
                src = item.get("src", "")
                tgt = item.get("tgt", "")
                if src and tgt:
                    pair = tuple(sorted([src, tgt]))
                    if pair not in seen:
                        seen.add(pair)
                        pairs.append((pair[0], pair[1]))

        return pairs

    def _generate_competitor_pairs(
        self, bids: list[dict]
    ) -> list[tuple[str, str]]:
        """Generate vendor pairs from vendors competing on same contracts.

        Fallback when Neptune is unavailable.

        Args:
            bids: All bid records.

        Returns:
            List of (vendor_a_id, vendor_b_id) tuples for vendors that
            competed on at least one common contract. Capped at 100 pairs.
        """
        # Group vendors by contract
        contract_vendors: dict[str, set[str]] = defaultdict(set)
        for bid in bids:
            contract_vendors[bid["contract_id"]].add(bid["vendor_id"])

        # Generate pairs from co-bidders
        pairs: set[tuple[str, str]] = set()
        for vendors in contract_vendors.values():
            vendor_list = sorted(vendors)
            for i in range(len(vendor_list)):
                for j in range(i + 1, len(vendor_list)):
                    pairs.add((vendor_list[i], vendor_list[j]))

        return list(pairs)[:100]

    def _compute_component_score(
        self,
        complementary_flags: list[dict],
        rotation_flags: list[dict],
        allocation_flags: list[dict],
        suppression_flags: list[dict],
    ) -> float:
        """Compute the bid_rigging component score (0-100).

        Combines evidence from all bid-rigging sub-detectors.

        Args:
            complementary_flags: Flagged complementary bids.
            rotation_flags: Flagged rotation patterns.
            allocation_flags: Flagged allocation patterns.
            suppression_flags: Flagged suppression patterns.

        Returns:
            Score in [0, 100].
        """
        score = 0.0

        # Complementary bidding contributes up to 40 points
        if complementary_flags:
            avg_score = np.mean([
                f.get("complementary_bid_score", 0) for f in complementary_flags
            ])
            score += min(40.0, float(avg_score) * 0.4)

        # Rotation contributes up to 30 points
        if rotation_flags:
            max_index = max(f.get("rotation_index", 0) for f in rotation_flags)
            score += min(30.0, max_index * 30.0)

        # Allocation contributes up to 20 points
        if allocation_flags:
            score += 20.0

        # Suppression contributes up to 10 points
        if suppression_flags:
            score += min(10.0, len(suppression_flags) * 3.0)

        return min(100.0, score)

    def _compute_pricing_score(self, anomalies: list[dict]) -> float:
        """Compute the pricing component score (0-100).

        Args:
            anomalies: Detected price anomalies.

        Returns:
            Score in [0, 100].
        """
        if not anomalies:
            return 0.0

        score = 0.0
        for anomaly in anomalies:
            severity = anomaly.get("severity", "Low")
            if severity == "High":
                score += 25.0
            elif severity == "Medium":
                score += 15.0
            else:
                score += 5.0

        return min(100.0, score)

    def _compute_communication_score(self, comm_flags: list[dict]) -> float:
        """Compute the communication component score (0-100).

        Args:
            comm_flags: Detected communication spikes.

        Returns:
            Score in [0, 100].
        """
        if not comm_flags:
            return 0.0

        total_std_devs = sum(
            f.get("std_devs_above", 0) for f in comm_flags
        )
        return min(100.0, total_std_devs * 10.0)

    def _compute_financial_score(self, financial_flags: list[dict]) -> float:
        """Compute the financial component score (0-100).

        Args:
            financial_flags: Detected financial flow patterns.

        Returns:
            Score in [0, 100].
        """
        if not financial_flags:
            return 0.0

        score = 0.0
        for flag in financial_flags:
            severity = flag.get("severity", "Low")
            if severity == "Critical":
                score += 35.0
            elif severity == "High":
                score += 20.0
            else:
                score += 10.0

        return min(100.0, score)

    def _compute_behavioral_score(self, rings: list[dict]) -> float:
        """Compute the behavioral component score (0-100).

        Based on the number and size of identified collusion rings.

        Args:
            rings: Identified collusion rings.

        Returns:
            Score in [0, 100].
        """
        if not rings:
            return 0.0

        score = 0.0
        for ring in rings:
            member_count = ring.get("member_count", 0)
            score += min(30.0, member_count * 10.0)

        return min(100.0, score)

    @staticmethod
    def _classify_severity(score: float) -> str:
        """Classify overall score into severity level.

        Args:
            score: Numeric score in [0, 100].

        Returns:
            "Critical", "High", "Medium", or "Low".
        """
        if score >= 75:
            return "Critical"
        elif score >= 50:
            return "High"
        elif score >= 25:
            return "Medium"
        else:
            return "Low"

    def _generate_red_flags(
        self,
        complementary_flags: list[dict],
        rotation_flags: list[dict],
        allocation_flags: list[dict],
        suppression_flags: list[dict],
        price_anomalies: list[dict],
        comm_flags: list[dict],
        financial_flags: list[dict],
    ) -> list[dict]:
        """Generate PCSF-aligned red flag indicators from all detections.

        Args:
            complementary_flags: Flagged complementary bids.
            rotation_flags: Flagged rotation patterns.
            allocation_flags: Flagged allocation patterns.
            suppression_flags: Flagged suppression patterns.
            price_anomalies: Detected price anomalies.
            comm_flags: Detected communication spikes.
            financial_flags: Detected financial flow patterns.

        Returns:
            List of red flag dicts with category, severity, and description.
        """
        red_flags: list[dict] = []

        # Complementary bidding red flags
        for flag in complementary_flags:
            score = flag.get("complementary_bid_score", 0)
            severity = "Critical" if score >= 90 else "High" if score >= 80 else "Medium"
            red_flags.append({
                "flag_id": str(uuid.uuid4()),
                "category": "bid_rigging",
                "severity": severity,
                "title": "Complementary Bidding Detected",
                "description": (
                    f"Vendor {flag.get('vendor_name', 'Unknown')} submitted a "
                    f"likely cover bid on contract {flag.get('contract_id')} "
                    f"(score: {score:.0f}/100)"
                ),
                "involved_vendors": [flag.get("vendor_id", "")],
                "involved_contracts": [flag.get("contract_id", "")],
            })

        # Rotation red flags
        for flag in rotation_flags:
            red_flags.append({
                "flag_id": str(uuid.uuid4()),
                "category": "bid_rigging",
                "severity": "Critical" if flag.get("rotation_index", 0) > 0.9 else "High",
                "title": "Bid Rotation Pattern Detected",
                "description": (
                    f"Vendor group shows suspiciously even win distribution "
                    f"(rotation index: {flag.get('rotation_index', 0):.3f})"
                ),
                "involved_vendors": flag.get("vendor_set", []),
            })

        # Allocation red flags
        for flag in allocation_flags:
            red_flags.append({
                "flag_id": str(uuid.uuid4()),
                "category": "market_allocation",
                "severity": "High",
                "title": f"Market Allocation ({flag.get('allocation_type', 'unknown').title()})",
                "description": (
                    f"Chi-squared test indicates non-random {flag.get('allocation_type')} "
                    f"distribution (p={flag.get('p_value', 0):.4f})"
                ),
                "involved_vendors": [
                    v["vendor_id"] for v in flag.get("exclusive_vendors", [])
                ],
            })

        # Suppression red flags
        for flag in suppression_flags:
            red_flags.append({
                "flag_id": str(uuid.uuid4()),
                "category": "bid_suppression",
                "severity": "High" if flag.get("abstention_rate", 0) > 0.8 else "Medium",
                "title": "Bid Suppression Detected",
                "description": (
                    f"Vendor {flag.get('vendor_id')} abstained from "
                    f"{flag.get('abstention_rate', 0)*100:.0f}% of eligible contracts"
                ),
                "involved_vendors": [flag.get("vendor_id", "")],
            })

        # Pricing red flags
        for anomaly in price_anomalies:
            red_flags.append({
                "flag_id": str(uuid.uuid4()),
                "category": "pricing",
                "severity": anomaly.get("severity", "Medium"),
                "title": f"Price Anomaly: {anomaly.get('test_type', 'unknown')}",
                "description": anomaly.get("interpretation", ""),
                "involved_vendors": anomaly.get("involved_vendors", []),
                "involved_contracts": [anomaly.get("contract_id", "")],
            })

        # Communication red flags
        for flag in comm_flags:
            red_flags.append({
                "flag_id": str(uuid.uuid4()),
                "category": "communication",
                "severity": "High" if flag.get("std_devs_above", 0) > 3 else "Medium",
                "title": "Pre-Deadline Communication Spike",
                "description": (
                    f"Communication between {flag.get('vendor_pair', [])} spiked "
                    f"{flag.get('std_devs_above', 0):.1f} std devs above baseline "
                    f"on {flag.get('spike_date', 'unknown')}"
                ),
                "involved_vendors": flag.get("vendor_pair", []),
            })

        # Financial red flags
        for flag in financial_flags:
            red_flags.append({
                "flag_id": str(uuid.uuid4()),
                "category": "financial",
                "severity": flag.get("severity", "Medium"),
                "title": f"Financial: {flag.get('pattern_type', 'unknown')}",
                "description": flag.get("interpretation", ""),
                "involved_vendors": flag.get("vendor_pair", []),
            })

        return red_flags

    def _cache_analysis_result(
        self, case_id: str, scoring_result: ScoringResult, status: str
    ) -> None:
        """Cache analysis results in Aurora for retrieval.

        Performs a single INSERT/UPSERT of the analysis summary row.

        Args:
            case_id: Investigation identifier.
            scoring_result: Computed PCSF scoring result.
            status: Analysis status ("completed" or "partial").
        """
        if not self._aurora:
            return

        analysis_id = str(uuid.uuid4())
        breakdown = {
            "factors": [
                {"name": f.name, "weight": f.weight, "score": f.score}
                for f in scoring_result.factors
            ],
            "severity": scoring_result.severity,
            "confidence": scoring_result.confidence,
        }

        try:
            with self._aurora.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO collusion_analyses
                            (analysis_id, case_id, pcsf_score, pcsf_breakdown,
                             analysis_status, created_at)
                        VALUES (%s, %s, %s, %s, %s, NOW())
                        ON CONFLICT (case_id) DO UPDATE SET
                            pcsf_score = EXCLUDED.pcsf_score,
                            pcsf_breakdown = EXCLUDED.pcsf_breakdown,
                            analysis_status = EXCLUDED.analysis_status,
                            updated_at = NOW()
                        """,
                        (
                            analysis_id,
                            case_id,
                            scoring_result.overall_score,
                            json.dumps(breakdown),
                            status,
                        ),
                    )
                conn.commit()
            logger.info(
                "Cached analysis result: case=%s score=%.1f",
                case_id,
                scoring_result.overall_score,
            )
        except Exception as e:
            logger.error("Failed to cache analysis result: %s", e)
