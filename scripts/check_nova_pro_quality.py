"""Check Nova Pro entity quality — compare to Nova Lite baseline."""
import boto3
import json

LAMBDA_NAME = "ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq"
CASE_ID = "7f05e8d5-4492-4f19-8894-25367606db96"
lam = boto3.client("lambda", region_name="us-east-1")

# Total entities (no filter)
resp = lam.invoke(
    FunctionName=LAMBDA_NAME,
    Payload=json.dumps({
        "action": "query_aurora_entities",
        "case_id": CASE_ID,
        "limit": 1,
        "offset": 0,
    }),
)
data = json.loads(resp["Payload"].read())
total = data.get("total", 0)
print(f"Total distinct entities: {total:,}")

# With occurrence >= 2
resp2 = lam.invoke(
    FunctionName=LAMBDA_NAME,
    Payload=json.dumps({
        "action": "query_aurora_entities",
        "case_id": CASE_ID,
        "limit": 1,
        "offset": 0,
        "min_occurrence": 2,
    }),
)
data2 = json.loads(resp2["Payload"].read())
occ2 = data2.get("total", 0)
print(f"Entities with occurrence >= 2: {occ2:,}")

# With occurrence >= 3
resp3 = lam.invoke(
    FunctionName=LAMBDA_NAME,
    Payload=json.dumps({
        "action": "query_aurora_entities",
        "case_id": CASE_ID,
        "limit": 1,
        "offset": 0,
        "min_occurrence": 3,
    }),
)
data3 = json.loads(resp3["Payload"].read())
occ3 = data3.get("total", 0)
print(f"Entities with occurrence >= 3: {occ3:,}")

# Core types + occurrence >= 2
core = "person,location,organization,financial_amount,account_number,phone_number,email,address,date,event,flight,legal_case,statute,vehicle,role"
resp4 = lam.invoke(
    FunctionName=LAMBDA_NAME,
    Payload=json.dumps({
        "action": "query_aurora_entities",
        "case_id": CASE_ID,
        "limit": 20,
        "offset": 0,
        "min_occurrence": 2,
        "type_filter": core,
    }),
)
data4 = json.loads(resp4["Payload"].read())
core_occ2 = data4.get("total", 0)
print(f"Core types + occurrence >= 2: {core_occ2:,}")

# Show top 20 entities
print(f"\nTop 20 entities (core types, occ >= 2):")
for e in data4.get("entities", []):
    print(f"  {e['type']:20s} count={e['count']:6d}  {e['name'][:50]}")

# Noise ratio
noise = total - occ2
print(f"\n--- QUALITY SUMMARY ---")
print(f"Total entities:     {total:,}")
print(f"Single-occurrence:  {total - occ2:,} ({(total-occ2)/total*100:.0f}% — likely noise)")
print(f"Occurrence >= 2:    {occ2:,} ({occ2/total*100:.0f}%)")
print(f"Core types + occ2:  {core_occ2:,}")
print(f"")
print(f"--- COMPARISON: Nova Lite vs Nova Pro ---")
print(f"Nova Lite total:    248,314")
print(f"Nova Pro total:     {total:,}")
print(f"Nova Lite occ >= 2: 71,163")
print(f"Nova Pro occ >= 2:  {occ2:,}")
