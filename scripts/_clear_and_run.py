"""Clear old results and start fresh pipeline run."""
import boto3, subprocess
client = boto3.client("rds-data", region_name="us-east-1")
C = "arn:aws:rds:us-east-1:974220725866:cluster:researchanalyststack-auroracluster23d869c0-18up0bpmkaco"
S = "arn:aws:secretsmanager:us-east-1:974220725866:secret:AuroraClusterSecret8E4F2BC8-4zmQsxQuyYQJ-TOjJyL"
D = "research_analyst"
CASE = "7f05e8d5-4492-4f19-8894-25367606db96"

client.execute_statement(resourceArn=C, secretArn=S, database=D, sql=f"DELETE FROM typology_precomputed_results WHERE case_id = '{CASE}'")
client.execute_statement(resourceArn=C, secretArn=S, database=D, sql=f"DELETE FROM typology_precomputed_summary WHERE case_id = '{CASE}'")
client.execute_statement(resourceArn=C, secretArn=S, database=D, sql=f"DELETE FROM pipeline_executions WHERE case_id = '{CASE}'")
print("Cleared old results. Starting pipeline...")

sfn = boto3.client("stepfunctions", region_name="us-east-1")
resp = sfn.start_execution(
    stateMachineArn="arn:aws:states:us-east-1:974220725866:stateMachine:TypologySubgraphPipeline",
    input=f'{{"case_id":"{CASE}","trigger_source":"manual"}}'
)
print(f"Execution: {resp['executionArn'].split(':')[-1]}")
