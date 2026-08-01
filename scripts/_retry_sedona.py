"""Retry Sedona cultural memory with simplified prompt."""
import boto3
import json
import os
from botocore.config import Config

bedrock = boto3.client("bedrock-runtime", region_name="us-east-1",
                       config=Config(read_timeout=120, retries={"max_attempts": 2}))

prompt = (
    "Research the indigenous sacred traditions at Sedona, Arizona "
    "(Yavapai-Apache territory, 34.87N, 111.76W).\n\n"
    "Score these traits as YES, POSSIBLE, or NO with brief evidence:\n"
    "1. ENERGY_SENSATION 2. HEALING_TRADITION 3. FORBIDDEN_ZONE 4. CREATION_MYTH\n"
    "5. PILGRIMAGE 6. ASTRONOMICAL_USE 7. SPIRIT_DWELLING 8. WATER_SACRED\n"
    "9. BURIAL_GROUND 10. POWER_TRANSFER\n\n"
    'Return ONLY valid JSON (no markdown, no explanation before/after):\n'
    '{"traits": [{"id": "ENERGY_SENSATION", "score": "YES or NO", "evidence": "brief"}], '
    '"primary_tradition": "text", "unique_feature": "text"}'
)

resp = bedrock.invoke_model(
    modelId="us.anthropic.claude-sonnet-4-6",
    contentType="application/json",
    accept="application/json",
    body=json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 2000,
        "messages": [{"role": "user", "content": prompt}]
    })
)
body = json.loads(resp["body"].read())
raw = ""
for block in body.get("content", []):
    if block.get("type") == "text":
        raw = block["text"]
        break

text = raw.strip()
if "```json" in text:
    text = text.split("```json")[1].split("```")[0].strip()
elif "```" in text:
    text = text.split("```")[1].split("```")[0].strip()

# Try parse
try:
    result = json.loads(text)
except json.JSONDecodeError:
    # Truncation repair
    for trim_to in [text.rfind("},"), text.rfind("}"), text.rfind('"]')]:
        if trim_to <= 0:
            continue
        candidate = text[:trim_to + 1]
        candidate += "]" * max(0, candidate.count("[") - candidate.count("]"))
        candidate += "}" * max(0, candidate.count("{") - candidate.count("}"))
        try:
            result = json.loads(candidate)
            break
        except json.JSONDecodeError:
            continue
    else:
        print(f"FAILED. Raw ({len(raw)} chars):")
        print(raw[:800])
        exit(1)

traits_yes = [t for t in result.get("traits", []) if t.get("score") == "YES"]
print(f"Sedona: {len(traits_yes)} confirmed traits")
for t in traits_yes:
    print(f"  {t['id']}: {t['evidence']}")

# Save
path = os.path.join("src", "data", "cultural-memory-results.json")
with open(path) as f:
    data = json.load(f)

for i, r in enumerate(data["results"]):
    if r["node_id"] == 17:
        data["results"][i] = {"node_id": 17, "name": "Sedona Vortexes", "cultural": result}
        break
else:
    data["results"].append({"node_id": 17, "name": "Sedona Vortexes", "cultural": result})

with open(path, "w") as f:
    json.dump(data, f, indent=2)
print(f"Saved: {path}")
