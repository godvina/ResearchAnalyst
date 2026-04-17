"""Matter Service — CRUD operations for matters (multi-tenant).

Manages creation, retrieval, listing, status updates, deletion, and
aggregated count computation for matters in Aurora. All queries enforce
tenant isolation via org_id filtering.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from db.connection import ConnectionManager
from db.neptune import entity_label
from models.hierarchy import Matter, MatterStatus

# Valid statuses as a set for fast membership checks.
_VALID_STATUSES = frozenset(s.value for s in MatterStatus)


class MatterService:
    """Handles matter CRUD, validation, and lifecycle management."""

    def __init__(self, connection_manager: ConnectionManager) -> None:
        self._db = connection_manager

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    def create_matter(
        self,
        org_id: str,
        matter_name: str,
        description: str,
        matter_type: str = "investigation",
        created_by: str = "",
    ) -> Matter:
        """Create a new matter scoped to an organization.

        Raises:
            ValueError: If *matter_name* or *description* is missing/empty.
        """
        if not matter_name or not matter_name.strip():
            raise ValueError("matter_name is required and cannot be empty")
        if not description or not description.strip():
            raise ValueError("description is required and cannot be empty")

        matter_id = str(uuid.uuid4())
        s3_pfx = f"orgs/{org_id}/matters/{matter_id}/"
        neptune_label = entity_label(matter_id)
        now = datetime.now(timezone.utc)

        with self._db.cursor() as cur:
            cur.execute(
                """
                INSERT INTO matters
                    (matter_id, org_id, matter_name, description, status,
                     matter_type, created_by, created_at, last_activity,
                     s3_prefix, neptune_subgraph_label)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    matter_id,
                    org_id,
                    matter_name.strip(),
                    description.strip(),
                    MatterStatus.CREATED.value,
                    matter_type,
                    created_by,
                    now,
                    now,
                    s3_pfx,
                    neptune_label,
                ),
            )

        return Matter(
            matter_id=matter_id,
            org_id=org_id,
            matter_name=matter_name.strip(),
            description=description.strip(),
            status=MatterStatus.CREATED,
            matter_type=matter_type,
            created_by=created_by,
            created_at=now,
            last_activity=now,
            s3_prefix=s3_pfx,
            neptune_subgraph_label=neptune_label,
        )

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_matter(self, matter_id: str, org_id: str) -> Matter:
        """Retrieve a matter by ID, scoped to org_id.

        Raises:
            KeyError: If the matter does not exist for the given org.
        """
        with self._db.cursor() as cur:
            cur.execute(
                """
                SELECT matter_id, org_id, matter_name, description, status,
                       matter_type, created_by, created_at, last_activity,
                       s3_prefix, neptune_subgraph_label,
                       total_documents, total_entities, total_relationships,
                       search_tier, error_details
                FROM matters
                WHERE matter_id = %s AND org_id = %s
                """,
                (matter_id, org_id),
            )
            row = cur.fetchone()

        if row is None:
            raise KeyError(f"Matter not found: {matter_id}")

        return self._row_to_matter(row)

    def list_matters(
        self,
        org_id: str,
        *,
        status: Optional[str] = None,
    ) -> list[Matter]:
        """List matters for an organization with optional status filter."""
        clauses: list[str] = ["org_id = %s"]
        params: list = [org_id]

        if status is not None:
            clauses.append("status = %s")
            params.append(status)

        where = "WHERE " + " AND ".join(clauses)

        query = f"""
            SELECT matter_id, org_id, matter_name, description, status,
                   matter_type, created_by, created_at, last_activity,
                   s3_prefix, neptune_subgraph_label,
                   total_documents, total_entities, total_relationships,
                   search_tier, error_details
            FROM matters
            {where}
            ORDER BY created_at DESC
        """

        with self._db.cursor() as cur:
            cur.execute(query, params)
            rows = cur.fetchall()

        return [self._row_to_matter(row) for row in rows]

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def update_status(
        self,
        matter_id: str,
        org_id: str,
        status: MatterStatus,
        error_details: Optional[str] = None,
    ) -> Matter:
        """Update matter status with valid status set enforcement.

        Raises:
            ValueError: If *status* is not a valid ``MatterStatus``.
            KeyError: If the matter does not exist for the given org.
        """
        if isinstance(status, str):
            if status not in _VALID_STATUSES:
                raise ValueError(
                    f"Invalid status '{status}'. Must be one of: {sorted(_VALID_STATUSES)}"
                )
            status = MatterStatus(status)
        elif not isinstance(status, MatterStatus):
            raise ValueError(
                f"Invalid status '{status}'. Must be one of: {sorted(_VALID_STATUSES)}"
            )

        now = datetime.now(timezone.utc)

        with self._db.cursor() as cur:
            cur.execute(
                """
                UPDATE matters
                SET status = %s, error_details = %s, last_activity = %s
                WHERE matter_id = %s AND org_id = %s
                RETURNING matter_id
                """,
                (status.value, error_details, now, matter_id, org_id),
            )
            if cur.fetchone() is None:
                raise KeyError(f"Matter not found: {matter_id}")

        return self.get_matter(matter_id, org_id)

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    def delete_matter(self, matter_id: str, org_id: str) -> None:
        """Delete a matter and its Aurora record.

        Raises:
            KeyError: If the matter does not exist for the given org.
        """
        # Verify existence first (raises KeyError if not found).
        self.get_matter(matter_id, org_id)

        with self._db.cursor() as cur:
            cur.execute(
                "DELETE FROM matters WHERE matter_id = %s AND org_id = %s",
                (matter_id, org_id),
            )

    # ------------------------------------------------------------------
    # Aggregated counts
    # ------------------------------------------------------------------

    def get_aggregated_counts(self, matter_id: str, org_id: str) -> dict:
        """Sum counts from all promoted collections for a matter.

        Returns:
            dict with keys: total_documents, total_entities, total_relationships
        """
        with self._db.cursor() as cur:
            cur.execute(
                """
                SELECT COALESCE(SUM(document_count), 0),
                       COALESCE(SUM(entity_count), 0),
                       COALESCE(SUM(relationship_count), 0)
                FROM collections
                WHERE matter_id = %s AND org_id = %s AND status = 'promoted'
                """,
                (matter_id, org_id),
            )
            row = cur.fetchone()

        return {
            "total_documents": row[0],
            "total_entities": row[1],
            "total_relationships": row[2],
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_matter(row: tuple) -> Matter:
        """Map a database row to a ``Matter`` model instance."""
        return Matter(
            matter_id=str(row[0]),
            org_id=str(row[1]),
            matter_name=row[2],
            description=row[3],
            status=MatterStatus(row[4]),
            matter_type=row[5],
            created_by=row[6] or "",
            created_at=row[7],
            last_activity=row[8],
            s3_prefix=row[9],
            neptune_subgraph_label=row[10],
            total_documents=row[11] or 0,
            total_entities=row[12] or 0,
            total_relationships=row[13] or 0,
            search_tier=row[14] or "standard",
            error_details=row[15],
        )
