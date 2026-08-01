#!/usr/bin/env python3
"""EC2 script: Generate JSONL for Bedrock Batch Inference, submit job, wait for completion, load results.

Runs unattended on EC2, self-terminates when done.
"""
import json
import time
import boto3

CASE_ID = "7f05e8d5-4492-4f19-8894-25367606db96"
LAMBDA_NAME = "ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq"
BUCKET = "research-analyst-data-lake-974220725866"
REGION = "us-east-1"
MODEL_ID = "amazon.nova-lite-v1:0"
INPUT_PREFIX = f"batch-inference/entity-extraction/{CASE_ID}/input/"
OUTPUT_PREFIX = f"batch-inference/entity-extraction/{CASE_ID}/output/"
MAX_RECORDS_PER_FILE = 50000

lam = boto3.client("lambda", region_name=REGION)
s3 = boto3.client("s3", region_name=REGION)
bedrock = boto3.client("bedrock", region_name=REGION)
iam = boto3.client("iam", region_name=REGION)


def invoke_lambda(payload):
    resp = lam.invoke(
        FunctionName=LAMBDA_NAME,
        InvocationType="RequestResponse",
        Payload=json.dumps(payload),
    )
    return json.loads(resp["Payload"].read().decode())


# ============================================================
# PHASE 1: Generate JSONL input
# ============================================================
print(f"\n{'='*60}")
print(f"PHASE 1: Generate JSONL for Bedrock Batch Inference")
print(f"Case: {CASE_ID}")
print(f"{'='*60}")

# Clean up any previous input files
resp = s3.list_objects_v2(Bucket=BUCKET, Prefix=INPUT_PREFIX)
for obj in resp.get("Contents", []):
    s3.delete_object(Bucket=BUCKET, Key=obj["Key"])
    print(f"  Deleted old: {obj['Key']}")

offset = 0
page_size = 500  # Keep pages small to avoid Lambda timeout
total_records = 0
file_num = 0
lines = []
start = time.time()

while True:
    try:
        result = invoke_lambda({
            "action": "get_docs_for_batch_extraction",
            "case_id": CASE_ID,
            "offset": offset,
            "limit": page_size,
        })
    except Exception as e:
        print(f"  Error at offset {offset}: {e}")
        time.sleep(5)
        continue

    if "error" in result:
        print(f"  Lambda error at offset {offset}: {result['error'][:200]}")
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

        prompt = f"""Extract named entities from this document. Return a JSON array of objects with "name", "type" (person/organization/location/date/financial/event), and "confidence" (0.0-1.0).

Document text:
{raw_text}

Return ONLY a JSON array, no other text."""

        record = {
            "recordId": doc_id,
            "modelInput": {
                "messages": [{"role": "user", "content": [{"text": prompt}]}],
                "inferenceConfig": {"maxTokens": 2048},
            },
        }
        lines.append(json.dumps(record, ensure_ascii=False))
        total_records += 1

        if len(lines) >= MAX_RECORDS_PER_FILE:
            key = f"{INPUT_PREFIX}entities_{file_num:04d}.jsonl"
            body = "\n".join(lines)
            s3.put_object(Bucket=BUCKET, Key=key, Body=body.encode("utf-8"))
            print(f"  Wrote {len(lines)} records to s3://{BUCKET}/{key}")
            lines = []
            file_num += 1

    offset += len(docs)
    if total_records % 5000 == 0 and total_records > 0:
        elapsed = time.time() - start
        rate = total_records / max(elapsed, 1) * 60
        print(f"  Progress: {total_records:,} records, {rate:.0f}/min, {elapsed/60:.1f} min elapsed")

    time.sleep(0.5)  # Don't hammer Lambda

# Write remaining
if lines:
    key = f"{INPUT_PREFIX}entities_{file_num:04d}.jsonl"
    body = "\n".join(lines)
    s3.put_object(Bucket=BUCKET, Key=key, Body=body.encode("utf-8"))
    print(f"  Wrote {len(lines)} records to s3://{BUCKET}/{key}")

elapsed = time.time() - start
print(f"\nPhase 1 Complete: {total_records:,} records in {file_num + 1} files, {elapsed/60:.1f} min")


# ============================================================
# PHASE 2: Create IAM role and submit batch job
# ============================================================
print(f"\n{'='*60}")
print(f"PHASE 2: Submit Bedrock Batch Inference Job")
print(f"{'='*60}")

if total_records == 0:
    print("No records to process. Exiting.")
    exit(0)

# Ensure IAM role exists
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
    s3_policy = {
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Action": ["s3:GetObject", "s3:PutObject", "s3:ListBucket"],
            "Resource": [f"arn:aws:s3:::{BUCKET}", f"arn:aws:s3:::{BUCKET}/*"]
        }]
    }
    iam.put_role_policy(RoleName=role_name, PolicyName="BedrockBatchS3Access",
                        PolicyDocument=json.dumps(s3_policy))
    print(f"Created role: {role_arn}")
    print("Waiting 15s for IAM propagation...")
    time.sleep(15)

# Submit batch job
job_name = f"entity-extract-{int(time.time())}"
print(f"Submitting job: {job_name}")
print(f"  Model: {MODEL_ID}")
print(f"  Input: s3://{BUCKET}/{INPUT_PREFIX}")
print(f"  Output: s3://{BUCKET}/{OUTPUT_PREFIX}")
print(f"  Records: {total_records:,}")

try:
    response = bedrock.create_model_invocation_job(
        jobName=job_name,
        modelId=MODEL_ID,
        roleArn=role_arn,
        inputDataConfig={"s3InputDataConfig": {"s3Uri": f"s3://{BUCKET}/{INPUT_PREFIX}"}},
        outputDataConfig={"s3OutputDataConfig": {"s3Uri": f"s3://{BUCKET}/{OUTPUT_PREFIX}"}},
    )
    job_arn = response["jobArn"]
    print(f"Job submitted: {job_arn}")
    s3.put_object(Bucket=BUCKET,
                  Key=f"batch-inference/entity-extraction/{CASE_ID}/job_arn.txt",
                  Body=job_arn.encode("utf-8"))
except Exception as e:
    print(f"FAILED to submit job: {e}")
    print("The JSONL files are in S3 — you can submit manually later.")
    exit(1)


# ============================================================
# PHASE 3: Poll for completion
# ============================================================
print(f"\n{'='*60}")
print(f"PHASE 3: Waiting for Bedrock to process {total_records:,} records...")
print(f"{'='*60}")

poll_start = time.time()
while True:
    try:
        job = bedrock.get_model_invocation_job(jobIdentifier=job_arn)
        status = job.get("status", "Unknown")
        elapsed = (time.time() - poll_start) / 3600
        print(f"  Status: {status} ({elapsed:.1f} hours elapsed)")

        if status == "Completed":
            print("Job completed!")
            break
        elif status == "Failed":
            print(f"Job FAILED: {job.get('message', 'unknown')}")
            exit(1)
        elif status in ("Stopping", "Stopped"):
            print("Job was stopped.")
            exit(1)
    except Exception as e:
        print(f"  Poll error: {e}")

    time.sleep(300)  # Check every 5 minutes


# ============================================================
# PHASE 4: Load results into Aurora
# ============================================================
print(f"\n{'='*60}")
print(f"PHASE 4: Loading results into Aurora")
print(f"{'='*60}")

# List output files
resp = s3.list_objects_v2(Bucket=BUCKET, Prefix=OUTPUT_PREFIX)
all_files = resp.get("Contents", [])
output_files = [f for f in all_files if f["Key"].endswith(".jsonl.out")]
print(f"Found {len(output_files)} output files")

total_docs = 0
total_entities = 0
total_errors = 0

for f in output_files:
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

            content = output.get("content", [{}])
            if isinstance(content, list) and content:
                text = content[0].get("text", "[]")
            else:
                text = "[]"

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

            if total_docs % 1000 == 0 and total_docs > 0:
                print(f"    Loaded: {total_docs:,} docs, {total_entities:,} entities")

        except Exception as e:
            total_errors += 1

    time.sleep(0.5)

print(f"\nPhase 4 Complete: {total_docs:,} docs, {total_entities:,} entities, {total_errors} errors")


# ============================================================
# PHASE 5: Refresh stats
# ============================================================
print(f"\n{'='*60}")
print(f"PHASE 5: Refresh Case Stats")
print(f"{'='*60}")

try:
    stats = invoke_lambda({"action": "refresh_case_stats", "case_id": CASE_ID})
    print(f"Stats: docs={stats.get('document_count', '?')}, entities={stats.get('entity_count', '?')}")
except Exception as e:
    print(f"Stats refresh failed: {e}")

overall = time.time() - start
print(f"\n{'='*60}")
print(f"ALL PHASES COMPLETE — {overall/3600:.1f} hours total")
print(f"{'='*60}")
