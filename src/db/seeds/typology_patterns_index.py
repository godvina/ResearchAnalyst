"""Seed script — create and populate the 'typology-patterns' OpenSearch index.

This index stores pre-embedded crime typology indicator descriptions. During
pipeline scoring, the score_typology Lambda performs k-NN search against this
index to find which prosecution patterns match the case evidence.

Usage:
    python -m src.db.seeds.typology_patterns_index

The script is idempotent: it deletes and recreates the index on every run.
"""

import hashlib
import json
import logging
import os
import time
import urllib.error

import boto3
import botocore.auth
import botocore.awsrequest
from botocore.config import Config
from botocore.session import Session as BotocoreSession

from services.typology_query_definitions import TYPOLOGY_QUERIES

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Index configuration
# ---------------------------------------------------------------------------

INDEX_NAME = "typology-patterns"

INDEX_MAPPING = {
    "settings": {
        "index": {
            "knn": True,
            "knn.algo_param.ef_search": 512,
        }
    },
    "mappings": {
        "properties": {
            "typology_module_id": {"type": "keyword"},
            "sub_category_id": {"type": "keyword"},
            "pattern_text": {"type": "text", "analyzer": "standard"},
            "embedding": {
                "type": "knn_vector",
                "dimension": 1024,
                "method": {
                    "name": "hnsw",
                    "space_type": "cosinesimil",
                    "engine": "nmslib",
                    "parameters": {"ef_construction": 512, "m": 16},
                },
            },
            "source": {"type": "keyword"},
            "severity": {"type": "keyword"},
            "indicator_name": {"type": "keyword"},
        }
    },
}


# ---------------------------------------------------------------------------
# Embedding helper
# ---------------------------------------------------------------------------


def _embed_text(bedrock_client, text: str) -> list[float]:
    """Generate 1536-dim embedding via Amazon Titan Embed Text v2."""
    response = bedrock_client.invoke_model(
        modelId="amazon.titan-embed-text-v2:0",
        contentType="application/json",
        accept="application/json",
        body=json.dumps({"inputText": text}),
    )
    body = json.loads(response["body"].read())
    return body["embedding"]


# ---------------------------------------------------------------------------
# OpenSearch Serverless HTTP helpers (SigV4-signed)
# ---------------------------------------------------------------------------


def _aoss_request(
    endpoint: str,
    region: str,
    method: str,
    path: str,
    body: str | None = None,
) -> dict:
    """Execute a SigV4-signed request against OpenSearch Serverless (AOSS)."""
    url = f"{endpoint}{path}"

    session = BotocoreSession()
    credentials = session.get_credentials()
    if credentials is None:
        raise EnvironmentError("No AWS credentials available for SigV4 signing")
    credentials = credentials.get_frozen_credentials()

    headers = {"Content-Type": "application/json"}
    body_bytes = body.encode("utf-8") if body else b""
    headers["X-Amz-Content-Sha256"] = hashlib.sha256(body_bytes).hexdigest()

    aws_request = botocore.awsrequest.AWSRequest(
        method=method, url=url, headers=headers, data=body_bytes
    )
    signer = botocore.auth.SigV4Auth(credentials, "aoss", region)
    signer.add_auth(aws_request)

    prepared = aws_request.prepare()

    from botocore.httpsession import URLLib3Session

    http_session = URLLib3Session()
    response = http_session.send(prepared)

    resp_body = response.content.decode("utf-8") if response.content else ""

    if response.status_code >= 400:
        # For HEAD requests or expected 404s, raise so caller can handle
        raise urllib.error.HTTPError(
            url, response.status_code, resp_body[:500], {}, None
        )

    return json.loads(resp_body) if resp_body else {}


def _index_exists(endpoint: str, region: str) -> bool:
    """Check if the typology-patterns index already exists."""
    try:
        _aoss_request(endpoint, region, "GET", f"/{INDEX_NAME}/_settings")
        return True
    except urllib.error.HTTPError as e:
        # AOSS returns 403 or 404 when index doesn't exist
        if e.code in (404, 403):
            return False
        raise


def _delete_index(endpoint: str, region: str) -> None:
    """Delete the typology-patterns index."""
    _aoss_request(endpoint, region, "DELETE", f"/{INDEX_NAME}")
    logger.info("Deleted existing index '%s'", INDEX_NAME)


def _create_index(endpoint: str, region: str) -> None:
    """Create the typology-patterns index with k-NN mapping."""
    _aoss_request(
        endpoint, region, "PUT", f"/{INDEX_NAME}", body=json.dumps(INDEX_MAPPING)
    )
    logger.info("Created index '%s' with k-NN mapping", INDEX_NAME)


def _bulk_index(endpoint: str, region: str, documents: list[dict]) -> None:
    """Bulk-index documents into the typology-patterns index."""
    # Build NDJSON bulk payload
    lines: list[str] = []
    for doc in documents:
        # AOSS does NOT support custom _id in bulk operations
        doc.pop("_id", None)
        action = json.dumps({"index": {"_index": INDEX_NAME}})
        lines.append(action)
        lines.append(json.dumps(doc))
    # Bulk body must end with a newline
    bulk_body = "\n".join(lines) + "\n"

    resp = _aoss_request(
        endpoint, region, "POST", "/_bulk", body=bulk_body
    )
    errors = resp.get("errors", False)
    if errors:
        failed = [
            item for item in resp.get("items", []) if item.get("index", {}).get("error")
        ]
        logger.warning("Bulk index had %d errors: %s", len(failed), failed[:3])
    else:
        logger.info("Bulk indexed %d documents successfully", len(documents))


# ---------------------------------------------------------------------------
# Document builder
# ---------------------------------------------------------------------------


def _build_pattern_documents() -> list[dict]:
    """Build pattern documents from TYPOLOGY_QUERIES (without embeddings yet)."""
    documents: list[dict] = []

    for module_id, sub_categories in TYPOLOGY_QUERIES.items():
        for sub_category_id, sub_cat_def in sub_categories.items():
            indicators = sub_cat_def.get("indicators", [])
            for indicator in indicators:
                doc = {
                    "typology_module_id": module_id,
                    "sub_category_id": sub_category_id,
                    "pattern_text": indicator,
                    "indicator_name": indicator,
                    "source": "prosecution_framework",
                    "severity": "high",
                }
                documents.append(doc)

    return documents


# ---------------------------------------------------------------------------
# Main seed function
# ---------------------------------------------------------------------------


def seed_typology_patterns() -> None:
    """Create the typology-patterns index and seed it with prosecution pattern embeddings.

    Steps:
        1. Delete and recreate the index (idempotent).
        2. Build pattern documents from TYPOLOGY_QUERIES.
        3. Generate embeddings via Bedrock Titan Embed v2.
        4. Bulk index all documents.
    """
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")

    endpoint = os.environ.get("OPENSEARCH_ENDPOINT", "")
    if not endpoint:
        raise EnvironmentError(
            "OPENSEARCH_ENDPOINT environment variable is required. "
            "Set it to your OpenSearch Serverless collection endpoint."
        )
    if not endpoint.startswith("https://"):
        endpoint = f"https://{endpoint}"
    endpoint = endpoint.rstrip("/")

    region = os.environ.get("AWS_REGION", "us-east-1")

    # --- Step 1: Delete and recreate index ---
    if _index_exists(endpoint, region):
        _delete_index(endpoint, region)
        # Brief pause to let deletion propagate
        time.sleep(2)

    _create_index(endpoint, region)
    # Allow index to initialize
    time.sleep(3)

    # --- Step 2: Build pattern documents ---
    documents = _build_pattern_documents()
    logger.info("Built %d pattern documents from TYPOLOGY_QUERIES", len(documents))

    # --- Step 3: Generate embeddings ---
    bedrock_client = boto3.client(
        "bedrock-runtime",
        region_name=region,
        config=Config(retries={"max_attempts": 3, "mode": "adaptive"}),
    )

    for i, doc in enumerate(documents):
        doc["embedding"] = _embed_text(bedrock_client, doc["pattern_text"])
        # Rate limiting: 0.1s between embedding calls
        time.sleep(0.1)
        if (i + 1) % 50 == 0:
            logger.info("Embedded %d / %d patterns...", i + 1, len(documents))

    logger.info("Completed embedding generation for %d patterns", len(documents))

    # --- Step 4: Bulk index ---
    # Index in batches of 100 to avoid oversized payloads
    batch_size = 100
    for start in range(0, len(documents), batch_size):
        batch = documents[start : start + batch_size]
        _bulk_index(endpoint, region, batch)

    logger.info(
        "Seeded %d prosecution pattern embeddings into %s index",
        len(documents),
        INDEX_NAME,
    )


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    seed_typology_patterns()
