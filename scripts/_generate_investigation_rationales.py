"""Generate 'WHY INVESTIGATE' rationales for unexplored/inconclusive nodes.

For each node, explains:
1. Probability factors (what increases likelihood of a find)
2. Analogous precedents (similar conditions that produced discoveries)
3. Specific prediction (what you'd expect to find)
4. Recommended method (LiDAR, dive survey, ground-penetrating radar, etc.)

Results saved to investigation-rationales.json for frontend display.
"""
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

# Load context data
scored = json.load(open(os.path.join(DATA_DIR, "uvg-grid-scored-findings.json")))
research = json.load(open(os.path.join(DATA_DIR, "uvg-grid-research-all-nodes.json")))
grid = json.load(open(os.path.join(DATA_DIR, "uvg-grid-investigation-database.json")))
node_coords = {n["id"]: n for n in grid.get("nodes", [])}

# Build brief map
brief_map = {}
for r in research.get("results", []):
    brief_map[r.get("node_id")] = r.get("brief", {})

# Find nodes needing rationales
TARGET_NODES = []
for r in scored["results"]:
    nid = r["node_id"]
    brief = brief_map.get(nid, {})
    status = brief.get("investigation_status", "UNKNOWN")
    if status in ("INCONCLUSIVE", "UNKNOWN"):
        # Only include nodes with SOME matches (more interesting than zero-data)
        if len(r.get("matches", [])) >= 1:
            TARGET_NODES.append(nid)

# Cap at 15 to control costs
TARGET_NODES = TARGET_NODES[:15]


def generate_rationale(node_id):
    """Generate investigation rationale for one node."""
    node = node_coords.get(node_id, {})
    scored_entry = next((r for r in scored["results"] if r["node_id"] == node_id), {})
    brief = brief_map.get(node_id, {})
    
    # Find nearest confirmed sites for context
    confirmed_sites = []
    for r in research.get("results", []):
        b = r.get("brief", {})
        if b.get("investigation_status") in ("CONFIRMED", "PROBABLE"):
            confirmed_sites.append({
                "id": r["node_id"],
                "name": b.get("codename", ""),
                "status": b.get("investigation_status")
            })

    context = (
        f"Node {node_id} at {node.get('lat', '?')}°N, {node.get('lng', '?')}°E\n"
        f"Classification: {node.get('classification', 'unknown')}\n"
        f"Current status: {brief.get('investigation_status', 'INCONCLUSIVE')}\n"
        f"Existing matches: {[m['signature_id'] for m in scored_entry.get('matches', [])]}\n"
        f"Situation: {brief.get('situation', 'No brief available')}\n"
        f"Nearest confirmed sites: {confirmed_sites[:5]}\n"
    )

    prompt = (
        "You are a research director deciding WHERE to invest limited investigation resources.\n\n"
        f"LOCATION: {context}\n\n"
        "Generate an INVESTIGATION RATIONALE explaining WHY this location deserves investigation.\n"
        "Be specific and quantitative where possible.\n\n"
        "Cover:\n"
        "1. PROBABILITY FACTORS: What specifically increases the likelihood of a discovery here?\n"
        "2. ANALOGOUS PRECEDENT: Name a similar location where investigation produced results\n"
        "3. SPECIFIC PREDICTION: What would you expect to find, based on the evidence?\n"
        "4. RECOMMENDED METHOD: LiDAR, dive survey, GPR, excavation, satellite imagery?\n"
        "5. CONFIDENCE: Low/Medium/High that investigation would produce a significant find\n\n"
        "Return ONLY valid JSON (no markdown):\n"
        '{"probability_factors": ["factor 1", "factor 2"], '
        '"analogous_precedent": "Similar site X produced Y", '
        '"prediction": "Expect to find Z based on W", '
        '"recommended_method": "method + estimated cost", '
        '"confidence": "low|medium|high", '
        '"one_line_hook": "One compelling sentence for why to investigate here"}'
    )

    try:
        resp = bedrock.invoke_model(
            modelId=MODEL, contentType="application/json", accept="application/json",
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 1200,
                "messages": [{"role": "user", "content": prompt}]
            })
        )
        body = json.loads(resp["body"].read())
        raw = ""
        for block in body.get("content", []):
            if block.get("type") == "text":
                raw = block["text"].strip()
                break
        # Parse with truncation repair
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0].strip()
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0].strip()
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            # Truncation repair
            for trim_to in [raw.rfind('"}'), raw.rfind('}'), raw.rfind('"]')]:
                if trim_to <= 0:
                    continue
                candidate = raw[:trim_to + 1]
                candidate += "]" * max(0, candidate.count("[") - candidate.count("]"))
                candidate += "}" * max(0, candidate.count("{") - candidate.count("}"))
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    continue
            print(f"    Parse failed ({len(raw)} chars)")
            return None
    except Exception as e:
        print(f"    Error: {e}")
        return None


def main():
    # Load existing rationales to skip already-done nodes
    output_path = os.path.join(DATA_DIR, "investigation-rationales.json")
    if os.path.exists(output_path):
        with open(output_path) as f:
            results = json.load(f)
    else:
        results = {}

    # Only process nodes not already done
    to_process = [nid for nid in TARGET_NODES if str(nid) not in results]
    print(f"Generating investigation rationales for {len(to_process)} remaining nodes...")
    print(f"(Already have {len(results)} cached)")
    print("=" * 60)

    for nid in to_process:
        print(f"  [{nid}] ...", end=" ")
        rationale = generate_rationale(nid)
        if rationale:
            results[str(nid)] = rationale
            print(f"OK ({rationale.get('confidence', '?')})")
        else:
            print("FAILED")
        time.sleep(1)

    # Save
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\n{'=' * 60}")
    print(f"Total rationales: {len(results)}")
    high = sum(1 for r in results.values() if r.get("confidence") == "high")
    med = sum(1 for r in results.values() if r.get("confidence") == "medium")
    print(f"  High confidence: {high}")
    print(f"  Medium confidence: {med}")
    print(f"  Saved: {output_path}")


if __name__ == "__main__":
    main()
