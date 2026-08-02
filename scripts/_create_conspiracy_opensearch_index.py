"""Create OpenSearch Serverless indices for the Conspiracy Theory Taxonomy.

Creates two indices:
1. Updates existing `typology-patterns` index mapping to support conspiracy taxonomy signatures
2. Creates new `conspiracy-documents` index for document embeddings and k-NN matching

Usage:
    python scripts/_create_conspiracy_opensearch_index.py

Requires:
    - AWS credentials configured (same account: 974220725866, us-east-1)
    - OpenSearch Serverless collection: u260nrrtc0q87ji8iu0k
"""
import json
import boto3
from opensearchpy import OpenSearch, RequestsHttpConnection, AWSV4SignerAuth

# Configuration
OPENSEARCH_ENDPOINT = "https://u260nrrtc0q87ji8iu0k.us-east-1.aoss.amazonaws.com"
REGION = "us-east-1"
SERVICE = "aoss"

# Index definitions
CONSPIRACY_DOCUMENTS_INDEX = "conspiracy-documents"
TYPOLOGY_PATTERNS_INDEX = "typology-patterns"

CONSPIRACY_DOCUMENTS_MAPPING = {
    "settings": {
        "index": {
            "knn": True,
            "knn.algo_param.ef_search": 512
        }
    },
    "mappings": {
        "properties": {
            "document_id": {"type": "keyword"},
            "theory_name": {"type": "keyword"},
            "source_file": {"type": "text"},
            "source_type": {"type": "keyword"},
            "content_summary": {"type": "text"},
            "embedding": {
                "type": "knn_vector",
                "dimension": 1024,
                "method": {
                    "name": "hnsw",
                    "engine": "nmslib",
                    "space_type": "cosinesimil",
                    "parameters": {"ef_construction": 512, "m": 16}
                }
            },
            "matched_signatures": {"type": "keyword"},
            "ach_dominant_hypothesis": {"type": "keyword"},
            "reproducibility_score": {"type": "float"},
            "ingestion_timestamp": {"type": "date"}
        }
    }
}

# Fields to add to existing typology-patterns index (if updating)
TYPOLOGY_PATTERNS_ADDITIONAL_FIELDS = {
    "taxonomy_domain": {"type": "keyword"},  # "ancient_mysteries" | "conspiracy_theory"
    "status": {"type": "keyword"},           # "active" | "universal_confirmed" | "deprecated"
    "theory_sources": {"type": "keyword"}    # Array of theory names where this signature was found
}


def get_opensearch_client():
    """Create an authenticated OpenSearch client for Serverless."""
    credentials = boto3.Session().get_credentials()
    auth = AWSV4SignerAuth(credentials, REGION, SERVICE)

    client = OpenSearch(
        hosts=[{"host": OPENSEARCH_ENDPOINT.replace("https://", ""), "port": 443}],
        http_auth=auth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection,
        timeout=30,
    )
    return client


def create_conspiracy_documents_index(client):
    """Create the conspiracy-documents index for document embeddings."""
    if client.indices.exists(index=CONSPIRACY_DOCUMENTS_INDEX):
        print(f"Index '{CONSPIRACY_DOCUMENTS_INDEX}' already exists — skipping creation")
        return

    print(f"Creating index '{CONSPIRACY_DOCUMENTS_INDEX}'...")
    response = client.indices.create(
        index=CONSPIRACY_DOCUMENTS_INDEX,
        body=CONSPIRACY_DOCUMENTS_MAPPING
    )
    print(f"Created: {response}")


def update_typology_patterns_mapping(client):
    """Add conspiracy-theory-specific fields to the existing typology-patterns index."""
    if not client.indices.exists(index=TYPOLOGY_PATTERNS_INDEX):
        print(f"Index '{TYPOLOGY_PATTERNS_INDEX}' does not exist — cannot update")
        return

    print(f"Updating mapping for '{TYPOLOGY_PATTERNS_INDEX}'...")
    try:
        response = client.indices.put_mapping(
            index=TYPOLOGY_PATTERNS_INDEX,
            body={"properties": TYPOLOGY_PATTERNS_ADDITIONAL_FIELDS}
        )
        print(f"Updated: {response}")
    except Exception as e:
        print(f"Mapping update failed (may already exist): {e}")


def main():
    print("Connecting to OpenSearch Serverless...")
    client = get_opensearch_client()

    # Test connection
    try:
        info = client.info()
        print(f"Connected: {info.get('version', {}).get('distribution', 'unknown')}")
    except Exception as e:
        print(f"Connection failed: {e}")
        print("Make sure AWS credentials are configured and VPC access is available.")
        return

    # Create new index
    create_conspiracy_documents_index(client)

    # Update existing index
    update_typology_patterns_mapping(client)

    print("\nDone. Indices ready for conspiracy theory taxonomy.")


if __name__ == "__main__":
    main()
