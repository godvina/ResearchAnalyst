"""Add country property to Irish site nodes in Neptune."""
import boto3, json, time

REGION = "us-east-1"
LAMBDA_NAME = "ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq"
CASE_ID = "d72b81fc-a4e1-4de5-a4d3-8c74a1a7e7f7"

lam = boto3.client("lambda", region_name=REGION)

def gremlin(q):
    r = lam.invoke(FunctionName=LAMBDA_NAME, InvocationType="RequestResponse",
        Payload=json.dumps({"action": "gremlin_query", "case_id": CASE_ID, "query": q, "timeout": 30}))
    return json.loads(r["Payload"].read().decode()).get("result", "")

# Add country=Ireland to all Irish site nodes
result = gremlin("g.V().has('source','irish_sacred_sites').property('country','Ireland').count()")
print(f"Updated nodes with country=Ireland: {result}")

# Also add region property for grouping
sites_by_region = {
    "irish_aa_irl-001": "Boyne Valley",
    "irish_aa_irl-002": "Boyne Valley",
    "irish_aa_irl-003": "Boyne Valley",
    "irish_aa_irl-004": "Boyne Valley",
    "irish_aa_irl-005": "Boyne Valley",
    "irish_aa_irl-006": "Boyne Valley",
    "irish_aa_irl-007": "The Burren",
    "irish_aa_irl-008": "Kerry Coast",
    "irish_aa_irl-009": "Sligo",
    "irish_aa_irl-010": "Sligo",
    "irish_aa_irl-011": "Sligo",
    "irish_aa_irl-012": "Aran Islands",
    "irish_aa_irl-013": "West Cork",
}

for node_id, region in sites_by_region.items():
    gremlin(f"g.V('{node_id}').property('region','{region}')")
    time.sleep(0.05)

print(f"Added region tags to {len(sites_by_region)} sites")
print("\nRegions: Boyne Valley, The Burren, Kerry Coast, Sligo, Aran Islands, West Cork")
print("\nFor filtering: use g.V().has('country','Ireland') or g.V().has('region','Sligo')")
