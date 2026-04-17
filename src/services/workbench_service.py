"""Investigator Workbench Service — personal case management.

Provides a personal dashboard filtered to the current user's assigned cases,
organized by urgency with AI-prioritized task lists, activity feeds, and findings.

Provides:
- get_my_cases: cases assigned to user, grouped by swim lane
- get_daily_priorities: AI-generated priority recommendations
- get_activity_feed: recent activity from investigator_activity table
- get_findings: all findings across user's cases
- add_finding: add a new finding/note to a case
- get_metrics: personal workload metrics
"""

import json
import logging
from datetime import datetime, timezone
from uuid import uuid4

logger = logging.getLogger(__name__)

# Swim lane definitions
SWIM_LANES = {
    "needs_action": "Needs Immediate Action",
    "active": "Active Investigation",
    "awaiting": "Awaiting Response",
    "review_close": "Review & Close",
}

VALID_FINDING_TYPES = {"note", "suspicious", "lead", "evidence_gap", "recommendation"}


class WorkbenchService:
    """Personal investigator workbench backed by Aurora."""

    def __init__(self, aurora_cm, bedrock_client=None) -> None:
        self._db = aurora_cm
        self._bedrock = bedrock_client

    # ------------------------------------------------------------------
    # My Cases
    # ------------------------------------------------------------------

    def get_my_cases(self, user_id: str) -> dict:
        """Cases assigned to user, grouped into swim lanes."""
        with self._db.cursor() as cur:
            cur.execute(
                """
                SELECT cf.case_id, cf.topic_name, cf.status, cf.priority,
                       cf.strength_score, cf.last_activity_at,
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
                WHERE cf.assigned_to = %s AND cf.status != 'archived'
                ORDER BY cf.priority DESC, cf.last_activity_at DESC
                """,
                (user_id,),
            )
            cases = []
            for row in cur.fetchall():
                case = {
                    "case_id": str(row[0]),
                    "topic_name": row[1],
                    "status": row[2],
                    "priority": row[3] or "medium",
                    "strength_score": row[4],
                    "last_activity_at": str(row[5]) if row[5] else None,
                    "document_count": row[6],
                    "entity_count": row[7],
                    "swim_lane": self._assign_swim_lane(row[2], row[3], row[5]),
                }
                cases.append(case)

        # Group by swim lane
        lanes = {lane: [] for lane in SWIM_LANES}
        for case in cases:
            lane = case.get("swim_lane", "active")
            if lane in lanes:
                lanes[lane].append(case)
            else:
                lanes["active"].append(case)

        return {"user_id": user_id, "swim_lanes": lanes, "total": len(cases)}

    def _assign_swim_lane(self, status: str, priority: str | None, last_activity) -> str:
        """Determine swim lane based on case attributes."""
        if status in ("error", "failed"):
            return "needs_action"
        if priority in ("critical", "high"):
            return "needs_action"
        if status in ("review", "closing"):
            return "review_close"
        if status in ("awaiting", "pending"):
            return "awaiting"
        return "active"

    # ------------------------------------------------------------------
    # Daily Priorities
    # ------------------------------------------------------------------

    def get_daily_priorities(self, user_id: str) -> list[dict]:
        """AI-generated priority recommendations for today."""
        # Gather recent activity and case data
        priorities: list[dict] = []

        with self._db.cursor() as cur:
            # Cases with recent evidence additions
            cur.execute(
                """
                SELECT cf.case_id, cf.topic_name, COUNT(d.document_id) as new_docs
                FROM case_files cf
                JOIN documents d ON cf.case_id = d.case_file_id
                WHERE cf.assigned_to = %s
                  AND d.created_at > NOW() - INTERVAL '2 days'
                GROUP BY cf.case_id, cf.topic_name
                ORDER BY new_docs DESC
                LIMIT 5
                """,
                (user_id,),
            )
            for row in cur.fetchall():
                priorities.append({
                    "case_id": str(row[0]),
                    "topic_name": row[1],
                    "reason": f"{row[2]} new documents uploaded recently",
                    "priority": "high",
                })

            # Cases with failed pipelines
            cur.execute(
                """
                SELECT cf.case_id, cf.topic_name
                FROM case_files cf
                JOIN pipeline_runs pr ON cf.case_id = pr.case_id
                WHERE cf.assigned_to = %s AND pr.status = 'failed'
                  AND pr.started_at > NOW() - INTERVAL '3 days'
                ORDER BY pr.started_at DESC
                LIMIT 5
                """,
                (user_id,),
            )
            for row in cur.fetchall():
                priorities.append({
                    "case_id": str(row[0]),
                    "topic_name": row[1],
                    "reason": "Pipeline run failed — review and retry",
                    "priority": "critical",
                })

        if not priorities:
            priorities.append({
                "case_id": None,
                "topic_name": None,
                "reason": "No urgent items today. Continue active investigations.",
                "priority": "low",
            })

        return priorities

    # ------------------------------------------------------------------
    # Activity Feed
    # ------------------------------------------------------------------

    def get_activity_feed(self, user_id: str, limit: int = 20) -> list[dict]:
        """Recent activity from investigator_activity table."""
        with self._db.cursor() as cur:
            cur.execute(
                """
                SELECT ia.activity_id, ia.case_id, cf.topic_name,
                       ia.action_type, ia.action_detail, ia.created_at
                FROM investigator_activity ia
                JOIN case_files cf ON ia.case_id = cf.case_id
                WHERE ia.user_id = %s
                ORDER BY ia.created_at DESC
                LIMIT %s
                """,
                (user_id, limit),
            )
            return [
                {
                    "activity_id": str(row[0]),
                    "case_id": str(row[1]),
                    "topic_name": row[2],
                    "action_type": row[3],
                    "action_detail": row[4] if isinstance(row[4], dict) else json.loads(row[4] or "{}"),
                    "created_at": str(row[5]),
                }
                for row in cur.fetchall()
            ]

    # ------------------------------------------------------------------
    # Findings
    # ------------------------------------------------------------------

    def get_findings(self, user_id: str, case_id: str | None = None, limit: int = 50) -> list[dict]:
        """All findings across user's cases, optionally filtered by case."""
        conditions = ["f.user_id = %s"]
        params: list = [user_id]

        if case_id:
            conditions.append("f.case_id = %s")
            params.append(case_id)

        where = " AND ".join(conditions)
        params.append(limit)

        with self._db.cursor() as cur:
            cur.execute(
                f"""
                SELECT f.finding_id, f.case_id, cf.topic_name,
                       f.finding_type, f.title, f.content,
                       f.entity_refs, f.document_refs, f.created_at
                FROM investigator_findings f
                JOIN case_files cf ON f.case_id = cf.case_id
                WHERE {where}
                ORDER BY f.created_at DESC
                LIMIT %s
                """,
                params,
            )
            return [
                {
                    "finding_id": str(row[0]),
                    "case_id": str(row[1]),
                    "topic_name": row[2],
                    "finding_type": row[3],
                    "title": row[4],
                    "content": row[5],
                    "entity_refs": row[6] or [],
                    "document_refs": row[7] or [],
                    "created_at": str(row[8]),
                }
                for row in cur.fetchall()
            ]

    def add_finding(
        self,
        user_id: str,
        case_id: str,
        finding_type: str,
        title: str,
        content: str,
        entity_refs: list[str] | None = None,
        document_refs: list[str] | None = None,
    ) -> dict:
        """Add a new finding/note to a case."""
        if finding_type not in VALID_FINDING_TYPES:
            raise ValueError(
                f"Invalid finding_type: {finding_type}. Must be one of {VALID_FINDING_TYPES}"
            )
        if not title.strip():
            raise ValueError("Finding title cannot be empty")

        finding_id = str(uuid4())
        now = datetime.now(timezone.utc)

        with self._db.cursor() as cur:
            cur.execute(
                """
                INSERT INTO investigator_findings
                    (finding_id, case_id, user_id, finding_type, title, content,
                     entity_refs, document_refs, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    finding_id, case_id, user_id, finding_type, title, content,
                    entity_refs or [], document_refs or [], now,
                ),
            )

            # Log activity
            cur.execute(
                """
                INSERT INTO investigator_activity
                    (case_id, user_id, action_type, action_detail, created_at)
                VALUES (%s, %s, 'add_finding', %s, %s)
                """,
                (
                    case_id, user_id,
                    json.dumps({"finding_id": finding_id, "finding_type": finding_type, "title": title}),
                    now,
                ),
            )

            # Update case last_activity_at
            cur.execute(
                "UPDATE case_files SET last_activity_at = %s WHERE case_id = %s",
                (now, case_id),
            )

        return {
            "finding_id": finding_id,
            "case_id": case_id,
            "finding_type": finding_type,
            "title": title,
            "created_at": str(now),
        }

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self, user_id: str) -> dict:
        """Personal workload metrics."""
        with self._db.cursor() as cur:
            # Total assigned
            cur.execute(
                "SELECT COUNT(*) FROM case_files WHERE assigned_to = %s AND status != 'archived'",
                (user_id,),
            )
            total_assigned = cur.fetchone()[0]

            # Cases worked this week (had activity)
            cur.execute(
                """
                SELECT COUNT(DISTINCT case_id)
                FROM investigator_activity
                WHERE user_id = %s AND created_at > NOW() - INTERVAL '7 days'
                """,
                (user_id,),
            )
            cases_this_week = cur.fetchone()[0]

            # Total findings
            cur.execute(
                "SELECT COUNT(*) FROM investigator_findings WHERE user_id = %s",
                (user_id,),
            )
            total_findings = cur.fetchone()[0]

        return {
            "user_id": user_id,
            "total_assigned": total_assigned,
            "cases_worked_this_week": cases_this_week,
            "total_findings": total_findings,
        }
