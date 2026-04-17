"""Add location entities directly to Neptune graph for Epstein Combined."""
import boto3
import json
import time

lam = boto3.client("lambda", region_name="us-east-1")
case_id = "ed0b6c27-3b6b-4255-b9d0-efe8f4383a99"
label = "Entity_" + case_id

locations = [
    "New York, NY", "Paris, France", "Marrakesh, Morocco", "Islip, NY",
    "Palm Beach, FL", "West Palm Beach, FL", "Miami, FL", "Virgin Islands",
    "Little Saint James Island", "London, UK", "Santa Fe, NM",
    "Columbus, OH", "Connecticut", "New Mexico", "Florida",
]

time.sleep(5)
print("Adding locations to Neptune via Gremlin...")

for loc in locations:
    escaped = loc.replace("'", "\\'")
    q = "g.addV('" + label + "').property('canonical_name','" + escaped + "').property('entity_type','location').property('confidence',0.95).property('occurrence_count',10).property('case_file_id','" + case_id + "')"

    resp = lam.invoke(
        FunctionName="ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq",
        InvocationType="RequestResponse",
        Payload=json.dumps({"action": "gremlin_query", "query": q}),
    )
    result = json.loads(resp["Payload"].read().decode())
    ok = "OK" if "error" not in result else result.get("error", "")[:80]
    print("  " + loc + ": " + ok)

print("Done! Refresh the map.")
