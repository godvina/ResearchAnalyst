"""Find person entities in Neptune for Epstein Combined and connect them to locations."""
import boto3
import json
import uuid

lam = boto3.client("lambda", region_name="us-east-1")
LAMBDA = "ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq"
CASE_ID = "ed0b6c27-3b6b-4255-b9d0-efe8f4383a99"
LABEL = f"Entity_{CASE_ID}"

def gremlin(query):
    r = lam.invoke(
        FunctionName=LAMBDA,
        InvocationType="RequestResponse",
        Payload=json.dumps({"action": "gremlin_query", "case_id": CASE_ID, "query": query}),
    )
    d = json.loads(r["Payload"].read().decode())
    if "error" in d:
        print(f"  ERROR: {d['error'][:500]}")
        return None
    return d.get("result")

def extract_count(result):
    if result is None:
        return 0
    if isinstance(result, (int, float)):
        return int(result)
    if isinstance(result, dict):
        if "@value" in result:
            return extract_count(result["@value"])
        return 0
    if isinstance(result, list):
        if len(result) > 0:
            return extract_count(result[0])
        return 0
    return 0

# Find top person entities
print("=== Top person entities by degree ===")
result = gremlin(
    f"g.V().hasLabel('{LABEL}').has('entity_type','person')"
    f".project('n','d').by('canonical_name').by(bothE().count())"
    f".order().by(select('d'),desc).limit(30)"
)
if result:
    raw = result
    if isinstance(raw, dict) and "@value" in raw:
        raw = raw["@value"]
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict):
                if "@value" in item:
                    item = item["@value"]
                if isinstance(item, dict):
                    name = item.get("n", "?")
                    degree = item.get("d", 0)
                    if isinstance(degree, dict):
                        degree = degree.get("@value", 0)
                    print(f"  {name}: {degree}")
                elif isinstance(item, list):
                    # GraphSON Map format: alternating key/value
                    d = {}
                    for i in range(0, len(item), 2):
                        k = item[i]
                        v = item[i+1] if i+1 < len(item) else None
                        if isinstance(v, dict) and "@value" in v:
                            v = v["@value"]
                        d[k] = v
                    print(f"  {d.get('n', '?')}: {d.get('d', 0)}")
            else:
                print(f"  {item}")
    else:
        print(f"  Raw: {str(result)[:2000]}")

# Search for Epstein-like names
print("\n=== Searching for Epstein-related person names ===")
result = gremlin(
    f"g.V().hasLabel('{LABEL}').has('entity_type','person')"
    f".has('canonical_name',containing('pstein'))"
    f".values('canonical_name').limit(20)"
)
if result:
    raw = result
    if isinstance(raw, dict) and "@value" in raw:
        raw = raw["@value"]
    print(f"  Epstein matches: {raw}")

# Search for Maxwell
result = gremlin(
    f"g.V().hasLabel('{LABEL}').has('entity_type','person')"
    f".has('canonical_name',containing('axwell'))"
    f".values('canonical_name').limit(20)"
)
if result:
    raw = result
    if isinstance(raw, dict) and "@value" in raw:
        raw = raw["@value"]
    print(f"  Maxwell matches: {raw}")

# Just get all person names
print("\n=== All person entity names ===")
result = gremlin(
    f"g.V().hasLabel('{LABEL}').has('entity_type','person')"
    f".values('canonical_name').limit(100)"
)
if result:
    raw = result
    if isinstance(raw, dict) and "@value" in raw:
        raw = raw["@value"]
    if isinstance(raw, list):
        print(f"  Found {len(raw)} persons:")
        for name in sorted(raw):
            print(f"    - {name}")
    else:
        print(f"  Raw: {str(raw)[:2000]}")
