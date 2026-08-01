"""AI Level Summary — Bedrock-generated insight panels for the Pattern Library.

Endpoints:
    GET  /pattern-library/summary/{level}/{context_key} — get or generate summary
    POST /pattern-library/summary/invalidate             — invalidate cached summaries
"""

import json
import logging
import os
import time
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Valid taxonomy levels
VALID_LEVELS = ("domain", "typology", "method", "signature", "precedent_case")

# Bedrock model ID
MODEL_ID = "anthropic.claude-3-haiku-20240307-v1:0"

# S3 location for taxonomy data
S3_BUCKET = os.environ.get("S3_BUCKET", "research-analyst-data-lake-974220725866")
TAXONOMY_S3_KEYS = [
    "pattern-library/pattern-library-taxonomy.json",
    "pattern-library/ancient-mysteries-taxonomy.json",
]

# Module-level rate limiter instance (persists across Lambda invocations via container reuse)
_rate_limiter = None

# Module-level Bedrock client (persists across Lambda invocations via container reuse)
# Configured per design spec: read_timeout=10s (match SLA), connect_timeout=5s,
# max_attempts=1 (no retries — fail fast to stay within 15s uncached p95 budget)
_bedrock_client = None


def _get_rate_limiter():
    """Return the module-level rate limiter singleton."""
    global _rate_limiter
    if _rate_limiter is None:
        from services.summary_rate_limiter import SummaryRateLimiter
        _rate_limiter = SummaryRateLimiter()
    return _rate_limiter


def _get_bedrock_client():
    """Return the module-level Bedrock Runtime client singleton.

    Configured with:
    - read_timeout=10: match 10-second SLA
    - connect_timeout=5: fail fast on connection issues
    - retries max_attempts=1: no retries to stay within 15s uncached p95 budget
    """
    global _bedrock_client
    if _bedrock_client is None:
        import boto3
        from botocore.config import Config

        bedrock_config = Config(
            read_timeout=10,
            connect_timeout=5,
            retries={"max_attempts": 1, "mode": "standard"},
        )
        _bedrock_client = boto3.client("bedrock-runtime", config=bedrock_config)
    return _bedrock_client


def _load_taxonomy_data():
    """Load taxonomy data from S3 (merges multiple taxonomy files).

    Returns the parsed JSON dict with all domains under 'domains' key,
    or None if loading fails.
    """
    import boto3

    try:
        s3 = boto3.client("s3")
        all_domains = []

        for key in TAXONOMY_S3_KEYS:
            try:
                resp = s3.get_object(Bucket=S3_BUCKET, Key=key)
                data = json.loads(resp["Body"].read().decode("utf-8"))

                # Handle multi-domain file (has 'domains' array)
                if "domains" in data:
                    all_domains.extend(data["domains"])
                # Handle single-domain file (top-level domain_id)
                elif "domain_id" in data:
                    all_domains.append(data)
            except Exception as e:
                logger.warning("Failed to load taxonomy key %s: %s", key, str(e)[:200])

        if not all_domains:
            return None

        return {"domains": all_domains}
    except Exception as e:
        logger.error("Failed to load taxonomy from S3: %s", str(e)[:300])
        return None


def _truncate_to_sentences(text: str, max_sentences: int = 5) -> str:
    """Truncate text to at most max_sentences sentences.

    Splits on sentence-ending punctuation (. ! ?) followed by whitespace or end of string.
    Returns only the first max_sentences sentences, preserving original text.
    """
    import re

    # Split on sentence boundaries: period/exclamation/question followed by space or end
    # This regex splits while keeping the delimiter attached to the preceding sentence.
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())

    if len(sentences) <= max_sentences:
        return text.strip()

    return " ".join(sentences[:max_sentences])


def _invoke_bedrock(prompt_payload: dict) -> dict:
    """Invoke Bedrock Claude Haiku with the given prompt payload.

    Returns dict with 'text', 'prompt_tokens', 'completion_tokens' on success.
    Raises Exception on failure or timeout.
    """
    bedrock = _get_bedrock_client()

    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": prompt_payload.get("max_tokens", 300),
        "system": prompt_payload.get("system", ""),
        "messages": prompt_payload.get("messages", []),
        "temperature": 0.3,
    }

    resp = bedrock.invoke_model(
        modelId=MODEL_ID,
        contentType="application/json",
        accept="application/json",
        body=json.dumps(body),
    )

    resp_body = json.loads(resp["body"].read().decode("utf-8"))
    text = resp_body.get("content", [{}])[0].get("text", "")
    usage = resp_body.get("usage", {})

    return {
        "text": text,
        "prompt_tokens": usage.get("input_tokens", 0),
        "completion_tokens": usage.get("output_tokens", 0),
    }


# ------------------------------------------------------------------
# GET /pattern-library/summary/{level}/{context_key}
# ------------------------------------------------------------------


def get_summary_handler(event, context):
    """Handle GET requests for AI level summaries.

    Flow:
    1. Validate path parameters (level, context_key)
    2. Check cache — if fresh hit, return immediately
    3. If cache miss/expired: check rate limiter
       a. Rate limited + stale ≤24h → return stale with is_throttled
       b. Rate limited + no usable cache → 429
       c. Under limit → generate via Bedrock, cache, return
    """
    from db.connection import ConnectionManager
    from lambdas.api.response_helper import CORS_HEADERS, error_response, success_response
    from services.summary_cache_manager import SummaryCacheManager
    from services.summary_prompt_builder import SummaryPromptBuilder

    # Handle OPTIONS preflight
    if event.get("httpMethod") == "OPTIONS":
        return {"statusCode": 200, "headers": CORS_HEADERS, "body": ""}

    # --- 1. Parse and validate path parameters ---
    from urllib.parse import unquote
    path_params = event.get("pathParameters") or {}
    level = path_params.get("level", "")
    context_key = unquote(path_params.get("context_key", ""))

    if level not in VALID_LEVELS:
        return error_response(
            400,
            "INVALID_TAXONOMY_LEVEL",
            f"Invalid taxonomy level '{level}'. Accepted values: {', '.join(VALID_LEVELS)}",
            event,
        )

    if not context_key or len(context_key) > 256:
        return error_response(
            400,
            "INVALID_TAXONOMY_LEVEL",
            "context_key must be a non-empty string of at most 256 characters",
            event,
        )

    # --- 2. Check cache ---
    cm = ConnectionManager()
    cache_manager = SummaryCacheManager(cm)
    cached = cache_manager.get_cached(context_key)

    # Cache hit — fresh (not expired)
    if cached and not cached.is_stale:
        generated_at = cached.generated_at
        if hasattr(generated_at, "isoformat"):
            generated_at = generated_at.isoformat()

        return success_response(
            {
                "summary_text": cached.summary_text,
                "generated_at": generated_at,
                "is_cached": True,
                "is_stale": False,
                "is_throttled": False,
                "taxonomy_level": cached.taxonomy_level,
            },
            200,
            event,
        )

    # --- 3. Cache miss or expired — check rate limiter ---
    rate_limiter = _get_rate_limiter()
    allowed, remaining_or_retry = rate_limiter.check_and_increment()

    if not allowed:
        # Rate limited — check if stale cache is usable (≤24h old)
        if cached:
            generated_at = cached.generated_at
            if hasattr(generated_at, "tzinfo") and generated_at.tzinfo is None:
                generated_at = generated_at.replace(tzinfo=timezone.utc)

            age = datetime.now(timezone.utc) - generated_at
            if age <= timedelta(hours=24):
                gen_at_str = cached.generated_at
                if hasattr(gen_at_str, "isoformat"):
                    gen_at_str = gen_at_str.isoformat()

                return success_response(
                    {
                        "summary_text": cached.summary_text,
                        "generated_at": gen_at_str,
                        "is_cached": True,
                        "is_stale": True,
                        "is_throttled": True,
                        "taxonomy_level": cached.taxonomy_level,
                    },
                    200,
                    event,
                )

        # No usable cache — return 429
        headers = {**CORS_HEADERS, "Retry-After": str(remaining_or_retry)}
        return {
            "statusCode": 429,
            "headers": headers,
            "body": json.dumps(
                {
                    "error": {
                        "code": "RATE_LIMITED",
                        "message": f"Rate limit exceeded. Retry after {remaining_or_retry} seconds.",
                    },
                    "requestId": (event.get("requestContext") or {}).get(
                        "requestId", ""
                    ),
                },
                default=str,
            ),
        }

    # --- 4. Under rate limit — generate summary via Bedrock ---

    # Load taxonomy data
    taxonomy_data = _load_taxonomy_data()
    if not taxonomy_data:
        return error_response(503, "GENERATION_FAILED", "Unable to load taxonomy data", event)

    # Build prompt
    prompt_builder = SummaryPromptBuilder()
    prompt_payload = prompt_builder.build_prompt(level, context_key, taxonomy_data)

    # Check if prompt context is empty (insufficient taxonomy data)
    # The prompt builder returns an empty context string if it can't find the node
    context_portion = prompt_builder._gather_context(level, context_key, taxonomy_data)
    if not context_portion.strip():
        return success_response(
            {
                "summary_text": "Insufficient data to generate summary for this level.",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "is_cached": False,
                "is_stale": False,
                "is_throttled": False,
                "taxonomy_level": level,
            },
            200,
            event,
        )

    # Invoke Bedrock
    t0 = time.time()
    try:
        result = _invoke_bedrock(prompt_payload)
    except Exception as e:
        latency_ms = int((time.time() - t0) * 1000)
        logger.error(
            "Bedrock invocation failed: context_key=%s, latency_ms=%d, error=%s",
            context_key,
            latency_ms,
            str(e)[:300],
        )
        return error_response(
            503,
            "GENERATION_FAILED",
            "Summary generation service is currently unavailable. Please try again later.",
            event,
        )

    latency_ms = int((time.time() - t0) * 1000)

    # Log Bedrock invocation to CloudWatch (Requirement 7.4)
    logger.info(
        "Bedrock invocation: context_key=%s, level=%s, prompt_tokens=%d, "
        "completion_tokens=%d, latency_ms=%d",
        context_key,
        level,
        result["prompt_tokens"],
        result["completion_tokens"],
        latency_ms,
    )

    # Truncate to ≤5 sentences (Requirement 5.7)
    summary_text = _truncate_to_sentences(result["text"])

    # Store in cache (Requirement 2.1, 2.7 — failures logged but don't block response)
    try:
        cache_manager.store_summary(
            context_key=context_key,
            level=level,
            summary_text=summary_text,
            model_id=MODEL_ID,
            prompt_tokens=result["prompt_tokens"],
            completion_tokens=result["completion_tokens"],
        )
    except Exception as e:
        logger.error(
            "Cache write failed (non-blocking): context_key=%s, error=%s",
            context_key,
            str(e)[:300],
        )

    generated_at = datetime.now(timezone.utc).isoformat()

    return success_response(
        {
            "summary_text": summary_text,
            "generated_at": generated_at,
            "is_cached": False,
            "is_stale": False,
            "is_throttled": False,
            "taxonomy_level": level,
        },
        200,
        event,
    )


# ------------------------------------------------------------------
# POST /pattern-library/summary/invalidate
# ------------------------------------------------------------------


def invalidate_handler(event, context):
    """Handle POST requests to invalidate cached summaries.

    Accepts optional context_key in request body:
    - If provided: invalidate entries matching that path prefix
    - If omitted: invalidate all cached summaries

    Returns: {"invalidated_count": N, "requestId": "..."}
    """
    from db.connection import ConnectionManager
    from lambdas.api.response_helper import CORS_HEADERS, error_response, success_response
    from services.summary_cache_manager import SummaryCacheManager

    # Handle OPTIONS preflight
    if event.get("httpMethod") == "OPTIONS":
        return {"statusCode": 200, "headers": CORS_HEADERS, "body": ""}

    # Parse request body
    body = {}
    raw_body = event.get("body", "")
    if raw_body:
        try:
            body = json.loads(raw_body)
        except (json.JSONDecodeError, TypeError):
            return error_response(
                400, "INVALID_REQUEST", "Request body must be valid JSON", event
            )

    context_key = body.get("context_key")

    # Validate context_key if provided
    if context_key is not None:
        if not isinstance(context_key, str) or len(context_key) > 256:
            return error_response(
                400,
                "INVALID_REQUEST",
                "context_key must be a string of at most 256 characters",
                event,
            )

    # Perform invalidation
    cm = ConnectionManager()
    cache_manager = SummaryCacheManager(cm)

    try:
        if context_key:
            invalidated_count = cache_manager.invalidate_by_path(context_key)
        else:
            invalidated_count = cache_manager.invalidate_all()
    except Exception as e:
        logger.error("Invalidation failed: %s", str(e)[:300])
        return error_response(
            500, "INTERNAL_ERROR", "Failed to invalidate summaries", event
        )

    return success_response(
        {"invalidated_count": invalidated_count},
        200,
        event,
    )
