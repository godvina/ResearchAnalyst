"""AI Level Research — Bedrock-generated research recommendations + Brave Search execution.

Endpoints:
    GET  /pattern-library/research/{level}/{context_key} — get research recommendations
    POST /pattern-library/research/execute               — execute a Brave search + synthesize
"""

import json
import logging
import os
import re
import time
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Valid taxonomy levels
VALID_LEVELS = ("domain", "typology", "method", "signature", "precedent_case")

# Bedrock model ID — Use Sonnet 4 for research synthesis (fast enough for 29s API Gateway timeout)
MODEL_ID = os.environ.get("RESEARCH_MODEL_ID", "us.anthropic.claude-sonnet-4-6")

# S3 location for taxonomy data
S3_BUCKET = os.environ.get("S3_BUCKET", "research-analyst-data-lake-974220725866")
TAXONOMY_S3_KEYS = [
    "pattern-library/pattern-library-taxonomy.json",
    "pattern-library/ancient-mysteries-taxonomy.json",
]

# Cache key prefix for research recommendations
RESEARCH_PREFIX = "research:"

# Brave Search API key
BRAVE_API_KEY = os.environ.get("BRAVE_API_KEY", os.environ.get("BRAVE_SEARCH_API_KEY", ""))

# Module-level singletons
_rate_limiter = None
_bedrock_client = None

# System prompts
RECOMMENDATIONS_SYSTEM_PROMPT = (
    "You are an investigative intelligence research analyst. Given a taxonomy pattern "
    "and its geographic context, identify 2-4 specific research hypotheses that would "
    "deepen understanding of this pattern. For each hypothesis, provide a concrete web "
    "search query that could test it.\n\n"
    "Focus on:\n"
    "1. Geographic gaps - places where the pattern predicts something should exist but "
    "hasn't been documented\n"
    "2. Dating evidence - sources that could confirm or challenge timeline assumptions\n"
    "3. Cross-pattern connections - links to other domains or typologies\n"
    "4. Primary sources - specific academic papers, surveys, or databases to consult\n\n"
    "Return ONLY a JSON object with keys:\n"
    "- recommendations: array of {id, title, description, search_query, significance "
    "(high/medium/low), category}\n"
    "- summary: one-paragraph overview of the research landscape\n\n"
    "No markdown, no preamble — just the JSON object."
)

SEARCH_SYNTHESIS_SYSTEM_PROMPT = (
    "You are a senior investigative researcher for a documentary production team. "
    "You analyze search results through the lens of the INVESTIGATION CONTEXT provided.\n\n"
    "CRITICAL: Read the 'Context' field carefully. It tells you WHAT QUESTION to answer.\n"
    "- If context mentions 'LEY LINE INVESTIGATION' — focus on: what other sites exist along this alignment? "
    "What's at intersection points? What undiscovered locations exist between known sites? "
    "Do NOT just describe the known sites. Find what's BETWEEN them and what's UNDISCOVERED.\n"
    "- If context mentions a specific location — investigate what's physically there and what evidence exists.\n\n"
    "Return ONLY a JSON object with:\n"
    "- codename: short dramatic name for this investigation\n"
    "- situation: 2-3 sentences answering the core research question from context\n"
    "- evidence_found: array of 3-5 objects with {source_type, finding, confidence: 'confirmed'/'probable'/'unverified', detail}. "
    "Source types: 'satellite', 'academic', 'geological', 'historical', 'archaeological'\n"
    "- smoking_gun: the single most compelling discovery (or 'No definitive evidence found')\n"
    "- investigation_status: 'CONFIRMED', 'PROBABLE', 'INCONCLUSIVE', or 'NEGATIVE'\n"
    "- undiscovered_sites: array of {location, coordinates_approx, rationale, what_to_look_for} — "
    "places that SHOULD be investigated based on the alignment pattern but haven't been surveyed\n"
    "- intersection_points: array of {description, significance} — where this alignment crosses other known alignments\n"
    "- field_recommendation: concrete next step for a field team\n"
    "- production_value: visual/documentary potential\n"
    "- sources_consulted: array of {name, url, reliability: 'primary'/'secondary'/'tertiary'}\n\n"
    "RULES: Be specific. Name coordinates, researchers, papers. "
    "If investigating an alignment, the VALUE is in finding what's UNKNOWN, not describing what's already documented. "
    "No markdown — just JSON."
)


def _get_rate_limiter():
    """Return the module-level rate limiter singleton."""
    global _rate_limiter
    if _rate_limiter is None:
        from services.summary_rate_limiter import SummaryRateLimiter
        _rate_limiter = SummaryRateLimiter()
    return _rate_limiter


def _get_bedrock_client():
    """Return the module-level Bedrock Runtime client singleton."""
    global _bedrock_client
    if _bedrock_client is None:
        import boto3
        from botocore.config import Config

        bedrock_config = Config(
            read_timeout=60,     # Sonnet needs more time than Haiku
            connect_timeout=10,
            retries={"max_attempts": 2, "mode": "adaptive"},
        )
        _bedrock_client = boto3.client("bedrock-runtime", config=bedrock_config)
    return _bedrock_client


def _load_taxonomy_data():
    """Load taxonomy data from S3 (merges multiple taxonomy files)."""
    import boto3

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
            except Exception as e:
                logger.warning("Failed to load taxonomy key %s: %s", key, str(e)[:200])

        if not all_domains:
            return None

        return {"domains": all_domains}
    except Exception as e:
        logger.error("Failed to load taxonomy from S3: %s", str(e)[:300])
        return None


def _invoke_bedrock(system_prompt: str, user_message: str, max_tokens: int = 800) -> dict:
    """Invoke Bedrock Claude Haiku with system + user message.

    Returns dict with 'text', 'prompt_tokens', 'completion_tokens' on success.
    Raises Exception on failure.
    """
    bedrock = _get_bedrock_client()

    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_message}],
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


def _parse_json_response(raw_text: str) -> dict:
    """Parse a JSON object from Bedrock's response, stripping markdown fences."""
    if not raw_text or not raw_text.strip():
        return {}

    text = raw_text.strip()

    # Strip markdown code fences if present
    fence_pattern = re.compile(r"```(?:json)?\s*\n?(.*?)\n?\s*```", re.DOTALL)
    fence_match = fence_pattern.search(text)
    if fence_match:
        text = fence_match.group(1).strip()

    # Find the first { and matching }
    brace_idx = text.find("{")
    if brace_idx == -1:
        return {}

    text = text[brace_idx:]
    brace_count = 0
    end_idx = -1
    for i, ch in enumerate(text):
        if ch == "{":
            brace_count += 1
        elif ch == "}":
            brace_count -= 1
            if brace_count == 0:
                end_idx = i
                break

    if end_idx == -1:
        return {}

    try:
        return json.loads(text[: end_idx + 1])
    except (json.JSONDecodeError, TypeError):
        return {}


def _gather_context(level: str, context_key: str, taxonomy_data: dict) -> str:
    """Gather taxonomy context for the given level and context_key.

    Reuses the same navigation logic as CoordinatePromptBuilder.
    """
    from services.coordinate_prompt_builder import CoordinatePromptBuilder
    builder = CoordinatePromptBuilder()
    return builder._gather_context(level, context_key, taxonomy_data)


def _search_brave(query: str, count: int = 5) -> list:
    """Search Brave and return top results."""
    import urllib.request
    import urllib.parse

    if not BRAVE_API_KEY:
        logger.warning("BRAVE_API_KEY not configured")
        return []

    params = urllib.parse.urlencode({"q": query, "count": count})
    url = f"https://api.search.brave.com/res/v1/web/search?{params}"
    req = urllib.request.Request(url)
    req.add_header("X-Subscription-Token", BRAVE_API_KEY)
    req.add_header("Accept", "application/json")

    try:
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read().decode())

        results = []
        for item in data.get("web", {}).get("results", [])[:count]:
            results.append({
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "snippet": item.get("description", "")[:300]
            })
        return results
    except Exception as e:
        logger.error("Brave Search failed: %s", str(e)[:300])
        return []


# ------------------------------------------------------------------
# GET /pattern-library/research/{level}/{context_key}
# ------------------------------------------------------------------


def get_recommendations_handler(event, context):
    """Handle GET requests for AI-generated research recommendations.

    Flow:
    1. Validate path parameters (level, context_key)
    2. Check cache (with research: prefix)
    3. If cache miss/expired: check rate limiter, generate via Bedrock, cache, return
    """
    from db.connection import ConnectionManager
    from lambdas.api.response_helper import CORS_HEADERS, error_response, success_response
    from services.summary_cache_manager import SummaryCacheManager

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
            "INVALID_CONTEXT_KEY",
            "context_key must be a non-empty string of at most 256 characters",
            event,
        )

    # --- 2. Check cache (with research: prefix) ---
    cache_key = f"{RESEARCH_PREFIX}{context_key}"
    cm = ConnectionManager()
    cache_manager = SummaryCacheManager(cm)
    cached = cache_manager.get_cached(cache_key)

    # Cache hit — fresh
    if cached and not cached.is_stale:
        generated_at = cached.generated_at
        if hasattr(generated_at, "isoformat"):
            generated_at = generated_at.isoformat()

        try:
            cached_data = json.loads(cached.summary_text)
        except (json.JSONDecodeError, TypeError):
            cached_data = {}

        return success_response(
            {
                "recommendations": cached_data.get("recommendations", []),
                "summary": cached_data.get("summary", ""),
                "generated_at": generated_at,
                "is_cached": True,
                "taxonomy_level": cached.taxonomy_level,
            },
            200,
            event,
        )

    # --- 3. Cache miss or expired — check rate limiter ---
    rate_limiter = _get_rate_limiter()
    allowed, remaining_or_retry = rate_limiter.check_and_increment()

    if not allowed:
        # Rate limited — check stale cache
        if cached:
            generated_at = cached.generated_at
            if hasattr(generated_at, "tzinfo") and generated_at.tzinfo is None:
                generated_at = generated_at.replace(tzinfo=timezone.utc)

            age = datetime.now(timezone.utc) - generated_at
            if age <= timedelta(hours=24):
                gen_at_str = cached.generated_at
                if hasattr(gen_at_str, "isoformat"):
                    gen_at_str = gen_at_str.isoformat()

                try:
                    cached_data = json.loads(cached.summary_text)
                except (json.JSONDecodeError, TypeError):
                    cached_data = {}

                return success_response(
                    {
                        "recommendations": cached_data.get("recommendations", []),
                        "summary": cached_data.get("summary", ""),
                        "generated_at": gen_at_str,
                        "is_cached": True,
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
                    "requestId": (event.get("requestContext") or {}).get("requestId", ""),
                },
                default=str,
            ),
        }

    # --- 4. Generate recommendations via Bedrock ---
    taxonomy_data = _load_taxonomy_data()
    if not taxonomy_data:
        return error_response(503, "GENERATION_FAILED", "Unable to load taxonomy data", event)

    # Gather context
    taxonomy_context = _gather_context(level, context_key, taxonomy_data)
    if not taxonomy_context.strip():
        return success_response(
            {
                "recommendations": [],
                "summary": "",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "is_cached": False,
                "taxonomy_level": level,
            },
            200,
            event,
        )

    user_message = (
        f"Analyze the following taxonomy pattern at the '{level}' level and generate "
        f"research recommendations:\n\n{taxonomy_context}"
    )

    t0 = time.time()
    try:
        result = _invoke_bedrock(RECOMMENDATIONS_SYSTEM_PROMPT, user_message, max_tokens=1000)
    except Exception as e:
        latency_ms = int((time.time() - t0) * 1000)
        logger.error(
            "Bedrock research invocation failed: context_key=%s, latency_ms=%d, error=%s",
            context_key, latency_ms, str(e)[:300],
        )
        return error_response(
            503,
            "GENERATION_FAILED",
            "Research recommendation service is currently unavailable. Please try again later.",
            event,
        )

    latency_ms = int((time.time() - t0) * 1000)
    logger.info(
        "Bedrock research invocation: context_key=%s, level=%s, prompt_tokens=%d, "
        "completion_tokens=%d, latency_ms=%d",
        context_key, level, result["prompt_tokens"], result["completion_tokens"], latency_ms,
    )

    # Parse response
    parsed = _parse_json_response(result["text"])
    recommendations = parsed.get("recommendations", [])
    summary = parsed.get("summary", "")

    # Assign IDs if missing
    for i, rec in enumerate(recommendations):
        if not rec.get("id"):
            rec["id"] = f"rec_{i + 1}"

    generated_at = datetime.now(timezone.utc).isoformat()

    # Cache the result
    cache_data = {"recommendations": recommendations, "summary": summary}
    try:
        cache_manager.store_summary(
            context_key=cache_key,
            level=level,
            summary_text=json.dumps(cache_data),
            model_id=MODEL_ID,
            prompt_tokens=result["prompt_tokens"],
            completion_tokens=result["completion_tokens"],
        )
    except Exception as e:
        logger.error(
            "Research cache write failed (non-blocking): context_key=%s, error=%s",
            cache_key, str(e)[:300],
        )

    return success_response(
        {
            "recommendations": recommendations,
            "summary": summary,
            "generated_at": generated_at,
            "is_cached": False,
            "taxonomy_level": level,
        },
        200,
        event,
    )


# ------------------------------------------------------------------
# POST /pattern-library/research/execute
# ------------------------------------------------------------------


def execute_search_handler(event, context):
    """Handle POST requests to execute a Brave search and synthesize results.

    Accepts JSON body: {"query": "...", "context": "..."}
    Returns: {"brief": {...}, "requestId": "..."}
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
        return error_response(400, "INVALID_REQUEST", "Request body must be valid JSON", event)

    query = body.get("query", "").strip()
    search_context = body.get("context", "").strip()

    if not query:
        return error_response(400, "INVALID_REQUEST", "query field is required", event)

    if len(query) > 500:
        return error_response(400, "INVALID_REQUEST", "query must be 500 characters or less", event)

    # Check rate limiter (shared with recommendations)
    rate_limiter = _get_rate_limiter()
    allowed, remaining_or_retry = rate_limiter.check_and_increment()

    if not allowed:
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
                    "requestId": (event.get("requestContext") or {}).get("requestId", ""),
                },
                default=str,
            ),
        }

    # Execute MULTI-QUERY research chain (Bellingcat methodology)
    # Phase 2: Pull concept research context to inform site investigation
    concept_context = ""
    try:
        from services.concept_research_agent import ConceptResearchAgent
        agent = ConceptResearchAgent()
        # Try to find cached concept briefing for the search context
        if search_context:
            cached_briefing = agent._get_cached_briefing(agent._make_cache_key(search_context))
            if cached_briefing:
                # Extract priority targets and evidence landscape for richer OSINT
                priorities = cached_briefing.get("priority_targets", [])
                evidence = cached_briefing.get("evidence_landscape", {})
                researchers = cached_briefing.get("key_researchers", [])
                concept_context = (
                    f"\n\nCONCEPT RESEARCH CONTEXT (from Phase 1 briefing):\n"
                    f"Field Status: {cached_briefing.get('field_status', 'Unknown')}\n"
                    f"Executive Summary: {cached_briefing.get('executive_summary', '')}\n"
                    f"Key Researchers: {', '.join(r.get('name', '') for r in researchers[:5])}\n"
                    f"Confirmed Evidence: {'; '.join(evidence.get('confirmed', [])[:3])}\n"
                    f"Contested Claims: {'; '.join(evidence.get('contested', [])[:3])}\n"
                    f"Priority Targets: {'; '.join(t.get('location', '') for t in priorities[:5])}\n"
                )
    except Exception as e:
        logger.debug("No concept context available (non-blocking): %s", str(e)[:100])

    # Instead of one search, execute 3 different research angles
    all_results = []
    
    # Angle 1: Primary query (user's original question)
    results_1 = _search_brave(query, count=3)
    all_results.extend(results_1)
    
    # Angle 2: Archaeological/academic angle
    academic_query = query.replace("ancient site", "archaeological survey excavation") + " research paper findings"
    if len(academic_query) <= 400:
        results_2 = _search_brave(academic_query[:200], count=3)
        all_results.extend(results_2)
    
    # Angle 3: Geological/anomaly angle  
    geo_query = query.replace("ancient site archaeological ruins", "geological anomaly geomagnetic survey") + " unusual formation"
    if len(geo_query) <= 400:
        results_3 = _search_brave(geo_query[:200], count=2)
        all_results.extend(results_3)
    
    # Deduplicate by URL
    seen_urls = set()
    search_results = []
    for r in all_results:
        if r['url'] not in seen_urls:
            seen_urls.add(r['url'])
            search_results.append(r)

    # Build synthesis prompt with multi-source results + concept context
    if search_results:
        results_text = "\n\n".join(
            f"[{i+1}] {r['title']}\nURL: {r['url']}\nSnippet: {r['snippet']}"
            for i, r in enumerate(search_results)
        )
        user_message = (
            f"INVESTIGATION BRIEF REQUEST\n"
            f"Target query: {query}\n"
            f"Context: {search_context}\n"
            f"Research methodology: Multi-angle OSINT (primary query + academic sources + geological data)\n"
            f"Total sources consulted: {len(search_results)}\n"
            f"{concept_context}\n\n"
            f"RAW INTELLIGENCE (search results from 3 research angles):\n{results_text}\n\n"
            f"Produce your OSINT field intelligence report based on these findings."
        )
    else:
        user_message = (
            f"INVESTIGATION BRIEF REQUEST\n"
            f"Target query: {query}\n"
            f"Context: {search_context}\n\n"
            "Note: Web search was unavailable. Provide your best analysis based on "
            "your training data. Mark investigation_status as 'INCONCLUSIVE' and "
            "note that sources could not be verified via live search."
        )

    # Synthesize with Bedrock
    t0 = time.time()
    try:
        result = _invoke_bedrock(SEARCH_SYNTHESIS_SYSTEM_PROMPT, user_message, max_tokens=2000)
    except Exception as e:
        latency_ms = int((time.time() - t0) * 1000)
        logger.error(
            "Bedrock search synthesis failed: query=%s, latency_ms=%d, error=%s",
            query[:80], latency_ms, str(e)[:300],
        )
        return error_response(
            503,
            "SYNTHESIS_FAILED",
            "Search synthesis service is currently unavailable. Please try again later.",
            event,
        )

    latency_ms = int((time.time() - t0) * 1000)
    logger.info(
        "Bedrock search synthesis: query=%s, results_count=%d, latency_ms=%d",
        query[:80], len(search_results), latency_ms,
    )

    # Parse synthesis response
    brief = _parse_json_response(result["text"])

    # Attach sources from Brave results
    if search_results and "sources" not in brief:
        brief["sources"] = search_results

    # Ensure required fields (new OSINT report format)
    brief.setdefault("codename", "SITE UNKNOWN")
    brief.setdefault("situation", brief.get("summary", "Investigation pending."))
    brief.setdefault("evidence_found", [])
    brief.setdefault("threat_to_theory", "inconclusive")
    brief.setdefault("smoking_gun", "No definitive evidence found at this location")
    brief.setdefault("investigation_status", "INCONCLUSIVE - Requires field visit")
    brief.setdefault("field_recommendation", "Conduct ground survey at coordinates")
    brief.setdefault("production_value", "Assessment pending field visit")
    brief.setdefault("sources_consulted", [])
    brief.setdefault("suggested_next_steps", [brief.get("field_recommendation", "")])
    # Backward compat
    brief.setdefault("summary", brief.get("situation", "Investigation pending."))
    brief.setdefault("key_findings", [e.get("finding", "") for e in brief.get("evidence_found", [])])
    brief.setdefault("confidence", "medium" if search_results else "low")
    if not brief.get("sources"):
        brief["sources"] = search_results or []

    # Store research brief in Aurora for persistence
    try:
        from db.connection import ConnectionManager
        from services.summary_cache_manager import SummaryCacheManager
        
        cm = ConnectionManager()
        cache_manager = SummaryCacheManager(cm)
        
        # Use a unique cache key based on the query
        import hashlib
        query_hash = hashlib.md5(query.encode()).hexdigest()[:12]
        cache_key = f"research_brief:{query_hash}"
        
        cache_manager.store_summary(
            context_key=cache_key,
            level="research",
            summary_text=json.dumps({"query": query, "context": search_context, "brief": brief, "sources": search_results}),
            model_id=MODEL_ID,
            prompt_tokens=result.get("prompt_tokens", 0),
            completion_tokens=result.get("completion_tokens", 0),
        )
    except Exception as e:
        logger.warning("Research brief cache write failed (non-blocking): %s", str(e)[:200])

    # Store finding in Research Findings Store (feeds back into taxonomy)
    try:
        from services.research_findings_store import ResearchFindingsStore
        findings_store = ResearchFindingsStore(cm)
        findings_store.store_site_investigation(
            context_key=search_context or f"research/{query_hash}",
            brief=brief,
            query=query,
            location=brief.get("situation", "")[:200],
        )
    except Exception as e:
        logger.warning("Research findings store write failed (non-blocking): %s", str(e)[:200])

    return success_response(
        {"brief": brief},
        200,
        event,
    )
