"""Organization Service — CRUD operations for organizations (tenants).

Manages creation, retrieval, settings updates, and listing of organizations
in Aurora. Each organization is a tenant boundary for all downstream data.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from db.connection import ConnectionManager
from models.hierarchy import Organization


class OrganizationService:
    """Handles organization CRUD and settings management."""

    def __init__(self, connection_manager: ConnectionManager) -> None:
        self._db = connection_manager

    # ------------------------------------------------------------------
    # Create

    def create_organization(
        self, org_name: str, settings: Optional[dict] = None
    ) -> Organization:
        """Create a new organization.

        Raises:
            ValueError: If *org_name* is missing or empty.
        """
        if not org_name or not org_name.strip():
            raise ValueError("org_name is required and cannot be empty")

        org_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        resolved_settings = settings if settings is not None else {}

        with self._db.cursor() as cur:
            cur.execute(
                """
                INSERT INTO organizations (org_id, org_name, settings, created_at)
                VALUES (%s, %s, %s::jsonb, %s)
                """,
                (org_id, org_name.strip(), _json_dumps(resolved_settings), now),
            )

        return Organization(
            org_id=org_id,
            org_name=org_name.strip(),
            settings=resolved_settings,
            created_at=now,
        )

    # ------------------------------------------------------------------
    # Read

    def get_organization(self, org_id: str) -> Organization:
        """Retrieve an organization by ID.

        Raises:
            KeyError: If the organization does not exist.
        """
        with self._db.cursor() as cur:
            cur.execute(
                """
                SELECT org_id, org_name, settings, created_at
                FROM organizations
                WHERE org_id = %s
                """,
                (org_id,),
            )
            row = cur.fetchone()

        if row is None:
            raise KeyError(f"Organization not found: {org_id}")

        return _row_to_organization(row)

    def list_organizations(self) -> list[Organization]:
        """List all organizations ordered by creation date."""
        with self._db.cursor() as cur:
            cur.execute(
                """
                SELECT org_id, org_name, settings, created_at
                FROM organizations
                ORDER BY created_at DESC
                """
            )
            rows = cur.fetchall()

        return [_row_to_organization(row) for row in rows]

    # ------------------------------------------------------------------
    # Update

    def update_settings(self, org_id: str, settings: dict) -> Organization:
        """Update an organization's settings.

        Raises:
            KeyError: If the organization does not exist.
        """
        with self._db.cursor() as cur:
            cur.execute(
                """
                UPDATE organizations
                SET settings = %s::jsonb
                WHERE org_id = %s
                RETURNING org_id, org_name, settings, created_at
                """,
                (_json_dumps(settings), org_id),
            )
            row = cur.fetchone()

        if row is None:
            raise KeyError(f"Organization not found: {org_id}")

        return _row_to_organization(row)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _json_dumps(obj: dict) -> str:
    """Serialize a dict to a JSON string for Postgres JSONB columns."""
    import json
    return json.dumps(obj)


def _row_to_organization(row: tuple) -> Organization:
    """Convert a database row tuple to an Organization model."""
    org_id, org_name, settings, created_at = row
    # settings may come back as a dict (psycopg2 auto-parses jsonb) or as a string
    if isinstance(settings, str):
        import json
        settings = json.loads(settings)
    return Organization(
        org_id=str(org_id),
        org_name=org_name,
        settings=settings if settings else {},
        created_at=created_at,
    )
