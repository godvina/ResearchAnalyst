"""Index UVG grid research findings into OpenSearch for vector similarity search.

Embeds each grid node's research findings using Amazon Titan Embed Text v2,
then indexes into OpenSearch Serverless for k-NN similarity queries like:
- "Find nodes similar to Giza" (what has similar characteristics?)
- "What do Node 7 and Node 44 have in common?" (vector comparison)
- "Find all nodes with megalithic construction evidence" (semantic search)

Uses the same pattern as index_pattern_library.py (SigV4 signed requests).
"""

import hashlib
import json
import math
import os
import sys
import time

import boto3
import botocore.auth
import botocore.awsrequest
from botocore.session import Session as BotocoreSession

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "src", "data")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
OPENSEARCH_ENDPOINT = os.environ.get("OPENSEARCH_ENDPOINT", "https://u260nrrtc0q87ji8iu0k.us-east-1.aoss.amazonaws.com")
INDEX_NAME = "grid-node-research"
EMBED_MODEL = "amazon.titan-embed-text-v2:0"

bedrock = boto3.client("bedrock-runtime", region_name=AWS_REGION)


def embed_text(text):
    """Embed text using Amazon Titan Embed Text v2 (1024 dimensions)."""
    resp = bedrock.invoke_model(
        modelId=EMBED_MODEL,
        contentType="application/json",
        accept="application/json",
        body=json.dumps({"inputText": text[:8000]}),
    )
    body = json.loads(resp["body"].read())
    return body["embedding"]


def opensearch_request(method, path, body=None):
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
        print(f"  OpenSearch {method} {path} → {response.status_code}: {response.content[:300]}")
        return {"error": response.status_code}

    return json.loads(response.content.decode("utf-8")) if response.content else {}


def create_index():
    """Create the grid-node-research index if it doesn't exist."""
    index_body = {
        "settings": {
            "index": {
                "knn": True,
                "number_of_shards": 1,
                "number_of_replicas": 0,
            }
        },
        "mappings": {
            "properties": {
                "node_id": {"type": "integer"},
                "lat": {"type": "float"},
                "lng": {"type": "float"},
                "classification": {"type": "keyword"},
                "continent": {"type": "keyword"},
                "known_site": {"type": "text"},
                "research_text": {"type": "text"},
                "investigation_status": {"type": "keyword"},
                "smoking_gun": {"type": "text"},
                "codename": {"type": "keyword"},
                "researched_at": {"type": "date"},
                "embedding": {
                    "type": "knn_vector",
                    "dimension": 1024,
                    "method": {
                        "name": "hnsw",
                        "space_type": "cosinesimil",
                        "engine": "nmslib",
                    },
                },
            }
        },
    }

    # Check if index exists
    resp = opensearch_request("HEAD", f"/{INDEX_NAME}")
    if not resp.get("error"):
        print(f"  Index '{INDEX_NAME}' already exists.")
        return True

    # Create it
    resp = opensearch_request("PUT", f"/{INDEX_NAME}", index_body)
    if resp.get("error"):
        print(f"  Failed to create index: {resp}")
        return False
    print(f"  Index '{INDEX_NAME}' created.")
    return True


def build_research_text(node, brief=None):
    """Build the text to embed for a grid node."""
    parts = [
        f"UVG Grid Node {node['id']}",
        f"Location: {node['lat']:.2f}°, {node['lng']:.2f}°",
        f"Classification: {node['classification']}",
    ]
    if node.get("continent"):
        parts.append(f"Region: {node['continent']}")
    if node.get("nearest_known_site"):
        parts.append(f"Nearest known site: {node['nearest_known_site']}")

    if brief and not brief.get("error"):
        if brief.get("situation"):
            parts.append(f"Situation: {brief['situation']}")
        if brief.get("smoking_gun"):
            parts.append(f"Key finding: {brief['smoking_gun']}")
        if brief.get("evidence_found"):
            for e in brief["evidence_found"][:3]:
                parts.append(f"Evidence: {e.get('finding', '')}")
        if brief.get("field_recommendation"):
            parts.append(f"Recommendation: {brief['field_recommendation']}")

    return " | ".join(parts)


def index_nodes(nodes, research_results=None):
    """Index all grid nodes into OpenSearch with embeddings."""
    # Build lookup for research results
    research_by_node = {}
    if research_results:
        for r in research_results.get("results", []):
            research_by_node[r["node_id"]] = r.get("brief", {})

    indexed = 0
    errors = 0
    for node in nodes:
        brief = research_by_node.get(node["id"], {})
        research_text = build_research_text(node, brief)

        # Embed
        try:
            embedding = embed_text(research_text)
        except Exception as e:
            print(f"  Embed failed for Node {node['id']}: {e}")
            errors += 1
            continue

        # Index document
        doc = {
            "node_id": node["id"],
            "lat": node["lat"],
            "lng": node["lng"],
            "classification": node["classification"],
            "continent": node.get("continent", ""),
            "known_site": node.get("nearest_known_site", ""),
            "research_text": research_text,
            "investigation_status": brief.get("investigation_status", "not_researched"),
            "smoking_gun": brief.get("smoking_gun", ""),
            "codename": brief.get("codename", ""),
            "researched_at": brief.get("researched_at") if brief else None,
            "embedding": embedding,
        }

        doc_id = f"grid_node_{node['id']}"
        resp = opensearch_request("POST", f"/{INDEX_NAME}/_doc", doc)
        if resp.get("error"):
            errors += 1
        else:
            indexed += 1

        if indexed % 10 == 0:
            print(f"  Indexed {indexed} nodes...")
        time.sleep(0.5)  # Rate limit embeddings

    return indexed, errors


def main():
    print("Indexing UVG Grid Nodes into OpenSearch")
    print("=" * 60)

    # Load grid data
    nodes = grid_db = json.load(open(os.path.join(DATA_DIR, "uvg-grid-investigation-database.json")))["nodes"]
    print(f"  Nodes to index: {len(nodes)}")

    # Load research results if available
    research_path = os.path.join(DATA_DIR, "uvg-grid-research-all-nodes.json")
    research_results = None
    if os.path.exists(research_path):
        with open(research_path) as f:
            research_results = json.load(f)
        print(f"  Research results loaded: {research_results.get('total_researched', 0)} nodes")
    else:
        print("  No research results yet (run batch_research_grid_nodes.py first)")

    # Create index
    print("\nCreating OpenSearch index...")
    if not create_index():
        print("Index creation failed. Proceeding anyway (may already exist).")

    # Index nodes
    print("\nIndexing nodes with embeddings...")
    indexed, errors = index_nodes(nodes, research_results)
    print(f"\nDone! Indexed: {indexed}, Errors: {errors}")
    print(f"\nSimilarity queries now available:")
    print(f'  "Find nodes similar to Giza" → k-NN search on embedding')
    print(f'  "Nodes with megalithic construction" → text search on research_text')


if __name__ == "__main__":
    main()
