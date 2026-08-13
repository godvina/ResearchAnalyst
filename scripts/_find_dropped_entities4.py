"""Check batch inference output for the dropped entity types."""
import boto3
import json

REGION = "us-east-1"
BUCKET = "research-analyst-data-lake-974220725866"
CASE_ID = "7f05e8d5-4492-4f19-8894-25367606db96"
DROPPED_TYPES = {"object", "other", "identifier", "number", "product",
                 "rule", "classification", "abstract"}

s3 = boto3.client("s3", region_name="us-east-1")

# Read first 100 lines of the batch output (97MB file)
key = f"batch-inference/entity-extraction/{CASE_ID}/output/17uppsaiaf4c/entities_0000.jsonl.out"
print(f"Reading batch output: {key}")

# Use range read for first 500KB
obj = s3.get_object(Bucket=BUCKET, Key=key, Range="bytes=0-500000")
content = obj["Body"].read().decode("utf-8", errors="ignore")
lines = content.split("\n")[:50]

all_types = {}
dropped_examples = []
total_entities = 0

for line in lines:
    if not line.strip():
        continue
    try:
        record = json.loads(line)
        # Batch inference output format: modelInput + modelOutput
        model_output = record.get("modelOutput", {})
        if isinstance(model_output, str):
            model_output = json.loads(model_output)
        
        # Claude batch output format
        output_content = model_output.get("content", [])
        if isinstance(output_content, list) and output_content:
            text = output_content[0].get("text", "")
        elif isinstance(output_content, str):
            text = output_content
        else:
            text = str(model_output)

        # Try to parse as JSON array of entities
        try:
            entities = json.loads(text)
            if isinstance(entities, dict):
                entities = entities.get("entities", [])
            if not isinstance(entities, list):
                entities = []
        except:
            entities = []

        for e in entities:
            if isinstance(e, dict):
                t = e.get("type", "unknown").lower()
                all_types[t] = all_types.get(t, 0) + 1
                total_entities += 1
                if t in DROPPED_TYPES:
                    dropped_examples.append(e)
    except Exception as ex:
        pass

print(f"\nParsed {len(lines)} lines, found {total_entities} entities")
print(f"\nEntity types in batch output:")
for t, c in sorted(all_types.items(), key=lambda x: -x[1]):
    marker = " *** DROPPED ***" if t in DROPPED_TYPES else ""
    print(f"  {t}: {c}{marker}")

if dropped_examples:
    print(f"\n{'='*60}")
    print(f"FOUND {len(dropped_examples)} DROPPED ENTITIES!")
    print(f"{'='*60}")
    print("\nSamples (what we lost):")
    for e in dropped_examples[:30]:
        print(f"  [{e.get('type', '?')}] {e.get('name', '?')} "
              f"(conf={e.get('confidence', '?')})")
else:
    print("\nNo dropped types in batch output either.")
    print("The 15K nodes may have come from cross-case pattern agent or")
    print("a Lambda that wrote directly to Neptune with non-standard types.")
