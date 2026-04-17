"""Lambda handler for updating case file status.

Updates the case file status and statistics after pipeline completion or failure.
"""

import logging
import os

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def handler(event, context):
    """Update case file status and optionally record error details.

    Expected event:
        {
            "case_id": "...",
            "status": "indexed" | "error",
            "error_details": "..." (optional),
            "document_count": N (optional),
            "entity_count": N (optional),
            "relationship_count": N (optional)
        }

    Returns:
        {
            "case_id": "...",
            "status": "...",
            "updated": true
        }
    """
    from db.connection import ConnectionManager
    from db.neptune import NeptuneConnectionManager
    from models.case_file import CaseFileStatus
    from services.case_file_service import CaseFileService

    case_id = event["case_id"]
    status_str = event["status"]
    error_details = event.get("error_details")

    logger.info("Updating case %s status to %s", case_id, status_str)

    aurora_cm = ConnectionManager()
    neptune_cm = NeptuneConnectionManager(
        endpoint=os.environ.get("NEPTUNE_ENDPOINT", ""),
    )
    service = CaseFileService(aurora_cm, neptune_cm)

    status = CaseFileStatus(status_str)
    service.update_status(case_id, status, error_details=error_details)

    # Update statistics if provided
    doc_count = event.get("document_count")
    if doc_count is not None:
        with aurora_cm.cursor() as cur:
            cur.execute(
                """
                UPDATE case_files
                SET document_count = %s,
                    entity_count = %s,
                    relationship_count = %s
                WHERE case_id = %s
                """,
                (
                    doc_count,
                    event.get("entity_count", 0),
                    event.get("relationship_count", 0),
                    case_id,
                ),
            )

    logger.info("Case %s status updated to %s", case_id, status_str)

    return {
        "case_id": case_id,
        "status": status_str,
        "updated": True,
    }
