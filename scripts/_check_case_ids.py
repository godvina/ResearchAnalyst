"""Check case ID mapping between Aurora and Neptune."""
import boto3
import json

lam = boto3.client("lambda", region_name="us-east-1")

def gremlin(query):
    event = {"action": "gremlin_query", "query": query}
    resp = lam.invoke(
        FunctionName="ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq",
        Payload=json.dumps(event),
    )
    return json.loads(resp["Payload"].read())

# Check vertex count for the Neptune label we found
neptune_case = "7f05e8d5-4492-4f19-8894-25367606db96"
print(f"Neptune case label Entity_{neptune_case}:")
r = gremlin(f"g.V().hasLabel('Entity_{neptune_case}').count()")
print(f"  Vertices: {r}")

# Check the demo case too
demo_neptune = "ed0b6c27-3b6b-4255-b9d0-efe8f4383a99"
print(f"\nNeptune demo label Entity_{demo_neptune}:")
r = gremlin(f"g.V().hasLabel('Entity_{demo_neptune}').count()")
print(f"  Vertices: {r}")

# Now check Aurora case_files for parent_case_id
print("\nChecking Aurora case_files for parent_case_id...")
event2 = {
    "action": "refresh_case_stats",
    "case_id": "7f05e8d5-6a7b-4b1c-9c0e-3f4a5b6c7d8e"
}
resp = lam.invoke(
    FunctionName="ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq",
    Payload=json.dumps(event2),
)
print(f"  Refresh stats result: {json.loads(resp['Payload'].read())}")
