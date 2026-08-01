"""Release pipeline lock Lambda — marks execution as completed/failed.

Updates the pipeline_executions row with final status, completion time,
and per-typology timing metrics.

Input event:
    {
        "case_id": "...",
        "execution_id": "...",
        "status": "completed"|"failed"|"partial",  (optional, defaults to "completed")
        "error_message": "...",  (optional, for failed status)
        "per_typology_timing": {...},  (optional)
    }

Output:
    { "released": true, "execution_id": "...", "status": "..." }
"""

import json
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def handler(event, context):
    """Lambda entry point."""
    from db.connection import ConnectionManager

    case_id = event.get("case_id", "")
    execution_id = event.get("execution_id", "")
    status = event.get("status", "completed")
    error_message = event.get("error_message")
    per_typology_timing = event.get("per_typology_timing")

    if not execution_id:
        logger.error("Missing execution_id — cannot release lock")
        return {"released": False, "error": "Missing execution_id"}

    logger.info("Releasing lock: execution_id=%s, status=%s", execution_id, status)

    try:
        cm = ConnectionManager()
        with cm.cursor() as cur:
            cur.execute(
                """
                UPDATE pipeline_executions
                SET status = %s,
                    completed_at = NOW(),
                    error_message = %s,
                    per_typology_timing = %s
                WHERE execution_id = %s
                """,
                (
                    status,
                    error_message,
                    json.dumps(per_typology_timing) if per_typology_timing else None,
                    execution_id,
                ),
            )
        logger.info("Lock released: execution_id=%s", execution_id)
        return {"released": True, "execution_id": execution_id, "status": status}

    except Exception as exc:
        logger.exception("Failed to release lock for execution_id=%s", execution_id)
        # Even if we can't update the DB, don't block the state machine
        return {"released": False, "execution_id": execution_id, "error": str(exc)[:200]}
