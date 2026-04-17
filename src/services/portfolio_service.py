"""Case Portfolio Service — manager-level case portfolio management.

Provides aggregate views, filtering, sorting, grouping, priority management,
case assignment, bulk actions, analytics, and attention-requiring case detection.

Provides:
- get_summary: aggregate stats across all cases
- list_cases: filtered, sorted, paginated case list
- set_priority: update case priority
- assign_case: assign investigator to case
- bulk_action: bulk assign/archive/prioritize
- get_analytics: portfolio analytics data
- get_attention_cases: cases requiring attention
"""

import json
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Valid priority values
VALID_PRIORITIES = {"critical", "high", "medium", "low"}

# Valid sort fields
VALID_SORT_FIELDS = {
    "name": "cf.topic_name",
    "created_at": "cf.created_at",
    "last_activity": "cf.last_activity_at",
    "document_count": "doc_count",
    "entity_count": "entity_count",
    "strength_score": "cf.strength_score",
    "priority": "cf.priority",
}


class PortfolioService:
    """Manages the case portfolio dashboard for supervisors."""

    def __init__(self, aurora_cm) -> None:
        self._db = aurora_cm

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def get_summary(self) -> dict:
        """Aggregate stats across all cases."""
        with self._db.cursor() as cur:
            cur.execute("""
                SELECT
                    COUNT(*) as total,
                    COUNT(*) FILTER (WHERE status NOT IN ('archived')) as active,
                    COUNT(*) FILTER (WHERE status = 'archived') as archived
                FROM case_files
            """)
            row = cur.fetchone()
            total, active, archived = row[0], row[1], row[2]

            # Status breakdown
            cur.execute("""
                SELECT status, COUNT(*) FROM case_files GROUP BY status
            """)
            by_status = {row[0]: row[1] for row in cur.fetchall()}

            # Total docs and entities
            cur.execute("SELECT COUNT(*) FROM documents")
            total_docs = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM entities")
            total_entities = cur.fetchone()[0]

        return {
            "total_cases": total,
            "active_cases": active,
            "archived_cases": archived,
            "by_status": by_status,
            "total_documents": total_docs,
            "total_entities": total_entities,
        }

    # ------------------------------------------------------------------
    # List Cases
    # ------------------------------------------------------------------

    def list_cases(
        self,
        status: str | None = None,
        priority: str | None = None,
        category: str | None = None,
        assigned_to: str | None = None,
        sort_by: str = "last_activity",
        sort_order: str = "desc",
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        """Filtered, sorted, paginated case list."""
        sort_col = VALID_SORT_FIELDS.get(sort_by, "cf.last_activity_at")
        direction = "DESC" if sort_order.lower() == "desc" else "ASC"

        conditions: list[str] = []
        params: list = []

        if status:
            conditions.append("cf.status = %s")
            params.append(status)
        if priority:
            conditions.append("cf.priority = %s")
            params.append(priority)
        if category:
            conditions.append("cf.case_category = %s")
            params.append(category)
        if assigned_to:
            conditions.append("cf.assigned_to = %s")
            params.append(assigned_to)

        where = ""
        if conditions:
            where = "WHERE " + " AND ".join(conditions)

        query = f"""
            SELECT cf.case_id, cf.topic_name, cf.status, cf.priority,
                   cf.assigned_to, cf.case_category, cf.strength_score,
                   cf.last_activity_at, cf.created_at,
                   COALESCE(d.doc_count, 0) as doc_count,
                   COALESCE(e.entity_count, 0) as entity_count
            FROM case_files cf
            LEFT JOIN (
                SELECT case_file_id, COUNT(*) as doc_count
                FROM documents GROUP BY case_file_id
            ) d ON cf.case_id = d.case_file_id
            LEFT JOIN (
                SELECT case_file_id, COUNT(*) as entity_count
                FROM entities GROUP BY case_file_id
            ) e ON cf.case_id = e.case_file_id
            {where}
            ORDER BY {sort_col} {direction} NULLS LAST
            LIMIT %s OFFSET %s
        """
        params.extend([limit, offset])

        with self._db.cursor() as cur:
            cur.execute(query, params)
            cases = []
            for row in cur.fetchall():
                cases.append({
                    "case_id": str(row[0]),
                    "topic_name": row[1],
                    "status": row[2],
                    "priority": row[3] or "medium",
                    "assigned_to": row[4],
                    "case_category": row[5],
                    "strength_score": row[6],
                    "last_activity_at": str(row[7]) if row[7] else None,
                    "created_at": str(row[8]) if row[8] else None,
                    "document_count": row[9],
                    "entity_count": row[10],
                })

        return {"cases": cases, "limit": limit, "offset": offset}

    # ------------------------------------------------------------------
    # Priority & Assignment
    # ------------------------------------------------------------------

    def set_priority(self, case_id: str, priority: str) -> dict:
        """Update case priority."""
        if priority not in VALID_PRIORITIES:
            raise ValueError(f"Invalid priority: {priority}. Must be one of {VALID_PRIORITIES}")
        with self._db.cursor() as cur:
            cur.execute(
                "UPDATE case_files SET priority = %s, last_activity_at = %s WHERE case_id = %s",
                (priority, datetime.now(timezone.utc), case_id),
            )
            if cur.rowcount == 0:
                raise ValueError(f"Case not found: {case_id}")
        return {"case_id": case_id, "priority": priority}

    def assign_case(self, case_id: str, assigned_to: str) -> dict:
        """Assign an investigator to a case."""
        with self._db.cursor() as cur:
            cur.execute(
                "UPDATE case_files SET assigned_to = %s, last_activity_at = %s WHERE case_id = %s",
                (assigned_to, datetime.now(timezone.utc), case_id),
            )
            if cur.rowcount == 0:
                raise ValueError(f"Case not found: {case_id}")
        return {"case_id": case_id, "assigned_to": assigned_to}

    # ------------------------------------------------------------------
    # Bulk Actions
    # ------------------------------------------------------------------

    def bulk_action(self, action: str, case_ids: list[str], params: dict | None = None) -> dict:
        """Execute a bulk action on multiple cases."""
        params = params or {}
        affected = 0

        with self._db.cursor() as cur:
            now = datetime.now(timezone.utc)
            if action == "set_priority":
                priority = params.get("priority", "medium")
                if priority not in VALID_PRIORITIES:
                    raise ValueError(f"Invalid priority: {priority}")
                for cid in case_ids:
                    cur.execute(
                        "UPDATE case_files SET priority = %s, last_activity_at = %s WHERE case_id = %s",
                        (priority, now, cid),
                    )
                    affected += cur.rowcount

            elif action == "assign":
                assigned_to = params.get("assigned_to", "")
                for cid in case_ids:
                    cur.execute(
                        "UPDATE case_files SET assigned_to = %s, last_activity_at = %s WHERE case_id = %s",
                        (assigned_to, now, cid),
                    )
                    affected += cur.rowcount

            elif action == "archive":
                for cid in case_ids:
                    cur.execute(
                        "UPDATE case_files SET status = 'archived', last_activity_at = %s WHERE case_id = %s",
                        (now, cid),
                    )
                    affected += cur.rowcount

            else:
                raise ValueError(f"Unknown bulk action: {action}")

        return {"action": action, "affected": affected}

    # ------------------------------------------------------------------
    # Analytics
    # ------------------------------------------------------------------

    def get_analytics(self) -> dict:
        """Portfolio analytics data for charts."""
        analytics: dict = {}

        with self._db.cursor() as cur:
            # Cases by creation month
            cur.execute("""
                SELECT DATE_TRUNC('month', created_at) as month, COUNT(*)
                FROM case_files
                GROUP BY month
                ORDER BY month
            """)
            analytics["cases_over_time"] = [
                {"month": str(row[0]), "count": row[1]}
                for row in cur.fetchall()
            ]

            # Strength distribution
            cur.execute("""
                SELECT
                    CASE
                        WHEN strength_score IS NULL THEN 'unscored'
                        WHEN strength_score <= 30 THEN 'weak'
                        WHEN strength_score <= 60 THEN 'moderate'
                        ELSE 'strong'
                    END as bucket,
                    COUNT(*)
                FROM case_files
                GROUP BY bucket
            """)
            analytics["strength_distribution"] = {
                row[0]: row[1] for row in cur.fetchall()
            }

            # Average case duration (created to last activity)
            cur.execute("""
                SELECT AVG(EXTRACT(EPOCH FROM (last_activity_at - created_at)) / 86400)
                FROM case_files
                WHERE last_activity_at IS NOT NULL
            """)
            avg_days = cur.fetchone()[0]
            analytics["avg_case_duration_days"] = round(avg_days, 1) if avg_days else 0

        return analytics

    # ------------------------------------------------------------------
    # Attention Cases
    # ------------------------------------------------------------------

    def get_attention_cases(self) -> list[dict]:
        """Cases requiring attention: stalled, errors, low strength + high docs."""
        attention: list[dict] = []

        with self._db.cursor() as cur:
            # Stalled: no activity in 30+ days
            cur.execute("""
                SELECT case_id, topic_name, last_activity_at
                FROM case_files
                WHERE status NOT IN ('archived')
                  AND last_activity_at < NOW() - INTERVAL '30 days'
                ORDER BY last_activity_at ASC
                LIMIT 20
            """)
            for row in cur.fetchall():
                attention.append({
                    "case_id": str(row[0]),
                    "topic_name": row[1],
                    "reason": "stalled",
                    "detail": f"No activity since {row[2]}",
                })

            # Pipeline errors
            cur.execute("""
                SELECT cf.case_id, cf.topic_name, pr.status
                FROM case_files cf
                JOIN pipeline_runs pr ON cf.case_id = pr.case_id
                WHERE pr.status = 'failed'
                  AND pr.started_at > NOW() - INTERVAL '7 days'
                ORDER BY pr.started_at DESC
                LIMIT 20
            """)
            for row in cur.fetchall():
                attention.append({
                    "case_id": str(row[0]),
                    "topic_name": row[1],
                    "reason": "pipeline_error",
                    "detail": "Recent pipeline run failed",
                })

            # Low strength + high docs
            cur.execute("""
                SELECT cf.case_id, cf.topic_name, cf.strength_score,
                       COUNT(d.document_id) as doc_count
                FROM case_files cf
                JOIN documents d ON cf.case_id = d.case_file_id
                WHERE cf.strength_score IS NOT NULL AND cf.strength_score < 30
                GROUP BY cf.case_id, cf.topic_name, cf.strength_score
                HAVING COUNT(d.document_id) > 100
                ORDER BY cf.strength_score ASC
                LIMIT 20
            """)
            for row in cur.fetchall():
                attention.append({
                    "case_id": str(row[0]),
                    "topic_name": row[1],
                    "reason": "low_strength_high_docs",
                    "detail": f"Strength {row[2]}/100 with {row[3]} documents",
                })

        return attention
