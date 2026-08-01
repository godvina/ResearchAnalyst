"""Fix the OPENSEARCH_ENDPOINT for all pipeline Lambdas and main Lambda."""
import json
import boto3

lambda_client = boto3.client("lambda", region_name="us-east-1")

CORRECT_ENDPOINT = "https://hzrvvva3hodw069v9442.us-east-1.aoss.amazonaws.com"
CORRECT_COLLECTION_ID = "hzrvvva3hodw069v9442"

LAMBDAS = [
    "TypologyPipeline-ThresholdCheck",
    "TypologyPipeline-AcquireLock",
    "TypologyPipeline-ReleaseLock",
    "TypologyPipeline-ExtractSubgraph",
    "TypologyPipeline-ScoreTypology",
    "TypologyPipeline-BuildSummaryGraph",
    "ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq",
]

for fn in LAMBDAS:
    # Get current env vars
    resp = lambda_client.get_function_configuration(FunctionName=fn)
    env = resp.get("Environment", {}).get("Variables", {})
    
    # Update OpenSearch endpoint
    old_endpoint = env.get("OPENSEARCH_ENDPOINT", "")
    env["OPENSEARCH_ENDPOINT"] = CORRECT_ENDPOINT
    env["OPENSEARCH_COLLECTION_ID"] = CORRECT_COLLECTION_ID
    
    # Update
    lambda_client.update_function_configuration(
        FunctionName=fn,
        Environment={"Variables": env}
    )
    changed = "CHANGED" if old_endpoint != CORRECT_ENDPOINT else "already correct"
    print(f"  ✓ {fn}: {changed} (was: {old_endpoint[:40]}...)")

print(f"\nAll {len(LAMBDAS)} Lambdas updated with correct endpoint: {CORRECT_ENDPOINT}")
