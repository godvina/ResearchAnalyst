"""Query for Epstein's most likely clients using KNN search + entity graph."""
import urllib.request
import json
import boto3

API = "https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1"
CASE_ID = "ed0b6c27-3b6b-4255-b9d0-efe8f4383a99"
LAMBDA = "ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq"
lam = boto3.client("lambda", region_name="us-east-1")

# Approach 1: KNN semantic search for "Epstein clients"
print("=== KNN Search: 'Epstein clients associates' ===")
try:
    req = urllib.request.Request(
        f"{API}/case-files/{CASE_ID}/search",
        data=json.dumps({"query": "Jeffrey Epstein clients associates visitors", "limit": 20}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=25) as resp:
        data = json.loads(resp.read().decode())
        results = data.get("results", [])
        print(f"  Found {len(results)} results")
        for r in results[:5]:
            print(f"  - {r.get('source_filename', '?')}: {r.get('raw_text', '')[:150]}")
except Exception as e:
    print(f"  Error: {e}")

# Approach 2: Get all person entities connected to Epstein in Neptune
print("\n=== Neptune: Persons connected to Jeffrey Epstein ===")
r = lam.invoke(
    FunctionName=LAMBDA,
    InvocationType="RequestResponse",
    Payload=json.dumps({
        "action": "gremlin_query",
        "case_id": CASE_ID,
        "query": "g.V().hasLabel('Entity_" + CASE_ID + "').has('canonical_name','Jeffrey Epstein').outE('RELATED_TO').inV().has('entity_type','person').values('canonical_name').limit(50)",
        "timeout": 30,
        "max_result_len": 4000,
    }),
)
d = json.loads(r["Payload"].read().decode())
print(f"  Result: {d.get('result', d.get('error', '?'))[:2000]}")

# Approach 3: Get top person entities by connection count from Aurora
print("\n=== Aurora: Top person entities by occurrence ===")
r = lam.invoke(
    FunctionName=LAMBDA,
    InvocationType="RequestResponse",
    Payload=json.dumps({
        "action": "query_aurora_entities",
        "case_id": CASE_ID,
        "limit": 50,
        "offset": 0,
    }),
)
d = json.loads(r["Payload"].read().decode())
if "entities" in d:
    persons = [e for e in d["entities"] if e["type"] == "person"]
    print(f"  Top persons ({len(persons)}):")
    for p in persons[:30]:
        print(f"    {p['name']}: {p['count']} occurrences")

# Approach 4: Hypothesis test via API
print("\n=== Hypothesis Test: 'Epstein's most likely clients' ===")
try:
    req = urllib.request.Request(
        f"{API}/case-files/{CASE_ID}/ai-hypotheses",
        data=json.dumps({
            "hypothesis": "Based on the evidence, who are Jeffrey Epstein's most likely clients? List all persons who appear to have a client, visitor, or associate relationship with Epstein, ranked by evidence strength.",
        }).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=29) as resp:
        data = json.loads(resp.read().decode())
        print(f"  Status: {resp.status}")
        analysis = data.get("analysis", data.get("result", ""))
        if isinstance(analysis, str):
            print(f"  Analysis: {analysis[:1500]}")
        elif isinstance(analysis, dict):
            for k, v in analysis.items():
                print(f"  {k}: {str(v)[:300]}")
except urllib.request.HTTPError as e:
    print(f"  HTTP {e.code}: {e.read().decode()[:300]}")
except Exception as e:
    print(f"  Error: {e}")
