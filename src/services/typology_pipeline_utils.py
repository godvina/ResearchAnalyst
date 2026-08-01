"""Shared utility functions for the typology subgraph pipeline.

This module provides database helper functions used by the pipeline Lambda
functions. Each function creates its own ConnectionManager instance following
the Lambda pattern (short-lived connections).
"""

import logging

from db.connection import ConnectionManager
from services.typology_query_definitions import CASE_ENTITY_THRESHOLD, get_affected_typologies

logger = logging.getLogger(__name__)


def get_case_entity_count(case_id: str) -> int:
    """Return the entity count for a case from Aurora.

    Args:
        case_id: The case identifier.

    Returns:
        The entity_count value from case_files, or 0 if not found/null.
    """
    try:
        cm = ConnectionManager()
        with cm.cursor() as cur:
            cur.execute(
                "SELECT entity_count FROM case_files WHERE case_id = %s",
                (case_id,),
            )
            row = cur.fetchone()
            if row is None or row[0] is None:
                return 0
            return int(row[0])
    except Exception:
        logger.exception("Failed to get entity count for case_id=%s", case_id)
        return 0


def is_large_case(case_id: str) -> bool:
    """Determine whether a case exceeds the large-case entity threshold.

    A case is considered 'large' when its entity count is at or above
    CASE_ENTITY_THRESHOLD, requiring pre-computation rather than real-time
    query execution.

    Args:
        case_id: The case identifier.

    Returns:
        True if entity_count >= CASE_ENTITY_THRESHOLD, False otherwise.
    """
    return get_case_entity_count(case_id) >= CASE_ENTITY_THRESHOLD


def mark_stale_typologies(case_id: str, new_entity_types: list[str]) -> list[str]:
    """Mark affected typology results as stale after new entity ingestion.

    Determines which typology modules are affected by the new entity types,
    then sets is_stale = TRUE on the corresponding precomputed summary rows,
    precomputed result rows, and the summary graph for the case.

    Args:
        case_id: The case identifier.
        new_entity_types: List of entity_type strings from newly ingested entities.

    Returns:
        List of affected typology module IDs that were marked stale.
    """
    affected = get_affected_typologies(new_entity_types)
    if not affected:
        logger.info("No typologies affected for case_id=%s with types=%s", case_id, new_entity_types)
        return []

    affected_list = sorted(affected)

    try:
        cm = ConnectionManager()
        with cm.cursor() as cur:
            cur.execute(
                "UPDATE typology_precomputed_summary SET is_stale = TRUE "
                "WHERE case_id = %s AND typology_module_id = ANY(%s)",
                (case_id, affected_list),
            )
            cur.execute(
                "UPDATE typology_precomputed_results SET is_stale = TRUE "
                "WHERE case_id = %s AND typology_module_id = ANY(%s)",
                (case_id, affected_list),
            )
            cur.execute(
                "UPDATE typology_summary_graph SET is_stale = TRUE "
                "WHERE case_id = %s",
                (case_id,),
            )
    except Exception:
        logger.warning(
            "Failed to mark stale typologies for case_id=%s (tables may not exist yet)",
            case_id,
            exc_info=True,
        )

    return affected_list


def get_stale_typologies(case_id: str) -> list[str]:
    """Return typology module IDs with stale precomputed results.

    Args:
        case_id: The case identifier.

    Returns:
        List of typology_module_id strings that are stale, or empty list
        if none found or table doesn't exist.
    """
    try:
        cm = ConnectionManager()
        with cm.cursor() as cur:
            cur.execute(
                "SELECT DISTINCT typology_module_id FROM typology_precomputed_summary "
                "WHERE case_id = %s AND is_stale = TRUE",
                (case_id,),
            )
            rows = cur.fetchall()
            return [row[0] for row in rows]
    except Exception:
        logger.warning(
            "Failed to get stale typologies for case_id=%s (table may not exist)",
            case_id,
            exc_info=True,
        )
        return []


def has_precomputed_results(case_id: str) -> bool:
    """Check whether any precomputed typology results exist for a case.

    Args:
        case_id: The case identifier.

    Returns:
        True if at least one precomputed summary row exists for the case.
    """
    try:
        cm = ConnectionManager()
        with cm.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM typology_precomputed_summary WHERE case_id = %s LIMIT 1",
                (case_id,),
            )
            return cur.fetchone() is not None
    except Exception:
        logger.exception("Failed to check precomputed results for case_id=%s", case_id)
        return False


def is_pipeline_running(case_id: str) -> bool:
    """Check whether a typology pipeline execution is currently running.

    Args:
        case_id: The case identifier.

    Returns:
        True if a running pipeline execution exists for the case.
    """
    try:
        cm = ConnectionManager()
        with cm.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM pipeline_executions "
                "WHERE case_id = %s AND status = 'running' LIMIT 1",
                (case_id,),
            )
            return cur.fetchone() is not None
    except Exception:
        logger.exception("Failed to check pipeline status for case_id=%s", case_id)
        return False
