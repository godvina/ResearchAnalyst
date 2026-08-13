"""FULL RECOVERY TRACE — Find the 15K dropped entities anywhere they exist.

The data flowed through: LLM → Lambda → Aurora → Neptune
If Neptune dropped them, check:
1. S3 batch output (raw LLM responses — 97MB + 49MB JSONL)
2. Aurora (entities table with ALL types, not just the Lambda query)
3. Neptune audit log (CloudWatch)
4. CloudTrail (API calls that created those vertices)
5. The ec2_aurora_neptune_sync results log

The entities had types: object, other, identifier, number, product,
rule, classification, abstract — plus 294 minor types.
"""
import boto3
import json
import re
import time
from collections import defaultdict

REGION = "us-east-1"
BUCKET = "research-analyst-data-lake-974220725866"
CASE_ID = "7f05e8d5-4492-4f19-8894-25367606db96"
LABEL = "Entity_" + CASE_ID
LAMBDA_NAME = "ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq"

DROPPED_TYPES = {"object", "other", "identifier", "number", "product",
                 "rule", "classification", "abstract"}

s3 = boto3.client("s3", region_name=REGION)
lam = boto3.client("lambda", region_name=REGION)


def invoke_lambda(payload):
    r = lam.invoke(FunctionName=LAMBDA_NAME, InvocationType="RequestResponse",
        Payload=json.dumps(payload))
    return json.loads(r["Payload"].read().decode())


def gremlin(q, timeout=60):
    r = invoke_lambda({"action": "gremlin_query", "case_id": CASE_ID,
                       "query": q, "timeout": timeout})
    return r.get("result", r.get("error", ""))


print("=" * 70)
print("FULL RECOVERY TRACE — Finding the 15K dropped entities")
print("=" * 70)

# ================================================================
# SOURCE 1: S3 Batch Inference Output (the raw LLM responses)
# ================================================================
print("\n" + "=" * 70)
print("SOURCE 1: S3 Batch Inference Output")
print("=" * 70)

output_key = f"batch-inference/entity-extraction/{CASE_ID}/output/17uppsaiaf4c/entities_0000.jsonl.out"
print(f"  File: s3://{BUCKET}/{output_key}")
print(f"  Size: ~97MB, reading in chunks...")

# Read the file in 2MB chunks and parse all entities with dropped types
recovered_entities = defaultdict(list)
all_types_found = defaultdict(int)
total_lines = 0
total_entities = 0
chunk_size = 2 * 1024 * 1024  # 2MB chunks
offset = 0
leftover = ""

# Get file size
head = s3.head_object(Bucket=BUCKET, Key=output_key)
file_size = head["ContentLength"]
print(f"  File size: {file_size / (1024*1024):.1f} MB")

while offset < file_size:
    end = min(offset + chunk_size - 1, file_size - 1)
    obj = s3.get_object(Bucket=BUCKET, Key=output_key, Range=f"bytes={offset}-{end}")
    chunk = obj["Body"].read().decode("utf-8", errors="ignore")
    
    # Combine with leftover from previous chunk
    text = leftover + chunk
    lines = text.split("\n")
    leftover = lines[-1]  # Last incomplete line carries over
    lines = lines[:-1]

    for line in lines:
        if not line.strip():
            continue
        total_lines += 1
        try:
            record = json.loads(line)
            # Try multiple output format patterns
            model_output = record.get("modelOutput", {})
            
            # Format 1: modelOutput is a dict with content
            if isinstance(model_output, dict):
                content = model_output.get("content", [])
                if isinstance(content, list) and content:
                    text_out = content[0].get("text", "") if isinstance(content[0], dict) else str(content[0])
                else:
                    text_out = ""
            elif isinstance(model_output, str):
                text_out = model_output
            else:
                # Maybe the output IS the record itself with entities
                text_out = ""
                
            # Also check if the record has "output" key (different format)
            if not text_out:
                output_field = record.get("output", {})
                if isinstance(output_field, dict):
                    content = output_field.get("message", {}).get("content", [])
                    if isinstance(content, list) and content:
                        text_out = content[0].get("text", "")
            
            if not text_out:
                continue

            # Parse entities from the LLM response text
            try:
                entities = json.loads(text_out)
                if isinstance(entities, dict):
                    entities = entities.get("entities", [])
                if not isinstance(entities, list):
                    entities = []
            except json.JSONDecodeError:
                # Try to find JSON array in the text
                match = re.search(r'\[.*\]', text_out, re.DOTALL)
                if match:
                    try:
                        entities = json.loads(match.group())
                    except:
                        entities = []
                else:
                    entities = []

            for ent in entities:
                if not isinstance(ent, dict):
                    continue
                etype = ent.get("type", "unknown").lower()
                all_types_found[etype] += 1
                total_entities += 1
                if etype in DROPPED_TYPES:
                    recovered_entities[etype].append({
                        "name": ent.get("name", "?"),
                        "type": etype,
                        "confidence": ent.get("confidence", 0.5),
                    })
        except Exception:
            pass

    offset = end + 1
    if offset % (10 * 1024 * 1024) == 0 or offset >= file_size:
        print(f"    Read {offset/(1024*1024):.0f}MB / {file_size/(1024*1024):.0f}MB "
              f"— {total_lines} lines, {total_entities} entities, "
              f"{sum(len(v) for v in recovered_entities.values())} recovered")

print(f"\n  BATCH OUTPUT RESULTS:")
print(f"    Total lines parsed: {total_lines}")
print(f"    Total entities found: {total_entities}")
print(f"    Entities with dropped types: {sum(len(v) for v in recovered_entities.values())}")

print(f"\n    All types in batch output:")
for t, c in sorted(all_types_found.items(), key=lambda x: -x[1])[:30]:
    marker = " *** RECOVERABLE ***" if t in DROPPED_TYPES else ""
    print(f"      {t}: {c}{marker}")

if recovered_entities:
    print(f"\n    RECOVERED ENTITIES BY TYPE:")
    for etype, ents in sorted(recovered_entities.items(), key=lambda x: -len(x[1])):
        print(f"\n    [{etype}] — {len(ents)} entities:")
        # Deduplicate by name
        unique_names = {}
        for e in ents:
            name = e["name"]
            if name in unique_names:
                unique_names[name]["count"] = unique_names[name].get("count", 1) + 1
            else:
                unique_names[name] = e
                unique_names[name]["count"] = 1
        
        # Show top 15 by frequency
        sorted_unique = sorted(unique_names.values(), key=lambda x: -x.get("count", 1))
        for e in sorted_unique[:15]:
            print(f"      {e['name']} (count={e.get('count', 1)}, conf={e['confidence']})")
        if len(sorted_unique) > 15:
            print(f"      ... and {len(sorted_unique) - 15} more")

    # Save recovered entities for re-insertion
    output_file = "scripts/recovered_dropped_entities.json"
    # Deduplicate across all types
    all_unique = {}
    for etype, ents in recovered_entities.items():
        for e in ents:
            key = f"{e['type']}:{e['name']}"
            if key not in all_unique:
                all_unique[key] = e
                all_unique[key]["occurrence_count"] = 1
            else:
                all_unique[key]["occurrence_count"] += 1

    output_data = {
        "recovered_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "s3_batch_inference_output",
        "total_recovered": len(all_unique),
        "by_type": {t: len(v) for t, v in recovered_entities.items()},
        "entities": sorted(all_unique.values(), key=lambda x: -x.get("occurrence_count", 1)),
    }
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2)
    print(f"\n    Saved to: {output_file}")

else:
    print("\n    No dropped-type entities found in batch output.")
    print("    Trying SOURCE 2: Aurora direct SQL query...")

# ================================================================
# SOURCE 2: Aurora — direct SQL via Lambda for ALL entity types
# ================================================================
print("\n" + "=" * 70)
print("SOURCE 2: Aurora Direct Query (checking ALL types)")
print("=" * 70)

# The query_aurora_entities action may filter types.
# Try a different approach — use a raw SQL action if available
result = invoke_lambda({
    "action": "query_aurora_entities",
    "case_id": CASE_ID,
    "limit": 5000,
    "offset": 250000,  # Skip to the end where non-standard types might be
})
entities = result.get("entities", [])
print(f"  Got {len(entities)} entities from offset 250000")
found_dropped = [e for e in entities if e.get("type", "") in DROPPED_TYPES]
print(f"  With dropped types: {len(found_dropped)}")
if found_dropped:
    for e in found_dropped[:10]:
        print(f"    [{e['type']}] {e['name']} (count={e.get('count', '?')})")

print("\n" + "=" * 70)
print("RECOVERY TRACE COMPLETE")
print("=" * 70)
