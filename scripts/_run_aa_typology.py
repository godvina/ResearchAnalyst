"""Trigger the full typology pipeline for the Ancient Aliens case.

This runs extract_subgraph → score_typology for the Ancient Aliens case,
scoring against the newly indexed pattern library signatures.
"""
import boto3
import json
import time

CASE = "d72b81fc-a4e1-4de5-a4d3-8c74a1a7e7f7"
SFN_ARN = "arn:aws:states:us-east-1:974220725866:stateMachine:TypologySubgraphPipeline"

# First clear any stale results for this case
print("Clearing any stale typology results for Ancient Aliens case...")
rds = boto3.client("rds-data", region_name="us-east-1")
C = "arn:aws:rds:us-east-1:974220725866:cluster:researchanalyststack-auroracluster23d869c0-18up0bpmkaco"
S = "arn:aws:secretsmanager:us-east-1:974220725866:secret:AuroraClusterSecret8E4F2BC8-4zmQsxQuyYQJ-TOjJyL"
D = "research_analyst"

rds.execute_statement(resourceArn=C, secretArn=S, database=D,
    sql=f"DELETE FROM typology_precomputed_results WHERE case_id = '{CASE}'")
rds.execute_statement(resourceArn=C, secretArn=S, database=D,
    sql=f"DELETE FROM typology_precomputed_summary WHERE case_id = '{CASE}'")
print("  ✓ Cleared old results")

# Trigger the pipeline
print(f"\nTriggering TypologySubgraphPipeline for Ancient Aliens...")
print(f"  Case: {CASE}")
print(f"  Pipeline: {SFN_ARN.split(':')[-1]}")

sfn = boto3.client("stepfunctions", region_name="us-east-1")
resp = sfn.start_execution(
    stateMachineArn=SFN_ARN,
    input=json.dumps({"case_id": CASE, "trigger_source": "manual_pattern_library_rescore"})
)
exec_arn = resp["executionArn"]
exec_name = exec_arn.split(":")[-1]
print(f"  ✓ Execution started: {exec_name}")

# Poll for completion
print("\nWaiting for pipeline to complete (may take 2-5 minutes)...")
for i in range(60):
    time.sleep(5)
    status_resp = sfn.describe_execution(executionArn=exec_arn)
    status = status_resp["status"]
    if status in ("SUCCEEDED", "FAILED", "TIMED_OUT", "ABORTED"):
        break
    if i % 6 == 0:
        print(f"  ... still running ({(i+1)*5}s elapsed, status: {status})")

print(f"\n{'='*50}")
print(f"Pipeline {status}")

if status == "SUCCEEDED":
    # Check what was scored
    result = rds.execute_statement(resourceArn=C, secretArn=S, database=D,
        sql=f"SELECT typology_module_id, overall_typology_score, match_strength FROM typology_precomputed_summary WHERE case_id = '{CASE}' ORDER BY overall_typology_score DESC")
    rows = result.get("records", [])
    print(f"\nTypology scores for Ancient Aliens case ({len(rows)} modules scored):")
    for row in rows:
        mod = row[0].get("stringValue", "?")
        score = row[1].get("doubleValue", row[1].get("longValue", 0))
        strength = row[2].get("stringValue", "?")
        print(f"  {mod}: {score:.1%} ({strength})")
elif status == "FAILED":
    error = status_resp.get("error", "unknown")
    cause = status_resp.get("cause", "")[:500]
    print(f"  Error: {error}")
    print(f"  Cause: {cause}")
