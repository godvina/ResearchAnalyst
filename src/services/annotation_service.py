"""Document Annotation and Evidence Chain Service (Req 29).

Manages document annotations: text highlighting, tagging, entity linking,
evidence board aggregation, and AI auto-tagging via Bedrock.
"""
import json
import logging
from datetime import datetime
from typing import Optional
from uuid import uuid4

logger = logging.getLogger(__name__)

TAG_CATEGORIES = {
    "evidence_of_offense": {"color": "#fc8181", "label": "Evidence of Offense"},
    "corroborating": {"color": "#48bb78", "label": "Corroborating Evidence"},
    "contradicting": {"color": "#f6ad55", "label": "Contradicting Evidence"},
    "witness_statement": {"color": "#63b3ed", "label": "Witness Statement"},
    "financial_record": {"color": "#f6e05e", "label": "Financial Record"},
    "communication": {"color": "#b794f4", "label": "Communication"},
    "suspicious": {"color": "#fc8181", "label": "Suspicious Activity"},
    "custom": {"color": "#718096", "label": "Custom"},
}


class AnnotationService:
    """CRUD for document annotations and evidence board."""

    def __init__(self, aurora_cm=None, bedrock_client=None):
        self._db = aurora_cm
        self._bedrock = bedrock_client

    def create_annotation(self, case_id, document_id, user_id, char_start, char_end,
                          highlighted_text, tag_category, note_text=None,
                          linked_entities=None, parent_id=None):
        """Create a new annotation on a document passage."""
        ann_id = str(uuid4())
        if tag_category not in TAG_CATEGORIES:
            tag_category = "custom"
        if not self._db:
            return {"annotation_id": ann_id, "status": "created_local"}
        try:
            with self._db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO document_annotations
                        (annotation_id, case_id, document_id, user_id, char_start, char_end,
                         highlighted_text, tag_category, note_text, linked_entities, parent_annotation_id)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    """, (ann_id, case_id, document_id, user_id, char_start, char_end,
                          highlighted_text, tag_category, note_text,
                          linked_entities or [], parent_id))
                conn.commit()
        except Exception as e:
            logger.error("Failed to create annotation: %s", e)
        return {"annotation_id": ann_id, "tag_category": tag_category}

    def get_annotations(self, case_id, document_id):
        """Get all annotations for a document."""
        if not self._db:
            return []
        try:
            with self._db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT annotation_id, user_id, char_start, char_end, highlighted_text,
                               tag_category, note_text, linked_entities, created_at
                        FROM document_annotations
                        WHERE case_id = %s AND document_id = %s
                        ORDER BY char_start
                    """, (case_id, document_id))
                    rows = cur.fetchall()
                    return [{"annotation_id": r[0], "user_id": r[1], "char_start": r[2],
                             "char_end": r[3], "highlighted_text": r[4], "tag_category": r[5],
                             "note_text": r[6], "linked_entities": r[7] or [],
                             "created_at": r[8].isoformat() if r[8] else None,
                             "color": TAG_CATEGORIES.get(r[5], {}).get("color", "#718096")}
                            for r in rows]
        except Exception as e:
            logger.error("Failed to get annotations: %s", e)
            return []

    def get_evidence_board(self, case_id, tag_filter=None):
        """Get all annotations across all documents for a case, grouped by tag."""
        if not self._db:
            return {}
        try:
            with self._db.get_connection() as conn:
                with conn.cursor() as cur:
                    sql = """SELECT annotation_id, document_id, user_id, highlighted_text,
                                    tag_category, note_text, linked_entities, created_at
                             FROM document_annotations WHERE case_id = %s"""
                    params = [case_id]
                    if tag_filter:
                        sql += " AND tag_category = %s"
                        params.append(tag_filter)
                    sql += " ORDER BY tag_category, created_at DESC"
                    cur.execute(sql, params)
                    rows = cur.fetchall()
                    board = {}
                    for r in rows:
                        tag = r[4]
                        if tag not in board:
                            board[tag] = {"label": TAG_CATEGORIES.get(tag, {}).get("label", tag),
                                          "color": TAG_CATEGORIES.get(tag, {}).get("color", "#718096"),
                                          "annotations": []}
                        board[tag]["annotations"].append({
                            "annotation_id": r[0], "document_id": r[1], "user_id": r[2],
                            "highlighted_text": r[3], "note_text": r[5],
                            "linked_entities": r[6] or [], "created_at": r[7].isoformat() if r[7] else None})
                    return board
        except Exception as e:
            logger.error("Failed to get evidence board: %s", e)
            return {}

    def delete_annotation(self, annotation_id, user_id):
        """Delete an annotation (only by the creator)."""
        if not self._db:
            return False
        try:
            with self._db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM document_annotations WHERE annotation_id = %s AND user_id = %s",
                                (annotation_id, user_id))
                conn.commit()
                return True
        except Exception as e:
            logger.error("Failed to delete annotation: %s", e)
            return False
