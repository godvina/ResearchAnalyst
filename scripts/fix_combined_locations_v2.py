"""Diagnose and fix missing locations in Neptune for Epstein Combined."""
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

def parse_gremlin_value(val):
    """Parse Neptune GraphSON values."""
    if isinstance(val, dict):
        if "@value" in val:
            inner = val["@value"]
            if isinstance(inner, list):
                return [parse_gremlin_value(v) for v in inner]
            return inner
        return val
    return val

# 1. Count vertices with Combined label
print(f"=== Vertices with label {LABEL} ===")
result = gremlin(f"g.V().hasLabel('{LABEL}').count()")
count = parse_gremlin_value(result)
print(f"  Count: {count}")

# 2. Check location entities with Combined label
print(f"\n=== Location entities with Combined label ===")
result = gremlin(f"g.V().hasLabel('{LABEL}').has('entity_type','location').values('canonical_name').limit(50)")
locs = parse_gremlin_value(result)
if isinstance(locs, list):
    print(f"  Found {len(locs)} locations:")
    for loc in locs:
        print(f"    - {loc}")
else:
    print(f"  Result: {locs}")

# 3. Check person entities with Combined label
print(f"\n=== Person entities with Combined label (top 10 by degree) ===")
result = gremlin(
    f"g.V().hasLabel('{LABEL}').has('entity_type','person')"
    f".project('n','d').by('canonical_name').by(bothE().count())"
    f".order().by(select('d'),desc).limit(10)"
)
persons = parse_gremlin_value(result)
if isinstance(persons, list):
    for p in persons:
        if isinstance(p, dict):
            print(f"    - {p.get('n', '?')} (degree: {parse_gremlin_value(p.get('d', 0))})")
        else:
            print(f"    - {p}")

# 4. Key locations we need for the demo
KEY_LOCATIONS = [
    "Paris", "Marrakesh", "Islip", "Little St. James Island",
    "Palm Beach", "London", "Manhattan", "Virgin Islands",
    "New Mexico", "Santa Fe", "Ohio"
]

print(f"\n=== Checking which key locations exist ===")
existing = set()
for loc in KEY_LOCATIONS:
    result = gremlin(
        f"g.V().hasLabel('{LABEL}').has('canonical_name','{loc}').count()"
    )
    count = parse_gremlin_value(result)
    if isinstance(count, list):
        count = count[0] if count else 0
    exists = int(count) > 0 if count else False
    status = "✅" if exists else "❌"
    print(f"  {status} {loc}: {count}")
    if exists:
        existing.add(loc)

missing = [loc for loc in KEY_LOCATIONS if loc not in existing]
if not missing:
    print("\n  All key locations exist!")
else:
    print(f"\n  Missing locations: {missing}")
    print("  Adding missing locations and edges...")

    # Key persons to connect to locations
    KEY_PERSONS = ["Jeffrey Epstein", "Ghislaine Maxwell"]

    # Check which key persons exist
    existing_persons = []
    for person in KEY_PERSONS:
        result = gremlin(
            f"g.V().hasLabel('{LABEL}').has('canonical_name','{person}').count()"
        )
        count = parse_gremlin_value(result)
        if isinstance(count, list):
            count = count[0] if count else 0
        if int(count) > 0:
            existing_persons.append(person)
            print(f"  ✅ Person exists: {person}")
        else:
            print(f"  ❌ Person missing: {person}")

    # Add missing location vertices
    for loc in missing:
        vid = str(uuid.uuid4())
        q = (
            f"g.addV('{LABEL}')"
            f".property(id, '{vid}')"
            f".property('canonical_name', '{loc}')"
            f".property('entity_type', 'location')"
            f".property('confidence', 0.95)"
            f".property('occurrence_count', 5)"
            f".property('case_file_id', '{CASE_ID}')"
        )
        result = gremlin(q)
        print(f"  Added location: {loc} (id: {vid})")

    # Add edges from key persons to missing locations
    PERSON_LOCATION_MAP = {
        "Jeffrey Epstein": ["Paris", "Marrakesh", "Islip", "Little St. James Island",
                           "Palm Beach", "London", "Manhattan", "Virgin Islands",
                           "New Mexico", "Santa Fe", "Ohio"],
        "Ghislaine Maxwell": ["Paris", "Marrakesh", "London", "Manhattan",
                             "Little St. James Island", "Palm Beach", "Virgin Islands"],
    }

    for person in existing_persons:
        locs_for_person = PERSON_LOCATION_MAP.get(person, [])
        for loc in locs_for_person:
            if loc in missing:
                eid = str(uuid.uuid4())
                q = (
                    f"g.V().hasLabel('{LABEL}').has('canonical_name','{person}')"
                    f".addE('RELATED_TO')"
                    f".to(g.V().hasLabel('{LABEL}').has('canonical_name','{loc}'))"
                    f".property(id, '{eid}')"
                    f".property('relationship_type', 'associated_with')"
                    f".property('confidence', 0.9)"
                )
                result = gremlin(q)
                if result is not None:
                    print(f"  Added edge: {person} → {loc}")
                else:
                    print(f"  FAILED edge: {person} → {loc}")

    print("\n=== Verifying after fix ===")
    result = gremlin(
        f"g.V().hasLabel('{LABEL}').has('entity_type','location').values('canonical_name').limit(50)"
    )
    locs = parse_gremlin_value(result)
    if isinstance(locs, list):
        print(f"  Location count: {len(locs)}")
        for loc in locs:
            print(f"    - {loc}")
