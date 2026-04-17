"""Lambda handler for embedding generation step of the ingestion pipeline.

Generates vector embeddings via Bedrock and stores them via the appropriate
search backend (Aurora pgvector for standard tier, OpenSearch for enterprise).
"""

import json
import logging
import os

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

_DEFAULT_EMBEDDING_MODEL = "amazon.titan-embed-text-v1"


def _get_backend_factory():
    """Build a BackendFactory if OpenSearch endpoint is configured."""
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


def _get_case_search_tier(case_id: str) -> str:
    """Look up the search_tier for a case file."""
    from db.connection import ConnectionManager
    from db.neptune import NeptuneConnectionManager
    from services.case_file_service import CaseFileService

    aurora_cm = ConnectionManager()
    neptune_cm = NeptuneConnectionManager(
        endpoint=os.environ.get("NEPTUNE_ENDPOINT", ""),
    )
    svc = CaseFileService(aurora_cm, neptune_cm)
    case_file = svc.get_case_file(case_id)
    tier = case_file.search_tier
    return tier.value if hasattr(tier, "value") else str(tier)


def handler(event, context):
    """Generate embedding for a document and store via the correct backend.

    Expected event:
        {
            "case_id": "...",
            "document_id": "...",
            "raw_text": "...",
            "sections": [...],
            "source_metadata": {...}
        }

    Returns:
        {
            "case_id": "...",
            "document_id": "...",
            "embedding_dimension": N,
            "search_tier": "standard"|"enterprise",
            "backend": "aurora"|"opensearch"
        }
    """
    import boto3
    from botocore.config import Config

    case_id = event["case_id"]
    document_id = event["document_id"]
    raw_text = event["raw_text"]
    sections = event.get("sections", [])
    source_metadata = event.get("source_metadata", {})

    # Read embed config from effective_config (set by ResolveConfig step),
    # falling back to env vars / hardcoded defaults for backward compatibility.
    embed_cfg = event.get("effective_config", {}).get("embed", {})
    model_id = embed_cfg.get(
        "embedding_model_id",
        os.environ.get("EMBEDDING_MODEL_ID", _DEFAULT_EMBEDDING_MODEL),
    )
    cfg_search_tier = embed_cfg.get("search_tier")
    opensearch_settings = embed_cfg.get("opensearch_settings", {})

    logger.info("Generating embedding for document %s in case %s (%d chars)", document_id, case_id, len(raw_text))

    # Titan embedding model has an 8192 token limit.
    # Conservative truncation: ~3.5 chars/token → 8000 tokens ≈ 28K chars,
    # but some docs have dense content with fewer chars/token.
    # Use 20K chars as safe ceiling (covers worst-case ~4 chars/token).
    MAX_EMBED_CHARS = 20_000
    embed_text = raw_text[:MAX_EMBED_CHARS] if len(raw_text) > MAX_EMBED_CHARS else raw_text

    bedrock_config = Config(
        read_timeout=120,
        connect_timeout=10,
        retries={"max_attempts": 2, "mode": "adaptive"},
    )
    bedrock = boto3.client("bedrock-runtime", config=bedrock_config)
    body = json.dumps({"inputText": embed_text})
    response = bedrock.invoke_model(
        modelId=model_id,
        contentType="application/json",
        accept="application/json",
        body=body,
    )
    response_body = json.loads(response["body"].read())
    embedding = response_body["embedding"]

    # Route to correct backend based on case search_tier.
    # Prefer effective_config value, fall back to DB lookup.
    search_tier = cfg_search_tier if cfg_search_tier else _get_case_search_tier(case_id)
    backend_factory = _get_backend_factory()
    backend = backend_factory.get_backend(search_tier)
    backend_name = "opensearch" if search_tier == "enterprise" else "aurora"

    from services.search_backend import IndexDocumentRequest
    index_req = IndexDocumentRequest(
        document_id=document_id,
        case_file_id=case_id,
        text=raw_text,
        embedding=embedding,
        metadata={
            "source_filename": source_metadata.get("filename", ""),
            "sections": sections,
        },
    )
    backend.index_documents(case_id, [index_req])

    logger.info(
        "Stored embedding (%d dims) for document %s via %s backend",
        len(embedding), document_id, backend_name,
    )

    return {
        "case_id": case_id,
        "document_id": document_id,
        "embedding_dimension": len(embedding),
        "search_tier": search_tier,
        "backend": backend_name,
    }
