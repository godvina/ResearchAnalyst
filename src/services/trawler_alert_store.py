"""Trawler Alert Store — CRUD operations for trawler alerts in Aurora.

Manages persistence and retrieval of intelligence trawler alerts,
scan history, and deduplication logic.
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


class TrawlerAlertStore:
    """CRUD operations for trawler alerts in Aurora."""

    def __init__(self, aurora_cm: Any) -> None:
        self._db = aurora_cm

    # ------------------------------------------------------------------
    # Alert queries
    # ------------------------------------------------------------------

    def list_alerts(
        self,
        case_id: str,
        alert_type: Optional[str] = None,
        severity: Optional[str] = None,
        source_type: Optional[str] = None,
        is_read: Optional[bool] = None,
        is_dismissed: Optional[bool] = None,
        limit: int = 50,
    ) -> list:
        """List alerts for a case with optional multi-filter support."""
        try:
            with self._db.cursor() as cur:
                q = """SELECT alert_id, case_id, scan_id, alert_type, severity,
                       title, summary, entity_names, evidence_refs, source_type,
                       is_read, is_dismissed, created_at, updated_at, ai_insight
                       FROM trawler_alerts WHERE case_id = %s"""
                params: list = [case_id]

                if alert_type is not None:
                    q += " AND alert_type = %s"
                    params.append(alert_type)
                if severity is not None:
                    q += " AND severity = %s"
                    params.append(severity)
                if source_type is not None:
                    q += " AND source_type = %s"
                    params.append(source_type)
                if is_read is not None:
                    q += " AND is_read = %s"
                    params.append(is_read)
                if is_dismissed is not None:
                    q += " AND is_dismissed = %s"
                    params.append(is_dismissed)

                q += " ORDER BY created_at DESC LIMIT %s"
                params.append(limit)
                cur.execute(q, tuple(params))
                rows = cur.fetchall()
                return [self._row_to_dict(r) for r in rows]
        except Exception as e:
            logger.error("list_alerts failed: %s", str(e)[:300])
            return []

    def get_alert(self, alert_id: str) -> Optional[dict]:
        """Return a single alert by ID, or None if not found."""
        try:
            with self._db.cursor() as cur:
                cur.execute(
                    """SELECT alert_id, case_id, scan_id, alert_type, severity,
                       title, summary, entity_names, evidence_refs, source_type,
                       is_read, is_dismissed, created_at, updated_at, ai_insight
                       FROM trawler_alerts WHERE alert_id = %s""",
                    (alert_id,),
                )
                row = cur.fetchone()
                return self._row_to_dict(row) if row else None
        except Exception as e:
            logger.error("get_alert failed: %s", str(e)[:300])
            return None

    def update_alert(
        self,
        alert_id: str,
        is_read: Optional[bool] = None,
        is_dismissed: Optional[bool] = None,
    ) -> Optional[dict]:
        """Update is_read / is_dismissed on an alert. Returns updated dict."""
        sets = ["updated_at = NOW()"]
        params: list = []
        if is_read is not None:
            sets.append("is_read = %s")
            params.append(is_read)
        if is_dismissed is not None:
            sets.append("is_dismissed = %s")
            params.append(is_dismissed)
        params.append(alert_id)
        try:
            with self._db.cursor() as cur:
                cur.execute(
                    f"""UPDATE trawler_alerts SET {', '.join(sets)}
                        WHERE alert_id = %s
                        RETURNING alert_id, case_id, scan_id, alert_type,
                        severity, title, summary, entity_names, evidence_refs,
                        source_type, is_read, is_dismissed, created_at,
                        updated_at""",
                    tuple(params),
                )
                row = cur.fetchone()
                return self._row_to_dict(row) if row else None
        except Exception as e:
            logger.error("update_alert failed: %s", str(e)[:300])
            return None

    def get_unread_count(self, case_id: str) -> int:
        """Return count of unread, non-dismissed alerts for badge display."""
        try:
            with self._db.cursor() as cur:
                cur.execute(
                    """SELECT COUNT(*) FROM trawler_alerts
                       WHERE case_id = %s AND is_read = FALSE
                       AND is_dismissed = FALSE""",
                    (case_id,),
                )
                row = cur.fetchone()
                return row[0] if row else 0
        except Exception as e:
            logger.error("get_unread_count failed: %s", str(e)[:300])
            return 0

    # ------------------------------------------------------------------
    # Scan history
    # ------------------------------------------------------------------

    def list_scan_history(self, case_id: str, limit: int = 50) -> list:
        """Return recent scan records sorted by started_at DESC."""
        try:
            with self._db.cursor() as cur:
                cur.execute(
                    """SELECT scan_id, case_id, started_at, completed_at,
                       alerts_generated, scan_status, scan_type,
                       phase_timings, error_message, pattern_baseline,
                       indicator_snapshot
                       FROM trawl_scans WHERE case_id = %s
                       ORDER BY started_at DESC LIMIT %s""",
                    (case_id, limit),
                )
                rows = cur.fetchall()
                return [self._scan_row_to_dict(r) for r in rows]
        except Exception as e:
            logger.error("list_scan_history failed: %s", str(e)[:300])
            return []

    # ------------------------------------------------------------------
    # Deduplication
    # ------------------------------------------------------------------

    def find_duplicate(
        self,
        case_id: str,
        alert_type: str,
        entity_names: list,
        days: int = 7,
    ) -> Optional[dict]:
        """Find an existing non-dismissed alert that overlaps with the candidate.

        A duplicate is an alert with the same case_id, alert_type, at least
        one overlapping entity_name, and created within the past *days* days.
        """
        if not entity_names:
            return None
        try:
            with self._db.cursor() as cur:
                cur.execute(
                    """SELECT alert_id, case_id, scan_id, alert_type, severity,
                       title, summary, entity_names, evidence_refs, source_type,
                       is_read, is_dismissed, created_at, updated_at
                       FROM trawler_alerts
                       WHERE case_id = %s
                         AND alert_type = %s
                         AND is_dismissed = FALSE
                         AND created_at >= NOW() - INTERVAL '%s days'
                         AND entity_names ?| %s
                       ORDER BY created_at DESC
                       LIMIT 1""",
                    (case_id, alert_type, days, entity_names),
                )
                row = cur.fetchone()
                return self._row_to_dict(row) if row else None
        except Exception as e:
            logger.error("find_duplicate failed: %s", str(e)[:300])
            return None

    def merge_into_existing(
        self,
        alert_id: str,
        new_evidence_refs: list,
        new_summary: str,
    ) -> dict:
        """Merge new evidence into an existing alert.

        Appends new_evidence_refs, updates summary, resets is_read to False,
        and updates created_at to NOW() so the alert resurfaces.
        """
        try:
            with self._db.cursor() as cur:
                cur.execute(
                    """UPDATE trawler_alerts
                       SET evidence_refs = evidence_refs || %s::jsonb,
                           summary = %s,
                           is_read = FALSE,
                           created_at = NOW(),
                           updated_at = NOW()
                       WHERE alert_id = %s
                       RETURNING alert_id, case_id, scan_id, alert_type,
                       severity, title, summary, entity_names, evidence_refs,
                       source_type, is_read, is_dismissed, created_at,
                       updated_at""",
                    (json.dumps(new_evidence_refs), new_summary, alert_id),
                )
                row = cur.fetchone()
                return self._row_to_dict(row) if row else {}
        except Exception as e:
            logger.error("merge_into_existing failed: %s", str(e)[:300])
            return {}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_dict(row: tuple) -> dict:
        """Convert a trawler_alerts SELECT row to a dict."""
        return {
            "alert_id": str(row[0]),
            "case_id": str(row[1]),
            "scan_id": str(row[2]) if row[2] else None,
            "alert_type": row[3],
            "severity": row[4],
            "title": row[5],
            "summary": row[6],
            "entity_names": row[7] if isinstance(row[7], list) else json.loads(row[7] or "[]"),
            "evidence_refs": row[8] if isinstance(row[8], list) else json.loads(row[8] or "[]"),
            "source_type": row[9],
            "is_read": row[10],
            "is_dismissed": row[11],
            "created_at": row[12].isoformat() if row[12] else "",
            "updated_at": row[13].isoformat() if row[13] else "",
            "ai_insight": row[14] if len(row) > 14 else None,
        }

    @staticmethod
    def _scan_row_to_dict(row: tuple) -> dict:
        """Convert a trawl_scans SELECT row to a dict."""
        return {
            "scan_id": str(row[0]),
            "case_id": str(row[1]),
            "started_at": row[2].isoformat() if row[2] else "",
            "completed_at": row[3].isoformat() if row[3] else None,
            "alerts_generated": row[4],
            "scan_status": row[5],
            "scan_type": row[6],
            "phase_timings": row[7] if isinstance(row[7], dict) else json.loads(row[7] or "{}"),
            "error_message": row[8],
            "pattern_baseline": row[9] if isinstance(row[9], dict) else json.loads(row[9] or "{}"),
            "indicator_snapshot": row[10] if len(row) > 10 and isinstance(row[10], dict) else json.loads(row[10] or "{}") if len(row) > 10 and row[10] else {},
        }
