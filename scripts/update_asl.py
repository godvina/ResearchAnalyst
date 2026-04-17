"""Update the Step Functions ASL to strip entities from DocumentSuccess."""
import json
import subprocess

# Get current state machine definition
result = subprocess.run(
    ["aws", "stepfunctions", "describe-state-machine",
     "--state-machine-arn", "arn:aws:states:us-east-1:974220725866:stateMachine:research-analyst-ingestion",
     "--region", "us-east-1", "--output", "json"],
    capture_output=True, text=True
)
sm = json.loads(result.stdout)
asl = json.loads(sm["definition"])

# Update DocumentSuccess to strip entities/relationships
ds = asl["States"]["ProcessDocuments"]["Iterator"]["States"]["DocumentSuccess"]
old_params = ds.get("Parameters", {})
ds["Parameters"] = {
    "case_id.$": "$.case_id",
    "document_id.$": "$.document_id",
    "status": "success",
}
print(f"Old params keys: {list(old_params.keys())}")
print(f"New params keys: {list(ds['Parameters'].keys())}")

# Update the state machine
new_def = json.dumps(asl)
update_result = subprocess.run(
    ["aws", "stepfunctions", "update-state-machine",
     "--state-machine-arn", "arn:aws:states:us-east-1:974220725866:stateMachine:research-analyst-ingestion",
     "--definition", new_def,
     "--region", "us-east-1", "--output", "json"],
    capture_output=True, text=True
)
if update_result.returncode == 0:
    print("State machine updated successfully")
else:
    print(f"Error: {update_result.stderr}")
