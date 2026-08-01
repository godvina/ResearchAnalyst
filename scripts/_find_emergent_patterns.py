"""Find emergent patterns via OpenSearch k-NN similarity.

This is the "fuzzy pattern discovery" feature:
- For each node's research embedding, find the most similar OTHER nodes
- Group by similarity that does NOT correspond to existing taxonomy signatures
- Surface the top unexpected clusters as "patterns you didn't search for"

Output: emergent-patterns.json for the dashboard to display.
"""
import boto3
import json
import os
from collections import defaultdict

from requests_aws4auth import AWS4Auth
from opensearchpy import OpenSearch, RequestsHttpConnection

REGION = "us-east-1"
HOST = "hzrvvva3hodw069v9442.us-east-1.aoss.amazonaws.com"
INDEX = "grid-node-research"
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "src", "data")


def get_client():
    session = boto3.Session(region_name=REGION)
    creds = session.get_credentials().get_frozen_credentials()
    auth = AWS4Auth(creds.access_key, creds.secret_key, REGION, 'aoss', session_token=creds.token)
    return OpenSearch(
        hosts=[{'host': HOST, 'port': 443}],
        http_auth=auth, use_ssl=True, verify_certs=True,
        connection_class=RequestsHttpConnection
    )


def get_all_nodes(client):
    """Fetch all 62 nodes with their embeddings and metadata."""
    result = client.search(index=INDEX, body={
        "size": 62,
        "query": {"match_all": {}},
        "_source": ["node_id", "codename", "known_site", "continent",
                    "investigation_status", "research_text", "smoking_gun", "embedding"]
    })
    return [hit["_source"] for hit in result["hits"]["hits"]]


def find_similar(client, embedding, exclude_node_id, k=8):
    """Find k most similar nodes to a given embedding."""
    result = client.search(index=INDEX, body={
        "size": k + 1,
        "query": {
            "knn": {
                "embedding": {
                    "vector": embedding,
                    "k": k + 1
                }
            }
        },
        "_source": ["node_id", "codename", "known_site", "continent", "research_text"]
    })
    neighbors = []
    for hit in result["hits"]["hits"]:
        if hit["_source"].get("node_id") != exclude_node_id:
            neighbors.append({
                "node_id": hit["_source"].get("node_id"),
                "codename": hit["_source"].get("codename", ""),
                "known_site": hit["_source"].get("known_site", ""),
                "score": hit["_score"],
            })
    return neighbors[:k]


def load_scored_findings():
    """Load existing scored findings to know which signatures are already matched."""
    path = os.path.join(DATA_DIR, "uvg-grid-scored-findings.json")
    with open(path) as f:
        return json.load(f)


def detect_emergent_patterns(nodes, scored):
    """Find clusters of similar nodes that don't share taxonomy signatures."""
    client = get_client()
    
    # Build a map of node_id → matched signature IDs
    sig_map = {}
    for r in scored.get("results", []):
        sig_map[r["node_id"]] = set(m["signature_id"] for m in r.get("matches", []))
    
    # For each node, find similar nodes and check if they share NO signatures
    unexpected_pairs = []
    
    for node in nodes:
        if not node.get("embedding"):
            continue
        node_id = node.get("node_id")
        node_sigs = sig_map.get(node_id, set())
        
        neighbors = find_similar(client, node["embedding"], node_id, k=5)
        
        for neighbor in neighbors:
            if neighbor["score"] < 0.7:  # Only high similarity
                continue
            neighbor_sigs = sig_map.get(neighbor["node_id"], set())
            shared_sigs = node_sigs & neighbor_sigs
            
            # EMERGENT = high similarity but NO shared taxonomy signature
            if not shared_sigs and neighbor["score"] >= 0.75:
                unexpected_pairs.append({
                    "node_a": node_id,
                    "node_a_name": node.get("known_site") or node.get("codename", f"Node {node_id}"),
                    "node_b": neighbor["node_id"],
                    "node_b_name": neighbor.get("known_site") or neighbor.get("codename", f"Node {neighbor['node_id']}"),
                    "similarity": round(neighbor["score"], 3),
                    "node_a_sigs": list(node_sigs),
                    "node_b_sigs": list(neighbor_sigs),
                })
    
    # Deduplicate (A→B and B→A)
    seen = set()
    unique_pairs = []
    for p in sorted(unexpected_pairs, key=lambda x: -x["similarity"]):
        key = tuple(sorted([p["node_a"], p["node_b"]]))
        if key not in seen:
            seen.add(key)
            unique_pairs.append(p)
    
    return unique_pairs


def extract_shared_themes(nodes, pairs):
    """For top pairs, extract WHAT they share using text analysis."""
    # Simple keyword extraction from research_text
    node_texts = {n.get("node_id"): n.get("research_text", "") for n in nodes}
    
    for pair in pairs[:10]:
        text_a = node_texts.get(pair["node_a"], "").lower()
        text_b = node_texts.get(pair["node_b"], "").lower()
        
        # Find shared significant words (not stopwords)
        stopwords = {'the','and','for','that','with','this','from','are','was','has','its',
                    'not','but','had','they','been','have','which','were','can','will',
                    'one','all','would','there','their','what','about','when','make',
                    'like','time','very','your','could','than','other','into','more'}
        
        words_a = set(w for w in text_a.split() if len(w) > 4 and w not in stopwords)
        words_b = set(w for w in text_b.split() if len(w) > 4 and w not in stopwords)
        shared = words_a & words_b
        
        # Filter to most interesting shared terms
        interesting = [w for w in shared if w not in {'grid','node','latitude','longitude',
                       'coordinates','located','region','within','ancient','sites'}]
        pair["shared_themes"] = sorted(interesting, key=lambda w: -(text_a.count(w) + text_b.count(w)))[:8]
    
    return pairs


def main():
    print("=" * 60)
    print("  EMERGENT PATTERN DETECTION via OpenSearch k-NN")
    print("=" * 60)
    
    client = get_client()
    print("  Connected to OpenSearch")
    
    # Load data
    nodes = get_all_nodes(client)
    print(f"  Loaded {len(nodes)} nodes with embeddings")
    
    scored = load_scored_findings()
    print(f"  Loaded scored findings ({scored.get('total_with_matches', '?')} with matches)")
    
    # Find emergent patterns
    print("\n  Running k-NN similarity analysis...")
    pairs = detect_emergent_patterns(nodes, scored)
    print(f"  Found {len(pairs)} unexpected similarity pairs")
    
    # Extract shared themes
    pairs = extract_shared_themes(nodes, pairs)
    
    # Display top results
    print("\n  TOP EMERGENT PATTERNS:")
    print("  " + "-" * 56)
    for i, p in enumerate(pairs[:8]):
        themes = ", ".join(p.get("shared_themes", [])[:5])
        print(f"  {i+1}. {p['node_a_name']} ↔ {p['node_b_name']}")
        print(f"     Similarity: {p['similarity']} | Shared themes: {themes}")
        print()
    
    # Save
    output = {
        "analysis_type": "emergent_pattern_detection",
        "method": "OpenSearch k-NN cosine similarity",
        "total_pairs": len(pairs),
        "threshold": 0.75,
        "description": "High-similarity node pairs that share NO taxonomy signatures — potential new patterns",
        "patterns": pairs[:15]
    }
    
    output_path = os.path.join(DATA_DIR, "emergent-patterns.json")
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)
    
    print(f"\n  Saved to: {output_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()
