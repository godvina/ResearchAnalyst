"""Check what entity types Aurora has vs what Neptune had."""
import boto3, json

lam = boto3.client("lambda", region_name="us-east-1")
LAMBDA_NAME = "ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq"
CASE_ID = "7f05e8d5-4492-4f19-8894-25367606db96"

def invoke_lambda(payload):
    r = lam.invoke(FunctionName=LAMBDA_NAME, InvocationType="RequestResponse",
        Payload=json.dumps(payload))
    return json.loads(r["Payload"].read().decode())

# Get a page of Aurora entities to see what types they have
result = invoke_lambda({
    "action": "query_aurora_entities",
    "case_id": CASE_ID,
    "limit": 1000,
    "offset": 0,
})

print(f"Total Aurora entities: {result.get('total', '?')}")
entities = result.get("entities", [])
print(f"Got {len(entities)} in this page")

if entities:
    print(f"\nEntity keys: {list(entities[0].keys())}")
    # Count types
    types = {}
    for e in entities:
        t = e.get("type", e.get("entity_type", "unknown"))
        types[t] = types.get(t, 0) + 1
    print(f"\nTypes in first 1000:")
    for t, c in sorted(types.items(), key=lambda x: -x[1]):
        print(f"  {t}: {c}")

    # Look for 'object', 'other', 'identifier' types
    dropped = ["object", "other", "identifier", "number", "product", "rule"]
    print(f"\nDropped types in Aurora?")
    for d in dropped:
        count = types.get(d, 0)
        print(f"  {d}: {count}")

    # Show a few samples
    print(f"\nSample entities:")
    for e in entities[:5]:
        print(f"  {e.get('name', '?')} | type={e.get('type', '?')} | count={e.get('count', '?')}")
