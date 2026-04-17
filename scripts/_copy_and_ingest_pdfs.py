"""Copy EFTA PDFs from source bucket to case raw folder and trigger pipeline."""
import boto3
import json
import time

s3 = boto3.client("s3", region_name="us-east-1")
sfn = boto3.client("stepfunctions", region_name="us-east-1")

SRC_BUCKET = "doj-cases-974220725866-us-east-1"
DST_BUCKET = "research-analyst-data-lake-974220725866"
CASE_ID = "7f05e8d5-4492-4f19-8894-25367606db96"
SFN_ARN = "arn:aws:states:us-east-1:974220725866:stateMachine:research-analyst-ingestion"

doc_ids = []
batch_doc_ids = []
for i in range(21, 521):
    src_key = f"pdfs/DataSet1/VOL00001/IMAGES/0001/EFTA{str(i).zfill(8)}.pdf"
    dst_key = f"cases/{CASE_ID}/raw/EFTA{str(i).zfill(8)}.pdf"
    doc_id = f"EFTA{str(i).zfill(8)}"
    try:
        s3.copy_object(
            CopySource={"Bucket": SRC_BUCKET, "Key": src_key},
            Bucket=DST_BUCKET,
            Key=dst_key,
        )
        batch_doc_ids.append(doc_id)
        print(f"  Copied {doc_id}.pdf ({len(batch_doc_ids)} in batch)")
        if len(batch_doc_ids) >= 50:
            inp = {
                "case_id": CASE_ID,
                "sample_mode": False,
                "upload_result": {
                    "document_ids": batch_doc_ids,
                    "document_count": len(batch_doc_ids),
                },
            }
            resp = sfn.start_execution(
                stateMachineArn=SFN_ARN,
                name=f"epstein-pdf-batch-{int(time.time())}",
                input=json.dumps(inp),
            )
            print(f"  -> SFN batch: {resp['executionArn'].split(':')[-1]}")
            doc_ids.extend(batch_doc_ids)
            batch_doc_ids = []
            time.sleep(2)
    except Exception as e:
        print(f"  SKIP {doc_id}: {e}")

if batch_doc_ids:
    inp = {
        "case_id": CASE_ID,
        "sample_mode": False,
        "upload_result": {
            "document_ids": batch_doc_ids,
            "document_count": len(batch_doc_ids),
        },
    }
    resp = sfn.start_execution(
        stateMachineArn=SFN_ARN,
        name=f"epstein-pdf-final-{int(time.time())}",
        input=json.dumps(inp),
    )
    print(f"  -> SFN final batch: {resp['executionArn'].split(':')[-1]}")
    doc_ids.extend(batch_doc_ids)

print(f"\nTotal: {len(doc_ids)} PDFs copied and submitted")
