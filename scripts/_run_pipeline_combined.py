"""Run the typology pipeline for Epstein Combined case."""
import boto3, json

sfn = boto3.client("stepfunctions", region_name="us-east-1")
CASE = "ed0b6c27-3b6b-4255-b9d0-efe8f4383a99"

resp = sfn.start_execution(
    stateMachineArn="arn:aws:states:us-east-1:974220725866:stateMachine:TypologySubgraphPipeline",
    input=json.dumps({"case_id": CASE, "trigger_source": "manual"})
)
print(f"Started pipeline for Epstein Combined: {resp['executionArn'].split(':')[-1]}")
