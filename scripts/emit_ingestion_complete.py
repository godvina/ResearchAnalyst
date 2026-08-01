"""Manually emit an 'Ingestion Complete' EventBridge event to trigger the typology pipeline.

Usage:
    python scripts/emit_ingestion_complete.py <case_id>
"""
import json
import sys
import boto3

def emit_ingestion_complete(case_id: str):
    client = boto3.client("events", region_name="us-east-1")
    response = client.put_events(
        Entries=[{
            "Source": "investigative-intelligence.ingestion",
            "DetailType": "Ingestion Complete",
            "Detail": json.dumps({
                "case_id": case_id,
                "status": "completed",
                "document_count": 0,
            }),
        }]
    )
    print(f"EventBridge response: {response}")
    failed = response.get("FailedEntryCount", 0)
    if failed > 0:
        print(f"ERROR: {failed} entries failed")
    else:
        print(f"SUCCESS: Event emitted for case_id={case_id}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/emit_ingestion_complete.py <case_id>")
        sys.exit(1)
    emit_ingestion_complete(sys.argv[1])
