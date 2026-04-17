"""API Lambda handlers for cross-case analysis and graph management.

Endpoints:
    POST  /cross-case/analyze     — run cross-case analysis on selected cases
    POST  /cross-case/graphs      — create a cross-case graph
    PATCH /cross-case/graphs/{id} — update cross-case graph membership
    GET   /cross-case/graphs/{id} — get cross-case graph details
"""

import json
import logging
import os

from services.access_control_middleware import with_access_control

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def _build_services():
    """Construct CrossCaseService and CaseFileService from environment."""
    import boto3

    from db.connection import ConnectionManager
    from db.neptune import NeptuneConnectionManager
    from services.case_file_service import CaseFileService
    from services.cross_case_service import CrossCaseService

    aurora_cm = ConnectionManager()
    neptune_cm = NeptuneConnectionManager(
        endpoint=os.environ.get("NEPTUNE_ENDPOINT", ""),
    )
    bedrock = boto3.client("bedrock-runtime")
    case_file_service = CaseFileService(aurora_cm, neptune_cm)
    cross_case_service = CrossCaseService(neptune_cm, aurora_cm, case_file_service, bedrock)
    return cross_case_service, case_file_service


# ------------------------------------------------------------------
# POST /cross-case/analyze
# ------------------------------------------------------------------

@with_access_control
def analyze_handler(event, context):
    """Run cross-case analysis on selected case files."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        body = (json.loads(event.get("body")) if isinstance(event.get("body"), str) else (event.get("body") or {}))
        case_ids = body.get("case_ids", [])

        if not case_ids or len(case_ids) < 2:
            return error_response(
                400, "VALIDATION_ERROR",
                "At least two case_ids are required for cross-case analysis", event,
            )

        cross_case_service, _ = _build_services()
        report = cross_case_service.generate_cross_reference_report(case_ids)

        return success_response(report.model_dump(mode="json"), 200, event)

    except KeyError as exc:
        return error_response(404, "NOT_FOUND", str(exc), event)
    except Exception as exc:
        logger.exception("Failed to run cross-case analysis")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# POST /cross-case/graphs
# ------------------------------------------------------------------

@with_access_control
def create_graph_handler(event, context):
    """Create a new cross-case graph."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        body = (json.loads(event.get("body")) if isinstance(event.get("body"), str) else (event.get("body") or {}))
        name = body.get("name", "")
        case_ids = body.get("case_ids", [])

        if not name:
            return error_response(400, "VALIDATION_ERROR", "Missing 'name' field", event)
        if not case_ids or len(case_ids) < 2:
            return error_response(
                400, "VALIDATION_ERROR",
                "At least two case_ids are required", event,
            )

        _, case_file_service = _build_services()
        graph = case_file_service.create_cross_case_graph(name=name, case_ids=case_ids)

        return success_response(graph.model_dump(mode="json"), 201, event)

    except ValueError as exc:
        return error_response(400, "VALIDATION_ERROR", str(exc), event)
    except Exception as exc:
        logger.exception("Failed to create cross-case graph")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# PATCH /cross-case/graphs/{id}
# ------------------------------------------------------------------

@with_access_control
def update_graph_handler(event, context):
    """Update cross-case graph membership (add/remove case files)."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        graph_id = (event.get("pathParameters") or {}).get("id", "")
        if not graph_id:
            return error_response(400, "VALIDATION_ERROR", "Missing graph ID", event)

        body = (json.loads(event.get("body")) if isinstance(event.get("body"), str) else (event.get("body") or {}))
        add_case_ids = body.get("add_case_ids")
        remove_case_ids = body.get("remove_case_ids")

        if not add_case_ids and not remove_case_ids:
            return error_response(
                400, "VALIDATION_ERROR",
                "Provide 'add_case_ids' and/or 'remove_case_ids'", event,
            )

        _, case_file_service = _build_services()
        graph = case_file_service.update_cross_case_graph(
            graph_id=graph_id,
            add_case_ids=add_case_ids,
            remove_case_ids=remove_case_ids,
        )

        return success_response(graph.model_dump(mode="json"), 200, event)

    except KeyError:
        return error_response(404, "NOT_FOUND", f"Cross-case graph not found: {graph_id}", event)
    except ValueError as exc:
        return error_response(400, "VALIDATION_ERROR", str(exc), event)
    except Exception as exc:
        logger.exception("Failed to update cross-case graph")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# GET /cross-case/graphs/{id}
# ------------------------------------------------------------------

@with_access_control
def get_graph_handler(event, context):
    """Get cross-case graph details."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        graph_id = (event.get("pathParameters") or {}).get("id", "")
        if not graph_id:
            return error_response(400, "VALIDATION_ERROR", "Missing graph ID", event)

        _, case_file_service = _build_services()
        graph = case_file_service.get_cross_case_graph(graph_id)

        return success_response(graph.model_dump(mode="json"), 200, event)

    except KeyError:
        return error_response(404, "NOT_FOUND", f"Cross-case graph not found: {graph_id}", event)
    except Exception as exc:
        logger.exception("Failed to get cross-case graph")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)
