"""Index Pattern Library taxonomy signatures into OpenSearch via Lambda.

Since OpenSearch Serverless is behind a VPC endpoint, we can't access it
directly from local. This script:
1. Uploads taxonomy JSON files to S3
2. Invokes the case-files Lambda with a special action to index them
   (the Lambda has VPC access to OpenSearch)

Alternative: invoke score_typology Lambda with seed action first (recreates
existing crime patterns), then run this to append taxonomy signatures.

Usage:
    python scripts/index_taxonomy_via_lambda.py
    python scripts/index_taxonomy_via_lambda.py --seed-first
"""

import argparse
import json
import os
import sys
import time

import boto3

AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
S3_BUCKET = "research-analyst-data-lake-974220725866"
LAMBDA_FUNCTION = "TypologyPipeline-ScoreTypology"

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TAXONOMY_FILES = [
    os.path.join(BASE_DIR, "src", "data", "pattern-library-taxonomy.json"),
    os.path.join(BASE_DIR, "src", "data", "ancient-mysteries-taxonomy.json"),
]

s3 = boto3.client("s3", region_name=AWS_REGION)
lambda_client = boto3.client("lambda", region_name=AWS_REGION)


def upload_taxonomy_to_s3():
    """Upload taxonomy files to S3 for Lambda to read."""
    for filepath in TAXONOMY_FILES:
        if not os.path.exists(filepath):
            print(f"  ⚠ Skipping (not found): {filepath}")
            continue
        key = f"pattern-library/{os.path.basename(filepath)}"
        print(f"  Uploading {os.path.basename(filepath)} → s3://{S3_BUCKET}/{key}")
        s3.upload_file(filepath, S3_BUCKET, key)
    print("  ✓ Taxonomy files uploaded to S3\n")


def seed_existing_patterns():
    """Re-seed the existing crime prosecution patterns (from TYPOLOGY_QUERIES)."""
    print("[1] Re-seeding existing prosecution patterns via Lambda...")
    print("    (This recreates the index with ~264 crime patterns)")
    print("    May take 30-60 seconds...\n")

    response = lambda_client.invoke(
        FunctionName=LAMBDA_FUNCTION,
        InvocationType="RequestResponse",
        Payload=json.dumps({"action": "seed_typology_patterns_index"}).encode(),
    )

    status = response["StatusCode"]
    payload_resp = json.loads(response["Payload"].read().decode())

    if response.get("FunctionError"):
        print(f"  ⚠ Lambda error: {payload_resp.get('errorMessage', 'unknown')[:300]}")
        return False

    print(f"  ✓ Seed complete: {payload_resp.get('message', 'done')}")
    return True


def index_taxonomy_signatures():
    """Index taxonomy signatures by invoking Lambda with pattern data.

    Since the Lambda's seed function reads from TYPOLOGY_QUERIES (hardcoded),
    we use an alternative approach: invoke case-files Lambda which also has
    OpenSearch access, with a custom action.

    For now, we build the documents locally and pass them in the payload.
    Lambda payloads support up to 6MB — our 105 sigs are well under 256KB.
    """
    print("[2] Indexing Pattern Library taxonomy signatures...")

    # Load all signatures from taxonomy files
    all_docs = []
    for filepath in TAXONOMY_FILES:
        if not os.path.exists(filepath):
            continue
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Handle multi-domain file
        domains = data.get("domains", [data] if "typologies" in data else [])
        for domain in domains:
            domain_id = domain.get("domain_id", "unknown")
            for typology in domain.get("typologies", []):
                for method in typology.get("methods", []):
                    for sig in method.get("signatures", []):
                        all_docs.append({
                            "pattern_id": sig["signature_id"],
                            "pattern_text": sig["vector_text"],
                            "typology_module_id": domain_id,
                            "sub_category_id": typology["typology_id"],
                            "indicator_name": sig["description"][:200],
                            "source": "pattern_library_taxonomy",
                            "severity": sig["severity"],
                        })

    print(f"    Found {len(all_docs)} signatures to index")

    # Invoke Lambda with signatures in payload (they'll be embedded + indexed)
    # We pass in batches of 25 to stay well under Lambda payload limits
    batch_size = 25
    total_indexed = 0

    for start in range(0, len(all_docs), batch_size):
        batch = all_docs[start:start + batch_size]
        payload = {
            "action": "index_pattern_library_batch",
            "patterns": batch,
        }

        print(f"    Batch {start // batch_size + 1}: indexing {len(batch)} signatures...", end=" ", flush=True)

        response = lambda_client.invoke(
            FunctionName=LAMBDA_FUNCTION,
            InvocationType="RequestResponse",
            Payload=json.dumps(payload).encode(),
        )

        resp_payload = json.loads(response["Payload"].read().decode())

        if response.get("FunctionError"):
            print(f"⚠ ERROR: {resp_payload.get('errorMessage', 'unknown')[:200]}")
            # If the Lambda doesn't support this action yet, fall back to seed approach
            if "Unknown action" in str(resp_payload) or "Missing" in str(resp_payload):
                print("\n    ⚠ Lambda doesn't support 'index_pattern_library_batch' action yet.")
                print("    The taxonomy signatures need to be added to TYPOLOGY_QUERIES or")
                print("    the seed script needs to be extended to also read from S3.")
                print(f"\n    Taxonomy files are in S3 at: s3://{S3_BUCKET}/pattern-library/")
                print("    You can extend the seed_typology_patterns() function to also index these.")
                return False
        else:
            indexed = resp_payload.get("indexed", len(batch))
            total_indexed += indexed
            print(f"✓ ({indexed})")

        time.sleep(0.5)  # Brief pause between batches

    print(f"\n  ✓ Total indexed: {total_indexed} taxonomy signatures")
    return True


def main():
    parser = argparse.ArgumentParser(description="Index taxonomy into OpenSearch via Lambda")
    parser.add_argument("--seed-first", action="store_true",
                        help="Re-seed existing crime patterns before adding taxonomy (DESTRUCTIVE to existing index)")
    parser.add_argument("--upload-only", action="store_true",
                        help="Only upload files to S3, don't invoke Lambda")
    args = parser.parse_args()

    print("=" * 60)
    print("Pattern Library → OpenSearch Indexer (via Lambda)")
    print("=" * 60 + "\n")

    # Upload taxonomy to S3 regardless
    print("[0] Uploading taxonomy files to S3...")
    upload_taxonomy_to_s3()

    if args.upload_only:
        print("Done (upload only). Files available at:")
        print(f"  s3://{S3_BUCKET}/pattern-library/pattern-library-taxonomy.json")
        print(f"  s3://{S3_BUCKET}/pattern-library/ancient-mysteries-taxonomy.json")
        return

    if args.seed_first:
        success = seed_existing_patterns()
        if not success:
            print("Seed failed. Continuing with taxonomy indexing anyway...")
        print()
        time.sleep(3)  # Let index settle

    index_taxonomy_signatures()

    print("\n" + "=" * 60)
    print("Next step: Re-score the Ancient Aliens case:")
    print("  python scripts/rescore_case_typology.py --case-id ancient_aliens --module ancient_mysteries --all-sub-categories")
    print("=" * 60)


if __name__ == "__main__":
    main()
