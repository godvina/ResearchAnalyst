"""Index Pattern Library signatures into OpenSearch typology-patterns index.

Reads taxonomy JSON files, embeds each signature's vector_text via
Amazon Titan Embed Text v2, and upserts into the OpenSearch Serverless
'typology-patterns' index for k-NN scoring.

Usage:
    python scripts/index_pattern_library.py [--dry-run] [--domain ancient_mysteries]

Environment variables:
    OPENSEARCH_ENDPOINT - OpenSearch Serverless endpoint (required)
    AWS_REGION - defaults to us-east-1
"""

import argparse
import hashlib
import json
import logging
import os
import sys
import time
import urllib.request
import urllib.error

import boto3
import botocore.auth
import botocore.awsrequest
from botocore.session import Session as BotocoreSession

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
OPENSEARCH_ENDPOINT = os.environ.get("OPENSEARCH_ENDPOINT", "")
API_URL = os.environ.get("API_URL", "https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1")
INDEX_NAME = "typology-patterns"
EMBED_MODEL = "amazon.titan-embed-text-v2:0"

# Paths to taxonomy files
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TAXONOMY_FILES = [
    os.path.join(BASE_DIR, "src", "data", "pattern-library-taxonomy.json"),
    os.path.join(BASE_DIR, "src", "data", "ancient-mysteries-taxonomy.json"),
]

bedrock = boto3.client("bedrock-runtime", region_name=AWS_REGION)


def embed_text(text: str) -> list[float]:
    """Embed text using Amazon Titan Embed Text v2 (1024 dimensions)."""
    resp = bedrock.invoke_model(
        modelId=EMBED_MODEL,
        contentType="application/json",
        accept="application/json",
        body=json.dumps({"inputText": text[:8000]}),
    )
    body = json.loads(resp["body"].read())
    return body["embedding"]


def opensearch_request(method: str, path: str, body: dict = None) -> dict:
    """Make a SigV4-signed request to OpenSearch Serverless."""
    endpoint = OPENSEARCH_ENDPOINT.rstrip("/")
    if not endpoint.startswith("https://"):
        endpoint = f"https://{endpoint}"

    url = f"{endpoint}{path}"
    body_bytes = json.dumps(body).encode("utf-8") if body else b""

    session = BotocoreSession()
    credentials = session.get_credentials().get_frozen_credentials()
    headers = {
        "Content-Type": "application/json",
        "X-Amz-Content-Sha256": hashlib.sha256(body_bytes).hexdigest(),
    }

    aws_req = botocore.awsrequest.AWSRequest(
        method=method, url=url, headers=headers, data=body_bytes
    )
    signer = botocore.auth.SigV4Auth(credentials, "aoss", AWS_REGION)
    signer.add_auth(aws_req)
    prepared = aws_req.prepare()

    from botocore.httpsession import URLLib3Session
    http_session = URLLib3Session()
    response = http_session.send(prepared)

    if response.status_code >= 400:
        logger.error("OpenSearch %s %s → %d: %s", method, path,
                     response.status_code, response.content[:500])
        return {"error": response.status_code}

    return json.loads(response.content.decode("utf-8")) if response.content else {}


def load_signatures(domain_filter: str = None) -> list[dict]:
    """Load all signatures from taxonomy files, optionally filtered by domain."""
    all_sigs = []

    for filepath in TAXONOMY_FILES:
        if not os.path.exists(filepath):
            logger.warning("Taxonomy file not found: %s", filepath)
            continue

        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Handle multi-domain file (pattern-library-taxonomy.json)
        if "domains" in data:
            domains = data["domains"]
        else:
            # Single-domain file (ancient-mysteries-taxonomy.json)
            domains = [data]

        for domain in domains:
            domain_id = domain.get("domain_id", "unknown")
            if domain_filter and domain_id != domain_filter:
                continue

            for typology in domain.get("typologies", []):
                typology_id = typology.get("typology_id", "")
                for method in typology.get("methods", []):
                    method_id = method.get("method_id", "")
                    for sig in method.get("signatures", []):
                        sig_doc = {
                            "pattern_id": sig["signature_id"],
                            "description": sig["description"],
                            "severity": sig["severity"],
                            "typology": typology_id,
                            "method": method_id,
                            "domain": domain_id,
                            "precedent_case": sig.get("precedent_case", ""),
                            "indicators": sig.get("indicators", []),
                            "vector_text": sig.get("vector_text", ""),
                            "vector_hash": hashlib.md5(
                                sig.get("vector_text", "").encode()
                            ).hexdigest(),
                        }
                        all_sigs.append(sig_doc)

    return all_sigs


def get_existing_hashes() -> dict[str, str]:
    """Fetch existing pattern_id → vector_hash from OpenSearch for delta detection."""
    try:
        result = opensearch_request("POST", f"/{INDEX_NAME}/_search", {
            "size": 10000,
            "_source": ["pattern_id", "vector_hash"],
            "query": {"match_all": {}}
        })
        hits = result.get("hits", {}).get("hits", [])
        return {h["_source"]["pattern_id"]: h["_source"].get("vector_hash", "")
                for h in hits}
    except Exception as e:
        logger.warning("Could not fetch existing hashes: %s", str(e)[:200])
        return {}


def index_signatures(signatures: list[dict], dry_run: bool = False):
    """Embed and index signatures into OpenSearch. Idempotent (upsert by pattern_id)."""
    existing = get_existing_hashes() if not dry_run else {}
    stats = {"indexed": 0, "skipped_unchanged": 0, "failed": 0}

    for i, sig in enumerate(signatures, 1):
        pid = sig["pattern_id"]

        # Skip if vector_text unchanged (hash match)
        if pid in existing and existing[pid] == sig["vector_hash"]:
            stats["skipped_unchanged"] += 1
            continue

        logger.info("[%d/%d] Embedding %s (%s/%s)...",
                    i, len(signatures), pid, sig["domain"], sig["typology"])

        if dry_run:
            stats["indexed"] += 1
            continue

        # Embed
        try:
            embedding = embed_text(sig["vector_text"])
            time.sleep(0.1)  # Rate limit courtesy
        except Exception as e:
            logger.error("Embedding failed for %s: %s", pid, str(e)[:200])
            stats["failed"] += 1
            continue

        # Build document
        doc = {
            "pattern_id": pid,
            "description": sig["description"],
            "severity": sig["severity"],
            "typology": sig["typology"],
            "method": sig["method"],
            "domain": sig["domain"],
            "precedent_case": sig["precedent_case"],
            "indicators": sig["indicators"],
            "vector_hash": sig["vector_hash"],
            "embedding": embedding,
        }

        # Upsert (use pattern_id as document ID for idempotency)
        doc_id = pid.replace("/", "_")
        result = opensearch_request("PUT", f"/{INDEX_NAME}/_doc/{doc_id}", doc)
        if "error" in result:
            stats["failed"] += 1
        else:
            stats["indexed"] += 1
            # Path-based invalidation: mark ancestor-chain summaries as stale
            # for this specific signature so analysts see fresh AI summaries.
            invalidate_signature_path(
                domain=sig["domain"],
                typology=sig["typology"],
                method=sig["method"],
                signature_id=pid,
            )

    return stats


def invalidate_signature_path(domain: str, typology: str, method: str, signature_id: str):
    """POST path-based invalidation for a single signature's ancestor chain.

    When a signature is added or modified, invalidate cached AI summaries for
    the parent method, parent typology, and parent domain. Uses the domain as
    the context_key prefix since invalidate_by_path uses LIKE prefix% matching.

    Args:
        domain: Domain ID (e.g., 'antitrust')
        typology: Typology ID (e.g., 'procurement_collusion')
        method: Method ID (e.g., 'bid_rotation')
        signature_id: Signature ID (e.g., 'atr-pc-br-001')

    Failure is non-fatal — logged as a warning.
    """
    # The invalidation endpoint uses LIKE prefix% on context_key, so passing
    # the domain prefix invalidates all ancestor levels:
    #   domain, domain/typology, domain/typology/method
    context_key_prefix = domain
    url = f"{API_URL.rstrip('/')}/pattern-library/summary/invalidate"
    body = json.dumps({"context_key": context_key_prefix}).encode("utf-8")
    req = urllib.request.Request(
        url, data=body, method="POST",
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            count = result.get("invalidated_count", "?")
            logger.info(
                "Path-based invalidation for %s/%s/%s/%s → %s summaries marked stale",
                domain, typology, method, signature_id, count,
            )
    except urllib.error.HTTPError as e:
        logger.warning(
            "Path-based invalidation returned HTTP %d for %s/%s/%s/%s: %s",
            e.code, domain, typology, method, signature_id,
            e.read().decode("utf-8", errors="replace")[:200],
        )
    except Exception as e:
        logger.warning(
            "Path-based invalidation failed (non-fatal) for %s/%s/%s/%s: %s",
            domain, typology, method, signature_id, str(e)[:200],
        )


def invalidate_summary_cache():
    """POST to /pattern-library/summary/invalidate to clear all cached AI summaries.

    Called after successful re-seed so analysts see fresh summaries reflecting
    updated taxonomy data. Failure is non-fatal — logged as a warning.
    """
    url = f"{API_URL.rstrip('/')}/pattern-library/summary/invalidate"
    body = json.dumps({}).encode("utf-8")
    req = urllib.request.Request(
        url, data=body, method="POST",
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            count = result.get("invalidated_count", "?")
            logger.info("AI summary cache invalidated: %s summaries marked stale", count)
    except urllib.error.HTTPError as e:
        logger.warning("Summary cache invalidation returned HTTP %d: %s",
                       e.code, e.read().decode("utf-8", errors="replace")[:200])
    except Exception as e:
        logger.warning("Summary cache invalidation failed (non-fatal): %s", str(e)[:200])


def main():
    parser = argparse.ArgumentParser(description="Index Pattern Library into OpenSearch")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be indexed without actually doing it")
    parser.add_argument("--domain", type=str, default=None, help="Filter to specific domain (e.g., ancient_mysteries)")
    args = parser.parse_args()

    if not OPENSEARCH_ENDPOINT and not args.dry_run:
        logger.error("OPENSEARCH_ENDPOINT environment variable not set. Use --dry-run to test without AWS.")
        sys.exit(1)

    logger.info("Loading signatures from taxonomy files...")
    signatures = load_signatures(domain_filter=args.domain)
    logger.info("Loaded %d signatures", len(signatures))

    # Summary by domain/typology
    from collections import Counter
    domain_counts = Counter(s["domain"] for s in signatures)
    typology_counts = Counter(f"{s['domain']}/{s['typology']}" for s in signatures)

    logger.info("=== Signatures by domain ===")
    for domain, count in sorted(domain_counts.items()):
        logger.info("  %s: %d signatures", domain, count)

    logger.info("=== Signatures by typology ===")
    for typo, count in sorted(typology_counts.items()):
        logger.info("  %s: %d", typo, count)

    if args.dry_run:
        logger.info("\n[DRY RUN] Would embed and index %d signatures. No AWS calls made.", len(signatures))
        return

    logger.info("\nIndexing %d signatures into %s/%s...", len(signatures), OPENSEARCH_ENDPOINT[:40], INDEX_NAME)
    stats = index_signatures(signatures, dry_run=args.dry_run)

    logger.info("\n=== Results ===")
    logger.info("  Indexed (new/updated): %d", stats["indexed"])
    logger.info("  Skipped (unchanged):   %d", stats["skipped_unchanged"])
    logger.info("  Failed:                %d", stats["failed"])

    # Invalidate AI summary cache so analysts see fresh summaries
    if stats["indexed"] > 0 or stats["failed"] == 0:
        invalidate_summary_cache()


if __name__ == "__main__":
    main()
