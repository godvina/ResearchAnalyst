"""API Lambda handler for drill-down investigation.

Endpoint:
    POST /case-files/{id}/drill-down — create a sub-case file from a pattern or entity
"""

import json
import logging
import os

from services.access_control_middleware import with_access_control

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def _build_case_file_service():
    """Construct a CaseFileService with dependencies from environment."""
    from db.connection import ConnectionManager
    from db.neptune import NeptuneConnectionManager
    from services.case_file_service import CaseFileService

    aurora_cm = ConnectionManager()
    neptune_cm = NeptuneConnectionManager(
        endpoint=os.environ.get("NEPTUNE_ENDPOINT", ""),
    )
    return CaseFileService(aurora_cm, neptune_cm)


# ------------------------------------------------------------------
# POST /case-files/{id}/drill-down
# ------------------------------------------------------------------

@with_access_control
def drill_down_handler(event, context):
    """Create a sub-case file for focused investigation."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        parent_case_id = (event.get("pathParameters") or {}).get("id", "")
        if not parent_case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case file ID", event)

        body = (json.loads(event.get("body")) if isinstance(event.get("body"), str) else (event.get("body") or {}))
        topic_name = body.get("topic_name", "")
        description = body.get("description", "")

        if not topic_name or not description:
            missing = []
            if not topic_name:
                missing.append("topic_name")
            if not description:
                missing.append("description")
            return error_response(
                400, "VALIDATION_ERROR",
                f"Missing required fields: {', '.join(missing)}", event,
            )

        entity_names = body.get("entity_names")
        pattern_id = body.get("pattern_id")

        service = _build_case_file_service()
        sub_case = service.create_sub_case_file(
            parent_case_id=parent_case_id,
            topic_name=topic_name,
            description=description,
            entity_names=entity_names,
            pattern_id=pattern_id,
        )

        return success_response(sub_case.model_dump(mode="json"), 201, event)

    except KeyError:
        return error_response(
            404, "NOT_FOUND", f"Case file not found: {parent_case_id}", event,
        )
    except ValueError as exc:
        return error_response(400, "VALIDATION_ERROR", str(exc), event)
    except Exception as exc:
        logger.exception("Failed to create sub-case file")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)
