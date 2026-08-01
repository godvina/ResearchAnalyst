#!/usr/bin/env python3
"""
Neptune Re-Sync Script — Aurora → Neptune with Master Taxonomy Filter.

Reads entities from Aurora, filters by the master entity taxonomy and quality
rules, then upserts into Neptune using fold/coalesce pattern (no duplicates).

Run on EC2 after the dedup script completes.

Usage:
    python3 ec2_neptune_resync.py [--case-id CASE_ID] [--dry-run]
"""
import json
import ssl
import time
import re
import urllib.request
import sys
import os
import boto3
from datetime import datetime

# ── Configuration ──────────────────────────────────────────────────
CASE_ID = os.environ.get("CASE_ID", "7f05e8d5-4492-4f19-8894-25367606db96")
CASE_LABEL = f"Entity_{CASE_ID}"
LAMBDA_NAME = "ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq"
REGION = "us-east-1"

NEPTUNE_ENDPOINT = os.environ.get(
    "NEPTUNE_ENDPOINT",
    "neptunedbcluster-qoxzlhiau0ao.cluster-cgaj5jxtrulh.us-east-1.neptune.amazonaws.com"
)
NEPTUNE_PORT = os.environ.get("NEPTUNE_PORT", "8182")

DRY_RUN = "--dry-run" in sys.argv
PAGE_SIZE = 5000
GREMLIN_TIMEOUT = 30
MIN_OCCURRENCE_COUNT = 1  # Load all entities regardless of occurrence

# ── Master Entity Taxonomy — KEEP types ────────────────────────────
# Reference: docs/master-entity-taxonomy.md
KEEP_TYPES = {
    # Tier 1: Core
    "person", "PERSON", "location", "LOCATION", "organization", "event",
    # Tier 2: Financial
    "financial", "FINANCIAL", "financial_amount", "financial_entity",
    "account_number", "account number",
    # Tier 3: Communication
    "phone_number", "phone number", "phone", "email",
    "online_identity", "username", "ip_address",
    # Tier 4: Travel
    "flight", "flight-number", "aircraft_identifier", "aircraft-identification",
    "aircraft", "vehicle", "vehicle_id",
    "travel_document", "passport", "visa",
    "transportation", "conveyance",
    # Tier 5: Legal
    "legal", "legal_case", "legal case", "legal_term", "legal_concept",
    "legislation", "statute", "rule", "regulation",
    "constitutional_provision", "constitutional provision",
    "court_location", "court_case", "charge", "offense", "evidence",
    # Tier 6: Physical Evidence
    "substance", "controlled_substance", "drug", "weapon", "firearm",
    "property", "real_estate",
    # Tier 7: Temporal
    "date", "time", "duration",
    # Tier 8: Identity
    "ethnicity", "nationality", "race", "gender",
    # Tier 9: Digital
    "cryptocurrency", "wallet_address", "domain", "url", "website",
    # Tier 10: Context
    "role", "relationship", "contact", "address",
    "case", "law", "publication",
    "industry", "service", "agreement", "title",
    # Tier 11: Catch-all for investigative relevance
    "artifact", "ARTIFACT", "theme", "THEME",
    "document", "evidence", "object", "item",
}

# Normalize type names to lowercase for matching
KEEP_TYPES_LOWER = {t.lower() for t in KEEP_TYPES}

# ── Quality Filters ────────────────────────────────────────────────
# These patterns indicate OCR noise, not real entities

# Regex for junk entity names
JUNK_PATTERNS = [
    r'^[_\-\.\*\#\>\<\:\;\,\!\?\@\$\%\^\&\(\)\[\]\{\}\/\\]+$',  # All punctuation/symbols
    r'^[\s_]+$',                    # All whitespace/underscores
    r'^\d{1,3}$',                   # Just 1-3 digits (page numbers, etc.)
    r'^[A-Z]{1,2}$',               # Just 1-2 uppercase letters
    r'^[\*]+$',                     # All asterisks
    r'^[\-]+$',                     # All dashes
    r'^[\.]+$',                     # All dots
    r'^[_]+$',                      # All underscores
    r'^\$\s*[\d\.]*$',             # Just dollar sign with optional number
    r'^\d+\.\d+%$',               # Just a percentage
    r'^0+$',                        # All zeros
    r'^[^\w\s]{3,}$',             # 3+ non-word non-space chars
    r'^.{0,1}$',                   # 0-1 character entities
]
JUNK_REGEXES = [re.compile(p) for p in JUNK_PATTERNS]

# Additional junk indicators
JUNK_SUBSTRINGS = {
    "<<<", ">>>", "***", "___", "---", "...", "///", "\\\\",
    "VOID", "WARRANTY", "SEAL", "LABEL", "SCREW", "REMOVED",
    "Product of", "Spare part", "Fireware", "MODEL MBD",
    "SER. NO.", "PART NO.", "REV NO",
}

def is_junk_entity(name: str) -> bool:
    """Return True if the entity name is OCR noise or formatting garbage."""
    if not name or len(name.strip()) < 2:
        return True
    
    stripped = name.strip()
    
    # Minimum length: real entities are at least 3 chars
    if len(stripped) < 3:
        return True
    
    # Check regex patterns
    for regex in JUNK_REGEXES:
        if regex.match(stripped):
            return True
    
    # Check junk substrings
    upper = stripped.upper()
    for sub in JUNK_SUBSTRINGS:
        if sub in upper:
            return True
    
    # Ratio of alphanumeric + space characters — if <40%, likely noise
    alnum = sum(1 for c in stripped if c.isalnum() or c == ' ')
    if len(stripped) > 3 and alnum / len(stripped) < 0.4:
        return True
    
    # Starts with special chars (not letters or digits)
    if stripped[0] in '[](){}|<>*#@$%^&!?;:,./\\-_+=~`':
        return True
    
    # All digits (not a real entity name — could be page number, code, etc.)
    # Exception: phone numbers (7+ digits) and account numbers (5+ digits with dashes)
    digits_only = stripped.replace('-', '').replace(' ', '').replace('.', '')
    if digits_only.isdigit() and len(digits_only) < 5:
        return True
    
    # Contains hex-like patterns (MAC addresses, hashes, device IDs)
    if re.match(r'^[0-9A-Fa-f]{8,}$', stripped.replace(':', '').replace('-', '')):
        return True
    
    # Looks like a dollar amount without context (just "$X.XX")
    if re.match(r'^\$[\d,\.]+$', stripped):
        return True
    
    # Looks like a percentage
    if re.match(r'^[\d\.]+%$', stripped):
        return True
    
    # Looks like a time without date context
    if re.match(r'^\d{1,2}:\d{2}(:\d{2})?([APap][Mm])?$', stripped):
        return True
    
    return False


# ── Neptune Client ─────────────────────────────────────────────────
SSL_CTX = ssl.create_default_context()

def neptune_query(query, timeout=GREMLIN_TIMEOUT):
    """Execute a Gremlin query via Neptune HTTP API."""
    url = f"https://{NEPTUNE_ENDPOINT}:{NEPTUNE_PORT}/gremlin"
    data = json.dumps({"gremlin": query}).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, context=SSL_CTX, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            return parse_result(body.get("result", {}).get("data", {}))
    except Exception as e:
        return {"error": str(e)[:300]}

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

def escape_gremlin(s: str) -> str:
    """Escape a string for Gremlin query embedding."""
    return s.replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"')


# ── Lambda Client ──────────────────────────────────────────────────
lam = boto3.client("lambda", region_name=REGION)

def query_aurora_entities(limit, offset):
    """Get paginated entities from Aurora with taxonomy and quality filters."""
    # Build type filter string from KEEP_TYPES
    type_list = ",".join(sorted(KEEP_TYPES_LOWER))
    resp = lam.invoke(
        FunctionName=LAMBDA_NAME,
        InvocationType="RequestResponse",
        Payload=json.dumps({
            "action": "query_aurora_entities",
            "case_id": CASE_ID,
            "limit": limit,
            "offset": offset,
            "min_occurrence": MIN_OCCURRENCE_COUNT,
            "type_filter": type_list,
        }),
    )
    return json.loads(resp["Payload"].read().decode())


def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


# ── Main Sync Logic ────────────────────────────────────────────────
def main():
    log("=" * 60)
    log("Neptune Re-Sync — Aurora → Neptune with Master Taxonomy")
    log(f"Case: {CASE_ID}")
    log(f"Neptune: {NEPTUNE_ENDPOINT}:{NEPTUNE_PORT}")
    log(f"Dry run: {DRY_RUN}")
    log("=" * 60)

    # Verify Neptune connectivity
    test = neptune_query("g.V().limit(1).count()", timeout=10)
    if isinstance(test, dict) and "error" in test:
        log(f"FATAL: Cannot connect to Neptune: {test['error']}")
        sys.exit(1)
    log("Neptune connection verified ✓")

    # Get current Neptune node count
    count_result = neptune_query(f"g.V().hasLabel('{CASE_LABEL}').count()", timeout=60)
    if isinstance(count_result, list) and count_result:
        count_result = count_result[0]
    log(f"Current Neptune nodes for this case: {count_result}")

    # Get total Aurora entities
    data = query_aurora_entities(1, 0)
    if "error" in data:
        log(f"FATAL: Aurora query failed: {data['error']}")
        sys.exit(1)
    total = data.get("total", 0)
    log(f"Total distinct entities in Aurora: {total:,}")

    # Process in pages
    offset = 0
    synced = 0
    filtered_type = 0
    filtered_junk = 0
    errors = 0
    start = time.time()

    while offset < total:
        data = query_aurora_entities(PAGE_SIZE, offset)
        if "error" in data:
            log(f"ERROR at offset {offset}: {data['error'][:200]}")
            errors += 1
            if errors > 10:
                log("Too many errors, stopping.")
                break
            time.sleep(5)
            continue

        entities = data.get("entities", [])
        if not entities:
            break

        for ent in entities:
            name = ent.get("name", "")
            etype = ent.get("type", "unknown")
            count = ent.get("count", 1)

            # Filter 1: Master taxonomy type check
            if etype.lower() not in KEEP_TYPES_LOWER:
                filtered_type += 1
                continue

            # Filter 2: Quality check — reject OCR noise
            if is_junk_entity(name):
                filtered_junk += 1
                continue

            # Filter 3: Occurrence count — entities in only 1 doc are likely noise
            if count < MIN_OCCURRENCE_COUNT:
                filtered_junk += 1
                continue

            # Build upsert query (fold/coalesce pattern — no duplicates)
            esc_name = escape_gremlin(name)
            esc_type = escape_gremlin(etype)

            upsert = (
                f"g.V().hasLabel('{CASE_LABEL}')"
                f".has('canonical_name', '{esc_name}')"
                f".has('entity_type', '{esc_type}')"
                f".fold()"
                f".coalesce("
                f"unfold().property('occurrence_count', {count}),"
                f"addV('{CASE_LABEL}')"
                f".property('canonical_name', '{esc_name}')"
                f".property('entity_type', '{esc_type}')"
                f".property('occurrence_count', {count})"
                f".property('confidence', 0.9)"
                f".property('case_file_id', '{CASE_ID}')"
                f")"
            )

            if DRY_RUN:
                synced += 1
                continue

            result = neptune_query(upsert, timeout=GREMLIN_TIMEOUT)
            if isinstance(result, dict) and "error" in result:
                errors += 1
                if errors % 50 == 0:
                    log(f"  Error #{errors}: {result['error'][:150]}")
            else:
                synced += 1

            # Rate limit — upserts are heavier than addV
            if synced % 10 == 0:
                time.sleep(0.05)

        offset += PAGE_SIZE

        # Progress report every page
        elapsed = time.time() - start
        rate = synced / max(elapsed, 1) * 60
        log(f"  Page {offset // PAGE_SIZE}: synced={synced:,}, "
            f"filtered_type={filtered_type:,}, filtered_junk={filtered_junk:,}, "
            f"errors={errors}, rate={rate:.0f}/min")

    elapsed = time.time() - start

    # Final Neptune count
    final_count = neptune_query(f"g.V().hasLabel('{CASE_LABEL}').count()", timeout=60)
    if isinstance(final_count, list) and final_count:
        final_count = final_count[0]

    log("=" * 60)
    log("RE-SYNC COMPLETE")
    log(f"  Aurora total:     {total:,}")
    log(f"  Synced to Neptune: {synced:,}")
    log(f"  Filtered (type):  {filtered_type:,}")
    log(f"  Filtered (junk):  {filtered_junk:,}")
    log(f"  Errors:           {errors}")
    log(f"  Neptune before:   {count_result}")
    log(f"  Neptune after:    {final_count}")
    log(f"  Elapsed:          {elapsed/60:.1f} minutes")
    log("=" * 60)


if __name__ == "__main__":
    # Parse --case-id argument
    for i, arg in enumerate(sys.argv):
        if arg == "--case-id" and i + 1 < len(sys.argv):
            CASE_ID = sys.argv[i + 1]
            CASE_LABEL = f"Entity_{CASE_ID}"
    main()
