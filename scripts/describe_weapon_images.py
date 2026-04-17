"""Send weapon-flagged images to Bedrock Claude for AI description.

Identifies images that Rekognition labeled as Weapon/Gun/Rifle, sends them
to Claude vision for accurate description, and saves results. This demonstrates
how AI vision corrects Rekognition false positives on redacted documents.

Usage:
    python scripts/describe_weapon_images.py [--case-id CASE_ID] [--max 20]
"""

import argparse
import base64
import json
import logging
import time

import boto3

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

BUCKET = "research-analyst-data-lake-974220725866"
REGION = "us-east-1"
CASE_ID = "7f05e8d5-4492-4f19-8894-25367606db96"
COMBINED_CASE = "ed0b6c27-3b6b-4255-b9d0-efe8f4383a99"
MODEL_ID = "anthropic.claude-3-haiku-20240307-v1:0"

WEAPON_LABELS = {"weapon", "gun", "pistol", "rifle", "knife", "sword"}

PROMPT = """Analyze this image extracted from a legal case document. Describe what you see factually:
1. What type of document or content is this? (email, letter, form, photo, etc.)
2. Are there any redaction bars (black rectangles covering text)?
3. What people, objects, or activities are visible?
4. Any names, dates, or locations visible?
5. Is there anything investigatively significant?

Be concise. Report only observable facts."""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-id", default=CASE_ID)
    parser.add_argument("--max", type=int, default=20)
    args = parser.parse_args()

    s3 = boto3.client("s3", region_name=REGION)
    bedrock = boto3.client("bedrock-runtime", region_name=REGION)

    # Load batch labels details
    details_key = f"cases/{args.case_id}/rekognition-artifacts/batch_labels_details.json"
    logger.info("Loading label data...")
    resp = s3.get_object(Bucket=BUCKET, Key=details_key)
    details = json.loads(resp["Body"].read().decode())

    # Find images with weapon labels
    weapon_images = []
    for item in details:
        label_names = {l["name"].lower() for l in item.get("labels", [])}
        weapon_matches = label_names & WEAPON_LABELS
        if weapon_matches:
            all_labels = [l["name"] for l in item.get("labels", [])]
            has_doc_label = bool(label_names & {"text", "page", "letter", "document", "paper"})
            weapon_images.append({
                "s3_key": item["s3_key"],
                "weapon_labels": list(weapon_matches),
                "all_labels": all_labels,
                "has_doc_label": has_doc_label,
            })

    logger.info("Found %d images with weapon labels", len(weapon_images))
    # Sort: likely false positives (has doc label) first
    weapon_images.sort(key=lambda x: (not x["has_doc_label"], x["s3_key"]))

    descriptions = []
    for i, img in enumerate(weapon_images[:args.max]):
        s3_key = img["s3_key"]
        filename = s3_key.split("/")[-1]
        logger.info("[%d/%d] Describing %s (labels: %s)...",
                    i + 1, min(len(weapon_images), args.max), filename, img["weapon_labels"])

        # Download image
        try:
            obj = s3.get_object(Bucket=BUCKET, Key=s3_key)
            image_bytes = obj["Body"].read()
            b64 = base64.b64encode(image_bytes).decode("ascii")
        except Exception as e:
            logger.error("Failed to download %s: %s", s3_key, str(e)[:80])
            continue

        # Call Bedrock Claude
        try:
            body = json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 500,
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b64}},
                        {"type": "text", "text": PROMPT},
                    ],
                }],
            })
            resp = bedrock.invoke_model(modelId=MODEL_ID, body=body, contentType="application/json")
            result = json.loads(resp["body"].read().decode())
            description = result.get("content", [{}])[0].get("text", "")
        except Exception as e:
            logger.error("Bedrock error for %s: %s", filename, str(e)[:120])
            description = f"ERROR: {str(e)[:100]}"

        is_false_positive = img["has_doc_label"] and ("redact" in description.lower() or "document" in description.lower() or "email" in description.lower() or "letter" in description.lower())

        entry = {
            "s3_key": s3_key,
            "filename": filename,
            "rekognition_labels": img["all_labels"],
            "weapon_labels": img["weapon_labels"],
            "has_doc_label": img["has_doc_label"],
            "ai_description": description,
            "likely_false_positive": is_false_positive,
        }
        descriptions.append(entry)

        status = "⚠️ FALSE POSITIVE" if is_false_positive else "✅ REAL"
        logger.info("  %s: %s", status, description[:120])
        time.sleep(0.5)  # Rate limit

    # Save results
    output = {
        "case_id": args.case_id,
        "total_weapon_images": len(weapon_images),
        "described": len(descriptions),
        "false_positives": sum(1 for d in descriptions if d["likely_false_positive"]),
        "descriptions": descriptions,
    }

    output_key = f"cases/{args.case_id}/rekognition-artifacts/weapon_ai_descriptions.json"
    s3.put_object(Bucket=BUCKET, Key=output_key, Body=json.dumps(output, indent=2).encode(), ContentType="application/json")
    # Also copy to combined case
    combined_key = output_key.replace(args.case_id, COMBINED_CASE)
    s3.put_object(Bucket=BUCKET, Key=combined_key, Body=json.dumps(output, indent=2).encode(), ContentType="application/json")

    print(f"\nResults: {len(descriptions)} images described")
    print(f"  False positives (redacted docs): {output['false_positives']}")
    print(f"  Potentially real: {len(descriptions) - output['false_positives']}")
    print(f"Saved to: {output_key}")


if __name__ == "__main__":
    main()
