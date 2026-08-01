"""Taxonomy-Guided Research — Second pass with targeted signature-informed queries.

Unlike the generic batch_research_direct.py which asks "what's here?",
this script asks SPECIFIC questions from the taxonomy signatures:
- "Are there stones >10 tons within 100km?" (signature san-001)
- "Is there a measurable geomagnetic anomaly?" (signature ga-001)
- "Are there geometric structures on the seafloor?" (signature se-001)
- "Do indigenous traditions consider this sacred?" (signature cm-001)

This produces higher-quality findings that directly map to signatures.

Usage:
    python scripts/batch_research_taxonomy_guided.py --limit 5
    python scripts/batch_research_taxonomy_guided.py --node 7
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

# Load grid + taxonomy
with open(os.path.join(DATA_DIR, "uvg-grid-investigation-database.json"), encoding="utf-8") as f:
    grid_db = json.load(f)

with open(os.path.join(DATA_DIR, "grid-investigation-taxonomy.json"), encoding="utf-8") as f:
    taxonomy = json.load(f)

bedrock = boto3.client("bedrock-runtime", region_name="us-east-1",
                       config=Config(read_timeout=90, connect_timeout=10, retries={"max_attempts": 2}))


def brave_search(query, count=4):
    import urllib.request, urllib.parse
    if not BRAVE_API_KEY: return []
    params = urllib.parse.urlencode({"q": query[:400], "count": count})
    url = f"https://api.search.brave.com/res/v1/web/search?{params}"
    req = urllib.request.Request(url)
    req.add_header("X-Subscription-Token", BRAVE_API_KEY)
    req.add_header("Accept", "application/json")
    try:
        resp = urllib.request.urlopen(req, timeout=12)
        data = json.loads(resp.read().decode())
        return [{"title": r.get("title",""), "snippet": r.get("description","")[:300]}
                for r in data.get("web",{}).get("results",[])[:count]]
    except:
        return []


def invoke_sonnet(system, user_msg, max_tokens=1000):
    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": user_msg}],
        "temperature": 0.3,
    }
    resp = bedrock.invoke_model(modelId=SONNET_MODEL, contentType="application/json",
                                accept="application/json", body=json.dumps(body))
    resp_body = json.loads(resp["body"].read().decode())
    for block in resp_body.get("content", []):
        if block.get("type") == "text":
            return block.get("text", "")
    return resp_body.get("content", [{}])[0].get("text", "")


def parse_json(raw):
    if not raw: return {}
    text = raw.strip()
    if text.startswith("```"): text = text.split("\n", 1)[-1]
    idx = text.find("{")
    if idx == -1: return {}
    text = text[idx:]
    bc = 0
    for i, ch in enumerate(text):
        if ch == "{": bc += 1
        elif ch == "}":
            bc -= 1
            if bc == 0:
                try: return json.loads(text[:i+1])
                except: break
    # Repair truncated
    for t in [text.rfind('},'), text.rfind('}'), text.rfind('"]')]:
        if t <= 0: continue
        c = text[:t+1]
        c += "]" * max(0, c.count("[") - c.count("]"))
        c += "}" * max(0, c.count("{") - c.count("}"))
        try: return json.loads(c)
        except: continue
    return {}


def build_taxonomy_queries(node):
    """Build search queries directly from taxonomy signature indicators."""
    lat, lng = node["lat"], node["lng"]
    classification = node["classification"]
    continent = node.get("continent", "")
    
    queries = []
    
    if classification == "ocean":
        # Use submerged evidence signatures
        queries = [
            f"sonar bathymetric survey geometric structure seafloor near {lat:.0f} {lng:.0f}",
            f"sunken civilization legend ancient text lost land near latitude {lat:.0f} longitude {lng:.0f}",
            f"ship disappearance electromagnetic anomaly compass malfunction near {lat:.0f} {lng:.0f}",
            f"submerged continental shelf plateau river channels depth less 200m near {lat:.0f} {lng:.0f}",
        ]
    else:
        # Use land-based signatures
        queries = [
            # san-001: Megalithic
            f"megalith dolmen large stone blocks ancient construction near {lat:.0f} {lng:.0f} {continent}",
            # san-002: Pyramid/mound
            f"pyramid mound tumulus astronomical alignment solstice near {lat:.0f} {lng:.0f} {continent}",
            # ga-001: Geomagnetic
            f"geomagnetic anomaly compass deviation magnetic measurement near {lat:.0f} {lng:.0f}",
            # cm-001: Indigenous sacred
            f"indigenous sacred site forbidden place traditional ceremony near {lat:.0f} {lng:.0f} {continent}",
        ]
    
    return queries


# System prompt that knows EXACTLY what signatures to look for
TAXONOMY_SYSTEM_PROMPT = """You are an investigative researcher scoring a location against specific archaeological evidence signatures.

For each signature below, determine if the search results provide evidence of it at this location. Score each as: MATCH (clear evidence), POSSIBLE (suggestive but not confirmed), or NO_MATCH.

SIGNATURES TO CHECK:
- MEGALITHIC: Stone blocks >10 tons, precision fitting, no local quarry source
- PYRAMID_MOUND: Pyramid or mound shape, astronomical alignment, monumental scale
- STONE_CIRCLE: Circular stone arrangement, diameter encodes Earth fraction
- UNDERGROUND: Artificial chambers/tunnels, cut stone walls, unknown purpose
- GEOMAGNETIC: Measurable magnetic deviation, compass anomalies, persistent
- GEOMETRIC_FORMATION: Circular/geometric landform visible from satellite
- TECTONIC: Plate boundary, fault line, volcanic features within 100km
- SUBMERGED_STRUCTURE: Geometric patterns on seafloor, right angles
- SUNKEN_MYTH: Ancient texts describing lost civilization here
- MARITIME_ANOMALY: Ship/aircraft disappearances, electromagnetic reports
- ICE_AGE_LAND: Shallow plateau <200m depth, river channels
- INDIGENOUS_SACRED: Designated sacred/forbidden for 500+ years
- MULTI_CULTURAL: Multiple unrelated cultures call this place significant
- CREATION_MYTH: Origin story matches this location

Return ONLY valid JSON:
{"codename": "name", "investigation_status": "CONFIRMED|PROBABLE|INCONCLUSIVE|NEGATIVE", "situation": "2-3 sentences", "signature_scores": [{"signature": "MEGALITHIC", "score": "MATCH|POSSIBLE|NO_MATCH", "evidence": "what was found"}], "smoking_gun": "best finding", "field_recommendation": "next step"}"""


def research_node_guided(node):
    """Research a node with taxonomy-guided queries and signature-aware synthesis."""
    queries = build_taxonomy_queries(node)
    
    # Search
    all_results = []
    for q in queries:
        results = brave_search(q, count=3)
        all_results.extend(results)
    
    # Deduplicate
    seen = set()
    unique = []
    for r in all_results:
        key = r.get("title", "")[:50]
        if key not in seen:
            seen.add(key)
            unique.append(r)
    
    # Synthesize with taxonomy-aware prompt
    results_text = "\n".join(f"[{i+1}] {r['title']} | {r['snippet']}" for i, r in enumerate(unique[:10]))
    if not results_text:
        results_text = "No search results. Use training knowledge only."
    
    user_msg = (
        f"Location: UVG Node {node['id']} at {node['lat']:.2f}°, {node['lng']:.2f}° "
        f"({node.get('continent','ocean')})\n"
        f"Classification: {node['classification']}\n\n"
        f"Search results:\n{results_text}"
    )
    
    raw = invoke_sonnet(TAXONOMY_SYSTEM_PROMPT, user_msg, max_tokens=800)
    return parse_json(raw)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--node", type=int, help="Research specific node ID")
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()
    
    nodes = grid_db["nodes"]
    
    if args.node:
        targets = [n for n in nodes if n["id"] == args.node]
    elif args.all:
        targets = nodes
        args.limit = 62
    else:
        targets = nodes
    
    limit = min(args.limit, len(targets))
    
    print(f"Taxonomy-Guided Research (signature-informed queries)")
    print(f"  Model: {SONNET_MODEL}")
    print(f"  Signatures checked per node: 14")
    print(f"  Targets: {limit}")
    print()
    
    if not BRAVE_API_KEY:
        print("ERROR: Set BRAVE_SEARCH_API_KEY env var!")
        return
    
    results = []
    for i, node in enumerate(targets[:limit]):
        label = node.get("nearest_known_site") or node.get("continent") or "ocean"
        print(f"[{i+1}/{limit}] Node {node['id']} ({label})")
        
        t0 = time.time()
        try:
            brief = research_node_guided(node)
            elapsed = time.time() - t0
            
            # Show signature matches
            scores = brief.get("signature_scores", [])
            matches = [s for s in scores if s.get("score") == "MATCH"]
            possibles = [s for s in scores if s.get("score") == "POSSIBLE"]
            
            print(f"  {brief.get('codename','?')} | {brief.get('investigation_status','?')} | {elapsed:.1f}s")
            if matches:
                print(f"  ✅ MATCHES: {', '.join(m['signature'] for m in matches)}")
            if possibles:
                print(f"  ⚠️  POSSIBLE: {', '.join(p['signature'] for p in possibles)}")
            gun = brief.get("smoking_gun", "")
            if gun and "No definitive" not in gun:
                print(f"  💡 {gun[:100]}")
                
        except Exception as e:
            brief = {"error": str(e)[:200]}
            elapsed = time.time() - t0
            print(f"  ❌ {str(e)[:80]}")
        
        results.append({
            "node_id": node["id"],
            "lat": node["lat"],
            "lng": node["lng"],
            "classification": node["classification"],
            "brief": brief,
        })
        
        if i < limit - 1:
            time.sleep(2)
    
    # Save
    output_path = os.path.join(DATA_DIR, "uvg-grid-taxonomy-guided-results.json")
    output = {
        "name": "UVG Grid — Taxonomy-Guided Research",
        "description": "Research findings scored against 14 investigation signatures per node",
        "total": len(results),
        "results": results,
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    
    # Summary
    all_matches = []
    for r in results:
        for s in r.get("brief", {}).get("signature_scores", []):
            if s.get("score") == "MATCH":
                all_matches.append(s["signature"])
    
    if all_matches:
        print(f"\nSIGNATURE MATCH SUMMARY:")
        from collections import Counter
        for sig, count in Counter(all_matches).most_common():
            print(f"  {sig}: {count} nodes")
    
    print(f"\nSaved: {output_path}")


if __name__ == "__main__":
    main()
