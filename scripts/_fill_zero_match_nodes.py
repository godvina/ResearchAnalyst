"""Fill zero-match nodes with basic research via Bedrock broad scan."""
import boto3
import json
import os
import time
from botocore.config import Config

REGION = "us-east-1"
MODEL = "us.anthropic.claude-sonnet-4-6"
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "src", "data")

bedrock = boto3.client("bedrock-runtime", region_name=REGION,
                       config=Config(read_timeout=120, retries={"max_attempts": 2}))

# Load grid nodes for coordinates
grid_path = os.path.join(DATA_DIR, "uvg-grid-investigation-database.json")
with open(grid_path) as f:
    grid_data = json.load(f)
node_map = {n["id"]: n for n in grid_data.get("nodes", [])}

# Nodes to fill
ZERO_MATCH = [10, 15, 19, 28, 31, 39, 46, 48, 54, 56, 57, 60, 61]
MISSING = [4, 5, 6]
ALL_FILL = ZERO_MATCH + MISSING

PROMPT_TEMPLATE = (
    "You are an archaeological research agent. Investigate UVG Grid Node {node_id} "
    "at coordinates {lat}N, {lng}E.\n\n"
    "Determine if ANY of these signatures match this location:\n"
    "1. am-gge-san-001: Megalithic construction (multi-ton stone blocks, precision fitting)\n"
    "2. am-gge-cnp-002: Astronomical alignment (solstice, star, precision <1 degree)\n"
    "3. am-gge-lla-001: Ley line or great-circle alignment passing through\n"
    "4. am-gge-cm-001: Indigenous sacred site (500+ years continuous designation)\n"
    "5. am-gge-cnp-004: Ancient site cluster (5+ sites within 300km)\n"
    "6. am-gge-ga-003: Tectonic/volcanic node (plate boundary, fault, hotspot)\n"
    "7. am-gge-se-004: Submerged platform (<200m depth, Ice Age coastline)\n"
    "8. am-gge-ga-002: Geometric formation (natural or constructed precision geometry)\n\n"
    "Return ONLY valid JSON with a matches array and brief object. No markdown fences."
)


def research_node(node_id):
    node = node_map.get(node_id)
    if not node:
        print(f"  Node {node_id} not in grid database")
        return None

    prompt = PROMPT_TEMPLATE.format(node_id=node_id, lat=node["lat"], lng=node["lng"])
    prompt += (
        '\n\nExample output format:\n'
        '{"matches": [{"signature_id": "am-gge-ga-003", "confidence": "strong", '
        '"matched_indicators": ["Plate boundary within 50km"], '
        '"evidence_excerpt": "Located on Pacific Ring of Fire"}], '
        '"brief": {"codename": "NODE_NAME", "investigation_status": "PROBABLE", '
        '"situation": "Summary text", "smoking_gun": "Key finding or null", '
        '"evidence_found": [{"finding": "text", "confidence": "probable", "source_type": "geological"}]}}'
    )

    try:
        resp = bedrock.invoke_model(
            modelId=MODEL,
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

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Truncation repair
            for trim_to in [text.rfind("},"), text.rfind("}"), text.rfind('"]')]:
                if trim_to <= 0:
                    continue
                candidate = text[:trim_to + 1]
                candidate += "]" * max(0, candidate.count("[") - candidate.count("]"))
                candidate += "}" * max(0, candidate.count("{") - candidate.count("}"))
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    continue
            print(f"  Parse failed ({len(raw)} chars)")
            return None
    except Exception as e:
        print(f"  Error: {e}")
        return None


def main():
    print(f"Filling {len(ALL_FILL)} zero-match/missing nodes...")
    print("=" * 60)

    # Load scored findings
    scored_path = os.path.join(DATA_DIR, "uvg-grid-scored-findings.json")
    with open(scored_path) as f:
        scored = json.load(f)

    # Load research briefs
    research_path = os.path.join(DATA_DIR, "uvg-grid-research-all-nodes.json")
    with open(research_path) as f:
        research = json.load(f)

    filled = 0
    for node_id in ALL_FILL:
        print(f"  [{node_id}] ...", end=" ")
        result = research_node(node_id)
        if not result:
            print("FAILED")
            time.sleep(1)
            continue

        matches = result.get("matches", [])
        brief = result.get("brief", {})
        non_weak = [m for m in matches if m.get("confidence") != "weak"]
        print(f"OK — {len(non_weak)} matches (non-weak)")

        # Update scored findings
        existing = next((r for r in scored["results"] if r["node_id"] == node_id), None)
        if existing:
            existing["matches"] = matches
            existing["match_count"] = len(matches)
        else:
            scored["results"].append({
                "node_id": node_id,
                "matches": matches,
                "match_count": len(matches),
                "strongest_match": matches[0]["signature_id"] if matches else None,
            })

        # Update research briefs
        existing_r = next((r for r in research.get("results", []) if r.get("node_id") == node_id), None)
        if existing_r:
            existing_r["brief"] = brief
        else:
            if "results" not in research:
                research["results"] = []
            research["results"].append({"node_id": node_id, "brief": brief})

        filled += 1
        time.sleep(1)

    # Update totals
    scored["total_with_matches"] = sum(1 for r in scored["results"] if len(r.get("matches", [])) > 0)

    with open(scored_path, "w") as f:
        json.dump(scored, f, indent=2)
    with open(research_path, "w") as f:
        json.dump(research, f, indent=2)

    print(f"\n{'=' * 60}")
    print(f"Filled {filled}/{len(ALL_FILL)} nodes")
    print(f"Total nodes with matches: {scored['total_with_matches']}/{scored['total_scored']}")
    print(f"Saved: {scored_path}")
    print(f"Saved: {research_path}")


if __name__ == "__main__":
    main()
