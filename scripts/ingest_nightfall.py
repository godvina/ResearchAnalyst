"""Ingest Operation Nightfall docs from S3 into Aurora.

The 9,565 text files already exist in S3 at:
  cases/0b24a307-a674-41b6-8d22-581c4a4aa566/raw/

This script:
1. Lists all .txt files in the S3 raw prefix
2. Registers them in Aurora `documents` table (via Lambda)
3. Triggers entity extraction + embedding in batches via Step Functions

Usage:
    python scripts/ingest_nightfall.py --register     # Step 1: register docs in Aurora
    python scripts/ingest_nightfall.py --ingest       # Step 2: trigger SFN pipeline
    python scripts/ingest_nightfall.py --status       # Check progress
"""
import argparse
import boto3
import json
import time
import uuid

CASE_ID = "0b24a307-a674-41b6-8d22-581c4a4aa566"
BUCKET = "research-analyst-data-lake-974220725866"
RAW_PREFIX = f"cases/{CASE_ID}/raw/"
LAMBDA_NAME = "ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq"
SFN_ARN = "arn:aws:states:us-east-1:974220725866:stateMachine:research-analyst-ingestion"
REGION = "us-east-1"
BATCH_SIZE = 50  # docs per SFN execution
PARALLEL = 10    # concurrent SFN executions

s3 = boto3.client("s3", region_name=REGION)
lam = boto3.client("lambda", region_name=REGION)
sfn = boto3.client("stepfunctions", region_name=REGION)
rds = boto3.client("rds-data", region_name=REGION)

DB_ARN = "arn:aws:rds:us-east-1:974220725866:cluster:researchanalyststack-auroracluster23d869c0-18up0bpmkaco"
SECRET_ARN = "arn:aws:secretsmanager:us-east-1:974220725866:secret:AuroraClusterSecret8E4F2BC8-4zmQsxQuyYQJ-TOjJyL"


def list_s3_files():
    """List all text files in the raw prefix."""
    print(f"Scanning s3://{BUCKET}/{RAW_PREFIX} ...")
    files = []
    token = None
    while True:
        kw = {"Bucket": BUCKET, "Prefix": RAW_PREFIX, "MaxKeys": 1000}
        if token:
            kw["ContinuationToken"] = token
        resp = s3.list_objects_v2(**kw)
        for obj in resp.get("Contents", []):
            key = obj["Key"]
            if key.endswith((".txt", ".pdf")):
                files.append(key)
        if not resp.get("IsTruncated"):
            break
        token = resp["NextContinuationToken"]
        if len(files) % 5000 == 0:
            print(f"  ...{len(files)} files found")
    print(f"  Total: {len(files)} files")
    return files


def register_docs(files):
    """Register documents in Aurora via batch SQL inserts."""
    print(f"\nRegistering {len(files)} documents in Aurora...")
    
    inserted = 0
    skipped = 0
    errors = 0
    batch_size = 100
    
    for i in range(0, len(files), batch_size):
        batch = files[i:i + batch_size]
        values_parts = []
        params = []
        
        for j, key in enumerate(batch):
            filename = key.split("/")[-1]
            doc_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"s3://{BUCKET}/{key}"))
            
            values_parts.append(f"(:id{j}::uuid, :case{j}::uuid, :fn{j}, NOW())")
            params.extend([
                {"name": f"id{j}", "value": {"stringValue": doc_id}},
                {"name": f"case{j}", "value": {"stringValue": CASE_ID}},
                {"name": f"fn{j}", "value": {"stringValue": filename}},
            ])
        
        sql = f"""
            INSERT INTO documents (document_id, case_file_id, source_filename, indexed_at)
            VALUES {', '.join(values_parts)}
            ON CONFLICT (document_id) DO NOTHING
        """
        
        try:
            resp = rds.execute_statement(
                resourceArn=DB_ARN,
                secretArn=SECRET_ARN,
                database="research_analyst",
                sql=sql,
                parameters=params,
            )
            count = resp.get("numberOfRecordsUpdated", 0)
            inserted += count
            skipped += len(batch) - count
        except Exception as e:
            errors += len(batch)
            print(f"  ERROR at batch {i//batch_size}: {e}")
        
        if (i + batch_size) % 1000 == 0 or i + batch_size >= len(files):
            print(f"  Progress: {i + len(batch)}/{len(files)} "
                  f"(inserted: {inserted}, skipped: {skipped}, errors: {errors})")
    
    print(f"\nDone! Inserted: {inserted}, Skipped: {skipped}, Errors: {errors}")
    
    # Update case document_count
    rds.execute_statement(
        resourceArn=DB_ARN,
        secretArn=SECRET_ARN,
        database="research_analyst",
        sql=f"UPDATE case_files SET document_count = {inserted + skipped}, status = 'indexed' WHERE case_id = :cid::uuid",
        parameters=[{"name": "cid", "value": {"stringValue": CASE_ID}}],
    )
    rds.execute_statement(
        resourceArn=DB_ARN,
        secretArn=SECRET_ARN,
        database="research_analyst",
        sql=f"UPDATE matters SET total_documents = {inserted + skipped}, status = 'indexed' WHERE matter_id = :mid::uuid",
        parameters=[{"name": "mid", "value": {"stringValue": CASE_ID}}],
    )
    print(f"  Updated case_files and matters document_count = {inserted + skipped}")
    return inserted


def trigger_ingestion(files):
    """Trigger Step Functions pipeline for embedding + entity extraction."""
    print(f"\nTriggering ingestion pipeline for {len(files)} docs...")
    
    batches = [files[i:i + BATCH_SIZE] for i in range(0, len(files), BATCH_SIZE)]
    print(f"  {len(batches)} SFN executions (batches of {BATCH_SIZE})")
    
    submitted = 0
    errors = 0
    
    for i, batch in enumerate(batches):
        doc_ids = []
        for key in batch:
            filename = key.split("/")[-1]
            doc_id = filename.rsplit(".", 1)[0] if "." in filename else filename
            doc_ids.append(doc_id)
        
        sfn_input = {
            "case_id": CASE_ID,
            "sample_mode": False,
            "upload_result": {
                "document_ids": doc_ids,
                "document_count": len(doc_ids),
            },
        }
        
        try:
            exec_name = f"nightfall-{i:04d}-{int(time.time())}"
            sfn.start_execution(
                stateMachineArn=SFN_ARN,
                name=exec_name,
                input=json.dumps(sfn_input),
            )
            submitted += 1
        except Exception as e:
            errors += 1
            if errors <= 3:
                print(f"  ERROR: {e}")
        
        # Throttle
        if (i + 1) % PARALLEL == 0:
            print(f"  Submitted {submitted}/{len(batches)} (errors: {errors}) — throttling 3s...")
            time.sleep(3)
    
    print(f"\n  Done! Submitted: {submitted}, Errors: {errors}")
    print(f"  Monitor: aws stepfunctions list-executions --state-machine-arn {SFN_ARN} --status-filter RUNNING")


def run_typology():
    """Trigger typology classification via the IPS worker Lambda."""
    print(f"\nTriggering sex trafficking typology classification for Operation Nightfall...")
    print(f"  Case: {CASE_ID}")

    payload = {
        "phase": "typology_classification",
        "case_id": CASE_ID,
        "run_id": f"typology-{int(time.time())}",
    }

    try:
        resp = lam.invoke(
            FunctionName=LAMBDA_NAME,
            InvocationType="RequestResponse",
            Payload=json.dumps({"action": "ips_worker", **payload}).encode(),
        )
        result = json.loads(resp["Payload"].read().decode())
        print(f"\n  Result: {json.dumps(result, indent=2)}")

        if result.get("status") == "completed":
            print(f"\n  ✓ Typology scores stored: {result.get('scores_stored', 0)}")
            print(f"  ✓ Overall score: {result.get('overall_score', 0)}%")
            print(f"  ✓ Dominant pattern: {result.get('dominant_typology', 'unknown')}")
            print(f"  ✓ Flags triggered: {result.get('flags_triggered', 0)}")
        else:
            print(f"\n  ✗ Error: {result.get('error', 'unknown')}")
    except Exception as e:
        print(f"  ERROR: {e}")


def check_status():
    """Check current document count and SFN status."""
    # Check Aurora doc count
    r = rds.execute_statement(
        resourceArn=DB_ARN,
        secretArn=SECRET_ARN,
        database="research_analyst",
        sql="SELECT COUNT(*) FROM documents WHERE case_file_id = :cid::uuid",
        parameters=[{"name": "cid", "value": {"stringValue": CASE_ID}}],
    )
    doc_count = r["records"][0][0].get("longValue", 0)
    
    # Check entity count
    try:
        r2 = rds.execute_statement(
            resourceArn=DB_ARN,
            secretArn=SECRET_ARN,
            database="research_analyst",
            sql="SELECT COUNT(*) FROM entities WHERE case_file_id = :cid::uuid",
            parameters=[{"name": "cid", "value": {"stringValue": CASE_ID}}],
        )
        ent_count = r2["records"][0][0].get("longValue", 0)
    except Exception:
        ent_count = 0
    
    print(f"Operation Nightfall ({CASE_ID[:12]}...)")
    print(f"  Documents in Aurora: {doc_count}")
    print(f"  Entities in Aurora:  {ent_count}")
    
    # Check SFN
    try:
        resp = sfn.list_executions(
            stateMachineArn=SFN_ARN,
            maxResults=20,
            statusFilter="RUNNING",
        )
        running = len(resp.get("executions", []))
        print(f"  SFN executions running: {running}")
    except Exception as e:
        print(f"  Could not check SFN: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--register", action="store_true", help="Register S3 docs in Aurora")
    parser.add_argument("--ingest", action="store_true", help="Trigger SFN pipeline")
    parser.add_argument("--status", action="store_true", help="Check progress")
    parser.add_argument("--typology", action="store_true", help="Trigger typology scoring via IPS")
    parser.add_argument("--all", action="store_true", help="Register + ingest")
    args = parser.parse_args()
    
    if args.status:
        check_status()
    elif args.register or args.all:
        files = list_s3_files()
        register_docs(files)
        if args.all:
            trigger_ingestion(files)
    elif args.ingest:
        files = list_s3_files()
        trigger_ingestion(files)
    elif args.typology:
        run_typology()
    else:
        parser.print_help()
