"""Audit service — immutable audit trail for label changes and access denials.

Provides append-only logging to the label_audit_log table. No UPDATE or DELETE
methods are exposed, ensuring audit integrity.

For MVP, uses an in-memory list when no DB connection is provided, allowing
easy testing and later swap to real Aurora queries.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional


class AuditService:
    """Handles all writes and reads to the label_audit_log table.

    When *connection_manager* is None the service stores entries in an
    in-memory list — suitable for unit tests and local development.
    """

    def __init__(self, connection_manager=None):
        self._db = connection_manager
        # In-memory store used when no DB connection is available.
        self._entries: list[dict] = []

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    def log_label_change(
        self,
        entity_type: str,
        entity_id: str,
        previous_label: Optional[str],
        new_label: Optional[str],
        changed_by: str,
        change_reason: Optional[str] = None,
    ) -> dict:
        """Insert an immutable audit entry for a label change.

        Returns the created audit entry dict.
        """
        entry = {
            "audit_id": str(uuid.uuid4()),
            "entity_type": entity_type,
            "entity_id": entity_id,
            "previous_label": previous_label,
            "new_label": new_label,
            "changed_by": changed_by,
            "changed_at": datetime.now(timezone.utc),
            "change_reason": change_reason,
        }

        if self._db is not None:
            self._insert_db(entry)
        else:
            self._entries.append(entry)

        return entry

    def log_access_denial(
        self,
        user_id: str,
        resource_id: str,
        reason: str,
    ) -> dict:
        """Insert an audit entry for an access denial.

        Uses entity_type='access_denied' as specified by the design.
        """
        return self.log_label_change(
            entity_type="access_denied",
            entity_id=resource_id,
            previous_label=None,
            new_label=None,
            changed_by=user_id,
            change_reason=reason,
        )

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    def query_audit_log(
        self,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        changed_by: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict]:
        """Query audit log with optional filters, reverse chronological order."""
        if self._db is not None:
            return self._query_db(
                entity_type, entity_id, changed_by, date_from, date_to, limit, offset
            )

        return self._query_memory(
            entity_type, entity_id, changed_by, date_from, date_to, limit, offset
        )

    # ------------------------------------------------------------------
    # Internal — in-memory implementation
    # ------------------------------------------------------------------

    def _query_memory(
        self,
        entity_type, entity_id, changed_by, date_from, date_to, limit, offset,
    ) -> list[dict]:
        results = list(self._entries)

        if entity_type is not None:
            results = [e for e in results if e["entity_type"] == entity_type]
        if entity_id is not None:
            results = [e for e in results if e["entity_id"] == entity_id]
        if changed_by is not None:
            results = [e for e in results if e["changed_by"] == changed_by]
        if date_from is not None:
            results = [e for e in results if e["changed_at"] >= date_from]
        if date_to is not None:
            results = [e for e in results if e["changed_at"] <= date_to]

        # Reverse chronological order
        results.sort(key=lambda e: e["changed_at"], reverse=True)

        return results[offset: offset + limit]

    # ------------------------------------------------------------------
    # Internal — Aurora DB implementation (for future use)
    # ------------------------------------------------------------------

    def _insert_db(self, entry: dict) -> None:
        """Insert an audit entry into the label_audit_log table."""
        with self._db.cursor() as cur:
            cur.execute(
                """
                INSERT INTO label_audit_log
                    (audit_id, entity_type, entity_id, previous_label,
                     new_label, changed_by, changed_at, change_reason)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    entry["audit_id"],
                    entry["entity_type"],
                    entry["entity_id"],
                    entry["previous_label"],
                    entry["new_label"],
                    entry["changed_by"],
                    entry["changed_at"],
                    entry["change_reason"],
                ),
            )

    def _query_db(
        self,
        entity_type, entity_id, changed_by, date_from, date_to, limit, offset,
    ) -> list[dict]:
        """Query the label_audit_log table with optional filters."""
        clauses: list[str] = []
        params: list = []

        if entity_type is not None:
            clauses.append("entity_type = %s")
            params.append(entity_type)
        if entity_id is not None:
            clauses.append("entity_id = %s")
            params.append(entity_id)
        if changed_by is not None:
            clauses.append("changed_by = %s")
            params.append(changed_by)
        if date_from is not None:
            clauses.append("changed_at >= %s")
            params.append(date_from)
        if date_to is not None:
            clauses.append("changed_at <= %s")
            params.append(date_to)

        where = ""
        if clauses:
            where = "WHERE " + " AND ".join(clauses)

        query = f"""
            SELECT audit_id, entity_type, entity_id, previous_label,
                   new_label, changed_by, changed_at, change_reason
            FROM label_audit_log
            {where}
            ORDER BY changed_at DESC
            LIMIT %s OFFSET %s
        """
        params.extend([limit, offset])

        with self._db.cursor() as cur:
            cur.execute(query, params)
            rows = cur.fetchall()

        return [
            {
                "audit_id": str(row[0]),
                "entity_type": row[1],
                "entity_id": str(row[2]),
                "previous_label": row[3],
                "new_label": row[4],
                "changed_by": row[5],
                "changed_at": row[6],
                "change_reason": row[7],
            }
            for row in rows
        ]
