"""API Lambda handlers for Statute Library operations.

Endpoints:
    GET    /statutes        — list all statutes
    GET    /statutes/{id}   — get statute with elements
"""

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

    if resource == "/statutes" and method == "GET":
        return list_statutes_handler(event, context)
    if resource == "/statutes/{id}" and method == "GET":
        return get_statute_handler(event, context)

    from lambdas.api.response_helper import error_response
    return error_response(404, "NOT_FOUND", f"No handler for {method} {resource}", event)


def _get_aurora_connection():
    """Get an Aurora connection manager."""
    from db.connection import ConnectionManager
    return ConnectionManager()


# ------------------------------------------------------------------
# GET /statutes
# ------------------------------------------------------------------

def list_statutes_handler(event, context):
    """List all statutes in the library."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        cm = _get_aurora_connection()
        with cm.cursor() as cur:
            cur.execute(
                "SELECT statute_id, citation, title, description, created_at "
                "FROM statutes ORDER BY citation"
            )
            rows = cur.fetchall()

        statutes = [
            {
                "statute_id": str(r[0]),
                "citation": r[1],
                "title": r[2],
                "description": r[3],
                "created_at": str(r[4]) if r[4] else None,
            }
            for r in rows
        ]

        return success_response({"statutes": statutes, "total": len(statutes)}, 200, event)

    except Exception as exc:
        logger.exception("Failed to list statutes")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# GET /statutes/{id}
# ------------------------------------------------------------------

def get_statute_handler(event, context):
    """Get a statute with its statutory elements."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        statute_id = (event.get("pathParameters") or {}).get("id", "")
        if not statute_id:
            return error_response(400, "VALIDATION_ERROR", "Missing statute ID", event)

        cm = _get_aurora_connection()
        with cm.cursor() as cur:
            cur.execute(
                "SELECT statute_id, citation, title, description, created_at "
                "FROM statutes WHERE statute_id = %s",
                (statute_id,),
            )
            row = cur.fetchone()

        if not row:
            return error_response(404, "NOT_FOUND", f"Statute not found: {statute_id}", event)

        statute = {
            "statute_id": str(row[0]),
            "citation": row[1],
            "title": row[2],
            "description": row[3],
            "created_at": str(row[4]) if row[4] else None,
        }

        # Fetch elements
        with cm.cursor() as cur:
            cur.execute(
                "SELECT element_id, statute_id, display_name, description, element_order "
                "FROM statutory_elements WHERE statute_id = %s ORDER BY element_order",
                (statute_id,),
            )
            element_rows = cur.fetchall()

        statute["elements"] = [
            {
                "element_id": str(r[0]),
                "statute_id": str(r[1]),
                "display_name": r[2],
                "description": r[3],
                "element_order": r[4],
            }
            for r in element_rows
        ]

        return success_response(statute, 200, event)

    except Exception as exc:
        logger.exception("Failed to get statute")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)
