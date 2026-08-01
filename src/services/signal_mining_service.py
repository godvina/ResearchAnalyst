"""Signal Mining Service — Top-level orchestrator for investigative signal mining.

Coordinates finding persistence, tree-structured retrieval, drill-down triggering,
and investigator search execution. Delegates AI/OSINT work to sub-services.

Constraints:
- No bulk processing of 100+ items (individual INSERT per finding).
- No EC2, no Bedrock calls (delegated to DrillDownEngine and InvestigatorSearchService).
"""

from __future__ import annotations

import json
import logging
import math
import uuid
from datetime import datetime, timezone
from typing import Any

from models.signal_mining import (
    DirectiveResult,
    DrillDownResult,
    Finding,
    PaginatedFindings,
)
from services.drill_down_engine import DrillDownEngine
from services.investigator_search_service import InvestigatorSearchService
from services.iov_taxonomy_service import IovTaxonomyService
from services.signal_scorer import SignalScorer

logger = logging.getLogger(__name__)


class SignalMiningService:
    """Orchestrates signal mining operations for pre-case leads.

    Coordinates finding persistence, tree-structured retrieval,
    drill-down triggering, and investigator search execution.
    """

    def __init__(
        self,
        aurora_cm,
        iov_taxonomy_service: IovTaxonomyService,
        signal_scorer: SignalScorer,
        drill_down_engine: DrillDownEngine,
        investigator_search_service: InvestigatorSearchService,
    ) -> None:
        self.aurora_cm = aurora_cm
        self.iov_taxonomy_service = iov_taxonomy_service
        self.signal_scorer = signal_scorer
        self.drill_down_engine = drill_down_engine
        self.investigator_search_service = investigator_search_service

    def get_findings(
        self, lead_id: str, page: int = 1, page_size: int = 25
    ) -> PaginatedFindings:
        """Query signal_mining_findings for a lead, build tree structure, paginate.

        Retrieves all findings (top-level and sub-findings) for the lead,
        assembles parent→child tree, sorts by signal_strength DESC within
        each level, and paginates top-level findings only.

        Args:
            lead_id: UUID of the pre-case lead.
            page: Page number (1-indexed).
            page_size: Number of top-level findings per page.

        Returns:
            PaginatedFindings with nested tree structure.

        Raises:
            KeyError: If lead_id does not exist in pre_case_leads.
        """
        # Verify lead exists
        self._verify_lead_exists(lead_id)

        with self.aurora_cm.cursor() as cur:
            cur.execute(
                """
                SELECT finding_id, lead_id, parent_finding_id, summary,
                       source_url, signal_strength, tier, matched_indicators,
                       drill_down_depth, directive_text, raw_data, is_alert,
                       alert_dismissed, created_at
                FROM signal_mining_findings
                WHERE lead_id = %s
                ORDER BY signal_strength DESC
                """,
                (lead_id,),
            )
            rows = cur.fetchall()

        # Build Finding objects from rows
        findings_map: dict[str, Finding] = {}
        for row in rows:
            finding = Finding(
                finding_id=str(row[0]),
                lead_id=str(row[1]),
                parent_finding_id=str(row[2]) if row[2] else None,
                summary=row[3] or "",
                source_url=row[4] or "",
                signal_strength=row[5] or 0,
                tier=row[6] or "LOW",
                matched_indicators=row[7] if row[7] else [],
                drill_down_depth=row[8] or 0,
                directive_text=row[9],
                raw_data=row[10] if row[10] else {},
                is_alert=row[11] or False,
                alert_dismissed=row[12] or False,
                created_at=row[13],
            )
            findings_map[finding.finding_id] = finding

        # Build parent→children map
        children_map: dict[str, list[Finding]] = {}
        top_level: list[Finding] = []

        for finding in findings_map.values():
            if finding.parent_finding_id is None:
                top_level.append(finding)
            else:
                children_map.setdefault(finding.parent_finding_id, []).append(finding)

        # Sort each level by signal_strength DESC
        top_level.sort(key=lambda f: f.signal_strength, reverse=True)
        for children in children_map.values():
            children.sort(key=lambda f: f.signal_strength, reverse=True)

        # Assemble tree structure recursively
        def attach_children(parent: Finding) -> None:
            children = children_map.get(parent.finding_id, [])
            parent.sub_findings = children
            for child in children:
                attach_children(child)

        for finding in top_level:
            attach_children(finding)

        # Paginate top-level findings only
        total_count = len(top_level)
        total_pages = math.ceil(total_count / page_size) if total_count > 0 else 0
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated = top_level[start_idx:end_idx]

        return PaginatedFindings(
            findings=paginated,
            total_count=total_count,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    def trigger_drill_down(self, lead_id: str, finding_id: str) -> DrillDownResult:
        """Load finding, get case_type, execute drill-down, persist sub-findings.

        Args:
            lead_id: UUID of the pre-case lead.
            finding_id: UUID of the finding to drill into.

        Returns:
            DrillDownResult with sub-findings.

        Raises:
            KeyError: If lead_id or finding_id does not exist.
        """
        # Load the finding from signal_mining_findings
        finding = self._load_finding(finding_id)

        # Load case_type from pre_case_leads
        case_type = self._get_case_type(lead_id)

        # Execute drill-down via engine
        result = self.drill_down_engine.execute_drill_down(
            finding, case_type, finding.drill_down_depth
        )

        # Persist each sub-finding
        for sub_finding in result.sub_findings:
            sub_finding.lead_id = lead_id
            sub_finding.parent_finding_id = finding_id
            self.persist_finding(sub_finding)

        return result

    def execute_search(self, lead_id: str, directive: str) -> DirectiveResult:
        """Load lead context, execute investigator search directive, persist findings.

        Args:
            lead_id: UUID of the pre-case lead.
            directive: Natural language search directive from investigator.

        Returns:
            DirectiveResult with findings produced.

        Raises:
            KeyError: If lead_id does not exist in pre_case_leads.
        """
        # Load case_type and source_content from pre_case_leads
        with self.aurora_cm.cursor() as cur:
            cur.execute(
                """
                SELECT case_type, source_content
                FROM pre_case_leads
                WHERE lead_id = %s
                """,
                (lead_id,),
            )
            row = cur.fetchone()
            if not row:
                raise KeyError(f"Lead not found: {lead_id}")

        case_type = row[0]
        source_content = row[1]

        # Extract subjects from source_content JSON
        subjects = []
        if source_content:
            if isinstance(source_content, str):
                source_content = json.loads(source_content)
            subjects = source_content.get("subjects", [])

        # Execute directive via investigator search service
        result = self.investigator_search_service.execute_directive(
            directive=directive,
            lead_id=lead_id,
            case_type=case_type,
            subjects=subjects,
        )

        # Persist each finding from the result
        for finding in result.findings:
            finding.lead_id = lead_id
            finding.directive_text = directive
            self.persist_finding(finding)

        return result

    def persist_finding(self, finding: Finding) -> str:
        """INSERT a finding into signal_mining_findings.

        Args:
            finding: Finding dataclass to persist.

        Returns:
            The finding_id (UUID string).
        """
        if not finding.finding_id:
            finding.finding_id = str(uuid.uuid4())

        now = datetime.now(timezone.utc)
        finding.created_at = now

        with self.aurora_cm.cursor() as cur:
            cur.execute(
                """
                INSERT INTO signal_mining_findings (
                    finding_id, lead_id, parent_finding_id, summary,
                    source_url, signal_strength, tier, matched_indicators,
                    drill_down_depth, directive_text, raw_data, is_alert,
                    alert_dismissed, created_at, updated_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                """,
                (
                    finding.finding_id,
                    finding.lead_id,
                    finding.parent_finding_id,
                    finding.summary,
                    finding.source_url,
                    finding.signal_strength,
                    finding.tier,
                    json.dumps(finding.matched_indicators),
                    finding.drill_down_depth,
                    finding.directive_text,
                    json.dumps(finding.raw_data),
                    finding.is_alert,
                    finding.alert_dismissed,
                    now,
                    now,
                ),
            )

        return finding.finding_id

    def get_finding_tree(self, finding_id: str) -> Finding:
        """Recursive CTE query to load a finding with all descendants.

        Args:
            finding_id: UUID of the root finding.

        Returns:
            Finding with sub_findings populated recursively.

        Raises:
            KeyError: If finding_id does not exist.
        """
        with self.aurora_cm.cursor() as cur:
            cur.execute(
                """
                WITH RECURSIVE finding_tree AS (
                    SELECT finding_id, lead_id, parent_finding_id, summary,
                           source_url, signal_strength, tier, matched_indicators,
                           drill_down_depth, directive_text, raw_data, is_alert,
                           alert_dismissed, created_at
                    FROM signal_mining_findings
                    WHERE finding_id = %s

                    UNION ALL

                    SELECT f.finding_id, f.lead_id, f.parent_finding_id, f.summary,
                           f.source_url, f.signal_strength, f.tier, f.matched_indicators,
                           f.drill_down_depth, f.directive_text, f.raw_data, f.is_alert,
                           f.alert_dismissed, f.created_at
                    FROM signal_mining_findings f
                    INNER JOIN finding_tree ft ON f.parent_finding_id = ft.finding_id
                )
                SELECT * FROM finding_tree
                ORDER BY signal_strength DESC
                """,
                (finding_id,),
            )
            rows = cur.fetchall()

        if not rows:
            raise KeyError(f"Finding not found: {finding_id}")

        # Build findings map from CTE results
        findings_map: dict[str, Finding] = {}
        for row in rows:
            finding = Finding(
                finding_id=str(row[0]),
                lead_id=str(row[1]),
                parent_finding_id=str(row[2]) if row[2] else None,
                summary=row[3] or "",
                source_url=row[4] or "",
                signal_strength=row[5] or 0,
                tier=row[6] or "LOW",
                matched_indicators=row[7] if row[7] else [],
                drill_down_depth=row[8] or 0,
                directive_text=row[9],
                raw_data=row[10] if row[10] else {},
                is_alert=row[11] or False,
                alert_dismissed=row[12] or False,
                created_at=row[13],
            )
            findings_map[finding.finding_id] = finding

        # Assemble tree
        root = findings_map[finding_id]
        children_map: dict[str, list[Finding]] = {}

        for f in findings_map.values():
            if f.parent_finding_id and f.finding_id != finding_id:
                children_map.setdefault(f.parent_finding_id, []).append(f)

        # Sort children by signal_strength DESC
        for children in children_map.values():
            children.sort(key=lambda f: f.signal_strength, reverse=True)

        def attach_children(parent: Finding) -> None:
            children = children_map.get(parent.finding_id, [])
            parent.sub_findings = children
            for child in children:
                attach_children(child)

        attach_children(root)
        return root

    # ─── Private helpers ───────────────────────────────────────────────

    def _verify_lead_exists(self, lead_id: str) -> None:
        """Verify that a lead exists in pre_case_leads. Raises KeyError if not."""
        with self.aurora_cm.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM pre_case_leads WHERE lead_id = %s",
                (lead_id,),
            )
            if not cur.fetchone():
                raise KeyError(f"Lead not found: {lead_id}")

    def _get_case_type(self, lead_id: str) -> str:
        """Load case_type from pre_case_leads by lead_id. Raises KeyError if not found."""
        with self.aurora_cm.cursor() as cur:
            cur.execute(
                "SELECT case_type FROM pre_case_leads WHERE lead_id = %s",
                (lead_id,),
            )
            row = cur.fetchone()
            if not row:
                raise KeyError(f"Lead not found: {lead_id}")
            return row[0]

    def _load_finding(self, finding_id: str) -> Finding:
        """Load a single finding from signal_mining_findings. Raises KeyError if not found."""
        with self.aurora_cm.cursor() as cur:
            cur.execute(
                """
                SELECT finding_id, lead_id, parent_finding_id, summary,
                       source_url, signal_strength, tier, matched_indicators,
                       drill_down_depth, directive_text, raw_data, is_alert,
                       alert_dismissed, created_at
                FROM signal_mining_findings
                WHERE finding_id = %s
                """,
                (finding_id,),
            )
            row = cur.fetchone()
            if not row:
                raise KeyError(f"Finding not found: {finding_id}")

        return Finding(
            finding_id=str(row[0]),
            lead_id=str(row[1]),
            parent_finding_id=str(row[2]) if row[2] else None,
            summary=row[3] or "",
            source_url=row[4] or "",
            signal_strength=row[5] or 0,
            tier=row[6] or "LOW",
            matched_indicators=row[7] if row[7] else [],
            drill_down_depth=row[8] or 0,
            directive_text=row[9],
            raw_data=row[10] if row[10] else {},
            is_alert=row[11] or False,
            alert_dismissed=row[12] or False,
            created_at=row[13],
        )
