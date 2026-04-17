"""Add missing key locations to Neptune for Epstein Combined."""
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
    """Extract integer count from Neptune GraphSON response."""
    if result is None:
        return 0
    # Handle raw string that looks like GraphSON
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except Exception:
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

def extract_list(result):
    """Extract list of strings from Neptune GraphSON response."""
    if isinstance(result, dict):
        val = result.get("@value", [])
        if isinstance(val, list):
            return [v.get("@value", v) if isinstance(v, dict) else v for v in val]
    if isinstance(result, list):
        return result
    return []

# Key locations for the Epstein demo
KEY_LOCATIONS = [
    "Marrakesh", "Islip", "Little St. James Island",
    "Palm Beach", "London", "Manhattan", "Virgin Islands",
    "New Mexico", "Santa Fe", "Ohio", "U.S. Virgin Islands",
]

# Check which already exist
print("=== Checking existing key locations ===")
existing = set()
for loc in KEY_LOCATIONS:
    escaped = loc.replace("'", "\\'")
    result = gremlin(f"g.V().hasLabel('{LABEL}').has('canonical_name','{escaped}').count()")
    count = extract_count(result)
    status = "✅" if int(count) > 0 else "❌"
    print(f"  {status} {loc}: {count}")
    if int(count) > 0:
        existing.add(loc)

missing = [loc for loc in KEY_LOCATIONS if loc not in existing]
print(f"\nMissing: {missing}")

if not missing:
    print("All key locations exist!")
else:
    # Add missing location vertices
    print("\n=== Adding missing location vertices ===")
    for loc in missing:
        vid = str(uuid.uuid4())
        escaped = loc.replace("'", "\\'")
        q = (
            f"g.addV('{LABEL}')"
            f".property(id, '{vid}')"
            f".property('canonical_name', '{escaped}')"
            f".property('entity_type', 'location')"
            f".property('confidence', 0.95)"
            f".property('occurrence_count', 5)"
            f".property('case_file_id', '{CASE_ID}')"
        )
        result = gremlin(q)
        if result is not None:
            print(f"  ✅ Added: {loc}")
        else:
            print(f"  ❌ Failed: {loc}")

    # Check which key persons exist
    KEY_PERSONS = ["Jeffrey Epstein", "Ghislaine Maxwell", "Jeffrey E. Epstein"]
    print("\n=== Checking key persons ===")
    existing_persons = []
    for person in KEY_PERSONS:
        result = gremlin(f"g.V().hasLabel('{LABEL}').has('canonical_name','{person}').count()")
        count = extract_count(result)
        if int(count) > 0:
            existing_persons.append(person)
            print(f"  ✅ {person}")
        else:
            print(f"  ❌ {person}")

    # Person→Location connections
    PERSON_LOCATION_MAP = {
        "Jeffrey Epstein": [
            "Marrakesh", "Islip", "Little St. James Island",
            "Palm Beach", "London", "Manhattan", "Virgin Islands",
            "New Mexico", "Santa Fe", "Ohio", "U.S. Virgin Islands",
        ],
        "Jeffrey E. Epstein": [
            "Marrakesh", "Islip", "Little St. James Island",
            "Palm Beach", "London", "Manhattan", "Virgin Islands",
            "New Mexico", "Santa Fe",
        ],
        "Ghislaine Maxwell": [
            "Marrakesh", "London", "Manhattan",
            "Little St. James Island", "Palm Beach", "Virgin Islands",
        ],
    }

    print("\n=== Adding person→location edges ===")
    for person in existing_persons:
        locs_for_person = PERSON_LOCATION_MAP.get(person, [])
        for loc in locs_for_person:
            if loc in missing:
                eid = str(uuid.uuid4())
                escaped_loc = loc.replace("'", "\\'")
                q = (
                    f"g.V().hasLabel('{LABEL}').has('canonical_name','{person}')"
                    f".addE('RELATED_TO')"
                    f".to(g.V().hasLabel('{LABEL}').has('canonical_name','{escaped_loc}'))"
                    f".property(id, '{eid}')"
                    f".property('relationship_type', 'associated_with')"
                    f".property('confidence', 0.9)"
                )
                result = gremlin(q)
                if result is not None:
                    print(f"  ✅ {person} → {loc}")
                else:
                    print(f"  ❌ {person} → {loc}")

    # Also connect existing locations (Paris, New York, Washington) to persons if not already connected
    EXISTING_LOC_CONNECTIONS = {
        "Jeffrey Epstein": ["Paris", "New York", "Washington", "PARIS", "NY"],
        "Ghislaine Maxwell": ["Paris", "New York", "PARIS"],
    }

    print("\n=== Adding edges to existing locations ===")
    for person in existing_persons:
        for loc in EXISTING_LOC_CONNECTIONS.get(person, []):
            # Check if edge already exists
            escaped_loc = loc.replace("'", "\\'")
            result = gremlin(
                f"g.V().hasLabel('{LABEL}').has('canonical_name','{person}')"
                f".outE('RELATED_TO')"
                f".inV().has('canonical_name','{escaped_loc}').count()"
            )
            count = extract_count(result)
            if int(count) > 0:
                print(f"  ⏭️  Edge exists: {person} → {loc}")
            else:
                eid = str(uuid.uuid4())
                q = (
                    f"g.V().hasLabel('{LABEL}').has('canonical_name','{person}')"
                    f".addE('RELATED_TO')"
                    f".to(g.V().hasLabel('{LABEL}').has('canonical_name','{escaped_loc}'))"
                    f".property(id, '{eid}')"
                    f".property('relationship_type', 'associated_with')"
                    f".property('confidence', 0.9)"
                )
                result = gremlin(q)
                if result is not None:
                    print(f"  ✅ {person} → {loc}")
                else:
                    print(f"  ❌ {person} → {loc}")

# Final verification
print("\n=== Final location check ===")
result = gremlin(
    f"g.V().hasLabel('{LABEL}').has('entity_type','location')"
    f".project('n','d').by('canonical_name').by(bothE().count())"
    f".order().by(select('d'),desc).limit(30)"
)
items = extract_list(result)
print(f"Top locations by degree:")
for item in items:
    if isinstance(item, dict):
        name = item.get("n", "?")
        degree = item.get("d", 0)
        if isinstance(degree, dict):
            degree = degree.get("@value", 0)
        print(f"  {name}: {degree} connections")
