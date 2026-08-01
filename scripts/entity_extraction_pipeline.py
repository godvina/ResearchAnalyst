#!/usr/bin/env python3
"""
Entity Extraction Pipeline — Production-Grade Bedrock Batch Inference

This script is the canonical entity extraction pipeline for the Investigative
Intelligence Platform. It reads document text from Aurora, generates JSONL
prompts using a constrained entity taxonomy, submits a Bedrock Batch Inference
job, and loads results back into Aurora.

DESIGNED FOR HANDOFF: This code will be passed to an AWS team to build as an
AWS service, then to customers. Document everything. No shortcuts.

Architecture:
    Aurora (documents table) → JSONL generation → S3 → Bedrock Batch Inference
    → S3 output → Aurora (entities table) → Neptune (graph sync)

Prerequisites:
    - Aurora `documents` table populated with document text
    - S3 bucket with write access
    - Bedrock model access for the chosen model
    - IAM role for Bedrock batch inference (BedrockBatchInferenceRole)
    - docs/master-entity-taxonomy.md reviewed for case type

Usage:
    # Step 1: Run model bake-off (MANDATORY for new datasets)
    python scripts/model_bakeoff.py --case-id <CASE_ID>

    # Step 2: Generate JSONL prompts
    python scripts/entity_extraction_pipeline.py generate --case-id <CASE_ID>

    # Step 3: Submit batch job
    python scripts/entity_extraction_pipeline.py submit --case-id <CASE_ID>

    # Step 4: Check status
    python scripts/entity_extraction_pipeline.py status --job-arn <ARN>

    # Step 5: Load results into Aurora
    python scripts/entity_extraction_pipeline.py load --case-id <CASE_ID> --job-arn <ARN>

    # Step 6: Sync to Neptune (separate script)
    python scripts/ec2_neptune_resync.py --case-id <CASE_ID>

Configuration:
    Edit the CONFIG section below or pass --model, --case-id, --bucket args.

Reference:
    - docs/master-entity-taxonomy.md — entity type definitions
    - docs/lessons-learned.md — Issue 46-49 (batch inference lessons)
    - .kiro/steering/entity-extraction-rules.md — extraction rules
"""
import argparse
import boto3
import json
import os
import sys
import time
import uuid
from datetime import datetime

# ═══════════════════════════════════════════════════════════════════
# CONFIGURATION — Edit these for your environment
# ═══════════════════════════════════════════════════════════════════

CONFIG = {
    # AWS
    "region": "us-east-1",
    "bucket": "research-analyst-data-lake-974220725866",
    "lambda_name": "ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq",
    "batch_role_arn": "arn:aws:iam::974220725866:role/BedrockBatchInferenceRole",
    
    # Model — CHANGE THIS based on bake-off results
    # Run `python scripts/model_bakeoff.py` first!
    "model_id": "amazon.nova-pro-v1:0",
    "model_format": "nova",  # "nova" or "anthropic"
    "max_tokens": 4096,
    
    # S3 paths
    "s3_prefix": "batch-inference/entity-extraction",
    
    # Processing
    "page_size": 500,         # Documents per Aurora query page (keep small — full text is large)
    "max_text_length": 8000,  # Max chars per document sent to model
    "min_text_length": 50,    # Skip documents shorter than this
}

# ═══════════════════════════════════════════════════════════════════
# ENTITY EXTRACTION PROMPT — Constrained to Master Taxonomy
# Reference: docs/master-entity-taxonomy.md
# ═══════════════════════════════════════════════════════════════════

EXTRACTION_PROMPT = """You are an expert investigative analyst extracting named entities from legal and financial documents. Extract entities with high precision — only extract entities you are confident about.

Return a JSON array of objects. Each object has:
- "name": the entity's canonical name (full name, not abbreviations)
- "type": one of the types listed below
- "confidence": 0.0 to 1.0

ENTITY TYPES TO EXTRACT (extract ONLY these):

TIER 1 — Core (always extract):
- person: Full names of people (suspects, witnesses, victims, associates, attorneys, judges)
- organization: Companies, banks, law firms, foundations, government agencies, nonprofits
- location: Cities, countries, states, specific addresses, properties, venues, airports
- event: Meetings, transactions, arrests, court hearings, filings, raids, seizures

TIER 2 — Financial (critical for following the money):
- financial_amount: Dollar amounts, transaction values (e.g., "$50,000", "€1.2 million")
- account_number: Bank account numbers, wire transfer IDs, routing numbers, SWIFT codes

TIER 3 — Communication (proves coordination):
- phone_number: Telephone numbers with area codes (e.g., "(212) 350-0099")
- email: Email addresses (e.g., "name@domain.com")
- address: Physical street addresses (e.g., "358 El Brillo Way, Palm Beach, FL")

TIER 4 — Travel (proves movement):
- flight: Flight numbers, aircraft tail numbers (e.g., "N908JE", "Flight AA1234")
- vehicle: Vehicles with identifying info (make, model, plate, VIN)

TIER 5 — Legal:
- legal_case: Case numbers (e.g., "Case 1:20-cr-00330-PAE")
- statute: Laws and regulations cited (e.g., "18 U.S.C. § 1591")

TIER 6 — Context:
- role: Job titles and organizational roles (e.g., "pilot", "personal assistant", "masseuse")
- date: Specific dates (e.g., "January 22, 2002", "March 2005")

DO NOT EXTRACT:
- Page numbers, headers, footers, or document formatting
- OCR artifacts (random characters, symbols, underscores)
- Generic descriptions (colors, sizes, measurements, weights)
- Medical terms, food items, clothing, music, animals
- Single words that aren't proper nouns
- Numbers that aren't account numbers, phone numbers, or financial amounts

Return ONLY valid JSON. No explanation, no markdown, just the array.
If no entities are found, return an empty array: []

Document text:
---
{text}
---"""


# ═══════════════════════════════════════════════════════════════════
# CLIENTS
# ═══════════════════════════════════════════════════════════════════

def get_clients():
    region = CONFIG["region"]
    return {
        "bedrock": boto3.client("bedrock", region_name=region),
        "s3": boto3.client("s3", region_name=region),
        "lambda": boto3.client("lambda", region_name=region),
    }


def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


# ═══════════════════════════════════════════════════════════════════
# STEP 1: GENERATE JSONL
# ═══════════════════════════════════════════════════════════════════

def cmd_generate(args):
    """Generate JSONL prompts from Aurora document text."""
    case_id = args.case_id
    clients = get_clients()
    lam = clients["lambda"]
    s3 = clients["s3"]
    
    log("=" * 60)
    log(f"GENERATE JSONL — Case: {case_id}")
    log(f"Model: {CONFIG['model_id']}")
    log("=" * 60)
    
    # Get total document count
    resp = lam.invoke(
        FunctionName=CONFIG["lambda_name"],
        Payload=json.dumps({
            "action": "query_aurora_entities",
            "case_id": case_id,
            "limit": 1,
            "offset": 0,
        }),
    )
    # We need documents, not entities. Use a different query.
    # For now, count documents directly
    dataset_filter = getattr(args, "dataset_filter", None)
    if dataset_filter:
        log(f"Dataset filter: {dataset_filter} (only docs with source_metadata.dataset = '{dataset_filter}')")
    else:
        log("Dataset filter: NONE (all documents in case)")
    
    log("Querying Aurora for documents with text...")
    
    s3_prefix = f"{CONFIG['s3_prefix']}/{case_id}/input-v2"
    bucket = CONFIG["bucket"]
    
    # Paginate through documents
    offset = 0
    total_records = 0
    total_skipped = 0
    jsonl_buffer = []
    file_index = 0
    
    while True:
        # Get documents from Aurora via Lambda
        payload = {
            "action": "get_documents_for_extraction",
            "case_id": case_id,
            "limit": CONFIG["page_size"],
            "offset": offset,
            "min_text_length": CONFIG["min_text_length"],
        }
        if dataset_filter:
            payload["dataset_filter"] = dataset_filter
        resp = lam.invoke(
            FunctionName=CONFIG["lambda_name"],
            Payload=json.dumps(payload),
        )
        result = json.loads(resp["Payload"].read())
        documents = result.get("docs", [])
        
        if offset == 0:
            total_available = result.get("total", 0)
            log(f"Total documents with text: {total_available:,}")
        
        if not documents:
            if offset == 0:
                log("ERROR: No documents found. Check case_id and documents table.")
                log("The documents table must have raw_text populated.")
            break
        
        for doc in documents:
            doc_id = doc.get("document_id", "")
            raw_text = doc.get("raw_text", "")
            
            if not raw_text or len(raw_text) < CONFIG["min_text_length"]:
                total_skipped += 1
                continue
            
            # Truncate to max length
            text = raw_text[:CONFIG["max_text_length"]]
            prompt = EXTRACTION_PROMPT.replace("{text}", text)
            
            # Build model input based on format
            if CONFIG["model_format"] == "nova":
                model_input = {
                    "messages": [{"role": "user", "content": [{"text": prompt}]}],
                    "inferenceConfig": {"maxTokens": CONFIG["max_tokens"]},
                }
            else:  # anthropic
                model_input = {
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": CONFIG["max_tokens"],
                    "messages": [{"role": "user", "content": prompt}],
                }
            
            record = {
                "recordId": doc_id,
                "modelInput": model_input,
            }
            jsonl_buffer.append(json.dumps(record))
            total_records += 1
        
        # Write JSONL file every 10K records (Bedrock has file size limits)
        if len(jsonl_buffer) >= 10000:
            key = f"{s3_prefix}/batch_{file_index:04d}.jsonl"
            s3.put_object(
                Bucket=bucket,
                Key=key,
                Body="\n".join(jsonl_buffer).encode("utf-8"),
            )
            log(f"  Wrote {len(jsonl_buffer)} records to s3://{bucket}/{key}")
            jsonl_buffer = []
            file_index += 1
        
        offset += CONFIG["page_size"]
        log(f"  Processed {offset} documents, {total_records} records generated, {total_skipped} skipped")
    
    # Write remaining records
    if jsonl_buffer:
        key = f"{s3_prefix}/batch_{file_index:04d}.jsonl"
        s3.put_object(
            Bucket=bucket,
            Key=key,
            Body="\n".join(jsonl_buffer).encode("utf-8"),
        )
        log(f"  Wrote {len(jsonl_buffer)} records to s3://{bucket}/{key}")
    
    log(f"\nGENERATE COMPLETE")
    log(f"  Total records: {total_records:,}")
    log(f"  Skipped (too short): {total_skipped:,}")
    log(f"  JSONL files: {file_index + 1}")
    log(f"  S3 location: s3://{bucket}/{s3_prefix}/")
    log(f"\nNext step: python scripts/entity_extraction_pipeline.py submit --case-id {case_id}")


# ═══════════════════════════════════════════════════════════════════
# STEP 2: SUBMIT BATCH JOB
# ═══════════════════════════════════════════════════════════════════

def cmd_submit(args):
    """Submit Bedrock Batch Inference job."""
    case_id = args.case_id
    clients = get_clients()
    bedrock = clients["bedrock"]
    
    bucket = CONFIG["bucket"]
    input_prefix = f"{CONFIG['s3_prefix']}/{case_id}/input-v2/"
    output_prefix = f"{CONFIG['s3_prefix']}/{case_id}/output-v2/"
    
    log("=" * 60)
    log(f"SUBMIT BATCH JOB — Case: {case_id}")
    log(f"Model: {CONFIG['model_id']}")
    log(f"Input: s3://{bucket}/{input_prefix}")
    log(f"Output: s3://{bucket}/{output_prefix}")
    log("=" * 60)
    
    job_name = f"entity-extract-{case_id[:8]}-{datetime.now().strftime('%Y%m%d-%H%M')}"
    
    try:
        response = bedrock.create_model_invocation_job(
            jobName=job_name,
            modelId=CONFIG["model_id"],
            roleArn=CONFIG["batch_role_arn"],
            inputDataConfig={
                "s3InputDataConfig": {
                    "s3Uri": f"s3://{bucket}/{input_prefix}",
                    "s3InputFormat": "JSONL",
                }
            },
            outputDataConfig={
                "s3OutputDataConfig": {
                    "s3Uri": f"s3://{bucket}/{output_prefix}",
                }
            },
        )
        
        job_arn = response["jobArn"]
        log(f"\nBatch job submitted successfully!")
        log(f"  Job ARN: {job_arn}")
        log(f"  Job name: {job_name}")
        log(f"\nNext step: python scripts/entity_extraction_pipeline.py status --job-arn {job_arn}")
        
        # Save job ARN for later
        with open(f"docs/batch-job-{case_id[:8]}.txt", "w") as f:
            f.write(f"Job ARN: {job_arn}\n")
            f.write(f"Job Name: {job_name}\n")
            f.write(f"Model: {CONFIG['model_id']}\n")
            f.write(f"Case: {case_id}\n")
            f.write(f"Submitted: {datetime.now().isoformat()}\n")
        
    except Exception as e:
        log(f"ERROR: {str(e)[:500]}")
        log("\nCommon issues:")
        log("  - Model not available for batch: try a different model")
        log("  - IAM role missing: check BedrockBatchInferenceRole exists")
        log("  - S3 access denied: check role has s3:GetObject and s3:PutObject")
        sys.exit(1)


# ═══════════════════════════════════════════════════════════════════
# STEP 3: CHECK STATUS
# ═══════════════════════════════════════════════════════════════════

def cmd_status(args):
    """Check Bedrock Batch Inference job status."""
    clients = get_clients()
    bedrock = clients["bedrock"]
    
    job_arn = args.job_arn
    
    try:
        response = bedrock.get_model_invocation_job(jobIdentifier=job_arn)
        status = response.get("status", "UNKNOWN")
        
        log(f"Job: {job_arn}")
        log(f"Status: {status}")
        log(f"Model: {response.get('modelId', '?')}")
        
        if "submitTime" in response:
            log(f"Submitted: {response['submitTime']}")
        if "endTime" in response:
            log(f"Completed: {response['endTime']}")
        if "message" in response:
            log(f"Message: {response['message']}")
        
        stats = response.get("statistics", {})
        if stats:
            log(f"Input records: {stats.get('inputRecordCount', '?')}")
            log(f"Output records: {stats.get('outputRecordCount', '?')}")
            log(f"Error records: {stats.get('errorRecordCount', '?')}")
        
        if status == "Completed":
            output_uri = response.get("outputDataConfig", {}).get("s3OutputDataConfig", {}).get("s3Uri", "")
            log(f"\nOutput: {output_uri}")
            log(f"\nNext step: python scripts/entity_extraction_pipeline.py load --case-id <CASE_ID> --job-arn {job_arn}")
        elif status == "Failed":
            log(f"\nJob FAILED. Check the error message above.")
            log("Common causes: model format mismatch, IAM permissions, S3 access")
        else:
            log(f"\nJob still running. Check again in a few minutes.")
            
    except Exception as e:
        log(f"ERROR: {str(e)[:500]}")


# ═══════════════════════════════════════════════════════════════════
# STEP 4: LOAD RESULTS
# ═══════════════════════════════════════════════════════════════════

def cmd_load(args):
    """Load Bedrock Batch results into Aurora entities table."""
    case_id = args.case_id
    clients = get_clients()
    s3 = clients["s3"]
    lam = clients["lambda"]
    
    bucket = CONFIG["bucket"]
    output_prefix = f"{CONFIG['s3_prefix']}/{case_id}/output-v2/"
    
    log("=" * 60)
    log(f"LOAD RESULTS — Case: {case_id}")
    log(f"Source: s3://{bucket}/{output_prefix}")
    log("=" * 60)
    
    # List output files
    paginator = s3.get_paginator("list_objects_v2")
    output_files = []
    for page in paginator.paginate(Bucket=bucket, Prefix=output_prefix):
        for obj in page.get("Contents", []):
            if obj["Key"].endswith(".jsonl.out"):
                output_files.append(obj["Key"])
    
    if not output_files:
        log("ERROR: No output files found. Check job status and output prefix.")
        sys.exit(1)
    
    log(f"Found {len(output_files)} output files")
    
    total_docs = 0
    total_entities = 0
    total_errors = 0
    batch_buffer = []
    BATCH_SIZE = 50  # Entities per Lambda call
    
    import re
    
    for file_key in output_files:
        log(f"Processing {file_key}...")
        obj = s3.get_object(Bucket=bucket, Key=file_key)
        content = obj["Body"].read().decode("utf-8")
        
        for line in content.strip().split("\n"):
            if not line.strip():
                continue
            
            try:
                record = json.loads(line)
                doc_id = record.get("recordId", "")
                model_output = record.get("modelOutput", {})
                
                # Extract text from model output
                if CONFIG["model_format"] == "nova":
                    text_out = (model_output.get("output", {})
                               .get("message", {})
                               .get("content", [{}])[0]
                               .get("text", ""))
                else:
                    text_out = (model_output.get("content", [{}])[0]
                               .get("text", ""))
                
                if not text_out:
                    # Check for error
                    error = record.get("error", {}).get("message", "")
                    if error:
                        total_errors += 1
                        continue
                
                # Parse entities from JSON
                entities = []
                try:
                    match = re.search(r'\[.*\]', text_out, re.DOTALL)
                    if match:
                        entities = json.loads(match.group())
                except (json.JSONDecodeError, AttributeError):
                    try:
                        match = re.search(r'```(?:json)?\s*(\[.*?\])\s*```', text_out, re.DOTALL)
                        if match:
                            entities = json.loads(match.group(1))
                    except:
                        total_errors += 1
                        continue
                
                total_docs += 1
                
                for ent in entities:
                    # Handle nested lists (some models return [[...]])
                    if isinstance(ent, list):
                        for sub in ent:
                            if isinstance(sub, dict):
                                n = sub.get("name", "").strip()
                                t = sub.get("type", "unknown").lower()
                                c = float(sub.get("confidence", 0.5))
                                if len(n) >= 3:
                                    batch_buffer.append({"case_id": case_id, "document_id": doc_id, "name": n, "type": t, "confidence": c})
                                    total_entities += 1
                        continue
                    if not isinstance(ent, dict):
                        continue
                    
                    name = ent.get("name", "").strip()
                    etype = ent.get("type", "unknown").lower()
                    confidence = float(ent.get("confidence", 0.5))
                    
                    # Quality filter
                    if len(name) < 3:
                        continue
                    
                    batch_buffer.append({
                        "case_id": case_id,
                        "document_id": doc_id,
                        "name": name,
                        "type": etype,
                        "confidence": confidence,
                    })
                    total_entities += 1
                
                # Flush batch to Aurora
                if len(batch_buffer) >= BATCH_SIZE:
                    _flush_entities(lam, batch_buffer)
                    batch_buffer = []
                
            except json.JSONDecodeError:
                total_errors += 1
                continue
        
        log(f"  Docs: {total_docs:,}, Entities: {total_entities:,}, Errors: {total_errors}")
    
    # Flush remaining
    if batch_buffer:
        _flush_entities(lam, batch_buffer)
    
    log(f"\nLOAD COMPLETE")
    log(f"  Documents processed: {total_docs:,}")
    log(f"  Entities loaded: {total_entities:,}")
    log(f"  Errors: {total_errors}")
    log(f"\nNext step: python scripts/ec2_neptune_resync.py --case-id {case_id}")


def _flush_entities(lam, entities):
    """Insert a batch of entities into Aurora via Lambda."""
    resp = lam.invoke(
        FunctionName=CONFIG["lambda_name"],
        Payload=json.dumps({
            "action": "insert_entities_from_batch",
            "entities": entities,
        }),
    )
    result = json.loads(resp["Payload"].read())
    if "error" in result:
        log(f"  Batch insert error: {result['error'][:200]}")


# ═══════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Entity Extraction Pipeline — Bedrock Batch Inference",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Steps:
  1. generate  — Create JSONL prompts from Aurora documents
  2. submit    — Submit Bedrock Batch Inference job
  3. status    — Check job status
  4. load      — Load results into Aurora

Example:
  python scripts/entity_extraction_pipeline.py generate --case-id 7f05e8d5-...
  python scripts/entity_extraction_pipeline.py submit --case-id 7f05e8d5-...
  python scripts/entity_extraction_pipeline.py status --job-arn arn:aws:bedrock:...
  python scripts/entity_extraction_pipeline.py load --case-id 7f05e8d5-... --job-arn arn:aws:bedrock:...
        """,
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Pipeline step to run")
    
    # Generate
    gen_parser = subparsers.add_parser("generate", help="Generate JSONL prompts")
    gen_parser.add_argument("--case-id", required=True, help="Case file ID (UUID)")
    gen_parser.add_argument("--model", default=CONFIG["model_id"], help="Bedrock model ID")
    gen_parser.add_argument("--dataset-filter", default=None,
                            help="Only extract docs with this source_metadata.dataset tag (e.g. DS12)")
    
    # Submit
    sub_parser = subparsers.add_parser("submit", help="Submit batch job")
    sub_parser.add_argument("--case-id", required=True, help="Case file ID (UUID)")
    
    # Status
    stat_parser = subparsers.add_parser("status", help="Check job status")
    stat_parser.add_argument("--job-arn", required=True, help="Batch job ARN")
    
    # Load
    load_parser = subparsers.add_parser("load", help="Load results into Aurora")
    load_parser.add_argument("--case-id", required=True, help="Case file ID (UUID)")
    load_parser.add_argument("--job-arn", required=True, help="Batch job ARN (for output path)")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    if hasattr(args, "model") and args.model:
        CONFIG["model_id"] = args.model
        if "nova" in args.model.lower():
            CONFIG["model_format"] = "nova"
        else:
            CONFIG["model_format"] = "anthropic"
    
    commands = {
        "generate": cmd_generate,
        "submit": cmd_submit,
        "status": cmd_status,
        "load": cmd_load,
    }
    
    commands[args.command](args)


if __name__ == "__main__":
    main()
