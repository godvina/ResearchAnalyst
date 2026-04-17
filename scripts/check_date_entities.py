"""Check what date entities look like in Aurora — find parseable ones."""
import boto3
import json
import re

lam = boto3.client("lambda", region_name="us-east-1")
LAMBDA = "ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq"
CASE_ID = "ed0b6c27-3b6b-4255-b9d0-efe8f4383a99"

# Get all date entities
r = lam.invoke(
    FunctionName=LAMBDA,
    InvocationType="RequestResponse",
    Payload=json.dumps({"action": "query_aurora_entities", "case_id": CASE_ID, "limit": 5000, "offset": 0}),
)
d = json.loads(r["Payload"].read().decode())
entities = d.get("entities", [])

dates = [e for e in entities if e["type"] in ("date", "event", "DATE", "date_time")]
print(f"Total date/event entities: {len(dates)}")

# Try to find parseable dates
date_pattern = re.compile(r'\b(19|20)\d{2}\b')  # Contains a year 1900-2099
parseable = []
noise = []
for e in dates:
    name = e["name"]
    if date_pattern.search(name):
        parseable.append(e)
    else:
        noise.append(e)

print(f"\nParseable (contain year 19xx/20xx): {len(parseable)}")
for e in sorted(parseable, key=lambda x: -x["count"])[:30]:
    print(f"  [{e['count']}x] {e['name']}")

print(f"\nNoise (no recognizable year): {len(noise)}")
for e in sorted(noise, key=lambda x: -x["count"])[:20]:
    print(f"  [{e['count']}x] {e['name']}")

# Also check event entities
events = [e for e in entities if e["type"] == "event"]
print(f"\nEvent entities: {len(events)}")
for e in sorted(events, key=lambda x: -x["count"])[:20]:
    print(f"  [{e['count']}x] {e['name']}")
