"""Update case_files.document_count from S3 actual file counts.

Counts real .txt/.pdf files in S3 for each case and updates Aurora via
the IngestionUpdateStatus Lambda.

Usage:
    python scripts/update_case_doc_counts.py
"""
import boto3, json, urllib.request

REGION = "us-east-1"
BUCKET = "research-analyst-data-lake-974220725866"
API_URL = "https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1"
UPDATE_LAMBDA = "ResearchAnalystStack-IngestionUpdateStatusLambda61-1FI9EFALbEpJ"

s3 = boto3.client("s3", region_name=REGION)
lam = boto3.client("lambda", region_name=REGION)


def count_s3_docs(case_id):
    prefix = f"cases/{case_id}/"
    count = 0
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=BUCKET, Prefix=prefix):
        for obj in page.get("Contents", []):
            if obj["Key"].endswith(".txt") or obj["Key"].endswith(".pdf"):
                count += 1
    return count


def list_cases():
    req = urllib.request.Request(f"{API_URL}/case-files", method="GET")
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode())
    return data.get("case_files", [])


def update_count(case_id, doc_count):
    try:
        resp = lam.invoke(
            FunctionName=UPDATE_LAMBDA,
            Payload=json.dumps({
                "case_id": case_id,
                "status": "indexed",
                "document_count": doc_count,
                "entity_count": 0,
                "relationship_count": 0,
            })
        )
        return True
    except Exception as e:
        print(f"  Failed: {e}")
        return False


def main():
    print("=" * 60)
    print("Update Case Document Counts from S3")
    print("=" * 60)
    cases = list_cases()

    updated = 0
    for c in cases:
        cid = c.get("case_id", "")
        name = c.get("topic_name", "?")
        current = c.get("document_count", 0)

        s3_count = count_s3_docs(cid)
        if s3_count > 0 and s3_count != current:
            print(f"  {cid[:12]} {name}: {current} -> {s3_count}")
            if update_count(cid, s3_count):
                updated += 1
        elif s3_count > 0:
            print(f"  {cid[:12]} {name}: {s3_count} (correct)")
        # Skip cases with 0 S3 docs

    print(f"\nUpdated {updated} cases. Refresh the UI.")


if __name__ == "__main__":
    main()
