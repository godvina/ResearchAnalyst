"""Invoke the Rekognition Lambda to reprocess all extracted images for a case."""
import json
import boto3

CASE_ID = "7f05e8d5-4492-4f19-8894-25367606db96"
LAMBDA_NAME = "ResearchAnalystStack-IngestionRekognitionLambdaB88-Y7vnbJlnp6mo"

lam = boto3.client("lambda", region_name="us-east-1")

payload = {
    "case_id": CASE_ID,
    "effective_config": {
        "rekognition": {
            "enabled": True,
            "min_face_confidence": 0.9,
            "min_object_confidence": 0.7,
            "detect_text": False,
            "video_processing_mode": "skip",
        }
    },
}

print(f"Invoking Rekognition Lambda for case {CASE_ID}...")
print(f"This will process all 5,435 extracted images. May take 10-20 minutes.")

resp = lam.invoke(
    FunctionName=LAMBDA_NAME,
    InvocationType="Event",  # async
    Payload=json.dumps(payload),
)

print(f"Status: {resp['StatusCode']}")
print("Lambda invoked asynchronously. Monitor in CloudWatch:")
print(f"  Log group: /aws/lambda/{LAMBDA_NAME}")
print("Check results with:")
print(f"  aws s3 ls s3://research-analyst-data-lake-974220725866/cases/{CASE_ID}/face-crops/ --recursive | Measure-Object -Line")
print(f"  aws s3 ls s3://research-analyst-data-lake-974220725866/cases/{CASE_ID}/rekognition-artifacts/ --recursive")
