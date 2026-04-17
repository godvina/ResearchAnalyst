"""Access control service — orchestrates provider resolution, user lookup, and filtering.

Central service that:
- Resolves user identity from API Gateway events
- Loads the configured AccessPolicyProvider
- Filters document lists by calling the provider for each document
- Provides SQL clause helpers for Aurora queries
- Logs access denials to the audit trail

For MVP, uses an in-memory user store when no DB connection is provided.
"""

import os
from typing import Optional

from models.access_control import (
    AccessDecision,
    SecurityLabel,
    UserContext,
)
from services.access_policy_provider import AccessPolicyProvider
from services.audit_service import AuditService


# Default in-memory users for MVP / testing
_DEFAULT_USERS: dict[str, dict] = {
    "admin-001": {
        "user_id": "admin-001",
        "username": "admin",
        "clearance_level": SecurityLabel.TOP_SECRET,
        "role": "admin",
        "groups": [],
    },
    "analyst-001": {
        "user_id": "analyst-001",
        "username": "analyst",
        "clearance_level": SecurityLabel.RESTRICTED,
        "role": "analyst",
        "groups": [],
    },
}


class AccessControlService:
    """Orchestrates access control checks across the platform."""

    def __init__(
        self,
        connection_manager=None,
        provider: Optional[AccessPolicyProvider] = None,
        audit_service: Optional[AuditService] = None,
    ):
        self._db = connection_manager
        self._provider = provider or self._load_provider()
        self._audit = audit_service or AuditService(connection_manager)
        self._enabled = (
            os.environ.get("ACCESS_CONTROL_ENABLED", "true").lower() == "true"
        )
        # In-memory user store for MVP when no DB
        self._users: dict[str, dict] = dict(_DEFAULT_USERS)

    # ------------------------------------------------------------------
    # Provider loading
    # ------------------------------------------------------------------

    def _load_provider(self) -> AccessPolicyProvider:
        """Load provider from ACCESS_POLICY_PROVIDER env var."""
        provider_name = os.environ.get("ACCESS_POLICY_PROVIDER", "label_based")
        if provider_name == "label_based":
            from services.label_based_provider import LabelBasedProvider

            return LabelBasedProvider()
        raise ValueError(f"Unknown access policy provider: {provider_name}")

    # ------------------------------------------------------------------
    # User context resolution
    # ------------------------------------------------------------------

    def resolve_user_context(self, event: dict) -> UserContext:
        """Extract user identity from API Gateway event and look up clearance.

        Checks (in order):
        1. API Gateway authorizer claims (requestContext.authorizer.claims.sub)
        2. X-User-Id header
        3. _user_id key directly on event (for testing)

        Returns a UserContext with the user's clearance level.
        Raises KeyError if the user cannot be resolved.
        """
        user_id = self._extract_user_id(event)
        if not user_id:
            raise KeyError("User identity not resolvable from event")

        user_data = self._lookup_user(user_id)
        if not user_data:
            raise KeyError(f"User not found: {user_id}")

        clearance = user_data.get("clearance_level", SecurityLabel.RESTRICTED)
        if isinstance(clearance, str):
            clearance = SecurityLabel[clearance.upper()]

        return UserContext(
            user_id=user_data["user_id"],
            username=user_data.get("username", user_id),
            clearance_level=clearance,
            role=user_data.get("role", "analyst"),
            groups=user_data.get("groups", []),
        )

    def _extract_user_id(self, event: dict) -> Optional[str]:
        """Extract user_id from various event sources."""
        # 1. API Gateway authorizer claims
        request_context = event.get("requestContext", {})
        authorizer = request_context.get("authorizer", {})
        claims = authorizer.get("claims", {})
        if claims.get("sub"):
            return claims["sub"]

        # 2. X-User-Id header
        headers = event.get("headers", {})
        if headers:
            # Headers can be case-insensitive
            for key, value in headers.items():
                if key.lower() == "x-user-id" and value:
                    return value

        # 3. Direct _user_id on event (testing convenience)
        if event.get("_user_id"):
            return event["_user_id"]

        return None

    def _lookup_user(self, user_id: str) -> Optional[dict]:
        """Look up user by user_id. Uses DB if available, else in-memory store."""
        if self._db is not None:
            return self._lookup_user_db(user_id)
        return self._users.get(user_id)

    def _lookup_user_db(self, user_id: str) -> Optional[dict]:
        """Look up user from platform_users table."""
        with self._db.cursor() as cur:
            cur.execute(
                """
                SELECT user_id, username, display_name, role,
                       clearance_level, created_at, updated_at
                FROM platform_users
                WHERE user_id = %s OR username = %s
                LIMIT 1
                """,
                (user_id, user_id),
            )
            row = cur.fetchone()

        if row is None:
            return None

        return {
            "user_id": str(row[0]),
            "username": row[1],
            "display_name": row[2],
            "role": row[3],
            "clearance_level": SecurityLabel[row[4].upper()],
            "groups": [],
        }

    # ------------------------------------------------------------------
    # Document filtering
    # ------------------------------------------------------------------

    def filter_documents(
        self, user_ctx: UserContext, documents: list[dict]
    ) -> list[dict]:
        """Filter a list of documents, keeping only those the user can access.

        Computes effective_label as COALESCE(security_label_override, security_label)
        for each document, then delegates to the provider.

        When ACCESS_CONTROL_ENABLED is false, returns all documents unfiltered.
        """
        if not self._enabled:
            return list(documents)

        allowed = []
        for doc in documents:
            effective = self._compute_effective_label(doc)
            resource_ctx = {
                "document_id": doc.get("document_id", ""),
                "case_id": doc.get("case_id", ""),
                "effective_label": effective,
                "security_label_override": doc.get("security_label_override"),
            }
            user_dict = {
                "clearance_level": user_ctx.clearance_level,
                "groups": user_ctx.groups,
            }
            decision = self._provider.check_access(user_dict, resource_ctx)
            if decision.allowed:
                allowed.append(doc)
            else:
                self._audit.log_access_denial(
                    user_id=user_ctx.user_id,
                    resource_id=doc.get("document_id", ""),
                    reason=decision.reason,
                )
        return allowed

    def check_document_access(
        self, user_ctx: UserContext, document: dict
    ) -> AccessDecision:
        """Check access for a single document. Returns AccessDecision.

        When ACCESS_CONTROL_ENABLED is false, always returns allowed.
        """
        if not self._enabled:
            return AccessDecision(allowed=True, reason="access_control_disabled")

        effective = self._compute_effective_label(document)
        resource_ctx = {
            "document_id": document.get("document_id", ""),
            "case_id": document.get("case_id", ""),
            "effective_label": effective,
            "security_label_override": document.get("security_label_override"),
        }
        user_dict = {
            "clearance_level": user_ctx.clearance_level,
            "groups": user_ctx.groups,
        }
        decision = self._provider.check_access(user_dict, resource_ctx)

        if not decision.allowed:
            self._audit.log_access_denial(
                user_id=user_ctx.user_id,
                resource_id=document.get("document_id", ""),
                reason=decision.reason,
            )

        return decision

    # ------------------------------------------------------------------
    # SQL helpers
    # ------------------------------------------------------------------

    def build_label_filter_clause(self, clearance_rank: int) -> tuple:
        """Return (sql_fragment, params) for WHERE clause filtering.

        The SQL fragment compares the effective label (COALESCE of override
        and case default) against the user's clearance rank.
        """
        sql = (
            "COALESCE("
            "  CASE d.security_label_override"
            "    WHEN 'public' THEN 0"
            "    WHEN 'restricted' THEN 1"
            "    WHEN 'confidential' THEN 2"
            "    WHEN 'top_secret' THEN 3"
            "  END,"
            "  CASE m.security_label"
            "    WHEN 'public' THEN 0"
            "    WHEN 'restricted' THEN 1"
            "    WHEN 'confidential' THEN 2"
            "    WHEN 'top_secret' THEN 3"
            "  END"
            ") <= %s"
        )
        return (sql, [clearance_rank])

    # ------------------------------------------------------------------
    # Neptune helpers
    # ------------------------------------------------------------------

    def get_accessible_document_ids(
        self, user_ctx: UserContext, case_id: str
    ) -> set:
        """Return set of document_ids the user can access within a case.

        When ACCESS_CONTROL_ENABLED is false, returns all document IDs.
        Uses DB if available, otherwise returns empty set (MVP placeholder).
        """
        if not self._enabled:
            return self._get_all_document_ids(case_id)

        if self._db is None:
            return set()

        clearance_rank = int(user_ctx.clearance_level)

        with self._db.cursor() as cur:
            cur.execute(
                """
                SELECT d.document_id
                FROM documents d
                JOIN matters m ON d.matter_id = m.matter_id
                WHERE d.case_id = %s
                AND COALESCE(
                    CASE d.security_label_override
                        WHEN 'public' THEN 0
                        WHEN 'restricted' THEN 1
                        WHEN 'confidential' THEN 2
                        WHEN 'top_secret' THEN 3
                    END,
                    CASE m.security_label
                        WHEN 'public' THEN 0
                        WHEN 'restricted' THEN 1
                        WHEN 'confidential' THEN 2
                        WHEN 'top_secret' THEN 3
                    END
                ) <= %s
                """,
                (case_id, clearance_rank),
            )
            rows = cur.fetchall()

        return {str(row[0]) for row in rows}

    def _get_all_document_ids(self, case_id: str) -> set:
        """Return all document IDs for a case (no filtering)."""
        if self._db is None:
            return set()

        with self._db.cursor() as cur:
            cur.execute(
                "SELECT document_id FROM documents WHERE case_id = %s",
                (case_id,),
            )
            rows = cur.fetchall()

        return {str(row[0]) for row in rows}

    # ------------------------------------------------------------------
    # Audit delegation
    # ------------------------------------------------------------------

    def log_access_denial(
        self, user_ctx: UserContext, resource_ctx: dict, reason: str
    ) -> dict:
        """Insert an access_denied audit entry, delegating to AuditService."""
        return self._audit.log_access_denial(
            user_id=user_ctx.user_id,
            resource_id=resource_ctx.get("document_id", resource_ctx.get("entity_id", "")),
            reason=reason,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _compute_effective_label(self, doc: dict) -> SecurityLabel:
        """Compute effective label: COALESCE(override, case default).

        Accepts string or SecurityLabel values in the document dict.
        """
        override = doc.get("security_label_override")
        case_label = doc.get("security_label", "restricted")

        label_str = override if override is not None else case_label

        if isinstance(label_str, SecurityLabel):
            return label_str
        if isinstance(label_str, int):
            return SecurityLabel(label_str)

        return SecurityLabel[str(label_str).upper()]

    # ------------------------------------------------------------------
    # MVP user management (in-memory)
    # ------------------------------------------------------------------

    def register_user(self, user_data: dict) -> None:
        """Register a user in the in-memory store (MVP convenience)."""
        self._users[user_data["user_id"]] = user_data
