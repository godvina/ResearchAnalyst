"""Conflict of Interest Detector — Cross-references Form 990 data against procurement records.

Detects conflicts of interest by matching nonprofit board members and related
organizations against vendor officers in Redshift/SAM.gov and procurement award
recipients. Creates CONFLICT_OF_INTEREST edges in Neptune with conflict_type,
dollar_amount, and detection_date.

Each detected conflict produces an analysis containing: nonprofit_entity,
conflicted_party, conflict_type, procurement_awards, dollar_amount, detection_date.

Uses Redshift Data API for cross-referencing against SAM.gov registrations and
FPDS awards. Uses Neptune Gremlin HTTP queries for edge creation.

Note: Conflict detection operates on small sets (Form 990 board members are
typically <50 per filing). Neptune edges are created individually following
the established pattern in osint_data_gatherer.py. Aurora inserts use batch
execute for efficiency.

Usage:
    detector = ConflictOfInterestDetector(
        redshift_client=redshift_data_client,
        neptune_endpoint="my-neptune-cluster.us-east-1.neptune.amazonaws.com",
        aurora_cm=connection_manager,
    )
    conflicts = detector.detect_conflicts("lead-uuid", form_990_data)
"""

from __future__ import annotations

import hashlib
import json
import logging
import ssl
import time
import urllib.request
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Redshift database name (matches cross_case_pattern_detector)
REDSHIFT_DATABASE = "pre_case_analytics"

# Fuzzy match confidence threshold for name matching
MATCH_CONFIDENCE_THRESHOLD = 0.75

# Valid conflict types
CONFLICT_TYPES = ("board_overlap", "related_organization", "financial_interest")


class ConflictOfInterestDetector:
    """Detects conflicts of interest between nonprofits and procurement vendors.

    Cross-references IRS Form 990 board members and related organizations
    against vendor officers in Redshift/SAM.gov and procurement award recipients.
    Creates CONFLICT_OF_INTEREST edges in Neptune for graph visualization.

    Follows Protocol/constructor-injection pattern for testability.
    Operates on small sets: Form 990 board members are typically <50 per filing.
    """

    def __init__(
        self,
        redshift_client: Any,
        neptune_endpoint: str,
        aurora_cm: Any,
    ) -> None:
        """Initialize with dependencies.

        Args:
            redshift_client: boto3 redshift-data client for execute_statement.
            neptune_endpoint: Neptune cluster endpoint for Gremlin queries.
            aurora_cm: Aurora PostgreSQL connection manager with cursor() context.
        """
        self.redshift_client = redshift_client
        self.neptune_endpoint = neptune_endpoint
        self.aurora_cm = aurora_cm

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def detect_conflicts(self, lead_id: str, form_990_data: list) -> list:
        """Orchestrate conflict of interest detection for a pre-case lead.

        Extracts board members and related organizations from Form 990 data,
        cross-references against vendor officers and procurement award recipients,
        stores detected conflicts as Neptune edges and Aurora records.

        Args:
            lead_id: UUID of the pre-case lead.
            form_990_data: List of Form 990 records, each containing:
                - nonprofit_name: Name of the nonprofit organization.
                - ein: Employer Identification Number.
                - board_members: List of dicts with name, role, compensation.
                - related_organizations: List of dicts with name, relationship_type.

        Returns:
            List of conflict analysis dicts, each containing:
                nonprofit_entity, conflicted_party, conflict_type,
                procurement_awards, dollar_amount, detection_date.
        """
        if not form_990_data:
            logger.info("No Form 990 data provided for lead %s", lead_id)
            return []

        conflicts = []
        detection_date = datetime.now(timezone.utc).isoformat()

        for filing in form_990_data:
            nonprofit_name = filing.get("nonprofit_name", "")
            ein = filing.get("ein", "")

            # Match board members against vendor officers
            board_members = filing.get("board_members", [])
            if board_members:
                board_conflicts = self._match_board_members(board_members)
                for conflict in board_conflicts:
                    conflicts.append({
                        "nonprofit_entity": nonprofit_name,
                        "nonprofit_ein": ein,
                        "conflicted_party": conflict["matched_name"],
                        "conflict_type": "board_overlap",
                        "procurement_awards": conflict.get("awards", []),
                        "dollar_amount": conflict.get("total_amount", 0.0),
                        "detection_date": detection_date,
                        "match_confidence": conflict.get("confidence", 0.0),
                        "vendor_id": conflict.get("vendor_id", ""),
                        "lead_id": lead_id,
                    })

            # Match related organizations against procurement recipients
            related_orgs = filing.get("related_organizations", [])
            if related_orgs:
                org_conflicts = self._match_related_orgs(related_orgs)
                for conflict in org_conflicts:
                    conflicts.append({
                        "nonprofit_entity": nonprofit_name,
                        "nonprofit_ein": ein,
                        "conflicted_party": conflict["matched_name"],
                        "conflict_type": "related_organization",
                        "procurement_awards": conflict.get("awards", []),
                        "dollar_amount": conflict.get("total_amount", 0.0),
                        "detection_date": detection_date,
                        "match_confidence": conflict.get("confidence", 0.0),
                        "vendor_id": conflict.get("vendor_id", ""),
                        "lead_id": lead_id,
                    })

        # Store conflict edges in Neptune and flags in Aurora
        if conflicts:
            self._store_conflict_edges(conflicts)
            self._store_conflict_flags(lead_id, conflicts)

        logger.info(
            "Detected %d conflicts for lead %s from %d Form 990 filings",
            len(conflicts), lead_id, len(form_990_data),
        )
        return conflicts

    # ------------------------------------------------------------------
    # Internal — Board Member Matching
    # ------------------------------------------------------------------

    def _match_board_members(self, members: list) -> list:
        """Cross-reference board members against vendor officers in Redshift/SAM.gov.

        Queries SAM.gov registrations in Redshift for officers whose names
        match the provided board members using fuzzy matching (token overlap).

        Args:
            members: List of dicts with keys: name, role, compensation.

        Returns:
            List of match dicts with: matched_name, vendor_id, awards,
            total_amount, confidence.
        """
        if not members:
            return []

        matches = []
        member_names = [m.get("name", "") for m in members if m.get("name")]

        if not member_names:
            return []

        # Build SQL to find matching officers in SAM registrations
        name_conditions = " OR ".join(
            f"LOWER(legal_name) LIKE LOWER('%{self._escape_sql(name)}%')"
            for name in member_names
        )

        query = f"""
            SELECT
                sr.entity_id AS vendor_id,
                sr.legal_name,
                sr.sam_status,
                COALESCE(
                    (SELECT SUM(fa.award_amount)
                     FROM fpds_awards fa
                     WHERE fa.vendor_id = sr.entity_id),
                    0
                ) AS total_award_amount,
                (SELECT COUNT(*)
                 FROM fpds_awards fa
                 WHERE fa.vendor_id = sr.entity_id) AS award_count
            FROM sam_registrations sr
            WHERE ({name_conditions})
              AND sr.sam_status = 'Active'
            LIMIT 100
        """

        results = self._execute_redshift_query(query)

        for row in results:
            vendor_id = row.get("vendor_id", "")
            legal_name = row.get("legal_name", "")
            total_amount = float(row.get("total_award_amount", 0))

            # Calculate match confidence based on name similarity
            best_confidence = 0.0
            best_match_name = ""
            for name in member_names:
                confidence = self._name_similarity(name, legal_name)
                if confidence > best_confidence:
                    best_confidence = confidence
                    best_match_name = name

            if best_confidence >= MATCH_CONFIDENCE_THRESHOLD:
                # Fetch specific awards for this vendor
                awards = self._get_vendor_awards(vendor_id)
                matches.append({
                    "matched_name": best_match_name,
                    "vendor_name": legal_name,
                    "vendor_id": vendor_id,
                    "awards": awards,
                    "total_amount": total_amount,
                    "confidence": best_confidence,
                })

        return matches

    # ------------------------------------------------------------------
    # Internal — Related Organization Matching
    # ------------------------------------------------------------------

    def _match_related_orgs(self, orgs: list) -> list:
        """Cross-reference related organizations against procurement award recipients.

        Queries FPDS awards and SAM registrations in Redshift for recipients
        matching the related organizations from Form 990 data.

        Args:
            orgs: List of dicts with keys: name, relationship_type.

        Returns:
            List of match dicts with: matched_name, vendor_id, awards,
            total_amount, confidence.
        """
        if not orgs:
            return []

        matches = []
        org_names = [o.get("name", "") for o in orgs if o.get("name")]

        if not org_names:
            return []

        # Query SAM registrations for matching recipients
        name_conditions = " OR ".join(
            f"LOWER(sr.legal_name) LIKE LOWER('%{self._escape_sql(name)}%')"
            for name in org_names
        )

        query = f"""
            SELECT
                sr.entity_id AS vendor_id,
                sr.legal_name,
                COALESCE(
                    (SELECT SUM(fa.award_amount)
                     FROM fpds_awards fa
                     WHERE fa.vendor_id = sr.entity_id),
                    0
                ) AS total_award_amount
            FROM sam_registrations sr
            WHERE ({name_conditions})
              AND sr.sam_status = 'Active'
            LIMIT 100
        """

        results = self._execute_redshift_query(query)

        for row in results:
            vendor_id = row.get("vendor_id", "")
            legal_name = row.get("legal_name", "")
            total_amount = float(row.get("total_award_amount", 0))

            # Calculate match confidence
            best_confidence = 0.0
            best_match_name = ""
            for name in org_names:
                confidence = self._name_similarity(name, legal_name)
                if confidence > best_confidence:
                    best_confidence = confidence
                    best_match_name = name

            if best_confidence >= MATCH_CONFIDENCE_THRESHOLD:
                awards = self._get_vendor_awards(vendor_id)
                matches.append({
                    "matched_name": best_match_name,
                    "vendor_name": legal_name,
                    "vendor_id": vendor_id,
                    "awards": awards,
                    "total_amount": total_amount,
                    "confidence": best_confidence,
                })

        return matches

    # ------------------------------------------------------------------
    # Internal — Neptune Edge Storage
    # ------------------------------------------------------------------

    def _store_conflict_edges(self, conflicts: list) -> None:
        """Create CONFLICT_OF_INTEREST edges in Neptune.

        Each edge connects a Nonprofit node to a Vendor node with properties:
        conflict_type, dollar_amount, detection_date.

        Operates on small sets (typically <20 conflicts per detection run).

        Args:
            conflicts: List of conflict analysis dicts.
        """
        if not self.neptune_endpoint or not conflicts:
            return

        for conflict in conflicts:
            nonprofit_entity = conflict.get("nonprofit_entity", "")
            conflicted_party = conflict.get("conflicted_party", "")
            conflict_type = conflict.get("conflict_type", "board_overlap")
            dollar_amount = conflict.get("dollar_amount", 0.0)
            detection_date = conflict.get("detection_date", "")
            vendor_id = conflict.get("vendor_id", "")
            lead_id = conflict.get("lead_id", "")

            # Generate deterministic node IDs
            nonprofit_node_id = hashlib.md5(
                f"nonprofit:{nonprofit_entity}".encode()
            ).hexdigest()[:16]
            vendor_node_id = hashlib.md5(
                f"vendor:{vendor_id or conflicted_party}".encode()
            ).hexdigest()[:16]

            # Escape values for Gremlin
            safe_nonprofit = self._escape_gremlin(nonprofit_entity)
            safe_party = self._escape_gremlin(conflicted_party)
            safe_type = self._escape_gremlin(conflict_type)
            safe_date = self._escape_gremlin(detection_date)

            # Upsert Nonprofit node
            nonprofit_query = (
                f"g.V('{nonprofit_node_id}').fold().coalesce("
                f"unfold(), "
                f"addV('Nonprofit').property(id, '{nonprofit_node_id}')"
                f".property('name', '{safe_nonprofit}')"
                f".property('lead_id', '{lead_id}')"
                f")"
            )
            self._execute_gremlin(nonprofit_query)

            # Upsert Vendor node
            vendor_query = (
                f"g.V('{vendor_node_id}').fold().coalesce("
                f"unfold(), "
                f"addV('Vendor').property(id, '{vendor_node_id}')"
                f".property('name', '{safe_party}')"
                f".property('vendor_id', '{vendor_id}')"
                f")"
            )
            self._execute_gremlin(vendor_query)

            # Create CONFLICT_OF_INTEREST edge with properties
            edge_query = (
                f"g.V('{nonprofit_node_id}')"
                f".coalesce("
                f"outE('CONFLICT_OF_INTEREST').where(inV().hasId('{vendor_node_id}')).has('conflict_type', '{safe_type}'), "
                f"addE('CONFLICT_OF_INTEREST').to(g.V('{vendor_node_id}'))"
                f".property('conflict_type', '{safe_type}')"
                f".property('dollar_amount', {dollar_amount})"
                f".property('detection_date', '{safe_date}')"
                f".property('lead_id', '{lead_id}')"
                f")"
            )
            self._execute_gremlin(edge_query)

        logger.info(
            "Stored %d CONFLICT_OF_INTEREST edges in Neptune", len(conflicts)
        )

    # ------------------------------------------------------------------
    # Internal — Aurora Storage
    # ------------------------------------------------------------------

    def _store_conflict_flags(self, lead_id: str, conflicts: list) -> None:
        """Store conflict flags in Aurora pre_case_conflict_flags table.

        Uses batch insert for efficiency.

        Args:
            lead_id: UUID of the pre-case lead.
            conflicts: List of conflict analysis dicts.
        """
        try:
            with self.aurora_cm.cursor() as cur:
                values = []
                for conflict in conflicts:
                    values.append((
                        str(uuid.uuid4()),
                        lead_id,
                        conflict.get("nonprofit_entity", ""),
                        conflict.get("conflicted_party", ""),
                        conflict.get("conflict_type", "board_overlap"),
                        json.dumps(conflict.get("procurement_awards", [])),
                        conflict.get("dollar_amount", 0.0),
                        conflict.get("detection_date",
                                     datetime.now(timezone.utc).isoformat()),
                    ))
                if values:
                    cur.executemany(
                        """INSERT INTO pre_case_conflict_flags
                           (flag_id, lead_id, nonprofit_entity, conflicted_party,
                            conflict_type, procurement_awards, dollar_amount,
                            detection_date)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                        values,
                    )
        except Exception as e:
            logger.error(
                "Failed to store conflict flags for lead %s: %s", lead_id, e
            )

    # ------------------------------------------------------------------
    # Internal — Redshift Query Helpers
    # ------------------------------------------------------------------

    def _execute_redshift_query(self, sql: str) -> list:
        """Execute a query against Redshift and return parsed results.

        Uses the Redshift Data API with async polling pattern.

        Args:
            sql: SQL query string.

        Returns:
            List of row dicts with column names as keys.
        """
        try:
            response = self.redshift_client.execute_statement(
                Database=REDSHIFT_DATABASE,
                Sql=sql,
                WithEvent=False,
            )
            statement_id = response["Id"]

            # Poll for completion
            if not self._poll_redshift_statement(statement_id):
                logger.error("Redshift query timed out: %s", sql[:200])
                return []

            # Fetch results
            result_response = self.redshift_client.get_statement_result(
                Id=statement_id
            )
            columns = [
                col["name"] for col in result_response.get("ColumnMetadata", [])
            ]
            rows = []
            for record in result_response.get("Records", []):
                row = {}
                for i, col_field in enumerate(record):
                    col_name = columns[i] if i < len(columns) else f"col_{i}"
                    if "stringValue" in col_field:
                        row[col_name] = col_field["stringValue"]
                    elif "longValue" in col_field:
                        row[col_name] = col_field["longValue"]
                    elif "doubleValue" in col_field:
                        row[col_name] = col_field["doubleValue"]
                    elif "booleanValue" in col_field:
                        row[col_name] = col_field["booleanValue"]
                    elif "isNull" in col_field and col_field["isNull"]:
                        row[col_name] = None
                    else:
                        row[col_name] = str(col_field)
                rows.append(row)
            return rows

        except Exception as e:
            logger.error("Redshift query failed: %s | error: %s", sql[:200], e)
            return []

    def _poll_redshift_statement(
        self, statement_id: str, max_attempts: int = 30
    ) -> bool:
        """Poll Redshift statement until completion or timeout.

        Args:
            statement_id: Redshift statement ID to poll.
            max_attempts: Maximum polling attempts (1 second apart).

        Returns:
            True if statement completed successfully, False otherwise.
        """
        for _ in range(max_attempts):
            desc = self.redshift_client.describe_statement(Id=statement_id)
            status = desc.get("Status", "")
            if status == "FINISHED":
                return True
            if status in ("FAILED", "ABORTED"):
                error = desc.get("Error", "Unknown error")
                logger.error(
                    "Redshift statement %s failed: %s", statement_id, error
                )
                return False
            time.sleep(1)
        return False

    def _get_vendor_awards(self, vendor_id: str) -> list:
        """Fetch recent procurement awards for a vendor from Redshift.

        Args:
            vendor_id: Vendor entity ID.

        Returns:
            List of award dicts with contract_number, award_amount, award_date,
            awarding_agency.
        """
        query = f"""
            SELECT contract_number, award_amount, award_date, awarding_agency
            FROM fpds_awards
            WHERE vendor_id = '{self._escape_sql(vendor_id)}'
            ORDER BY award_date DESC
            LIMIT 10
        """
        results = self._execute_redshift_query(query)
        return [
            {
                "contract_number": r.get("contract_number", ""),
                "award_amount": float(r.get("award_amount", 0)),
                "award_date": str(r.get("award_date", "")),
                "awarding_agency": r.get("awarding_agency", ""),
            }
            for r in results
        ]

    # ------------------------------------------------------------------
    # Internal — Neptune Gremlin Helpers
    # ------------------------------------------------------------------

    def _execute_gremlin(self, query: str) -> list:
        """Execute a Gremlin query via Neptune HTTP API.

        Args:
            query: Gremlin query string.

        Returns:
            List of results from Neptune.
        """
        if not self.neptune_endpoint:
            return []

        url = f"https://{self.neptune_endpoint}:8182/gremlin"
        data = json.dumps({"gremlin": query}).encode("utf-8")
        ctx = ssl.create_default_context()
        req = urllib.request.Request(
            url, data=data, headers={"Content-Type": "application/json"}
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
            logger.error(
                "Neptune Gremlin query error: %s | query: %s",
                str(e)[:200], query[:200],
            )
            return []

    # ------------------------------------------------------------------
    # Internal — Utility Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _name_similarity(name_a: str, name_b: str) -> float:
        """Compute name similarity score using token overlap (Jaccard).

        Uses lowercased word tokens for lightweight fuzzy matching.
        For production, Redshift's built-in similarity functions or
        pg_trgm would be used server-side.

        Args:
            name_a: First name string.
            name_b: Second name string.

        Returns:
            Similarity score in [0.0, 1.0].
        """
        if not name_a or not name_b:
            return 0.0

        tokens_a = set(name_a.lower().split())
        tokens_b = set(name_b.lower().split())

        if not tokens_a or not tokens_b:
            return 0.0

        intersection = tokens_a & tokens_b
        union = tokens_a | tokens_b

        return len(intersection) / len(union) if union else 0.0

    @staticmethod
    def _escape_sql(value: str) -> str:
        """Escape single quotes for SQL string literals.

        Args:
            value: Raw string value.

        Returns:
            Escaped string safe for SQL interpolation.
        """
        return value.replace("'", "''") if value else ""

    @staticmethod
    def _escape_gremlin(value: str) -> str:
        """Escape single quotes for Gremlin string literals.

        Args:
            value: Raw string value.

        Returns:
            Escaped string safe for Gremlin queries.
        """
        return value.replace("'", "\\'") if value else ""
