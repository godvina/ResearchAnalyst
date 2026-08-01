"""Cross-Case Pattern Detector - Redshift analytical queries for antitrust patterns.

Runs analytical queries across all procurement data in Redshift to detect
patterns spanning multiple jurisdictions and time periods. Identifies bid
rotation, market allocation, price fixing, and win-rate anomalies. When
patterns are statistically significant (p-value < 0.01), automatically
creates new pre-case leads.

Usage:
    detector = CrossCasePatternDetector(
        redshift_client=redshift_data_client,
        aurora_cm=connection_manager,
        bedrock_client=bedrock_runtime,
    )
    patterns = detector.detect_bid_rotation({"min_co_bids": 5})
    leads = detector.auto_create_leads(patterns)
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Redshift database name
REDSHIFT_DATABASE = "pre_case_analytics"

# Statistical significance threshold for auto-creating leads
P_VALUE_THRESHOLD = 0.01

# Default parameters for pattern detection
DEFAULT_PARAMS = {
    "min_co_bids": 5,
    "min_win_rate": 0.70,
    "min_contracts": 10,
    "lookback_days": 730,  # 2 years
    "min_bid_spread_correlation": 0.85,
}


class CrossCasePatternDetector:
    """Detects cross-case antitrust patterns in Redshift procurement data.

    Follows Protocol/constructor-injection pattern for testability.
    Uses Redshift Data API (execute_statement + describe_statement polling)
    for analytical queries across millions of bid records.
    """

    def __init__(
        self,
        redshift_client: Any,
        aurora_cm: Any,
        bedrock_client: Any = None,
    ) -> None:
        """Initialize with dependencies.

        Args:
            redshift_client: boto3 redshift-data client for execute_statement.
            aurora_cm: Aurora PostgreSQL connection manager with cursor() context.
            bedrock_client: Optional boto3 Bedrock Runtime client (for future
                AI-enhanced pattern analysis).
        """
        self.redshift_client = redshift_client
        self.aurora_cm = aurora_cm
        self.bedrock_client = bedrock_client

    # ------------------------------------------------------------------
    # Public API - Pattern Detection
    # ------------------------------------------------------------------

    def detect_bid_rotation(self, params: dict = None) -> list:
        """Detect consistent winner/loser pairs across jurisdictions.

        Finds vendor pairs that appear together in competitive bids across
        multiple jurisdictions with consistent winner/loser patterns,
        flagging potential multi-state bid rotation schemes.

        Args:
            params: Optional dict with min_co_bids, lookback_days.

        Returns:
            List of detected bid rotation patterns with statistical details.
        """
        p = {**DEFAULT_PARAMS, **(params or {})}

        sql = """
            WITH bid_pairs AS (
                SELECT
                    a.vendor_id AS vendor_a,
                    b.vendor_id AS vendor_b,
                    a.contract_id,
                    a.state,
                    a.bid_amount AS bid_a,
                    b.bid_amount AS bid_b,
                    CASE WHEN a.award_status = 'awarded' THEN a.vendor_id
                         WHEN b.award_status = 'awarded' THEN b.vendor_id
                         ELSE NULL END AS winner
                FROM bid_tabulations a
                JOIN bid_tabulations b
                    ON a.contract_id = b.contract_id
                    AND a.vendor_id < b.vendor_id
                WHERE a.submission_date >= DATEADD(day, -{lookback}, CURRENT_DATE)
            ),
            pair_stats AS (
                SELECT
                    vendor_a,
                    vendor_b,
                    COUNT(*) AS co_bid_count,
                    COUNT(DISTINCT state) AS jurisdictions,
                    SUM(CASE WHEN winner = vendor_a THEN 1 ELSE 0 END) AS a_wins,
                    SUM(CASE WHEN winner = vendor_b THEN 1 ELSE 0 END) AS b_wins,
                    POWER(
                        ABS(SUM(CASE WHEN winner = vendor_a THEN 1 ELSE 0 END)
                            - SUM(CASE WHEN winner = vendor_b THEN 1 ELSE 0 END)),
                        2
                    ) / GREATEST(COUNT(*), 1) AS rotation_score
                FROM bid_pairs
                WHERE winner IS NOT NULL
                GROUP BY vendor_a, vendor_b
                HAVING COUNT(*) >= {min_co_bids}
            )
            SELECT
                vendor_a, vendor_b, co_bid_count, jurisdictions,
                a_wins, b_wins, rotation_score,
                EXP(-0.5 * rotation_score) AS p_value
            FROM pair_stats
            WHERE co_bid_count >= {min_co_bids}
            ORDER BY rotation_score DESC
            LIMIT 100
        """.format(
            lookback=p["lookback_days"],
            min_co_bids=p["min_co_bids"],
        )

        results = self._execute_query(sql)
        patterns = []

        for row in results:
            p_value = float(row[7]) if len(row) > 7 and row[7] else 1.0
            patterns.append({
                "pattern_type": "bid_rotation",
                "vendor_a": row[0],
                "vendor_b": row[1],
                "co_bid_count": int(row[2]) if row[2] else 0,
                "jurisdictions": int(row[3]) if row[3] else 0,
                "a_wins": int(row[4]) if row[4] else 0,
                "b_wins": int(row[5]) if row[5] else 0,
                "rotation_score": float(row[6]) if row[6] else 0.0,
                "p_value": p_value,
                "statistically_significant": p_value < P_VALUE_THRESHOLD,
                "detected_at": datetime.now(timezone.utc).isoformat(),
            })

        return patterns

    def detect_market_allocation(self, params: dict = None) -> list:
        """Detect geographic exclusivity patterns.

        Finds vendors that consistently win contracts in specific geographic
        regions while never competing in adjacent regions, flagging potential
        market allocation agreements.

        Args:
            params: Optional dict with min_contracts, min_win_rate.

        Returns:
            List of detected market allocation patterns.
        """
        p = {**DEFAULT_PARAMS, **(params or {})}

        sql = """
            WITH vendor_geo AS (
                SELECT
                    vendor_id,
                    state,
                    COUNT(*) AS total_bids,
                    SUM(CASE WHEN award_status = 'awarded' THEN 1 ELSE 0 END) AS wins,
                    ROUND(
                        SUM(CASE WHEN award_status = 'awarded' THEN 1.0 ELSE 0 END)
                        / GREATEST(COUNT(*), 1) * 100, 2
                    ) AS win_rate_pct
                FROM bid_tabulations
                WHERE submission_date >= DATEADD(day, -{lookback}, CURRENT_DATE)
                GROUP BY vendor_id, state
                HAVING COUNT(*) >= {min_contracts}
            ),
            exclusive_vendors AS (
                SELECT
                    vendor_id,
                    COUNT(DISTINCT state) AS active_states,
                    MAX(win_rate_pct) AS max_win_rate,
                    MIN(win_rate_pct) AS min_win_rate,
                    SUM(total_bids) AS total_bids_all,
                    LISTAGG(state || ':' || CAST(win_rate_pct AS VARCHAR), ', ')
                        WITHIN GROUP (ORDER BY win_rate_pct DESC) AS state_breakdown
                FROM vendor_geo
                WHERE win_rate_pct >= {min_win_rate}
                GROUP BY vendor_id
            )
            SELECT
                ev.vendor_id,
                ev.active_states,
                ev.max_win_rate,
                ev.min_win_rate,
                ev.total_bids_all,
                ev.state_breakdown,
                (ev.max_win_rate / GREATEST(ev.active_states, 1)) AS exclusivity_score,
                POWER(1.0 - ({min_win_rate} / 100.0), ev.total_bids_all) AS p_value
            FROM exclusive_vendors ev
            WHERE ev.active_states <= 3
                AND ev.max_win_rate >= {min_win_rate}
            ORDER BY exclusivity_score DESC
            LIMIT 100
        """.format(
            lookback=p["lookback_days"],
            min_contracts=p["min_contracts"],
            min_win_rate=p["min_win_rate"] * 100,
        )

        results = self._execute_query(sql)
        patterns = []

        for row in results:
            p_value = float(row[7]) if len(row) > 7 and row[7] else 1.0
            patterns.append({
                "pattern_type": "market_allocation",
                "vendor_id": row[0],
                "active_states": int(row[1]) if row[1] else 0,
                "max_win_rate": float(row[2]) if row[2] else 0.0,
                "min_win_rate": float(row[3]) if row[3] else 0.0,
                "total_bids": int(row[4]) if row[4] else 0,
                "state_breakdown": row[5] or "",
                "exclusivity_score": float(row[6]) if row[6] else 0.0,
                "p_value": p_value,
                "statistically_significant": p_value < P_VALUE_THRESHOLD,
                "detected_at": datetime.now(timezone.utc).isoformat(),
            })

        return patterns

    def detect_price_fixing(self, params: dict = None) -> list:
        """Detect correlated bid spreads indicating price fixing.

        Finds pricing patterns where bid amounts across multiple unrelated
        contracts show statistical correlation (similar percentage spreads,
        synchronized price increases).

        Args:
            params: Optional dict with min_bid_spread_correlation, min_contracts.

        Returns:
            List of detected price fixing patterns.
        """
        p = {**DEFAULT_PARAMS, **(params or {})}

        sql = """
            WITH contract_spreads AS (
                SELECT
                    contract_id,
                    state,
                    submission_date,
                    MIN(bid_amount) AS min_bid,
                    MAX(bid_amount) AS max_bid,
                    AVG(bid_amount) AS avg_bid,
                    STDDEV(bid_amount) AS std_bid,
                    COUNT(*) AS bidder_count,
                    CASE WHEN AVG(bid_amount) > 0
                        THEN STDDEV(bid_amount) / AVG(bid_amount)
                        ELSE 0 END AS cv,
                    CASE WHEN MIN(bid_amount) > 0
                        THEN (MAX(bid_amount) - MIN(bid_amount)) / MIN(bid_amount)
                        ELSE 0 END AS spread_ratio
                FROM bid_tabulations
                WHERE submission_date >= DATEADD(day, -{lookback}, CURRENT_DATE)
                    AND bid_amount > 0
                GROUP BY contract_id, state, submission_date
                HAVING COUNT(*) >= 3
            ),
            suspicious_spreads AS (
                SELECT
                    state,
                    COUNT(*) AS contract_count,
                    AVG(spread_ratio) AS avg_spread,
                    STDDEV(spread_ratio) AS std_spread,
                    AVG(cv) AS avg_cv,
                    CASE WHEN AVG(cv) > 0
                        THEN 1.0 / AVG(cv)
                        ELSE 0 END AS uniformity_score,
                    CASE WHEN STDDEV(spread_ratio) > 0
                        THEN 1.0 - (STDDEV(spread_ratio) / GREATEST(AVG(spread_ratio), 0.01))
                        ELSE 0 END AS spread_correlation
                FROM contract_spreads
                GROUP BY state
                HAVING COUNT(*) >= {min_contracts}
            )
            SELECT
                state,
                contract_count,
                avg_spread,
                std_spread,
                avg_cv,
                uniformity_score,
                spread_correlation,
                EXP(-2.0 * uniformity_score) AS p_value
            FROM suspicious_spreads
            WHERE spread_correlation >= {min_correlation}
            ORDER BY uniformity_score DESC
            LIMIT 100
        """.format(
            lookback=p["lookback_days"],
            min_contracts=p["min_contracts"],
            min_correlation=p["min_bid_spread_correlation"],
        )

        results = self._execute_query(sql)
        patterns = []

        for row in results:
            p_value = float(row[7]) if len(row) > 7 and row[7] else 1.0
            patterns.append({
                "pattern_type": "price_fixing",
                "state": row[0] or "",
                "contract_count": int(row[1]) if row[1] else 0,
                "avg_spread": float(row[2]) if row[2] else 0.0,
                "std_spread": float(row[3]) if row[3] else 0.0,
                "avg_cv": float(row[4]) if row[4] else 0.0,
                "uniformity_score": float(row[5]) if row[5] else 0.0,
                "spread_correlation": float(row[6]) if row[6] else 0.0,
                "p_value": p_value,
                "statistically_significant": p_value < P_VALUE_THRESHOLD,
                "detected_at": datetime.now(timezone.utc).isoformat(),
            })

        return patterns

    def detect_win_rate_anomalies(self, params: dict = None) -> list:
        """Detect suspicious win patterns using materialized view data.

        Finds vendors with statistically improbable win rates that deviate
        significantly from expected rates given the competitive landscape.

        Args:
            params: Optional dict with min_win_rate, min_contracts.

        Returns:
            List of detected win rate anomaly patterns.
        """
        p = {**DEFAULT_PARAMS, **(params or {})}

        sql = """
            WITH avg_competition AS (
                SELECT AVG(bidder_count) AS avg_bidders
                FROM (
                    SELECT contract_id, COUNT(*) AS bidder_count
                    FROM bid_tabulations
                    GROUP BY contract_id
                )
            )
            SELECT
                wr.vendor_id,
                wr.state,
                wr.total_bids,
                wr.wins,
                wr.win_rate_pct,
                (100.0 / GREATEST(ac.avg_bidders, 2)) AS expected_win_rate,
                (wr.win_rate_pct - (100.0 / GREATEST(ac.avg_bidders, 2)))
                    / GREATEST(
                        SQRT((100.0 / GREATEST(ac.avg_bidders, 2))
                            * (1 - (1.0 / GREATEST(ac.avg_bidders, 2)))
                            / GREATEST(wr.total_bids, 1)),
                        0.01
                    ) AS z_score,
                EXP(-0.5 * POWER(
                    (wr.win_rate_pct - (100.0 / GREATEST(ac.avg_bidders, 2)))
                    / GREATEST(
                        SQRT((100.0 / GREATEST(ac.avg_bidders, 2))
                            * (1 - (1.0 / GREATEST(ac.avg_bidders, 2)))
                            / GREATEST(wr.total_bids, 1)),
                        0.01
                    ), 2
                )) AS p_value
            FROM mv_vendor_win_rates wr
            CROSS JOIN avg_competition ac
            WHERE wr.total_bids >= {min_contracts}
                AND wr.win_rate_pct >= {min_win_rate}
            ORDER BY wr.win_rate_pct DESC
            LIMIT 100
        """.format(
            min_contracts=p["min_contracts"],
            min_win_rate=p["min_win_rate"] * 100,
        )

        results = self._execute_query(sql)
        patterns = []

        for row in results:
            p_value = float(row[7]) if len(row) > 7 and row[7] else 1.0
            patterns.append({
                "pattern_type": "win_rate_anomaly",
                "vendor_id": row[0] or "",
                "state": row[1] or "",
                "total_bids": int(row[2]) if row[2] else 0,
                "wins": int(row[3]) if row[3] else 0,
                "win_rate_pct": float(row[4]) if row[4] else 0.0,
                "expected_win_rate": float(row[5]) if row[5] else 0.0,
                "z_score": float(row[6]) if row[6] else 0.0,
                "p_value": p_value,
                "statistically_significant": p_value < P_VALUE_THRESHOLD,
                "detected_at": datetime.now(timezone.utc).isoformat(),
            })

        return patterns

    def run_custom_query(self, sql: str, params: dict = None) -> dict:
        """Execute an analyst-defined custom query against Redshift.

        Provides a SQL interface with parameterized templates for common
        antitrust analysis patterns.

        Args:
            sql: SQL query string (parameterized with {key} placeholders).
            params: Optional dict of parameter values to substitute.

        Returns:
            dict with: columns, rows, row_count, execution_time_ms.
        """
        if params:
            formatted_sql = sql.format(**params)
        else:
            formatted_sql = sql

        start_time = time.time()

        try:
            response = self.redshift_client.execute_statement(
                Database=REDSHIFT_DATABASE,
                Sql=formatted_sql,
                WithEvent=False,
            )
            statement_id = response.get("Id", "")
            success = self._poll_redshift_statement(statement_id)

            execution_time_ms = int((time.time() - start_time) * 1000)

            if not success:
                error = self._get_statement_error(statement_id)
                return {
                    "status": "failed",
                    "error": error,
                    "execution_time_ms": execution_time_ms,
                }

            desc = self.redshift_client.describe_statement(Id=statement_id)
            columns = []
            rows = []
            if desc.get("ResultRows", 0) > 0:
                result_response = self.redshift_client.get_statement_result(
                    Id=statement_id
                )
                columns = [
                    col.get("name", "col_{0}".format(i))
                    for i, col in enumerate(
                        result_response.get("ColumnMetadata", [])
                    )
                ]
                rows = self._parse_result_records(
                    result_response.get("Records", [])
                )

            return {
                "status": "completed",
                "columns": columns,
                "rows": rows,
                "row_count": len(rows),
                "execution_time_ms": execution_time_ms,
            }

        except Exception as e:
            execution_time_ms = int((time.time() - start_time) * 1000)
            logger.error("Custom query failed: %s", e)
            return {
                "status": "failed",
                "error": str(e),
                "execution_time_ms": execution_time_ms,
            }

    def refresh_materialized_views(self) -> None:
        """Refresh mv_vendor_win_rates and mv_vendor_co_occurrence.

        Refreshes the materialized views used for cross-case pattern
        detection queries. Should be called daily to balance query
        performance against data freshness.
        """
        views = ["mv_vendor_win_rates", "mv_vendor_co_occurrence"]

        for view in views:
            try:
                sql = "REFRESH MATERIALIZED VIEW {0};".format(view)
                response = self.redshift_client.execute_statement(
                    Database=REDSHIFT_DATABASE,
                    Sql=sql,
                    WithEvent=False,
                )
                statement_id = response.get("Id", "")
                success = self._poll_redshift_statement(statement_id)

                if success:
                    logger.info("Refreshed materialized view: %s", view)
                else:
                    logger.error("Failed to refresh materialized view: %s", view)

            except Exception as e:
                logger.error(
                    "Error refreshing materialized view %s: %s", view, e
                )

    def auto_create_leads(self, patterns: list) -> list:
        """Create new pre-case leads for statistically significant patterns.

        When a detected pattern has p-value < 0.01, automatically creates
        a new pre-case lead with the pattern analysis as the lead content
        and triggers the CaseTypeClassifier.

        Args:
            patterns: List of pattern dicts from detect_* methods.

        Returns:
            List of created lead dicts with lead_id and pattern details.
        """
        created_leads = []

        for pattern in patterns:
            p_value = pattern.get("p_value", 1.0)

            # Only create leads for statistically significant patterns
            if p_value >= P_VALUE_THRESHOLD:
                continue

            pattern_type = pattern.get("pattern_type", "unknown")
            lead_id = str(uuid.uuid4())

            # Map pattern type to case type
            case_type_map = {
                "bid_rotation": "procurement_collusion",
                "market_allocation": "market_allocation",
                "price_fixing": "price_fixing",
                "win_rate_anomaly": "procurement_collusion",
            }
            case_type = case_type_map.get(pattern_type, "procurement_collusion")

            # Build lead title and summary
            title = self._build_lead_title(pattern)
            summary = json.dumps(pattern, default=str)

            try:
                with self.aurora_cm.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO pre_case_leads
                            (lead_id, title, summary, source_type, source_content,
                             case_type, status, priority, created_at, updated_at)
                        VALUES (%s, %s, %s, 'anomaly', %s, %s, 'intake', 'high', %s, %s)
                        """,
                        (
                            lead_id,
                            title,
                            summary,
                            json.dumps(pattern, default=str),
                            case_type,
                            datetime.now(timezone.utc),
                            datetime.now(timezone.utc),
                        ),
                    )

                created_leads.append({
                    "lead_id": lead_id,
                    "title": title,
                    "case_type": case_type,
                    "pattern_type": pattern_type,
                    "p_value": p_value,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                })

                logger.info(
                    "Auto-created lead %s from %s pattern (p=%.6f)",
                    lead_id, pattern_type, p_value,
                )

            except Exception as e:
                logger.error(
                    "Failed to auto-create lead for pattern %s: %s",
                    pattern_type, e,
                )

        return created_leads

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _execute_query(self, sql: str) -> list:
        """Execute a Redshift query and return result rows.

        Args:
            sql: SQL query to execute.

        Returns:
            List of row tuples.
        """
        try:
            response = self.redshift_client.execute_statement(
                Database=REDSHIFT_DATABASE,
                Sql=sql,
                WithEvent=False,
            )
            statement_id = response.get("Id", "")
            success = self._poll_redshift_statement(statement_id)

            if not success:
                return []

            result_response = self.redshift_client.get_statement_result(
                Id=statement_id
            )
            return self._parse_result_records(
                result_response.get("Records", [])
            )

        except Exception as e:
            logger.error("Query execution failed: %s", e)
            return []

    def _poll_redshift_statement(
        self, statement_id: str, max_attempts: int = 60
    ) -> bool:
        """Poll Redshift Data API for statement completion.

        Args:
            statement_id: The statement ID from execute_statement.
            max_attempts: Maximum polling attempts (2s intervals).

        Returns:
            True if statement completed successfully, False otherwise.
        """
        for _ in range(max_attempts):
            try:
                desc = self.redshift_client.describe_statement(Id=statement_id)
                status = desc.get("Status", "")
                if status == "FINISHED":
                    return True
                elif status in ("FAILED", "ABORTED"):
                    logger.error(
                        "Redshift statement %s failed: %s",
                        statement_id, desc.get("Error", "unknown"),
                    )
                    return False
                time.sleep(2)
            except Exception as e:
                logger.error("Error polling Redshift statement: %s", e)
                return False
        logger.warning("Redshift statement %s timed out", statement_id)
        return False

    def _get_statement_error(self, statement_id: str) -> str:
        """Get error details from a failed statement.

        Args:
            statement_id: Failed statement ID.

        Returns:
            Error message string.
        """
        try:
            desc = self.redshift_client.describe_statement(Id=statement_id)
            return desc.get("Error", "Unknown error")
        except Exception as e:
            return "Could not retrieve error: {0}".format(e)

    def _parse_result_records(self, records: list) -> list:
        """Parse Redshift Data API result records into row tuples.

        Args:
            records: Raw records from get_statement_result.

        Returns:
            List of row tuples with extracted values.
        """
        rows = []
        for record in records:
            row = []
            for field in record:
                value = (
                    field.get("stringValue")
                    or field.get("longValue")
                    or field.get("doubleValue")
                    or field.get("booleanValue")
                    or field.get("blobValue")
                    or ""
                )
                row.append(value)
            rows.append(row)
        return rows

    def _build_lead_title(self, pattern: dict) -> str:
        """Build a descriptive title for an auto-created lead.

        Args:
            pattern: Pattern dict from detection methods.

        Returns:
            Human-readable title string.
        """
        pattern_type = pattern.get("pattern_type", "unknown")
        p_value = pattern.get("p_value", 0)

        if pattern_type == "bid_rotation":
            vendor_a = pattern.get("vendor_a", "Unknown")
            vendor_b = pattern.get("vendor_b", "Unknown")
            count = pattern.get("co_bid_count", 0)
            return (
                "Potential Bid Rotation: {0} / {1} "
                "({2} co-bids, p={3:.4f})"
            ).format(vendor_a, vendor_b, count, p_value)
        elif pattern_type == "market_allocation":
            vendor = pattern.get("vendor_id", "Unknown")
            states = pattern.get("active_states", 0)
            win_rate = pattern.get("max_win_rate", 0)
            return (
                "Potential Market Allocation: {0} "
                "({1} states, {2:.0f}% win rate, p={3:.4f})"
            ).format(vendor, states, win_rate, p_value)
        elif pattern_type == "price_fixing":
            state = pattern.get("state", "Unknown")
            contracts = pattern.get("contract_count", 0)
            return (
                "Potential Price Fixing: {0} "
                "({1} contracts, correlated spreads, p={2:.4f})"
            ).format(state, contracts, p_value)
        elif pattern_type == "win_rate_anomaly":
            vendor = pattern.get("vendor_id", "Unknown")
            win_rate = pattern.get("win_rate_pct", 0)
            return (
                "Win Rate Anomaly: {0} "
                "({1:.0f}% win rate, p={2:.4f})"
            ).format(vendor, win_rate, p_value)
        else:
            return "Detected Pattern: {0} (p={1:.4f})".format(pattern_type, p_value)
