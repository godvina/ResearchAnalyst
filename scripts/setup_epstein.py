"""Epstein Files Investigation — Setup and Ingestion Script.

Creates the Epstein master case file, copies Textract output from the
source DOJ bucket into the case's S3 prefix, and triggers the Step
Functions ingestion pipeline.

Usage:
    python scripts/setup_epstein.py
"""
import json
import os
import re
import uuid

import boto3
import requests

API = "https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1"
REGION = "us-east-1"
SOURCE_BUCKET = "doj-cases-974220725866-us-east-1"
DEST_BUCKET = "research-analyst-data-lake-974220725866"
STATE_MACHINE_ARN = "arn:aws:states:us-east-1:974220725866:stateMachine:research-analyst-ingestion"

# Textract output folders to ingest
TEXTRACT_PREFIXES = [
    "textract-output/DataSet1/",
    "textract-output/DataSet2/",
    "textract-output/DataSet3/",
    "textract-output/DataSet4/",
    "textract-output/DataSet5/",
]


def create_case_file():
    """Create the Epstein Files master case."""
    print("1. Creating Epstein Files Investigation case...")
    resp = requests.post(f"{API}/case-files", json={
        "topic_name": "Epstein Files Investigation",
        "description": (
            "Comprehensive analysis of 3,800+ documents from the DOJ Epstein Files "
            "release under the Epstein Files Transparency Act. Extracting entities "
            "(persons, locations, dates, organizations), relationships, and hidden "
            "patterns across court documents, communications, and evidence files."
        ),
    }, timeout=60)
    if resp.status_code in (200, 201):
        data = resp.json()
        case_id = data.get("case_id")
        print(f"  Created: {case_id}")
        return case_id
    print(f"  Error {resp.status_code}: {resp.text[:200]}")
    return None


def list_textract_files(s3):
    """List all Textract output files from the source bucket."""
    all_files = []
    for prefix in TEXTRACT_PREFIXES:
        print(f"  Scanning {prefix}...")
        paginator = s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=SOURCE_BUCKET, Prefix=prefix):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                if key.endswith("/"):
                    continue
                all_files.append(key)
    return all_files


def copy_to_case_prefix(s3, case_id, source_keys):
    """Copy Textract output files to the case's raw/ prefix in the data lake."""
    print(f"\n2. Copying {len(source_keys)} files to case prefix...")
    doc_ids = []
    for i, src_key in enumerate(source_keys):
        doc_id = str(uuid.uuid4())
        # Preserve original filename in the key for traceability
        original_name = src_key.split("/")[-1]
        ext = original_name.rsplit(".", 1)[-1] if "." in original_name else "txt"
        dest_key = f"cases/{case_id}/raw/{doc_id}.{ext}"

        s3.copy_object(
            CopySource={"Bucket": SOURCE_BUCKET, "Key": src_key},
            Bucket=DEST_BUCKET,
            Key=dest_key,
        )
        doc_ids.append(doc_id)

        if (i + 1) % 100 == 0:
            print(f"  Copied {i + 1}/{len(source_keys)}...")

    print(f"  Done — {len(doc_ids)} files copied")
    return doc_ids


def trigger_pipeline(case_id, doc_ids):
    """Trigger the Step Functions ingestion pipeline."""
    print(f"\n3. Triggering ingestion pipeline for {len(doc_ids)} documents...")
    sfn = boto3.client("stepfunctions", region_name=REGION)

    sfn_input = json.dumps({
        "case_id": case_id,
        "upload_result": {
            "document_ids": doc_ids,
            "document_count": len(doc_ids),
        },
    })

    execution = sfn.start_execution(
        stateMachineArn=STATE_MACHINE_ARN,
        name=f"epstein-{case_id[:8]}-{uuid.uuid4().hex[:8]}",
        input=sfn_input,
    )
    print(f"  Execution ARN: {execution['executionArn']}")
    return execution["executionArn"]


def main():
    print("=== Epstein Files Investigation — Setup ===\n")

    # Step 1: Create case
    case_id = create_case_file()
    if not case_id:
        print("Failed to create case file.")
        return

    # Step 2: Copy Textract files to case prefix
    s3 = boto3.client("s3", region_name=REGION)
    source_keys = list_textract_files(s3)
    print(f"\n  Found {len(source_keys)} Textract output files")

    if not source_keys:
        print("No Textract files found. Check source bucket.")
        return

    doc_ids = copy_to_case_prefix(s3, case_id, source_keys)

    # Step 3: Trigger pipeline
    execution_arn = trigger_pipeline(case_id, doc_ids)

    print(f"\n=== Setup Complete ===")
    print(f"Case ID: {case_id}")
    print(f"Documents: {len(doc_ids)}")
    print(f"Pipeline: {execution_arn}")
    print(f"Monitor: AWS Console > Step Functions > research-analyst-ingestion")


if __name__ == "__main__":
    main()
