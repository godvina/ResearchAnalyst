"""Lambda handler for document classification step of the ingestion pipeline.

Classifies documents and routes them to the appropriate case using one of
three modes: folder_based (default/skip), metadata_routing, or ai_classification.
Runs after ParseDocument and before ExtractEntities in the Step Functions pipeline.
"""

import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Lazy-initialized clients (reused across warm invocations)
_aurora_cm = None
_bedrock_client = None
_s3_client = None


def _get_aurora_cm():
    """Lazy-initialize Aurora connection manager."""
    global _aurora_cm
    if _aurora_cm is None:
        from db.connection import ConnectionManager
        _aurora_cm = ConnectionManager()
    return _aurora_cm


def _get_bedrock_client():
    """Lazy-initialize Bedrock runtime client."""
    global _bedrock_client
    if _bedrock_client is None:
        import boto3
        from botocore.config import Config
        bedrock_config = Config(
            read_timeout=120,
            connect_timeout=10,
            retries={"max_attempts": 2, "mode": "adaptive"},
        )
        _bedrock_client = boto3.client("bedrock-runtime", config=bedrock_config)
    return _bedrock_client


def _get_s3_client():
    """Lazy-initialize S3 client."""
    global _s3_client
    if _s3_client is None:
        import boto3
        _s3_client = boto3.client("s3")
    return _s3_client


def handler(event, context):
    """Classify a single document and route it to the appropriate case.

    Expected event:
        {
            "case_id": "...",
            "document_id": "...",
            "parse_result": {"raw_text": "...", "source_metadata": {...}},
            "effective_config": {"classification": {"routing_mode": "...", ...}}
        }

    Returns:
        {
            "classification_result": {
                "action": "skipped" | "assigned" | "triage",
                "case_id": "..." | None,
                "confidence": float,
                "case_category": "..." | None,
                "routing_reason": "..."
            }
        }
    """
    try:
        config = event.get("effective_config", {}).get("classification", {})

        # If folder_based or classification section is missing/empty, skip
        routing_mode = config.get("routing_mode", "folder_based")
        if routing_mode == "folder_based" or not config:
            logger.info("Classification skipped: routing_mode=%s", routing_mode)
            return {
                "classification_result": {
                    "action": "skipped",
                    "reason": "folder_based",
                }
            }

        document_id = event["document_id"]
        parsed_text = event.get("parse_result", {}).get("raw_text", "")
        source_metadata = event.get("parse_result", {}).get("source_metadata", {})

        logger.info(
            "Classifying document %s with routing_mode=%s (%d chars)",
            document_id, routing_mode, len(parsed_text),
        )

        from services.document_classification_service import DocumentClassificationService

        svc = DocumentClassificationService(
            _get_aurora_cm(),
            _get_bedrock_client(),
            _get_s3_client(),
        )

        result = svc.classify(document_id, parsed_text, source_metadata, config)
        outcome = svc.route_document(document_id, result, config)

        logger.info(
            "Document %s classified: action=%s, confidence=%.2f",
            document_id, outcome.action, result.confidence,
        )

        return {
            "classification_result": {
                "action": outcome.action,
                "case_id": str(outcome.case_id) if outcome.case_id else None,
                "confidence": result.confidence,
                "case_category": result.case_category,
                "routing_reason": result.routing_reason,
            }
        }

    except Exception as exc:
        logger.exception("Classification failed for document %s", event.get("document_id", "unknown"))
        return {
            "classification_result": {
                "action": "error",
                "error": str(exc),
                "document_id": event.get("document_id"),
            }
        }
