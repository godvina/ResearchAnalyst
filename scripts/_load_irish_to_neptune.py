"""Load Irish sacred sites into Neptune with coordinates + relationships.

Creates nodes for each site with lat/lon for geospatial map,
plus edges showing connections between sites (intervisibility,
cultural links, shared construction techniques, ley lines).
"""
import boto3
import json
import re
import time

REGION = "us-east-1"
LAMBDA_NAME = "ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq"
CASE_ID = "7f05e8d5-4492-4f19-8894-25367606db96"
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


# Load all sites
sites = []
for filename in ["irish_ancient_sites.json", "irish_ancient_sites_continued.json"]:
    path = f"src/data/conspiracy-seed/irish_sacred_sites/{filename}"
    data = json.load(open(path, "r", encoding="utf-8"))
    sites.extend(data.get("sites", data.get("sites_continued", [])))

print(f"Loading {len(sites)} Irish sites into Neptune...")

# Also insert into Aurora with the simple action that works
aurora_entities = []

# Create Neptune nodes
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
    node_id = f"irish_{sid}"
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
    result = gremlin(q)
    print(f"  ✓ {name} ({lat}, {lon})")
    time.sleep(0.05)

    aurora_entities.append({"name": name, "type": "location", "confidence": 0.99})

# Insert Aurora entities
result = invoke_lambda({
    "action": "insert_entities",
    "case_id": CASE_ID,
    "entities": aurora_entities,
})
print(f"\nAurora: inserted {result.get('inserted', 0)} sites")

# Create edges between connected sites
print(f"\nCreating relationship edges...")

SITE_CONNECTIONS = [
    # Boyne Valley cluster (intervisibility)
    ("irl-001", "irl-002", "geographic", "Same valley complex (Brú na Bóinne)"),
    ("irl-001", "irl-003", "geographic", "Complementary solstice alignment (sunrise/sunset)"),
    ("irl-002", "irl-003", "geographic", "Same valley complex"),
    # Tara-Slane-Newgrange visual network
    ("irl-004", "irl-005", "geographic", "Direct intervisibility (16km)"),
    ("irl-004", "irl-001", "geographic", "Ley line alignment Tara-Newgrange"),
    ("irl-005", "irl-001", "geographic", "Overlooking Boyne Valley passage mounds"),
    # Tara-Loughcrew connection
    ("irl-004", "irl-006", "thematic", "Both hilltop ceremonial with passage tombs"),
    # Sligo cluster
    ("irl-009", "irl-010", "geographic", "All Carrowmore tombs oriented toward Knocknarea"),
    ("irl-009", "irl-011", "thematic", "Paired megalithic complexes 30km apart"),
    # Construction technique links
    ("irl-001", "irl-011", "thematic", "Both have roofbox solar mechanism (100km apart)"),
    ("irl-001", "irl-008", "thematic", "Shared corbelled construction technique (3000yr gap)"),
    ("irl-001", "irl-006", "thematic", "Both passage tombs with equinox/solstice alignment"),
    # Astronomical alignment network
    ("irl-001", "irl-013", "thematic", "Both winter solstice aligned (sunrise vs sunset)"),
    ("irl-002", "irl-006", "thematic", "Both equinox aligned"),
    ("irl-011", "irl-003", "thematic", "Summer solstice sunset / winter solstice sunset pair"),
    # Cultural/mythological links
    ("irl-004", "irl-010", "thematic", "Both associated with sovereignty/kingship mythology"),
    ("irl-007", "irl-012", "thematic", "Both Atlantic-facing 'edge of world' sites"),
]

edges_created = 0
for src_id, tgt_id, rtype, description in SITE_CONNECTIONS:
    from_node = node_ids.get(src_id)
    to_node = node_ids.get(tgt_id)
    if not from_node or not to_node:
        continue

    escaped_desc = description.replace("'", "\\'")
    q = (
        f"g.V('{from_node}')"
        f".addE('related_to')"
        f".to(__.V('{to_node}'))"
        f".property('relationship_type', '{rtype}')"
        f".property('description', '{escaped_desc}')"
        f".property('confidence', 0.90)"
        f".property('source', 'irish_sacred_sites')"
    )
    result = gremlin(q)
    edges_created += 1
    time.sleep(0.05)

print(f"  Edges created: {edges_created}")

print(f"\n{'='*60}")
print(f"DONE — Irish sites in Neptune")
print(f"  Nodes: {len(sites)} (with lat/lon for map)")
print(f"  Edges: {edges_created} (connections for graph)")
print(f"  Aurora: {len(aurora_entities)} entities")
print(f"{'='*60}")
