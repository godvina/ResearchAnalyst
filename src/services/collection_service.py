"""Collection Service — CRUD and lifecycle management for collections (multi-tenant).

Manages creation, retrieval, listing, status transitions, and rejection
for collections in Aurora. All queries enforce tenant isolation via org_id
filtering. Status transitions follow a strict state machine:

    staging → processing → qa_review → promoted | rejected → archived
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from db.connection import ConnectionManager
from models.hierarchy import Collection, CollectionStatus
from storage.s3_helper import org_matter_collection_prefix

# ---------------------------------------------------------------------------
# Valid state transitions
# ---------------------------------------------------------------------------

_VALID_TRANSITIONS: dict[CollectionStatus, frozenset[CollectionStatus]] = {
    CollectionStatus.STAGING: frozenset({CollectionStatus.PROCESSING}),
    CollectionStatus.PROCESSING: frozenset({CollectionStatus.QA_REVIEW}),
    CollectionStatus.QA_REVIEW: frozenset({CollectionStatus.PROMOTED, CollectionStatus.REJECTED}),
    CollectionStatus.PROMOTED: frozenset({CollectionStatus.ARCHIVED}),
    CollectionStatus.REJECTED: frozenset({CollectionStatus.ARCHIVED}),
    CollectionStatus.ARCHIVED: frozenset(),
}

_VALID_STATUSES = frozenset(s.value for s in CollectionStatus)


class CollectionService:
    """Handles collection CRUD, status transitions, and rejection."""

    def __init__(self, connection_manager: ConnectionManager) -> None:
        self._db = connection_manager

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    def create_collection(
        self,
        matter_id: str,
        org_id: str,
        collection_name: str,
        source_description: str = "",
        uploaded_by: str = "",
    ) -> Collection:
        """Create a new collection in staging status.

        Raises:
            ValueError: If *collection_name* is missing/empty.
        """
        if not collection_name or not collection_name.strip():
            raise ValueError("collection_name is required and cannot be empty")

        collection_id = str(uuid.uuid4())
        s3_pfx = org_matter_collection_prefix(org_id, matter_id, collection_id)
        now = datetime.now(timezone.utc)

        with self._db.cursor() as cur:
            cur.execute(
                """
                INSERT INTO collections
                    (collection_id, matter_id, org_id, collection_name,
                     source_description, status, uploaded_by, uploaded_at,
                     s3_prefix)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    collection_id,
                    matter_id,
                    org_id,
                    collection_name.strip(),
                    source_description,
                    CollectionStatus.STAGING.value,
                    uploaded_by,
                    now,
                    s3_pfx,
                ),
            )

        return Collection(
            collection_id=collection_id,
            matter_id=matter_id,
            org_id=org_id,
            collection_name=collection_name.strip(),
            source_description=source_description,
            status=CollectionStatus.STAGING,
            uploaded_by=uploaded_by,
            uploaded_at=now,
            s3_prefix=s3_pfx,
        )

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_collection(self, collection_id: str, org_id: str) -> Collection:
        """Retrieve a collection by ID, scoped to org_id.

        Raises:
            KeyError: If the collection does not exist for the given org.
        """
        with self._db.cursor() as cur:
            cur.execute(
                """
                SELECT collection_id, matter_id, org_id, collection_name,
                       source_description, status, document_count,
                       entity_count, relationship_count, uploaded_by,
                       uploaded_at, promoted_at, chain_of_custody, s3_prefix
                FROM collections
                WHERE collection_id = %s AND org_id = %s
                """,
                (collection_id, org_id),
            )
            row = cur.fetchone()

        if row is None:
            raise KeyError(f"Collection not found: {collection_id}")

        return self._row_to_collection(row)

    def list_collections(self, matter_id: str, org_id: str) -> list[Collection]:
        """List all collections for a matter, scoped to org_id."""
        with self._db.cursor() as cur:
            cur.execute(
                """
                SELECT collection_id, matter_id, org_id, collection_name,
                       source_description, status, document_count,
                       entity_count, relationship_count, uploaded_by,
                       uploaded_at, promoted_at, chain_of_custody, s3_prefix
                FROM collections
                WHERE matter_id = %s AND org_id = %s
                ORDER BY uploaded_at DESC
                """,
                (matter_id, org_id),
            )
            rows = cur.fetchall()

        return [self._row_to_collection(row) for row in rows]

    # ------------------------------------------------------------------
    # Update status
    # ------------------------------------------------------------------

    def update_status(
        self,
        collection_id: str,
        org_id: str,
        status: CollectionStatus,
    ) -> Collection:
        """Transition a collection to a new status, enforcing valid transitions.

        Raises:
            ValueError: If the transition is invalid or *status* is not a
                        valid ``CollectionStatus``.
            KeyError: If the collection does not exist for the given org.
        """
        if isinstance(status, str):
            if status not in _VALID_STATUSES:
                raise ValueError(
                    f"Invalid status '{status}'. Must be one of: {sorted(_VALID_STATUSES)}"
                )
            status = CollectionStatus(status)
        elif not isinstance(status, CollectionStatus):
            raise ValueError(
                f"Invalid status '{status}'. Must be one of: {sorted(_VALID_STATUSES)}"
            )

        # Fetch current status to validate transition.
        current = self.get_collection(collection_id, org_id)
        allowed = _VALID_TRANSITIONS.get(current.status, frozenset())

        if status not in allowed:
            raise ValueError(
                f"Invalid transition from '{current.status.value}' to '{status.value}'. "
                f"Allowed: {sorted(s.value for s in allowed)}"
            )

        now = datetime.now(timezone.utc)
        promoted_at_clause = ""
        params: list = [status.value, now, collection_id, org_id]

        if status == CollectionStatus.PROMOTED:
            promoted_at_clause = ", promoted_at = %s"
            params = [status.value, now, now, collection_id, org_id]

        with self._db.cursor() as cur:
            cur.execute(
                f"""
                UPDATE collections
                SET status = %s, uploaded_at = uploaded_at{promoted_at_clause}
                WHERE collection_id = %s AND org_id = %s
                RETURNING collection_id
                """,
                params,
            )
            if cur.fetchone() is None:
                raise KeyError(f"Collection not found: {collection_id}")

        return self.get_collection(collection_id, org_id)

    # ------------------------------------------------------------------
    # Reject
    # ------------------------------------------------------------------

    def reject_collection(self, collection_id: str, org_id: str) -> Collection:
        """Reject a collection — only valid from qa_review status.

        Raises:
            ValueError: If the collection is not in qa_review status.
            KeyError: If the collection does not exist for the given org.
        """
        current = self.get_collection(collection_id, org_id)

        if current.status != CollectionStatus.QA_REVIEW:
            raise ValueError(
                f"Cannot reject collection in '{current.status.value}' status. "
                f"Collection must be in 'qa_review' status to reject."
            )

        return self.update_status(collection_id, org_id, CollectionStatus.REJECTED)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_collection(row: tuple) -> Collection:
        """Map a database row to a ``Collection`` model instance."""
        return Collection(
            collection_id=str(row[0]),
            matter_id=str(row[1]),
            org_id=str(row[2]),
            collection_name=row[3],
            source_description=row[4] or "",
            status=CollectionStatus(row[5]),
            document_count=row[6] or 0,
            entity_count=row[7] or 0,
            relationship_count=row[8] or 0,
            uploaded_by=row[9] or "",
            uploaded_at=row[10],
            promoted_at=row[11],
            chain_of_custody=row[12] or [],
            s3_prefix=row[13],
        )
