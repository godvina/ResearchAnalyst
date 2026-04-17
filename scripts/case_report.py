"""Report actual document counts per case from S3 (ground truth)."""
import boto3, json

REGION = "us-east-1"
BUCKET = "research-analyst-data-lake-974220725866"
API_URL = "https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1"

s3 = boto3.client("s3", region_name=REGION)


def count_s3_docs(case_id):
    """Count actual files in S3 for a case."""
    prefix = f"cases/{case_id}/"
    count = 0
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=BUCKET, Prefix=prefix):
        for obj in page.get("Contents", []):
            if obj["Key"].endswith(".txt") or obj["Key"].endswith(".pdf"):
                count += 1
    return count


def list_cases():
    import urllib.request
    url = f"{API_URL}/case-files"
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode())
    return data.get("case_files", [])


def main():
    print("=" * 80)
    print("CASE REPORT — Actual Document Counts (from S3)")
    print("=" * 80)

    cases = list_cases()
    print(f"\n{'Case ID':<14} {'S3 Docs':>8} {'Aurora':>8}  Name")
    print("-" * 80)

    total_s3 = 0
    for c in sorted(cases, key=lambda x: x.get("topic_name", "")):
        cid = c.get("case_id", "?")
        name = c.get("topic_name", "?")
        aurora_count = c.get("document_count", 0)
        s3_count = count_s3_docs(cid)
        total_s3 += s3_count
        marker = " <--" if s3_count > 100 else ""
        print(f"{cid[:12]}.. {s3_count:>8} {aurora_count:>8}  {name}{marker}")

    print("-" * 80)
    print(f"{'TOTAL':<14} {total_s3:>8}")
    print()

    # Key cases summary
    print("KEY CASES:")
    key_ids = {
        "7f05e8d5": "Epstein Main (Original)",
        "ed0b6c27": "Epstein Combined (Phase 1 loaded)",
        "156256c3": "Epstein Combined DS1-5+DS11 (earlier attempt)",
        "d72b81fc": "Ancient Aliens",
    }
    for prefix, label in key_ids.items():
        match = [c for c in cases if c.get("case_id", "").startswith(prefix)]
        if match:
            cid = match[0]["case_id"]
            s3_count = count_s3_docs(cid)
            print(f"  {prefix}.. = {s3_count:>6} docs  {label}")


if __name__ == "__main__":
    main()
