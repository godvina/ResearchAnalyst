"""Seed the typology-patterns OpenSearch index by invoking a pipeline Lambda.

The Lambda has VPC access to OpenSearch. We invoke ScoreTypology with a
special 'seed_index' action that triggers the seeding logic.
"""
import json
import boto3
import base64

lambda_client = boto3.client("lambda", region_name="us-east-1")

# We'll invoke the ScoreTypology Lambda with a special payload
# that triggers index seeding instead of scoring
payload = {
    "action": "seed_typology_patterns_index"
}

print("Invoking TypologyPipeline-ScoreTypology with seed action...")
print("This will create and populate the typology-patterns OpenSearch index.")
print("May take 30-60 seconds (embedding 264 patterns via Bedrock)...\n")

response = lambda_client.invoke(
    FunctionName="TypologyPipeline-ScoreTypology",
    InvocationType="RequestResponse",
    Payload=json.dumps(payload).encode(),
)

status = response["StatusCode"]
payload_resp = json.loads(response["Payload"].read().decode())

print(f"Status: {status}")
print(f"Response: {json.dumps(payload_resp, indent=2)[:1000]}")

if response.get("FunctionError"):
    print(f"\n⚠️ Lambda error: {response['FunctionError']}")
    # Try to get the error from logs
    if "errorMessage" in payload_resp:
        print(f"   {payload_resp['errorMessage']}")
else:
    print("\n✓ Seed complete (or action not recognized — check Lambda logs)")
