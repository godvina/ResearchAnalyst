"""API Lambda handler for semantic search.

Endpoint:
    POST /case-files/{id}/search — semantic search within a case file

Supports multi-backend search with optional search_mode and filters parameters.
"""

import json
import logging
import os

from services.access_control_middleware import with_access_control

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def _build_search_service():
    """Construct a SemanticSearchService with dependencies from environment."""
    import boto3

    from services.backend_factory import BackendFactory
    from services.aurora_pgvector_backend import AuroraPgvectorBackend
    from services.case_file_service import CaseFileService
    from services.semantic_search_service import SemanticSearchService
    from db.connection import ConnectionManager
    from db.neptune import NeptuneConnectionManager

    # Bedrock Agent Runtime client (for legacy KB search + agent analysis)
    agent_runtime_client = boto3.client("bedrock-agent-runtime")
    kb_id = os.environ.get("KNOWLEDGE_BASE_ID", "")
    agent_id = os.environ.get("BEDROCK_AGENT_ID", "")
    enterprise_kb_id = os.environ.get("ENTERPRISE_KNOWLEDGE_BASE_ID", "")

    # Bedrock Runtime client (for embedding generation)
    bedrock_client = boto3.client("bedrock-runtime")
    embedding_model_id = os.environ.get(
        "BEDROCK_EMBEDDING_MODEL_ID", "amazon.titan-embed-text-v2:0"
    )

    # Aurora connection manager
    aurora_cm = ConnectionManager()
    aurora_backend = AuroraPgvectorBackend(aurora_cm)

    # OpenSearch backend (optional, only if endpoint is configured)
    opensearch_backend = None
    os_endpoint = os.environ.get("OPENSEARCH_ENDPOINT", "")
    if os_endpoint:
        from services.opensearch_serverless_backend import OpenSearchServerlessBackend
        opensearch_backend = OpenSearchServerlessBackend(
            collection_endpoint=os_endpoint,
        )

    backend_factory = BackendFactory(
        aurora_backend=aurora_backend,
        opensearch_backend=opensearch_backend,
    )

    # Case file service
    neptune_cm = NeptuneConnectionManager(
        endpoint=os.environ.get("NEPTUNE_ENDPOINT", ""),
    )
    case_file_service = CaseFileService(aurora_cm, neptune_cm)

    return SemanticSearchService(
        bedrock_agent_runtime_client=agent_runtime_client,
        knowledge_base_id=kb_id,
        agent_id=agent_id,
        backend_factory=backend_factory,
        case_file_service=case_file_service,
        bedrock_client=bedrock_client,
        embedding_model_id=embedding_model_id,
        enterprise_knowledge_base_id=enterprise_kb_id,
    )


def _build_case_file_service():
    """Construct a CaseFileService for reading case file metadata."""
    from db.connection import ConnectionManager
    from db.neptune import NeptuneConnectionManager
    from services.case_file_service import CaseFileService

    aurora_cm = ConnectionManager()
    neptune_cm = NeptuneConnectionManager(
        endpoint=os.environ.get("NEPTUNE_ENDPOINT", ""),
    )
    return CaseFileService(aurora_cm, neptune_cm)


def _build_backend_factory():
    """Construct a BackendFactory for resolving backends."""
    from services.backend_factory import BackendFactory
    from services.aurora_pgvector_backend import AuroraPgvectorBackend
    from db.connection import ConnectionManager

    aurora_cm = ConnectionManager()
    aurora_backend = AuroraPgvectorBackend(aurora_cm)

    opensearch_backend = None
    os_endpoint = os.environ.get("OPENSEARCH_ENDPOINT", "")
    if os_endpoint:
        from services.opensearch_serverless_backend import OpenSearchServerlessBackend
        opensearch_backend = OpenSearchServerlessBackend(
            collection_endpoint=os_endpoint,
        )

    return BackendFactory(
        aurora_backend=aurora_backend,
        opensearch_backend=opensearch_backend,
    )


# ------------------------------------------------------------------
# POST /case-files/{id}/search
# ------------------------------------------------------------------

@with_access_control
def search_handler(event, context):
    """Perform search within a case file.

    Supports optional search_mode (semantic|keyword|hybrid) and filters.
    Returns search_tier and available_modes in the response.
    """
    from lambdas.api.response_helper import CORS_HEADERS, error_response, success_response
    from models.search import FacetedFilter

    if event.get("httpMethod") == "OPTIONS":
        return {"statusCode": 200, "headers": CORS_HEADERS, "body": ""}

    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        if not case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case file ID", event)

        body = (json.loads(event.get("body")) if isinstance(event.get("body"), str) else (event.get("body") or {}))
        query = body.get("query", "")

        if not query:
            return error_response(400, "VALIDATION_ERROR", "Missing 'query' in request body", event)

        mode = body.get("search_mode", "semantic")
        top_k = body.get("top_k", 10)
        filters_raw = body.get("filters")

        # Construct FacetedFilter from raw payload
        filters = None
        if filters_raw:
            filters = FacetedFilter(**filters_raw)

        # Load case file to get tier info for response
        case_file_service = _build_case_file_service()
        case_file = case_file_service.get_case_file(case_id)

        backend_factory = _build_backend_factory()
        backend = backend_factory.get_backend(case_file.search_tier)

        # Perform search
        service = _build_search_service()
        try:
            results = service.search(
                case_id=case_id, query=query, mode=mode,
                filters=filters, top_k=top_k,
            )
        except ValueError as exc:
            # Unsupported mode or filter for the tier
            return error_response(400, "UNSUPPORTED_MODE", str(exc), event)

        # Post-filter search results through access control
        result_dicts = [r.model_dump(mode="json") for r in results]
        user_ctx_dict = event.get("_user_context")
        if user_ctx_dict:
            from models.access_control import UserContext
            from services.access_control_service import AccessControlService
            user_ctx = UserContext(**user_ctx_dict)
            ac_service = AccessControlService()
            result_dicts = ac_service.filter_documents(user_ctx, result_dicts)

        return success_response(
            {
                "results": result_dicts,
                "search_tier": case_file.search_tier.value if hasattr(case_file.search_tier, 'value') else case_file.search_tier,
                "available_modes": backend.supported_modes,
            },
            200, event,
        )

    except KeyError:
        return error_response(404, "NOT_FOUND", f"Case file not found: {case_id}", event)
    except Exception as exc:
        logger.exception("Failed to perform search")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)
