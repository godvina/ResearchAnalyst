"""Batch research grid nodes by calling Bedrock + Brave DIRECTLY (no API Gateway).

This bypasses the 29s timeout by running locally with direct AWS SDK calls.
For each node, does 3 Brave searches + 1 Sonnet synthesis.

Usage:
    python scripts/batch_research_direct.py --limit 5
    python scripts/batch_research_direct.py --ocean-only --limit 10
    python scripts/batch_research_direct.py --all
"""

import argparse
import json
import os
import sys
import time

import boto3
from botocore.config import Config

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "src", "data")
BRAVE_API_KEY = os.environ.get("BRAVE_SEARCH_API_KEY", os.environ.get("BRAVE_API_KEY", ""))
SONNET_MODEL = "us.anthropic.claude-sonnet-4-6"

# Load grid
with open(os.path.join(DATA_DIR, "uvg-grid-investigation-database.json")) as f:
    grid_db = json.load(f)

# Bedrock client
bedrock = boto3.client("bedrock-runtime", region_name="us-east-1",
                       config=Config(read_timeout=90, connect_timeout=10, retries={"max_attempts": 2}))


def brave_search(query, count=5):
    """Execute a Brave search."""
    import urllib.request, urllib.parse
    if not BRAVE_API_KEY:
        return []
    params = urllib.parse.urlencode({"q": query[:400], "count": count})
    url = f"https://api.search.brave.com/res/v1/web/search?{params}"
    req = urllib.request.Request(url)
    req.add_header("X-Subscription-Token", BRAVE_API_KEY)
    req.add_header("Accept", "application/json")
    try:
        resp = urllib.request.urlopen(req, timeout=12)
        data = json.loads(resp.read().decode())
        return [{"title": r.get("title",""), "url": r.get("url",""), "snippet": r.get("description","")[:300]}
                for r in data.get("web",{}).get("results",[])[:count]]
    except Exception as e:
        return []


def invoke_sonnet(system_prompt, user_message, max_tokens=1000):
    """Call Sonnet directly via Bedrock SDK."""
    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_message}],
        "temperature": 0.4,
    }
    resp = bedrock.invoke_model(modelId=SONNET_MODEL, contentType="application/json",
                                accept="application/json", body=json.dumps(body))
    resp_body = json.loads(resp["body"].read().decode())
    # Handle extended thinking
    text = ""
    for block in resp_body.get("content", []):
        if block.get("type") == "text":
            text = block.get("text", "")
            break
    if not text and resp_body.get("content"):
        text = resp_body["content"][0].get("text", "")
    return text


def parse_json(raw):
    """Parse JSON from model output, handling truncation."""
    import re
    if not raw: return {}
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].strip()
    idx = text.find("{")
    if idx == -1: return {}
    text = text[idx:]
    # Try full parse
    brace_count = 0
    end_idx = -1
    for i, ch in enumerate(text):
        if ch == "{": brace_count += 1
        elif ch == "}":
            brace_count -= 1
            if brace_count == 0: end_idx = i; break
    if end_idx >= 0:
        try: return json.loads(text[:end_idx+1])
        except: pass
    # Truncated: repair
    for trim_to in [text.rfind('},'), text.rfind('}'), text.rfind('"]')]:
        if trim_to <= 0: continue
        candidate = text[:trim_to+1]
        ob = candidate.count("[") - candidate.count("]")
        candidate += "]" * max(0, ob)
        oc = candidate.count("{") - candidate.count("}")
        candidate += "}" * max(0, oc)
        try: return json.loads(candidate)
        except: continue
    return {}


SYSTEM_PROMPT = """You are a senior investigative researcher. Synthesize search results into a JSON investigation brief.

Return ONLY valid JSON (no markdown, no backticks):
{"codename": "short name", "investigation_status": "CONFIRMED or PROBABLE or INCONCLUSIVE or NEGATIVE", "situation": "2-3 sentences on what exists at this location", "smoking_gun": "single most compelling finding or No definitive evidence found", "evidence_found": [{"source_type": "type", "finding": "what was found", "confidence": "confirmed or probable or unverified"}], "undiscovered_sites": [{"location": "place", "rationale": "why investigate"}], "field_recommendation": "next step for a team"}

Be specific. Name real places, researchers, formations. If ocean: look for submerged structures, myths, anomalies. If nothing found, say so clearly."""


def research_node(node):
    """Research a single grid node using Brave + Sonnet directly."""
    lat, lng = node["lat"], node["lng"]
    classification = node["classification"]
    continent = node.get("continent", "")

    # Build creative queries based on node type
    if classification == "ocean":
        queries = [
            f"submerged ruins underwater structure near {lat:.0f} {lng:.0f}",
            f"sunken city Atlantis Lemuria legend myth near latitude {lat:.0f} longitude {lng:.0f}",
            f"bathymetric anomaly sonar discovery ocean floor {lat:.0f} {lng:.0f}",
        ]
        context = f"Ocean grid node at {lat:.2f}°, {lng:.2f}°. What's underwater here?"
    elif classification == "unexplored_land":
        queries = [
            f"ancient ruins megalith sacred site near {lat:.0f} {lng:.0f} {continent}",
            f"archaeological discovery LiDAR survey {continent} {lat:.0f} latitude",
            f"indigenous sacred site folklore buried city {continent} near {lat:.0f} {lng:.0f}",
        ]
        context = f"Land grid node at {lat:.2f}°, {lng:.2f}° ({continent}). What ancient sites are here?"
    else:
        site = node.get("nearest_known_site", "")
        queries = [
            f"{site} alignment connection other ancient sites grid line",
            f"{site} undiscovered nearby ruins additional sites not excavated",
            f"{site} shared construction technique with distant ancient sites",
        ]
        context = f"Known site: {site}. What connects it to other grid sites?"

    # Execute searches
    all_results = []
    for q in queries:
        results = brave_search(q, count=4)
        all_results.extend(results)

    # Deduplicate
    seen = set()
    unique = []
    for r in all_results:
        if r["url"] not in seen:
            seen.add(r["url"])
            unique.append(r)

    # Synthesize with Sonnet
    if unique:
        results_text = "\n".join(f"[{i+1}] {r['title']} | {r['snippet']}" for i, r in enumerate(unique[:10]))
    else:
        results_text = "No search results available. Use training knowledge only."

    user_msg = f"Node {node['id']} | {lat:.2f}°, {lng:.2f}° | {classification} | {context}\n\nSearch results:\n{results_text}"

    raw = invoke_sonnet(SYSTEM_PROMPT, user_msg, max_tokens=800)
    brief = parse_json(raw)
    brief["_sources_count"] = len(unique)
    return brief


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--ocean-only", action="store_true")
    parser.add_argument("--land-only", action="store_true")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--start-at", type=int, default=0, help="Skip first N nodes")
    args = parser.parse_args()

    nodes = grid_db["nodes"]
    if args.ocean_only:
        targets = [n for n in nodes if n["classification"] == "ocean"]
    elif args.land_only:
        targets = [n for n in nodes if n["classification"] != "ocean"]
    elif args.all:
        targets = nodes
        args.limit = 62
    else:
        targets = sorted(nodes, key=lambda n: 0 if n["classification"] == "unexplored_land" else 1)

    targets = targets[args.start_at:]
    limit = min(args.limit, len(targets))

    print(f"Direct Batch Research (Bedrock + Brave, no API Gateway)")
    print(f"  Model: {SONNET_MODEL}")
    print(f"  Targets: {limit} nodes")
    print(f"  Brave API key: {'SET' if BRAVE_API_KEY else 'MISSING'}")
    print()

    if not BRAVE_API_KEY:
        print("ERROR: Set BRAVE_SEARCH_API_KEY environment variable!")
        print("  $env:BRAVE_SEARCH_API_KEY = 'your-key-here'")
        return

    results = []
    for i, node in enumerate(targets[:limit]):
        label = node.get("nearest_known_site") or node.get("continent") or "ocean"
        print(f"[{i+1}/{limit}] Node {node['id']} ({node['classification']}) — {label}")

        t0 = time.time()
        try:
            brief = research_node(node)
            elapsed = time.time() - t0

            if brief.get("codename"):
                status = brief.get("investigation_status", "?")
                gun = brief.get("smoking_gun", "")
                print(f"  ✅ {brief['codename']} | {status} | {elapsed:.1f}s")
                if gun and "No definitive" not in gun:
                    print(f"     💡 {gun[:100]}")
            else:
                print(f"  ⚠️  Partial result ({elapsed:.1f}s)")
        except Exception as e:
            brief = {"error": str(e)[:200]}
            print(f"  ❌ {str(e)[:80]}")

        results.append({
            "node_id": node["id"],
            "lat": node["lat"],
            "lng": node["lng"],
            "classification": node["classification"],
            "brief": brief,
            "researched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        })

        if i < limit - 1:
            time.sleep(2)

    # Save
    output_path = os.path.join(DATA_DIR, "uvg-grid-research-all-nodes.json")

    # Merge with existing results if any
    existing = {}
    if os.path.exists(output_path):
        with open(output_path) as f:
            existing_data = json.load(f)
            for r in existing_data.get("results", []):
                existing[r["node_id"]] = r

    for r in results:
        existing[r["node_id"]] = r

    output = {
        "name": "UVG Grid Research — All Nodes (Direct Bedrock)",
        "total_researched": len(existing),
        "results": sorted(existing.values(), key=lambda r: r["node_id"]),
    }
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)

    successful = [r for r in results if r.get("brief", {}).get("codename")]
    print(f"\nDone! {len(successful)}/{len(results)} successful.")
    print(f"Total researched (cumulative): {len(existing)}")
    print(f"Saved: {output_path}")


if __name__ == "__main__":
    main()
