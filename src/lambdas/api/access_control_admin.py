"""API Lambda handlers for Access Control Admin endpoints.

Endpoints:
    POST   /admin/users                    — create platform user
    GET    /admin/users                    — list platform users
    GET    /admin/users/{id}               — get user details
    PUT    /admin/users/{id}               — update user (clearance, role)
    DELETE /admin/users/{id}               — delete user
    PUT    /matters/{id}/security-label    — update case default label
    PUT    /documents/{id}/security-label  — set document label override
    DELETE /documents/{id}/security-label  — clear document label override
    GET    /admin/audit-log                — query audit log with filters
"""

import json
import logging
import uuid
from datetime import datetime, timezone

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

VALID_LABELS = ("public", "restricted", "confidential", "top_secret")
VALID_ROLES = ("admin", "analyst", "reviewer", "supervisor")


def dispatch_handler(event, context):
    """Route to the correct handler based on HTTP method and resource path."""
    from lambdas.api.response_helper import CORS_HEADERS
    method = event.get("httpMethod", "")
    resource = event.get("resource", "")

    if method == "OPTIONS":
        return {"statusCode": 200, "headers": CORS_HEADERS, "body": ""}

    # --- User CRUD ---
    if resource == "/admin/users" and method == "POST":
        return create_user(event, context)
    if resource == "/admin/users" and method == "GET":
        return list_users(event, context)
    if resource == "/admin/users/{id}" and method == "GET":
        return get_user(event, context)
    if resource == "/admin/users/{id}" and method == "PUT":
        return update_user(event, context)
    if resource == "/admin/users/{id}" and method == "DELETE":
        return delete_user(event, context)

    # --- Security label management ---
    if resource == "/matters/{id}/security-label" and method == "PUT":
        return update_matter_label(event, context)
    if resource == "/documents/{id}/security-label" and method == "PUT":
        return set_document_label(event, context)
    if resource == "/documents/{id}/security-label" and method == "DELETE":
        return clear_document_label(event, context)

    # --- Audit log ---
    if resource == "/admin/audit-log" and method == "GET":
        return query_audit_log(event, context)

    from lambdas.api.response_helper import error_response
    return error_response(404, "NOT_FOUND", f"No handler for {method} {resource}", event)


# ------------------------------------------------------------------
# Service helpers
# ------------------------------------------------------------------

def _build_services():
    """Return (AccessControlService, AuditService) using in-memory stores for MVP."""
    from services.access_control_service import AccessControlService
    from services.audit_service import AuditService

    audit = AuditService()
    ac = AccessControlService(audit_service=audit)
    return ac, audit


# Singleton services for the lifetime of the Lambda container
_ac_service = None
_audit_service = None


def _get_services():
    global _ac_service, _audit_service
    if _ac_service is None:
        _ac_service, _audit_service = _build_services()
    return _ac_service, _audit_service


def _validate_label(label):
    """Return error message if label is invalid, else None."""
    if label not in VALID_LABELS:
        return f"Invalid security_label: '{label}'. Must be one of: {list(VALID_LABELS)}"
    return None


# ------------------------------------------------------------------
# POST /admin/users
# ------------------------------------------------------------------

def create_user(event, context):
    from lambdas.api.response_helper import error_response, success_response
    try:
        body = (json.loads(event.get("body")) if isinstance(event.get("body"), str) else (event.get("body") or {}))
        username = body.get("username", "").strip()
        display_name = body.get("display_name", "").strip()
        role = body.get("role", "analyst").strip()
        clearance_level = body.get("clearance_level", "restricted").strip()

        if not username:
            return error_response(400, "VALIDATION_ERROR", "Missing required field: username", event)

        label_err = _validate_label(clearance_level)
        if label_err:
            return error_response(400, "VALIDATION_ERROR", label_err, event)

        ac, audit = _get_services()

        user_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        user_data = {
            "user_id": user_id,
            "username": username,
            "display_name": display_name or username,
            "role": role,
            "clearance_level": clearance_level,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }
        # Register in the in-memory store
        from models.access_control import SecurityLabel
        ac.register_user({
            "user_id": user_id,
            "username": username,
            "clearance_level": SecurityLabel[clearance_level.upper()],
            "role": role,
            "groups": [],
        })

        return success_response(user_data, 201, event)
    except Exception as exc:
        logger.exception("Failed to create user")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# GET /admin/users
# ------------------------------------------------------------------

def list_users(event, context):
    from lambdas.api.response_helper import error_response, success_response
    try:
        ac, _ = _get_services()
        users = []
        for uid, u in ac._users.items():
            users.append({
                "user_id": u["user_id"],
                "username": u.get("username", uid),
                "display_name": u.get("display_name", u.get("username", uid)),
                "role": u.get("role", "analyst"),
                "clearance_level": u["clearance_level"].name.lower() if hasattr(u["clearance_level"], "name") else str(u["clearance_level"]),
            })
        return success_response({"users": users}, 200, event)
    except Exception as exc:
        logger.exception("Failed to list users")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# GET /admin/users/{id}
# ------------------------------------------------------------------

def get_user(event, context):
    from lambdas.api.response_helper import error_response, success_response
    try:
        user_id = (event.get("pathParameters") or {}).get("id", "")
        if not user_id:
            return error_response(400, "VALIDATION_ERROR", "Missing user ID", event)

        ac, _ = _get_services()
        u = ac._users.get(user_id)
        if not u:
            return error_response(404, "NOT_FOUND", f"User not found: {user_id}", event)

        return success_response({
            "user_id": u["user_id"],
            "username": u.get("username", user_id),
            "display_name": u.get("display_name", u.get("username", user_id)),
            "role": u.get("role", "analyst"),
            "clearance_level": u["clearance_level"].name.lower() if hasattr(u["clearance_level"], "name") else str(u["clearance_level"]),
        }, 200, event)
    except Exception as exc:
        logger.exception("Failed to get user")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# PUT /admin/users/{id}
# ------------------------------------------------------------------

def update_user(event, context):
    from lambdas.api.response_helper import error_response, success_response
    try:
        user_id = (event.get("pathParameters") or {}).get("id", "")
        if not user_id:
            return error_response(400, "VALIDATION_ERROR", "Missing user ID", event)

        ac, audit = _get_services()
        u = ac._users.get(user_id)
        if not u:
            return error_response(404, "NOT_FOUND", f"User not found: {user_id}", event)

        body = (json.loads(event.get("body")) if isinstance(event.get("body"), str) else (event.get("body") or {}))
        from models.access_control import SecurityLabel

        if "clearance_level" in body:
            new_cl = body["clearance_level"].strip()
            label_err = _validate_label(new_cl)
            if label_err:
                return error_response(400, "VALIDATION_ERROR", label_err, event)
            prev = u["clearance_level"].name.lower() if hasattr(u["clearance_level"], "name") else str(u["clearance_level"])
            u["clearance_level"] = SecurityLabel[new_cl.upper()]
            changed_by = body.get("changed_by", "admin")
            audit.log_label_change("user", user_id, prev, new_cl, changed_by)

        if "role" in body:
            u["role"] = body["role"].strip()

        return success_response({
            "user_id": u["user_id"],
            "username": u.get("username", user_id),
            "display_name": u.get("display_name", u.get("username", user_id)),
            "role": u.get("role", "analyst"),
            "clearance_level": u["clearance_level"].name.lower() if hasattr(u["clearance_level"], "name") else str(u["clearance_level"]),
        }, 200, event)
    except Exception as exc:
        logger.exception("Failed to update user")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# DELETE /admin/users/{id}
# ------------------------------------------------------------------

def delete_user(event, context):
    from lambdas.api.response_helper import error_response, success_response
    try:
        user_id = (event.get("pathParameters") or {}).get("id", "")
        if not user_id:
            return error_response(400, "VALIDATION_ERROR", "Missing user ID", event)

        ac, _ = _get_services()
        if user_id not in ac._users:
            return error_response(404, "NOT_FOUND", f"User not found: {user_id}", event)

        del ac._users[user_id]
        return success_response({"deleted": True, "user_id": user_id}, 200, event)
    except Exception as exc:
        logger.exception("Failed to delete user")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# PUT /matters/{id}/security-label
# ------------------------------------------------------------------

def update_matter_label(event, context):
    """Update the default security label for a matter/case.

    Does NOT modify any document-level overrides.
    """
    from lambdas.api.response_helper import error_response, success_response
    try:
        matter_id = (event.get("pathParameters") or {}).get("id", "")
        if not matter_id:
            return error_response(400, "VALIDATION_ERROR", "Missing matter ID", event)

        body = (json.loads(event.get("body")) if isinstance(event.get("body"), str) else (event.get("body") or {}))
        new_label = body.get("security_label", "").strip()
        if not new_label:
            return error_response(400, "VALIDATION_ERROR", "Missing required field: security_label", event)

        label_err = _validate_label(new_label)
        if label_err:
            return error_response(400, "VALIDATION_ERROR", label_err, event)

        changed_by = body.get("changed_by", "admin")
        _, audit = _get_services()

        # For MVP, just log the audit entry (actual DB update would happen with real DB)
        previous_label = body.get("previous_label", "restricted")
        audit.log_label_change("matter", matter_id, previous_label, new_label, changed_by)

        return success_response({
            "matter_id": matter_id,
            "security_label": new_label,
            "updated": True,
        }, 200, event)
    except Exception as exc:
        logger.exception("Failed to update matter label")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# PUT /documents/{id}/security-label
# ------------------------------------------------------------------

def set_document_label(event, context):
    """Set a document-level security label override."""
    from lambdas.api.response_helper import error_response, success_response
    try:
        doc_id = (event.get("pathParameters") or {}).get("id", "")
        if not doc_id:
            return error_response(400, "VALIDATION_ERROR", "Missing document ID", event)

        body = (json.loads(event.get("body")) if isinstance(event.get("body"), str) else (event.get("body") or {}))
        new_label = body.get("security_label", "").strip()
        if not new_label:
            return error_response(400, "VALIDATION_ERROR", "Missing required field: security_label", event)

        label_err = _validate_label(new_label)
        if label_err:
            return error_response(400, "VALIDATION_ERROR", label_err, event)

        changed_by = body.get("changed_by", "admin")
        _, audit = _get_services()

        previous_label = body.get("previous_label")
        audit.log_label_change("document", doc_id, previous_label, new_label, changed_by)

        return success_response({
            "document_id": doc_id,
            "security_label_override": new_label,
            "updated": True,
        }, 200, event)
    except Exception as exc:
        logger.exception("Failed to set document label")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# DELETE /documents/{id}/security-label
# ------------------------------------------------------------------

def clear_document_label(event, context):
    """Clear a document-level security label override."""
    from lambdas.api.response_helper import error_response, success_response
    try:
        doc_id = (event.get("pathParameters") or {}).get("id", "")
        if not doc_id:
            return error_response(400, "VALIDATION_ERROR", "Missing document ID", event)

        _, audit = _get_services()
        audit.log_label_change("document", doc_id, None, None, "admin", "override_cleared")

        return success_response({
            "document_id": doc_id,
            "security_label_override": None,
            "cleared": True,
        }, 200, event)
    except Exception as exc:
        logger.exception("Failed to clear document label")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# GET /admin/audit-log
# ------------------------------------------------------------------

def query_audit_log(event, context):
    """Query audit log with optional filters, reverse chronological."""
    from lambdas.api.response_helper import error_response, success_response
    try:
        params = event.get("queryStringParameters") or {}
        kwargs = {}
        if "entity_type" in params:
            kwargs["entity_type"] = params["entity_type"]
        if "entity_id" in params:
            kwargs["entity_id"] = params["entity_id"]
        if "changed_by" in params:
            kwargs["changed_by"] = params["changed_by"]
        if "date_from" in params:
            kwargs["date_from"] = datetime.fromisoformat(params["date_from"])
        if "date_to" in params:
            kwargs["date_to"] = datetime.fromisoformat(params["date_to"])
        if "limit" in params:
            kwargs["limit"] = int(params["limit"])
        if "offset" in params:
            kwargs["offset"] = int(params["offset"])

        _, audit = _get_services()
        entries = audit.query_audit_log(**kwargs)

        return success_response({"audit_entries": entries, "count": len(entries)}, 200, event)
    except (ValueError, TypeError) as exc:
        return error_response(400, "VALIDATION_ERROR", str(exc), event)
    except Exception as exc:
        logger.exception("Failed to query audit log")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)
