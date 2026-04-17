"""Update the Step Functions state machine with the current definition."""
import json
import boto3

SFN_ARN = "arn:aws:states:us-east-1:974220725866:stateMachine:research-analyst-ingestion"

sfn = boto3.client("stepfunctions", region_name="us-east-1")

# Get current definition
resp = sfn.describe_state_machine(stateMachineArn=SFN_ARN)
current_def = json.loads(resp["definition"])

# Find the RekognitionStep and add document_ids parameter
states = current_def.get("States", {})
rek_step = states.get("RekognitionStep", {})
if rek_step:
    params = rek_step.get("Parameters", {})
    if "document_ids.$" not in params:
        params["document_ids.$"] = "$.upload_result.document_ids"
        rek_step["Parameters"] = params
        states["RekognitionStep"] = rek_step
        current_def["States"] = states
        print("Added document_ids parameter to RekognitionStep")
    else:
        print("document_ids already present in RekognitionStep")

    # Update the state machine
    sfn.update_state_machine(
        stateMachineArn=SFN_ARN,
        definition=json.dumps(current_def),
    )
    print("State machine updated successfully")
else:
    print("RekognitionStep not found in state machine definition")
