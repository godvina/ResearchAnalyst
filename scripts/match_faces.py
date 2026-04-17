"""Match unidentified face crops against known entity photos using Rekognition CompareFaces.

For each unidentified crop, compares against all known entity demo photos.
If a match is found (similarity >= threshold), copies the crop to the entity's named folder.
Supports incremental runs via comparison log tracking — skips already-completed comparisons.
Merges new results into existing face_match_results.json cumulatively.

Usage:
    python scripts/match_faces.py [--case-id CASE_ID] [--threshold 80] [--dry-run]
    python scripts/match_faces.py --comparison-log scripts/face_match_log.json
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone

import boto3

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

BUCKET = "research-analyst-data-lake-974220725866"
REGION = "us-east-1"
MAIN_CASE = "7f05e8d5-4492-4f19-8894-25367606db96"
COMBINED_CASE = "ed0b6c27-3b6b-4255-b9d0-efe8f4383a99"
DEFAULT_LOG = "scripts/face_match_comparison_log.json"


def load_comparison_log(path):
    """Load the comparison log from disk. Returns empty log if missing/corrupted."""
    if not os.path.exists(path):
        return {"completed_comparisons": [], "last_run": None, "total_comparisons": 0}
    try:
        with open(path) as f:
            data = json.load(f)
        if not isinstance(data.get("completed_comparisons"), list):
            raise ValueError("Invalid log format")
        return data
    except Exception as e:
        logger.warning("Comparison log corrupted, starting fresh: %s", e)
        return {"completed_comparisons": [], "last_run": None, "total_comparisons": 0}


def save_comparison_log(path, log):
    """Save the comparison log to disk."""
    with open(path, "w") as f:
        json.dump(log, f, indent=2)


def load_existing_results(s3, case_id):
    """Load existing face_match_results.json from S3. Returns empty if missing."""
    key = f"cases/{case_id}/rekognition-artifacts/face_match_results.json"
    try:
        resp = s3.get_object(Bucket=BUCKET, Key=key)
        data = json.loads(resp["Body"].read().decode())
        if not isinstance(data.get("matches"), list):
            raise ValueError("Invalid results format")
        return data
    except Exception:
        return {"matches": [], "no_match": [], "threshold": 80.0, "runs": []}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-id", default=MAIN_CASE)
    parser.add_argument("--threshold", type=float, default=80.0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--comparison-log", default=DEFAULT_LOG,
                        help="Path to comparison log for incremental runs")
    args = parser.parse_args()

    s3 = boto3.client("s3", region_name=REGION)
    rek = boto3.client("rekognition", region_name=REGION)
    run_timestamp = datetime.now(timezone.utc).isoformat()

    # Load comparison log for incremental tracking
    comp_log = load_comparison_log(args.comparison_log)
    completed_set = {(c["crop"], c["entity"]) for c in comp_log["completed_comparisons"]}
    logger.info("Loaded comparison log: %d previous comparisons", len(completed_set))

    # Load existing results for cumulative merging
    existing_results = load_existing_results(s3, args.case_id)
    existing_match_set = {(m["crop"], m["entity"]) for m in existing_results.get("matches", [])}

    # List known entity demo photos
    demo_prefix = f"cases/{args.case_id}/face-crops/demo/"
    known_entities = {}
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=BUCKET, Prefix=demo_prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            name = key[len(demo_prefix):].replace(".jpg", "")
            if name:
                known_entities[name] = key
    logger.info("Found %d known entity photos: %s", len(known_entities), list(known_entities.keys()))

    # List unidentified face crops
    unid_prefix = f"cases/{args.case_id}/face-crops/unidentified/"
    unid_crops = []
    for page in paginator.paginate(Bucket=BUCKET, Prefix=unid_prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if key.endswith(".jpg"):
                unid_crops.append(key)
    logger.info("Found %d unidentified face crops", len(unid_crops))

    if not unid_crops or not known_entities:
        print("Nothing to match.")
        return

    matches = []
    no_match = []
    skipped = 0
    new_comparisons = []

    for i, crop_key in enumerate(unid_crops):
        crop_name = crop_key.split("/")[-1]
        best_match = None
        best_similarity = 0

        for entity_name, entity_key in known_entities.items():
            # Skip already-completed comparisons
            if (crop_name, entity_name) in completed_set:
                skipped += 1
                continue

            try:
                resp = rek.compare_faces(
                    SourceImage={"S3Object": {"Bucket": BUCKET, "Name": crop_key}},
                    TargetImage={"S3Object": {"Bucket": BUCKET, "Name": entity_key}},
                    SimilarityThreshold=args.threshold,
                )
                for face_match in resp.get("FaceMatches", []):
                    similarity = face_match.get("Similarity", 0)
                    if similarity > best_similarity:
                        best_similarity = similarity
                        best_match = entity_name
            except Exception as e:
                err_str = str(e)
                if "InvalidParameterException" in err_str:
                    continue
                logger.warning("CompareFaces error for %s vs %s: %s", crop_name, entity_name, err_str[:80])
                continue

            # Record this comparison as completed
            new_comparisons.append({"crop": crop_name, "entity": entity_name, "timestamp": run_timestamp})
            time.sleep(0.1)

        if best_match and (crop_name, best_match) not in existing_match_set:
            logger.info("  MATCH: %s -> %s (%.1f%%)", crop_name, best_match, best_similarity)
            new_key = f"cases/{args.case_id}/face-crops/{best_match}/{crop_name}"
            if not args.dry_run:
                s3.copy_object(Bucket=BUCKET, CopySource={"Bucket": BUCKET, "Key": crop_key}, Key=new_key)
                combined_key = new_key.replace(args.case_id, COMBINED_CASE)
                s3.copy_object(Bucket=BUCKET, CopySource={"Bucket": BUCKET, "Key": crop_key}, Key=combined_key)
            matches.append({
                "crop": crop_name, "entity": best_match,
                "similarity": round(best_similarity, 1),
                "source_key": crop_key, "new_key": new_key,
                "run_timestamp": run_timestamp,
            })
        elif not best_match:
            logger.info("  NO MATCH: %s", crop_name)
            no_match.append(crop_name)

        if (i + 1) % 5 == 0:
            logger.info("Progress: %d/%d crops, %d new matches, %d skipped comparisons",
                        i + 1, len(unid_crops), len(matches), skipped)

    # Update comparison log
    comp_log["completed_comparisons"].extend(new_comparisons)
    comp_log["last_run"] = run_timestamp
    comp_log["total_comparisons"] = len(comp_log["completed_comparisons"])
    save_comparison_log(args.comparison_log, comp_log)
    logger.info("Saved comparison log: %d total comparisons", comp_log["total_comparisons"])

    # Merge results cumulatively
    all_matches = existing_results.get("matches", []) + matches
    # Deduplicate by (crop, entity)
    seen = set()
    deduped = []
    for m in all_matches:
        key = (m["crop"], m.get("entity", ""))
        if key not in seen:
            seen.add(key)
            deduped.append(m)

    all_no_match = list(set(existing_results.get("no_match", []) + no_match))
    # Remove from no_match any crops that now have matches
    matched_crops = {m["crop"] for m in deduped}
    all_no_match = [c for c in all_no_match if c not in matched_crops]

    runs = existing_results.get("runs", [])
    runs.append({
        "timestamp": run_timestamp,
        "new_matches": len(matches),
        "new_crops": len(unid_crops),
        "new_entities": len(known_entities),
        "skipped_comparisons": skipped,
        "new_api_calls": len(new_comparisons),
    })

    merged = {"matches": deduped, "no_match": all_no_match, "threshold": args.threshold, "runs": runs}
    results_key = f"cases/{args.case_id}/rekognition-artifacts/face_match_results.json"
    if not args.dry_run:
        s3.put_object(Bucket=BUCKET, Key=results_key,
                      Body=json.dumps(merged, indent=2).encode(), ContentType="application/json")

    print(f"\nResults: {len(matches)} new matches, {len(no_match)} unmatched, {skipped} skipped")
    print(f"Cumulative: {len(deduped)} total matches across {len(runs)} runs")
    for m in matches:
        print(f"  {m['crop']} -> {m['entity']} ({m['similarity']}%)")


if __name__ == "__main__":
    main()
