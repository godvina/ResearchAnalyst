"""Batch Rekognition label detection on all extracted images.

Processes images in batches, calls detect_labels for each, saves per-image
results to S3, and produces a consolidated labels summary for Neptune loading.

Supports resume via progress file. Rate-limits to avoid Rekognition throttling.

Usage:
    python scripts/batch_rekognition_labels.py [--case-id CASE_ID] [--limit N] [--parallel 5]
"""

import argparse
import json
import logging
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import boto3

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

BUCKET = "research-analyst-data-lake-974220725866"
REGION = "us-east-1"
DEFAULT_CASE = "7f05e8d5-4492-4f19-8894-25367606db96"
PROGRESS_FILE = "scripts/batch_rek_labels_progress.json"

# Investigative labels we care about (expanded set from rekognition_handler.py)
INVESTIGATIVE_LABELS = {
    "person", "people", "human", "face", "head", "portrait", "man", "woman", "boy", "girl", "child", "adult",
    "document", "text", "paper", "letter", "page", "book", "newspaper", "magazine", "receipt", "check",
    "handwriting", "signature", "envelope", "folder", "file", "notebook", "diary", "calendar", "contract",
    "passport", "id card", "license", "badge", "certificate",
    "money", "currency", "cash", "coin", "credit card", "wallet", "safe", "vault",
    "phone", "cell phone", "mobile phone", "telephone", "computer", "laptop", "tablet", "monitor", "screen",
    "camera", "video camera", "surveillance",
    "car", "vehicle", "automobile", "truck", "van", "bus", "motorcycle", "bicycle",
    "boat", "yacht", "ship", "watercraft", "jet ski",
    "airplane", "aircraft", "helicopter", "jet",
    "weapon", "gun", "pistol", "rifle", "knife", "sword",
    "drug", "pill", "syringe", "needle", "bottle", "medication",
    "jewelry", "ring", "necklace", "bracelet", "watch", "diamond", "gold",
    "building", "house", "mansion", "hotel", "office", "tower", "skyscraper",
    "island", "beach", "pool", "swimming pool", "garden", "yard",
    "suitcase", "bag", "luggage", "backpack", "briefcase",
    "alcohol", "wine", "beer", "cocktail", "champagne",
    "food", "meal", "dining", "restaurant",
    "clothing", "suit", "dress", "uniform", "swimwear", "bikini",
    "bed", "bedroom", "hotel room", "bathroom",
    "map", "chart", "graph", "spreadsheet", "table",
    "photograph", "photo", "picture", "image", "painting", "art",
}

MIN_CONFIDENCE = 70.0


def load_progress():
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE) as f:
            return json.load(f)
    return {"processed": 0, "cursor": 0, "labels_found": 0, "faces_found": 0, "errors": 0}


def save_progress(progress):
    with open(PROGRESS_FILE, "w") as f:
        json.dump(progress, f, indent=2)


def process_image(rek, s3_key):
    """Run detect_labels on a single image. Returns dict with labels and faces."""
    try:
        resp = rek.detect_labels(
            Image={"S3Object": {"Bucket": BUCKET, "Name": s3_key}},
            MinConfidence=MIN_CONFIDENCE,
            MaxLabels=50,
        )
        labels = []
        for label in resp.get("Labels", []):
            name = label.get("Name", "")
            conf = label.get("Confidence", 0)
            if name.lower() in INVESTIGATIVE_LABELS and conf >= MIN_CONFIDENCE:
                labels.append({
                    "name": name,
                    "confidence": round(conf, 1),
                    "parents": [p["Name"] for p in label.get("Parents", [])],
                })
        return {"s3_key": s3_key, "labels": labels, "all_label_count": len(resp.get("Labels", [])), "error": None}
    except Exception as e:
        return {"s3_key": s3_key, "labels": [], "all_label_count": 0, "error": str(e)[:200]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-id", default=DEFAULT_CASE)
    parser.add_argument("--limit", type=int, default=0, help="Max images to process (0=all)")
    parser.add_argument("--parallel", type=int, default=3, help="Parallel Rekognition calls")
    args = parser.parse_args()

    s3 = boto3.client("s3", region_name=REGION)
    rek = boto3.client("rekognition", region_name=REGION)

    # List all extracted images
    prefix = f"cases/{args.case_id}/extracted-images/"
    logger.info("Listing extracted images...")
    images = []
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=BUCKET, Prefix=prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if key.lower().endswith((".jpg", ".jpeg", ".png")):
                images.append(key)
    logger.info("Found %d images", len(images))

    # Resume from progress
    progress = load_progress()
    start_idx = progress["cursor"]
    if start_idx > 0:
        logger.info("Resuming from image %d", start_idx)

    if args.limit > 0:
        end_idx = min(start_idx + args.limit, len(images))
    else:
        end_idx = len(images)

    batch = images[start_idx:end_idx]
    logger.info("Processing %d images (index %d to %d)", len(batch), start_idx, end_idx)

    # Collect all results
    all_results = []
    label_counts = {}  # label_name -> count
    errors = 0

    # Process with thread pool for parallelism
    with ThreadPoolExecutor(max_workers=args.parallel) as executor:
        futures = {}
        for s3_key in batch:
            future = executor.submit(process_image, rek, s3_key)
            futures[future] = s3_key

        for i, future in enumerate(as_completed(futures)):
            result = future.result()
            if result["error"]:
                errors += 1
                if errors <= 10:
                    logger.warning("Error on %s: %s", result["s3_key"].split("/")[-1], result["error"][:80])
            else:
                all_results.append(result)
                for label in result["labels"]:
                    label_counts[label["name"]] = label_counts.get(label["name"], 0) + 1

            progress["cursor"] = start_idx + i + 1
            progress["processed"] = start_idx + i + 1
            progress["labels_found"] = sum(label_counts.values())
            progress["errors"] = errors

            if (i + 1) % 100 == 0:
                save_progress(progress)
                top5 = sorted(label_counts.items(), key=lambda x: -x[1])[:5]
                logger.info(
                    "Progress: %d/%d | Labels: %d unique, %d total | Errors: %d | Top: %s",
                    i + 1, len(batch), len(label_counts), sum(label_counts.values()), errors,
                    ", ".join(f"{k}:{v}" for k, v in top5),
                )
            time.sleep(0.05)  # Small delay between batches

    save_progress(progress)

    # Save consolidated results to S3
    summary = {
        "case_id": args.case_id,
        "images_processed": len(all_results),
        "unique_labels": len(label_counts),
        "total_label_instances": sum(label_counts.values()),
        "label_counts": dict(sorted(label_counts.items(), key=lambda x: -x[1])),
        "errors": errors,
    }

    summary_key = f"cases/{args.case_id}/rekognition-artifacts/batch_labels_summary.json"
    s3.put_object(
        Bucket=BUCKET, Key=summary_key,
        Body=json.dumps(summary, indent=2).encode(),
        ContentType="application/json",
    )
    logger.info("Saved summary to %s", summary_key)

    # Save per-image results (only images with labels)
    labeled_images = [r for r in all_results if r["labels"]]
    details_key = f"cases/{args.case_id}/rekognition-artifacts/batch_labels_details.json"
    s3.put_object(
        Bucket=BUCKET, Key=details_key,
        Body=json.dumps(labeled_images, default=str).encode(),
        ContentType="application/json",
    )
    logger.info("Saved %d labeled image details to %s", len(labeled_images), details_key)

    # Print summary
    print(f"\n{'='*60}")
    print(f"Batch Rekognition Labels Complete")
    print(f"  Images processed: {len(all_results)}")
    print(f"  Images with labels: {len(labeled_images)}")
    print(f"  Unique labels: {len(label_counts)}")
    print(f"  Total label instances: {sum(label_counts.values())}")
    print(f"  Errors: {errors}")
    print(f"\nTop 20 labels:")
    for name, count in sorted(label_counts.items(), key=lambda x: -x[1])[:20]:
        print(f"  {name}: {count}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
