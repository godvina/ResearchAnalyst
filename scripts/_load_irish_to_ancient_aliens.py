"""Load Irish sites into the Ancient Aliens Investigation case."""
import boto3, json, re, time

REGION = "us-east-1"
LAMBDA_NAME = "ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq"
CASE_ID = "d72b81fc-a4e1-4de5-a4d3-8c74a1a7e7f7"  # Ancient Aliens Investigation
LABEL = "Entity_" + CASE_ID

lam = boto3.client("lambda", region_name=REGION)

def invoke_lambda(payload):
    r = lam.invoke(FunctionName=LAMBDA_NAME, InvocationType="RequestResponse",
        Payload=json.dumps(payload))
    return json.loads(r["Payload"].read().decode())

def gremlin(q, timeout=60):
    r = invoke_lambda({"action": "gremlin_query", "case_id": CASE_ID,
                       "query": q, "timeout": timeout})
    return r.get("result", r.get("error", ""))

# Load sites
sites = []
for filename in ["irish_ancient_sites.json", "irish_ancient_sites_continued.json"]:
    path = f"src/data/conspiracy-seed/irish_sacred_sites/{filename}"
    data = json.load(open(path, "r", encoding="utf-8"))
    sites.extend(data.get("sites", data.get("sites_continued", [])))

print(f"Loading {len(sites)} Irish sites into Ancient Aliens case ({CASE_ID[:8]}...)")

# Insert into Aurora
aurora_entities = []
for site in sites:
    aurora_entities.append({"name": site["name"], "type": "location", "confidence": 0.99})
    for mystery in site.get("mysteries", [])[:2]:
        aurora_entities.append({"name": mystery[:255], "type": "theme", "confidence": 0.85})

result = invoke_lambda({
    "action": "insert_entities",
    "case_id": CASE_ID,
    "entities": aurora_entities,
})
print(f"  Aurora: inserted {result.get('inserted', 0)} entities")

# Create Neptune nodes with coordinates
node_ids = {}
for site in sites:
    name = site["name"]
    sid = site["id"]
    lat = site["coordinates"]["lat"]
    lon = site["coordinates"]["lon"]
    category = site.get("category", "")
    county = site.get("county", "")
    age = site.get("age_years", 0)

    escaped_name = name.replace("'", "\\'")
    node_id = f"irish_aa_{sid}"
    node_ids[sid] = node_id

    q = (
        f"g.addV('{LABEL}')"
        f".property(id, '{node_id}')"
        f".property('canonical_name', '{escaped_name}')"
        f".property('entity_type', 'location')"
        f".property('confidence', 0.99)"
        f".property('latitude', {lat})"
        f".property('longitude', {lon})"
        f".property('category', '{category}')"
        f".property('county', '{county}')"
        f".property('age_years', {age})"
        f".property('case_file_id', '{CASE_ID}')"
        f".property('source', 'irish_sacred_sites')"
    )
    gremlin(q)
    print(f"  ✓ {name}")
    time.sleep(0.05)

# Create edges
CONNECTIONS = [
    ("irl-001", "irl-002", "geographic", "Same valley complex (Brú na Bóinne)"),
    ("irl-001", "irl-003", "geographic", "Complementary solstice alignment"),
    ("irl-002", "irl-003", "geographic", "Same valley complex"),
    ("irl-004", "irl-005", "geographic", "Direct intervisibility (16km)"),
    ("irl-004", "irl-001", "geographic", "Ley line alignment Tara-Newgrange"),
    ("irl-009", "irl-010", "geographic", "All tombs oriented toward Knocknarea"),
    ("irl-001", "irl-011", "thematic", "Both have roofbox solar mechanism"),
    ("irl-001", "irl-008", "thematic", "Shared corbelled construction (3000yr gap)"),
    ("irl-001", "irl-006", "thematic", "Both passage tombs with alignment"),
    ("irl-001", "irl-013", "thematic", "Both winter solstice aligned"),
    ("irl-009", "irl-011", "thematic", "Paired megalithic complexes"),
    ("irl-004", "irl-010", "thematic", "Both sovereignty/kingship sites"),
    ("irl-007", "irl-012", "thematic", "Both Atlantic edge-of-world sites"),
]

edges = 0
for src, tgt, rtype, desc in CONNECTIONS:
    from_id = node_ids.get(src)
    to_id = node_ids.get(tgt)
    if from_id and to_id:
        escaped = desc.replace("'", "\\'")
        q = (f"g.V('{from_id}').addE('related_to').to(__.V('{to_id}'))"
             f".property('relationship_type','{rtype}')"
             f".property('description','{escaped}')"
             f".property('source','irish_sacred_sites')")
        gremlin(q)
        edges += 1
        time.sleep(0.05)

print(f"\n  Neptune: {len(sites)} nodes, {edges} edges")
print(f"  Case: Ancient Aliens Investigation")
print(f"  DONE — open the case and check Map tab")
