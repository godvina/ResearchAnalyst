"""Batch image classification for extracted images using Pillow heuristics.

Downloads each extracted image from S3, computes entropy, color variance, and
edge density, then assigns a classification: photograph, document_page,
redacted_text, or blank. Produces image_classification.json artifact in S3.

Supports resume via local progress file. Handles errors gracefully.

Usage:
    python scripts/classify_images.py [--case-id CASE_ID] [--target-case TARGET] [--limit N] [--dry-run]
"""

import argparse
import io
import json
import logging
import os
import sys
import time

import boto3
import numpy as np
from PIL import Image, ImageFilter

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

BUCKET = "research-analyst-data-lake-974220725866"
REGION = "us-east-1"
DEFAULT_CASE = "7f05e8d5-4492-4f19-8894-25367606db96"
COMBINED_CASE = "ed0b6c27-3b6b-4255-b9d0-efe8f4383a99"
PROGRESS_FILE = "scripts/classify_images_progress.json"
EDGE_THRESHOLD = 30  # pixel value threshold for edge detection


def classify_image_metrics(entropy: float, color_variance: float, edge_density: float) -> str:
    """Classify an image based on precomputed metrics using priority rules.

    This is a pure function with no side effects or I/O.

    Priority order:
        1. blank:         entropy < 2.0
        2. redacted_text: entropy < 4.0
        3. document_page: entropy < 5.5 AND color_variance < 50
                      OR  color_variance < 35 AND edge_density > 0.15
        4. photograph:    default

    Args:
        entropy: Grayscale image entropy (0-8 typical range).
        color_variance: Std dev of grayscale pixel values.
        edge_density: Ratio of edge pixels to total pixels (0.0-1.0).

    Returns:
        One of "blank", "redacted_text", "document_page", "photograph".
    """
    if entropy < 2.0:
        return "blank"
    if entropy < 4.0:
        return "redacted_text"
    if entropy < 5.5 and color_variance < 50:
        return "document_page"
    if color_variance < 35 and edge_density > 0.15:
        return "document_page"
    return "photograph"


def compute_metrics(image_bytes: bytes) -> dict:
    """Compute entropy, color_variance, and edge_density from raw image bytes.

    Args:
        image_bytes: Raw bytes of the image file.

    Returns:
        Dict with keys: entropy, color_variance, edge_density.
    """
    img = Image.open(io.BytesIO(image_bytes))
    gray = img.convert("L")

    # Entropy: Pillow grayscale entropy
    entropy = gray.entropy()

    # Color variance: std dev of grayscale pixel values
    gray_array = np.array(gray, dtype=np.float64)
    color_variance = float(np.std(gray_array))

    # Edge density: ratio of edge pixels above threshold to total pixels
    edges = gray.filter(ImageFilter.FIND_EDGES)
    edge_array = np.array(edges)
    total_pixels = edge_array.size
    edge_pixels = int(np.sum(edge_array > EDGE_THRESHOLD))
    edge_density = edge_pixels / total_pixels if total_pixels > 0 else 0.0

    return {
        "entropy": round(entropy, 4),
        "color_variance": round(color_variance, 4),
        "edge_density": round(edge_density, 4),
    }


def build_summary(classifications: list) -> dict:
    """Build summary counts from a list of classification dicts.

    Args:
        classifications: List of dicts each with a "classification" key.

    Returns:
        Dict with total, photograph, document_page, redacted_text, blank, errors counts.
    """
    counts = {"photograph": 0, "document_page": 0, "redacted_text": 0, "blank": 0}
    for entry in classifications:
        cat = entry.get("classification", "")
        if cat in counts:
            counts[cat] += 1
    return {
        "total": len(classifications),
        **counts,
        "errors": 0,  # updated by caller
    }


def load_progress() -> dict:
    """Load resume progress from local file."""
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE) as f:
            return json.load(f)
    return {"cursor": 0, "classifications": []}


def save_progress(progress: dict):
    """Save resume progress to local file."""
    with open(PROGRESS_FILE, "w") as f:
        json.dump(progress, f, indent=2)


def _run_diagnostics():
    """Analyze metrics from the progress file and print distribution stats."""
    progress = load_progress()
    classifications = progress.get("classifications", [])
    if not classifications:
        print("No classifications in progress file. Run the classifier first.")
        return

    # Group by classification
    buckets = {"photograph": [], "document_page": [], "redacted_text": [], "blank": []}
    for entry in classifications:
        cat = entry.get("classification", "unknown")
        metrics = entry.get("metrics", {})
        if cat in buckets:
            buckets[cat].append(metrics)

    print(f"\n{'='*80}")
    print(f"CLASSIFICATION DIAGNOSTICS — {len(classifications)} images analyzed")
    print(f"{'='*80}")

    for cat, items in buckets.items():
        if not items:
            print(f"\n  {cat.upper()}: 0 images")
            continue
        entropies = [m.get("entropy", 0) for m in items]
        cvs = [m.get("color_variance", 0) for m in items]
        eds = [m.get("edge_density", 0) for m in items]
        print(f"\n  {cat.upper()}: {len(items)} images")
        print(f"    entropy:        min={min(entropies):.2f}  max={max(entropies):.2f}  "
              f"mean={sum(entropies)/len(entropies):.2f}  median={sorted(entropies)[len(entropies)//2]:.2f}")
        print(f"    color_variance: min={min(cvs):.2f}  max={max(cvs):.2f}  "
              f"mean={sum(cvs)/len(cvs):.2f}  median={sorted(cvs)[len(cvs)//2]:.2f}")
        print(f"    edge_density:   min={min(eds):.4f}  max={max(eds):.4f}  "
              f"mean={sum(eds)/len(eds):.4f}  median={sorted(eds)[len(eds)//2]:.4f}")

    # Show samples from "photograph" bucket to spot misclassified docs
    photos = buckets.get("photograph", [])
    if photos:
        # Sort by color_variance ascending — lowest CV photos are most likely misclassified docs
        photo_entries = [(m, e) for e in classifications
                         if e.get("classification") == "photograph"
                         for m in [e.get("metrics", {})]]
        photo_entries.sort(key=lambda x: x[0].get("color_variance", 999))
        print(f"\n  PHOTOGRAPH samples (lowest color_variance — likely misclassified docs):")
        for m, entry in photo_entries[:10]:
            fname = entry.get("s3_key", "").split("/")[-1][:40]
            print(f"    {fname:42s}  ent={m.get('entropy',0):5.2f}  cv={m.get('color_variance',0):6.2f}  ed={m.get('edge_density',0):.4f}")

        # Highest CV photos — likely real photos
        print(f"\n  PHOTOGRAPH samples (highest color_variance — likely real photos):")
        for m, entry in photo_entries[-10:]:
            fname = entry.get("s3_key", "").split("/")[-1][:40]
            print(f"    {fname:42s}  ent={m.get('entropy',0):5.2f}  cv={m.get('color_variance',0):6.2f}  ed={m.get('edge_density',0):.4f}")

    # Show histogram buckets for the "photograph" category
    if photos:
        print(f"\n  PHOTOGRAPH color_variance histogram:")
        cv_vals = sorted(m.get("color_variance", 0) for m in photos)
        ranges = [(0, 20), (20, 30), (30, 40), (40, 50), (50, 60), (60, 80), (80, 100), (100, 999)]
        for lo, hi in ranges:
            count = sum(1 for v in cv_vals if lo <= v < hi)
            bar = "#" * min(count, 60)
            print(f"    cv {lo:3d}-{hi:3d}: {count:5d} {bar}")

        print(f"\n  PHOTOGRAPH entropy histogram:")
        ent_vals = sorted(m.get("entropy", 0) for m in photos)
        ranges = [(2, 3), (3, 4), (4, 5), (5, 6), (6, 7), (7, 8), (8, 10)]
        for lo, hi in ranges:
            count = sum(1 for v in ent_vals if lo <= v < hi)
            bar = "#" * min(count, 60)
            print(f"    ent {lo:2d}-{hi:2d}: {count:5d} {bar}")

    print(f"\n{'='*80}")


def main():
    parser = argparse.ArgumentParser(description="Classify extracted images by visual content type")
    parser.add_argument("--case-id", default=DEFAULT_CASE,
                        help="Case ID to process")
    parser.add_argument("--target-case", default=None,
                        help="Also copy artifact to this case ID (e.g. combined case)")
    parser.add_argument("--limit", type=int, default=0,
                        help="Max images to process (0=all)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Compute classifications but don't upload to S3")
    parser.add_argument("--diagnostics", action="store_true",
                        help="Dump metric distributions from existing progress file and exit")
    args = parser.parse_args()

    if args.diagnostics:
        _run_diagnostics()
        return

    s3 = boto3.client("s3", region_name=REGION)

    # List all extracted images
    prefix = f"cases/{args.case_id}/extracted-images/"
    logger.info("Listing extracted images under %s ...", prefix)
    images = []
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=BUCKET, Prefix=prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if key.lower().endswith((".jpg", ".jpeg", ".png")):
                images.append(key)
    logger.info("Found %d images", len(images))

    if not images:
        logger.warning("No images found. Exiting.")
        return

    # Resume from progress
    progress = load_progress()
    start_idx = progress["cursor"]
    classifications = progress.get("classifications", [])
    if start_idx > 0:
        logger.info("Resuming from image %d (%d already classified)", start_idx, len(classifications))

    # Apply limit
    if args.limit > 0:
        end_idx = min(start_idx + args.limit, len(images))
    else:
        end_idx = len(images)

    batch = images[start_idx:end_idx]
    logger.info("Processing %d images (index %d to %d)", len(batch), start_idx, end_idx)

    errors = 0

    for i, s3_key in enumerate(batch):
        try:
            # Download image
            obj = s3.get_object(Bucket=BUCKET, Key=s3_key)
            image_bytes = obj["Body"].read()

            # Compute metrics
            metrics = compute_metrics(image_bytes)

            # Classify
            classification = classify_image_metrics(
                metrics["entropy"], metrics["color_variance"], metrics["edge_density"]
            )

            classifications.append({
                "s3_key": s3_key,
                "classification": classification,
                "metrics": metrics,
            })

        except Exception as e:
            logger.warning("Failed to process %s: %s", s3_key.split("/")[-1], str(e)[:150])
            errors += 1

        # Update progress periodically
        progress["cursor"] = start_idx + i + 1
        progress["classifications"] = classifications
        if (i + 1) % 50 == 0:
            save_progress(progress)
            logger.info("Progress: %d/%d processed, %d errors", i + 1, len(batch), errors)

    save_progress(progress)

    # Build summary
    summary = build_summary(classifications)
    summary["errors"] = errors

    artifact = {
        "case_id": args.case_id,
        "classifications": classifications,
        "summary": summary,
    }

    artifact_key = f"cases/{args.case_id}/rekognition-artifacts/image_classification.json"

    if args.dry_run:
        logger.info("[DRY RUN] Would upload artifact to %s", artifact_key)
        logger.info("[DRY RUN] Summary: %s", json.dumps(summary, indent=2))
    else:
        artifact_body = json.dumps(artifact, indent=2).encode()
        s3.put_object(
            Bucket=BUCKET, Key=artifact_key, Body=artifact_body,
            ContentType="application/json",
        )
        logger.info("Uploaded classification artifact to %s", artifact_key)

        # Copy to target case if specified
        if args.target_case:
            target_key = f"cases/{args.target_case}/rekognition-artifacts/image_classification.json"
            s3.put_object(
                Bucket=BUCKET, Key=target_key, Body=artifact_body,
                ContentType="application/json",
            )
            logger.info("Copied artifact to target case: %s", target_key)

    # Print summary
    print(f"\n{'='*60}")
    print(f"Image Classification Complete")
    print(f"  Total images:    {summary['total']}")
    print(f"  Photographs:     {summary['photograph']}")
    print(f"  Document pages:  {summary['document_page']}")
    print(f"  Redacted text:   {summary['redacted_text']}")
    print(f"  Blank:           {summary['blank']}")
    print(f"  Errors:          {summary['errors']}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
