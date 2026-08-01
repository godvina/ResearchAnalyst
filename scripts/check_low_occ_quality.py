"""Check quality of low-occurrence entities — this is where Nova Pro should shine."""
import boto3
import json

LAMBDA_NAME = "ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq"
CASE_ID = "7f05e8d5-4492-4f19-8894-25367606db96"
lam = boto3.client("lambda", region_name="us-east-1")

# Get entities with occurrence = 1 (the noise zone)
resp = lam.invoke(
    FunctionName=LAMBDA_NAME,
    Payload=json.dumps({
        "action": "query_aurora_entities",
        "case_id": CASE_ID,
        "limit": 50,
        "offset": 0,
        "type_filter": "person",
    }),
)
data = json.loads(resp["Payload"].read())
entities = data.get("entities", [])

# Show the LOWEST occurrence persons (most likely to be noise)
print("Person entities with LOWEST occurrence count (bottom of list):")
resp2 = lam.invoke(
    FunctionName=LAMBDA_NAME,
    Payload=json.dumps({
        "action": "query_aurora_entities",
        "case_id": CASE_ID,
        "limit": 30,
        "offset": 5000,  # Skip to low-occurrence entities
        "type_filter": "person",
    }),
)
data2 = json.loads(resp2["Payload"].read())
total_persons = data2.get("total", 0)
print(f"Total person entities: {total_persons:,}")
for e in data2.get("entities", []):
    name = e["name"]
    count = e["count"]
    # Flag likely noise
    is_noise = len(name) < 3 or name.startswith("_") or name.startswith("[") or not any(c.isalpha() for c in name)
    flag = " ← NOISE" if is_noise else ""
    print(f"  count={count:3d}  {name[:60]}{flag}")

# Also check types distribution
print(f"\nEntity type distribution (all entities):")
for etype in ["person", "location", "organization", "date", "email", "financial_amount", "event", "phone_number", "address", "role", "legal_case", "statute", "flight"]:
    resp3 = lam.invoke(
        FunctionName=LAMBDA_NAME,
        Payload=json.dumps({
            "action": "query_aurora_entities",
            "case_id": CASE_ID,
            "limit": 1,
            "offset": 0,
            "type_filter": etype,
        }),
    )
    d3 = json.loads(resp3["Payload"].read())
    t = d3.get("total", 0)
    # Also get occ >= 2 count
    resp4 = lam.invoke(
        FunctionName=LAMBDA_NAME,
        Payload=json.dumps({
            "action": "query_aurora_entities",
            "case_id": CASE_ID,
            "limit": 1,
            "offset": 0,
            "type_filter": etype,
            "min_occurrence": 2,
        }),
    )
    d4 = json.loads(resp4["Payload"].read())
    t2 = d4.get("total", 0)
    pct = t2/t*100 if t > 0 else 0
    print(f"  {etype:20s}: {t:6,} total, {t2:6,} occ>=2 ({pct:.0f}% quality)")
