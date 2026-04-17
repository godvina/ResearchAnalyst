"""Quick check if Rekognition edges loaded into Neptune."""
import boto3
import json
from botocore.config import Config

lam = boto3.client("lambda", region_name="us-east-1", config=Config(read_timeout=30))

# Check Ghislaine Maxwell - a known Rekognition entity
event = {
    "httpMethod": "POST",
    "pathParameters": {"id": "7f05e8d5-4492-4f19-8894-25367606db96"},
    "body": json.dumps({"entity_name": "Ghislaine Maxwell"}),
    "headers": {},
}
resp = lam.invoke(
    FunctionName="ResearchAnalystStack-PatternsLambda457C2046-toyjGz36d37l",
    InvocationType="RequestResponse",
    Payload=json.dumps(event),
)
result = json.loads(resp["Payload"].read().decode())
body = json.loads(result.get("body", "{}"))

print(f"Entity: {body.get('entity_name', '?')}")
print(f"Level 1 neighbors: {body.get('level1_count', 0)}")
print(f"Level 2 neighbors: {body.get('level2_count', 0)}")
print(f"Total edges: {len(body.get('edges', []))}")
print()
for n in body.get("nodes", [])[:15]:
    level = n.get("level", "?")
    ntype = n.get("type", "?")
    name = n.get("name", "?")
    print(f"  L{level} [{ntype}] {name}")
