"""Trigger the ingestion pipeline for the 6 DOJ video files.

This triggers a Step Functions execution with video_processing_mode=full
so Rekognition processes the videos for labels and faces.

Usage:
    python scripts/trigger_video_pipeline.py
"""
import boto3
import json

REGION = "us-east-1"
CASE_ID = "7f05e8d5-4492-4f19-8894-25367606db96"
SFN_ARN = "arn:aws:states:us-east-1:974220725866:stateMachine:research-analyst-ingestion"
BUCKET = "research-analyst-data-lake-974220725866"

VIDEO_FILES = [
    "EFTA01648768.mp4",
    "EFTA01688320.mp4",
    "EFTA01688321.mp4",
    "EFTA01621046.mov",
    "EFTA01621029.mov",
    "EFTA01619633.mov",
]


def main():
    sfn = boto3.client("stepfunctions", region_name=REGION)

    # Build the pipeline input — trigger with video processing enabled
    pipeline_input = {
        "case_id": CASE_ID,
        "s3_bucket": BUCKET,
        "s3_prefix": f"cases/{CASE_ID}/raw/",
        "document_ids": [f.split(".")[0] for f in VIDEO_FILES],
        "effective_config": {
            "rekognition": {
                "enabled": True,
                "video_processing_mode": "full",
                "min_confidence": 70,
                "detect_labels": True,
                "detect_faces": True,
                "detect_text": False,
            },
            "entity_extraction": {"enabled": True},
            "embedding": {"enabled": True},
            "graph_load": {"enabled": True},
        },
    }

    print("=" * 60)
    print("Triggering Video Pipeline")
    print(f"Case: {CASE_ID}")
    print(f"Videos: {len(VIDEO_FILES)}")
    print(f"SFN: {SFN_ARN}")
    print(f"Video mode: full (labels + faces)")
    print("=" * 60)

    try:
        resp = sfn.start_execution(
            stateMachineArn=SFN_ARN,
            name=f"video-processing-{CASE_ID[:8]}",
            input=json.dumps(pipeline_input),
        )
        exec_arn = resp["executionArn"]
        print(f"\nExecution started: {exec_arn}")
        print(f"\nMonitor in AWS Console:")
        print(f"  https://console.aws.amazon.com/states/home?region={REGION}#/executions/details/{exec_arn}")
    except Exception as e:
        print(f"ERROR: {e}")
        if "ExecutionAlreadyExists" in str(e):
            print("An execution with this name already exists. Try again or use a different name.")


if __name__ == "__main__":
    main()
