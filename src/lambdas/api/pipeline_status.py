"""API handler for typology pipeline health status.

Endpoint: GET /case-files/{id}/pipeline-status
Returns the most recent pipeline execution info for the case.
"""

import json
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def handler(event, context):
    """Return pipeline execution status for a case."""
    from db.connection import ConnectionManager
    from lambdas.api.response_helper import error_response, success_response

    case_id = (event.get("pathParameters") or {}).get("id", "")
    if not case_id:
        return error_response(400, "VALIDATION_ERROR", "Missing case ID", event)

    try:
        cm = ConnectionManager()
        with cm.cursor() as cur:
            # Get most recent execution
            cur.execute("""
                SELECT execution_id, status, trigger_source, started_at,
                       completed_at, per_typology_timing, error_message
                FROM pipeline_executions
                WHERE case_id = %s
                ORDER BY started_at DESC
                LIMIT 5
            """, (case_id,))
            rows = cur.fetchall()

        if not rows:
            return success_response({
                "case_id": case_id,
                "has_executions": False,
                "message": "No pipeline executions found for this case",
            }, 200, event)

        executions = []
        for row in rows:
            timing = row[5]
            if isinstance(timing, str):
                timing = json.loads(timing)
            executions.append({
                "execution_id": str(row[0]),
                "status": row[1],
                "trigger_source": row[2],
                "started_at": str(row[3]) if row[3] else None,
                "completed_at": str(row[4]) if row[4] else None,
                "per_typology_timing": timing,
                "error_message": row[6],
            })

        latest = executions[0]
        is_running = latest["status"] == "running"

        # Calculate duration for completed executions
        duration_seconds = None
        if latest.get("started_at") and latest.get("completed_at"):
            from datetime import datetime
            try:
                start = datetime.fromisoformat(latest["started_at"].replace("Z", "+00:00"))
                end = datetime.fromisoformat(latest["completed_at"].replace("Z", "+00:00"))
                duration_seconds = (end - start).total_seconds()
            except Exception:
                pass

        return success_response({
            "case_id": case_id,
            "has_executions": True,
            "is_running": is_running,
            "latest": latest,
            "duration_seconds": duration_seconds,
            "history": executions,
        }, 200, event)

    except Exception as exc:
        logger.exception("Pipeline status check failed")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)
