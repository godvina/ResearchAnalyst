"""Check what entity types exist in Aurora for each case."""
import boto3
import json

lam = boto3.client("lambda", region_name="us-east-1")
LAMBDA = "ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq"

for cid, name in [
    ("ed0b6c27-3b6b-4255-b9d0-efe8f4383a99", "Combined"),
    ("7f05e8d5-4492-4f19-8894-25367606db96", "Main"),
]:
    r = lam.invoke(
        FunctionName=LAMBDA,
        InvocationType="RequestResponse",
        Payload=json.dumps({"action": "query_aurora_entities", "case_id": cid, "limit": 5000, "offset": 0}),
    )
    d = json.loads(r["Payload"].read().decode())
    if "entities" in d:
        types = {}
        for e in d["entities"]:
            t = e["type"]
            types[t] = types.get(t, 0) + e["count"]
        total = d["total"]
        print(f"{name}: {total} distinct entities")
        for t, c in sorted(types.items(), key=lambda x: -x[1]):
            print(f"  {t}: {c}")
        # Show sample date entities
        dates = [e for e in d["entities"] if e["type"] in ("date", "event")]
        if dates:
            print(f"  Sample dates: {[e['name'] for e in dates[:10]]}")
        else:
            print("  NO date/event entities found!")
    else:
        print(f"{name}: {d.get('error', 'unknown error')}")
