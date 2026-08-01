"""Concept Research API — Phase 1 auto-research for Pattern Library concepts.

Endpoints:
    GET  /pattern-library/concept-research/{level}/{context_key}  — get or trigger concept research
    POST /pattern-library/concept-research/refresh               — force re-research a concept
"""

import json
import logging
import os
import time
from datetime import datetime, timezone

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Rate limiter singleton (shared with other research endpoints)
_rate_limiter = None


def _get_rate_limiter():
    """Return the shared rate limiter singleton."""
    global _rate_limiter
    if _rate_limiter is None:
        from services.summary_rate_limiter import SummaryRateLimiter
        _rate_limiter = SummaryRateLimiter()
    return _rate_limiter


def _extract_concept_info(level: str, context_key: str) -> dict:
    """Extract concept name and description from taxonomy for the given context_key.

    Loads taxonomy from S3 and navigates to the correct node to get
    a meaningful name and description for the concept research agent.
    """
    import boto3

    S3_BUCKET = os.environ.get("S3_BUCKET", "research-analyst-data-lake-974220725866")
    TAXONOMY_S3_KEYS = [
        "pattern-library/pattern-library-taxonomy.json",
        "pattern-library/ancient-mysteries-taxonomy.json",
    ]

    try:
        s3 = boto3.client("s3")
        all_domains = []

        for key in TAXONOMY_S3_KEYS:
            try:
                resp = s3.get_object(Bucket=S3_BUCKET, Key=key)
                data = json.loads(resp["Body"].read().decode("utf-8"))
                if "domains" in data:
                    all_domains.extend(data["domains"])
                elif "domain_id" in data:
                    all_domains.append(data)
            except Exception:
                continue

        if not all_domains:
            return {"name": context_key, "description": ""}

        parts = context_key.split("/")
        taxonomy_data = {"domains": all_domains}

        # Navigate to the correct node based on level
        if level == "domain" and len(parts) >= 1:
            for d in all_domains:
                if d.get("domain_id") == parts[0]:
                    return {
                        "name": d.get("name", parts[0]),
                        "description": d.get("description", ""),
                        "taxonomy_context": json.dumps(d, default=str)[:2000],
                    }

        elif level == "typology" and len(parts) >= 2:
            for d in all_domains:
                if d.get("domain_id") == parts[0]:
                    for t in d.get("typologies", []):
                        if t.get("typology_id") == parts[1]:
                            return {
                                "name": t.get("name", parts[1]),
                                "description": t.get("description", ""),
                                "taxonomy_context": json.dumps(t, default=str)[:2000],
                            }

        elif level == "method" and len(parts) >= 3:
            for d in all_domains:
                if d.get("domain_id") == parts[0]:
                    for t in d.get("typologies", []):
                        if t.get("typology_id") == parts[1]:
                            for m in t.get("methods", []):
                                if m.get("method_id") == parts[2]:
                                    return {
                                        "name": m.get("name", parts[2]),
                                        "description": m.get("description", ""),
                                        "taxonomy_context": json.dumps(m, default=str)[:2000],
                                    }

        elif level == "signature" and len(parts) >= 4:
            for d in all_domains:
                if d.get("domain_id") == parts[0]:
                    for t in d.get("typologies", []):
                        if t.get("typology_id") == parts[1]:
                            for m in t.get("methods", []):
                                if m.get("method_id") == parts[2]:
                                    for s in m.get("signatures", []):
                                        if s.get("signature_id") == parts[3]:
                                            return {
                                                "name": s.get("description", parts[3])[:100],
                                                "description": s.get("vector_text", ""),
                                                "taxonomy_context": json.dumps(s, default=str)[:2000],
                                            }

        # Fallback: use the context_key as the concept name
        return {"name": context_key.replace("/", " > "), "description": ""}

    except Exception as e:
        logger.warning("Failed to extract concept info: %s", str(e)[:200])
        return {"name": context_key.replace("/", " > "), "description": ""}


# ------------------------------------------------------------------
# GET /pattern-library/concept-research/{level}/{context_key}
# ------------------------------------------------------------------


def get_concept_research_handler(event, context):
    """Handle GET requests for concept research.

    Flow:
    1. Extract concept info from taxonomy
    2. Check if cached concept briefing exists (return immediately if fresh)
    3. If no cache: check rate limiter, execute concept research, cache, return
    """
    from lambdas.api.response_helper import CORS_HEADERS, error_response, success_response

    # Handle OPTIONS preflight
    if event.get("httpMethod") == "OPTIONS":
        return {"statusCode": 200, "headers": CORS_HEADERS, "body": ""}

    # --- 1. Parse and validate path parameters ---
    from urllib.parse import unquote

    VALID_LEVELS = ("domain", "typology", "method", "signature", "precedent_case")

    path_params = event.get("pathParameters") or {}
    level = path_params.get("level", "")
    context_key = unquote(path_params.get("context_key", ""))

    if level not in VALID_LEVELS:
        return error_response(
            400,
            "INVALID_TAXONOMY_LEVEL",
            f"Invalid taxonomy level '{level}'. Accepted: {', '.join(VALID_LEVELS)}",
            event,
        )

    if not context_key or len(context_key) > 256:
        return error_response(
            400,
            "INVALID_CONTEXT_KEY",
            "context_key must be non-empty and at most 256 characters",
            event,
        )

    # --- 2. Extract concept info from taxonomy ---
    concept_info = _extract_concept_info(level, context_key)
    concept_name = concept_info.get("name", context_key)
    concept_description = concept_info.get("description", "")
    taxonomy_context = concept_info.get("taxonomy_context", "")

    # --- 3. Run concept research agent ---
    from services.concept_research_agent import ConceptResearchAgent

    agent = ConceptResearchAgent()

    # Check cache first (agent handles this internally)
    # But we also need to check rate limiter before allowing generation
    bypass_cache = event.get("queryStringParameters", {}) or {}
    bypass = bypass_cache.get("refresh", "false").lower() == "true"

    if not bypass:
        # Try cache first without rate limiting
        cached = agent._get_cached_briefing(agent._make_cache_key(concept_name))
        if cached:
            cached["_from_cache"] = True
            return success_response(
                {
                    "concept_name": concept_name,
                    "briefing": cached,
                    "is_cached": True,
                    "taxonomy_level": level,
                    "context_key": context_key,
                },
                200,
                event,
            )

    # No cache — check rate limiter (concept research uses 2 Bedrock calls)
    rate_limiter = _get_rate_limiter()
    allowed, remaining_or_retry = rate_limiter.check_and_increment()
    if not allowed:
        headers = {**CORS_HEADERS, "Retry-After": str(remaining_or_retry)}
        return {
            "statusCode": 429,
            "headers": headers,
            "body": json.dumps({
                "error": {
                    "code": "RATE_LIMITED",
                    "message": f"Rate limit exceeded. Retry after {remaining_or_retry}s.",
                },
                "requestId": (event.get("requestContext") or {}).get("requestId", ""),
            }),
        }

    # Also consume a second slot (concept research makes 2 Bedrock calls: query gen + synthesis)
    rate_limiter.check_and_increment()

    # Execute full concept research
    t0 = time.time()
    try:
        briefing = agent.research_concept(
            concept_name=concept_name,
            concept_description=concept_description,
            taxonomy_context=taxonomy_context,
            bypass_cache=True,  # We already checked cache above
        )
    except Exception as e:
        latency_ms = int((time.time() - t0) * 1000)
        logger.error(
            "Concept research failed: concept='%s', latency_ms=%d, error=%s",
            concept_name, latency_ms, str(e)[:300],
        )
        return error_response(
            503,
            "RESEARCH_FAILED",
            "Concept research service is currently unavailable. Please try again later.",
            event,
        )

    latency_ms = int((time.time() - t0) * 1000)
    logger.info(
        "Concept research complete: concept='%s', targets=%d, latency_ms=%d",
        concept_name, len(briefing.get("priority_targets", [])), latency_ms,
    )

    return success_response(
        {
            "concept_name": concept_name,
            "briefing": briefing,
            "is_cached": False,
            "taxonomy_level": level,
            "context_key": context_key,
        },
        200,
        event,
    )


# ------------------------------------------------------------------
# POST /pattern-library/concept-research/refresh
# ------------------------------------------------------------------


def refresh_concept_research_handler(event, context):
    """Handle POST to force re-research a concept (bypasses cache).

    Body: {"level": "typology", "context_key": "ancient_mysteries/ley_lines"}
    """
    from lambdas.api.response_helper import CORS_HEADERS, error_response, success_response

    # Handle OPTIONS preflight
    if event.get("httpMethod") == "OPTIONS":
        return {"statusCode": 200, "headers": CORS_HEADERS, "body": ""}

    # Parse request body
    raw_body = event.get("body", "")
    if not raw_body:
        return error_response(400, "INVALID_REQUEST", "Request body is required", event)

    try:
        body = json.loads(raw_body)
    except (json.JSONDecodeError, TypeError):
        return error_response(400, "INVALID_REQUEST", "Body must be valid JSON", event)

    level = body.get("level", "").strip()
    context_key = body.get("context_key", "").strip()

    if not level or not context_key:
        return error_response(400, "INVALID_REQUEST", "level and context_key are required", event)

    # Inject into a synthetic event and call the GET handler with bypass
    synthetic_event = {
        "httpMethod": "GET",
        "pathParameters": {"level": level, "context_key": context_key},
        "queryStringParameters": {"refresh": "true"},
        "requestContext": event.get("requestContext", {}),
    }

    return get_concept_research_handler(synthetic_event, context)


# ------------------------------------------------------------------
# GET /pattern-library/concept-research/evidence-map/{domain_prefix}
# ------------------------------------------------------------------


def get_evidence_map_handler(event, context):
    """Return evidence scores for all nodes under a domain prefix.

    Used by the frontend to color-code map dots based on accumulated research.
    Red = unexplored, Yellow = inconclusive, Blue = probable, Green = confirmed.
    """
    from lambdas.api.response_helper import CORS_HEADERS, error_response, success_response

    # Handle OPTIONS preflight
    if event.get("httpMethod") == "OPTIONS":
        return {"statusCode": 200, "headers": CORS_HEADERS, "body": ""}

    from urllib.parse import unquote

    path_params = event.get("pathParameters") or {}
    domain_prefix = unquote(path_params.get("domain_prefix", ""))

    if not domain_prefix:
        return error_response(400, "INVALID_REQUEST", "domain_prefix is required", event)

    try:
        from services.research_findings_store import ResearchFindingsStore
        store = ResearchFindingsStore()
        evidence_map = store.get_evidence_map(domain_prefix)

        return success_response(
            {
                "domain_prefix": domain_prefix,
                "evidence_map": evidence_map,
                "node_count": len(evidence_map),
            },
            200,
            event,
        )
    except Exception as e:
        logger.error("Evidence map failed: %s", str(e)[:300])
        return error_response(503, "SERVICE_ERROR", "Could not load evidence map", event)
