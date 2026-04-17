"""Load Rekognition and photo-metadata into Neptune knowledge graph.

Reads photo-metadata/ and rekognition-output/ from the Epstein source bucket,
extracts person entities, locations, objects, and document references,
generates Neptune bulk CSV files, and loads via the bulk loader.
"""
import boto3
import csv
import io
import json
import re
import ssl
import time
import urllib.request
import uuid

REGION = "us-east-1"
SOURCE_BUCKET = "doj-cases-974220725866-us-east-1"
DATA_BUCKET = None  # Will be resolved
CASE_ID = "7f05e8d5-4492-4f19-8894-25367606db96"  # Main Epstein case
NEPTUNE_ENDPOINT = None  # Will be resolved from Lambda env
IAM_ROLE_ARN = None

# Quality filters
MIN_PERSON_NAME_LENGTH = 3
NOISE_WORDS = {"the", "a", "an", "of", "in", "on", "at", "to", "for", "and", "or", "is", "it",
               "this", "that", "with", "from", "by", "as", "be", "was", "are", "were", "been",
               "have", "has", "had", "do", "does", "did", "will", "would", "could", "should",
               "may", "might", "can", "shall", "not", "no", "yes", "ok", "good", "bad"}

# Label-to-entity-type mapping for Rekognition labels
LABEL_TYPE_MAP = {
    "person": {"person", "people", "human", "face", "head", "portrait", "man", "woman", "boy", "girl", "child", "adult"},
    "vehicle": {"car", "vehicle", "automobile", "truck", "van", "bus", "motorcycle", "bicycle",
                "boat", "yacht", "ship", "watercraft", "jet ski", "airplane", "aircraft", "helicopter", "jet"},
    "document": {"document", "text", "paper", "letter", "page", "book", "newspaper", "magazine", "receipt", "check",
                 "handwriting", "signature", "envelope", "folder", "file", "notebook", "diary", "calendar", "contract",
                 "passport", "id card", "license", "badge", "certificate", "map", "chart", "graph", "spreadsheet", "table"},
    "weapon": {"weapon", "gun", "pistol", "rifle", "knife", "sword"},
}
# Labels confirmed as false positives (redacted document bars, not real weapons)
# See: weapon_ai_descriptions.json — 20/20 confirmed false positives via Bedrock Claude Haiku
WEAPON_FALSE_POSITIVE_LABELS = {"Weapon", "Gun", "Rifle", "Pistol", "Knife", "Sword"}
COMBINED_CASE = "ed0b6c27-3b6b-4255-b9d0-efe8f4383a99"
DATA_LAKE_BUCKET = "research-analyst-data-lake-974220725866"


def map_label_type(label_name):
    """Map a Rekognition label to an entity type."""
    lower = label_name.lower()
    for etype, labels in LABEL_TYPE_MAP.items():
        if lower in labels:
            return etype
    return "artifact"


def is_quality_person(name):
    """Filter out OCR noise from person entity names."""
    if not name or len(name) < MIN_PERSON_NAME_LENGTH:
        return False
    # Skip single words that are common noise
    if name.lower() in NOISE_WORDS:
        return False
    # Skip all-numeric
    if name.replace(" ", "").replace("-", "").isdigit():
        return False
    # Skip very short single words (likely OCR fragments)
    words = name.split()
    if len(words) == 1 and len(name) < 4:
        return False
    # Skip if mostly non-alpha
    alpha_ratio = sum(1 for c in name if c.isalpha()) / max(len(name), 1)
    if alpha_ratio < 0.5:
        return False
    return True


def extract_locations_from_text(text):
    """Extract location-like patterns from document text."""
    locations = []
    # US address patterns
    addr_pattern = re.compile(r'\d+\s+(?:East|West|North|South|E\.|W\.|N\.|S\.)?\s*\d*\s*(?:st|nd|rd|th|Street|Avenue|Ave|Blvd|Drive|Dr|Road|Rd|Lane|Ln|Way|Place|Pl|Court|Ct)\b[^,]*(?:,\s*[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)?(?:,?\s*[A-Z]{2}\s*\d{5})?', re.IGNORECASE)
    for m in addr_pattern.finditer(text):
        addr = m.group().strip()
        if len(addr) > 10:
            locations.append(addr)

    # State patterns (City, ST)
    state_pattern = re.compile(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*),\s*([A-Z]{2})\b')
    for m in state_pattern.finditer(text):
        locations.append(f"{m.group(1)}, {m.group(2)}")

    return locations[:5]  # Cap at 5 per document


def resolve_infra():
    """Get Neptune endpoint, IAM role, and data bucket from Lambda config."""
    global NEPTUNE_ENDPOINT, IAM_ROLE_ARN, DATA_BUCKET
    lam = boto3.client("lambda", region_name=REGION)
    fn = lam.get_function_configuration(
        FunctionName="ResearchAnalystStack-IngestionGraphLoadLambda9C8CC-64fx1gSSh7Fg"
    )
    env = fn["Environment"]["Variables"]
    NEPTUNE_ENDPOINT = env.get("NEPTUNE_ENDPOINT", "")
    IAM_ROLE_ARN = env.get("NEPTUNE_IAM_ROLE_ARN", "")
    DATA_BUCKET = env.get("S3_DATA_BUCKET", env.get("S3_BUCKET_NAME", ""))
    print(f"Neptune: {NEPTUNE_ENDPOINT}")
    print(f"IAM Role: {IAM_ROLE_ARN}")
    print(f"Data Bucket: {DATA_BUCKET}")


def collect_visual_entities():
    """Read all photo-metadata and rekognition-output files, extract entities."""
    s3 = boto3.client("s3", region_name=REGION)
    entities = {}  # name -> {type, confidence, occurrence_count, source}
    doc_entities = []  # (doc_id, entity_name) pairs for edges

    # --- Process photo-metadata ---
    print("\nReading photo-metadata files...")
    paginator = s3.get_paginator("list_objects_v2")
    pm_count = 0
    pm_entities = 0

    for page in paginator.paginate(Bucket=SOURCE_BUCKET, Prefix="photo-metadata/"):
        for obj in page.get("Contents", []):
            if obj["Size"] < 100:
                continue
            try:
                body = s3.get_object(Bucket=SOURCE_BUCKET, Key=obj["Key"])["Body"].read().decode()
                data = json.loads(body)
                doc_id = obj["Key"].split("/")[-1].replace(".json", "")
                pm_count += 1

                # Extract person entities
                for person in data.get("personEntities", []):
                    if is_quality_person(person):
                        name = person.strip()
                        if name in entities:
                            entities[name]["occurrence_count"] += 1
                        else:
                            entities[name] = {"type": "person", "confidence": 0.7, "occurrence_count": 1, "source": "rekognition"}
                            pm_entities += 1
                        doc_entities.append((doc_id, name))

                # Extract locations from document text
                text = data.get("documentText", "") or ""
                for loc in extract_locations_from_text(text):
                    if loc in entities:
                        entities[loc]["occurrence_count"] += 1
                    else:
                        entities[loc] = {"type": "address", "confidence": 0.6, "occurrence_count": 1, "source": "rekognition_text"}
                        pm_entities += 1
                    doc_entities.append((doc_id, loc))

            except Exception:
                pass

        if pm_count % 500 == 0:
            print(f"  Processed {pm_count} photo-metadata files, {pm_entities} entities so far")

    print(f"  Total: {pm_count} files, {pm_entities} unique entities")

    # --- Process rekognition-output ---
    print("\nReading rekognition-output files...")
    rek_count = 0
    rek_entities = 0

    for page in paginator.paginate(Bucket=SOURCE_BUCKET, Prefix="rekognition-output/"):
        for obj in page.get("Contents", []):
            if obj["Size"] < 200:
                continue
            try:
                body = s3.get_object(Bucket=SOURCE_BUCKET, Key=obj["Key"])["Body"].read().decode()
                data = json.loads(body)
                doc_id = obj["Key"].split("/")[-1].replace(".json", "")
                rek_count += 1

                # Celebrities
                for celeb in data.get("celebrities", []):
                    name = celeb.get("Name", celeb.get("name", ""))
                    if name and is_quality_person(name):
                        conf = celeb.get("MatchConfidence", celeb.get("confidence", 90)) / 100.0
                        if name in entities:
                            entities[name]["occurrence_count"] += 1
                            entities[name]["confidence"] = max(entities[name]["confidence"], conf)
                        else:
                            entities[name] = {"type": "person", "confidence": conf, "occurrence_count": 1, "source": "rekognition_celebrity"}
                            rek_entities += 1
                        doc_entities.append((doc_id, name))

                # Labels (objects/scenes) — only high-confidence investigative labels
                investigative_labels = {"weapon", "gun", "knife", "drug", "currency", "money", "car", "vehicle",
                                       "phone", "computer", "laptop", "passport", "document", "boat", "airplane",
                                       "jewelry", "watch", "safe", "camera", "suitcase", "bag"}
                for label in data.get("labels", []):
                    lname = label.get("Name", label.get("name", ""))
                    if lname and lname.lower() in investigative_labels:
                        conf = label.get("Confidence", label.get("confidence", 80)) / 100.0
                        if conf >= 0.7:
                            if lname in entities:
                                entities[lname]["occurrence_count"] += 1
                            else:
                                entities[lname] = {"type": "artifact", "confidence": conf, "occurrence_count": 1, "source": "rekognition_label"}
                                rek_entities += 1
                            doc_entities.append((doc_id, lname))

                # Text detected in images
                for text_item in data.get("text", []):
                    detected = text_item.get("DetectedText", text_item.get("text", ""))
                    if detected and len(detected) > 5:
                        # Look for phone numbers
                        phone_match = re.search(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', detected)
                        if phone_match:
                            phone = phone_match.group()
                            if phone in entities:
                                entities[phone]["occurrence_count"] += 1
                            else:
                                entities[phone] = {"type": "phone_number", "confidence": 0.8, "occurrence_count": 1, "source": "rekognition_text"}
                                rek_entities += 1
                            doc_entities.append((doc_id, phone))

            except Exception:
                pass

        if rek_count % 500 == 0 and rek_count > 0:
            print(f"  Processed {rek_count} rekognition-output files, {rek_entities} entities so far")

    print(f"  Total: {rek_count} files, {rek_entities} unique entities")
    print(f"\nCombined: {len(entities)} unique entities, {len(doc_entities)} entity-document links")

    return entities, doc_entities


def collect_label_entities(case_id=None, exclude_weapons=False):
    """Read batch_labels_details.json from the data lake bucket and extract visual entities.

    Creates Visual_Entity nodes per unique label, maps labels to entity types,
    builds DETECTED_IN edges to source documents, and co-occurrence edges.
    
    Args:
        case_id: Override case ID
        exclude_weapons: If True, skip all weapon-type labels (confirmed false positives)
    """
    cid = case_id or CASE_ID
    s3 = boto3.client("s3", region_name=REGION)
    entities = {}  # label_name -> {type, confidence_sum, confidence_count, occurrence_count, source}
    doc_entities = []  # (doc_id, label_name) pairs for edges

    details_key = f"cases/{cid}/rekognition-artifacts/batch_labels_details.json"
    print(f"\nReading label data from s3://{DATA_LAKE_BUCKET}/{details_key}")

    try:
        resp = s3.get_object(Bucket=DATA_LAKE_BUCKET, Key=details_key)
        details = json.loads(resp["Body"].read().decode())
    except Exception as e:
        print(f"ERROR: Could not read {details_key}: {e}")
        return {}, []

    print(f"Found {len(details)} images with labels")

    for item in details:
        s3_key = item.get("s3_key", "")
        filename = s3_key.split("/")[-1] if s3_key else ""
        # Parse source_document_id from filename: {doc_id}_page{N}_img{M}.jpg
        doc_id = filename.split("_page")[0] if "_page" in filename else ""

        for label in item.get("labels", []):
            name = label.get("name", "")
            conf = label.get("confidence", 0)
            if not name:
                continue

            # Skip weapon false positives if requested
            if exclude_weapons and name in WEAPON_FALSE_POSITIVE_LABELS:
                continue

            if name in entities:
                entities[name]["confidence_sum"] += conf
                entities[name]["confidence_count"] += 1
                entities[name]["occurrence_count"] += 1
            else:
                entities[name] = {
                    "type": map_label_type(name),
                    "confidence_sum": conf,
                    "confidence_count": 1,
                    "occurrence_count": 1,
                    "source": "rekognition_label",
                }

            if doc_id:
                doc_entities.append((doc_id, name))

    # Compute average confidence
    for name, ent in entities.items():
        ent["confidence"] = round(ent["confidence_sum"] / max(ent["confidence_count"], 1) / 100, 4)

    print(f"Collected {len(entities)} unique visual entities, {len(doc_entities)} entity-document links")
    return entities, doc_entities


def generate_label_csv_and_load(entities, doc_entities, case_id=None):
    """Generate Neptune bulk CSV for Visual_Entity nodes and load into Neptune."""
    cid = case_id or CASE_ID
    s3 = boto3.client("s3", region_name=REGION)
    bucket = DATA_BUCKET or DATA_LAKE_BUCKET
    label = f"VisualEntity_{cid}"
    batch_id = uuid.uuid4().hex[:12]

    # --- Nodes CSV ---
    nodes_buf = io.StringIO()
    writer = csv.writer(nodes_buf)
    writer.writerow(["~id", "~label", "entity_type:String", "canonical_name:String",
                      "confidence:Double", "occurrence_count:Int", "case_file_id:String", "source:String"])

    node_ids = {}
    for name, ent in entities.items():
        node_id = f"{cid}_visual_{name}"
        node_ids[name] = node_id
        writer.writerow([node_id, label, ent["type"], name, ent["confidence"],
                         ent["occurrence_count"], cid, ent["source"]])

    nodes_key = f"neptune-bulk-load/{cid}/rek_labels_{batch_id}_nodes.csv"
    s3.put_object(Bucket=bucket, Key=nodes_key, Body=nodes_buf.getvalue().encode("utf-8"))
    print(f"\nUploaded nodes CSV: {nodes_key} ({len(entities)} visual entities)")

    # --- Edges CSV (DETECTED_IN + CO_OCCURS_WITH) ---
    edges_buf = io.StringIO()
    writer = csv.writer(edges_buf)
    writer.writerow(["~id", "~from", "~to", "~label", "confidence:Double", "case_file_id:String"])

    # DETECTED_IN edges: unique (label, doc_id) pairs
    seen_detected = set()
    detected_count = 0
    for doc_id, label_name in doc_entities:
        if label_name not in node_ids:
            continue
        edge_key = (label_name, doc_id)
        if edge_key in seen_detected:
            continue
        seen_detected.add(edge_key)
        edge_id = f"{cid}_detected_{label_name}_{doc_id}"
        # Target is the document node — use the existing document node ID format
        doc_node_id = f"{cid}_document_{doc_id}"
        writer.writerow([edge_id, node_ids[label_name], doc_node_id, "DETECTED_IN",
                         entities[label_name]["confidence"], cid])
        detected_count += 1

    # CO_OCCURS_WITH edges: labels sharing the same source document
    from collections import defaultdict
    doc_to_labels = defaultdict(set)
    for doc_id, label_name in doc_entities:
        if label_name in node_ids and doc_id:
            doc_to_labels[doc_id].add(label_name)

    seen_cooccur = {}
    cooccur_count = 0
    for doc_id, label_set in doc_to_labels.items():
        label_list = sorted(label_set)
        for i, l1 in enumerate(label_list):
            for l2 in label_list[i + 1:]:
                pair = (l1, l2)
                if pair not in seen_cooccur:
                    seen_cooccur[pair] = 0
                seen_cooccur[pair] += 1

    for (l1, l2), count in seen_cooccur.items():
        edge_id = f"{cid}_cooccur_{l1}_{l2}"
        writer.writerow([edge_id, node_ids[l1], node_ids[l2], "CO_OCCURS_WITH",
                         count, cid])
        cooccur_count += 1

    edges_key = f"neptune-bulk-load/{cid}/rek_labels_{batch_id}_edges.csv"
    s3.put_object(Bucket=bucket, Key=edges_key, Body=edges_buf.getvalue().encode("utf-8"))
    print(f"Uploaded edges CSV: {edges_key} ({detected_count} DETECTED_IN + {cooccur_count} CO_OCCURS_WITH)")

    # --- Trigger Neptune bulk loader ---
    if not IAM_ROLE_ARN or not NEPTUNE_ENDPOINT:
        print("No Neptune endpoint or IAM role — skipping bulk load trigger")
        print("CSVs are in S3 and can be loaded manually")
        return

    loader_url = f"https://{NEPTUNE_ENDPOINT}:8182/loader"
    ctx = ssl.create_default_context()

    for label_name, s3_key in [("nodes", nodes_key), ("edges", edges_key)]:
        payload = json.dumps({
            "source": f"s3://{bucket}/{s3_key}",
            "format": "csv",
            "iamRoleArn": IAM_ROLE_ARN,
            "region": REGION,
            "failOnError": "FALSE",
            "parallelism": "MEDIUM",
            "updateSingleCardinalityProperties": "TRUE",
        }).encode("utf-8")
        req = urllib.request.Request(loader_url, data=payload, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
                body = json.loads(resp.read().decode())
                load_id = body.get("payload", {}).get("loadId", "")
                print(f"Bulk load {label_name} started: {load_id}")
                # Poll for completion
                for _ in range(60):
                    poll_req = urllib.request.Request(f"{loader_url}/{load_id}")
                    with urllib.request.urlopen(poll_req, context=ctx, timeout=15) as poll_resp:
                        poll_body = json.loads(poll_resp.read().decode())
                        status = poll_body.get("payload", {}).get("overallStatus", {}).get("status", "")
                        if status == "LOAD_COMPLETED":
                            print(f"  {label_name} load completed")
                            break
                        if status in ("LOAD_FAILED", "LOAD_CANCELLED_BY_USER"):
                            print(f"  {label_name} load FAILED: {poll_body}")
                            break
                    time.sleep(5)
        except Exception as e:
            print(f"Bulk load {label_name} error: {e}")


def sync_artifacts_to_combined(case_id, combined_case_id):
    """Copy Rekognition artifacts from main case to combined case in S3."""
    s3 = boto3.client("s3", region_name=REGION)
    artifacts = ["batch_labels_summary.json", "batch_labels_details.json",
                 "face_crop_metadata.json", "face_match_results.json"]
    for artifact in artifacts:
        src_key = f"cases/{case_id}/rekognition-artifacts/{artifact}"
        dst_key = f"cases/{combined_case_id}/rekognition-artifacts/{artifact}"
        try:
            s3.copy_object(Bucket=DATA_LAKE_BUCKET,
                           CopySource={"Bucket": DATA_LAKE_BUCKET, "Key": src_key},
                           Key=dst_key)
            print(f"  Synced {artifact}")
        except Exception as e:
            print(f"  Skip {artifact}: {e}")


def generate_csv_and_load(entities, doc_entities):
    """Generate Neptune bulk CSV and trigger bulk loader."""
    s3 = boto3.client("s3", region_name=REGION)
    label = f"Entity_{CASE_ID}"
    batch_id = uuid.uuid4().hex[:12]

    # --- Nodes CSV ---
    nodes_buf = io.StringIO()
    writer = csv.writer(nodes_buf)
    writer.writerow(["~id", "~label", "entity_type:String", "canonical_name:String",
                      "confidence:Double", "occurrence_count:Int", "case_file_id:String", "source:String"])

    for name, ent in entities.items():
        node_id = f"{CASE_ID}_{ent['type']}_{name}"
        writer.writerow([node_id, label, ent["type"], name, ent["confidence"],
                         ent["occurrence_count"], CASE_ID, ent["source"]])

    nodes_key = f"neptune-bulk-load/{CASE_ID}/rek_{batch_id}_nodes.csv"
    s3.put_object(Bucket=DATA_BUCKET, Key=nodes_key, Body=nodes_buf.getvalue().encode("utf-8"))
    print(f"\nUploaded nodes CSV: {nodes_key} ({len(entities)} entities)")

    # --- Edges CSV ---
    edges_buf = io.StringIO()
    writer = csv.writer(edges_buf)
    writer.writerow(["~id", "~from", "~to", "~label", "relationship_type:String",
                      "confidence:Double", "case_file_id:String"])

    # Build node ID lookup
    node_ids = {}
    for name, ent in entities.items():
        node_ids[name] = f"{CASE_ID}_{ent['type']}_{name}"

    # Create document nodes and edges
    doc_nodes = set()
    seen_edges = set()
    edge_count = 0

    for doc_id, entity_name in doc_entities:
        if entity_name not in node_ids:
            continue
        # Create edge: entity APPEARS_IN document
        edge_key = (entity_name, doc_id)
        if edge_key in seen_edges:
            continue
        seen_edges.add(edge_key)

        # We don't create document nodes (they'd need a different label)
        # Instead, connect entities that co-occur in the same document
        pass

    # Create co-occurrence edges: entities that appear in the same document
    from collections import defaultdict
    doc_to_entities = defaultdict(set)
    for doc_id, entity_name in doc_entities:
        if entity_name in node_ids:
            doc_to_entities[doc_id].add(entity_name)

    for doc_id, ent_set in doc_to_entities.items():
        ent_list = sorted(ent_set)
        for i, e1 in enumerate(ent_list):
            for e2 in ent_list[i+1:]:
                edge_key = (e1, e2)
                if edge_key in seen_edges:
                    continue
                seen_edges.add(edge_key)
                edge_id = f"{CASE_ID}_rek_edge_{uuid.uuid4().hex[:8]}"
                writer.writerow([edge_id, node_ids[e1], node_ids[e2], "RELATED_TO",
                                 "co-occurrence", 0.6, CASE_ID])
                edge_count += 1

    edges_key = f"neptune-bulk-load/{CASE_ID}/rek_{batch_id}_edges.csv"
    s3.put_object(Bucket=DATA_BUCKET, Key=edges_key, Body=edges_buf.getvalue().encode("utf-8"))
    print(f"Uploaded edges CSV: {edges_key} ({edge_count} edges)")

    # --- Trigger Neptune bulk loader ---
    if not IAM_ROLE_ARN or not NEPTUNE_ENDPOINT:
        print("No Neptune endpoint or IAM role — skipping bulk load")
        return

    loader_url = f"https://{NEPTUNE_ENDPOINT}:8182/loader"
    ctx = ssl.create_default_context()

    for label_name, s3_key in [("nodes", nodes_key), ("edges", edges_key)]:
        payload = json.dumps({
            "source": f"s3://{DATA_BUCKET}/{s3_key}",
            "format": "csv",
            "iamRoleArn": IAM_ROLE_ARN,
            "region": REGION,
            "failOnError": "FALSE",
            "parallelism": "MEDIUM",
            "updateSingleCardinalityProperties": "TRUE",
        }).encode("utf-8")
        req = urllib.request.Request(loader_url, data=payload, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
                body = json.loads(resp.read().decode())
                load_id = body.get("payload", {}).get("loadId", "")
                print(f"Bulk load {label_name} started: {load_id}")

                # Poll for completion
                for _ in range(60):
                    poll_req = urllib.request.Request(f"{loader_url}/{load_id}")
                    with urllib.request.urlopen(poll_req, context=ctx, timeout=15) as poll_resp:
                        poll_body = json.loads(poll_resp.read().decode())
                        status = poll_body.get("payload", {}).get("overallStatus", {}).get("status", "")
                        if status == "LOAD_COMPLETED":
                            print(f"  {label_name} load completed")
                            break
                        if status in ("LOAD_FAILED", "LOAD_CANCELLED_BY_USER"):
                            print(f"  {label_name} load FAILED")
                            break
                    time.sleep(5)
        except Exception as e:
            print(f"Bulk load {label_name} error: {e}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Load Rekognition data into Neptune")
    parser.add_argument("--mode", choices=["rekognition", "labels", "all"], default="rekognition",
                        help="rekognition=existing photo-metadata, labels=batch label data, all=both")
    parser.add_argument("--case-id", default=CASE_ID)
    parser.add_argument("--sync-combined", action="store_true",
                        help="Sync artifacts to combined case after loading")
    parser.add_argument("--exclude-weapons", action="store_true",
                        help="Exclude weapon/gun/rifle labels (confirmed false positives from redacted docs)")
    args = parser.parse_args()

    resolve_infra()

    if args.mode in ("rekognition", "all"):
        print("\n=== Mode: rekognition (photo-metadata + rekognition-output) ===")
        entities, doc_entities = collect_visual_entities()
        type_counts = {}
        for name, ent in entities.items():
            t = ent["type"]
            type_counts[t] = type_counts.get(t, 0) + 1
        print("\nEntity type breakdown:")
        for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
            print(f"  {t}: {c}")
        top = sorted(entities.items(), key=lambda x: -x[1]["occurrence_count"])[:15]
        print("\nTop 15 entities by occurrence:")
        for name, ent in top:
            print(f"  {name} ({ent['type']}) — {ent['occurrence_count']} occurrences, source: {ent['source']}")
        generate_csv_and_load(entities, doc_entities)

    if args.mode in ("labels", "all"):
        print("\n=== Mode: labels (batch Rekognition label data) ===")
        if args.exclude_weapons:
            print("  Excluding weapon false positives: " + ", ".join(sorted(WEAPON_FALSE_POSITIVE_LABELS)))
        entities, doc_entities = collect_label_entities(args.case_id, exclude_weapons=args.exclude_weapons)
        if entities:
            type_counts = {}
            for name, ent in entities.items():
                t = ent["type"]
                type_counts[t] = type_counts.get(t, 0) + 1
            print("\nVisual entity type breakdown:")
            for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
                print(f"  {t}: {c}")
            top = sorted(entities.items(), key=lambda x: -x[1]["occurrence_count"])[:15]
            print("\nTop 15 visual entities by occurrence:")
            for name, ent in top:
                print(f"  {name} ({ent['type']}) — {ent['occurrence_count']} occurrences")
            generate_label_csv_and_load(entities, doc_entities, args.case_id)

    if args.sync_combined:
        print("\n=== Syncing artifacts to combined case ===")
        sync_artifacts_to_combined(args.case_id, COMBINED_CASE)

    print("\nDone!")


if __name__ == "__main__":
    main()
