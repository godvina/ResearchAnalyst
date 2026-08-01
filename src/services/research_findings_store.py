"""Research Findings Store — Persists investigation results and feeds them back into the taxonomy.

This service closes the loop between research and the Pattern Library:
1. Stores all research findings (concept briefings + site investigations) in Aurora
2. Provides a queryable findings history per taxonomy node
3. Computes an Evidence Score per node based on accumulated findings
4. Can export enriched taxonomy data (with findings annotations) for the frontend

The key insight: findings discovered by the AI research agent should ENRICH
the Pattern Library over time. A node that was "UNEXPLORED" becomes "PROBABLE"
once evidence is found, and "CONFIRMED" after verification.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Evidence status progression
EVIDENCE_STATUS = {
    "unexplored": 0,
    "inconclusive": 1,
    "probable": 2,
    "confirmed": 3,
    "negative": -1,
}

# Status colors for frontend map dots
STATUS_COLORS = {
    "unexplored": "#fc8181",     # Red
    "inconclusive": "#ecc94b",   # Yellow
    "probable": "#63b3ed",       # Blue
    "confirmed": "#48bb78",      # Green
    "negative": "#718096",       # Gray
}


class ResearchFindingsStore:
    """Manages persistent storage of research findings linked to taxonomy nodes.

    Each finding is stored as a row in Aurora with:
    - context_key: links to the taxonomy node
    - finding_type: 'concept_briefing' | 'site_investigation' | 'manual_annotation'
    - evidence_status: the confidence level of the finding
    - finding_data: full JSON payload of the research result
    - created_at: when the finding was recorded

    The accumulated findings for a node determine its overall evidence_status,
    which drives the map dot color and priority ranking.
    """

    TABLE_NAME = "research_findings"

    def __init__(self, connection_manager=None):
        self._db = connection_manager

    def _get_db(self):
        """Lazy-initialize database connection."""
        if self._db is None:
            from db.connection import ConnectionManager
            self._db = ConnectionManager()
        return self._db

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def store_finding(
        self,
        context_key: str,
        finding_type: str,
        evidence_status: str,
        finding_data: dict,
        query: str = "",
        location: str = "",
    ) -> Optional[str]:
        """Store a new research finding linked to a taxonomy node.

        Args:
            context_key: Taxonomy path (e.g., 'ancient_mysteries/ley_lines/grid_alignments')
            finding_type: One of 'concept_briefing', 'site_investigation', 'manual_annotation'
            evidence_status: One of 'unexplored', 'inconclusive', 'probable', 'confirmed', 'negative'
            finding_data: Full JSON payload of the research result
            query: The search query that produced this finding
            location: Geographic location if applicable

        Returns:
            The finding_id (UUID) on success, None on failure.
        """
        try:
            db = self._get_db()
            with db.cursor() as cur:
                cur.execute(
                    f"""INSERT INTO {self.TABLE_NAME}
                        (context_key, finding_type, evidence_status, finding_data,
                         query, location, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, NOW())
                    RETURNING finding_id""",
                    (
                        context_key,
                        finding_type,
                        evidence_status,
                        json.dumps(finding_data, default=str),
                        query,
                        location,
                    ),
                )
                row = cur.fetchone()
                finding_id = str(row[0]) if row else None
                logger.info(
                    "Stored finding: context_key=%s, type=%s, status=%s, id=%s",
                    context_key, finding_type, evidence_status, finding_id,
                )
                return finding_id
        except Exception as e:
            logger.error("store_finding failed: %s", str(e)[:300])
            return None

    def store_concept_briefing(self, context_key: str, briefing: dict) -> Optional[str]:
        """Convenience: store a concept research briefing."""
        # Determine evidence status from field_status
        field_status = briefing.get("field_status", "").upper()
        if "ESTABLISHED" in field_status:
            status = "confirmed"
        elif "ACTIVE" in field_status:
            status = "probable"
        elif "CONTESTED" in field_status:
            status = "inconclusive"
        else:
            status = "unexplored"

        return self.store_finding(
            context_key=context_key,
            finding_type="concept_briefing",
            evidence_status=status,
            finding_data=briefing,
            query=briefing.get("codename", ""),
        )

    def store_site_investigation(
        self, context_key: str, brief: dict, query: str = "", location: str = ""
    ) -> Optional[str]:
        """Convenience: store a site investigation result."""
        # Map investigation_status to evidence_status
        inv_status = brief.get("investigation_status", "").upper()
        if "CONFIRMED" in inv_status:
            status = "confirmed"
        elif "PROBABLE" in inv_status:
            status = "probable"
        elif "NEGATIVE" in inv_status:
            status = "negative"
        else:
            status = "inconclusive"

        return self.store_finding(
            context_key=context_key,
            finding_type="site_investigation",
            evidence_status=status,
            finding_data=brief,
            query=query,
            location=location or brief.get("situation", "")[:200],
        )

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_findings_for_node(self, context_key: str, limit: int = 20) -> list[dict]:
        """Get all findings for a taxonomy node, most recent first."""
        try:
            db = self._get_db()
            with db.cursor() as cur:
                cur.execute(
                    f"""SELECT finding_id, context_key, finding_type, evidence_status,
                               finding_data, query, location, created_at
                        FROM {self.TABLE_NAME}
                        WHERE context_key = %s
                        ORDER BY created_at DESC
                        LIMIT %s""",
                    (context_key, limit),
                )
                rows = cur.fetchall()
                return [
                    {
                        "finding_id": str(row[0]),
                        "context_key": row[1],
                        "finding_type": row[2],
                        "evidence_status": row[3],
                        "finding_data": json.loads(row[4]) if isinstance(row[4], str) else row[4],
                        "query": row[5],
                        "location": row[6],
                        "created_at": row[7].isoformat() if hasattr(row[7], "isoformat") else str(row[7]),
                    }
                    for row in rows
                ]
        except Exception as e:
            logger.error("get_findings_for_node failed: %s", str(e)[:300])
            return []

    def get_findings_by_prefix(self, prefix: str, limit: int = 50) -> list[dict]:
        """Get all findings under a taxonomy prefix (e.g., all under a domain)."""
        try:
            db = self._get_db()
            with db.cursor() as cur:
                cur.execute(
                    f"""SELECT finding_id, context_key, finding_type, evidence_status,
                               query, location, created_at
                        FROM {self.TABLE_NAME}
                        WHERE context_key LIKE %s
                        ORDER BY created_at DESC
                        LIMIT %s""",
                    (prefix + "%", limit),
                )
                rows = cur.fetchall()
                return [
                    {
                        "finding_id": str(row[0]),
                        "context_key": row[1],
                        "finding_type": row[2],
                        "evidence_status": row[3],
                        "query": row[4],
                        "location": row[5],
                        "created_at": row[6].isoformat() if hasattr(row[6], "isoformat") else str(row[6]),
                    }
                    for row in rows
                ]
        except Exception as e:
            logger.error("get_findings_by_prefix failed: %s", str(e)[:300])
            return []

    # ------------------------------------------------------------------
    # Evidence Score computation
    # ------------------------------------------------------------------

    def compute_evidence_score(self, context_key: str) -> dict:
        """Compute the aggregate evidence score for a taxonomy node.

        Looks at all findings for the node and determines:
        - overall_status: the highest confidence finding
        - score: numeric 0-100 based on quantity + quality of findings
        - color: map dot color based on status
        - finding_count: total findings
        - last_updated: most recent finding date

        Returns:
            Dict with score details for frontend consumption.
        """
        findings = self.get_findings_for_node(context_key, limit=50)

        if not findings:
            return {
                "overall_status": "unexplored",
                "score": 0,
                "color": STATUS_COLORS["unexplored"],
                "finding_count": 0,
                "last_updated": None,
            }

        # Determine highest evidence status
        statuses = [f["evidence_status"] for f in findings]
        best_status = "unexplored"
        best_value = 0

        for s in statuses:
            val = EVIDENCE_STATUS.get(s, 0)
            if val > best_value:
                best_value = val
                best_status = s

        # Special case: if any finding is "negative" and none are higher, use negative
        if best_value <= 0 and "negative" in statuses:
            best_status = "negative"

        # Compute score (0-100)
        # Base score from status: unexplored=0, inconclusive=25, probable=60, confirmed=90
        status_base = {
            "unexplored": 0,
            "inconclusive": 25,
            "probable": 60,
            "confirmed": 90,
            "negative": 10,
        }
        base = status_base.get(best_status, 0)

        # Bonus for quantity of findings (up to +10)
        quantity_bonus = min(10, len(findings) * 2)

        # Bonus for having multiple types of findings (up to +5)
        types_found = set(f["finding_type"] for f in findings)
        type_bonus = min(5, len(types_found) * 2)

        score = min(100, base + quantity_bonus + type_bonus)

        return {
            "overall_status": best_status,
            "score": score,
            "color": STATUS_COLORS.get(best_status, STATUS_COLORS["unexplored"]),
            "finding_count": len(findings),
            "last_updated": findings[0]["created_at"] if findings else None,
            "finding_types": list(types_found),
        }

    def get_evidence_map(self, domain_prefix: str) -> dict:
        """Get evidence scores for all nodes under a domain.

        Returns a dict mapping context_key → evidence_score for the frontend
        to color-code map dots.
        """
        findings = self.get_findings_by_prefix(domain_prefix, limit=200)

        # Group by context_key
        by_node = {}
        for f in findings:
            key = f["context_key"]
            if key not in by_node:
                by_node[key] = []
            by_node[key].append(f)

        # Compute score per node
        evidence_map = {}
        for key, node_findings in by_node.items():
            statuses = [f["evidence_status"] for f in node_findings]
            best_status = "unexplored"
            best_value = 0
            for s in statuses:
                val = EVIDENCE_STATUS.get(s, 0)
                if val > best_value:
                    best_value = val
                    best_status = s

            if best_value <= 0 and "negative" in statuses:
                best_status = "negative"

            evidence_map[key] = {
                "status": best_status,
                "color": STATUS_COLORS.get(best_status, STATUS_COLORS["unexplored"]),
                "finding_count": len(node_findings),
                "last_updated": node_findings[0]["created_at"],
            }

        return evidence_map
