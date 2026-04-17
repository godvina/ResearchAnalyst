"""API Lambda handlers for the Investigator Workbench.

Endpoints:
    GET  /workbench/my-cases     — cases assigned to current user
    GET  /workbench/priorities   — AI-generated daily priorities
    GET  /workbench/activity     — recent activity feed
    GET  /workbench/findings     — all findings across cases
    POST /workbench/findings     — add a new finding
    GET  /workbench/metrics      — personal workload metrics
"""

import json
import logging
import os

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def _build_workbench_service():
    """Construct WorkbenchService with dependencies."""
    import boto3

    from db.connection import ConnectionManager
    from services.workbench_service import WorkbenchService

    aurora_cm = ConnectionManager()
    bedrock_client = boto3.client("bedrock-runtime")
    return WorkbenchService(aurora_cm, bedrock_client)


def _get_user_id(event: dict) -> str:
    """Extract user ID from request context or headers."""
    # Check authorizer claims first
    ctx = event.get("requestContext", {})
    authorizer = ctx.get("authorizer", {})
    claims = authorizer.get("claims", {})
    if claims.get("sub"):
        return claims["sub"]
    # Fall back to header or query param
    headers = event.get("headers") or {}
    if headers.get("x-user-id"):
        return headers["x-user-id"]
    params = event.get("queryStringParameters") or {}
    return params.get("user_id", "investigator")


def dispatch_handler(event, context):
    """Route to the correct handler based on HTTP method and resource path."""
    from lambdas.api.response_helper import CORS_HEADERS

    method = event.get("httpMethod", "")
    resource = event.get("resource", "")

    if method == "OPTIONS":
        return {"statusCode": 200, "headers": CORS_HEADERS, "body": ""}

    if resource == "/workbench/my-cases" and method == "GET":
        return get_my_cases_handler(event, context)
    if resource == "/workbench/priorities" and method == "GET":
        return get_priorities_handler(event, context)
    if resource == "/workbench/activity" and method == "GET":
        return get_activity_handler(event, context)
    if resource == "/workbench/findings" and method == "GET":
        return get_findings_handler(event, context)
    if resource == "/workbench/findings" and method == "POST":
        return add_finding_handler(event, context)
    if resource == "/workbench/metrics" and method == "GET":
        return get_metrics_handler(event, context)

    from lambdas.api.response_helper import error_response
    return error_response(404, "NOT_FOUND", f"No handler for {method} {resource}", event)


# ------------------------------------------------------------------
# GET /workbench/my-cases
# ------------------------------------------------------------------

def get_my_cases_handler(event, context):
    """Get cases assigned to current user grouped by swim lane."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        user_id = _get_user_id(event)
        svc = _build_workbench_service()
        result = svc.get_my_cases(user_id)
        return success_response(result, 200, event)
    except Exception as exc:
        logger.exception("get_my_cases failed")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# GET /workbench/priorities
# ------------------------------------------------------------------

def get_priorities_handler(event, context):
    """Get AI-generated daily priorities."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        user_id = _get_user_id(event)
        svc = _build_workbench_service()
        priorities = svc.get_daily_priorities(user_id)
        return success_response({"priorities": priorities}, 200, event)
    except Exception as exc:
        logger.exception("get_priorities failed")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# GET /workbench/activity
# ------------------------------------------------------------------

def get_activity_handler(event, context):
    """Get recent activity feed."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        user_id = _get_user_id(event)
        params = event.get("queryStringParameters") or {}
        limit = int(params.get("limit", "20"))

        svc = _build_workbench_service()
        activities = svc.get_activity_feed(user_id, limit=limit)
        return success_response({"activities": activities}, 200, event)
    except Exception as exc:
        logger.exception("get_activity failed")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# GET /workbench/findings
# ------------------------------------------------------------------

def get_findings_handler(event, context):
    """Get all findings across user's cases."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        user_id = _get_user_id(event)
        params = event.get("queryStringParameters") or {}
        case_id = params.get("case_id")
        limit = int(params.get("limit", "50"))

        svc = _build_workbench_service()
        findings = svc.get_findings(user_id, case_id=case_id, limit=limit)
        return success_response({"findings": findings}, 200, event)
    except Exception as exc:
        logger.exception("get_findings failed")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# POST /workbench/findings
# ------------------------------------------------------------------

def add_finding_handler(event, context):
    """Add a new finding to a case."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        user_id = _get_user_id(event)
        body = (json.loads(event.get("body")) if isinstance(event.get("body"), str) else (event.get("body") or {}))

        case_id = body.get("case_id", "").strip()
        if not case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing 'case_id'", event)

        finding_type = body.get("finding_type", "note")
        title = body.get("title", "").strip()
        content = body.get("content", "")
        entity_refs = body.get("entity_refs", [])
        document_refs = body.get("document_refs", [])

        if not title:
            return error_response(400, "VALIDATION_ERROR", "Missing 'title'", event)

        svc = _build_workbench_service()
        result = svc.add_finding(
            user_id=user_id,
            case_id=case_id,
            finding_type=finding_type,
            title=title,
            content=content,
            entity_refs=entity_refs,
            document_refs=document_refs,
        )
        return success_response(result, 201, event)

    except ValueError as exc:
        return error_response(400, "VALIDATION_ERROR", str(exc), event)
    except Exception as exc:
        logger.exception("add_finding failed")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# GET /workbench/metrics
# ------------------------------------------------------------------

def get_metrics_handler(event, context):
    """Get personal workload metrics."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        user_id = _get_user_id(event)
        svc = _build_workbench_service()
        metrics = svc.get_metrics(user_id)
        return success_response(metrics, 200, event)
    except Exception as exc:
        logger.exception("get_metrics failed")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)
