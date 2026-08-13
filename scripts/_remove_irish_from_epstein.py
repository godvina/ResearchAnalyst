"""Remove Irish sacred site nodes from the Epstein case in Neptune."""
import boto3, json, re, time

REGION = "us-east-1"
LAMBDA_NAME = "ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq"
EPSTEIN_CASE_ID = "7f05e8d5-4492-4f19-8894-25367606db96"
LABEL = "Entity_" + EPSTEIN_CASE_ID

lam = boto3.client("lambda", region_name=REGION)

def gremlin(q, timeout=60):
    r = lam.invoke(FunctionName=LAMBDA_NAME, InvocationType="RequestResponse",
        Payload=json.dumps({"action": "gremlin_query", "case_id": EPSTEIN_CASE_ID,
                           "query": q, "timeout": timeout}))
    d = json.loads(r["Payload"].read().decode())
    return d.get("result", d.get("error", ""))

# Count before
result = gremlin(f"g.V().hasLabel('{LABEL}').has('source','irish_sacred_sites').count()")
print(f"Irish nodes in Epstein case: {result}")

# Drop them (nodes + attached edges)
result = gremlin(f"g.V().hasLabel('{LABEL}').has('source','irish_sacred_sites').drop()")
print(f"Dropped: {result}")

# Verify
result = gremlin(f"g.V().hasLabel('{LABEL}').has('source','irish_sacred_sites').count()")
print(f"Remaining: {result}")
print("Done — Irish data removed from Epstein case")
