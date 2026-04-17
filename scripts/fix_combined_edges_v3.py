"""Connect key persons to new location nodes in Neptune for Epstein Combined."""
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

# Person→Location edges to create
EDGES = [
    # Jeffrey Epstein connections
    ("Jeffrey Epstein", "Marrakesh"),
    ("Jeffrey Epstein", "Islip"),
    ("Jeffrey Epstein", "Little St. James Island"),
    ("Jeffrey Epstein", "Palm Beach"),
    ("Jeffrey Epstein", "London"),
    ("Jeffrey Epstein", "Manhattan"),
    ("Jeffrey Epstein", "Virgin Islands"),
    ("Jeffrey Epstein", "U.S. Virgin Islands"),
    ("Jeffrey Epstein", "New Mexico"),
    ("Jeffrey Epstein", "Santa Fe"),
    ("Jeffrey Epstein", "Ohio"),
    ("Jeffrey Epstein", "Paris"),
    ("Jeffrey Epstein", "New York"),
    ("Jeffrey Epstein", "PARIS"),
    # Ghislaine Maxwell connections
    ("Ghislaine Maxwell", "Marrakesh"),
    ("Ghislaine Maxwell", "London"),
    ("Ghislaine Maxwell", "Manhattan"),
    ("Ghislaine Maxwell", "Little St. James Island"),
    ("Ghislaine Maxwell", "Palm Beach"),
    ("Ghislaine Maxwell", "Virgin Islands"),
    ("Ghislaine Maxwell", "Paris"),
    ("Ghislaine Maxwell", "New York"),
    # Lesley Groff (Epstein's assistant)
    ("Lesley Groff", "Manhattan"),
    ("Lesley Groff", "Palm Beach"),
    ("Lesley Groff", "New York"),
]

print(f"=== Adding {len(EDGES)} person→location edges ===")
success = 0
skipped = 0
failed = 0

for person, loc in EDGES:
    escaped_loc = loc.replace("'", "\\'")
    escaped_person = person.replace("'", "\\'")
    
    # Check if edge already exists
    check_q = (
        f"g.V().hasLabel('{LABEL}').has('canonical_name','{escaped_person}')"
        f".outE('RELATED_TO')"
        f".inV().has('canonical_name','{escaped_loc}').count()"
    )
    result = gremlin(check_q)
    # Parse count
    count = 0
    if result:
        r = result
        while isinstance(r, dict) and "@value" in r:
            r = r["@value"]
        if isinstance(r, list) and r:
            r = r[0]
            while isinstance(r, dict) and "@value" in r:
                r = r["@value"]
            count = int(r) if r else 0
    
    if count > 0:
        print(f"  ⏭️  {person} → {loc} (exists)")
        skipped += 1
        continue
    
    eid = str(uuid.uuid4())
    q = (
        f"g.V().hasLabel('{LABEL}').has('canonical_name','{escaped_person}')"
        f".addE('RELATED_TO')"
        f".to(g.V().hasLabel('{LABEL}').has('canonical_name','{escaped_loc}'))"
        f".property(id, '{eid}')"
        f".property('relationship_type', 'associated_with')"
        f".property('confidence', 0.9)"
    )
    result = gremlin(q)
    if result is not None:
        print(f"  ✅ {person} → {loc}")
        success += 1
    else:
        print(f"  ❌ {person} → {loc}")
        failed += 1

print(f"\nDone: {success} added, {skipped} skipped, {failed} failed")

# Verify: check location degrees
print("\n=== Location degrees after fix ===")
result = gremlin(
    f"g.V().hasLabel('{LABEL}').has('entity_type','location')"
    f".project('n','d').by('canonical_name').by(bothE().count())"
    f".order().by(select('d'),desc).limit(30)"
)
if result:
    raw = result
    while isinstance(raw, dict) and "@value" in raw:
        raw = raw["@value"]
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict) and "@value" in item:
                item = item["@value"]
            if isinstance(item, list):
                # GraphSON Map: alternating key/value
                d = {}
                for i in range(0, len(item), 2):
                    k = item[i]
                    v = item[i+1] if i+1 < len(item) else None
                    while isinstance(v, dict) and "@value" in v:
                        v = v["@value"]
                    d[k] = v
                print(f"  {d.get('n', '?')}: {d.get('d', 0)} connections")
