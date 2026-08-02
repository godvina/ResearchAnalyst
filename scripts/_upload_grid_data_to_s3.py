"""Upload grid research and scored findings to S3 for the API to serve.

These files are needed by the grid-globe.html dashboard:
- uvg-grid-research-all-nodes.json (AI briefs per node)
- uvg-grid-scored-findings.json (signature matches for network graph)

Usage:
    python scripts/_upload_grid_data_to_s3.py
"""
import boto3
import os

S3_BUCKET = "research-analyst-data-lake-974220725866"
REGION = "us-east-1"
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "src", "data")

FILES_TO_UPLOAD = [
    "uvg-grid-research-all-nodes.json",
    "uvg-grid-scored-findings.json",
    "uvg-grid-investigation-database.json",
    "audio-combined-v2.json",
    "investigation-rationales.json",
]

def main():
    s3 = boto3.client("s3", region_name=REGION)
    print(f"Uploading grid data to s3://{S3_BUCKET}/pattern-library/\n")

    for filename in FILES_TO_UPLOAD:
        filepath = os.path.join(DATA_DIR, filename)
        if not os.path.exists(filepath):
            print(f"  SKIP: {filename} (file not found)")
            continue
        key = f"pattern-library/{filename}"
        size_kb = os.path.getsize(filepath) / 1024
        print(f"  {filename} ({size_kb:.0f} KB) → {key}")
        s3.upload_file(filepath, S3_BUCKET, key)

    print("\n✓ Done. Grid API endpoints now have data.")

if __name__ == "__main__":
    main()
