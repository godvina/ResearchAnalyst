"""Findings Service — persistence for investigation research notebook.

Manages CRUD operations on the investigation_findings table in Aurora
and archives full assessment JSON to S3.
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


class FindingsService:
    """Manages persistence and retrieval of investigation findings."""

    def __init__(self, aurora_cm: Any, s3_helper: Optional[Any] = None,
                 s3_bucket: str = "") -> None:
        self._db = aurora_cm
        self._s3 = s3_helper
        self._bucket = s3_bucket

    def save_finding(
        self, case_id: str, user_id: str, query: Optional[str],
        finding_type: str, title: str, summary: Optional[str],
        full_assessment: Optional[dict], source_citations: Optional[list] = None,
        entity_names: Optional[list] = None, tags: Optional[list] = None,
        notes: Optional[str] = None, confidence: Optional[str] = None,
    ) -> str:
        """Persist finding to Aurora + archive to S3. Returns finding_id."""
        finding_id = str(uuid.uuid4())
        s3_key = f"cases/{case_id}/findings/{finding_id}.json"

        # S3 archival
        if self._s3 and full_assessment and self._bucket:
            try:
                import boto3
                s3 = boto3.client("s3")
                s3.put_object(
                    Bucket=self._bucket, Key=s3_key,
                    Body=json.dumps(full_assessment, default=str).encode("utf-8"),
                    ContentType="application/json",
                )
            except Exception as e:
                logger.error("S3 archival failed for %s: %s", finding_id, str(e)[:200])
                s3_key = ""
        elif not self._s3:
            s3_key = ""

        # Aurora insert
        try:
            with self._db.cursor() as cur:
                cur.execute(
                    """INSERT INTO investigation_findings
                    (finding_id, case_id, user_id, query, finding_type, title,
                     summary, full_assessment, source_citations, entity_names,
                     tags, investigator_notes, confidence_level, s3_artifact_key)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb,
                            %s::jsonb, %s::jsonb, %s, %s, %s)""",
                    (finding_id, case_id, user_id, query, finding_type, title,
                     summary, json.dumps(full_assessment or {}),
                     json.dumps(source_citations or []),
                     json.dumps(entity_names or []),
                     json.dumps(tags or []),
                     notes, confidence, s3_key or None),
                )
        except Exception as e:
            logger.error("Save finding failed: %s", str(e)[:300])
            raise
        return finding_id

    def list_findings(
        self, case_id: str, tags_filter: Optional[list] = None,
        entity_filter: Optional[list] = None, sort_by: str = "created_at",
        limit: int = 50,
    ) -> list:
        """List findings for a case with optional filtering."""
        allowed_sorts = {"created_at", "confidence_level", "updated_at", "title"}
        sort_col = sort_by if sort_by in allowed_sorts else "created_at"
        try:
            with self._db.cursor() as cur:
                q = """SELECT finding_id, case_id, user_id, query, finding_type,
                       title, summary, source_citations, entity_names, tags,
                       investigator_notes, confidence_level, is_key_evidence,
                       needs_follow_up, created_at, updated_at
                       FROM investigation_findings WHERE case_id = %s"""
                params: list = [case_id]
                if tags_filter:
                    q += " AND tags @> %s::jsonb"
                    params.append(json.dumps(tags_filter))
                if entity_filter:
                    q += " AND entity_names ?| %s"
                    params.append(entity_filter)
                q += f" ORDER BY {sort_col} DESC LIMIT %s"
                params.append(limit)
                cur.execute(q, tuple(params))
                rows = cur.fetchall()
                return [
                    {"finding_id": str(r[0]), "case_id": str(r[1]),
                     "user_id": r[2], "query": r[3], "finding_type": r[4],
                     "title": r[5], "summary": r[6],
                     "source_citations": r[7] if isinstance(r[7], list) else json.loads(r[7] or "[]"),
                     "entity_names": r[8] if isinstance(r[8], list) else json.loads(r[8] or "[]"),
                     "tags": r[9] if isinstance(r[9], list) else json.loads(r[9] or "[]"),
                     "investigator_notes": r[10], "confidence_level": r[11],
                     "is_key_evidence": r[12], "needs_follow_up": r[13],
                     "created_at": r[14].isoformat() if r[14] else "",
                     "updated_at": r[15].isoformat() if r[15] else ""}
                    for r in rows
                ]
        except Exception as e:
            logger.error("List findings failed: %s", str(e)[:300])
            return []

    def update_finding(
        self, finding_id: str, notes: Optional[str] = None,
        tags: Optional[list] = None, is_key_evidence: Optional[bool] = None,
        needs_follow_up: Optional[bool] = None,
    ) -> Optional[dict]:
        """Update notes, tags, or status flags on a finding."""
        sets = ["updated_at = NOW()"]
        params: list = []
        if notes is not None:
            sets.append("investigator_notes = %s")
            params.append(notes)
        if tags is not None:
            sets.append("tags = %s::jsonb")
            params.append(json.dumps(tags))
        if is_key_evidence is not None:
            sets.append("is_key_evidence = %s")
            params.append(is_key_evidence)
        if needs_follow_up is not None:
            sets.append("needs_follow_up = %s")
            params.append(needs_follow_up)
        params.append(finding_id)
        try:
            with self._db.cursor() as cur:
                cur.execute(
                    f"UPDATE investigation_findings SET {', '.join(sets)} WHERE finding_id = %s RETURNING finding_id",
                    tuple(params),
                )
                row = cur.fetchone()
                return {"finding_id": str(row[0]), "updated": True} if row else None
        except Exception as e:
            logger.error("Update finding failed: %s", str(e)[:300])
            return None

    def delete_finding(self, finding_id: str) -> bool:
        """Delete a finding from Aurora and its S3 artifact."""
        try:
            with self._db.cursor() as cur:
                cur.execute(
                    "DELETE FROM investigation_findings WHERE finding_id = %s RETURNING s3_artifact_key",
                    (finding_id,),
                )
                row = cur.fetchone()
                if not row:
                    return False
                s3_key = row[0]
            if s3_key and self._s3 and self._bucket:
                try:
                    import boto3
                    s3 = boto3.client("s3")
                    s3.delete_object(Bucket=self._bucket, Key=s3_key)
                except Exception:
                    pass
            return True
        except Exception as e:
            logger.error("Delete finding failed: %s", str(e)[:300])
            return False

    def get_findings_for_entities(
        self, case_id: str, entity_names: list,
    ) -> list:
        """Retrieve findings matching entity names for search enrichment."""
        if not entity_names:
            return []
        try:
            with self._db.cursor() as cur:
                cur.execute(
                    """SELECT finding_id, title, summary, entity_names, tags,
                       confidence_level, created_at
                       FROM investigation_findings
                       WHERE case_id = %s AND entity_names ?| %s
                       ORDER BY created_at DESC LIMIT 10""",
                    (case_id, entity_names),
                )
                return [
                    {"finding_id": str(r[0]), "title": r[1], "summary": r[2],
                     "entity_names": r[3] if isinstance(r[3], list) else json.loads(r[3] or "[]"),
                     "tags": r[4] if isinstance(r[4], list) else json.loads(r[4] or "[]"),
                     "confidence_level": r[5],
                     "created_at": r[6].isoformat() if r[6] else ""}
                    for r in cur.fetchall()
                ]
        except Exception as e:
            logger.error("Get findings for entities failed: %s", str(e)[:300])
            return []
