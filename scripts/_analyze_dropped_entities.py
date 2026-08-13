"""Deep analysis of the 6,608 "dropped" entities — Junk or Gold?

Pulls all entities with non-standard types from Aurora and categorizes
them into:
- GOLD: Investigatively valuable (DOJ doc references, case numbers, 
        evidence identifiers, financial products, legal rules)
- SILVER: Potentially useful context (devices, standards, measurements)
- JUNK: OCR noise, formatting artifacts, meaningless data
"""
import boto3
import json
import re
from collections import defaultdict

REGION = "us-east-1"
LAMBDA_NAME = "ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq"
CASE_ID = "7f05e8d5-4492-4f19-8894-25367606db96"

DROPPED_TYPES = {"object", "other", "identifier", "number", "product",
                 "rule", "classification", "abstract", "device",
                 "standard", "attribute", "measurement", "miscellaneous",
                 "thing", "mechanism", "information", "abbreviation",
                 "policy", "medical"}

lam = boto3.client("lambda", region_name=REGION)


def invoke_lambda(payload):
    r = lam.invoke(FunctionName=LAMBDA_NAME, InvocationType="RequestResponse",
        Payload=json.dumps(payload))
    return json.loads(r["Payload"].read().decode())


# Phase 1: Collect all dropped-type entities
print("=" * 70)
print("DEEP ANALYSIS: 6,608 Non-Standard Entities — Junk or Gold?")
print("=" * 70)

print("\nCollecting all non-standard entities from Aurora...")
page_size = 5000
offset = 0
total_aurora = 255922
all_entities = []

while offset < total_aurora:
    result = invoke_lambda({
        "action": "query_aurora_entities",
        "case_id": CASE_ID,
        "limit": page_size,
        "offset": offset,
    })
    entities = result.get("entities", [])
    if not entities:
        break
    for ent in entities:
        if ent.get("type", "") in DROPPED_TYPES:
            all_entities.append(ent)
    offset += page_size

print(f"  Total non-standard entities: {len(all_entities)}")

# Phase 2: Classify each entity
print("\nPhase 2: Classifying entities...")

# Classification patterns
GOLD_PATTERNS = [
    # DOJ document references (critical for investigations)
    (r'^DOJ-', "DOJ document reference"),
    (r'^EFTA\d+', "EFTA document ID"),
    (r'^\d{2,3}-[A-Z]{2,4}-\d+', "Case file number"),
    # Financial products and instruments
    (r'(bond|stock|fund|trust|LLC|Inc|Corp|mortgage|loan|credit)', "Financial instrument"),
    # Legal references
    (r'(statute|U\.S\.C|§|section \d|rule \d|act of)', "Legal citation"),
    (r'(NPA|plea|agreement|immunity|order|warrant|subpoena)', "Legal instrument"),
    # Evidence identifiers
    (r'(exhibit|evidence|serial|badge|case.?no)', "Evidence reference"),
    # Account/transaction references
    (r'(acct|account|routing|swift|IBAN|wire)', "Financial account"),
]

SILVER_PATTERNS = [
    # Technical identifiers that might link entities
    (r'^[A-Z]{2,5}\d{4,}', "Coded identifier"),
    (r'(phone|fax|cell|tel)', "Communication device"),
    (r'(camera|surveillance|recording|computer|laptop|hard.?drive)', "Surveillance/device"),
    (r'(passport|license|ID|SSN|EIN)', "Identity document"),
    (r'(flight|aircraft|N\d{3})', "Aviation reference"),
    (r'(property|real.?estate|deed|title)', "Property reference"),
]

JUNK_PATTERNS = [
    # OCR artifacts
    (r'^[.\-_\s]+$', "Whitespace/punctuation only"),
    (r'^\d{1,3}$', "Single short number"),
    (r'^(page|of|the|and|for|to|from|in|on|at|by|with)$', "Stop word"),
    # Formatting
    (r'^(true|false|null|none|n/a|unknown|other)$', "Placeholder value"),
    (r'^\(b\)\(\d\)', "FOIA redaction code"),
    # Too generic
    (r'^(item|total|amount|date|number|name|type|value|code|id)$', "Generic field name"),
]


def classify_entity(name, etype):
    """Classify an entity as GOLD, SILVER, or JUNK."""
    name_lower = name.lower().strip()
    
    # Check JUNK first
    for pattern, reason in JUNK_PATTERNS:
        if re.search(pattern, name_lower, re.IGNORECASE):
            return "JUNK", reason
    
    # Very short names are likely junk
    if len(name.strip()) <= 2:
        return "JUNK", "Too short"
    
    # Check GOLD
    for pattern, reason in GOLD_PATTERNS:
        if re.search(pattern, name, re.IGNORECASE):
            return "GOLD", reason
    
    # Check SILVER
    for pattern, reason in SILVER_PATTERNS:
        if re.search(pattern, name, re.IGNORECASE):
            return "SILVER", reason
    
    # High occurrence count suggests importance
    return "UNKNOWN", "Needs manual review"


# Classify all entities
gold = []
silver = []
junk = []
unknown = []

for ent in all_entities:
    name = ent.get("name", "")
    etype = ent.get("type", "")
    count = ent.get("count", 1)
    
    classification, reason = classify_entity(name, etype)
    entry = {"name": name, "type": etype, "count": count,
             "classification": classification, "reason": reason}
    
    if classification == "GOLD":
        gold.append(entry)
    elif classification == "SILVER":
        silver.append(entry)
    elif classification == "JUNK":
        junk.append(entry)
    else:
        unknown.append(entry)

# Phase 3: Report
print("\n" + "=" * 70)
print("CLASSIFICATION RESULTS")
print("=" * 70)

print(f"\n  🥇 GOLD (investigatively valuable): {len(gold)}")
print(f"  🥈 SILVER (contextually useful):     {len(silver)}")
print(f"  🗑️  JUNK (noise/artifacts):           {len(junk)}")
print(f"  ❓ UNKNOWN (needs review):            {len(unknown)}")
print(f"  ─────────────────────────────────────")
print(f"  TOTAL:                                {len(all_entities)}")

# GOLD details
print(f"\n{'='*70}")
print(f"🥇 GOLD ENTITIES ({len(gold)}) — These matter for investigations")
print(f"{'='*70}")
gold_by_reason = defaultdict(list)
for e in gold:
    gold_by_reason[e["reason"]].append(e)
for reason, ents in sorted(gold_by_reason.items(), key=lambda x: -len(x[1])):
    print(f"\n  [{reason}] — {len(ents)} entities:")
    for e in sorted(ents, key=lambda x: -x["count"])[:10]:
        print(f"    {e['name'][:60]} (type={e['type']}, count={e['count']})")
    if len(ents) > 10:
        print(f"    ... +{len(ents)-10} more")

# SILVER details
print(f"\n{'='*70}")
print(f"🥈 SILVER ENTITIES ({len(silver)}) — Contextual value")
print(f"{'='*70}")
silver_by_reason = defaultdict(list)
for e in silver:
    silver_by_reason[e["reason"]].append(e)
for reason, ents in sorted(silver_by_reason.items(), key=lambda x: -len(x[1])):
    print(f"\n  [{reason}] — {len(ents)} entities:")
    for e in sorted(ents, key=lambda x: -x["count"])[:8]:
        print(f"    {e['name'][:60]} (type={e['type']}, count={e['count']})")

# JUNK details
print(f"\n{'='*70}")
print(f"🗑️  JUNK ENTITIES ({len(junk)}) — Noise")
print(f"{'='*70}")
junk_by_reason = defaultdict(int)
for e in junk:
    junk_by_reason[e["reason"]] += 1
for reason, count in sorted(junk_by_reason.items(), key=lambda x: -x[1]):
    print(f"  {reason}: {count}")
# Show samples
print(f"\n  Junk samples:")
for e in junk[:10]:
    print(f"    '{e['name']}' (type={e['type']}, reason={e['reason']})")

# UNKNOWN — these need human review
print(f"\n{'='*70}")
print(f"❓ UNKNOWN ENTITIES ({len(unknown)}) — Needs human review")
print(f"{'='*70}")
# Group by type
unknown_by_type = defaultdict(list)
for e in unknown:
    unknown_by_type[e["type"]].append(e)
for etype, ents in sorted(unknown_by_type.items(), key=lambda x: -len(x[1])):
    print(f"\n  [{etype}] — {len(ents)} entities:")
    for e in sorted(ents, key=lambda x: -x["count"])[:10]:
        print(f"    {e['name'][:60]} (count={e['count']})")
    if len(ents) > 10:
        print(f"    ... +{len(ents)-10} more")

# Save full analysis
output = {
    "analysis_date": __import__("time").strftime("%Y-%m-%dT%H:%M:%SZ"),
    "total_entities": len(all_entities),
    "summary": {
        "gold": len(gold),
        "silver": len(silver),
        "junk": len(junk),
        "unknown": len(unknown),
    },
    "gold_entities": sorted(gold, key=lambda x: -x["count"]),
    "silver_entities": sorted(silver, key=lambda x: -x["count"]),
    "junk_entities": junk[:50],  # just samples
    "unknown_entities": sorted(unknown, key=lambda x: -x["count"]),
}
with open("scripts/entity_analysis_junk_or_gold.json", "w", encoding="utf-8") as f:
    json.dump(output, f, indent=2, ensure_ascii=False)
print(f"\n\nFull analysis saved: scripts/entity_analysis_junk_or_gold.json")

# Verdict
gold_pct = len(gold) / max(len(all_entities), 1) * 100
silver_pct = len(silver) / max(len(all_entities), 1) * 100
junk_pct = len(junk) / max(len(all_entities), 1) * 100

print(f"\n{'='*70}")
print(f"VERDICT")
print(f"{'='*70}")
if gold_pct + silver_pct > 50:
    print(f"  MOSTLY GOLD/SILVER ({gold_pct+silver_pct:.0f}% valuable)")
    print(f"  These entities ARE investigatively relevant.")
    print(f"  The deletion was a mistake — good thing we recovered them.")
elif junk_pct > 70:
    print(f"  MOSTLY JUNK ({junk_pct:.0f}% noise)")
    print(f"  The deletion was correct — these were noise.")
else:
    print(f"  MIXED BAG ({gold_pct:.0f}% gold, {silver_pct:.0f}% silver, {junk_pct:.0f}% junk)")
    print(f"  Worth keeping the gold/silver, junk should be cleaned.")
