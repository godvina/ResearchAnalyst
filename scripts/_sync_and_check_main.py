"""Sync Neptune entities for Epstein Main and check actual doc counts."""
import boto3
import json
import urllib.request

API = "https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1"
MAIN_ID = "7f05e8d5-4492-4f19-8894-25367606db96"
LAMBDA = "ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq"

# Check current state
print("=== Epstein Main Current State ===")
req = urllib.request.Request(f"{API}/case-files/{MAIN_ID}")
with urllib.request.urlopen(req, timeout=15) as resp:
    data = json.loads(resp.read().decode())
print(f"  topic_name:       {data.get('topic_name')}")
print(f"  document_count:   {data.get('document_count')}")
print(f"  entity_count:     {data.get('entity_count')}")
print(f"  search_tier:      {data.get('search_tier')}")
print(f"  status:           {data.get('status')}")

# List all cases to see what's there
print("\n=== All Cases ===")
req2 = urllib.request.Request(f"{API}/case-files")
with urllib.request.urlopen(req2, timeout=15) as resp:
    cases = json.loads(resp.read().decode())
if isinstance(cases, list):
    for c in cases:
        print(f"  {c.get('topic_name', '?'):40s}  docs={c.get('document_count', '?'):>8}  entities={c.get('entity_count', '?'):>8}  id={c.get('case_id', '?')[:8]}")
elif isinstance(cases, dict) and 'case_files' in cases:
    for c in cases['case_files']:
        print(f"  {c.get('topic_name', '?'):40s}  docs={c.get('document_count', '?'):>8}  entities={c.get('entity_count', '?'):>8}  id={c.get('case_id', '?')[:8]}")

# Kick off entity sync
print("\n=== Syncing Neptune → Aurora for Epstein Main ===")
lam = boto3.client("lambda", region_name="us-east-1")
payload = {"action": "sync_neptune_to_aurora", "case_id": MAIN_ID}
resp = lam.invoke(
    FunctionName=LAMBDA,
    InvocationType="Event",
    Payload=json.dumps(payload),
)
print(f"Sync invoked async: {resp['StatusCode']}")
print("Check logs for completion.")
