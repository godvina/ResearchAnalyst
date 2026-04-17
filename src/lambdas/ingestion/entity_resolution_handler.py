"""Lambda handler for entity resolution — merges duplicate entities in Neptune.

Invoked as a post-ingestion step or on-demand via API. Runs inside VPC
to access Neptune directly.

Event format:
    {
        "case_id": "...",
        "dry_run": true/false,    # default false
        "use_llm": true/false     # default true
    }

Returns:
    {
        "case_id": "...",
        "entities_fetched": N,
        "candidates_found": N,
        "clusters": N,
        "merge_stats": {...},
        "opensearch_updated": N,
        "cluster_details": [...]
    }
"""

import json
import logging
import os

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

NEPTUNE_ENDPOINT = os.environ.get("NEPTUNE_ENDPOINT", "")
NEPTUNE_PORT = os.environ.get("NEPTUNE_PORT", "8182")
OPENSEARCH_ENDPOINT = os.environ.get("OPENSEARCH_ENDPOINT", "")


def handler(event, context):
    """Run entity resolution for a case."""
    import boto3
    from services.entity_resolution_service import EntityResolutionService

    case_id = event.get("case_id", "")
    dry_run = event.get("dry_run", False)
    use_llm = event.get("use_llm", True)
    max_degree = event.get("max_degree", 500)

    if not case_id:
        return {"statusCode": 400, "error": "Missing case_id"}

    if not NEPTUNE_ENDPOINT:
        return {"statusCode": 500, "error": "NEPTUNE_ENDPOINT not configured"}

    logger.info("Entity resolution for case %s (dry_run=%s, use_llm=%s)",
                case_id[:8], dry_run, use_llm)

    bedrock_client = boto3.client("bedrock-runtime") if use_llm else None

    service = EntityResolutionService(
        neptune_endpoint=NEPTUNE_ENDPOINT,
        neptune_port=NEPTUNE_PORT,
        bedrock_client=bedrock_client,
        opensearch_endpoint=OPENSEARCH_ENDPOINT or None,
    )

    result = service.resolve(
        case_id=case_id,
        dry_run=dry_run,
        use_llm=use_llm,
        max_degree=max_degree,
    )

    logger.info("Entity resolution complete: %d clusters, %d nodes merged",
                result["clusters"], result["merge_stats"].get("nodes_dropped", 0))

    return result
