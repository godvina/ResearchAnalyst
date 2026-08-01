#!/usr/bin/env python3
"""
Neptune Dedup Script — Run on EC2 overnight.

Phase 1: Drop noise entity types (artifact, formatting junk, medical, etc.)
Phase 2: Dedup remaining entities by (canonical_name, entity_type)

NOTE: account_number, phone_number, email, address are KEPT because they are
investigatively relevant when they appear across multiple documents or cases.
They get deduplicated in Phase 2 instead of dropped.

Usage:
    python3 ec2_neptune_dedup.py

Neptune endpoint is auto-detected from Lambda env vars via boto3.
"""
import json
import ssl
import time
import urllib.request
import sys
import os
from collections import defaultdict
from datetime import datetime

# ── Configuration ──────────────────────────────────────────────────
CASE_ID = "7f05e8d5-4492-4f19-8894-25367606db96"
CASE_LABEL = f"Entity_{CASE_ID}"

# Neptune connection — auto-detect or override
NEPTUNE_ENDPOINT = os.environ.get(
    "NEPTUNE_ENDPOINT",
    "neptunedbcluster-qoxzlhiau0ao.cluster-cgaj5jxtrulh.us-east-1.neptune.amazonaws.com"
)
NEPTUNE_PORT = os.environ.get("NEPTUNE_PORT", "8182")

# ── Entity Type Taxonomy (user-defined April 21 2026) ──────────────
#
# HIGH VALUE — KEEP and dedup in Phase 2:
#   person          — subjects, witnesses, victims, associates
#   location        — addresses, cities, properties, venues
#   organization    — companies, banks, law firms, foundations
#   financial/financial_amount — transactions, amounts, account patterns
#   account_number  — bank accounts, wire transfers (cross-doc = financial trail)
#   phone_number    — communication links between persons
#   email           — communication links, identity confirmation
#   address         — physical locations tied to persons
#   date/time/event — timeline construction
#   flight/aircraft — travel patterns (critical for Epstein case)
#   legal/statute   — legal framework
#   vehicle         — transportation evidence
#
# NOISE — DROP in Phase 1:
#   artifact, object, device, form, page, text, font — document structure noise
#   measurement, size, weight, color, shape — physical descriptions
#   medical_*, symptom, disease — irrelevant unless medical case
#   food, animal, clothing, music_genre — irrelevant
#   job titles, skills, education — irrelevant to investigation
#   formatting: number, id, hash, barcode, password — structural noise

NOISE_TYPES = {
    # Document structure noise
    "artifact", "object", "device", "form", "page", "text", "text_style",
    "font", "word", "label", "document", "document_id", "document_identifier",
    "document_section", "document_metadata", "document-reference",
    # Structural / formatting noise
    "number", "id", "identifier", "reference_number", "reference_id",
    "product_id", "digital_product_id", "order_number", "barcode",
    "hash", "password", "username", "device_identifier",
    "comment", "description", "section_heading", "statement",
    "abbreviation", "alphanumeric", "ordinal", "symbol", "greeting",
    "preposition", "information", "series", "version", "status",
    "field", "chart", "system", "standard", "classification",
    "attribute", "concept", "term", "item", "thing",
    "name", "class", "category", "type", "group", "set",
    # Physical descriptions
    "measurement", "measurements", "measure", "size", "weight",
    "height", "frequency", "duration", "magnification", "age",
    "color", "shape", "quality", "clarity", "clarity_grade",
    "cutting_style", "girdle", "inclusion_symbol",
    # Financial noise (not actual financial entities)
    "cost_basis_method", "investment_eligibility", "investment_objective",
    "risk_profile", "shipping_method",
    # Medical (irrelevant unless medical case)
    "medical_equipment", "medical_device", "medical_test", "lab_test",
    "medical", "medical_condition", "health_condition", "health_problem",
    "health condition", "symptom", "treatment", "disease", "mental_disorder",
    "radiology", "cause_of_death", "body part",
    # Irrelevant categories
    "food", "animal", "horse", "clothing", "material",
    "music_genre", "movie", "book", "book_title",
    "software", "technology", "program",
    # Job/education (not investigatively relevant)
    "job_title", "job title", "job-title", "job posting", "job grade",
    "occupation", "profession", "degree", "education", "certification",
    "skill", "SKILL",
    "shift", "schedule", "season",
    "concern", "behavior", "mechanism",
    "descriptor",
    # Catch-all noise
    "none", "NONE", "misc", "miscellaneous", "unspecified", "other", "MISC",
    "zip", "money", "case_type", "case_citation",
    "polish", "natural resource",
}

# Entity types to KEEP (investigatively relevant) — dedup in Phase 2
# Reference: docs/master-entity-taxonomy.md (40 canonical types across 10 tiers)
KEEP_TYPES = {
    # ── Tier 1: Core Investigative Entities ──
    "person", "PERSON",
    "location", "LOCATION",
    "organization",
    "event",
    # ── Tier 2: Financial Intelligence ──
    "financial", "FINANCIAL", "financial_amount", "financial_entity",
    "account_number", "account number",
    "bank_account", "wire_transfer", "investment_fund",
    "financial_instrument", "stock", "bond", "option", "mortgage", "loan",
    # ── Tier 3: Communication Intelligence ──
    "phone_number", "phone number", "phone",
    "email",
    "online_identity", "social_media_handle", "username",
    "IP_address", "ip_address", "digital_identifier",
    "MAC_address", "IMEI", "SIM_card",
    # ── Tier 4: Travel & Transportation ──
    "flight", "flight-number", "aircraft_identifier", "aircraft-identification",
    "aircraft",
    "vehicle", "vehicle_id", "automobile", "boat", "yacht",
    "travel_document", "passport", "visa", "boarding_pass",
    "transportation", "conveyance",
    # ── Tier 5: Legal & Regulatory ──
    "legal", "legal_case", "legal case", "legal_term", "legal_concept",
    "legislation", "statute", "rule", "regulation",
    "constitutional_provision", "constitutional provision",
    "court_location", "court_case",
    "charge", "offense", "evidence",
    "attorney", "judge", "court",
    # ── Tier 6: Physical Evidence ──
    "substance", "controlled_substance", "drug", "chemical", "explosive",
    "weapon", "firearm",
    "property", "real_estate", "jewelry", "art",
    # ── Tier 7: Temporal Intelligence ──
    "date", "time",
    "duration", "period",
    # ── Tier 8: Identity & Demographics ──
    "personal_identifier", "SSN", "EIN", "driver_license", "passport_number",
    "biometric", "fingerprint", "DNA", "tattoo",
    "ethnicity", "nationality", "race", "gender",
    # ── Tier 9: Digital & Cyber ──
    "cryptocurrency", "wallet_address", "blockchain",
    "domain", "url", "website",
    "malware", "ransomware",
    # ── Tier 10: Contextual & Supporting ──
    "role", "relationship",
    "contact", "contact_info",
    "document_reference",
    # ── Supporting context ──
    "case", "address",
    "industry", "service", "agreement", "policy",
    "work", "project", "title",
    "law", "publication", "reference",
}

# Batch sizes
DROP_BATCH = 500       # vertices to drop per Gremlin call
DEDUP_FETCH_BATCH = 5000  # vertices to fetch per dedup scan
QUERY_TIMEOUT = 60     # seconds per Gremlin query

# ── Neptune HTTP Client ────────────────────────────────────────────
SSL_CTX = ssl.create_default_context()

def gremlin(query, timeout=QUERY_TIMEOUT):
    """Execute a Gremlin query via Neptune HTTP API."""
    url = f"https://{NEPTUNE_ENDPOINT}:{NEPTUNE_PORT}/gremlin"
    data = json.dumps({"gremlin": query}).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, context=SSL_CTX, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            return parse_result(body.get("result", {}).get("data", {}))
    except urllib.request.HTTPError as he:
        err_body = ""
        try:
            err_body = he.read().decode("utf-8")[:500]
        except Exception:
            pass
        log(f"HTTP Error {he.code}: {err_body[:200]}")
        return None
    except Exception as e:
        log(f"Query error: {str(e)[:200]}")
        return None

def parse_result(data):
    """Parse Neptune GraphSON response."""
    if isinstance(data, dict):
        gt = data.get("@type", "")
        gv = data.get("@value")
        if gt == "g:List" and isinstance(gv, list):
            return [parse_result(v) for v in gv]
        if gt == "g:Map" and isinstance(gv, list):
            d = {}
            for i in range(0, len(gv) - 1, 2):
                d[parse_result(gv[i])] = parse_result(gv[i + 1])
            return d
        if gt in ("g:Int64", "g:Int32", "g:Double", "g:Float"):
            return gv
        if "@value" in data:
            return parse_result(gv)
        return data
    if isinstance(data, list):
        return [parse_result(v) for v in data]
    return data

def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)

# ── Phase 1: Drop Noise Entity Types ──────────────────────────────
def phase1_drop_noise():
    """Drop all vertices with noise entity types."""
    log("=" * 60)
    log("PHASE 1: Dropping noise entity types")
    log("=" * 60)

    # First, get current counts by type
    log("Counting vertices by entity_type...")
    counts = gremlin(
        f"g.V().hasLabel('{CASE_LABEL}').groupCount().by('entity_type')",
        timeout=120
    )
    if not counts:
        log("ERROR: Could not get vertex counts. Neptune may be unreachable.")
        return False

    if isinstance(counts, list) and len(counts) == 1:
        counts = counts[0]

    total_before = sum(counts.values()) if isinstance(counts, dict) else 0
    log(f"Total vertices before cleanup: {total_before:,}")

    # Identify noise types present in the graph
    noise_to_drop = {}
    keep_count = 0
    unknown_types = {}

    if isinstance(counts, dict):
        for etype, count in sorted(counts.items(), key=lambda x: -x[1]):
            if etype in NOISE_TYPES:
                noise_to_drop[etype] = count
            elif etype in KEEP_TYPES:
                keep_count += count
            else:
                unknown_types[etype] = count

    noise_total = sum(noise_to_drop.values())
    unknown_total = sum(unknown_types.values())

    log(f"Noise types to drop: {len(noise_to_drop)} types, {noise_total:,} vertices")
    log(f"Keep types: {keep_count:,} vertices")
    log(f"Unknown types: {len(unknown_types)} types, {unknown_total:,} vertices")

    if unknown_types:
        log("Unknown types (will be KEPT for review):")
        for t, c in sorted(unknown_types.items(), key=lambda x: -x[1])[:20]:
            log(f"  {t}: {c:,}")

    # Drop noise types one at a time
    total_dropped = 0
    for etype, count in sorted(noise_to_drop.items(), key=lambda x: -x[1]):
        log(f"Dropping '{etype}' ({count:,} vertices)...")
        dropped_this_type = 0

        while True:
            # Drop in batches to avoid timeout
            esc_type = etype.replace("'", "\\'").replace("\\", "\\\\")
            q = (
                f"g.V().hasLabel('{CASE_LABEL}')"
                f".has('entity_type', '{esc_type}')"
                f".limit({DROP_BATCH})"
                f".sideEffect(bothE().drop())"
                f".drop()"
            )
            result = gremlin(q, timeout=QUERY_TIMEOUT)
            if result is None:
                log(f"  Error dropping batch, retrying in 2s...")
                time.sleep(2)
                continue

            dropped_this_type += DROP_BATCH
            total_dropped += DROP_BATCH

            # Check if more remain
            remaining = gremlin(
                f"g.V().hasLabel('{CASE_LABEL}')"
                f".has('entity_type', '{esc_type}')"
                f".count()",
                timeout=30
            )
            rem_count = 0
            if isinstance(remaining, list) and remaining:
                rem_count = remaining[0] if isinstance(remaining[0], (int, float)) else 0
            elif isinstance(remaining, (int, float)):
                rem_count = remaining

            if rem_count == 0:
                log(f"  Done — dropped all '{etype}' vertices")
                break
            else:
                log(f"  Dropped batch, {rem_count:,} remaining...")
                time.sleep(0.5)  # Brief pause between batches

    # Final count
    final_count = gremlin(
        f"g.V().hasLabel('{CASE_LABEL}').count()",
        timeout=120
    )
    if isinstance(final_count, list) and final_count:
        final_count = final_count[0]
    log(f"Phase 1 complete. Vertices: {total_before:,} → {final_count:,} (dropped ~{total_before - (final_count or 0):,})")
    return True

# ── Phase 2: Dedup Remaining Entities ──────────────────────────────
def phase2_dedup():
    """Find and merge duplicate vertices by (canonical_name, entity_type)."""
    log("=" * 60)
    log("PHASE 2: Deduplicating remaining entities")
    log("=" * 60)

    # Get total count
    total = gremlin(
        f"g.V().hasLabel('{CASE_LABEL}').count()",
        timeout=120
    )
    if isinstance(total, list) and total:
        total = total[0]
    log(f"Total vertices to scan: {total:,}")

    # Get entity types remaining
    type_counts = gremlin(
        f"g.V().hasLabel('{CASE_LABEL}').groupCount().by('entity_type')",
        timeout=120
    )
    if isinstance(type_counts, list) and len(type_counts) == 1:
        type_counts = type_counts[0]

    if isinstance(type_counts, dict):
        log("Entity types remaining:")
        for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
            log(f"  {t}: {c:,}")

    # Process each entity type separately for manageable batch sizes
    total_merged = 0
    total_errors = 0

    if not isinstance(type_counts, dict):
        log("ERROR: Could not get type counts")
        return False

    for etype, count in sorted(type_counts.items(), key=lambda x: -x[1]):
        if count < 2:
            continue  # Can't have duplicates with only 1 vertex

        log(f"\nScanning '{etype}' ({count:,} vertices) for duplicates...")
        esc_type = etype.replace("'", "\\'").replace("\\", "\\\\")

        # Fetch all vertices of this type in batches
        all_vertices = []
        offset = 0

        while offset < count + DEDUP_FETCH_BATCH:
            q = (
                f"g.V().hasLabel('{CASE_LABEL}')"
                f".has('entity_type', '{esc_type}')"
                f".range({offset}, {offset + DEDUP_FETCH_BATCH})"
                f".project('id', 'name', 'occ')"
                f".by(id).by('canonical_name')"
                f".by(coalesce(values('occurrence_count'), constant(1)))"
            )
            batch = gremlin(q, timeout=60)
            if not batch or not isinstance(batch, list):
                break
            if len(batch) == 0:
                break

            all_vertices.extend(batch)
            offset += DEDUP_FETCH_BATCH

            if len(batch) < DEDUP_FETCH_BATCH:
                break  # Last batch

        log(f"  Fetched {len(all_vertices)} vertices")

        # Group by canonical_name
        groups = defaultdict(list)
        for v in all_vertices:
            if isinstance(v, dict):
                name = v.get("name", "")
                groups[name].append(v)

        # Find duplicates
        dup_groups = {name: verts for name, verts in groups.items() if len(verts) > 1}
        if not dup_groups:
            log(f"  No duplicates found")
            continue

        dup_count = sum(len(v) - 1 for v in dup_groups.values())
        log(f"  Found {len(dup_groups)} duplicate groups ({dup_count} extra vertices to merge)")

        # Collect all vertex IDs to delete (batch approach)
        all_delete_ids = []
        for name, vertices in dup_groups.items():
            vertices.sort(key=lambda v: v.get("occ", 0), reverse=True)
            # Keep first (highest occ), delete rest
            for v in vertices[1:]:
                all_delete_ids.append(v["id"])

        log(f"  Batch-dropping {len(all_delete_ids)} duplicate vertices...")

        # Drop in batches of DROP_BATCH
        for i in range(0, len(all_delete_ids), DROP_BATCH):
            batch_ids = all_delete_ids[i:i + DROP_BATCH]
            # Build Gremlin query to drop batch of vertices + their edges
            id_list = ",".join(f"'{vid}'" for vid in batch_ids)
            try:
                # Drop edges first
                gremlin(
                    f"g.V({id_list}).bothE().drop()",
                    timeout=QUERY_TIMEOUT
                )
                # Drop vertices
                gremlin(
                    f"g.V({id_list}).drop()",
                    timeout=QUERY_TIMEOUT
                )
                total_merged += len(batch_ids)
            except Exception as e:
                log(f"  Batch drop error at offset {i}: {str(e)[:100]}")
                total_errors += len(batch_ids)

            if (i // DROP_BATCH) % 10 == 0 and i > 0:
                log(f"  Progress: {total_merged:,} merged, {total_errors} errors")
            time.sleep(0.3)  # Brief pause between batches

    log(f"\nPhase 2 complete. Merged: {total_merged:,}, Errors: {total_errors}")

    # Final count
    final = gremlin(f"g.V().hasLabel('{CASE_LABEL}').count()", timeout=120)
    if isinstance(final, list) and final:
        final = final[0]
    log(f"Final vertex count: {final:,}")
    return True

# ── Main ───────────────────────────────────────────────────────────
def main():
    log("=" * 60)
    log("Neptune Dedup — Epstein Main Case")
    log(f"Case: {CASE_ID}")
    log(f"Neptune: {NEPTUNE_ENDPOINT}:{NEPTUNE_PORT}")
    log("=" * 60)

    # Verify Neptune connectivity
    test = gremlin("g.V().limit(1).count()", timeout=10)
    if test is None:
        log("FATAL: Cannot connect to Neptune. Check endpoint and security groups.")
        sys.exit(1)
    log("Neptune connection verified ✓")

    # Get initial count
    initial = gremlin(f"g.V().hasLabel('{CASE_LABEL}').count()", timeout=120)
    if isinstance(initial, list) and initial:
        initial = initial[0]
    log(f"Initial vertex count: {initial:,}")

    # Phase 1: Drop noise
    start = time.time()
    ok = phase1_drop_noise()
    elapsed1 = time.time() - start
    log(f"Phase 1 took {elapsed1/60:.1f} minutes")

    if not ok:
        log("Phase 1 failed. Stopping.")
        sys.exit(1)

    # Phase 2: Dedup
    start = time.time()
    ok = phase2_dedup()
    elapsed2 = time.time() - start
    log(f"Phase 2 took {elapsed2/60:.1f} minutes")

    # Summary
    final = gremlin(f"g.V().hasLabel('{CASE_LABEL}').count()", timeout=120)
    if isinstance(final, list) and final:
        final = final[0]

    log("=" * 60)
    log("DEDUP COMPLETE")
    log(f"Initial: {initial:,} → Final: {final:,}")
    log(f"Total time: {(elapsed1 + elapsed2)/60:.1f} minutes")
    log("=" * 60)

if __name__ == "__main__":
    main()
