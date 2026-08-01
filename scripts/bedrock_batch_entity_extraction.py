#!/usr/bin/env python3
"""Bedrock Batch Inference for Entity Extraction — 50% cheaper, massively parallel.

Instead of calling invoke_model() 82K times serially (12 days),
this writes all prompts to a JSONL file in S3, submits one batch job,
and Bedrock processes everything internally in ~2-6 hours.

Usage:
    # Step 1: Generate JSONL input from Aurora docs
    python scripts/bedrock_batch_entity_extraction.py generate

    # Step 2: Submit batch job to Bedrock
    python scripts/bedrock_batch_entity_extraction.py submit

    # Step 3: Check job status
    python scripts/bedrock_batch_entity_extraction.py status

    # Step 4: Load results into Aurora
    python scripts/bedrock_batch_entity_extraction.py load
"""
import json
import sys
import time
import uuid
import boto3

CASE_ID = "7f05e8d5-4492-4f19-8894-25367606db96"
LAMBDA_NAME = "ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq"
BUCKET = "research-analyst-data-lake-974220725866"
REGION = "us-east-1"
MODEL_ID = "anthropic.claude-3-haiku-20240307-v1:0"
INPUT_PREFIX = f"batch-inference/entity-extraction/{CASE_ID}/input/"
OUTPUT_PREFIX = f"batch-inference/entity-extraction/{CASE_ID}/output/"
BATCH_SIZE = 50000  # Max records per JSONL file (Bedrock limit)

lam = boto3.client("lambda", region_name=REGION)
s3 = boto3.client("s3", region_name=REGION)
bedrock = boto3.client("bedrock", region_name=REGION)


def invoke_lambda(payload):
    resp = lam.invoke(
        FunctionName=LAMBDA_NAME,
        InvocationType="RequestResponse",
        Payload=json.dumps(payload),
    )
    return json.loads(resp["Payload"].read().decode())


def generate_jsonl():
    """Step 1: Query Aurora for docs missing entities, write JSONL to S3."""
    from db.connection import ConnectionManager
    print(f"Generating JSONL input for case {CASE_ID}...")

    # We can't import db.connection locally — use Lambda to query Aurora
    # Query docs in pages of 5000
    offset = 0
    page_size = 5000
    total_records = 0
    file_num = 0
    lines = []

    while True:
        print(f"  Querying docs offset={offset}...")
        result = invoke_lambda({
            "action": "query_docs_for_batch",
            "case_id": CASE_ID,
            "offset": offset,
            "limit": page_size,
        })

        if "error" in result:
            print(f"  Error: {result['error']}")
            break

        docs = result.get("docs", [])
        if not docs:
            print(f"  No more docs at offset {offset}")
            break

        for doc in docs:
            doc_id = doc["document_id"]
            raw_text = doc.get("raw_text", "")
            if not raw_text or len(raw_text) < 50:
                continue

            text_for_extraction = raw_text[:8000]
            prompt = f"""Extract named entities from this document. Return a JSON array of objects with "name", "type" (person/organization/location/date/financial/event), and "confidence" (0.0-1.0).

Document text:
{text_for_extraction}

Return ONLY a JSON array, no other text."""

            record = {
                "recordId": doc_id,
                "modelInput": {
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 2048,
                    "messages": [{"role": "user", "content": prompt}],
                },
            }
            lines.append(json.dumps(record, ensure_ascii=False))
            total_records += 1

            # Write file every BATCH_SIZE records
            if len(lines) >= BATCH_SIZE:
                key = f"{INPUT_PREFIX}entities_{file_num:04d}.jsonl"
                body = "\n".join(lines)
                s3.put_object(Bucket=BUCKET, Key=key, Body=body.encode("utf-8"))
                print(f"  Wrote {len(lines)} records to s3://{BUCKET}/{key}")
                lines = []
                file_num += 1

        offset += page_size

    # Write remaining lines
    if lines:
        key = f"{INPUT_PREFIX}entities_{file_num:04d}.jsonl"
        body = "\n".join(lines)
        s3.put_object(Bucket=BUCKET, Key=key, Body=body.encode("utf-8"))
        print(f"  Wrote {len(lines)} records to s3://{BUCKET}/{key}")

    print(f"\nTotal: {total_records} records in {file_num + 1} files")
    print(f"S3 location: s3://{BUCKET}/{INPUT_PREFIX}")
    return total_records


def generate_jsonl_direct():
    """Step 1 (alternative): Generate JSONL directly from Aurora via Lambda SQL.
    
    Uses a Lambda action that returns doc IDs and text in pages,
    avoiding the need for a local DB connection.
    """
    print(f"Generating JSONL input for case {CASE_ID}...")
    print("Querying Aurora for docs needing entity extraction...")

    # First get total count
    count_result = invoke_lambda({
        "action": "backfill_entities_count",
        "case_id": CASE_ID,
    })
    total = count_result.get("total_eligible", 0)
    done = count_result.get("has_entities_count", 0)
    remaining = count_result.get("missing_count", 0)
    print(f"  Total docs: {total:,}, Already done: {done:,}, Remaining: {remaining:,}")

    # Query docs in pages using admin SQL
    offset = 0
    page_size = 1000
    total_records = 0
    file_num = 0
    lines = []

    while offset < total:
        # Use a Lambda action to get doc IDs and text
        result = invoke_lambda({
            "action": "get_docs_for_batch_extraction",
            "case_id": CASE_ID,
            "offset": offset,
            "limit": page_size,
        })

        if "error" in result:
            print(f"  Error at offset {offset}: {result['error'][:200]}")
            # Try smaller page
            if page_size > 100:
                page_size = 100
                continue
            break

        docs = result.get("docs", [])
        if not docs:
            break

        for doc in docs:
            doc_id = doc["document_id"]
            raw_text = doc.get("raw_text", "")
            if not raw_text or len(raw_text) < 50:
                continue

            text_for_extraction = raw_text[:8000]
            prompt = f"""Extract named entities from this document. Return a JSON array of objects with "name", "type" (person/organization/location/date/financial/event), and "confidence" (0.0-1.0).

Document text:
{text_for_extraction}

Return ONLY a JSON array, no other text."""

            record = {
                "recordId": doc_id,
                "modelInput": {
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 2048,
                    "messages": [{"role": "user", "content": prompt}],
                },
            }
            lines.append(json.dumps(record, ensure_ascii=False))
            total_records += 1

            if len(lines) >= BATCH_SIZE:
                key = f"{INPUT_PREFIX}entities_{file_num:04d}.jsonl"
                body = "\n".join(lines)
                s3.put_object(Bucket=BUCKET, Key=key, Body=body.encode("utf-8"))
                print(f"  Wrote {len(lines)} records to s3://{BUCKET}/{key}")
                lines = []
                file_num += 1

        print(f"  Processed offset {offset}, {total_records} records so far")
        offset += len(docs)

    if lines:
        key = f"{INPUT_PREFIX}entities_{file_num:04d}.jsonl"
        body = "\n".join(lines)
        s3.put_object(Bucket=BUCKET, Key=key, Body=body.encode("utf-8"))
        print(f"  Wrote {len(lines)} records to s3://{BUCKET}/{key}")

    print(f"\nTotal: {total_records:,} records in {file_num + 1} files")
    print(f"S3 location: s3://{BUCKET}/{INPUT_PREFIX}")
    return total_records


def submit_job():
    """Step 2: Submit batch inference job to Bedrock."""
    # Check if input files exist
    resp = s3.list_objects_v2(Bucket=BUCKET, Prefix=INPUT_PREFIX, MaxKeys=5)
    files = resp.get("Contents", [])
    if not files:
        print(f"No input files found at s3://{BUCKET}/{INPUT_PREFIX}")
        print("Run 'generate' first.")
        return None

    total_size = sum(f["Size"] for f in files)
    print(f"Found {len(files)} input files, total size: {total_size / 1024 / 1024:.1f} MB")

    # Need a role ARN that Bedrock can assume to read/write S3
    # Check if the role exists
    iam = boto3.client("iam", region_name=REGION)
    role_name = "BedrockBatchInferenceRole"
    role_arn = None

    try:
        role = iam.get_role(RoleName=role_name)
        role_arn = role["Role"]["Arn"]
        print(f"Using existing role: {role_arn}")
    except iam.exceptions.NoSuchEntityException:
        print(f"Creating IAM role {role_name}...")
        trust_policy = {
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Principal": {"Service": "bedrock.amazonaws.com"},
                "Action": "sts:AssumeRole",
                "Condition": {
                    "StringEquals": {"aws:SourceAccount": "974220725866"},
                    "ArnEquals": {"aws:SourceArn": f"arn:aws:bedrock:{REGION}:974220725866:model-invocation-job/*"}
                }
            }]
        }
        role = iam.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(trust_policy),
            Description="Allows Bedrock batch inference to read/write S3",
        )
        role_arn = role["Role"]["Arn"]

        # Attach S3 policy
        s3_policy = {
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Action": ["s3:GetObject", "s3:PutObject", "s3:ListBucket"],
                "Resource": [
                    f"arn:aws:s3:::{BUCKET}",
                    f"arn:aws:s3:::{BUCKET}/*",
                ]
            }]
        }
        iam.put_role_policy(
            RoleName=role_name,
            PolicyName="BedrockBatchS3Access",
            PolicyDocument=json.dumps(s3_policy),
        )
        print(f"Created role: {role_arn}")
        print("Waiting 10s for IAM propagation...")
        time.sleep(10)

    # Submit the batch job
    job_name = f"entity-extract-{CASE_ID[:8]}-{int(time.time())}"
    print(f"Submitting batch job: {job_name}")
    print(f"  Model: {MODEL_ID}")
    print(f"  Input: s3://{BUCKET}/{INPUT_PREFIX}")
    print(f"  Output: s3://{BUCKET}/{OUTPUT_PREFIX}")

    try:
        response = bedrock.create_model_invocation_job(
            jobName=job_name,
            modelId=MODEL_ID,
            roleArn=role_arn,
            inputDataConfig={
                "s3InputDataConfig": {
                    "s3Uri": f"s3://{BUCKET}/{INPUT_PREFIX}",
                }
            },
            outputDataConfig={
                "s3OutputDataConfig": {
                    "s3Uri": f"s3://{BUCKET}/{OUTPUT_PREFIX}",
                }
            },
        )
        job_arn = response["jobArn"]
        print(f"\nJob submitted successfully!")
        print(f"  Job ARN: {job_arn}")
        print(f"  Expected completion: 2-6 hours")
        print(f"\nCheck status: python scripts/bedrock_batch_entity_extraction.py status")

        # Save job ARN for status checks
        s3.put_object(
            Bucket=BUCKET,
            Key=f"batch-inference/entity-extraction/{CASE_ID}/job_arn.txt",
            Body=job_arn.encode("utf-8"),
        )
        return job_arn
    except Exception as e:
        print(f"Failed to submit job: {e}")
        return None


def check_status():
    """Step 3: Check batch job status."""
    # Read saved job ARN
    try:
        resp = s3.get_object(
            Bucket=BUCKET,
            Key=f"batch-inference/entity-extraction/{CASE_ID}/job_arn.txt",
        )
        job_arn = resp["Body"].read().decode("utf-8").strip()
    except Exception:
        print("No job ARN found. Run 'submit' first.")
        return None

    # Get job status
    try:
        job = bedrock.get_model_invocation_job(jobIdentifier=job_arn)
        status = job.get("status", "Unknown")
        print(f"Job: {job.get('jobName', 'unknown')}")
        print(f"Status: {status}")
        print(f"Model: {job.get('modelId', 'unknown')}")

        if "inputDataConfig" in job:
            print(f"Input: {job['inputDataConfig'].get('s3InputDataConfig', {}).get('s3Uri', 'unknown')}")
        if "outputDataConfig" in job:
            print(f"Output: {job['outputDataConfig'].get('s3OutputDataConfig', {}).get('s3Uri', 'unknown')}")

        stats = job.get("jobStatistics", {})
        if stats:
            print(f"Input records: {stats.get('inputTokenCount', 'unknown')}")

        if status == "Completed":
            print("\nJob completed! Run 'load' to import results into Aurora.")
        elif status == "Failed":
            print(f"\nJob failed: {job.get('message', 'unknown error')}")
        elif status in ("InProgress", "Submitted"):
            submit_time = job.get("submitTime")
            if submit_time:
                elapsed = time.time() - submit_time.timestamp()
                print(f"Running for: {elapsed/3600:.1f} hours")

        return status
    except Exception as e:
        print(f"Error checking status: {e}")
        return None


def load_results():
    """Step 4: Read batch output from S3, insert entities into Aurora."""
    print(f"Loading batch results for case {CASE_ID}...")

    # List output files
    resp = s3.list_objects_v2(Bucket=BUCKET, Prefix=OUTPUT_PREFIX)
    files = [f for f in resp.get("Contents", []) if f["Key"].endswith(".jsonl.out")]
    if not files:
        print(f"No output files found at s3://{BUCKET}/{OUTPUT_PREFIX}")
        print("Check job status first.")
        return

    print(f"Found {len(files)} output files")

    total_docs = 0
    total_entities = 0
    total_errors = 0

    for f in files:
        key = f["Key"]
        print(f"  Processing {key}...")
        obj = s3.get_object(Bucket=BUCKET, Key=key)
        body = obj["Body"].read().decode("utf-8")

        for line in body.strip().split("\n"):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
                doc_id = record.get("recordId", "")
                output = record.get("modelOutput", {})

                if record.get("error"):
                    total_errors += 1
                    continue

                # Parse the entity extraction response
                content = output.get("content", [{}])
                if isinstance(content, list) and content:
                    text = content[0].get("text", "[]")
                else:
                    text = "[]"

                # Insert entities via Lambda
                result = invoke_lambda({
                    "action": "insert_entities_from_batch",
                    "case_id": CASE_ID,
                    "document_id": doc_id,
                    "entity_json": text,
                })

                if "error" not in result:
                    total_docs += 1
                    total_entities += result.get("entities_inserted", 0)
                else:
                    total_errors += 1

            except Exception as e:
                total_errors += 1

        print(f"    Cumulative: {total_docs} docs, {total_entities} entities, {total_errors} errors")

    print(f"\nLoad complete: {total_docs:,} docs, {total_entities:,} entities, {total_errors} errors")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/bedrock_batch_entity_extraction.py [generate|submit|status|load]")
        sys.exit(1)

    command = sys.argv[1].lower()
    if command == "generate":
        generate_jsonl_direct()
    elif command == "submit":
        submit_job()
    elif command == "status":
        check_status()
    elif command == "load":
        load_results()
    else:
        print(f"Unknown command: {command}")
        print("Use: generate, submit, status, or load")
