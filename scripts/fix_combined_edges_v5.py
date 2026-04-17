"""Connect persons to locations using vertex IDs to avoid Neptune traversal timeouts."""
import boto3
import json
import uuid

lam = boto3.client("lambda", region_name="us-east-1")
LAMBDA = "ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq"
CASE_ID = "ed0b6c27-3b6b-4255-b9d0-efe8f4383a99"
LABEL = f"Entity_{CASE_ID}"

def gremlin(query, timeout=120):
    r = lam.invoke(
        FunctionName=LAMBDA,
        InvocationType="RequestResponse",
        Payload=json.dumps({
            "action": "gremlin_query",
            "case_id": CASE_ID,
            "query": query,
            "timeout": timeout,
            "max_result_len": 8000,
        }),
    )
    d = json.loads(r["Payload"].read().decode())
    if "error" in d:
        return None, d["error"][:500]
    return d.get("result"), None

# Step 1: Get vertex IDs for key persons
print("=== Getting vertex IDs for key persons ===")
person_ids = {}
for person in ["Jeffrey Epstein", "Ghislaine Maxwell", "Lesley Groff"]:
    result, err = gremlin(
        f"g.V().hasLabel('{LABEL}').has('canonical_name','{person}').limit(1).id()"
    )
    if err:
        print(f"  ❌ {person}: {err}")
    else:
        print(f"  {person}: {result}")
        # Parse the ID from GraphSON
        raw = result
        if isinstance(raw, str):
            # Try to extract ID from the string representation
            import re
            match = re.search(r"'@value':\s*'([^']+)'", raw)
            if match:
                person_ids[person] = match.group(1)
            elif "'@value': [" in raw:
                # List format
                match = re.search(r"'@value':\s*\['([^']+)'\]", raw)
                if match:
                    person_ids[person] = match.group(1)
            else:
                # Maybe it's just the ID
                person_ids[person] = raw.strip("[]' ")
        elif isinstance(raw, list) and raw:
            person_ids[person] = raw[0]
        elif isinstance(raw, dict):
            val = raw.get("@value", [])
            if isinstance(val, list) and val:
                person_ids[person] = val[0]

print(f"\nPerson IDs found: {person_ids}")

# Step 2: Get vertex IDs for locations
print("\n=== Getting vertex IDs for locations ===")
loc_ids = {}
locations = [
    "Marrakesh", "Islip", "Little St. James Island", "Palm Beach",
    "London", "Manhattan", "Virgin Islands", "U.S. Virgin Islands",
    "New Mexico", "Santa Fe", "Ohio", "Paris", "New York", "PARIS", "NY",
]
for loc in locations:
    escaped = loc.replace("'", "\\'")
    result, err = gremlin(
        f"g.V().hasLabel('{LABEL}').has('canonical_name','{escaped}').limit(1).id()"
    )
    if err:
        print(f"  ❌ {loc}: {err}")
    else:
        raw = result
        if isinstance(raw, str):
            import re
            match = re.search(r"'@value':\s*'([^']+)'", raw)
            if match:
                loc_ids[loc] = match.group(1)
            elif "'@value': [" in raw:
                match = re.search(r"'@value':\s*\['([^']+)'\]", raw)
                if match:
                    loc_ids[loc] = match.group(1)
            else:
                loc_ids[loc] = raw.strip("[]' ")
        elif isinstance(raw, list) and raw:
            loc_ids[loc] = raw[0]
        elif isinstance(raw, dict):
            val = raw.get("@value", [])
            if isinstance(val, list) and val:
                loc_ids[loc] = val[0]
        
        if loc in loc_ids:
            print(f"  ✅ {loc}: {loc_ids[loc]}")
        else:
            print(f"  ⚠️  {loc}: couldn't parse ID from {str(result)[:200]}")

# Step 3: Add edges using vertex IDs
EDGES = [
    ("Jeffrey Epstein", ["Marrakesh", "Islip", "Little St. James Island", "Palm Beach",
                         "London", "Manhattan", "Virgin Islands", "U.S. Virgin Islands",
                         "New Mexico", "Santa Fe", "Ohio"]),
    ("Ghislaine Maxwell", ["Marrakesh", "London", "Manhattan", "Little St. James Island",
                           "Palm Beach", "Virgin Islands"]),
    ("Lesley Groff", ["Manhattan", "Palm Beach"]),
]

print(f"\n=== Adding edges using vertex IDs ===")
success = 0
failed = 0
for person, locs in EDGES:
    pid = person_ids.get(person)
    if not pid:
        print(f"  ⏭️  Skipping {person} (no vertex ID)")
        continue
    for loc in locs:
        lid = loc_ids.get(loc)
        if not lid:
            print(f"  ⏭️  Skipping {person} → {loc} (no vertex ID)")
            continue
        eid = str(uuid.uuid4())
        q = (
            f"g.V('{pid}')"
            f".addE('RELATED_TO')"
            f".to(g.V('{lid}'))"
            f".property(id, '{eid}')"
            f".property('relationship_type', 'associated_with')"
            f".property('confidence', 0.9)"
        )
        result, err = gremlin(q)
        if err:
            print(f"  ❌ {person} → {loc}: {err[:200]}")
            failed += 1
        else:
            print(f"  ✅ {person} → {loc}")
            success += 1

print(f"\nDone: {success} added, {failed} failed")
