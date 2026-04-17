"""API Lambda handlers for Organization CRUD operations.

Endpoints:
    GET    /organizations          — list all organizations
    POST   /organizations          — create a new organization
    GET    /organizations/{id}     — get organization details
    PATCH  /organizations/{id}     — update organization settings
"""

import json
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def dispatch_handler(event, context):
    """Route to the correct handler based on HTTP method and resource path."""
    from lambdas.api.response_helper import CORS_HEADERS, error_response

    method = event.get("httpMethod", "")
    resource = event.get("resource", "")

    # Handle CORS preflight
    if method == "OPTIONS":
        return {"statusCode": 200, "headers": CORS_HEADERS, "body": ""}

    if resource == "/organizations" and method == "GET":
        return list_organizations_handler(event, context)
    if resource == "/organizations" and method == "POST":
        return create_organization_handler(event, context)
    if resource == "/organizations/{id}" and method == "GET":
        return get_organization_handler(event, context)
    if resource == "/organizations/{id}" and method == "PATCH":
        return update_organization_settings_handler(event, context)

    return error_response(404, "NOT_FOUND", f"No handler for {method} {resource}", event)


def _build_organization_service():
    """Construct an OrganizationService with dependencies from environment."""
    from db.connection import ConnectionManager
    from services.organization_service import OrganizationService

    return OrganizationService(ConnectionManager())



# ------------------------------------------------------------------
# GET /organizations
# ------------------------------------------------------------------

def list_organizations_handler(event, context):
    """List all organizations."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        svc = _build_organization_service()
        orgs = svc.list_organizations()
        return success_response(
            {"organizations": [_serialize(o) for o in orgs]},
            event=event,
        )
    except Exception as e:
        logger.exception("Failed to list organizations")
        return error_response(500, "INTERNAL_ERROR", str(e), event)


# ------------------------------------------------------------------
# POST /organizations
# ------------------------------------------------------------------

def create_organization_handler(event, context):
    """Create a new organization."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        body = (json.loads(event.get("body")) if isinstance(event.get("body"), str) else (event.get("body") or {}))
        org_name = body.get("org_name", "")

        if not org_name:
            return error_response(
                400, "VALIDATION_ERROR", "Missing required field: org_name", event
            )

        settings = body.get("settings")
        svc = _build_organization_service()
        org = svc.create_organization(org_name=org_name, settings=settings)
        return success_response({"organization": _serialize(org)}, status_code=201, event=event)
    except ValueError as e:
        return error_response(400, "VALIDATION_ERROR", str(e), event)
    except Exception as e:
        logger.exception("Failed to create organization")
        return error_response(500, "INTERNAL_ERROR", str(e), event)


# ------------------------------------------------------------------
# GET /organizations/{id}
# ------------------------------------------------------------------

def get_organization_handler(event, context):
    """Get a single organization by ID."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        org_id = event["pathParameters"]["id"]
        svc = _build_organization_service()
        org = svc.get_organization(org_id)
        return success_response({"organization": _serialize(org)}, event=event)
    except KeyError as e:
        if "Organization not found" in str(e):
            return error_response(404, "NOT_FOUND", str(e), event)
        raise
    except Exception as e:
        logger.exception("Failed to get organization")
        return error_response(500, "INTERNAL_ERROR", str(e), event)


# ------------------------------------------------------------------
# PATCH /organizations/{id}
# ------------------------------------------------------------------

def update_organization_settings_handler(event, context):
    """Update an organization's settings."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        org_id = event["pathParameters"]["id"]
        body = (json.loads(event.get("body")) if isinstance(event.get("body"), str) else (event.get("body") or {}))
        settings = body.get("settings")

        if settings is None:
            return error_response(
                400, "VALIDATION_ERROR", "Missing required field: settings", event
            )

        svc = _build_organization_service()
        org = svc.update_settings(org_id=org_id, settings=settings)
        return success_response({"organization": _serialize(org)}, event=event)
    except KeyError as e:
        if "Organization not found" in str(e):
            return error_response(404, "NOT_FOUND", str(e), event)
        raise
    except Exception as e:
        logger.exception("Failed to update organization settings")
        return error_response(500, "INTERNAL_ERROR", str(e), event)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _serialize(org) -> dict:
    """Convert an Organization model to a JSON-safe dict."""
    return {
        "org_id": org.org_id,
        "org_name": org.org_name,
        "settings": org.settings,
        "created_at": str(org.created_at),
    }
