"""Summary Cache Manager — CRUD operations for AI level summaries in Aurora.

Manages caching, retrieval, and invalidation of Bedrock-generated summaries
stored in the `ai_level_summaries` table. Uses path-prefix invalidation to
support stale-while-revalidate serving with an `is_stale` flag.

Also provides the `invalidate_signature_ancestors` utility for path-based
invalidation when a single signature is added or modified.
"""

import logging
from collections import namedtuple
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Returned by get_cached — includes the stale flag so callers can decide
# whether to serve immediately or trigger regeneration.
CachedSummary = namedtuple("CachedSummary", [
    "context_key",
    "taxonomy_level",
    "summary_text",
    "model_id",
    "prompt_token_count",
    "completion_token_count",
    "generated_at",
    "expires_at",
    "is_stale",
])


class SummaryCacheManager:
    """Cache layer for AI-generated taxonomy level summaries in Aurora."""

    # Default TTL: 7 days
    DEFAULT_TTL_SECONDS = 604800

    def __init__(self, connection_manager: Any, ttl_seconds: int = 604800) -> None:
        self._db = connection_manager
        self._ttl_seconds = ttl_seconds

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_cached(self, context_key: str) -> Optional[CachedSummary]:
        """Return cached summary if it exists. Sets `is_stale=True` for expired entries.

        Returns None only when no row exists for the given context_key.
        Expired-but-existing entries are returned with `is_stale=True` so the
        caller can serve stale content while triggering regeneration.
        """
        try:
            with self._db.cursor() as cur:
                cur.execute(
                    """SELECT context_key, taxonomy_level, summary_text, model_id,
                              prompt_token_count, completion_token_count,
                              generated_at, expires_at
                       FROM ai_level_summaries
                       WHERE context_key = %s""",
                    (context_key,),
                )
                row = cur.fetchone()
                if row is None:
                    return None

                now = datetime.now(timezone.utc)
                expires_at = row[7]
                # Ensure timezone-aware comparison
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=timezone.utc)

                is_stale = now >= expires_at

                return CachedSummary(
                    context_key=row[0],
                    taxonomy_level=row[1],
                    summary_text=row[2],
                    model_id=row[3],
                    prompt_token_count=row[4],
                    completion_token_count=row[5],
                    generated_at=row[6],
                    expires_at=row[7],
                    is_stale=is_stale,
                )
        except Exception as e:
            logger.error("get_cached failed for key=%s: %s", context_key, str(e)[:300])
            return None

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def store_summary(
        self,
        context_key: str,
        level: str,
        summary_text: str,
        model_id: str,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> None:
        """UPSERT a generated summary into the cache.

        Sets expires_at = NOW() + configured TTL. On conflict (same context_key),
        updates all mutable fields and refreshes the expiration.
        """
        try:
            with self._db.cursor() as cur:
                cur.execute(
                    """INSERT INTO ai_level_summaries
                           (context_key, taxonomy_level, summary_text, model_id,
                            prompt_token_count, completion_token_count,
                            generated_at, expires_at)
                       VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW() + %s * INTERVAL '1 second')
                       ON CONFLICT (context_key) DO UPDATE SET
                           taxonomy_level = EXCLUDED.taxonomy_level,
                           summary_text = EXCLUDED.summary_text,
                           model_id = EXCLUDED.model_id,
                           prompt_token_count = EXCLUDED.prompt_token_count,
                           completion_token_count = EXCLUDED.completion_token_count,
                           generated_at = EXCLUDED.generated_at,
                           expires_at = EXCLUDED.expires_at""",
                    (
                        context_key,
                        level,
                        summary_text,
                        model_id,
                        prompt_tokens,
                        completion_tokens,
                        self._ttl_seconds,
                    ),
                )
        except Exception as e:
            # Requirement 2.7: cache write failure must not prevent returning
            # the summary to the caller — just log the error.
            logger.error(
                "store_summary failed for key=%s: %s", context_key, str(e)[:300]
            )

    # ------------------------------------------------------------------
    # Invalidation
    # ------------------------------------------------------------------

    def invalidate_by_path(self, context_key: str) -> int:
        """Mark all entries whose context_key starts with the given prefix as stale.

        Sets expires_at = NOW() so subsequent reads see `is_stale=True`.
        Returns the number of rows affected.
        """
        try:
            with self._db.cursor() as cur:
                # Use prefix match — e.g. "antitrust/procurement_collusion%"
                prefix = context_key + "%"
                cur.execute(
                    """UPDATE ai_level_summaries
                       SET expires_at = NOW()
                       WHERE context_key LIKE %s""",
                    (prefix,),
                )
                return cur.rowcount
        except Exception as e:
            logger.error(
                "invalidate_by_path failed for key=%s: %s", context_key, str(e)[:300]
            )
            return 0

    def invalidate_all(self) -> int:
        """Mark all cached summaries as stale. Returns the number of rows affected."""
        try:
            with self._db.cursor() as cur:
                cur.execute(
                    """UPDATE ai_level_summaries
                       SET expires_at = NOW()"""
                )
                return cur.rowcount
        except Exception as e:
            logger.error("invalidate_all failed: %s", str(e)[:300])
            return 0


# ------------------------------------------------------------------
# Utility: Path-based ancestor invalidation for single-signature updates
# ------------------------------------------------------------------


def invalidate_signature_ancestors(context_key: str, cache_manager: "SummaryCacheManager" = None) -> int:
    """Invalidate cached summaries in the ancestor chain of a modified signature.

    Given a signature context_key like 'antitrust/procurement_collusion/bid_rotation/atr-pc-br-001',
    this function computes the ancestor context_keys (domain, typology, method) and marks
    all matching cached summaries as stale. It uses the domain prefix for LIKE-based
    invalidation so all entries in the ancestor chain are covered.

    Args:
        context_key: The full context_key of the modified signature.
            Format: 'domain/typology/method/signature_id'
        cache_manager: Optional SummaryCacheManager instance. If not provided,
            one will be created using a new ConnectionManager.

    Returns:
        Number of cache entries invalidated (marked stale).
    """
    if not context_key or "/" not in context_key:
        logger.warning(
            "invalidate_signature_ancestors: invalid context_key '%s' — "
            "expected format 'domain/typology/method/signature_id'",
            context_key,
        )
        return 0

    # Extract the domain prefix (first segment) — since invalidate_by_path uses
    # LIKE prefix%, passing just the domain will match:
    #   domain, domain/typology, domain/typology/method, domain/typology/method/sig
    # This is intentional: a signature change should invalidate summaries at
    # the parent method, parent typology, AND parent domain levels.
    parts = context_key.split("/")
    domain_prefix = parts[0]

    if cache_manager is None:
        # Lazy import to avoid circular dependencies when used as standalone utility
        from db.connection import ConnectionManager
        cm = ConnectionManager()
        cache_manager = SummaryCacheManager(cm)

    invalidated = cache_manager.invalidate_by_path(domain_prefix)
    logger.info(
        "invalidate_signature_ancestors: key='%s' → prefix='%s' → %d entries invalidated",
        context_key,
        domain_prefix,
        invalidated,
    )
    return invalidated
