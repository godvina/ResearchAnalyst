"""Quick check of Epstein Combined case state — entities, graph, documents."""
import urllib.request
import json

API = "https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1"
CASE_ID = "ed0b6c27-3b6b-4255-b9d0-efe8f4383a99"


def check_case():
    url = f"{API}/case-files/{CASE_ID}"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode())
    print("=== Case File ===")
    print(f"  document_count:     {data.get('document_count')}")
    print(f"  entity_count:       {data.get('entity_count')}")
    print(f"  relationship_count: {data.get('relationship_count')}")
    print(f"  status:             {data.get('status')}")
    print(f"  search_tier:        {data.get('search_tier')}")
    print(f"  neptune_label:      {data.get('neptune_subgraph_label')}")


def check_graph():
    """Query Neptune node/edge counts via the patterns endpoint."""
    url = f"{API}/case-files/{CASE_ID}/patterns"
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
        print("\n=== Patterns (graph-derived) ===")
        print(f"  graph_patterns_count:  {data.get('graph_patterns_count', 'N/A')}")
        print(f"  vector_patterns_count: {data.get('vector_patterns_count', 'N/A')}")
        patterns = data.get("patterns", [])
        print(f"  total patterns:        {len(patterns)}")
        for p in patterns[:3]:
            print(f"    - {p.get('pattern_type', '?')}: {p.get('description', '')[:80]}")
    except Exception as exc:
        print(f"\nPatterns error: {exc}")


def check_theories():
    url = f"{API}/case-files/{CASE_ID}/theories"
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
        theories = data if isinstance(data, list) else data.get("theories", [])
        print(f"\n=== Theories ===")
        print(f"  count: {len(theories)}")
        for t in theories[:3]:
            print(f"    - {t.get('title', t.get('name', '?'))[:60]}")
    except Exception as exc:
        print(f"\nTheories error: {exc}")


def check_documents_sample():
    url = f"{API}/case-files/{CASE_ID}/documents?limit=3"
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
        docs = data if isinstance(data, list) else data.get("documents", [])
        print(f"\n=== Documents (sample) ===")
        print(f"  returned: {len(docs)}")
        for d in docs[:3]:
            doc_id = d.get("document_id", d.get("id", "?"))
            title = d.get("title", d.get("filename", ""))[:50]
            has_entities = bool(d.get("entities") or d.get("entity_count"))
            print(f"    - {doc_id[:30]}  title={title}  has_entities={has_entities}")
    except Exception as exc:
        print(f"\nDocuments error: {exc}")


if __name__ == "__main__":
    check_case()
    check_graph()
    check_theories()
    check_documents_sample()
