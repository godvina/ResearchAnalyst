"""API handlers for AI Investigative Search.

Endpoints:
    POST /case-files/{id}/investigative-search — intelligence-grade search
    POST /case-files/{id}/lead-assessment — lead deep-dive
    GET  /case-files/{id}/lead-assessment/{job_id} — poll async result
"""

import json
import logging
import os

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Module-level cache to avoid rebuilding service on every invocation
_cached_service = None


def _build_service():
    """Construct InvestigativeSearchService with all dependencies (cached)."""
    global _cached_service
    if _cached_service is not None:
        return _cached_service

    import boto3
    from botocore.config import Config
    from db.connection import ConnectionManager
    from db.neptune import NeptuneConnectionManager
    from services.semantic_search_service import SemanticSearchService
    from services.case_file_service import CaseFileService
    from services.backend_factory import BackendFactory
    from services.aurora_pgvector_backend import AuroraPgvectorBackend
    from services.question_answer_service import QuestionAnswerService
    from services.investigator_ai_engine import InvestigatorAIEngine
    from services.ai_research_agent import AIResearchAgent
    from services.investigative_search_service import InvestigativeSearchService
    from services.findings_service import FindingsService

    aurora_cm = ConnectionManager()
    bedrock_config = Config(read_timeout=60, connect_timeout=5,
                            retries={"max_attempts": 1, "mode": "standard"})
    bedrock = boto3.client("bedrock-runtime", config=bedrock_config)
    neptune_ep = os.environ.get("NEPTUNE_ENDPOINT", "")

    # Build search service with proper backend factory (same as search.py)
    agent_runtime_client = boto3.client("bedrock-agent-runtime",
        config=Config(read_timeout=15, connect_timeout=5,
                      retries={"max_attempts": 1, "mode": "standard"}))
    kb_id = os.environ.get("KNOWLEDGE_BASE_ID", "")
    embedding_model_id = os.environ.get("BEDROCK_EMBEDDING_MODEL_ID", "amazon.titan-embed-text-v2:0")

    aurora_backend = AuroraPgvectorBackend(aurora_cm)
    opensearch_backend = None
    os_endpoint = os.environ.get("OPENSEARCH_ENDPOINT", "")
    if os_endpoint:
        from services.opensearch_serverless_backend import OpenSearchServerlessBackend
        opensearch_backend = OpenSearchServerlessBackend(collection_endpoint=os_endpoint)

    backend_factory = BackendFactory(
        aurora_backend=aurora_backend,
        opensearch_backend=opensearch_backend,
    )
    neptune_cm = NeptuneConnectionManager(endpoint=neptune_ep)
    case_file_service = CaseFileService(aurora_cm, neptune_cm)

    search_svc = SemanticSearchService(
        bedrock_agent_runtime_client=agent_runtime_client,
        knowledge_base_id=kb_id,
        backend_factory=backend_factory,
        case_file_service=case_file_service,
        bedrock_client=bedrock,
        embedding_model_id=embedding_model_id,
    )
    qa_svc = QuestionAnswerService(
        aurora_cm=aurora_cm, bedrock_client=bedrock,
        neptune_endpoint=neptune_ep,
    )
    ai_engine = InvestigatorAIEngine(
        aurora_cm=aurora_cm, bedrock_client=bedrock,
        neptune_endpoint=neptune_ep,
    )
    research_agent = AIResearchAgent(bedrock_client=bedrock)
    findings_svc = FindingsService(
        aurora_cm=aurora_cm,
        s3_bucket=os.environ.get("S3_DATA_BUCKET", os.environ.get("S3_BUCKET_NAME", "")),
    )

    _cached_service = InvestigativeSearchService(
        semantic_search=search_svc, question_answer=qa_svc,
        ai_engine=ai_engine, research_agent=research_agent,
        bedrock_client=bedrock, neptune_endpoint=neptune_ep,
        findings_service=findings_svc,
    )
    return _cached_service


def investigative_search_handler(event, context):
    """POST /case-files/{id}/investigative-search"""
    from lambdas.api.response_helper import error_response, success_response
    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        if not case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case ID", event)

        body = (json.loads(event.get("body")) if isinstance(event.get("body"), str) else (event.get("body") or {}))
        query = body.get("query", "").strip()
        if not query:
            return error_response(400, "VALIDATION_ERROR", "Missing 'query' in request body", event)

        search_scope = body.get("search_scope", "internal")
        if search_scope not in ("internal", "internal_external"):
            return error_response(400, "VALIDATION_ERROR", "search_scope must be 'internal' or 'internal_external'", event)

        top_k = int(body.get("top_k", 10))
        if top_k < 1 or top_k > 50:
            return error_response(400, "VALIDATION_ERROR", "top_k must be 1-50", event)

        output_format = body.get("output_format", "full")
        if output_format not in ("full", "brief"):
            return error_response(400, "VALIDATION_ERROR", "output_format must be 'full' or 'brief'", event)

        svc = _build_service()
        result = svc.investigative_search(
            case_id=case_id, query=query, search_scope=search_scope,
            top_k=top_k, output_format=output_format,
            graph_case_id=body.get("graph_case_id", ""),
        )
        return success_response(result, 200, event)

    except Exception as exc:
        logger.exception("Investigative search failed")
        return error_response(500, "INTERNAL_ERROR", str(exc)[:500], event)


def lead_assessment_handler(event, context):
    """POST /case-files/{id}/lead-assessment"""
    from lambdas.api.response_helper import error_response, success_response
    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        if not case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case ID", event)

        body = (json.loads(event.get("body")) if isinstance(event.get("body"), str) else (event.get("body") or {}))
        subjects = body.get("subjects", [])
        if not subjects:
            return error_response(400, "VALIDATION_ERROR", "Missing 'subjects' array", event)
        if len(subjects) > 20:
            return error_response(400, "SUBJECT_LIMIT_EXCEEDED", "Maximum 20 subjects per lead assessment", event)

        svc = _build_service()
        result = svc.lead_assessment(case_id=case_id, lead_payload=body)
        return success_response(result, 200, event)

    except Exception as exc:
        logger.exception("Lead assessment failed")
        return error_response(500, "INTERNAL_ERROR", str(exc)[:500], event)
