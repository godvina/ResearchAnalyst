"""API Lambda handlers for Decision Workflow operations.

Endpoints:
    POST   /decisions/{id}/confirm      — confirm an AI_Proposed decision
    POST   /decisions/{id}/override     — override an AI_Proposed decision
    GET    /case-files/{id}/decisions    — list all decisions for a case
"""

import json
import logging
import os

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def dispatch_handler(event, context):
    """Route to the correct handler based on HTTP method and resource path."""
    from lambdas.api.response_helper import CORS_HEADERS
    method = event.get("httpMethod", "")
    resource = event.get("resource", "")

    # Handle CORS preflight
    if method == "OPTIONS":
        return {"statusCode": 200, "headers": CORS_HEADERS, "body": ""}

    if resource == "/decisions/{id}/confirm" and method == "POST":
        return confirm_decision_handler(event, context)
    if resource == "/decisions/{id}/override" and method == "POST":
        return override_decision_handler(event, context)
    if resource == "/case-files/{id}/decisions" and method == "GET":
        return list_case_decisions_handler(event, context)

    from lambdas.api.response_helper import error_response
    return error_response(404, "NOT_FOUND", f"No handler for {method} {resource}", event)


def _build_decision_workflow_service():
    """Construct a DecisionWorkflowService with dependencies from environment."""
    from db.connection import ConnectionManager
    from services.decision_workflow_service import DecisionWorkflowService

    aurora_cm = ConnectionManager()
    return DecisionWorkflowService(aurora_cm)


# ------------------------------------------------------------------
# POST /decisions/{id}/confirm
# ------------------------------------------------------------------

def confirm_decision_handler(event, context):
    """Confirm an AI_Proposed decision. Requires attorney_id in body."""
    from lambdas.api.response_helper import error_response, success_response
    from services.decision_workflow_service import ConflictError

    try:
        decision_id = (event.get("pathParameters") or {}).get("id", "")
        if not decision_id:
            return error_response(400, "VALIDATION_ERROR", "Missing decision ID", event)

        body = (json.loads(event.get("body")) if isinstance(event.get("body"), str) else (event.get("body") or {}))
        attorney_id = body.get("attorney_id", "")
        if not attorney_id:
            return error_response(400, "VALIDATION_ERROR", "Missing required field: attorney_id", event)

        service = _build_decision_workflow_service()
        decision = service.confirm_decision(decision_id, attorney_id)

        return success_response(decision.model_dump(mode="json"), 200, event)

    except KeyError:
        return error_response(404, "NOT_FOUND", f"Decision not found: {decision_id}", event)
    except ConflictError as exc:
        return error_response(409, "CONFLICT", str(exc), event)
    except Exception as exc:
        logger.exception("Failed to confirm decision")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# POST /decisions/{id}/override
# ------------------------------------------------------------------

def override_decision_handler(event, context):
    """Override an AI_Proposed decision. Requires attorney_id and override_rationale."""
    from lambdas.api.response_helper import error_response, success_response
    from services.decision_workflow_service import ConflictError

    try:
        decision_id = (event.get("pathParameters") or {}).get("id", "")
        if not decision_id:
            return error_response(400, "VALIDATION_ERROR", "Missing decision ID", event)

        body = (json.loads(event.get("body")) if isinstance(event.get("body"), str) else (event.get("body") or {}))
        attorney_id = body.get("attorney_id", "")
        override_rationale = body.get("override_rationale", "")

        if not attorney_id:
            return error_response(400, "VALIDATION_ERROR", "Missing required field: attorney_id", event)
        if not override_rationale or not override_rationale.strip():
            return error_response(400, "VALIDATION_ERROR", "Missing required field: override_rationale", event)

        service = _build_decision_workflow_service()
        decision = service.override_decision(decision_id, attorney_id, override_rationale)

        return success_response(decision.model_dump(mode="json"), 200, event)

    except KeyError:
        return error_response(404, "NOT_FOUND", f"Decision not found: {decision_id}", event)
    except ConflictError as exc:
        return error_response(409, "CONFLICT", str(exc), event)
    except ValueError as exc:
        return error_response(400, "VALIDATION_ERROR", str(exc), event)
    except Exception as exc:
        logger.exception("Failed to override decision")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# GET /case-files/{id}/decisions
# ------------------------------------------------------------------

def list_case_decisions_handler(event, context):
    """List all decisions for a case with optional filters."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        if not case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case file ID", event)

        params = event.get("queryStringParameters") or {}
        decision_type = params.get("decision_type")
        state = params.get("state")

        service = _build_decision_workflow_service()
        decisions = service.get_case_decisions(case_id, decision_type=decision_type, state=state)

        result = {
            "case_id": case_id,
            "decisions": [d.model_dump(mode="json") for d in decisions],
            "total": len(decisions),
        }

        return success_response(result, 200, event)

    except Exception as exc:
        logger.exception("Failed to list case decisions")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)
