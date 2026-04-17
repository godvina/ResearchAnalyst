"""API Lambda handlers for the Case Portfolio Dashboard.

Endpoints:
    GET  /portfolio/summary              — aggregate stats across all cases
    GET  /portfolio/cases                — filtered, sorted, paginated case list
    PUT  /portfolio/cases/{id}/priority  — set case priority
    PUT  /portfolio/cases/{id}/assign    — assign investigator to case
    POST /portfolio/bulk-action          — bulk assign/archive/prioritize
    GET  /portfolio/analytics            — portfolio analytics data
    GET  /portfolio/attention            — cases requiring attention
"""

import json
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def _build_portfolio_service():
    """Construct PortfolioService with dependencies."""
    from db.connection import ConnectionManager
    from services.portfolio_service import PortfolioService

    aurora_cm = ConnectionManager()
    return PortfolioService(aurora_cm)


def dispatch_handler(event, context):
    """Route to the correct handler based on HTTP method and resource path."""
    from lambdas.api.response_helper import CORS_HEADERS

    method = event.get("httpMethod", "")
    resource = event.get("resource", "")

    if method == "OPTIONS":
        return {"statusCode": 200, "headers": CORS_HEADERS, "body": ""}

    if resource == "/portfolio/summary" and method == "GET":
        return get_summary_handler(event, context)
    if resource == "/portfolio/cases" and method == "GET":
        return list_cases_handler(event, context)
    if resource == "/portfolio/cases/{id}/priority" and method == "PUT":
        return set_priority_handler(event, context)
    if resource == "/portfolio/cases/{id}/assign" and method == "PUT":
        return assign_case_handler(event, context)
    if resource == "/portfolio/bulk-action" and method == "POST":
        return bulk_action_handler(event, context)
    if resource == "/portfolio/analytics" and method == "GET":
        return get_analytics_handler(event, context)
    if resource == "/portfolio/attention" and method == "GET":
        return get_attention_handler(event, context)

    from lambdas.api.response_helper import error_response
    return error_response(404, "NOT_FOUND", f"No handler for {method} {resource}", event)


# ------------------------------------------------------------------
# GET /portfolio/summary
# ------------------------------------------------------------------

def get_summary_handler(event, context):
    """Get aggregate stats across all cases."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        svc = _build_portfolio_service()
        summary = svc.get_summary()
        return success_response(summary, 200, event)
    except Exception as exc:
        logger.exception("get_summary failed")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# GET /portfolio/cases
# ------------------------------------------------------------------

def list_cases_handler(event, context):
    """List cases with filtering, sorting, pagination."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        params = event.get("queryStringParameters") or {}
        svc = _build_portfolio_service()
        result = svc.list_cases(
            status=params.get("status"),
            priority=params.get("priority"),
            category=params.get("category"),
            assigned_to=params.get("assigned_to"),
            sort_by=params.get("sort_by", "last_activity"),
            sort_order=params.get("sort_order", "desc"),
            limit=int(params.get("limit", "50")),
            offset=int(params.get("offset", "0")),
        )
        return success_response(result, 200, event)
    except ValueError as exc:
        return error_response(400, "VALIDATION_ERROR", str(exc), event)
    except Exception as exc:
        logger.exception("list_cases failed")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# PUT /portfolio/cases/{id}/priority
# ------------------------------------------------------------------

def set_priority_handler(event, context):
    """Set case priority."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        if not case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case ID", event)

        body = (json.loads(event.get("body")) if isinstance(event.get("body"), str) else (event.get("body") or {}))
        priority = body.get("priority", "").strip()
        if not priority:
            return error_response(400, "VALIDATION_ERROR", "Missing 'priority'", event)

        svc = _build_portfolio_service()
        result = svc.set_priority(case_id, priority)
        return success_response(result, 200, event)

    except ValueError as exc:
        return error_response(400, "VALIDATION_ERROR", str(exc), event)
    except Exception as exc:
        logger.exception("set_priority failed")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# PUT /portfolio/cases/{id}/assign
# ------------------------------------------------------------------

def assign_case_handler(event, context):
    """Assign investigator to case."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        if not case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case ID", event)

        body = (json.loads(event.get("body")) if isinstance(event.get("body"), str) else (event.get("body") or {}))
        assigned_to = body.get("assigned_to", "").strip()
        if not assigned_to:
            return error_response(400, "VALIDATION_ERROR", "Missing 'assigned_to'", event)

        svc = _build_portfolio_service()
        result = svc.assign_case(case_id, assigned_to)
        return success_response(result, 200, event)

    except ValueError as exc:
        return error_response(400, "VALIDATION_ERROR", str(exc), event)
    except Exception as exc:
        logger.exception("assign_case failed")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# POST /portfolio/bulk-action
# ------------------------------------------------------------------

def bulk_action_handler(event, context):
    """Execute bulk action on multiple cases."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        body = (json.loads(event.get("body")) if isinstance(event.get("body"), str) else (event.get("body") or {}))
        action = body.get("action", "").strip()
        case_ids = body.get("case_ids", [])
        params = body.get("params", {})

        if not action:
            return error_response(400, "VALIDATION_ERROR", "Missing 'action'", event)
        if not case_ids or not isinstance(case_ids, list):
            return error_response(400, "VALIDATION_ERROR", "Missing or invalid 'case_ids'", event)

        svc = _build_portfolio_service()
        result = svc.bulk_action(action, case_ids, params)
        return success_response(result, 200, event)

    except ValueError as exc:
        return error_response(400, "VALIDATION_ERROR", str(exc), event)
    except Exception as exc:
        logger.exception("bulk_action failed")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# GET /portfolio/analytics
# ------------------------------------------------------------------

def get_analytics_handler(event, context):
    """Get portfolio analytics data."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        svc = _build_portfolio_service()
        analytics = svc.get_analytics()
        return success_response(analytics, 200, event)
    except Exception as exc:
        logger.exception("get_analytics failed")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# GET /portfolio/attention
# ------------------------------------------------------------------

def get_attention_handler(event, context):
    """Get cases requiring attention."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        svc = _build_portfolio_service()
        cases = svc.get_attention_cases()
        return success_response({"attention_cases": cases}, 200, event)
    except Exception as exc:
        logger.exception("get_attention failed")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)
