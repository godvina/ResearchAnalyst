"""Policy Priority Service — CRUD for enforcement policy directives.

Manages policy priority directives stored in Aurora that influence case backlog
scoring. Implements the PolicyPriorityProvider protocol for injection into
BacklogScoringService.

Uses Protocol/constructor-injection pattern consistent with project conventions.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


class PolicyPriorityService:
    """CRUD for policy priority directives stored in Aurora.

    Implements PolicyPriorityProvider protocol for BacklogScoringService injection.
    """

    def __init__(self, aurora_cm: Any):
        self.aurora_cm = aurora_cm

    def get_active_policies(self) -> list[dict]:
        """Return all non-expired policy directives.

        Filters: effective_date <= NOW() AND (expiration_date IS NULL OR expiration_date > NOW())
        """
        try:
            with self.aurora_cm.cursor() as cur:
                cur.execute(
                    """
                    SELECT directive_id, directive_title, source, effective_date,
                           expiration_date, target_industries, target_case_types,
                           boost_multiplier, citation_url, created_at, updated_at
                    FROM policy_priority_config
                    WHERE effective_date <= CURRENT_DATE
                      AND (expiration_date IS NULL OR expiration_date > CURRENT_DATE)
                    ORDER BY boost_multiplier DESC
                    """
                )
                rows = cur.fetchall()
                return [self._row_to_dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get active policies: {e}")
            return []

    def create_or_update_policy(self, policy_data: dict) -> dict:
        """Insert or update a policy directive.

        Required fields: directive_title, source, effective_date, target_industries,
                         target_case_types, boost_multiplier.
        Optional: directive_id (for update), expiration_date, citation_url.

        Returns:
            Dict with the created/updated policy directive.
        """
        directive_id = policy_data.get("directive_id", str(uuid.uuid4()))
        now = datetime.now(timezone.utc)

        directive_title = policy_data.get("directive_title", "")
        source = policy_data.get("source", "")
        effective_date = policy_data.get("effective_date", "")
        expiration_date = policy_data.get("expiration_date")
        target_industries = policy_data.get("target_industries", [])
        target_case_types = policy_data.get("target_case_types", [])
        boost_multiplier = float(policy_data.get("boost_multiplier", 1.0))
        citation_url = policy_data.get("citation_url", "")

        # Validate boost_multiplier range
        if boost_multiplier < 1.0 or boost_multiplier > 2.0:
            raise ValueError(f"boost_multiplier must be between 1.0 and 2.0, got {boost_multiplier}")

        # Validate source
        valid_sources = ("executive_order", "ag_memo", "congressional_referral", "interagency")
        if source not in valid_sources:
            raise ValueError(f"source must be one of {valid_sources}, got '{source}'")

        try:
            with self.aurora_cm.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO policy_priority_config
                        (directive_id, directive_title, source, effective_date,
                         expiration_date, target_industries, target_case_types,
                         boost_multiplier, citation_url, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (directive_id) DO UPDATE SET
                        directive_title = EXCLUDED.directive_title,
                        source = EXCLUDED.source,
                        effective_date = EXCLUDED.effective_date,
                        expiration_date = EXCLUDED.expiration_date,
                        target_industries = EXCLUDED.target_industries,
                        target_case_types = EXCLUDED.target_case_types,
                        boost_multiplier = EXCLUDED.boost_multiplier,
                        citation_url = EXCLUDED.citation_url,
                        updated_at = EXCLUDED.updated_at
                    """,
                    (
                        directive_id,
                        directive_title,
                        source,
                        effective_date,
                        expiration_date,
                        target_industries,
                        target_case_types,
                        boost_multiplier,
                        citation_url,
                        now,
                        now,
                    ),
                )
        except Exception as e:
            logger.error(f"Failed to create/update policy: {e}")
            raise

        return {
            "directive_id": directive_id,
            "directive_title": directive_title,
            "source": source,
            "effective_date": str(effective_date),
            "expiration_date": str(expiration_date) if expiration_date else None,
            "target_industries": target_industries,
            "target_case_types": target_case_types,
            "boost_multiplier": boost_multiplier,
            "citation_url": citation_url,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }

    def get_policy_by_id(self, directive_id: str) -> dict:
        """Get a single policy directive by ID.

        Args:
            directive_id: UUID of the directive.

        Returns:
            Dict with policy directive data.

        Raises:
            KeyError: If directive not found.
        """
        try:
            with self.aurora_cm.cursor() as cur:
                cur.execute(
                    """
                    SELECT directive_id, directive_title, source, effective_date,
                           expiration_date, target_industries, target_case_types,
                           boost_multiplier, citation_url, created_at, updated_at
                    FROM policy_priority_config
                    WHERE directive_id = %s
                    """,
                    (directive_id,),
                )
                row = cur.fetchone()
                if not row:
                    raise KeyError(f"Policy directive {directive_id} not found")
                return self._row_to_dict(row)
        except KeyError:
            raise
        except Exception as e:
            logger.error(f"Failed to get policy {directive_id}: {e}")
            raise

    def _row_to_dict(self, row) -> dict:
        """Convert a database row to a policy dict."""
        return {
            "directive_id": str(row[0]),
            "directive_title": row[1],
            "source": row[2],
            "effective_date": str(row[3]) if row[3] else None,
            "expiration_date": str(row[4]) if row[4] else None,
            "target_industries": row[5] if row[5] else [],
            "target_case_types": row[6] if row[6] else [],
            "boost_multiplier": float(row[7]) if row[7] else 1.0,
            "citation_url": row[8],
            "created_at": row[9].isoformat() if row[9] else None,
            "updated_at": row[10].isoformat() if row[10] else None,
        }
