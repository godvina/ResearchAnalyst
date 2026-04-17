"""OSINT Research Agent — API handler.

POST /case-files/{id}/osint-research  — trigger OSINT research
GET  /case-files/{id}/osint-research/cache — list cached results
"""

import json
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


def _build_osint_service():
    """Construct OsintResearchService with dependencies."""
    from db.connection import ConnectionManager
    from services.osint_research_service import OsintResearchService
    import boto3
    from botocore.config import Config

    aurora_cm = ConnectionManager()
    bedrock_config = Config(
        read_timeout=20, connect_timeout=3,
        retries={"max_attempts": 1, "mode": "standard"},
    )
    bedrock = boto3.client("bedrock-runtime", config=bedrock_config)
    neptune_ep = os.environ.get("NEPTUNE_ENDPOINT", "")
    brave_key = os.environ.get("BRAVE_SEARCH_API_KEY", "")

    return OsintResearchService(
        aurora_cm=aurora_cm,
        bedrock_client=bedrock,
        neptune_endpoint=neptune_ep,
        brave_api_key=brave_key or None,
    )


def research_handler(event, context):
    """POST /case-files/{id}/osint-research"""
    from lambdas.api.response_helper import CORS_HEADERS, error_response, success_response

    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        if not case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case ID", event)

        body = (json.loads(event.get("body")) if isinstance(event.get("body"), str) else (event.get("body") or {}))
        research_type = body.get("research_type", "")
        ctx = body.get("context", {})
        force_refresh = body.get("force_refresh", False)

        if not research_type:
            return error_response(400, "VALIDATION_ERROR", "Missing research_type field", event)
        if research_type not in ("entity", "pattern", "question"):
            return error_response(400, "VALIDATION_ERROR",
                                  f"Invalid research_type: {research_type}. Must be entity, pattern, or question.", event)
        if not ctx:
            return error_response(400, "VALIDATION_ERROR", "Missing context field", event)

        service = _build_osint_service()
        result = service.research(case_id, research_type, ctx, force_refresh=bool(force_refresh))
        return success_response(result, 200, event)

    except Exception as exc:
        logger.exception("OSINT research handler failed")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


def list_cache_handler(event, context):
    """GET /case-files/{id}/osint-research/cache"""
    from lambdas.api.response_helper import error_response, success_response

    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        if not case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case ID", event)

        params = event.get("queryStringParameters") or {}
        limit = int(params.get("limit", 50))

        service = _build_osint_service()
        results = service.get_cached_results(case_id, limit=limit)
        return success_response({"results": results, "total": len(results)}, 200, event)

    except Exception as exc:
        logger.exception("OSINT cache list failed")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)
