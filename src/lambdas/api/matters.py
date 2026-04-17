"""API Lambda handlers for Matter and Collection CRUD operations.

Endpoints:
    GET    /organizations/{org_id}/matters              — list matters for org
    POST   /organizations/{org_id}/matters              — create a new matter
    GET    /matters/{id}                                — get matter details
    PUT    /matters/{id}                                — update matter status
    DELETE /matters/{id}                                — delete a matter
    GET    /matters/{id}/collections                    — list collections for matter
    POST   /matters/{id}/collections                    — create a new collection
    GET    /matters/{id}/collections/{cid}              — get collection details
    POST   /matters/{id}/collections/{cid}/promote      — promote collection
    POST   /matters/{id}/collections/{cid}/reject       — reject collection
"""

import json
import logging
import os

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

    # Matter routes under organization
    if resource == "/organizations/{org_id}/matters" and method == "GET":
        return list_matters(event, context)
    if resource == "/organizations/{org_id}/matters" and method == "POST":
        return create_matter(event, context)

    # Matter direct routes
    if resource == "/matters/{id}" and method == "GET":
        return get_matter(event, context)
    if resource == "/matters/{id}" and method == "PUT":
        return update_status(event, context)
    if resource == "/matters/{id}" and method == "DELETE":
        return delete_matter(event, context)

    # Collection routes under matter
    if resource == "/matters/{id}/collections" and method == "GET":
        return list_collections(event, context)
    if resource == "/matters/{id}/collections" and method == "POST":
        return create_collection(event, context)
    if resource == "/matters/{id}/collections/{cid}" and method == "GET":
        return get_collection(event, context)
    if resource == "/matters/{id}/collections/{cid}/promote" and method == "POST":
        return promote_collection(event, context)
    if resource == "/matters/{id}/collections/{cid}/reject" and method == "POST":
        return reject_collection(event, context)

    return error_response(404, "NOT_FOUND", f"No handler for {method} {resource}", event)


# ------------------------------------------------------------------
# Service builders
# ------------------------------------------------------------------

def _build_matter_service():
    """Construct a MatterService with dependencies from environment."""
    from db.connection import ConnectionManager
    from services.matter_service import MatterService

    return MatterService(ConnectionManager())


def _build_collection_service():
    """Construct a CollectionService with dependencies from environment."""
    from db.connection import ConnectionManager
    from services.collection_service import CollectionService

    return CollectionService(ConnectionManager())


def _build_promotion_service():
    """Construct a PromotionService with dependencies from environment."""
    from db.connection import ConnectionManager
    from db.neptune import NeptuneConnectionManager
    from services.promotion_service import PromotionService

    aurora_cm = ConnectionManager()
    neptune_cm = NeptuneConnectionManager(
        endpoint=os.environ.get("NEPTUNE_ENDPOINT", ""),
    )
    return PromotionService(aurora_cm, neptune_cm)


# ------------------------------------------------------------------
# GET /organizations/{org_id}/matters
# ------------------------------------------------------------------

def list_matters(event, context):
    """List matters for an organization."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        org_id = (event.get("pathParameters") or {}).get("org_id", "")
        if not org_id:
            return error_response(400, "VALIDATION_ERROR", "Missing org_id", event)

        params = event.get("queryStringParameters") or {}
        status_filter = params.get("status")

        service = _build_matter_service()
        matters = service.list_matters(org_id, status=status_filter)

        return success_response(
            {"matters": [m.model_dump(mode="json") for m in matters]},
            200, event,
        )

    except Exception as exc:
        logger.exception("Failed to list matters")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# POST /organizations/{org_id}/matters
# ------------------------------------------------------------------

def create_matter(event, context):
    """Create a new matter under an organization."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        org_id = (event.get("pathParameters") or {}).get("org_id", "")
        if not org_id:
            return error_response(400, "VALIDATION_ERROR", "Missing org_id", event)

        body = (json.loads(event.get("body")) if isinstance(event.get("body"), str) else (event.get("body") or {}))
        matter_name = body.get("matter_name", "")
        description = body.get("description", "")

        if not matter_name or not description:
            missing = []
            if not matter_name:
                missing.append("matter_name")
            if not description:
                missing.append("description")
            return error_response(
                400, "VALIDATION_ERROR",
                f"Missing required fields: {', '.join(missing)}", event,
            )

        service = _build_matter_service()
        matter = service.create_matter(
            org_id=org_id,
            matter_name=matter_name,
            description=description,
            matter_type=body.get("matter_type", "investigation"),
        )

        return success_response(matter.model_dump(mode="json"), 201, event)

    except ValueError as exc:
        return error_response(400, "VALIDATION_ERROR", str(exc), event)
    except Exception as exc:
        logger.exception("Failed to create matter")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# GET /matters/{id}
# ------------------------------------------------------------------

def get_matter(event, context):
    """Get matter details by ID."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        matter_id = (event.get("pathParameters") or {}).get("id", "")
        if not matter_id:
            return error_response(400, "VALIDATION_ERROR", "Missing matter ID", event)

        # org_id from query param or header (path params for now)
        params = event.get("queryStringParameters") or {}
        headers = event.get("headers") or {}
        org_id = params.get("org_id") or headers.get("x-org-id", "")
        if not org_id:
            return error_response(400, "VALIDATION_ERROR", "Missing org_id query parameter or x-org-id header", event)

        service = _build_matter_service()
        matter = service.get_matter(matter_id, org_id)

        return success_response(matter.model_dump(mode="json"), 200, event)

    except KeyError:
        return error_response(404, "NOT_FOUND", f"Matter not found: {matter_id}", event)
    except Exception as exc:
        logger.exception("Failed to get matter")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# PUT /matters/{id}
# ------------------------------------------------------------------

def update_status(event, context):
    """Update matter status."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        matter_id = (event.get("pathParameters") or {}).get("id", "")
        if not matter_id:
            return error_response(400, "VALIDATION_ERROR", "Missing matter ID", event)

        body = (json.loads(event.get("body")) if isinstance(event.get("body"), str) else (event.get("body") or {}))
        status = body.get("status", "")
        if not status:
            return error_response(400, "VALIDATION_ERROR", "Missing required field: status", event)

        params = event.get("queryStringParameters") or {}
        headers = event.get("headers") or {}
        org_id = params.get("org_id") or headers.get("x-org-id", "")
        if not org_id:
            return error_response(400, "VALIDATION_ERROR", "Missing org_id query parameter or x-org-id header", event)

        service = _build_matter_service()
        matter = service.update_status(
            matter_id=matter_id,
            org_id=org_id,
            status=status,
            error_details=body.get("error_details"),
        )

        return success_response(matter.model_dump(mode="json"), 200, event)

    except KeyError:
        return error_response(404, "NOT_FOUND", f"Matter not found: {matter_id}", event)
    except ValueError as exc:
        return error_response(400, "VALIDATION_ERROR", str(exc), event)
    except Exception as exc:
        logger.exception("Failed to update matter status")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# DELETE /matters/{id}
# ------------------------------------------------------------------

def delete_matter(event, context):
    """Delete a matter."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        matter_id = (event.get("pathParameters") or {}).get("id", "")
        if not matter_id:
            return error_response(400, "VALIDATION_ERROR", "Missing matter ID", event)

        params = event.get("queryStringParameters") or {}
        headers = event.get("headers") or {}
        org_id = params.get("org_id") or headers.get("x-org-id", "")
        if not org_id:
            return error_response(400, "VALIDATION_ERROR", "Missing org_id query parameter or x-org-id header", event)

        service = _build_matter_service()
        service.delete_matter(matter_id, org_id)

        return success_response({"deleted": True, "matter_id": matter_id}, 200, event)

    except KeyError:
        return error_response(404, "NOT_FOUND", f"Matter not found: {matter_id}", event)
    except Exception as exc:
        logger.exception("Failed to delete matter")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# GET /matters/{id}/collections
# ------------------------------------------------------------------

def list_collections(event, context):
    """List collections for a matter."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        matter_id = (event.get("pathParameters") or {}).get("id", "")
        if not matter_id:
            return error_response(400, "VALIDATION_ERROR", "Missing matter ID", event)

        params = event.get("queryStringParameters") or {}
        headers = event.get("headers") or {}
        org_id = params.get("org_id") or headers.get("x-org-id", "")
        if not org_id:
            return error_response(400, "VALIDATION_ERROR", "Missing org_id query parameter or x-org-id header", event)

        service = _build_collection_service()
        collections = service.list_collections(matter_id, org_id)

        return success_response(
            {"collections": [c.model_dump(mode="json") for c in collections]},
            200, event,
        )

    except Exception as exc:
        logger.exception("Failed to list collections")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# POST /matters/{id}/collections
# ------------------------------------------------------------------

def create_collection(event, context):
    """Create a new collection under a matter."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        matter_id = (event.get("pathParameters") or {}).get("id", "")
        if not matter_id:
            return error_response(400, "VALIDATION_ERROR", "Missing matter ID", event)

        body = (json.loads(event.get("body")) if isinstance(event.get("body"), str) else (event.get("body") or {}))
        collection_name = body.get("collection_name", "")
        if not collection_name:
            return error_response(
                400, "VALIDATION_ERROR",
                "Missing required field: collection_name", event,
            )

        params = event.get("queryStringParameters") or {}
        headers = event.get("headers") or {}
        org_id = params.get("org_id") or headers.get("x-org-id", "")
        if not org_id:
            return error_response(400, "VALIDATION_ERROR", "Missing org_id query parameter or x-org-id header", event)

        service = _build_collection_service()
        collection = service.create_collection(
            matter_id=matter_id,
            org_id=org_id,
            collection_name=collection_name,
            source_description=body.get("source_description", ""),
        )

        return success_response(collection.model_dump(mode="json"), 201, event)

    except ValueError as exc:
        return error_response(400, "VALIDATION_ERROR", str(exc), event)
    except Exception as exc:
        logger.exception("Failed to create collection")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# GET /matters/{id}/collections/{cid}
# ------------------------------------------------------------------

def get_collection(event, context):
    """Get collection details by ID."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        collection_id = (event.get("pathParameters") or {}).get("cid", "")
        if not collection_id:
            return error_response(400, "VALIDATION_ERROR", "Missing collection ID", event)

        params = event.get("queryStringParameters") or {}
        headers = event.get("headers") or {}
        org_id = params.get("org_id") or headers.get("x-org-id", "")
        if not org_id:
            return error_response(400, "VALIDATION_ERROR", "Missing org_id query parameter or x-org-id header", event)

        service = _build_collection_service()
        collection = service.get_collection(collection_id, org_id)

        return success_response(collection.model_dump(mode="json"), 200, event)

    except KeyError:
        return error_response(404, "NOT_FOUND", f"Collection not found: {collection_id}", event)
    except Exception as exc:
        logger.exception("Failed to get collection")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# POST /matters/{id}/collections/{cid}/promote
# ------------------------------------------------------------------

def promote_collection(event, context):
    """Promote a collection — merge its entities into the matter graph."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        matter_id = (event.get("pathParameters") or {}).get("id", "")
        collection_id = (event.get("pathParameters") or {}).get("cid", "")
        if not matter_id or not collection_id:
            return error_response(400, "VALIDATION_ERROR", "Missing matter ID or collection ID", event)

        params = event.get("queryStringParameters") or {}
        headers = event.get("headers") or {}
        org_id = params.get("org_id") or headers.get("x-org-id", "")
        if not org_id:
            return error_response(400, "VALIDATION_ERROR", "Missing org_id query parameter or x-org-id header", event)

        service = _build_promotion_service()
        snapshot = service.promote_collection(
            matter_id=matter_id,
            collection_id=collection_id,
            org_id=org_id,
        )

        return success_response(snapshot.model_dump(mode="json"), 200, event)

    except KeyError:
        return error_response(404, "NOT_FOUND", f"Collection not found: {collection_id}", event)
    except ValueError as exc:
        return error_response(409, "CONFLICT", str(exc), event)
    except Exception as exc:
        logger.exception("Failed to promote collection")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# POST /matters/{id}/collections/{cid}/reject
# ------------------------------------------------------------------

def reject_collection(event, context):
    """Reject a collection — mark as rejected without merging."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        collection_id = (event.get("pathParameters") or {}).get("cid", "")
        if not collection_id:
            return error_response(400, "VALIDATION_ERROR", "Missing collection ID", event)

        params = event.get("queryStringParameters") or {}
        headers = event.get("headers") or {}
        org_id = params.get("org_id") or headers.get("x-org-id", "")
        if not org_id:
            return error_response(400, "VALIDATION_ERROR", "Missing org_id query parameter or x-org-id header", event)

        service = _build_collection_service()
        collection = service.reject_collection(collection_id, org_id)

        return success_response(collection.model_dump(mode="json"), 200, event)

    except KeyError:
        return error_response(404, "NOT_FOUND", f"Collection not found: {collection_id}", event)
    except ValueError as exc:
        return error_response(409, "CONFLICT", str(exc), event)
    except Exception as exc:
        logger.exception("Failed to reject collection")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)
