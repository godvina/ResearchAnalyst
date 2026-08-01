"""Acquire pipeline lock Lambda — prevents concurrent executions for the same case.

Inserts a 'running' row into pipeline_executions. The partial unique index
(case_id WHERE status='running') ensures only one active execution per case.

Input event:
    { "case_id": "...", "trigger_source": "...", "mode": "full"|"incremental", ... }

Output:
    Same as input (pass-through) with added "execution_id" field.

Raises:
    LockConflict: If another pipeline is already running for this case.
"""

import json
import logging
import uuid

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class LockConflict(Exception):
    """Raised when a pipeline execution is already running for the case."""
    pass


def handler(event, context):
    """Lambda entry point."""
    from db.connection import ConnectionManager

    case_id = event.get("case_id", "")
    trigger_source = event.get("trigger_source", "manual")
    execution_id = str(uuid.uuid4())

    logger.info("Acquiring pipeline lock for case %s (execution_id=%s)", case_id, execution_id)

    try:
        cm = ConnectionManager()
        with cm.cursor() as cur:
            # Attempt insert — the partial unique index prevents duplicates
            cur.execute(
                """
                INSERT INTO pipeline_executions (execution_id, case_id, status, trigger_source)
                VALUES (%s, %s, 'running', %s)
                ON CONFLICT DO NOTHING
                """,
                (execution_id, case_id, trigger_source),
            )
            # Check if our row was actually inserted
            cur.execute(
                "SELECT execution_id FROM pipeline_executions WHERE execution_id = %s",
                (execution_id,),
            )
            row = cur.fetchone()
            if row is None:
                # Our insert was blocked by ON CONFLICT — another execution is running
                logger.warning("Lock conflict: pipeline already running for case %s", case_id)
                raise LockConflict(f"Pipeline already running for case {case_id}")

        logger.info("Lock acquired: execution_id=%s for case %s", execution_id, case_id)

        # Pass through all input fields plus the execution_id
        result = dict(event)
        result["execution_id"] = execution_id
        return result

    except LockConflict:
        raise  # Let Step Functions catch this as a named error
    except Exception as exc:
        logger.exception("Failed to acquire lock for case %s", case_id)
        raise LockConflict(f"Lock acquisition failed: {str(exc)[:200]}")
