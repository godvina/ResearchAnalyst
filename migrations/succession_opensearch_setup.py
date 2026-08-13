"""
Create OpenSearch indices for the Executive Succession Planning module.
Uses the existing OpenSearch Serverless cluster (hzrvvva3hodw069v9442).

Usage:
    python migrations/succession_opensearch_setup.py [--tenant-id TENANT_ID]

If --tenant-id is provided, creates the tenant-specific candidate index.
Otherwise creates only the shared role-signatures index.
"""
import argparse
import json
import logging
import sys
from pathlib import Path

import boto3
from opensearchpy import OpenSearch, RequestsHttpConnection, AWSV4SignerAuth

# Config
REGION = "us-east-1"
OPENSEARCH_ENDPOINT = "https://hzrvvva3hodw069v9442.us-east-1.aoss.amazonaws.com"
COLLECTION_ID = "hzrvvva3hodw069v9442"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def get_opensearch_client():
    """Create authenticated OpenSearch client using SigV4."""
    credentials = boto3.Session().get_credentials()
    auth = AWSV4SignerAuth(credentials, REGION, "aoss")

    client = OpenSearch(
        hosts=[{"host": OPENSEARCH_ENDPOINT.replace("https://", ""), "port": 443}],
        http_auth=auth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection,
        timeout=30,
    )
    return client


def create_role_signatures_index(client):
    """Create the shared role-signatures index (not tenant-specific)."""
    index_name = "succession-role-signatures"

    if client.indices.exists(index=index_name):
        logger.info(f"Index '{index_name}' already exists — skipping")
        return

    body = {
        "settings": {
            "index": {
                "knn": True,
                "knn.algo_param.ef_search": 512,
                "number_of_shards": 1,
                "number_of_replicas": 1
            }
        },
        "mappings": {
            "properties": {
                "role_config_id": {"type": "keyword"},
                "tenant_id": {"type": "keyword"},
                "role_type": {"type": "keyword"},
                "sector": {"type": "keyword"},
                "country": {"type": "keyword"},
                "signature_text": {"type": "text"},
                "competency_requirements": {"type": "text"},
                "signature_embedding": {
                    "type": "knn_vector",
                    "dimension": 1536,
                    "method": {
                        "name": "hnsw",
                        "space_type": "cosinesimil",
                        "engine": "nmslib",
                        "parameters": {
                            "ef_construction": 512,
                            "m": 16
                        }
                    }
                },
                "minimum_similarity_threshold": {"type": "float"},
                "created_at": {"type": "date"},
                "updated_at": {"type": "date"}
            }
        }
    }

    client.indices.create(index=index_name, body=body)
    logger.info(f"✅ Created index: {index_name}")


def create_candidate_index(client, tenant_id):
    """Create a tenant-specific candidate index."""
    index_name = f"succession-candidates-{tenant_id}"

    if client.indices.exists(index=index_name):
        logger.info(f"Index '{index_name}' already exists — skipping")
        return

    body = {
        "settings": {
            "index": {
                "knn": True,
                "knn.algo_param.ef_search": 512,
                "number_of_shards": 2,
                "number_of_replicas": 1
            }
        },
        "mappings": {
            "properties": {
                "candidate_id": {"type": "keyword"},
                "tenant_id": {"type": "keyword"},
                "name": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
                "current_title": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
                "current_organization": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
                "sector": {"type": "keyword"},
                "country": {"type": "keyword"},
                "seniority_level": {"type": "keyword"},
                "industries": {"type": "keyword"},
                "competency_summary": {"type": "text"},
                "profile_embedding": {
                    "type": "knn_vector",
                    "dimension": 1536,
                    "method": {
                        "name": "hnsw",
                        "space_type": "cosinesimil",
                        "engine": "nmslib",
                        "parameters": {
                            "ef_construction": 512,
                            "m": 16
                        }
                    }
                },
                "source_provenance": {
                    "type": "object",
                    "properties": {
                        "source_system": {"type": "keyword"},
                        "ingestion_timestamp": {"type": "date"},
                        "tier1_passed": {"type": "boolean"},
                        "tier2_passed": {"type": "boolean"},
                        "tier3_passed": {"type": "boolean"},
                        "original_doc_ref": {"type": "keyword"}
                    }
                },
                "last_profile_update": {"type": "date"},
                "is_passive": {"type": "boolean"},
                "open_to_work": {"type": "boolean"},
                "created_at": {"type": "date"},
                "updated_at": {"type": "date"}
            }
        }
    }

    client.indices.create(index=index_name, body=body)
    logger.info(f"✅ Created index: {index_name}")


def main():
    parser = argparse.ArgumentParser(description="Create OpenSearch indices for succession planning")
    parser.add_argument("--tenant-id", help="Tenant ID for candidate index creation")
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("Executive Succession Planning — OpenSearch Index Setup")
    logger.info(f"Endpoint: {OPENSEARCH_ENDPOINT}")
    logger.info(f"Region: {REGION}")
    logger.info("=" * 60)

    client = get_opensearch_client()

    # Always create the shared role-signatures index
    create_role_signatures_index(client)

    # Create tenant-specific candidate index if tenant_id provided
    if args.tenant_id:
        create_candidate_index(client, args.tenant_id)
    else:
        logger.info("No --tenant-id provided — skipping candidate index creation")
        logger.info("Run with --tenant-id <UUID> to create a tenant-specific candidate index")

    logger.info("\n✅ Done!")


if __name__ == "__main__":
    main()
